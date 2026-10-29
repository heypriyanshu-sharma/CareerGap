"""Plain-text CareerGap explanation, opened by the unchanged hero label."""
from pathlib import Path

FRONTEND = Path(__file__).resolve().parent.parent / 'frontend'


def test_about_dialog_is_named_text_only_and_keeps_badge_label():
    html = (FRONTEND / 'index.html').read_text()
    assert 'CAREER READINESS ENGINE' in html
    assert 'id="about-careergap-trigger"' in html
    assert 'aria-haspopup="dialog"' in html
    start = html.index('<dialog')
    end = html.index('</dialog>', start)
    dialog = html[start:end]
    assert 'aria-label="About CareerGap"' in dialog
    assert 'aria-describedby="about-careergap-description"' in dialog
    assert 'CareerGap compares your resume with a job description' in dialog
    assert '<svg' not in dialog and '<button' not in dialog


def test_about_dialog_uses_native_modal_and_restores_focus():
    js = (FRONTEND / 'script.js').read_text()
    assert 'aboutDialog.showModal();' in js
    assert 'aboutDialog.focus({ preventScroll: true });' in js
    assert 'aboutDialog.addEventListener("close"' in js
    assert 'aboutTrigger.focus({ preventScroll: true });' in js


def test_about_dialog_dismisses_only_outside_its_bounds():
    js = (FRONTEND / 'script.js').read_text()
    assert 'event.target === aboutDialog' in js
    for edge in ['left', 'right', 'top', 'bottom']:
        assert f'bounds.{edge}' in js
    assert 'aboutDialog.close();' in js


def test_about_dialog_is_compact_centered_and_theme_aware():
    css = (FRONTEND / 'style.css').read_text()
    start = css.index('#about-careergap-dialog {')
    rule = css[start:css.index('}', start)]
    for value in ['position: fixed;', 'inset: 0;', 'margin: auto;',
                  'width: min(400px, calc(100vw - 40px));',
                  'background: var(--cream);', 'color: var(--olive-dark);']:
        assert value in rule


def test_about_badge_has_raised_and_pressed_depth():
    css = (FRONTEND / 'style.css').read_text()
    start = css.index('#about-careergap-trigger {')
    rule = css[start:css.index('}', start)]
    assert 'box-shadow:' in rule and 'inset 0 1px' in rule
    start = css.index('#about-careergap-trigger:active {')
    pressed = css[start:css.index('}', start)]
    assert 'transform: translateY(2px);' in pressed
    assert 'box-shadow:' in pressed
    assert '#about-careergap-trigger:focus-visible' in css
