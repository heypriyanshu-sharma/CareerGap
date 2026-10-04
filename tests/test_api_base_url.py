"""
Focused tests for production versus local API base URL selection.

The deployed frontend was requesting http://127.0.0.1:8001 because
frontend/index.html hardcoded that loopback URL in the api-base-url
meta tag and frontend/script.js always preferred it, which made the
environment auto-detection dead code. The real selection block is
extracted from frontend/script.js and exercised against a fake
document/window so both the production and the local paths are
covered, including the case where a stale local meta tag is present
on the deployed site.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
SCRIPT_JS = FRONTEND_DIR / "script.js"
INDEX_HTML = FRONTEND_DIR / "index.html"


def _read_script_js() -> str:
    return SCRIPT_JS.read_text(encoding="utf-8")


def _extract_api_selection(source: str) -> str:
    """Return the API_BASE_URL selection block from script.js.

    The block is a run of ``const`` declarations rather than a
    braced function body, so it is bounded by its first and last
    statements instead of by matching braces.
    """
    start = source.index("const metaApiUrl =")
    end_marker = ': "https://careergap.onrender.com";'
    end = source.index(end_marker, start) + len(end_marker)
    return source[start:end]


_NODE_TEMPLATE = r"""
'use strict';

function resolveApiBaseUrl(document, window) {
__SELECTION_BLOCK__
    return API_BASE_URL;
}

const scenarios = [
    {
        name: "production_without_meta",
        metaContent: null,
        protocol: "https:",
        hostname: "careergap.pages.dev",
        expected: "https://careergap.onrender.com"
    },
    {
        name: "production_with_stale_local_meta",
        metaContent: "http://127.0.0.1:8001",
        protocol: "https:",
        hostname: "careergap.pages.dev",
        expected: "https://careergap.onrender.com"
    },
    {
        name: "localhost_without_meta",
        metaContent: null,
        protocol: "http:",
        hostname: "localhost",
        expected: "http://127.0.0.1:8001"
    },
    {
        name: "localhost_with_meta",
        metaContent: "http://127.0.0.1:8001",
        protocol: "http:",
        hostname: "localhost",
        expected: "http://127.0.0.1:8001"
    },
    {
        name: "loopback_without_meta",
        metaContent: null,
        protocol: "http:",
        hostname: "127.0.0.1",
        expected: "http://127.0.0.1:8001"
    },
    {
        name: "file_protocol_without_meta",
        metaContent: null,
        protocol: "file:",
        hostname: "",
        expected: "http://127.0.0.1:8001"
    },
    {
        name: "file_protocol_with_meta",
        metaContent: "http://127.0.0.1:8001",
        protocol: "file:",
        hostname: "",
        expected: "http://127.0.0.1:8001"
    }
];

let failures = 0;
for (const scenario of scenarios) {
    const fakeDocument = {
        querySelector: function (selector) {
            if (selector === 'meta[name="api-base-url"]') {
                return scenario.metaContent === null
                    ? null
                    : { getAttribute: function () { return scenario.metaContent; } };
            }
            return null;
        }
    };
    const fakeWindow = {
        location: { protocol: scenario.protocol, hostname: scenario.hostname }
    };
    const actual = resolveApiBaseUrl(fakeDocument, fakeWindow);
    if (actual !== scenario.expected) {
        console.log("FAIL " + scenario.name +
            ": expected " + scenario.expected + " got " + actual);
        failures += 1;
    } else {
        console.log("PASS " + scenario.name + ": " + actual);
    }
}

if (failures > 0) {
    process.exit(1);
}
console.log("ALL_PASS");
"""


def _run_node_api_url_test(tmp_path: Path) -> subprocess.CompletedProcess:
    selection = _extract_api_selection(_read_script_js())
    node_script = _NODE_TEMPLATE.replace("__SELECTION_BLOCK__", selection)
    script_path = tmp_path / "api_url_test.js"
    script_path.write_text(node_script, encoding="utf-8")
    return subprocess.run(
        ["node", str(script_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_api_base_url_selection_production_vs_local(tmp_path):
    """The deployed frontend must resolve to the production API, a
    stale local meta tag must never override it, and localhost must
    keep using the local backend."""
    if shutil.which("node") is None:
        pytest.skip("node is required to run the API URL selection test")

    result = _run_node_api_url_test(tmp_path)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "ALL_PASS" in result.stdout
    assert (
        "production_with_stale_local_meta: https://careergap.onrender.com"
        in result.stdout
    )
    assert "localhost_with_meta: http://127.0.0.1:8001" in result.stdout


def test_meta_tag_does_not_force_a_local_url():
    """The api-base-url meta tag must be empty so environment
    auto-detection governs; a hardcoded loopback URL is what broke
    the deployed frontend."""
    html = INDEX_HTML.read_text(encoding="utf-8")
    match = re.search(
        r'<meta\s+name="api-base-url"\s+content="([^"]*)"',
        html,
    )
    assert match is not None, "api-base-url meta tag is missing"
    assert match.group(1).strip() == "", (
        "api-base-url meta tag must be empty so auto-detection governs"
    )


def test_selection_logic_scopes_override_to_localhost():
    """The meta tag override must be gated on isLocalhost so a local
    URL can never be used by the deployed frontend, and the local and
    production fallbacks must be the intended URLs."""
    source = _read_script_js()

    assert "configuredApiUrl && isLocalhost" in source, (
        "meta tag override must be scoped to localhost"
    )
    assert '"http://127.0.0.1:8001"' in source, (
        "local backend fallback must be http://127.0.0.1:8001"
    )
    assert '"https://careergap.onrender.com"' in source, (
        "production API fallback must be https://careergap.onrender.com"
    )
    assert '"http://127.0.0.1:8000"' not in source, (
        "stale local fallback port 8000 must be gone"
    )
