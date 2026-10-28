"""Regression tests for the responsive hero illustration.

The hero chart is a decorative absolutely-positioned SVG. It must stay
on wide screens, disappear before it can cover the headline, and must
not leave the phone hero pinned to a tall empty min-height.
"""

import re
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
STYLE_CSS = FRONTEND_DIR / "style.css"
INDEX_HTML = FRONTEND_DIR / "index.html"


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
        if selector + " {" in block
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


def test_illustration_hidden_below_wide_breakpoint():
    css = _read(STYLE_CSS)
    block = _block_with(css, 1100, ".hero-illustration")
    illustration = _rule(block, ".hero-illustration")

    assert "display: none;" in illustration
    assert block.count("@media") == 1, "the hide rule must be its own breakpoint"


def test_desktop_illustration_unchanged():
    css = _read(STYLE_CSS)
    illustration = _rule(css, ".hero-illustration")

    assert "position: absolute;" in illustration
    assert "right: 0;" in illustration
    assert "top: 50%;" in illustration
    assert "transform: translateY(-50%);" in illustration
    assert "width: 420px;" in illustration
    assert "height: 520px;" in illustration
    assert "max-width: 45%;" in illustration
    assert "pointer-events: none;" in illustration
    assert "display: none" not in illustration, (
        "the base desktop rule must keep painting the chart"
    )


def test_illustration_is_decorative():
    html = _read(INDEX_HTML)
    start = html.index('<div class="hero-illustration"')
    block = html[start:html.index("</div>", start)]

    assert 'aria-hidden="true"' in block
    assert "tabindex" not in block
    assert not re.search(r"<(a|button|input|select|textarea)\b", block), (
        "hiding the chart must not remove an interactive control"
    )


def test_mobile_hero_height_collapses():
    css = _read(STYLE_CSS)
    block = _block_with(css, 700, ".hero")
    hero = _rule(block, ".hero")

    assert "min-height: 0;" in hero
    assert "min-height: 570px;" not in hero
    assert "padding: 40px 0 48px;" in hero

    heading = _rule(block, ".hero h1")
    assert "font-size: 3.4rem;" in heading, (
        "the mobile fix must not shrink the headline"
    )


def test_only_one_hide_rule():
    css = _read(STYLE_CSS)

    assert css.count(".hero-illustration {") == 2, (
        "the base rule plus exactly one responsive hide rule"
    )

    for max_width in (950, 900):
        assert all(
            ".hero-illustration" not in block
            for block in _media_blocks(css, max_width)
        ), f"the {max_width}px breakpoint must not hide the chart"
