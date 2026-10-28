"""Regression tests for the mobile navbar shell.

The mobile navbar is pure CSS: a wrapping flex row whose order
decides whether the tabs share a row with the controls or get
their own scrollable line. These tests pin the two-row layout,
its scroll affordances, and the desktop rules it must not change.
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


def test_mobile_nav_puts_tabs_after_brand_and_controls():
    css = _read(STYLE_CSS)
    block = _block_with(css, 900, ".primary-nav")

    assert "order: 1;" in _rule(block, ".brand")
    assert "order: 2;" in _rule(block, ".theme-toggle")
    assert "margin-left: auto;" in _rule(block, ".theme-toggle")
    assert "order: 3;" in _rule(block, ".account-area")
    assert "order: 4;" in _rule(block, ".primary-nav")

    # Exactly four ordering rules, all in the wrapping breakpoint.
    assert len(re.findall(r"^\s*order:", css, re.MULTILINE)) == 4


def test_mobile_nav_row_is_horizontally_scrollable():
    css = _read(STYLE_CSS)
    nav = _rule(_block_with(css, 700, ".primary-nav"), ".primary-nav")

    assert "width: 100%;" in nav
    assert "min-width: 0;" in nav
    assert "overflow-x: auto;" in nav


def test_mobile_nav_hides_native_scrollbar():
    css = _read(STYLE_CSS)
    block = _block_with(css, 700, ".primary-nav")
    nav = _rule(block, ".primary-nav")
    scrollbar = _rule(block, ".primary-nav::-webkit-scrollbar")

    assert "scrollbar-width: none;" in nav
    assert "display: none;" in scrollbar


def test_mobile_nav_fades_right_edge():
    css = _read(STYLE_CSS)
    block = _block_with(css, 700, ".primary-nav")
    nav = _rule(block, ".primary-nav")

    assert "mask-image: linear-gradient(" in nav
    assert "-webkit-mask-image: linear-gradient(" in nav
    assert "calc(100% - 24px)" in nav
    assert "transparent" in nav

    # The fade belongs to the scroll viewport, not the whole navbar.
    nav_inner = _rule(_block_with(css, 900, ".nav-inner"), ".nav-inner")
    assert "mask-image" not in nav_inner


def test_desktop_nav_unchanged():
    css = _read(STYLE_CSS)

    nav_inner = _rule(css, ".nav-inner")
    assert "width: min(1180px, 90%);" in nav_inner
    assert "height: 76px;" in nav_inner
    assert "display: flex;" in nav_inner
    assert "flex-wrap" not in nav_inner
    assert not re.search(r"^\s*order:", nav_inner, re.MULTILINE)

    primary = _rule(css, ".primary-nav")
    assert "display: flex;" in primary
    assert not re.search(r"^\s*order:", primary, re.MULTILINE)

    button = _rule(css, ".primary-nav-btn")
    assert "white-space: nowrap;" in button


def test_nav_labels_and_order_unchanged():
    html = _read(INDEX_HTML)
    nav_start = html.index('class="primary-nav"')
    nav = html[nav_start:html.index("</nav>", nav_start)]

    labels = ["Analyze", "Resume Builder", "Saved Analyses", "Interview Studio"]
    positions = [nav.index(label) for label in labels]
    assert positions == sorted(positions), "nav labels must keep their order"
    assert nav.count("primary-nav-btn") == 4

    assert re.search(r'id="theme-toggle"', html)
    assert len(re.findall(r'id="profile-trigger"', html)) == 1
