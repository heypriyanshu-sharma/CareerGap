"""Regression tests for the Part 2 Analyze form polish.

The form now sits on a white elevated card, its step badges match the
pillar cards, its fields use a very light green surface with a green
focus border and soft ring, and the submit button matches the hero
call-to-action. Everything stays scoped to ``.analysis-card`` so other
forms on the page keep their current surfaces, and every animation has
a reduced-motion fallback.
"""

import re
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
STYLE_CSS = FRONTEND_DIR / "style.css"
INDEX_HTML = FRONTEND_DIR / "index.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _matching_brace(text: str, open_index: int) -> int:
    """Return the index of the brace that closes the one at open_index."""
    depth = 0
    for index in range(open_index, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    raise AssertionError("unbalanced braces in style.css")


def _media_blocks(css: str, max_width: int) -> list:
    marker = f"@media (max-width: {max_width}px)"
    blocks = []
    position = 0
    while True:
        start = css.find(marker, position)
        if start == -1:
            return blocks
        open_index = css.index("{", start)
        close_index = _matching_brace(css, open_index)
        blocks.append(css[start:close_index + 1])
        position = close_index + 1


def _block_with(css: str, max_width: int, selector: str) -> str:
    matches = [
        block
        for block in _media_blocks(css, max_width)
        if selector + " {" in block or selector + "::" in block
    ]
    assert matches, (
        f"no @media (max-width: {max_width}px) block contains {selector}"
    )
    return matches[0]


def _rule(text: str, selector: str) -> str:
    start = text.index(selector + " {")
    open_index = text.index("{", start)
    close_index = _matching_brace(text, open_index)
    return text[start:close_index + 1]


def _rule_from(text: str, needle: str) -> str:
    """Return the rule whose selector list contains needle."""
    start = text.index(needle)
    open_index = text.index("{", start)
    close_index = _matching_brace(text, open_index)
    return text[start:close_index + 1]


def _reduced_motion_block(css: str, selector: str) -> str:
    marker = "@media (prefers-reduced-motion: reduce)"
    position = 0
    while True:
        start = css.index(marker, position)
        open_index = css.index("{", start)
        close_index = _matching_brace(css, open_index)
        block = css[start:close_index + 1]
        if selector + " {" in block:
            return block
        position = close_index + 1


def test_card_is_white_elevated_surface():
    css = _read(STYLE_CSS)
    card = _rule(css, ".analysis-card")

    assert "background: var(--white);" in card
    assert "var(--cream)" not in card, (
        "the handoff calls for a white card, not the cream fill"
    )
    assert "border: 1px solid var(--border);" in card
    assert "border-radius: 32px;" in card
    assert "box-shadow: var(--shadow-pop);" in card
    assert "padding: 38px;" in card

    # The section intro copy stays AA on the page background.
    intro = _rule(css, ".analysis-intro p:last-child")
    assert "color: var(--olive);" in intro


def test_step_badges_match_pillar_badges():
    css = _read(STYLE_CSS)
    badge = _rule(css, ".input-number")
    pillar = _rule(css, ".pillar-number")

    for prop in (
        "width: 42px;",
        "height: 42px;",
        "border-radius: 50%;",
        "background: var(--accent-solid);",
        "color: var(--on-accent);",
        "font-size: 0.8rem;",
        "font-weight: 700;",
    ):
        assert prop in badge, prop
        assert prop in pillar, prop

    # The dark "sage chip" override no longer recolours this badge,
    # which kept it visually different from the pillar badge.
    assert "[data-theme=\"dark\"] .input-number" not in css

    # The step badge is not a text-entry control, so it is not part of
    # the iOS zoom-size list.
    coarse = css[css.index("@media (pointer: coarse)"):]
    assert ".input-number" not in coarse.split("}", 1)[0]


def test_fields_use_light_green_surface_and_green_focus():
    css = _read(STYLE_CSS)

    surface = _rule_from(css, ".analysis-card textarea")
    assert ".analysis-card .project-name {" in surface
    assert "background: var(--pistachio-soft);" in surface

    placeholder = _rule_from(css, ".analysis-card textarea::placeholder")
    assert "color: var(--field-placeholder);" in placeholder

    focus = _rule_from(css, ".analysis-card textarea:focus")
    assert "border-color: var(--ref-green-primary);" in focus
    assert "box-shadow: var(--field-focus-ring);" in focus

    root = _rule(css, ":root")
    dark = _rule(css, '[data-theme="dark"]')
    assert "--field-placeholder:" in root
    assert "--field-focus-ring:" in root
    assert "--field-placeholder:" in dark
    assert "--field-focus-ring:" in dark

    # The shared, unscoped field rules are still in place for other
    # forms; the Analyze changes only win by scope and specificity.
    shared_start = css.index("\ntextarea:focus,")
    shared = css[shared_start:css.index("}", shared_start)]
    assert "border-color: var(--pistachio);" in shared
    assert "#" not in surface
    assert "#" not in focus


def test_analyze_button_matches_hero_cta():
    css = _read(STYLE_CSS)
    button = _rule(css, ".analyze-button")
    hero = _rule(css, ".hero-button")

    assert "border-radius: 999px;" in button
    assert "border-radius: 999px;" in hero
    assert "color: var(--on-accent);" in button
    assert "var(--white)" not in button, (
        "dark-mode label contrast needs the on-accent token"
    )
    assert "box-shadow: var(--hero-cta-shadow);" in button
    assert "transform 0.18s ease," in button
    assert "box-shadow 0.18s ease," in button

    hover = _rule(css, ".analyze-button:hover")
    assert "transform: translateY(-3px);" in hover
    assert "box-shadow: var(--hero-cta-shadow-hover);" in hover

    focus = _rule(css, ".analyze-button:focus-visible")
    assert "outline: 3px solid var(--ref-green-primary);" in focus
    assert "outline-offset: 2px;" in focus

    # The two secondary actions share one chip surface now that the card
    # behind them is white; cream would have disappeared into the card.
    add = _rule(css, ".add-project-button")
    upload = _rule(css, ".upload-button")
    assert "background: var(--pistachio-soft);" in add
    assert "background: var(--pistachio-soft);" in upload
    assert "border-radius: 12px;" in add
    assert "border-radius: 12px;" in upload
    add_hover = _rule(css, ".add-project-button:hover")
    upload_hover = _rule(css, ".upload-button:hover")
    assert "background: var(--pistachio-light);" in add_hover
    assert "background: var(--pistachio-light);" in upload_hover

    html = _read(INDEX_HTML)
    assert 'id="analyze-button"' in html
    assert html.count('class="analyze-button"') == 1
    assert "Analyze My Career Gap" in html


def test_form_controls_have_visible_focus_rings():
    css = _read(STYLE_CSS)
    upload = _rule(css, ".upload-button:focus-visible")
    add = _rule_from(css, ".add-project-button:focus-visible")
    analyze = _rule(css, ".analyze-button:focus-visible")

    for rule in (upload, add, analyze):
        assert "outline: 3px solid var(--ref-green-primary);" in rule
        assert "outline-offset: 2px;" in rule

    assert ".remove-project-button:focus-visible {" in add

    # The old low-contrast ring is gone from the Analyze form controls.
    # Other components still use it site-wide, which is out of scope.
    for rule in (upload, add, analyze):
        assert "rgba(198, 216, 167, 0.45)" not in rule


def test_responsive_motion_and_markup_contracts_hold():
    css = _read(STYLE_CSS)

    tablet = _block_with(css, 950, ".analysis-section")
    assert "grid-template-columns: 1fr;" in _rule(tablet, ".analysis-section")
    assert "gap: 35px;" in _rule(tablet, ".analysis-section")

    mobile = _block_with(css, 700, ".analysis-card")
    assert "padding: 23px;" in _rule(mobile, ".analysis-card")

    reduced = _reduced_motion_block(css, ".analyze-button")
    assert "transition: none;" in _rule(reduced, ".analyze-button")
    for selector in (
        ".upload-button",
        ".add-project-button",
        ".remove-project-button",
    ):
        assert selector + "," in reduced or selector + " {" in reduced
    assert "transform: none;" in _rule(reduced, ".analyze-button:hover")
    assert css.index(reduced) > css.index(".analyze-button:hover"), (
        "the reduced-motion override must win the cascade"
    )

    html = _read(INDEX_HTML)
    assert html.count('class="input-number"') == 3
    assert html.count('class="input-group"') == 3
    assert html.count('class="upload-button"') == 2
    assert html.count('class="add-project-button"') == 1
    for anchor in (
        'id="resume"',
        'id="job-description"',
        'id="analyze"',
        'id="add-project"',
    ):
        assert anchor in html

    # New rules stay token-driven and the stylesheet stays balanced.
    for selector in (
        ".analysis-card textarea",
        ".analysis-card textarea:focus",
        ".input-number",
        ".analyze-button",
        ".analyze-button:hover",
        ".analyze-button:focus-visible",
        ".analysis-intro p:last-child",
    ):
        assert "#" not in _rule_from(css, selector)

    assert not re.findall(r"^\s*order:", css, re.MULTILINE)
    assert css.count("{") == css.count("}")
