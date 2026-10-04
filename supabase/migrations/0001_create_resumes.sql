-- CareerGap: ATS-friendly Resume Builder
--
-- STATUS: PROPOSAL ONLY. This migration has NOT been applied.
-- It must be reviewed and applied manually before the resume API works.
--
-- Apply from the Supabase dashboard (SQL editor) or with
-- `supabase db push` / `psql`. It is additive: it creates one new
-- table, one trigger, three functions and two indexes. It does not
-- alter or drop any existing object, so it is safe to run alongside
-- the existing `career_analyses` table.
--
-- Ownership is enforced in the database with row level security. The
-- API also filters by user id, but RLS is the authority: even a
-- compromised or buggy API cannot read or write another user's rows.
--
-- Every function below is SECURITY INVOKER, so the caller's own RLS
-- context applies. Each also re-checks `auth.uid()` against the
-- caller_id argument so a mismatched token cannot act on another user.

-- ============================================================
-- TABLE
-- ============================================================

create table if not exists public.resumes (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users (id) on delete cascade,
    title text not null,
    content jsonb not null default '{}'::jsonb,
    plain_text text not null default '',
    is_default boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint resumes_title_length
        check (char_length(btrim(title)) between 1 and 120),

    constraint resumes_plain_text_length
        check (char_length(plain_text) <= 60000),

    constraint resumes_content_is_object
        check (jsonb_typeof(content) = 'object')
);

comment on table public.resumes is
    'User-authored resumes. content holds structured editor data; '
    'plain_text is generated server-side for ATS parsing.';

-- ============================================================
-- TIMESTAMPS
-- ============================================================

create or replace function public.set_resume_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = public
as $$
begin
    new.updated_at = now();

    return new;
end;
$$;

drop trigger if exists resumes_set_updated_at on public.resumes;

create trigger resumes_set_updated_at
    before update on public.resumes
    for each row
    execute function public.set_resume_updated_at();

-- ============================================================
-- ONE DEFAULT RESUME PER USER
-- ============================================================

create unique index if not exists resumes_one_default_per_user
    on public.resumes (user_id)
    where is_default;

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

alter table public.resumes enable row level security;

-- The policies are recreated so this file can be re-run safely.
drop policy if exists "resumes_select_own" on public.resumes;
drop policy if exists "resumes_insert_own" on public.resumes;
drop policy if exists "resumes_update_own" on public.resumes;
drop policy if exists "resumes_delete_own" on public.resumes;

create policy "resumes_select_own"
    on public.resumes
    for select
    to authenticated
    using ((select auth.uid()) = user_id);

create policy "resumes_insert_own"
    on public.resumes
    for insert
    to authenticated
    with check ((select auth.uid()) = user_id);

create policy "resumes_update_own"
    on public.resumes
    for update
    to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

create policy "resumes_delete_own"
    on public.resumes
    for delete
    to authenticated
    using ((select auth.uid()) = user_id);

-- ============================================================
-- TABLE GRANTS
-- ============================================================

grant select, insert, update, delete on public.resumes to authenticated;

-- ============================================================
-- SHARED AUTHORIZATION GUARD
-- ============================================================

-- Raises 42501 (insufficient_privilege) when the caller's token does
-- not belong to caller_id. Defence in depth: ownership still comes
-- from auth.uid(), never from a value the client chose.
create or replace function public.assert_resume_owner(
    caller_id uuid
)
returns void
language plpgsql
security invoker
set search_path = public
as $$
begin
    if (select auth.uid()) is distinct from caller_id then
        raise exception 'Not authorized.'
            using errcode = '42501';
    end if;
end;
$$;

-- ============================================================
-- ATOMIC DEFAULT SWITCH
-- ============================================================

-- Clears the caller's previous default and sets the new one in one
-- transaction. The target row is verified and locked BEFORE any
-- mutation, so a missing or unowned id changes nothing.
--
-- The advisory lock serializes concurrent default switches for the
-- same user. If a caller bypasses these functions and writes
-- is_default directly, the partial unique index can still raise
-- 23505; the API maps that to 409 rather than hiding it.
create or replace function public.set_default_resume(
    caller_id uuid,
    resume_id uuid
)
returns void
language plpgsql
security invoker
set search_path = public
as $$
declare
    target_user uuid;
begin
    perform public.assert_resume_owner(caller_id);

    -- Serialize default switches for this user.
    perform pg_advisory_xact_lock(
        hashtext(caller_id::text)
    );

    select user_id into target_user
      from public.resumes
     where id = resume_id
       and user_id = caller_id
       for update;

    if target_user is null then
        raise exception 'Resume not found.'
            using errcode = 'P0002';
    end if;

    update public.resumes
       set is_default = false
     where user_id = caller_id
       and is_default = true
       and id <> resume_id;

    update public.resumes
       set is_default = true
     where id = resume_id
       and user_id = caller_id;
end;
$$;

-- ============================================================
-- TRANSACTIONAL WRITES
-- ============================================================

-- Insert plus optional default switch in a single transaction. The
-- insert never sets is_default directly, so the partial unique index
-- cannot reject it. If make_default is true and the switch fails, the
-- insert is rolled back and no resume is left behind.
create or replace function public.create_resume(
    caller_id uuid,
    resume_title text,
    resume_content jsonb,
    resume_plain_text text,
    make_default boolean default false
)
returns public.resumes
language plpgsql
security invoker
set search_path = public
as $$
declare
    new_resume public.resumes;
begin
    perform public.assert_resume_owner(caller_id);

    insert into public.resumes (
        user_id,
        title,
        content,
        plain_text,
        is_default
    )
    values (
        caller_id,
        resume_title,
        resume_content,
        resume_plain_text,
        false
    )
    returning * into new_resume;

        if make_default then
        perform public.set_default_resume(
            caller_id,
            new_resume.id
        );

        select * into new_resume
          from public.resumes
         where id = new_resume.id
           and user_id = caller_id;
    end if;

    return new_resume;
end;
$$;

-- Update plus optional default switch in one transaction. If the
-- switch fails, the content update is rolled back as well, so a
-- resume is never left updated against the caller's intent.
create or replace function public.update_resume(
    caller_id uuid,
    resume_id uuid,
    resume_title text,
    resume_content jsonb,
    resume_plain_text text,
    make_default boolean default false
)
returns public.resumes
language plpgsql
security invoker
set search_path = public
as $$
declare
    target_user uuid;
    updated_resume public.resumes;
begin
    perform public.assert_resume_owner(caller_id);
    if make_default then
    perform pg_advisory_xact_lock(
        hashtext(caller_id::text)
    );
    end if;

    select user_id into target_user
      from public.resumes
     where id = resume_id
       and user_id = caller_id
     for update;

    if target_user is null then
        raise exception 'Resume not found.'
            using errcode = 'P0002';
    end if;

    update public.resumes
       set title = resume_title,
           content = resume_content,
           plain_text = resume_plain_text
     where id = resume_id
       and user_id = caller_id
    returning * into updated_resume;

    if make_default then
        perform public.set_default_resume(
            caller_id,
            resume_id
        );

        select * into updated_resume
          from public.resumes
         where id = resume_id;
    end if;

    return updated_resume;
end;
$$;

-- ============================================================
-- FUNCTION GRANTS
-- ============================================================

revoke all on function public.assert_resume_owner(uuid) from public;
revoke all on function public.set_default_resume(uuid, uuid) from public;
revoke all on function public.create_resume(uuid, text, jsonb, text, boolean) from public;
revoke all on function public.update_resume(uuid, uuid, text, jsonb, text, boolean) from public;

grant execute on function public.assert_resume_owner(uuid) to authenticated;
grant execute on function public.set_default_resume(uuid, uuid) to authenticated;
grant execute on function public.create_resume(uuid, text, jsonb, text, boolean) to authenticated;
grant execute on function public.update_resume(uuid, uuid, text, jsonb, text, boolean) to authenticated;

-- ============================================================
-- ROLLBACK (run manually only if you must undo this migration)
-- ============================================================

-- drop table if exists public.resumes;