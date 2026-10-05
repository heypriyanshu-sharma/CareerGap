-- CareerGap: User Profiles
--
-- Creates a profiles table for storing user profile data.
-- Linked to auth.users with CASCADE delete.
-- RLS enforces user isolation.

-- ============================================================
-- TABLE
-- ============================================================

create table if not exists public.profiles (
    id uuid primary key references auth.users (id) on delete cascade,
    avatar_url text,
    full_name text,
    target_role text,
    experience_level text check (experience_level in ('student', 'junior', 'mid', 'senior', 'lead')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

comment on table public.profiles is 'User profile data. One row per authenticated user.';

-- ============================================================
-- TIMESTAMPS
-- ============================================================

create or replace function public.set_profile_updated_at()
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

drop trigger if exists profiles_set_updated_at on public.profiles;

create trigger profiles_set_updated_at
    before update on public.profiles
    for each row
    execute function public.set_profile_updated_at();

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================

alter table public.profiles enable row level security;

drop policy if exists "profiles_select_own" on public.profiles;
drop policy if exists "profiles_insert_own" on public.profiles;
drop policy if exists "profiles_update_own" on public.profiles;
drop policy if exists "profiles_delete_own" on public.profiles;

create policy "profiles_select_own"
    on public.profiles
    for select
    to authenticated
    using ((select auth.uid()) = id);

create policy "profiles_insert_own"
    on public.profiles
    for insert
    to authenticated
    with check ((select auth.uid()) = id);

create policy "profiles_update_own"
    on public.profiles
    for update
    to authenticated
    using ((select auth.uid()) = id)
    with check ((select auth.uid()) = id);

create policy "profiles_delete_own"
    on public.profiles
    for delete
    to authenticated
    using ((select auth.uid()) = id);

-- ============================================================
-- TABLE GRANTS
-- ============================================================

grant select, insert, update, delete on public.profiles to authenticated;

-- ============================================================
-- AUTO-CREATE PROFILE ON USER SIGNUP
-- ============================================================

-- Creates an empty profile row when a new user signs up.
-- This ensures the profile exists for immediate use.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
    insert into public.profiles (id, full_name, avatar_url)
    values (
        new.id,
        new.raw_user_meta_data->>'full_name',
        new.raw_user_meta_data->>'avatar_url'
    );
    return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
    after insert on auth.users
    for each row
    execute function public.handle_new_user();