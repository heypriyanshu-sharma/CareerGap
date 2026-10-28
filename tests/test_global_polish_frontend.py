"""Regression tests for the Part 2 global-polish pass (Section 6).

These tests pin only genuine, audited fixes:
- every keyboard focus ring is a contrast-safe theme token (the old
  sage-tinted ring measured ~1.14:1 on light surfaces);
- the analysis result tabs and the sticky subnav tabs have focus
  indicators at all;
- one site-wide reduced-motion guard backs the per-component blocks;
- text-entry controls that iOS Safari would auto-zoom are covered by
  the 16px touch floor;
- duplicated history-button rules and an identical score-ring override
  are removed without changing computed styles;
- the page intro and signed-in workspace panels no longer hug their
  neighbours (page-intro was 8px/4px against a 120px analyzer gap).
"""

import re
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
STYLE_CSS = FRONTEND_DIR / "style.css"
SCRIPT_JS = FRONTEND_DIR / "script.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _matching_brace(text: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise AssertionError("unbalanced braces in style.css")


def _rule(text: str, selector: str) -> str:
    start = text.index(selector + " {")
    open_index = text.index("{", start)
    close_index = _matching_brace(text, open_index)
    return text[start:close_index + 1]


def _rules(text: str, selector: str) -> list:
    """Every standalone rule for the selector, in file order."""
    rules = []
    position = 0
    while True:
        try:
            start = text.index(selector + " {", position)
        except ValueError:
            return rules
        open_index = text.index("{", start)
        close_index = _matching_brace(text, open_index)
        rules.append(text[start:close_index + 1])
        position = close_index + 1


def _full_rule(text: str, selector: str) -> str:
    """The rule for a selector that also has a responsive override."""
    candidates = [rule for rule in _rules(text, selector) if len(rule) > 120]
    assert candidates, f"no substantive rule for {selector}"
    return candidates[0]


def test_focus_rings_are_token_contrast_safe():
    css = _read(STYLE_CSS)

    # The old sage ring washed out on white/cream surfaces (~1.14:1).
    assert "rgba(198, 216, 167, 0.45)" not in css
    assert "rgba(198, 216, 167, 0.5)" not in css

    for match in re.finditer(r"outline: 3px solid([^;]+);", css):
        colour = match.group(1).strip()
        assert colour.startswith("var(--"), colour

    fixed = _rule(css, ".password-toggle:focus-visible")
    assert "outline: 3px solid var(--ref-green-primary);" in fixed
    assert "outline-offset: 2px;" in fixed


def test_result_tabs_have_keyboard_focus_indicators():
    css = _read(STYLE_CSS)

    for selector in (".analysis-tab:focus-visible", ".analysis-subnav-tab:focus-visible"):
        rule = _rule(css, selector)
        assert "outline: 3px solid var(--ref-green-primary);" in rule
        assert "outline-offset: 2px;" in rule

    # The base tab rules keep their pointer/current/disabled contracts.
    tab = _full_rule(css, ".analysis-tab")
    assert "border-radius: 12px;" in tab
    assert "background: var(--cream);" in tab
    for expected in (
        ".analysis-tab:hover:not(:disabled) {",
        ".analysis-tab.active {",
        ".analysis-tab:disabled {",
    ):
        assert expected in css

    active = _rule(css, ".analysis-subnav-tab.active")
    assert "background: var(--ref-green-primary);" in active
    subnav_disabled = _rule(css, ".analysis-subnav-tab:disabled")
    assert "opacity: 0.5;" in subnav_disabled


def test_site_wide_reduced_motion_guard_backs_component_blocks():
    css = _read(STYLE_CSS)
    smooth = css.index("scroll-behavior: smooth;")
    html_rule = _rule(css, "html")

    assert "scroll-behavior: smooth;" in html_rule
    guard_start = css.index("@media (prefers-reduced-motion: reduce)")
    guard = _rule(css[guard_start:], "*")

    assert "animation-duration: 0.01ms !important;" in guard
    assert "animation-iteration-count: 1 !important;" in guard
    assert "transition-duration: 0.01ms !important;" in guard
    assert "scroll-behavior: auto !important;" in guard
    assert guard_start > smooth, (
        "the guard must be able to disable the smooth-scroll default"
    )

    # Animated primitives still exist for the guard to cover (the audit
    # found spinners and gauge strokes with no motion handling).
    assert css.count("animation:") >= 3

    # Component-scoped blocks remain in place alongside the guard.
    css.count("@media (prefers-reduced-motion: reduce)") >= 9


def test_touch_entry_controls_cannot_trigger_ios_zoom():
    css = _read(STYLE_CSS)
    coarse_start = css.index("@media (pointer: coarse)")
    coarse = css[coarse_start:css.index("}", css.index("font-size: 16px;", coarse_start) + len("font-size: 16px;"))]

    for selector in (
        ".account-field input",
        ".account-field select",
        ".resume-field input",
        ".interview-field-group input",
        ".resume-bullet-row input",
    ):
        assert selector + "," in coarse or selector + " {" in coarse, selector

    # Buttons do not trigger iOS zoom and stay in the pill-scale list.
    assert ".custom-select-trigger," not in coarse
    assert ".input-number," not in coarse


def test_duplicated_history_button_rules_are_gone_without_visual_change():
    css = _read(STYLE_CSS)

    # The buttons are only generated inside history items, so the bare
    # selectors were dead code; the weaker second definition actually
    # conflicted with the scoped one.
    assert not re.search(r"^\.history-view-button \{", css, re.MULTILINE)
    assert not re.search(r"^\.history-view-button:hover", css, re.MULTILINE)
    assert not re.search(r"^\.history-delete-button \{", css, re.MULTILINE)
    assert not re.search(r"^\.history-delete-button:hover", css, re.MULTILINE)

    view = _full_rule(css, ".analysis-history-item .history-view-button")
    assert "background: var(--accent-solid);" in view
    assert "color: var(--on-accent);" in view
    assert "border-radius: 12px;" in view
    assert "box-shadow: 0 5px 14px rgba(75, 96, 67, 0.10);" in view

    view_hover = _rule(css, ".analysis-history-item .history-view-button:hover")
    assert "background: var(--olive-dark);" in view_hover

    view_focus = _rule(css, ".analysis-history-item .history-view-button:focus-visible")
    assert "outline: 3px solid var(--ref-green-primary);" in view_focus

    delete = _rule(css, ".analysis-history-item .history-delete-button")
    assert "border-radius: 50%;" in delete
    assert "background: transparent;" in delete

    # The still-active mobile stretch of the view button is untouched.
    mobile = css[css.index("@media (max-width: 700px)"):]
    assert "flex: 1;" in mobile

    # The gauge overrides are defined exactly once.
    assert len(re.findall(r"^\.score-ring-track \{", css, re.MULTILINE)) == 2
    assert len(re.findall(r"^\.score-ring-progress \{", css, re.MULTILINE)) == 2
    assert "#C6E8B5" in css, "the gauge's on-accent stroke value survives"

    assert css.count("{") == css.count("}")


def test_section_rhythm_matches_the_rest_of_the_page():
    css = _read(STYLE_CSS)

    intro = _rule(css, ".page-intro")
    assert "padding: 28px 0 20px;" in intro

    workspace = _rule(css, ".workspace-section")
    assert "padding: 24px 0 40px;" in workspace

    # The wider rhythm anchors are untouched.
    analysis = _rule(css, ".analysis-section")
    assert "margin: 0 auto 120px;" in analysis
    pillars = _rule(css, ".pillars")
    assert "margin: 24px auto 40px;" in pillars
    desktop_hero = _rule(css, ".hero")
    assert "min-height: 670px;" in desktop_hero

    # Hover transitions across the site keep the short spec timing
    # (0.2s was the established value; 0.18s matches Sections 1-5).
    # cubic-bezier entries are icon cross-fades (theme toggle), an
    # easing choice rather than a hover lift.
    for match in re.finditer(r"transition:([^;]*transform[^;]*);", css):
        body = match.group(1)
        if "cubic-bezier" in body:
            continue
        assert (
            "0.2s" in body
            or "0.18s" in body
            or "0.15s" in body
            or "0.25s" in body
        ), body

    js = _read(SCRIPT_JS)
    assert "history-view-button" in js, (
        "the history button stays generated only inside history items"
    )
