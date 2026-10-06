"""Tests for the password recovery and change-password flows.

Password operations belong to Supabase Auth: the login page asks
Supabase to email a reset link, the reset page and the profile
page both set a new password through the authenticated session.
These tests assert the frontend wiring, that no password ever
reaches the FastAPI backend or the profiles table, and that the
current password is never requested, read or displayed.
"""

import re
from pathlib import Path

import pytest


FRONTEND_DIR = (
    Path(__file__).resolve().parent.parent / "frontend"
)

LOGIN_HTML = FRONTEND_DIR / "login.html"
LOGIN_JS = FRONTEND_DIR / "login.js"
LOGIN_CSS = FRONTEND_DIR / "login.css"
RESET_HTML = FRONTEND_DIR / "reset-password.html"
RESET_JS = FRONTEND_DIR / "reset-password.js"
PROFILE_HTML = FRONTEND_DIR / "profile.html"
PROFILE_JS = FRONTEND_DIR / "profile.js"
MIGRATION = (
    Path(__file__).resolve().parent.parent
    / "supabase"
    / "migrations"
    / "0002_create_profiles.sql"
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _compact(source):
    return re.sub(r"\s+", "", source)


def _strip_strings(source):
    """Replace string and template literals with empty
    strings, so a word inside a message cannot be
    mistaken for a bare identifier."""

    return re.sub(
        r'"(?:[^"\\]|\\.)*"'
        r"|'(?:[^'\\]|\\.)*'"
        r"|`(?:[^`\\]|\\.)*`",
        '""',
        source,
    )


def _extract_function(source, name):
    """Return the body of a named function declaration,
    brace-matched so nested braces do not end it early."""

    match = re.search(
        r"function\s+" + re.escape(name) + r"\s*\(",
        source,
    )

    if match is None:
        return ""

    open_idx = source.index("{", match.end())

    depth = 0
    i = open_idx

    while i < len(source):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1

            if depth == 0:
                return source[match.start() : i + 1]

        i += 1

    return ""


# ============================================================
# LOGIN — FORGOT PASSWORD
# ============================================================

class TestForgotPassword:

    def test_forgot_password_ui_exists(self):
        html = _read(LOGIN_HTML)

        assert 'id="forgot-password"' in html
        assert 'id="password-recovery"' in html
        assert 'id="recovery-email"' in html
        assert 'id="recovery-submit"' in html
        assert 'id="recovery-status"' in html
        assert 'id="recovery-back"' in html

    def test_recovery_form_uses_existing_design(self):
        html = _read(LOGIN_HTML)

        assert 'class="login-form hidden"' in html
        assert 'class="form-field"' in html
        assert 'class="login-button"' in html

    def test_forgot_password_triggers_recovery_flow(self):
        source = _read(LOGIN_JS)

        assert "resetPasswordForEmail" in source

    def test_recovery_uses_the_existing_supabase_client(self):
        source = _read(LOGIN_JS)

        assert (
            "careerGapSupabase.auth.resetPasswordForEmail"
            in _compact(source)
        )

    def test_recovery_redirect_targets_the_reset_page(self):
        """The redirect must resolve per environment, so it is
        derived from the page origin rather than hardcoded."""

        source = _read(LOGIN_JS)

        assert "window.location.origin" in source
        assert "reset-password.html" in source

        # No environment may be hardcoded into the other.
        assert "localhost" not in source
        assert "careergap.pages.dev" not in source

    def test_invalid_or_missing_email_is_handled(self):
        source = _read(LOGIN_JS)

        compact = _compact(source)

        assert "!recoveryEmail" in compact
        assert '!recoveryEmail.includes("@")' in compact

    def test_recovery_shows_generic_success_message(self):
        """The message must not reveal whether the address is
        registered, so account enumeration is not possible."""

        source = _read(LOGIN_JS)

        assert (
            "If an account exists for that email" in source
        )
        assert "a password reset link has been sent" in (
            source
        )

    def test_recovery_supabase_error_is_surfaced(self):
        source = _read(LOGIN_JS)

        compact = _compact(source)

        assert "if(error){" in compact
        assert "error.message" in source

    def test_normal_login_behaviour_is_unchanged(self):
        source = _read(LOGIN_JS)

        # The login submit handler still signs in with
        # the email and password the visitor typed.
        assert "signInWithPassword" in source
        assert "window.location.href" in source
        assert '"index.html"' in source

    def test_recovery_styles_exist(self):
        css = _read(LOGIN_CSS)

        assert ".recovery-status" in css
        assert ".recovery-status.success" in css
        assert ".recovery-status.error" in css
        assert ".hidden" in css


# ============================================================
# RESET PASSWORD PAGE
# ============================================================

class TestResetPasswordPage:

    def test_reset_page_exists(self):
        assert RESET_HTML.exists()
        assert RESET_JS.exists()

    def test_reset_page_uses_existing_design(self):
        html = _read(RESET_HTML)

        assert 'class="login-page"' in html
        assert 'class="login-card"' in html
        assert 'href="login.css"' in html
        assert 'src="supabase-config.js"' in html

    def test_reset_page_has_both_password_fields(self):
        html = _read(RESET_HTML)

        assert 'id="new-password"' in html
        assert 'id="confirm-new-password"' in html
        assert 'id="reset-submit"' in html
        assert 'id="reset-status"' in html

    def test_reset_requires_both_fields(self):
        source = _read(RESET_JS)

        compact = _compact(source)

        assert "!password||!confirmPassword" in compact
        assert "Both password fields are required" in (
            source
        )

    def test_reset_rejects_mismatched_passwords(self):
        source = _read(RESET_JS)

        assert "password!==confirmPassword" in (
            _compact(source)
        )
        assert "Passwords do not match" in source

    def test_reset_enforces_minimum_length(self):
        source = _read(RESET_JS)

        assert "MIN_PASSWORD_LENGTH" in source
        assert "password.length<MIN_PASSWORD_LENGTH" in (
            _compact(source)
        )

    def test_reset_calls_update_user_with_new_password(self):
        source = _read(RESET_JS)

        compact = _compact(source)

        assert (
            "careerGapSupabase.auth.updateUser" in compact
        )
        assert "password:password" in compact

    def test_reset_handles_failed_update(self):
        source = _read(RESET_JS)

        compact = _compact(source)

        assert "if(error){" in compact
        assert "Unable to update your password" in source

    def test_reset_redirects_to_login_after_success(self):
        source = _read(RESET_JS)

        assert "Password updated successfully" in source
        assert '"login.html"' in source

    def test_reset_rejects_missing_or_expired_session(self):
        """The form only works for a valid recovery session,
        so an expired or malformed link cannot set a password."""

        source = _read(RESET_JS)

        assert "getSession" in source
        assert "PASSWORD_RECOVERY" in source
        assert "invalid or has expired" in source

    def test_reset_form_starts_hidden(self):
        html = _read(RESET_HTML)

        assert 'class="login-form hidden"' in html

    def test_reset_does_not_expose_tokens(self):
        source = _read(RESET_JS)

        assert "access_token" not in source
        assert "refresh_token" not in source

    def test_reset_uses_the_existing_supabase_client(self):
        source = _read(RESET_JS)

        assert "create_client" not in source
        assert "createClient" not in source


# ============================================================
# PROFILE — CHANGE PASSWORD
# ============================================================

class TestChangePassword:

    def test_account_security_section_exists(self):
        html = _read(PROFILE_HTML)

        assert "ACCOUNT SECURITY" in html
        assert 'id="security-heading"' in html
        assert 'id="change-password"' in html
        assert 'id="change-password-form"' in html
        assert 'id="new-password"' in html
        assert 'id="confirm-new-password"' in html
        assert 'id="update-password"' in html
        assert 'id="password-status"' in html

    def test_current_password_is_not_displayed_or_retrieved(self):
        """Only a static mask is shown. There is no current
        password input, and no code path reads one."""

        html = _read(PROFILE_HTML)
        source = _read(PROFILE_JS)

        assert "current-password" not in html
        assert "current_password" not in html

        # No field asks for the existing password.
        assert 'id="current-password"' not in html
        assert 'id="old-password"' not in html

        # The masked hint is a static bullet string, not a
        # value read from anywhere.
        assert "••••••••••••••••" in html

        # No code path reads a current or old password.
        stripped = _strip_strings(source)

        assert "current-password" not in stripped
        assert "old-password" not in stripped
        assert "currentPassword" not in stripped
        assert "oldPassword" not in stripped

    def test_change_password_ui_can_be_opened(self):
        source = _read(PROFILE_JS)

        assert "change-password" in source
        assert 'classList.toggle("hidden")' in (
            _compact(source)
        )

    def test_change_password_requires_both_fields(self):
        source = _read(PROFILE_JS)

        compact = _compact(source)

        assert "!newPassword||!confirmPassword" in compact
        assert "Both password fields are required" in (
            source
        )

    def test_change_password_rejects_mismatch(self):
        source = _read(PROFILE_JS)

        assert "newPassword!==confirmPassword" in (
            _compact(source)
        )
        assert "Passwords do not match" in source

    def test_change_password_enforces_minimum_length(self):
        source = _read(PROFILE_JS)

        assert "MIN_PASSWORD_LENGTH" in source

    def test_change_password_calls_update_user(self):
        source = _read(PROFILE_JS)

        compact = _compact(source)

        assert (
            "careerGapSupabase.auth.updateUser" in compact
        )
        assert "password:newPassword" in compact

    def test_change_password_handles_failed_update(self):
        source = _read(PROFILE_JS)

        assert "Unable to update your password" in source
        assert "error.message" in source

    def test_change_password_shows_success_message(self):
        source = _read(PROFILE_JS)

        assert "Password updated successfully" in source

    def test_change_password_reuses_account_styles(self):
        html = _read(PROFILE_HTML)

        assert 'class="account-row"' in html
        assert 'class="account-secondary-button"' in html
        assert 'class="account-form hidden"' in html
        assert 'class="account-field"' in html
        assert 'class="account-primary-button"' in html
        assert 'class="account-status"' in html


# ============================================================
# SECURITY BOUNDARIES
# ============================================================

class TestPasswordBoundaries:

    def test_no_password_is_sent_to_the_backend(self):
        """The profile save payload carries profile fields
        only; the password never reaches FastAPI."""

        source = _read(PROFILE_JS)

        save = _extract_function(source, "saveProfile")

        assert save != ""
        assert "password" not in save.lower()

    def test_profiles_table_has_no_password_column(self):
        sql = _read(MIGRATION).lower()

        assert "password" not in sql

    def test_no_password_is_stored_client_side(self):
        for path in (LOGIN_JS, RESET_JS, PROFILE_JS):
            source = _read(path)

            assert "localStorage" not in source
            assert "sessionStorage" not in source

    def test_no_password_is_logged(self):
        for path in (LOGIN_JS, RESET_JS, PROFILE_JS):
            source = _read(path)

            # String literals are removed first, so a
            # message that merely mentions the word
            # "password" does not count. What remains
            # is a check that no console call receives
            # a password value as an argument.
            stripped = _strip_strings(source)

            assert not re.search(
                r"console\.(log|error|warn|info|debug)"
                r"\([^)]*\bpassword\b",
                stripped,
            )

    def test_no_password_is_placed_in_a_url(self):
        for path in (LOGIN_JS, RESET_JS, PROFILE_JS):
            source = _read(path)

            assert not re.search(
                r"location\.href=[^;]*password",
                _compact(source),
            )

    def test_backend_receives_no_password_endpoint(self):
        """The FastAPI backend is untouched by this feature:
        no password route may exist for the frontend to call."""

        backend = (
            Path(__file__).resolve().parent.parent
            / "backend.py"
        )

        source = _read(backend)

        assert "password" not in source.lower()

    def test_password_change_uses_the_existing_session(self):
        """Both flows call updateUser on the shared client, so
        the authenticated session is reused rather than a new
        auth path being created."""

        for path in (RESET_JS, PROFILE_JS):
            source = _read(path)

            assert "careerGapSupabase.auth.updateUser" in (
                _compact(source)
            )

            # No second Supabase client is created.
            assert "create_client" not in source
            assert "createClient" not in source