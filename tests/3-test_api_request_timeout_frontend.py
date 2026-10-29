"""
Regression tests for the apiRequest cold-start handling in frontend/script.js.

The backend runs on a Render free instance that sleeps after inactivity;
a cold start was measured at ~41s, so the old 30s default timeout aborted
the first request of a session before the backend finished waking. The
fix raises the default timeout to 65s and retries idempotent methods
(GET/HEAD) once when OUR timeout fires, while never retrying POSTs or
caller-aborted requests.

These tests extract the real apiRequest source and run it in Node
against a fake fetch, mirroring the harness in
test_resume_builder_frontend.py.
"""

import json
import subprocess
from pathlib import Path

import pytest

SCRIPT_JS = Path(__file__).resolve().parent.parent / "frontend" / "script.js"


def _extract_braced_block(source: str, start_marker: str) -> str:
    """Return the source block that opens with the first ``{``
    after ``start_marker`` and closes with its matching brace.

    Skips string literals, template literals (including nested
    ``${...}`` expressions) and comments so braces inside them do
    not confuse the matching.
    """
    start = source.index(start_marker)
    # The apiRequest signature contains a default ``options = {}`` whose
    # braces must not be mistaken for the function body, so open on the
    # ") {" that closes the parameter list instead of the first "{".
    open_idx = source.index(") {", start) + 1

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
            i += 2
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


_NODE_HARNESS = r"""
'use strict';

// ---- Stubs for apiRequest's closure dependencies ----
const API_BASE_URL = 'https://api.example.test';
async function getAccessToken() { return 'fake-token'; }

let fetchCalls = [];
let fetchBehaviour = null;

// Fake fetch that rejects with an AbortError when the request's own
// signal fires (mirroring how a real fetch reacts to controller.abort()),
// or resolves with a canned response when fetchBehaviour says so.
function fetch(url, options) {
    fetchCalls.push({ url, method: (options.method ?? 'GET').toUpperCase() });
    return new Promise((resolve, reject) => {
        const behaviour = fetchBehaviour(fetchCalls.length);
        if (behaviour === 'ok') {
            resolve({
                ok: true,
                status: 200,
                json: async () => ({ done: true }),
            });
            return;
        }
        // 'hang': never respond; only the caller's abort settles it.
        options.signal.addEventListener('abort', () => {
            reject(new DOMException('The operation was aborted.', 'AbortError'));
        }, { once: true });
    });
}

__API_REQUEST_SOURCE__

(async () => {
    const scenario = process.argv[2];
    const tinyTimeout = { timeout: 30 };

    if (scenario === 'get-retries-after-timeout') {
        // First attempt hangs and is aborted by our timeout; the retry succeeds.
        fetchBehaviour = (call) => (call === 1 ? 'hang' : 'ok');
        const result = await apiRequest('/resumes', tinyTimeout, false);
        if (!result || result.done !== true) {
            throw new Error('expected the retry result to be returned');
        }
        if (fetchCalls.length !== 2) {
            throw new Error(`expected 2 fetch calls, saw ${fetchCalls.length}`);
        }
        return;
    }

    if (scenario === 'post-never-retries') {
        fetchBehaviour = () => 'hang';
        let threw = false;
        try {
            await apiRequest('/resumes', { ...tinyTimeout, method: 'POST' }, false);
        } catch (error) {
            threw = true;
            if (error.name !== 'AbortError') {
                throw new Error(`expected AbortError, saw ${error.name}`);
            }
        }
        if (!threw) {
            throw new Error('expected the POST attempt to throw');
        }
        if (fetchCalls.length !== 1) {
            throw new Error(`expected exactly 1 fetch call, saw ${fetchCalls.length}`);
        }
        return;
    }

    if (scenario === 'caller-abort-not-retried') {
        fetchBehaviour = () => 'hang';
        const caller = new AbortController();
        const pending = apiRequest(
            '/resumes',
            { timeout: 60000, signal: caller.signal },
            false
        );
        // The caller cancels before our timeout could ever fire.
        setTimeout(() => caller.abort(), 10);
        let threw = false;
        try {
            await pending;
        } catch (error) {
            threw = true;
        }
        if (!threw) {
            throw new Error('expected the caller-aborted request to throw');
        }
        if (fetchCalls.length !== 1) {
            throw new Error(`expected exactly 1 fetch call, saw ${fetchCalls.length}`);
        }
        return;
    }

    if (scenario === 'error-response-not-retried') {
        // A completed HTTP error response is a server answer, not a
        // timeout: retrying must not re-issue the request.
        fetchBehaviour = () => 'ok';
        let threw = false;
        try {
            const originalFetch = fetch;
            fetch = (url, options) => {
                fetchCalls.push({ url, method: (options.method ?? 'GET').toUpperCase() });
                return Promise.resolve({
                    ok: false,
                    status: 500,
                    json: async () => ({ detail: 'boom' }),
                });
            };
            await apiRequest('/resumes', tinyTimeout, false);
        } catch (error) {
            threw = true;
            if (!/boom/.test(error.message)) {
                throw new Error(`expected server detail, saw ${error.message}`);
            }
        }
        if (!threw) {
            throw new Error('expected the 500 response to throw');
        }
        if (fetchCalls.length !== 1) {
            throw new Error(`expected exactly 1 fetch call, saw ${fetchCalls.length}`);
        }
        return;
    }

    throw new Error(`unknown scenario ${scenario}`);
})().catch((error) => {
    console.error(error);
    process.exit(1);
});
"""


def _build_node_script() -> str:
    source = SCRIPT_JS.read_text(encoding="utf-8")
    api_request_source = _extract_braced_block(
        source, "async function apiRequest("
    )
    return _NODE_HARNESS.replace("__API_REQUEST_SOURCE__", api_request_source)


def _run_scenario(tmp_path: Path, scenario: str) -> None:
    script = tmp_path / "api_request_scenario.cjs"
    script.write_text(_build_node_script(), encoding="utf-8")
    result = subprocess.run(
        ["node", str(script), scenario],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"scenario {scenario} failed:\n{result.stdout}\n{result.stderr}"
    )


def test_default_timeout_outlasts_cold_start():
    """The default timeout must outlast the measured ~41s Render cold start."""
    source = SCRIPT_JS.read_text(encoding="utf-8")
    api_request_source = _extract_braced_block(
        source, "async function apiRequest("
    )
    assert "?? 65000" in api_request_source
    assert "?? 30000" not in api_request_source


def test_get_retries_once_after_own_timeout(tmp_path):
    _run_scenario(tmp_path, "get-retries-after-timeout")


def test_post_is_never_retried(tmp_path):
    _run_scenario(tmp_path, "post-never-retries")


def test_caller_abort_is_not_retried(tmp_path):
    _run_scenario(tmp_path, "caller-abort-not-retried")


def test_http_error_response_is_not_retried(tmp_path):
    _run_scenario(tmp_path, "error-response-not-retried")


def _run_describe_request_error(tmp_path: Path, cases: list) -> list:
    """Run the real describeRequestError source against fake error objects."""
    source = SCRIPT_JS.read_text(encoding="utf-8")
    helper = _extract_braced_block(source, "function describeRequestError(")
    script = tmp_path / "describe_request_error.cjs"
    script.write_text(
        helper
        + "\nconst cases = "
        + json.dumps(cases)
        + "\nprocess.stdout.write(JSON.stringify(cases.map((c) => describeRequestError(c, c.fallback))));\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["node", str(script)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_describe_request_error_translates_abort_jargon(tmp_path):
    outputs = _run_describe_request_error(
        tmp_path,
        [
            {"name": "AbortError", "message": "signal is aborted without reason"},
            {"name": "AbortError", "message": "The operation was aborted."},
            {"name": "Error", "message": "HTTP 500"},
            {"name": "Error", "message": ""},
            {"name": "Error", "message": "", "fallback": "Unable to delete resume."},
            {"name": "Error", "message": "HTTP 429", "fallback": "Ignored."},
        ],
    )
    assert "waking up" in outputs[0]
    assert "signal is aborted" not in outputs[0]
    assert "waking up" in outputs[1]
    assert outputs[2] == "HTTP 500", "ordinary errors pass through unchanged"
    assert outputs[3] == "Something went wrong. Please try again."
    assert outputs[4] == "Unable to delete resume.", "empty message uses the caller fallback"
    assert outputs[5] == "HTTP 429", "a real message beats the fallback"
