"""Regression tests for the Part 2 navbar polish.

The homepage tabs sit in one rounded pill, the bar floats on a soft
shadow, and the active tab is a deep-green pill. All of it is scoped
to ``body:not(.account-page)`` so the single "Back to CareerGap" nav
on profile.html and settings.html keeps its current look. These tests
also pin the contracts the polish must not break: focus order, labels,
dark-mode tokens, and the 700px scroll row with its right-edge fade.
"""

import re
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
STYLE_CSS = FRONTEND_DIR / "style.css"
INDEX_HTML = FRONTEND_DIR / "index.html"

SCOPE = "body:not(.account-page) .primary-nav"


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


def _is_top_level(css: str, index: int) -> bool:
    """True when index sits outside every @media block."""
    depth = 0
    for char in css[:index]:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
    return depth == 0


def test_frosted_navbar_has_soft_shadow():
    css = _read(STYLE_CSS)
    navbar = _rule(css, ".navbar")

    assert "backdrop-filter: blur(14px);" in navbar
    assert "border-bottom:" in navbar
    assert "box-shadow" not in navbar, (
        "account pages keep the shared bar unchanged"
    )

    scope = "body:not(.account-page) .navbar"
    assert _is_top_level(css, css.index(scope))
    assert "box-shadow: var(--navbar-shadow);" in _rule(css, scope)

    # The shadow is a theme token, so dark mode never inherits a
    # light-only rgba value.
    assert "--navbar-shadow:" in _rule(css, ":root")
    assert "--navbar-shadow:" in _rule(css, '[data-theme="dark"]')


def test_homepage_tabs_sit_in_one_rounded_pill():
    css = _read(STYLE_CSS)
    pill = _rule(css, SCOPE)

    assert _is_top_level(css, css.index(SCOPE)), (
        "the pill must apply at desktop and tablet widths"
    )
    assert "padding: 4px;" in pill
    assert "border-radius: 999px;" in pill
    assert "background: var(--cream);" in pill
    assert "border: 1px solid var(--border);" in pill

    # profile.html and settings.html carry .account-page, so the scope
    # keeps their plain nav untouched.
    html = _read(INDEX_HTML)
    body_tag = re.search(r"<body[^>]*>", html).group(0)
    assert "account-page" not in body_tag
    for page in ("profile.html", "settings.html"):
        assert 'class="account-page"' in _read(FRONTEND_DIR / page)

    shared = _rule(css, ".primary-nav")
    assert "display: flex;" in shared
    assert "gap: 10px;" in shared
    assert "background" not in shared

    # Account pages keep the original standalone button treatment.
    shared_button = _rule(css, ".primary-nav-btn")
    assert "border: 1px solid var(--ref-green-border);" in shared_button
    assert "border-radius: 12px;" in shared_button
    assert "background: var(--ref-page);" in shared_button

    # 701-900px keeps the pill and only wraps the shell.
    for block in _media_blocks(css, 900):
        assert ".primary-nav" not in block


def test_inactive_tab_is_plain_with_subtle_hover():
    css = _read(STYLE_CSS)
    base = _rule(css, SCOPE + " .primary-nav-btn")
    hover = _rule(css, SCOPE + " .primary-nav-btn:hover")

    assert "background: transparent;" in base
    assert "border-color: transparent;" in base
    assert "border-radius: 999px;" in base
    assert "color: var(--ref-green-dark);" in base
    assert "0.18s ease" in base

    assert "background: var(--pistachio-soft);" in hover
    assert "#" not in hover, "hover must stay theme-token driven"


def test_active_tab_is_deep_green_pill_with_soft_shadow():
    css = _read(STYLE_CSS)
    active = _rule(css, SCOPE + " .primary-nav-btn.active")

    assert "background: var(--ref-green-primary);" in active
    assert "color: var(--white);" in active
    assert "box-shadow: var(--nav-pill-shadow);" in active
    assert "#" not in active, "the active pill must use theme tokens only"

    assert "--nav-pill-shadow:" in _rule(css, ":root")
    assert "--nav-pill-shadow:" in _rule(css, '[data-theme="dark"]')


def test_nav_buttons_have_visible_focus_ring():
    css = _read(STYLE_CSS)
    focus = _rule(css, SCOPE + " .primary-nav-btn:focus-visible")

    assert "outline: 3px solid var(--ref-green-primary);" in focus
    assert "outline-offset: 2px;" in focus


def test_mobile_scroll_fade_and_focus_order_preserved():
    css = _read(STYLE_CSS)
    block = _block_with(css, 700, ".primary-nav")
    nav = _rule(block, ".primary-nav")

    assert "width: 100%;" in nav
    assert "min-width: 0;" in nav
    assert "overflow-x: auto;" in nav
    assert "scrollbar-width: none;" in nav
    assert "-webkit-mask-image: linear-gradient(" in nav
    assert "calc(100% - 24px)" in nav

    # On phones the tabs keep the desktop pill surface inside a
    # horizontally scrolling capsule, with the fades on the wrapper.
    reset = _rule(block, SCOPE)
    assert not _is_top_level(block, block.index(SCOPE))
    assert "width: max-content;" in reset
    assert "position: relative;" in reset
    assert "gap: 2px;" in reset
    assert "padding: 4px;" in reset
    assert "border: 1px solid var(--border);" in reset
    assert "border-radius: 999px;" in reset
    assert "background: var(--cream);" in reset
    assert "overflow-x: visible;" in reset
    assert "mask-image: none;" in reset

    block_start = css.index(block)
    assert css.index(SCOPE) < block_start
    assert block_start < css.index(SCOPE, block_start), (
        "the mobile reset must come after the desktop pill"
    )

    # Focus order and labels are untouched by the polish.
    assert not re.findall(r"^\s*order:", css, re.MULTILINE)

    html = _read(INDEX_HTML)
    nav_start = html.index('class="primary-nav"')
    nav_html = html[nav_start:html.index("</nav>", nav_start)]

    assert html.index('id="account-area"') < nav_start
    labels = ["Analyze", "Resume Builder", "Saved Analyses", "Interview Studio"]
    positions = [nav_html.index(label) for label in labels]
    assert positions == sorted(positions)
    assert nav_html.count("primary-nav-btn") == 4
