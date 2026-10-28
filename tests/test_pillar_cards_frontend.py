"""Regression tests for the Part 2 pillar-card polish.

The three "How it works" cards should read as elevated white surfaces on
the cream page: generous padding, a soft border, large rounded corners,
and a gentle hover lift that falls away under reduced motion. The step
badges stay deep-green circles because Section 4 reuses them. These
tests also pin the responsive single-column fallback and the untouched
copy, markup, and IDs.
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


def _pillar_section(html: str) -> str:
    start = html.index('class="pillars"')
    return html[start:html.index("</section>", start)]


def test_cards_are_white_elevated_surfaces():
    css = _read(STYLE_CSS)
    card = _rule(css, ".pillar-card")

    assert "background: var(--white);" in card
    assert "var(--pistachio-light)" not in card, (
        "the handoff calls for a white card, not the pale-green fill"
    )
    assert "border: 1px solid var(--border);" in card
    assert "border-radius: var(--radius-lg);" in card
    assert "box-shadow: var(--shadow-soft);" in card
    assert "padding: 26px;" in card
    assert "#" not in card, "the surface must resolve through theme tokens"

    # White and the shadow tokens both flip with the theme.
    dark = _rule(css, '[data-theme="dark"]')
    assert "--white:" in dark
    assert "--shadow-soft:" in dark


def test_grid_and_heading_spacing():
    css = _read(STYLE_CSS)
    grid = _rule(css, ".pillar-grid")

    assert "repeat(3, 1fr);" in grid
    assert "gap: 20px;" in grid
    assert "display: grid;" in grid

    heading = _rule(css, ".pillars .section-heading")
    assert "margin-bottom: 28px;" in heading

    # The shared default is left alone for any other section.
    assert "margin-bottom: 16px;" in _rule(css, ".section-heading")


def test_hover_lift_is_gentle_and_motion_safe():
    css = _read(STYLE_CSS)
    card = _rule(css, ".pillar-card")
    hover = _rule(css, ".pillar-card:hover")

    assert "transform 0.18s ease," in card
    assert "box-shadow 0.18s ease;" in card
    assert "transform: translateY(-4px);" in hover
    assert "box-shadow: var(--shadow-pop);" in hover

    reduced = _reduced_motion_block(css, ".pillar-card")
    assert "transition: none;" in _rule(reduced, ".pillar-card")
    assert "transform: none;" in _rule(reduced, ".pillar-card:hover")
    assert css.index(reduced) > css.index(".pillar-card:hover"), (
        "the reduced-motion override must win the cascade"
    )


def test_step_badges_stay_deep_green_circles():
    css = _read(STYLE_CSS)
    number = _rule(css, ".pillar-number")

    assert "border-radius: 50%;" in number
    assert "background: var(--accent-solid);" in number
    assert "color: var(--on-accent);" in number
    assert "width: 42px;" in number
    assert "height: 42px;" in number
    assert "font-weight: 700;" in number

    # Section 4 reuses these badges, so the geometry stays put.
    assert "44px" not in number


def test_typography_and_responsive_contracts_hold():
    css = _read(STYLE_CSS)

    heading = _rule(css, ".pillar-card h3")
    assert "margin-top: 14px;" in heading
    assert "font-size: 1.25rem;" in heading
    assert "letter-spacing: -0.01em;" in heading

    body = _rule(css, ".pillar-card p")
    assert "margin-top: 8px;" in body
    assert "font-size: 0.92rem;" in body
    assert "line-height: 1.6;" in body
    assert "color: var(--olive-soft);" in body

    # Only the grid reflows; the cards themselves stay condition-free.
    mobile = _block_with(css, 700, ".pillar-grid")
    assert "grid-template-columns: 1fr;" in _rule(mobile, ".pillar-grid")
    assert sum(".pillar-grid {" in block for block in _media_blocks(css, 700)) == 1
    for width in (700, 900, 1100):
        for block in _media_blocks(css, width):
            assert ".pillar-card {" not in block

    # Copy, structure, and IDs are untouched by the CSS polish.
    html = _read(INDEX_HTML)
    section = _pillar_section(html)
    assert section.count('class="pillar-card"') == 3
    assert section.count('class="pillar-number"') == 3
    for label in ("Identify", "Understand", "Strengthen"):
        assert label in section
    for number in ("01", "02", "03"):
        assert number in section
    assert 'id="how-it-works"' in html

    # New rules stay token-driven and the stylesheet stays balanced.
    for selector in (
        ".pillar-grid",
        ".pillar-card",
        ".pillar-card:hover",
        ".pillar-card h3",
        ".pillar-card p",
        ".pillars .section-heading",
    ):
        assert "#" not in _rule(css, selector)
    assert not re.findall(r"^\s*order:", css, re.MULTILINE)
    assert css.count("{") == css.count("}")
