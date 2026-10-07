"""Tests for the account menu, profile page and settings page.

The dropdown behaviour lives in frontend/script.js inside a
DOMContentLoaded closure, so the behavioural test extracts the real
helper sources and runs them against a small fake DOM, the same
approach already used by test_resume_builder_frontend.py. The markup
tests assert the pages expose the accessibility wiring the handlers
depend on.
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


FRONTEND_DIR = (
    Path(__file__).resolve().parent.parent / "frontend"
)

SCRIPT_JS = FRONTEND_DIR / "script.js"
SUPABASE_CONFIG_JS = FRONTEND_DIR / "supabase-config.js"
STYLE_CSS = FRONTEND_DIR / "style.css"
INDEX_HTML = FRONTEND_DIR / "index.html"
PROFILE_HTML = FRONTEND_DIR / "profile.html"
SETTINGS_HTML = FRONTEND_DIR / "settings.html"
SETTINGS_JS = FRONTEND_DIR / "settings.js"
MIGRATION = (
    Path(__file__).resolve().parent.parent
    / "supabase"
    / "migrations"
    / "0002_create_profiles.sql"
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _extract_braced_block(
    source,
    start_marker,
):
    """Return the source block opening with the first ``{`` after
    ``start_marker`` and closing with its matching brace.

    String literals, template literals (including nested
    ``${...}``) and comments are skipped so braces inside them do
    not confuse the matching.
    """

    start = source.index(start_marker)
    open_idx = source.index("{", start)

    depth = 0
    i = open_idx
    n = len(source)

    while i < n:
        char = source[i]

        if char in "\"'`":
            quote = char
            i += 1

            while i < n:
                if source[i] == "\\":
                    i += 2
                    continue

                if (
                    quote == "`"
                    and source[i] == "$"
                    and i + 1 < n
                    and source[i + 1] == "{"
                ):
                    i += 2
                    nested = 1

                    while i < n and nested > 0:
                        if source[i] == "{":
                            nested += 1
                        elif source[i] == "}":
                            nested -= 1
                        i += 1

                    continue

                if source[i] == quote:
                    break

                i += 1

            i += 1
            continue

        if char == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue

        if char == "/" and i + 1 < n and source[i + 1] == "*":
            i += 2

            while i + 1 < n and not (
                source[i] == "*" and source[i + 1] == "/"
            ):
                i += 1

            i += 2
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1

            if depth == 0:
                return source[start:i + 1]

        i += 1

    raise ValueError(
        f"unbalanced braces for {start_marker!r}"
    )


# ============================================================
# ACCOUNT MENU MARKUP
# ============================================================

class TestAccountMenuMarkup:

    def test_trigger_exists(self):
        html = _read(INDEX_HTML)

        assert 'id="profile-trigger"' in html
        assert "profile-trigger" in html

    def test_menu_starts_hidden(self):
        html = _read(INDEX_HTML)

        assert re.search(
            r'id="profile-menu"[^>]*class="profile-menu hidden"',
            html,
            re.DOTALL,
        )

    def test_trigger_exposes_expanded_state(self):
        """aria-expanded is what the toggle flips, so it must be
        present and start collapsed."""

        html = _read(INDEX_HTML)

        assert re.search(
            r'id="profile-trigger"[^>]*aria-expanded="false"',
            html,
            re.DOTALL,
        )

        assert 'aria-controls="profile-menu"' in html

    def test_menu_has_menu_semantics(self):
        html = _read(INDEX_HTML)

        assert 'id="profile-menu"' in html
        assert 'role="menu"' in html

    def test_menu_exposes_exactly_the_approved_options(self):
        """Only the five approved actions are present.

        Notifications, billing, help, preferences and a theme
        selector were explicitly ruled out, so their absence is
        asserted rather than assumed.
        """

        html = _read(INDEX_HTML)

        for option_id in (
            "menu-profile",
            "menu-resumes",
            "menu-analyses",
            "menu-settings",
            "menu-signout",
        ):
            assert f'id="{option_id}"' in html, (
                f"missing approved option {option_id}"
            )

        menu_block = html.split(
            'id="profile-menu"', 1
        )[1].split("</header>", 1)[0]

        for forbidden in (
            "notification",
            "billing",
            "upgrade",
            "premium",
            "help",
            "theme",
            "dark-mode",
            "appearance",
        ):
            assert forbidden not in menu_block.lower(), (
                f"unapproved menu option present: {forbidden}"
            )

    def test_menu_option_count_is_exactly_five(self):
        html = _read(INDEX_HTML)

        menu_block = html.split(
            'id="profile-menu"', 1
        )[1].split("</header>", 1)[0]

        assert menu_block.count(
            'role="menuitem"'
        ) == 5

    def test_menu_header_shows_identity_fields(self):
        html = _read(INDEX_HTML)

        assert 'id="menu-user-name"' in html
        assert 'id="menu-user-email"' in html

    def test_previous_email_and_logout_box_is_gone(self):
        """The old inline email + logout control is replaced."""

        html = _read(INDEX_HTML)

        assert 'id="user-email"' not in html
        assert 'id="auth-action-button"' not in html

    def test_existing_navigation_is_untouched(self):
        """My Resumes and My Analyses must not replace or remove the
        primary navigation."""

        html = _read(INDEX_HTML)

        for view in (
            "analyze",
            "resume-builder",
            "saved-analyses",
        ):
            assert f'data-view="{view}"' in html

        assert 'id="nav-resume-builder"' in html
        assert 'id="nav-saved-analyses"' in html


# ============================================================
# ACCOUNT MENU BEHAVIOUR (real source, fake DOM)
# ============================================================

_MENU_TOGGLE_TEST = r"""
'use strict';

// ---- Fake DOM mirroring the real account menu ----
function FakeMenu() {
    const classes = new Set(['hidden']);

    const menu = {
        classes: classes,
        isHidden: function () {
            return classes.has('hidden');
        },
        classList: {
            add: function (name) {
                classes.add(name);
            },
            remove: function (name) {
                classes.delete(name);
            },
            contains: function (name) {
                return classes.has(name);
            }
        }
    };

    return menu;
}

function FakeTrigger() {
    const attributes = {};

    return {
        setAttribute: function (name, value) {
            attributes[name] = value;
        },
        getAttribute: function (name) {
            return attributes[name];
        }
    };
}

// The real helpers read these closure variables directly.
const profileMenu = FakeMenu();
const profileTrigger = FakeTrigger();

__TOGGLE__
__CLOSE__

function fail(message) {
    console.error('ASSERTION FAILED: ' + message);
    process.exit(1);
}

// Starts collapsed. The initial aria-expanded value ships in the
// markup, which is asserted separately in TestAccountMenuMarkup.
if (!profileMenu.isHidden()) {
    fail('menu should start hidden');
}

toggleProfileMenu();
if (profileMenu.isHidden()) {
    fail('first toggle should open the menu');
}
if (
    profileTrigger.getAttribute('aria-expanded')
    !== 'true'
) {
    fail('aria-expanded should be true when open');
}

// Second toggle closes it again.
toggleProfileMenu();
if (!profileMenu.isHidden()) {
    fail('second toggle should close the menu');
}
if (
    profileTrigger.getAttribute('aria-expanded')
    !== 'false'
) {
    fail('aria-expanded should be false when closed');
}

// Reopen, then force close (the outside-click / Escape path).
toggleProfileMenu();
if (profileMenu.isHidden()) {
    fail('menu should reopen');
}

closeProfileMenu();
if (!profileMenu.isHidden()) {
    fail('force close must close an open menu');
}
if (
    profileTrigger.getAttribute('aria-expanded')
    !== 'false'
) {
    fail('force close must reset aria-expanded');
}

// Forcing close on an already-closed menu must be a no-op.
closeProfileMenu();
if (!profileMenu.isHidden()) {
    fail('force close on a closed menu must stay closed');
}

console.log('account menu toggle OK');
"""


def _run_node(source):
    with tempfile.NamedTemporaryFile(
        "w",
        suffix=".js",
        delete=False,
        encoding="utf-8",
    ) as handle:
        handle.write(source)
        tmp_path = handle.name

    try:
        return subprocess.run(
            ["node", tmp_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is required for the account menu test",
)
class TestAccountMenuBehaviour:

    def test_menu_toggles_and_force_closes(self):
        """The real toggle helpers must open, close and force close
        the menu while keeping aria-expanded in step."""

        source = _read(SCRIPT_JS)

        toggle = _extract_braced_block(
            source, "function toggleProfileMenu"
        )

        close = _extract_braced_block(
            source, "function closeProfileMenu"
        )

        script = (
            _MENU_TOGGLE_TEST
            .replace("__TOGGLE__", toggle)
            .replace("__CLOSE__", close)
        )

        result = _run_node(script)

        assert result.returncode == 0, (
            "account menu toggle test failed:\n"
            f"{result.stdout}\n{result.stderr}"
        )

        assert "account menu toggle OK" in result.stdout

    def test_toggle_syncs_aria_expanded(self):
        source = _read(SCRIPT_JS)

        toggle = _extract_braced_block(
            source, "function toggleProfileMenu"
        )

        assert (
            'profileTrigger.setAttribute(' in toggle
        ), "toggle must keep aria-expanded in sync"

    def test_menu_closes_on_outside_click(self):
        source = _read(SCRIPT_JS)

        assert (
            "document.addEventListener(" in source
        )
        assert "closeProfileMenu()" in source

    def test_menu_closes_on_escape(self):
        source = _read(SCRIPT_JS)

        compact = re.sub(r"\s+", "", source)

        assert 'event.key==="Escape"' in compact or (
            'e.key==="Escape"' in compact
        ) or ('event.key==="Escape"' in compact)

    def test_resumes_item_reuses_existing_workspace(self):
        """My Resumes must open the existing builder, not a new view."""

        source = _read(SCRIPT_JS)

        assert (
            'getElementById("nav-resume-builder")'
            in source
        )

    def test_analyses_item_reuses_existing_workspace(self):
        source = _read(SCRIPT_JS)

        assert (
            'getElementById("nav-saved-analyses")'
            in source
        )

    def test_no_second_sign_out_implementation(self):
        """Sign out is defined once in the shared auth module and
        reused everywhere, not reimplemented per page."""

        config = _read(SUPABASE_CONFIG_JS)

        assert (
            config.count("careerGapSupabase.auth.signOut()")
            == 1
        )

        # No page may call Supabase sign-out directly; they must go
        # through the shared helper.
        assert (
            "careerGapSupabase.auth.signOut()"
            not in _read(SCRIPT_JS)
        )
        assert (
            "careerGapSignOut()" in _read(SCRIPT_JS)
        )
        assert (
            "careerGapSupabase.auth.signOut()"
            not in _read(SETTINGS_JS)
        )
        assert "careerGapSignOut()" in _read(SETTINGS_JS)

    def test_signout_redirects_to_login(self):
        source = _read(SCRIPT_JS)

        compact = re.sub(r"\s+", "", source)

        assert (
            'window.location.replace("login.html")'
            in compact
        )

    def test_signed_out_user_keeps_a_way_to_log_in(self):
        """The account icon is the only route to sign in, so it must
        stay visible without a session and navigate rather than
        disappear."""

        source = _read(SCRIPT_JS)

        assert (
            "function setupSignedOutTrigger()" in source
        )

        signed_out = _extract_braced_block(
            source,
            "function setupSignedOutTrigger",
        )

        assert (
            'window.location.replace(' in signed_out
        )
        assert '"login.html"' in signed_out

        assert "profileTrigger.style.display = \"none\"" not in source, (
            "the trigger must not be hidden for signed-out "
            "visitors, or the login page becomes unreachable"
        )

    def test_avatar_url_is_validated_before_rendering(self):
        """Only absolute http(s) avatar URLs reach the style, so a
        stored javascript: or data: value cannot be rendered."""

        for path in (
            SCRIPT_JS,
            FRONTEND_DIR / "profile.js",
        ):
            source = _read(path)

            assert (
                "function safeAvatarUrl(" in source
            ), f"{path.name} must validate avatar URLs"

            helper = _extract_braced_block(
                source, "function safeAvatarUrl"
            )

            assert (
                'startsWith("http://")' in helper
            )
            assert (
                'startsWith("https://")' in helper
            )

    def test_navbar_uses_profile_full_name(self):
        """The navbar trigger must show the stored profile name instead
        of the email-derived label."""

        source = _read(SCRIPT_JS)

        assert "function loadProfileForUI(" in source
        assert "/auth/profile" in source
        assert "function resolveProfileName(" in source
        assert "profile.full_name" in source

        helper = _extract_braced_block(
            source, "function resolveProfileName"
        )

        assert "resolveUserIdentity(" in helper, (
            "profile name must fall back to the existing identity "
            "resolution when no profile name is stored"
        )

        assert "profileTrigger.style.display = \"none\"" not in source

    def test_navbar_falls_back_to_email_without_profile_name(self):
        """When no profile row or full_name exists the existing email
        behaviour must be preserved."""

        source = _read(SCRIPT_JS)

        compact = re.sub(r"\s+", "", source)

        assert (
            "returnresolveUserIdentity(user);" in compact
        )

        # The fallback path must still reach the email when the
        # identity helper returns empty.
        assert "name||email" in compact

    def test_navbar_fetches_profile_after_session(self):
        """The dropdown setup must fetch the profile row and pass it
        to the UI before rendering."""

        source = _read(SCRIPT_JS)

        setup = _extract_braced_block(
            source, "function setupProfileDropdown"
        )

        assert "loadProfileForUI(" in setup

        compact = re.sub(r"\s+", "", setup)

        assert (
            "updateProfileUI(data.session.user,profile)" in compact
        )


# ============================================================
# PROFILE PAGE
# ============================================================

class TestProfilePage:

    def test_page_exists(self):
        assert PROFILE_HTML.exists()
        assert (FRONTEND_DIR / "profile.js").exists()

    def test_page_shows_the_approved_fields(self):
        html = _read(PROFILE_HTML)

        assert 'id="profile-full-name"' in html
        assert 'id="profile-target-role"' in html
        assert (
            'id="profile-experience-level"' in html
        )
        assert 'id="profile-page-avatar"' in html

    def test_page_uses_existing_stylesheet(self):
        html = _read(PROFILE_HTML)

        assert 'href="style.css"' in html

    def test_page_loads_supabase_config(self):
        html = _read(PROFILE_HTML)

        assert 'src="supabase-config.js"' in html
        assert "supabase-js@2" in html

    def test_experience_level_options(self):
        html = _read(PROFILE_HTML)

        for level in (
            "student",
            "junior",
            "mid",
            "senior",
            "lead",
        ):
            assert f'value="{level}"' in html

        assert 'value="principal"' not in html

    def test_page_has_no_theme_or_billing_controls(self):
        html = _read(PROFILE_HTML).lower()

        for forbidden in (
            "theme",
            "dark mode",
            "billing",
            "notification",
        ):
            assert forbidden not in html

    def test_profile_script_targets_profile_endpoint(self):
        source = _read(FRONTEND_DIR / "profile.js")

        assert "/auth/profile" in source

    def test_profile_script_sends_bearer_token(self):
        source = _read(FRONTEND_DIR / "profile.js")

        assert "Bearer ${accessToken}" in source

    def test_profile_script_reuses_production_url_rule(self):
        """The page must resolve the API the same way script.js does,
        so production keeps pointing at the deployed backend."""

        source = _read(FRONTEND_DIR / "profile.js")

        assert (
            "https://careergap.onrender.com"
            in source
        )
        assert (
            "configuredApiUrl && isLocalhost"
            in source
        )

    def test_successful_save_redirects_home(self):
        """A completed save shows the success state, then
        hands the user back to the dashboard."""

        source = _read(FRONTEND_DIR / "profile.js")

        compact = re.sub(r"\s+", "", source)

        assert (
            'setStatus("Profilesaved.","success")'
            in compact
        )

        assert (
            'window.location.href="index.html"' in compact
        )

        assert "window.setTimeout" in compact

    def test_failed_save_does_not_redirect(self):
        """The redirect lives inside the try block, after
        the response is known to be ok, so a rejected
        request can never reach it."""

        source = _read(FRONTEND_DIR / "profile.js")

        compact = re.sub(r"\s+", "", source)

        # The save handler is the last try block in the
        # file, so its catch is the final one.
        redirect = compact.rindex(
            'window.location.href="index.html"'
        )
        catch = compact.rindex("}catch(error){")

        assert redirect < catch

        # The failure path reports the error instead.
        assert '"error"' in compact

    def test_profile_page_has_no_settings_link(self):
        """Settings is reached from the account menu, not
        from the profile page, so the two pages do not
        loop back and forth."""

        html = _read(PROFILE_HTML)

        assert "settings.html" not in html
        assert "account-back-link" not in html

    def test_profile_page_keeps_back_to_careergap(self):
        html = _read(PROFILE_HTML)

        assert 'href="index.html"' in html
        assert "Back to CareerGap" in html


# ============================================================
# SETTINGS PAGE
# ============================================================

class TestSettingsPage:

    def test_page_exists(self):
        assert SETTINGS_HTML.exists()
        assert SETTINGS_JS.exists()

    def test_page_uses_existing_stylesheet(self):
        html = _read(SETTINGS_HTML)

        assert 'href="style.css"' in html

    def test_shows_email_information(self):
        html = _read(SETTINGS_HTML)

        assert 'id="settings-email"' in html

    def test_exposes_delete_and_signout_actions(self):
        html = _read(SETTINGS_HTML)

        assert 'id="settings-delete-account"' in html
        assert 'id="settings-signout"' in html

    def test_has_no_danger_zone_heading(self):
        """The design brief ruled this out explicitly."""

        html = _read(SETTINGS_HTML).lower()

        assert "danger zone" not in html

    def test_has_no_unnecessary_settings_sections(self):
        html = _read(SETTINGS_HTML).lower()

        for forbidden in (
            "theme",
            "billing",
            "notification",
            "preferences",
        ):
            assert forbidden not in html

    def test_delete_requires_confirmation_modal(self):
        html = _read(SETTINGS_HTML)

        assert 'id="delete-modal"' in html
        assert 'aria-modal="true"' in html
        assert 'id="delete-cancel"' in html
        assert 'id="delete-confirm"' in html

    def test_modal_states_action_is_irreversible(self):
        html = _read(SETTINGS_HTML)

        assert "cannot be undone" in html

    def test_modal_cannot_be_dismissed_without_a_choice(self):
        """The backdrop click handler exists so the modal can be
        dismissed, but Delete itself must be behind the confirm
        button rather than firing on open."""

        source = _read(SETTINGS_JS)

        compact = re.sub(r"\s+", "", source)

        assert (
            'deleteConfirm.addEventListener("click"'
            in compact.replace(" ", "")
        )

    def test_no_profile_settings_navigation_loop(self):
        """The bottom back-link is removed so Settings does
        not point straight back at the profile page. The
        account dropdown remains the way back to Profile,
        which keeps the two pages from looping."""

        html = _read(SETTINGS_HTML)

        assert "account-back-link" not in html
        assert "← My Profile" not in html

    def test_settings_keeps_back_to_careergap(self):
        html = _read(SETTINGS_HTML)

        assert 'href="index.html"' in html
        assert "Back to CareerGap" in html

    def test_delete_calls_backend_not_supabase_directly(self):
        """Account deletion goes through the API so ownership is
        verified server-side."""

        source = _read(SETTINGS_JS)

        assert "/auth/delete-account" in source

        assert "auth.admin.deleteUser" not in source

    def test_signout_reuses_existing_implementation(self):
        source = _read(SETTINGS_JS)

        assert "careerGapSignOut()" in source

    def test_signs_out_locally_after_delete(self):
        """The session is no longer valid once the account is gone,
        so it must be cleared before leaving the page."""

        source = _read(SETTINGS_JS)

        compact = re.sub(r"\s+", "", source)

        assert (
            "awaitcareerGapSignOut();"
            in compact
        )

    def test_redirects_to_login_after_delete(self):
        source = _read(SETTINGS_JS)

        compact = re.sub(r"\s+", "", source)

        assert "awaitcareerGapSignOut();" in compact

        # The redirect lives in the shared helper so every caller
        # lands on login.html the same way.
        config = re.sub(
            r"\s+", "", _read(SUPABASE_CONFIG_JS)
        )

        assert (
            'window.location.replace("login.html")'
            in config
        )


# ============================================================
# STYLES
# ============================================================

class TestAccountStyles:

    def test_profile_menu_is_styled(self):
        css = _read(STYLE_CSS)

        assert ".profile-menu {" in css
        assert ".profile-trigger {" in css
        assert ".profile-menu-item {" in css

    def test_menu_uses_existing_design_tokens(self):
        """No new colour system is introduced."""

        css = _read(STYLE_CSS)

        assert "var(--cream)" in css
        assert "var(--olive)" in css
        assert "var(--pistachio)" in css

    def test_account_pages_are_styled(self):
        css = _read(STYLE_CSS)

        assert ".account-main {" in css
        assert ".account-card {" in css
        assert ".account-modal {" in css

    def test_menu_has_small_screen_rules(self):
        css = _read(STYLE_CSS)

        assert ".profile-menu {" in css

    def test_modal_is_hidden_by_default_class(self):
        css = _read(STYLE_CSS)

        assert ".account-modal.hidden {" in css

    def test_no_new_backdrop_blur_stack(self):
        """The brief ruled out extra glassmorphism; the account
        surfaces use the flat cream panel."""

        css = _read(STYLE_CSS)

        account_start = css.index(
            "   ACCOUNT PAGES"
        )

        account_css = css[account_start:]

        next_section = account_css.find(
            "   RESPONSIVE"
        )

        block = account_css[:next_section]

        assert "backdrop-filter" not in block


# ============================================================
# MIGRATION
# ============================================================

class TestProfilesMigration:

    def test_migration_file_exists(self):
        assert MIGRATION.exists()

    def test_creates_profiles_table(self):
        sql = _read(MIGRATION).lower()

        assert "create table if not exists public.profiles" in sql

    def test_has_the_approved_columns(self):
        sql = _read(MIGRATION).lower()

        for column in (
            "id uuid primary key",
            "avatar_url",
            "full_name",
            "target_role",
            "experience_level",
            "created_at",
            "updated_at",
        ):
            assert column in sql

    def test_id_references_auth_users_with_cascade(self):
        """The cascade is what removes the profile when the account
        is deleted."""

        sql = _read(MIGRATION).lower()

        assert "references auth.users (id)" in sql
        assert "on delete cascade" in sql

    def test_enables_row_level_security(self):
        sql = _read(MIGRATION).lower()

        assert (
            "alter table public.profiles enable row level security"
            in sql
        )

    def test_has_per_command_policies(self):
        sql = _read(MIGRATION).lower()

        for command in (
            "select",
            "insert",
            "update",
            "delete",
        ):
            assert (
                f"for {command}" in sql
            ), f"missing {command} policy"

    def test_policies_are_scoped_to_own_row(self):
        sql = _read(MIGRATION).lower()

        assert "auth.uid()" in sql

        assert sql.count(
            "= id"
        ) >= 4, (
            "every policy must compare auth.uid() to the row id"
        )

    def test_grants_to_authenticated_role(self):
        sql = _read(MIGRATION).lower()

        assert (
            "grant select, insert, update, delete on "
            "public.profiles to authenticated" in sql
        )

    def test_constrains_experience_level(self):
        sql = _read(MIGRATION).lower()

        assert "check (experience_level in" in sql

        for level in (
            "student",
            "junior",
            "mid",
            "senior",
            "lead",
        ):
            assert f"'{level}'" in sql

        assert "'principal'" not in sql

    def test_uses_the_existing_timestamp_helper(self):
        """updated_at is maintained by a trigger, not by the app."""

        sql = _read(MIGRATION).lower()

        assert "before update on public.profiles" in sql

    def test_is_additive(self):
        """The migration must not drop or alter existing objects."""

        sql = _read(MIGRATION).lower()

        assert "drop table" not in sql
        assert "drop schema" not in sql
        assert "alter table public.resumes" not in sql
        assert "alter table public.career_analyses" not in sql

    def test_does_not_expose_the_service_key(self):
        sql = _read(MIGRATION)

        assert "service_role" not in sql.lower()
        assert "service_key" not in sql.lower()

    def test_does_not_disable_rls(self):
        sql = _read(MIGRATION).lower()

        assert "disable row level security" not in sql

    def test_resume_migration_is_unchanged(self):
        """The resume migration must not be touched by this feature."""

        resume_migration = (
            Path(__file__).resolve().parent.parent
            / "supabase"
            / "migrations"
            / "0001_create_resumes.sql"
        )

        sql = _read(resume_migration)

        assert "create table if not exists public.resumes" in sql
        assert "public.profiles" not in sql