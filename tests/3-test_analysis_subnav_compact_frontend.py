"""Phone-only compact analysis nav, without placement or visibility changes."""
from pathlib import Path
F=Path(__file__).resolve().parent.parent/'frontend'
def test_compact_rules_scoped_to_phone_width():
    css=(F/'style.css').read_text()
    phone=css[css.index('/* Compact phone analysis navigation;'):]
    assert '@media (max-width: 700px)' in phone
    assert '.analysis-subnav-heading,' in phone and '.analysis-subnav-hint' in phone
    assert 'display: none;' in phone
    assert 'min-height: 44px;' in phone
    assert 'white-space: nowrap;' in phone
    assert 'touch-action' not in phone

def test_all_section_links_and_accessible_nav_name_remain():
    html=(F/'index.html').read_text()
    assert 'aria-label="Analysis navigation"' in html
    for name in ('overview','skills','projects','keywords','resources','ai-advice'):
        assert f'id="subnav-{name}"' in html

def test_visible_nav_is_measured_before_scroll():
    src=(F/'script.js').read_text()
    fn=src[src.index('function syncSubnavState()'):src.index('function activateSubnavTab')]
    assert 'if (hasNavigableSections)' in fn
    assert 'syncStickyOffsets();' in fn
