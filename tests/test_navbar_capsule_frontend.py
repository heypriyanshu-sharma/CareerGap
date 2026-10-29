"""Regression tests for the phone capsule navbar.

At 700px and narrower the homepage tabs live in one rounded capsule
(the desktop pill surface) that scrolls sideways inside a wrapper
viewport. A glider pill behind the active tab slides between tabs
(translateX + width, driven from script.js) and the capsule scrolls
the tapped tab fully into view. Everything is gated behind the 700px
breakpoint and a matchMedia check so wider screens keep the desktop
pill untouched; the glider is display:none outside the phone layout
and the wrapper is display:contents there.
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


def _media_blocks(css: str, marker: str) -> list:
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


def _rule(text: str, selector: str) -> str:
    start = text.index(selector + " {")
    open_index = text.index("{", start)
    close_index = _matching_brace(text, open_index)
    return text[start:close_index + 1]


def _phone_block(css: str, selector: str) -> str:
    matches = [
        block
        for block in _media_blocks(css, "@media (max-width: 700px)")
        if selector + " {" in block
    ]
    assert matches, f"no 700px block contains {selector}"
    return matches[0]


# ============================================================
# MARKUP
# ============================================================

def test_nav_is_wrapped_in_scroll_viewport_with_glider():
    html = _read(INDEX_HTML)

    wrap = html.index('class="primary-nav-scroll"')
    nav = html.index('class="primary-nav"')
    glider = html.index('class="primary-nav-glider"')
    first_tab = html.index('id="nav-analyze"')
    close_nav = html.index("</nav>", nav)
    close_wrap = html.index("</div>", close_nav)

    # Wrapper around the nav, glider inside before the first tab.
    assert wrap < nav < glider < first_tab < close_nav < close_wrap
    assert 'aria-hidden="true"' in html[glider:html.index(">", glider)]

    # Exactly one wrapper and one glider, all four tabs intact.
    assert html.count('class="primary-nav-scroll"') == 1
    assert html.count('class="primary-nav-glider"') == 1
    assert html.count("primary-nav-btn") == 4


# ============================================================
# DESKTOP IS UNTOUCHED
# ============================================================

def test_wrapper_and_glider_are_inert_by_default():
    css = _read(STYLE_CSS)

    wrap = _rule(css, ".primary-nav-scroll")
    assert "display: contents;" in wrap

    glider = _rule(css, ".primary-nav-glider")
    assert "display: none;" in glider


def test_capsule_rules_only_exist_inside_phone_breakpoint():
    css = _read(STYLE_CSS)

    # Every capsule/glider rule beyond the inert defaults must live
    # inside a max-width: 700px block, never at top level.
    phone = _phone_block(css, ".primary-nav-scroll")
    for selector in (
        ".primary-nav-scroll.nav-scrolled",
        ".primary-nav-scroll.nav-scroll-end",
        "body:not(.account-page) .primary-nav",
        ".primary-nav-glider.no-transition",
    ):
        assert selector + " {" in phone

    top_level_glider = _rule(css, ".primary-nav-glider")
    assert "position" not in top_level_glider
    assert "transition" not in top_level_glider

    # The desktop pill and buttons keep their shared rules.
    pill = _rule(css, "body:not(.account-page) .primary-nav")
    assert "border-radius: 999px;" in pill
    assert "background: var(--cream);" in pill
    assert "width: max-content" not in pill


# ============================================================
# PHONE CAPSULE STYLING
# ============================================================

def test_glider_carries_the_active_pill_on_phones():
    css = _read(STYLE_CSS)
    block = _phone_block(css, ".primary-nav-glider")
    glider = _rule(block, ".primary-nav-glider")

    assert "display: block;" in glider
    assert "position: absolute;" in glider
    assert "border-radius: 999px;" in glider
    assert "background: var(--ref-green-primary);" in glider
    assert "box-shadow: var(--nav-pill-shadow);" in glider
    assert "transform 0.45s" in glider
    assert "width 0.45s" in glider
    assert "#" not in re.sub(r"#000", "", glider), (
        "the glider must use theme tokens only"
    )

    # The active tab's own fill is removed so the glider shows.
    active = _rule(
        block,
        "body:not(.account-page) .primary-nav .primary-nav-btn.active",
    )
    assert "background: transparent;" in active
    assert "box-shadow: none;" in active
    assert "color: var(--white);" in active


def test_glider_respects_reduced_motion():
    css = _read(STYLE_CSS)
    blocks = [
        block
        for block in _media_blocks(
            css, "@media (prefers-reduced-motion: reduce)"
        )
        if ".primary-nav-glider" in block
    ]
    assert blocks, "glider missing from reduced-motion handling"
    assert "transition: none;" in blocks[0]


# ============================================================
# SCRIPT BEHAVIOR
# ============================================================

def test_script_gates_capsule_behind_phone_breakpoint():
    js = _read(SCRIPT_JS)

    assert 'window.matchMedia(\n                "(max-width: 700px)"\n            )' in js
    # Every entry point checks the phone query before acting.
    for fn in ("updatePrimaryNavGlider", "scrollPrimaryNavActive"):
        start = js.index(f"function {fn}(")
        head = js[start:start + 400]
        assert "mobileNavQuery.matches" in head, fn


def test_script_slides_glider_and_scrolls_active_tab_into_view():
    js = _read(SCRIPT_JS)

    # Glider is moved with translateX + width, never layout props.
    assert '"translateX("' in js
    assert "primaryNavGlider.style.width" in js
    assert "no-transition" in js

    # The tapped tab scrolls fully into view, smooth unless the
    # user asked for reduced motion.
    assert "primaryNavScroll.scrollTo({" in js
    assert '"smooth"' in js
    assert "navMotionQuery.matches" in js
    assert "(prefers-reduced-motion: reduce)" in js

    # View switches drive both behaviors.
    hook = js.index("updatePrimaryNavGlider(true);")
    assert js.index("scrollPrimaryNavActive();", hook) > hook

    # Fades follow scroll position; geometry refreshes on resize
    # and once webfonts settle.
    assert '"scroll"' in js
    assert '"resize"' in js
    assert "document.fonts?.ready" in js
    assert "nav-scrolled" in js
    assert "nav-scroll-end" in js
