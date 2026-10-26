"""Regression tests for the rate-limit key function (Item 4c).

get_client_key keys slowapi limits on CF-Connecting-IP when that
header is present and a valid IP address, and falls back to the real
peer address otherwise. X-Forwarded-For is never key material.
"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials
from starlette.datastructures import Headers

import backend


client = TestClient(backend.app)


def make_request(headers=None, client_host="10.0.0.1"):
    """Build a minimal stand-in for a Starlette request."""
    return SimpleNamespace(
        headers=Headers(headers or {}),
        client=SimpleNamespace(host=client_host, port=49152),
    )


# ---------------------------------------------------------------------------
# Unit tests: get_client_key selection logic
# ---------------------------------------------------------------------------

def test_cf_connecting_ip_ipv4_is_key():
    request = make_request(
        headers={"CF-Connecting-IP": "192.0.2.7"},
        client_host="10.0.0.1",
    )

    assert backend.get_client_key(request) == "192.0.2.7"


def test_cf_connecting_ip_ipv6_is_key():
    request = make_request(
        headers={"CF-Connecting-IP": "2001:db8::1"},
        client_host="10.0.0.1",
    )

    assert backend.get_client_key(request) == "2001:db8::1"


def test_missing_cf_header_falls_back_to_peer():
    request = make_request(client_host="10.0.0.1")

    assert backend.get_client_key(request) == "10.0.0.1"


def test_empty_cf_header_falls_back_to_peer():
    request = make_request(
        headers={"CF-Connecting-IP": ""},
        client_host="10.0.0.1",
    )

    assert backend.get_client_key(request) == "10.0.0.1"


def test_invalid_cf_header_falls_back_to_peer():
    """Non-IP values must never become limiter keys."""
    request = make_request(
        headers={"CF-Connecting-IP": "garbage-value"},
        client_host="10.0.0.1",
    )

    assert backend.get_client_key(request) == "10.0.0.1"


def test_xff_alone_is_never_keyed():
    """Spoofed X-Forwarded-For without a CF header must be ignored."""
    request = make_request(
        headers={"X-Forwarded-For": "6.6.6.6"},
        client_host="10.0.0.1",
    )

    assert backend.get_client_key(request) == "10.0.0.1"


def test_xff_ignored_when_cf_header_present():
    """A spoofed XFF next to a real CF header must not change the key."""
    request = make_request(
        headers={
            "X-Forwarded-For": "6.6.6.6",
            "CF-Connecting-IP": "192.0.2.7",
        },
        client_host="10.0.0.1",
    )

    assert backend.get_client_key(request) == "192.0.2.7"


def test_limiter_uses_get_client_key():
    """Pin the wiring: the limiter must be built on get_client_key."""
    assert backend.limiter._key_func == backend.get_client_key


# ---------------------------------------------------------------------------
# Integration test: per-client isolation on /analyze
# ---------------------------------------------------------------------------

ANALYZE_PAYLOAD = {
    "resume": "I know Python.",
    "job_description": "Required: Python FastAPI.",
    "projects": [
        {
            "name": "Test API",
            "description": "A Python API project.",
        }
    ],
}


@pytest.fixture
def analyze_client(monkeypatch):
    """Authenticated client with every external dependency stubbed."""
    backend.app.dependency_overrides[
        backend.get_current_user
    ] = lambda: {
        "sub": "rate-limit-user",
        "email": "limit@example.com",
    }

    backend.app.dependency_overrides[
        backend.security
    ] = lambda: HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="test-access-token",
    )

    monkeypatch.setattr(
        backend,
        "run_careergap",
        lambda resume, job_description, projects: {
            "resume_skills": ["Python"],
            "job_skills": ["Python", "FastAPI"],
            "matched_skills": ["Python"],
            "missing_skills": ["FastAPI"],
            "score": 50.0,
        },
    )

    monkeypatch.setattr(
        backend,
        "generate_career_advice",
        lambda career_gap_data: "Advice.",
    )

    monkeypatch.setattr(
        backend,
        "calculate_ats_scorecard",
        lambda **kwargs: None,
    )

    monkeypatch.setattr(
        backend,
        "save_analysis",
        lambda **kwargs: None,
    )

    yield

    backend.app.dependency_overrides.pop(
        backend.get_current_user,
        None,
    )

    backend.app.dependency_overrides.pop(
        backend.security,
        None,
    )


def test_analyze_isolates_clients_by_cf_header(analyze_client):
    """/analyze must key its limit per CF-Connecting-IP client."""
    backend.limiter._storage.reset()

    headers_a = {"CF-Connecting-IP": "198.51.100.10"}
    headers_b = {"CF-Connecting-IP": "198.51.100.11"}

    last = None

    for _ in range(10):
        last = client.post("/analyze", json=ANALYZE_PAYLOAD, headers=headers_a)

    assert last.status_code == 200

    # The 11th request from the same key exceeds 10/minute.
    exhausted = client.post("/analyze", json=ANALYZE_PAYLOAD, headers=headers_a)

    assert exhausted.status_code == 429

    # A different client key is unaffected by client A's exhaustion.
    other = client.post("/analyze", json=ANALYZE_PAYLOAD, headers=headers_b)

    assert other.status_code == 200

    backend.limiter._storage.reset()
