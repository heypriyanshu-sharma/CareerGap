"""
Regression tests for the Cloudflare Pages security headers (Item 4b).

The frontend is served as static files by Cloudflare Pages, so the
headers live in ``frontend/_headers``. The CSP is rolled out in
report-only mode first. Because ``frame-ancestors`` is ignored in a
report-only policy, ``X-Frame-Options`` is the control that protects
against clickjacking until the policy is enforced.

The tests parse the real header file, so a typo or a weakened directive
fails here instead of silently shipping.
"""

import base64
import hashlib
import re
from pathlib import Path

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
HEADERS_FILE = FRONTEND_DIR / "_headers"
INDEX_HTML = FRONTEND_DIR / "index.html"
SUPABASE_CONFIG = FRONTEND_DIR / "supabase-config.js"
SCRIPT_JS = FRONTEND_DIR / "script.js"

INLINE_SCRIPT_PATTERN = re.compile(
    rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>",
    re.S,
)

MIN_HSTS_MAX_AGE = 15_552_000  # 180 days


# ============================================================
# PARSING
# ============================================================

def _rules():
    """Parse frontend/_headers into {pattern: {header: value}}."""

    rules = {}
    current = None

    for raw_line in HEADERS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if raw_line[:1] not in (" ", "\t"):
            current = {}
            rules[line] = current
            continue

        name, _, value = line.partition(":")
        current[name.strip().lower()] = value.strip()

    return rules


def _site_headers():
    return _rules()["/*"]


def _csp():
    headers = _site_headers()
    assert "content-security-policy-report-only" in headers
    return headers["content-security-policy-report-only"]


def _directives():
    directives = {}

    for part in _csp().split(";"):
        tokens = part.split()
        if tokens:
            directives[tokens[0].lower()] = tokens[1:]

    return directives


# ============================================================
# HEADER FILE
# ============================================================

def test_headers_file_lives_at_the_pages_site_root():
    """Cloudflare Pages only reads _headers from the deployed root,
    which is frontend/ for this project."""

    assert HEADERS_FILE.is_file()


def test_headers_apply_to_every_path():
    rules = _rules()

    assert "/*" in rules
    assert rules["/*"]


# ============================================================
# CSP ROLLOUT STATE
# ============================================================

def test_csp_is_report_only_during_rollout():
    headers = _site_headers()

    assert "content-security-policy-report-only" in headers
    assert "content-security-policy" not in headers


def test_csp_blocks_objects_frames_and_base_rewrites():
    directives = _directives()

    assert directives["default-src"] == ["'self'"]
    assert directives["object-src"] == ["'none'"]
    assert directives["base-uri"] == ["'self'"]
    assert directives["frame-ancestors"] == ["'none'"]
    assert directives["form-action"] == ["'self'"]


def test_csp_keeps_script_sources_strict():
    script_src = _directives()["script-src"]

    assert "'self'" in script_src
    assert "https://cdn.jsdelivr.net" in script_src

    for weakened in ("'unsafe-inline'", "'unsafe-eval'", "*"):
        assert weakened not in script_src


def test_inline_theme_script_hashes_match_both_line_endings():
    """The inline theme bootstrap is allowed by hash only.

    The hash is computed over the script text as served. A Git checkout
    and a Windows working copy can differ in line endings, so both
    variants are pinned; extra hashes are ignored by browsers.
    """

    raw = INDEX_HTML.read_bytes()
    lf_content = raw.replace(b"\r\n", b"\n")
    crlf_content = lf_content.replace(b"\n", b"\r\n")

    lf_scripts = INLINE_SCRIPT_PATTERN.findall(lf_content)
    crlf_scripts = INLINE_SCRIPT_PATTERN.findall(crlf_content)

    assert len(lf_scripts) == 1
    assert len(crlf_scripts) == 1

    script_src = _directives()["script-src"]

    for content in (lf_scripts[0], crlf_scripts[0]):
        digest = base64.b64encode(
            hashlib.sha256(content).digest()
        ).decode()
        assert f"'sha256-{digest}'" in script_src


def test_csp_allows_the_styles_and_images_the_app_actually_uses():
    """Inline style attributes exist in index.html and in generated
    markup (ATS gauges), and avatars are arbitrary HTTPS images."""

    directives = _directives()

    assert "'self'" in directives["style-src"]
    assert "'unsafe-inline'" in directives["style-src"]

    img_src = directives["img-src"]
    assert "'self'" in img_src
    assert "data:" in img_src
    assert "https:" in img_src


def test_csp_connect_sources_match_the_frontend_configuration():
    """The policy must allow the real API and Supabase hosts, so a
    project or API host change cannot silently break the app."""

    connect_src = _directives()["connect-src"]
    assert "'self'" in connect_src

    supabase_url = re.search(
        r"https://[a-z0-9]+\.supabase\.co",
        SUPABASE_CONFIG.read_text(encoding="utf-8"),
    )
    assert supabase_url
    assert supabase_url.group(0) in connect_src

    api_url = re.search(
        r"https://careergap\.onrender\.com",
        SCRIPT_JS.read_text(encoding="utf-8"),
    )
    assert api_url
    assert api_url.group(0) in connect_src


# ============================================================
# HEADERS THAT ARE ALREADY ENFORCED
# ============================================================

def test_frame_protection_is_enforced_while_csp_is_report_only():
    assert _site_headers()["x-frame-options"] == "DENY"


def test_permissions_policy_denies_sensitive_features():
    policy = _site_headers()["permissions-policy"]

    for feature in (
        "accelerometer",
        "camera",
        "geolocation",
        "gyroscope",
        "magnetometer",
        "microphone",
        "payment",
        "usb",
    ):
        assert f"{feature}=()" in policy


def test_hsts_is_enabled_without_preload():
    hsts = _site_headers()["strict-transport-security"]

    match = re.search(r"max-age=(\d+)", hsts)
    assert match
    assert int(match.group(1)) >= MIN_HSTS_MAX_AGE
    assert "includeSubDomains" in hsts
    assert "preload" not in hsts
