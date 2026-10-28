"""Regression tests for the navbar focus order.

The navbar used to reorder its flex children with CSS ``order`` on
mobile, so the visual order (brand, controls, tabs) disagreed with
the DOM and keyboard order (brand, tabs, controls). The fix lists
the tabs last in the markup and keeps every breakpoint free of
``order``, so paint order and focus order always agree while the
desktop bar stays brand-left with the controls and tabs grouped
right.
"""

import re
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
STYLE_CSS = FRONTEND_DIR / "style.css"
INDEX_HTML = FRONTEND_DIR / "index.html"
SCRIPT_JS = FRONTEND_DIR / "script.js"


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


def test_nav_follows_account_area_in_dom():
    html = _read(INDEX_HTML)

    account = html.index('id="account-area"')
    nav = html.index('class="primary-nav"')
    nav_end = html.index("</nav>", nav)

    assert account < nav, "the tab nav must follow the account area"

    # Exactly one navbar, and the tabs stay inside .nav-inner.
    assert html.count('class="primary-nav"') == 1
    assert html.count('id="account-area"') == 1
    assert nav_end < html.index("</header>")

    assert 'aria-label="Primary navigation"' in html[nav:nav_end]


def test_no_css_order_overrides():
    css = _read(STYLE_CSS)

    # ``order`` is the only thing that can desync paint order from the
    # DOM, so the navbar must not use it at any breakpoint.
    assert not re.findall(r"^\s*order:", css, re.MULTILINE)

    # The mobile breakpoint only wraps the shell; it must not reorder
    # any individual navbar item.
    block = _block_with(css, 900, ".nav-inner")
    for selector in (
        ".brand",
        ".primary-nav",
        ".theme-toggle",
        ".account-area",
    ):
        assert selector not in block, (
            f"{selector} must not be reordered in the 900px breakpoint"
        )


def test_mobile_tab_row_unchanged():
    css = _read(STYLE_CSS)
    block = _block_with(css, 700, ".primary-nav")
    nav = _rule(block, ".primary-nav")

    # Tabs keep their own full-width, touch-scrollable row.
    assert "width: 100%;" in nav
    assert "min-width: 0;" in nav
    assert "overflow-x: auto;" in nav
    assert "scrollbar-width: none;" in nav

    # The right-edge fade stays pinned to the scroll viewport.
    assert "-webkit-mask-image: linear-gradient(" in nav
    assert "mask-image: linear-gradient(" in nav
    assert "calc(100% - 24px)" in nav

    scrollbar = _rule(block, ".primary-nav::-webkit-scrollbar")
    assert "display: none;" in scrollbar

    # Ordering the tabs into their own row is the wrapper's job.
    wrapper = _rule(_block_with(css, 900, ".nav-inner"), ".nav-inner")
    assert "flex-wrap: wrap;" in wrapper
    assert "height: auto;" in wrapper


def test_desktop_grouping_preserved():
    css = _read(STYLE_CSS)

    nav_inner = _rule(css, ".nav-inner")
    assert "display: flex;" in nav_inner
    assert "justify-content: space-between;" in nav_inner
    assert "gap: 12px;" in nav_inner
    assert "height: 76px;" in nav_inner
    assert "flex-wrap" not in nav_inner

    # Brand stays left; the theme toggle pushes the controls and tabs
    # into one right-hand group.
    assert "margin-left: auto;" in _rule(css, ".theme-toggle")


def test_nav_structure_and_labels_unchanged():
    html = _read(INDEX_HTML)
    js = _read(SCRIPT_JS)

    start = html.index('class="primary-nav"')
    nav = html[start:html.index("</nav>", start)]

    labels = [
        "Analyze",
        "Resume Builder",
        "Saved Analyses",
        "Interview Studio",
    ]
    positions = [nav.index(label) for label in labels]
    assert positions == sorted(positions), "nav labels must keep their order"
    assert nav.count("primary-nav-btn") == 4

    nav_ids = [
        "nav-analyze",
        "nav-resume-builder",
        "nav-saved-analyses",
        "nav-interview-studio",
    ]
    for nav_id in nav_ids:
        assert f'id="{nav_id}"' in nav

    assert html.count('id="theme-toggle"') == 1
    assert html.count('id="profile-trigger"') == 1

    # No artificial tab order, and no positional DOM access in JS.
    header_start = html.index('class="nav-inner"')
    header = html[header_start:html.index("</header>", header_start)]
    assert 'tabindex="' not in header
    assert '".primary-nav-btn"' in js
    assert "nextElementSibling" not in js
