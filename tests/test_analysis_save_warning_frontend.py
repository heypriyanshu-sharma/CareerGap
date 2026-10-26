"""
Regression tests for the analysis save warning (Item 4f).

backend /analyze reports analysis_save_error when the completed
analysis could not be persisted; the report must show that message
at the top instead of silently ignoring it. The primary tests run
the real helper source, extracted verbatim from frontend/script.js
together with the real escapeHTML, through Node. Python-side pins
cover the render-path ordering in buildAnalysisMarkup.
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
SCRIPT_JS = FRONTEND_DIR / "script.js"


# ============================================================
# SOURCE EXTRACTION
# ============================================================

def _extract_braced_block(source: str, start_marker: str) -> str:
    """Return the source block that opens with the first ``{``
    after ``start_marker`` and closes with its matching brace.

    Skips string literals, template literals (including nested
    ``${...}`` expressions) and comments so braces inside them do
    not confuse the matching.
    """
    start = source.index(start_marker)
    open_idx = source.index("{", start)

    depth = 0
    i = open_idx
    n = len(source)

    while i < n:
        char = source[i]

        if char in "\"'`":
            quote = char
            i += 1
            while i < n:
                if source[i] == "\\":
                    i += 2
                    continue
                if (
                    quote == "`"
                    and source[i] == "$"
                    and i + 1 < n
                    and source[i + 1] == "{"
                ):
                    i += 2
                    nested = 1
                    while i < n and nested > 0:
                        if source[i] == "{":
                            nested += 1
                        elif source[i] == "}":
                            nested -= 1
                        i += 1
                    continue
                if source[i] == quote:
                    break
                i += 1
            i += 1
            continue

        if char == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue

        if char == "/" and i + 1 < n and source[i + 1] == "*":
            while i + 1 < n and not (
                source[i] == "*" and source[i + 1] == "/"
            ):
                i += 1
            i += 2
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]

        i += 1

    raise ValueError(f"unbalanced braces for {start_marker!r}")


def _read_script_js() -> str:
    return SCRIPT_JS.read_text(encoding="utf-8")


# ============================================================
# NODE-BASED SAVE WARNING REGRESSION TEST
# ============================================================

_NODE_TEST_TEMPLATE = r"""
'use strict';

// ---- Real source extracted verbatim from frontend/script.js ----
__ESCAPE_HTML__

__SAVE_WARNING__

// ---- Assertions against the real helpers ----
(function () {
    const SERVER_MESSAGE =
        "Your analysis is complete, but saving it to your " +
        "history failed. It is not available in Saved Analyses.";

    let failures = [];

    function expect(name, condition) {
        if (!condition) {
            failures.push(name);
        }
    }

    // 1. A string field renders the banner.
    const rendered = createSaveWarning({
        analysis_save_error: SERVER_MESSAGE,
    });
    expect("render contains result-error", rendered.includes('result-error'));
    expect("render contains save-warning", rendered.includes('save-warning'));
    expect(
        "render contains escaped server message",
        rendered.includes("Your analysis is complete, but saving it to")
    );
    expect(
        "render contains the h3 heading",
        rendered.includes("Analysis saved to your screen, not")
    );

    // 2. HTML in the field must be escaped, never injected raw.
    const malicious = '<img src="x" onerror="alert(1)">';
    const escapedRender = createSaveWarning({
        analysis_save_error: malicious,
    });
    expect(
        "no raw img tag",
        !escapedRender.includes('<img src="x"')
    );
    expect(
        "escaped img tag present",
        escapedRender.includes("&lt;img src=&quot;x&quot;")
    );

    // 3. Absence, empty and blank fields render nothing.
    const absent = createSaveWarning({});
    const empty = createSaveWarning({ analysis_save_error: "" });
    const blank = createSaveWarning({ analysis_save_error: "   \n " });
    const nonString = createSaveWarning({ analysis_save_error: 42 });
    expect("empty for absence", absent === "");
    expect("empty for empty string", empty === "");
    expect("empty for blank string", blank === "");
    expect("empty for non-string value", nonString === "");

    // 4. Surrounding whitespace is trimmed away.
    const padded = createSaveWarning({
        analysis_save_error: "  " + SERVER_MESSAGE + "  ",
    });
    expect(
        "trimmed message rendered",
        padded.includes("Your analysis is complete")
    );

    if (failures.length > 0) {
        console.log("FAILED: " + failures.join(", "));
        process.exit(1);
    }

    console.log("save warning handlers OK");
})();
"""


def _run_node_save_warning_test() -> subprocess.CompletedProcess:
    source = _read_script_js()

    escape_html = _extract_braced_block(source, "function escapeHTML(value)")
    save_warning = _extract_braced_block(source, "function createSaveWarning(")

    program = (
        _NODE_TEST_TEMPLATE
        .replace("__ESCAPE_HTML__", escape_html)
        .replace("__SAVE_WARNING__", save_warning)
    )

    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".js",
        delete=False,
    )

    try:
        handle.write(program)
        handle.close()

        tmp_path = handle.name

        return subprocess.run(
            ["node", tmp_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
    finally:
        Path(handle.name).unlink(missing_ok=True)


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is required to run the frontend handler test",
)
def test_save_warning_renders_and_escapes_the_server_message():
    """The banner renders the backend message through the real
    escapeHTML and .result-error structure; injected HTML must be
    neutralized and the heading must be present."""

    result = _run_node_save_warning_test()

    assert result.returncode == 0, (
        "Save warning handler test failed:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "save warning handlers OK" in result.stdout


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is required to run the frontend handler test",
)
def test_save_warning_renders_nothing_without_a_save_failure():
    """Normal successful saves (no field, empty, blank or
    non-string) must render no warning."""

    result = _run_node_save_warning_test()

    assert result.returncode == 0, (
        "Save warning handler test failed:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert "FAILED" not in result.stdout
    assert "save warning handlers OK" in result.stdout


# ============================================================
# SOURCE PINS — RENDER PATH
# ============================================================

def test_build_analysis_markup_renders_the_warning_first():
    """The warning banner must be prepended before the report
    sections so the top-of-report banner is the first content."""

    compact = re.sub(
        r"\s+",
        "",
        _read_script_js(),
    )

    chain = (
        "return(createSaveWarning(result)+top+projects+atsKeywords+"
        "aiAdvice+"
    )

    assert chain in compact


def test_save_warning_escapes_through_the_helper():
    """The message must pass through escapeHTML within the
    helper, matching how every other server string is
    interpolated."""

    source = _read_script_js()
    helper = _extract_braced_block(
        source,
        "function createSaveWarning(",
    )

    compact = re.sub(r"\s+", "", helper)
    stripped = re.sub(
        r'"(?:[^"\\]|\\.)*"'
        r"|'(?:[^'\\]|\\.)*'"
        r"|`(?:[^`\\]|\\.)*`",
        '""',
        compact,
    )

    assert "escapeHTML(message)" in compact
    assert 'typeofresult.analysis_save_error==="' in stripped
    assert 'if(!message){return"";}' in compact


def test_save_warning_is_used_once():
    """A single helper keeps the render path to one wiring point
    in buildAnalysisMarkup."""

    compact = re.sub(r"\s+", "", _read_script_js())

    assert compact.count("createSaveWarning(") == 2


def test_save_warning_message_text_is_not_hardcoded_frontend_text():
    """The user-facing failure text stays server-owned: the
    helper must not embed the backend message body."""

    compact = re.sub(r"\s+", "", _read_script_js())

    assert "butsavingittoyourhistoryfailed" not in compact
