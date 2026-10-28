"""Regression tests for the Part 2 hero polish.

The hero eyebrow becomes a rounded badge, the headline tightens, the
description grows and narrows, and the call-to-action turns into a pill
with a soft green shadow. A radial glow sits behind the artwork on wide
screens only. Everything is CSS-only: the copy, the markup, the
``href``, and the other four section eyebrows must stay exactly as they
are, and the polish has to keep working in dark mode and on mobile.
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


def _reduced_motion_block(css: str) -> str:
    marker = "@media (prefers-reduced-motion: reduce)"
    position = 0
    while True:
        start = css.index(marker, position)
        open_index = css.index("{", start)
        close_index = _matching_brace(css, open_index)
        block = css[start:close_index + 1]
        if ".hero-button {" in block:
            return block
        position = close_index + 1


def _hero_section(html: str) -> str:
    start = html.index('<section class="hero">')
    return html[start:html.index("</section>", start)]


def test_eyebrow_badge_is_scoped_to_the_hero():
    css = _read(STYLE_CSS)
    badge = _rule(css, ".hero .eyebrow")

    assert "display: inline-block;" in badge
    assert "padding: 7px 14px;" in badge
    assert "border: 1px solid var(--border);" in badge
    assert "border-radius: 999px;" in badge
    assert "background: var(--pistachio-soft);" in badge
    assert "color: var(--olive);" in badge
    assert "#" not in badge, "the badge must resolve through theme tokens"

    # The shared eyebrow rule keeps its flat treatment and wide tracking,
    # so the four section eyebrows outside the hero are unchanged.
    base = _rule(css, ".eyebrow")
    assert "padding" not in base
    assert "background" not in base
    assert "border" not in base
    assert "letter-spacing: 0.22em;" in base

    html = _read(INDEX_HTML)
    assert html.count('class="eyebrow"') == 5
    hero = _hero_section(html)
    assert hero.count('class="eyebrow"') == 1
    assert "CAREER READINESS ENGINE" in hero


def test_headline_tightened_without_copy_change():
    css = _read(STYLE_CSS)
    heading = _rule(css, ".hero h1")

    assert "font-weight: 800;" in heading
    assert "line-height: 0.94;" in heading
    assert "letter-spacing: -0.06em;" in heading

    # The responsive clamp, colour, and top margin are untouched.
    assert "clamp(3.2rem, 7vw, 6rem);" in heading
    assert "color: var(--olive-dark);" in heading
    assert "margin-top: 18px;" in heading

    hero = _hero_section(_read(INDEX_HTML))
    heading_html = hero[
        hero.index("<h1>") : hero.index("</h1>", hero.index("<h1>"))
    ]
    assert "Build a career" in heading_html
    assert "that actually grows." in heading_html
    assert heading_html.count("<br>") == 1


def test_description_is_larger_and_capped():
    css = _read(STYLE_CSS)
    description = _rule(css, ".hero-description")

    assert "font-size: 1.18rem;" in description
    assert "line-height: 1.7;" in description
    assert "max-width: 560px;" in description
    assert "color: var(--hero-description);" in description
    assert "margin-top: 28px;" in description

    # AA body text on the page background, in both themes.
    assert "--hero-description: #62735A;" in _rule(css, ":root")
    assert (
        "--hero-description: var(--olive-soft);"
        in _rule(css, '[data-theme="dark"]')
    )


def test_cta_is_pill_with_soft_green_shadow():
    css = _read(STYLE_CSS)
    button = _rule(css, ".hero-button")

    assert "border-radius: 999px;" in button
    assert "box-shadow: var(--hero-cta-shadow);" in button
    assert "transform 0.18s ease," in button
    assert "box-shadow 0.18s ease;" in button
    assert "background: var(--accent-solid);" in button

    hover = _rule(css, ".hero-button:hover")
    assert "transform: translateY(-3px);" in hover
    assert "box-shadow: var(--hero-cta-shadow-hover);" in hover
    assert "#" not in hover

    focus = _rule(css, ".hero-button:focus-visible")
    assert "outline: 3px solid var(--ref-green-primary);" in focus
    assert "outline-offset: 2px;" in focus

    # Both shadow tokens, and the glow, are theme-aware.
    light = _rule(css, ":root")
    dark = _rule(css, '[data-theme="dark"]')
    for token in ("--hero-cta-shadow", "--hero-cta-shadow-hover"):
        assert token + ":" in light
        assert token + ":" in dark

    # Label and link are unchanged.
    hero = _hero_section(_read(INDEX_HTML))
    assert 'href="#analyze"' in hero
    assert "Analyze My Career Gap" in hero
    assert hero.count('class="hero-button"') == 1


def test_hero_glow_is_wide_screen_only():
    css = _read(STYLE_CSS)
    glow = _rule(css, ".hero::before")

    assert "content: \"\";" in glow
    assert "radial-gradient(" in glow
    assert "var(--hero-glow)" in glow
    assert "transparent 70%" in glow
    assert "pointer-events: none;" in glow
    assert "z-index: 0;" in glow

    # The copy and the chart paint above the glow.
    assert "z-index: 1;" in _rule(css, ".hero-content")
    assert "z-index: 1;" in _rule(css, ".hero-illustration")

    assert "--hero-glow:" in _rule(css, ":root")
    assert "--hero-glow:" in _rule(css, '[data-theme="dark"]')

    # Below 1100px the artwork is hidden, and the glow goes with it.
    block = _block_with(css, 1100, ".hero::before")
    assert "display: none;" in _rule(block, ".hero::before")
    assert "display: none;" in _rule(block, ".hero-illustration")


def test_responsive_and_existing_hero_contracts_hold():
    css = _read(STYLE_CSS)

    block = _block_with(css, 700, ".hero")
    hero = _rule(block, ".hero")
    assert "min-height: 0;" in hero
    assert "padding: 40px 0 48px;" in hero
    assert "font-size: 3.4rem;" in _rule(block, ".hero h1")

    # The illustration keeps its existing contract and its single hide rule.
    illustration = _rule(css, ".hero-illustration")
    for prop in (
        "position: absolute;",
        "right: 0;",
        "top: 50%;",
        "transform: translateY(-50%);",
        "width: 420px;",
        "height: 520px;",
        "max-width: 45%;",
        "pointer-events: none;",
    ):
        assert prop in illustration
    assert css.count(".hero-illustration {") == 2

    # No hard-coded colours in the new polish rules.
    for selector in (
        ".hero::before",
        ".hero-button",
        ".hero-button:hover",
        ".hero-button:focus-visible",
    ):
        assert "#" not in _rule(css, selector)

    assert not re.findall(r"^\s*order:", css, re.MULTILINE)
    assert css.count("{") == css.count("}")

    # Reduced-motion users keep the colour and shadow but lose the lift.
    reduced = _reduced_motion_block(css)
    assert "transition: none;" in _rule(reduced, ".hero-button")
    assert "transform: none;" in _rule(reduced, ".hero-button:hover")
    assert css.index(reduced) > css.index(".hero-button:hover"), (
        "the reduced-motion override must win the cascade"
    )
