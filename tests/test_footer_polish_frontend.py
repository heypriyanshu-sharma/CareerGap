"""Regression tests for the Part 2 site-footer polish.

The main footer is now a deep forest-green band that spans the viewport,
with rounded top corners, light text and comfortable padding. The brand,
tagline, GitHub link and copyright keep their exact copy, and the link
gains a clear hover, active and focus-visible treatment on the dark
surface. Everything is scoped to ``.site-footer`` so the ATS modal
footer keeps its current look, and the single moving part honours
reduced-motion.
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


def _token(block: str, name: str) -> str:
    match = re.search(rf"{re.escape(name)}:\s*([^;]+);", block)
    assert match, f"{name} is missing"
    return match.group(1).strip()


def _luminance(hex_colour: str) -> float:
    value = hex_colour.lstrip("#")
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [
        channel / 12.92
        if channel <= 0.03928
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(foreground: str, background: str) -> float:
    high, low = sorted(
        (_luminance(foreground), _luminance(background)), reverse=True
    )
    return (high + 0.05) / (low + 0.05)


def _footer_markup(html: str) -> str:
    start = html.index('<footer class="site-footer">')
    return html[start:html.index("</footer>", start) + len("</footer>")]


def test_footer_is_a_full_width_forest_band():
    css = _read(STYLE_CSS)
    footer = _rule(css, ".site-footer")

    assert "width: 100%;" in footer
    assert "margin: 0;" in footer
    assert "background: var(--accent-solid);" in footer
    assert "color: var(--on-accent);" in footer
    assert "border-top: 1px solid var(--on-accent-track);" in footer
    assert "border-radius: 32px 32px 0 0;" in footer
    assert "display: flex;" in footer
    assert "justify-content: space-between;" in footer
    assert "flex-wrap: wrap;" in footer
    assert "gap: 16px 28px;" in footer
    assert (
        "padding: 36px max(5%, calc((100% - 1180px) / 2)) 40px;" in footer
    ), "the band must stay aligned with the 1180px / 90% page grid"
    assert "#" not in footer, "the band must resolve through theme tokens"

    # The previous cream-on-cream rule used a 4.37:1 text colour on the
    # page background, so the footer must not fall back to it.
    assert "var(--olive-soft)" not in footer
    assert "var(--border)" not in footer

    root = _rule(css, ":root")
    dark = _rule(css, '[data-theme="dark"]')
    for block in (root, dark):
        assert "--accent-solid:" in block
        assert "--on-accent:" in block
        assert "--on-accent-track:" in block
        assert "--on-accent-icon-bg:" in block


def test_brand_and_footer_copy_keep_aa_contrast():
    css = _read(STYLE_CSS)
    footer = _rule(css, ".site-footer")
    brand = _rule(css, ".site-footer strong")
    brand_row = _rule(css, ".site-footer div")
    copyright = _rule(css, ".site-footer > span")

    assert "font-size: 1.05rem;" in brand
    assert "font-weight: 800;" in brand
    assert "letter-spacing: -0.01em;" in brand
    assert "color: var(--on-accent);" in brand

    assert "display: flex;" in brand_row
    assert "align-items: center;" in brand_row
    assert "gap: 14px;" in brand_row

    assert "font-size: 0.78rem;" in copyright
    assert "letter-spacing: 0.01em;" in copyright
    assert "font-size: 0.82rem;" in footer

    root = _rule(css, ":root")
    dark = _rule(css, '[data-theme="dark"]')
    for block in (root, dark):
        on_accent = _token(block, "--on-accent")
        accent = _token(block, "--accent-solid")
        assert _contrast(on_accent, accent) >= 4.5, (
            "the footer's small text must stay AA on the forest band"
        )


def test_github_link_has_light_chip_and_visible_states():
    css = _read(STYLE_CSS)
    link = _rule(css, ".github-link")
    hover = _rule(css, ".github-link:hover")
    active = _rule(css, ".github-link:active")
    focus = _rule(css, ".github-link:focus-visible")
    icon = _rule(css, ".github-icon")

    assert "width: 42px;" in link
    assert "height: 42px;" in link, "the target must clear the 24px minimum"
    assert "border-radius: 12px;" in link
    assert "color: var(--on-accent);" in link
    assert "background: var(--on-accent-icon-bg);" in link
    assert "border: 1px solid var(--on-accent-track);" in link
    for prop in (
        "background 0.18s ease,",
        "border-color 0.18s ease,",
        "color 0.18s ease,",
        "transform 0.18s ease",
    ):
        assert prop in link, prop

    assert "background: var(--on-accent);" in hover
    assert "border-color: var(--on-accent);" in hover
    assert "color: var(--accent-solid);" in hover
    assert "transform: translateY(-1px);" in hover
    assert "transform: translateY(0);" in active

    assert "outline: 3px solid var(--on-accent);" in focus
    assert "outline-offset: 3px;" in focus
    assert "rgba(198, 216, 167, 0.45)" not in focus

    assert "width: 20px;" in icon
    assert "height: 20px;" in icon

    html = _read(INDEX_HTML)
    footer = _footer_markup(html)
    assert footer.count('class="github-link"') == 1
    assert 'aria-label="Visit GitHub profile"' in footer
    assert 'title="Visit GitHub profile"' in footer
    assert 'href="https://github.com/priyanshumakes"' in footer
    assert 'target="_blank"' in footer
    assert 'rel="noopener noreferrer"' in footer
    assert 'class="github-icon"' in footer

    # The idle icon is non-text (3:1 minimum); the hover inversion is a
    # text-strength pairing so it clears 4.5:1 in both themes.
    root = _rule(css, ":root")
    dark = _rule(css, '[data-theme="dark"]')
    for block in (root, dark):
        icon = _token(block, "--on-accent")
        band = _token(block, "--accent-solid")
        assert _contrast(icon, band) >= 3.0
        hover_icon = _token(block, "--accent-solid")
        hover_bg = _token(block, "--on-accent")
        assert _contrast(hover_icon, hover_bg) >= 4.5


def test_footer_stacks_cleanly_on_phones():
    css = _read(STYLE_CSS)

    tablet_or_phone = _block_with(css, 700, ".site-footer")
    phone = _rule(tablet_or_phone, ".site-footer")
    assert "flex-direction: column;" in phone
    assert "align-items: flex-start;" in phone
    assert "gap: 16px;" in phone
    assert "padding: 30px 5% 34px;" in phone
    assert "border-radius: 26px 26px 0 0;" in phone

    # The results footer keeps its previous stacking contract.
    results = _rule(tablet_or_phone, ".results-footer")
    assert "flex-direction: column;" in results
    assert "gap: 12px;" in results

    assert sum(
        ".site-footer {" in block for block in _media_blocks(css, 700)
    ) == 1


def test_motion_and_cascade_contracts_hold():
    css = _read(STYLE_CSS)

    reduced = _reduced_motion_block(css, ".github-link")
    assert "transition: none;" in _rule(reduced, ".github-link")
    assert (
        "transform: none;"
        in _rule(reduced, ".github-link:hover,\n    .github-link:active")
    )
    assert css.index(reduced) > css.index(".github-link:hover"), (
        "the reduced-motion override must win the cascade"
    )

    for selector in (
        ".site-footer",
        ".site-footer strong",
        ".site-footer > span",
        ".github-link",
        ".github-link:hover",
        ".github-link:active",
        ".github-link:focus-visible",
    ):
        assert "!important" not in _rule(css, selector)

    assert not re.findall(r"^\s*order:", css, re.MULTILINE)
    assert css.count("{") == css.count("}")


def test_modal_footer_and_copy_are_untouched():
    css = _read(STYLE_CSS)
    modal = _rule(css, ".ats-modal-footer")

    # The ATS modal footer keeps its own surface and border.
    assert "background: var(--pistachio-soft);" in modal
    assert "border-top: 1px solid var(--border);" in modal
    assert "border-radius" not in modal
    assert "var(--accent-solid)" not in modal
    assert "var(--on-accent)" not in modal

    html = _read(INDEX_HTML)
    footer = _footer_markup(html)
    assert footer.count("<strong>") == 1
    assert "CareerGap" in footer
    assert "Keep growing." in footer
    assert "© 2026 CareerGap" in footer
    assert footer.count("<span>") == 2
    assert footer.count("<div") == 2
    assert html.count('<footer class="site-footer">') == 1
    assert html.count('class="ats-modal-footer"') == 1
