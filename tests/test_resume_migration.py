"""Structural tests for the resume migration.

The project has no PostgreSQL test database and no database driver, so
these tests assert the *text* of the migration: the statement order and
the locking discipline inside each function. They deliberately do not
claim to prove runtime behaviour. Transaction rollback, index
enforcement and real deadlock avoidance still require applying the
migration to a live Supabase project.
"""

from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "0001_create_resumes.sql"
)

MIGRATION = MIGRATION_PATH.read_text(encoding="utf-8")


ADVISORY_LOCK = "pg_advisory_xact_lock"

ADVISORY_KEY = "hashtext(caller_id::text)"

ROW_LOCK = "for update"


def function_body(name: str) -> str:
    """Return the body of one migration function."""

    return function_declaration(name).split(
        "as $$",
        1,
    )[1]


def function_declaration(name: str) -> str:
    """Return the whole declaration, including its header.

    The slice stops before the closing `$$;`, so the body returned by
    function_body is the text between the two dollar-quote markers.
    """

    header = f"create or replace function public.{name}("

    assert header in MIGRATION, f"{name} is not defined"

    start = MIGRATION.index(header)

    end = MIGRATION.index(
        "$$;",
        MIGRATION.index("as $$", start),
    )

    return MIGRATION[start:end]


def normalized(text: str) -> str:
    """Collapse whitespace so a statement can be matched as one line."""

    return " ".join(text.split())


def statement_from(body: str, start: int) -> str:
    """Return the SQL statement that begins at start."""

    return body[start:body.index(";", start)]


def switch_call_position(body: str) -> int:
    return body.index("perform public.set_default_resume(")


# ============================================================
# DEFAULT SWITCH IS DELEGATED
# ============================================================

def test_write_functions_delegate_to_the_shared_switch():
    """Both writers use one implementation of the switch.

    The advisory lock and the row ordering live inside
    set_default_resume, so a writer that did not call it would skip the
    serialization entirely.
    """

    for name in ("create_resume", "update_resume"):

        assert "perform public.set_default_resume(" in (
            function_body(name)
        )


def test_set_default_resume_verifies_ownership_before_mutating():
    body = function_body("set_default_resume")

    assert (
        body.index("perform public.assert_resume_owner(caller_id);")
        < body.index(ROW_LOCK)
    )
    assert body.index(ROW_LOCK) < body.index("set is_default = false")


# ============================================================
# LOCKING ORDER
# ============================================================

def test_advisory_lock_precedes_the_row_lock_in_set_default_resume():
    body = function_body("set_default_resume")

    assert body.index(ADVISORY_LOCK) < body.index(ROW_LOCK)


def test_advisory_lock_precedes_the_row_lock_in_update_resume():
    """The advisory lock must come before any row lock.

    Taking the row lock first inverts the order used by
    set_default_resume. A writer then holds its own row while waiting
    for the advisory lock, and the switch inside that lock needs to
    clear the previous default, which can be exactly the row the other
    transaction is holding. That pair deadlocks.
    """

    body = function_body("update_resume")

    assert body.index(ADVISORY_LOCK) < body.index(ROW_LOCK)


def test_both_functions_lock_in_the_same_order():
    """update_resume and set_default_resume must agree on the order."""

    orders = {}

    for name in ("update_resume", "set_default_resume"):

        body = function_body(name)

        advisory_at = body.index(ADVISORY_LOCK)
        row_at = body.index(ROW_LOCK)

        assert advisory_at != row_at

        orders[name] = (
            "advisory"
            if advisory_at < row_at
            else "row"
        )

    assert set(orders.values()) == {"advisory"}


def test_both_functions_lock_on_the_same_key():
    """A different key expression would silently not serialize.

    Mutual exclusion only works while every default switch for one
    user contends on one advisory lock, so the key expression has to
    be identical in both functions.
    """

    for name in ("update_resume", "set_default_resume"):

        body = function_body(name)

        lock_at = body.index(ADVISORY_LOCK)

        assert ADVISORY_KEY in body[lock_at:lock_at + 120]


def test_update_resume_locks_only_when_making_a_default():
    """A plain update must not serialize behind the default switch."""

    body = function_body("update_resume")

    lock_at = body.index(ADVISORY_LOCK)

    guard_at = body.rindex(
        "if make_default then",
        0,
        lock_at,
    )

    # Only whitespace and the perform keyword of the lock call itself
    # may sit between the guard and the lock, so the lock is the
    # guarded statement rather than an unconditional one.
    between = body[
        guard_at + len("if make_default then"):lock_at
    ]

    assert between.strip() in ("", "perform")


# ============================================================
# REFRESHED RETURN VALUE
# ============================================================

def test_create_resume_returns_the_row_reloaded_after_the_switch():
    """The returned record must reflect the switch, not the insert.

    The insert always writes is_default false, so the composite record
    captured by `returning *` is stale the moment the switch runs. The
    reload is what makes the response say is_default true.
    """

    body = function_body("create_resume")

    inserted_at = body.index("returning * into new_resume")
    switch_at = switch_call_position(body)

    assert inserted_at < switch_at

    reload_statement = statement_from(
        body,
        body.index("select * into new_resume", switch_at),
    )

    assert "from public.resumes" in reload_statement
    assert "id = new_resume.id" in reload_statement
    assert "user_id = caller_id" in reload_statement


def test_update_resume_returns_the_row_reloaded_after_the_switch():
    body = function_body("update_resume")

    switch_at = switch_call_position(body)

    reload_statement = statement_from(
        body,
        body.index("select * into updated_resume", switch_at),
    )

    assert "from public.resumes" in reload_statement
    assert "id = resume_id" in reload_statement


def test_create_resume_never_writes_a_default_on_insert():
    """The insert must not set is_default true.

    The partial unique index allows only one default per user, so an
    insert that claimed the flag could collide with the existing
    default and fail with 23505 before the switch is ever attempted.
    """

    body = function_body("create_resume")

    insert = statement_from(
        body,
        body.index("insert into public.resumes"),
    )

    assert "is_default" in insert

    values = insert[insert.index("values"):].lower()

    assert "true" not in values
    assert "false" in values


# ============================================================
# ROLLBACK SAFETY
# ============================================================

def test_write_functions_do_not_swallow_failures():
    """No exception handler may commit a partial write.

    Rollback of a failed switch depends on the error leaving the
    function uncaught: an exception block in plpgsql would let
    create_resume commit the insert, or update_resume commit the
    content change, after the switch failed. Raising is fine, handling
    is not, so the legitimate `raise exception` statements are removed
    before the check.
    """

    for name in (
        "set_default_resume",
        "create_resume",
        "update_resume",
    ):

        body = function_body(name).lower()

        body = body.replace("raise exception", "")

        assert "exception" not in body

    assert "raise exception" in function_body(
        "assert_resume_owner"
    )


def test_missing_resume_raises_the_mapped_sqlstate():
    """P0002 is what the API maps to 404."""

    for name in ("set_default_resume", "update_resume"):

        body = function_body(name)

        assert "errcode = 'P0002'" in body


def test_ownership_mismatch_raises_the_mapped_sqlstate():
    """42501 is what the API maps to 403."""

    assert "errcode = '42501'" in function_body(
        "assert_resume_owner"
    )


# ============================================================
# RLS AND CONSTRAINTS
# ============================================================

def test_functions_stay_security_invoker():
    """SECURITY DEFINER would bypass the caller's RLS policies."""

    for name in (
        "set_resume_updated_at",
        "assert_resume_owner",
        "set_default_resume",
        "create_resume",
        "update_resume",
    ):

        assert "security invoker" in function_declaration(name)


def test_one_default_per_user_is_enforced_by_a_partial_index():
    assert (
        "create unique index if not exists resumes_one_default_per_user"
        " on public.resumes (user_id) where is_default"
        in normalized(MIGRATION)
    )


def test_table_enables_row_level_security():
    assert (
        "alter table public.resumes enable row level security"
        in normalized(MIGRATION)
    )


def test_migration_is_still_marked_as_not_applied():
    assert "has NOT been applied" in MIGRATION
