"""Theme continuity and account-dropdown regression coverage.

The account pages (profile.html, settings.html) must honor the saved
theme exactly like index.html, via the same pre-paint boot script, and
the dropdown polish must keep its accessibility and reduced-motion
contracts. The behaviour test runs the real boot script against a fake
browser environment through node, matching the approach in
test_account_menu_frontend.py.
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

INDEX_HTML = FRONTEND_DIR / "index.html"
PROFILE_HTML = FRONTEND_DIR / "profile.html"
SETTINGS_HTML = FRONTEND_DIR / "settings.html"
STYLE_CSS = FRONTEND_DIR / "style.css"

PAGES = (INDEX_HTML, PROFILE_HTML, SETTINGS_HTML)


def _read(path):
    return path.read_text(encoding="utf-8")


_BOOT_PATTERN = re.compile(
    r"<script>\s*(/\* Apply the saved theme[\s\S]*?)</script>"
)


def _extract_boot_script(path):
    match = _BOOT_PATTERN.search(_read(path))

    assert match, (
        f"{path.name} is missing the shared pre-paint theme "
        "boot script"
    )

    return match.group(0)


def _extract_css_rule(css, selector):
    """Return the declaration block for an exact simple selector."""

    match = re.search(
        re.escape(selector) + r"\s*\{([^}]*)\}", css
    )

    assert match, f"missing CSS rule for {selector!r}"

    return match.group(1)


class TestThemeBootScript:

    def test_all_pages_embed_identical_boot_script(self):
        """Every themed page must boot the theme the same way, so an
        account page can never drift back to always-light."""

        scripts = {
            _extract_boot_script(page) for page in PAGES
        }

        assert len(scripts) == 1, (
            "the theme boot script differs between pages"
        )

    def test_boot_script_runs_before_stylesheet(self):
        """It must execute before style.css so there is no flash of
        the light theme on dark-mode users."""

        for page in PAGES:
            html = _read(page)

            script_pos = html.index("Apply the saved theme")
            style_pos = html.index('rel="stylesheet"')

            assert script_pos < style_pos, (
                f"{page.name}: boot script must precede the "
                "stylesheet link"
            )

    def test_boot_script_reads_saved_theme_with_system_fallback(self):
        for page in PAGES:
            script = _extract_boot_script(page)

            assert 'localStorage.getItem("theme")' in script
            assert "prefers-color-scheme: dark" in script
            assert (
                'setAttribute("data-theme", theme)' in script
            )

    def test_dark_theme_recovers_account_surfaces(self):
        """The dark theme must redefine the surface tokens the account
        cards are built from, otherwise the pages stay light."""

        css = _read(STYLE_CSS)
        dark = css.split('[data-theme="dark"] {', 1)[1]

        for token in (
            "--ref-page:",
            "--cream:",
            "--white:",
            "--border:",
        ):
            assert token in dark.split("}", 1)[0], (
                f"dark theme no longer redefines {token}"
            )

    def test_dark_avatar_chip_keeps_contrast(self):
        """The profile-page avatar uses the same light-sage chip as
        the menu avatar; both must be re-surfaced on dark."""

        css = _read(STYLE_CSS)

        assert (
            '[data-theme="dark"] .profile-page-avatar' in css
        )


_BOOT_BEHAVIOUR_TEST = r"""
'use strict';

function runBoot(saved, prefersDark, throwOnRead) {
    const attributes = {};

    const localStorage = {
        getItem: function (key) {
            if (throwOnRead) {
                throw new Error('blocked');
            }
            return saved;
        }
    };

    const window = {
        matchMedia: function (query) {
            return {
                matches: prefersDark && query.indexOf('dark') !== -1
            };
        }
    };

    const document = {
        documentElement: {
            setAttribute: function (name, value) {
                attributes[name] = value;
            }
        }
    };

    __BOOT__

    return attributes['data-theme'] || null;
}

function fail(message) {
    console.error('ASSERTION FAILED: ' + message);
    process.exit(1);
}

// Saved preference always wins.
if (runBoot('dark', false, false) !== 'dark') {
    fail('saved dark must win over light system');
}
if (runBoot('light', true, false) !== 'light') {
    fail('saved light must win over dark system');
}

// System preference applies only without a saved value.
if (runBoot(null, true, false) !== 'dark') {
    fail('dark system should apply with no saved value');
}
if (runBoot(null, false, false) !== 'light') {
    fail('light system default should apply with no saved value');
}

// An unrecognized saved value falls back to the system preference.
if (runBoot('neon', true, false) !== 'dark') {
    fail('invalid saved value should fall back to system');
}

// Storage unavailable (private browsing) must not throw and must
// fall back to the default light theme.
if (runBoot(null, false, true) !== 'light') {
    fail('blocked storage should fall back to light');
}

console.log('theme boot behaviour OK');
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
    reason="node is required for the theme boot behaviour test",
)
class TestThemeBootBehaviour:

    def test_boot_script_resolves_theme_correctly(self):
        """The real inline script must prefer the saved theme, fall
        back to the system preference, and survive blocked storage."""

        script = _extract_boot_script(INDEX_HTML)
        inner = re.sub(
            r"^<script>\s*|\s*</script>$", "", script
        )

        result = _run_node(
            _BOOT_BEHAVIOUR_TEST.replace("__BOOT__", inner)
        )

        assert result.returncode == 0, (
            "theme boot behaviour test failed:\n"
            f"{result.stdout}\n{result.stderr}"
        )

        assert "theme boot behaviour OK" in result.stdout


class TestDropdownPolish:

    def test_trigger_has_decorative_caret(self):
        html = _read(INDEX_HTML)

        trigger = html.split(
            'id="profile-trigger"', 1
        )[1].split("</button>", 1)[0]

        assert 'class="profile-caret"' in trigger
        assert 'aria-hidden="true"' in trigger

    def test_caret_rotates_with_aria_expanded(self):
        """The caret state must follow the aria-expanded attribute the
        toggle handler already maintains."""

        css = _read(STYLE_CSS)

        rule = _extract_css_rule(
            css,
            ".profile-trigger[aria-expanded=\"true\"] "
            ".profile-caret",
        )

        assert "rotate(180deg)" in rule

    def test_expanded_trigger_has_visible_state(self):
        css = _read(STYLE_CSS)

        assert (
            '.profile-trigger[aria-expanded="true"]' in css
        )

    def test_menu_entrance_animation_respects_reduced_motion(self):
        css = _read(STYLE_CSS)

        assert "@keyframes profile-menu-in" in css

        # Match a direct menu rule inside a reduced-motion media
        # block, not a normal rule somewhere later in the stylesheet.
        assert re.search(
            r"@media \(prefers-reduced-motion: reduce\)\s*\{"
            r"\s*\.profile-menu\s*\{\s*animation: none", css
        ), "menu entrance animation is not reduced-motion safe"

    def test_menu_header_is_tonal_card(self):
        css = _read(STYLE_CSS)
        rule = _extract_css_rule(css, ".profile-menu-header")

        assert "background: var(--pistachio-soft)" in rule
        assert "border-radius" in rule
        assert "border-bottom" not in rule, (
            "the tonal header card replaces the hard divider"
        )

    def test_menu_items_are_rounded_inset_pills(self):
        css = _read(STYLE_CSS)

        menu_rule = _extract_css_rule(css, ".profile-menu")
        assert "padding: 6px" in menu_rule

        item_rule = _extract_css_rule(css, ".profile-menu-item")
        assert "border-radius: 10px" in item_rule

    def test_menu_semantics_survive_polish(self):
        """role=menu / menuitem wiring and the hidden-by-default
        contract must be untouched by the visual polish."""

        html = _read(INDEX_HTML)

        assert re.search(
            r'id="profile-menu"[^>]*role="menu"',
            html,
            re.DOTALL,
        )
        assert re.search(
            r'id="profile-menu"[^>]*class="profile-menu hidden"',
            html,
            re.DOTALL,
        )
        assert html.count('role="menuitem"') == 5
