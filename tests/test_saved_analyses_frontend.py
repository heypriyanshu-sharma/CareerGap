"""Regression tests for the Saved Analyses signed-out state.

The history view is rendered entirely from frontend/script.js, so these
tests assert against the shipped source. The signed-out guard must write
a prompt instead of leaving the list empty, must clear any cached rows
from a previous session, and must never reach the network.
"""

from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "frontend" / "script.js"
SIGN_IN_SENTENCE = "Sign in to see your saved analyses."


def _source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def _load_history_fn() -> str:
    """Return loadAnalysisHistory up to the next section banner."""
    source = _source()
    start = source.index("async function loadAnalysisHistory()")
    end = source.index("// AUTO-GROW TEXTAREAS", start)
    return source[start:end]


def _signed_out_guard(fn: str) -> str:
    """Return the no-token guard, ending at its first return."""
    start = fn.index("if (!accessToken)")
    end = fn.index("return;", start)
    return fn[start:end]


def test_signed_out_history_shows_sign_in_prompt():
    guard = _signed_out_guard(_load_history_fn())

    assert '<div class="empty-state">' in guard
    assert SIGN_IN_SENTENCE in guard
    assert 'href="login.html"' in guard
    assert ">Sign in</a>" in guard
    assert "resume-action-btn primary" in guard


def test_signed_out_history_clears_cached_rows():
    guard = _signed_out_guard(_load_history_fn())

    clear_pos = guard.index("analysisHistoryData = [];")
    prompt_pos = guard.index(SIGN_IN_SENTENCE)

    assert clear_pos < prompt_pos, (
        "cached rows must be dropped before the prompt is rendered so a "
        "previous session's analyses cannot linger in the DOM"
    )


def test_signed_out_guard_runs_before_fetch():
    fn = _load_history_fn()
    guard = _signed_out_guard(fn)

    token_pos = fn.index("await getAccessToken(false)")
    guard_pos = fn.index("if (!accessToken)")
    fetch_pos = fn.index("await fetch(")

    assert token_pos < guard_pos < fetch_pos
    assert "fetch(" not in guard, "the signed-out path must not request /analyses"


def test_signed_in_empty_and_error_copy_unchanged():
    fn = _load_history_fn()

    # Signed out, empty, populated, and error: one assignment each.
    assert fn.count("analysisHistoryList.innerHTML") == 4
    assert fn.count(SIGN_IN_SENTENCE) == 1
    assert "No previous analyses yet." in fn
    assert "Unable to load previous analyses." in fn


def test_saved_analyses_navigation_reloads_history():
    source = _source()

    nav_start = source.index('if (view === "saved-analyses")')
    nav_branch = source[nav_start:source.index("return;", nav_start)]
    assert 'setAnalysisView("history");' in nav_branch
    assert "loadAnalysisHistory();" in nav_branch
    assert nav_branch.index('setAnalysisView("history")') < nav_branch.index(
        "loadAnalysisHistory()"
    )

    tab_start = source.index("historyTab.addEventListener(")
    tab_block = source[tab_start:tab_start + 800]
    assert "loadAnalysisHistory();" in tab_block, (
        "clicking the Previous Analyses tab must refresh the list state"
    )


def test_delete_history_uses_non_redirecting_token_read():
    source = _source()
    start = source.index("deleteButton.disabled =")
    end = source.index("// TAB BUTTONS", start)
    block = source[start:end]

    assert "await getAccessToken(false);" in block
    assert "await getAccessToken();" not in block, (
        "a missing session must not redirect away mid-delete"
    )

    guard_start = block.index("if (!accessToken)")
    guard = block[guard_start:block.index("return;", guard_start)]
    assert "await loadAnalysisHistory();" in guard, (
        "the signed-out prompt must replace the stale row"
    )
    assert "login.html" not in guard
    assert "window.location" not in guard
