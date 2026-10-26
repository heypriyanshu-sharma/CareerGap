import pytest
import requests
from fastapi.testclient import TestClient
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

import auth
import backend
import database


client = TestClient(backend.app)


@pytest.fixture
def authenticated_user():
    backend.app.dependency_overrides[
        backend.get_current_user
    ] = lambda: {
        "sub": "test-user-id",
        "email": "test@example.com",
    }

    yield

    backend.app.dependency_overrides.pop(
        backend.get_current_user,
        None,
    )


def test_analyses_returns_history(
    authenticated_user,
    monkeypatch,
):
    expected_history = [
        {
            "id": "analysis-1",
            "job_description": "Python Backend Developer",
            "analysis": {
                "score": 75.0,
            },
            "created_at": "2026-09-27T10:00:00+00:00",
        }
    ]

    captured = {}

    def fake_get_analysis_history(access_token, user_id):
        captured["access_token"] = access_token
        captured["user_id"] = user_id

        return expected_history

    monkeypatch.setattr(
        backend,
        "get_analysis_history",
        fake_get_analysis_history,
    )

    response = client.get(
        "/analyses",
        headers={
            "Authorization": "Bearer test-access-token",
        },
    )

    assert response.status_code == 200
    assert response.json() == expected_history
    assert captured["access_token"] == (
        "test-access-token"
    )
    assert captured["user_id"] == "test-user-id"


def test_analyses_rejects_invalid_token(
    monkeypatch,
):
    def fake_get_claims(access_token):
        raise RuntimeError("Invalid token.")

    monkeypatch.setattr(
        auth.supabase.auth,
        "get_claims",
        fake_get_claims,
    )

    response = client.get(
        "/analyses",
        headers={
            "Authorization": "Bearer invalid-token",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or expired authentication token."
    )


class _FakeSupabaseResponse:
    """Minimal requests.Response stand-in for param verification."""

    ok = True
    status_code = 200

    def raise_for_status(self):
        pass

    def json(self):
        return []


def test_get_analysis_history_filters_by_user_id(monkeypatch):
    """The history read must scope the PostgREST query to the caller."""

    captured = {}

    def fake_get(url, headers=None, params=None, timeout=None):
        captured["url"] = url
        captured["params"] = params

        return _FakeSupabaseResponse()

    monkeypatch.setattr(
        database.requests,
        "get",
        fake_get,
    )

    database.get_analysis_history(
        "test-access-token",
        "test-user-id",
    )

    assert captured["url"].endswith("/career_analyses")

    assert captured["params"]["user_id"] == (
        "eq.test-user-id"
    )

    assert captured["params"]["order"] == (
        "created_at.desc"
    )


def test_delete_analysis_filters_by_user_id_and_analysis_id(
    monkeypatch,
):
    """The delete must scope to both the caller and one analysis id."""

    captured = {}

    def fake_delete(url, headers=None, params=None, timeout=None):
        captured["params"] = params

        return _FakeSupabaseResponse()

    monkeypatch.setattr(
        database.requests,
        "delete",
        fake_delete,
    )

    database.delete_analysis(
        "test-access-token",
        "test-user-id",
        "test-analysis-id",
    )

    assert captured["params"]["user_id"] == (
        "eq.test-user-id"
    )

    assert captured["params"]["id"] == (
        "eq.test-analysis-id"
    )


class _FakeFailedSupabaseResponse:
    """requests.Response stand-in for a rejected save (RLS/system)."""

    ok = False
    status_code = 403

    def json(self):
        return {
            "code": "42501",
            "message": "new row violates row-level security policy",
        }


def test_save_analysis_success_does_not_raise(monkeypatch):
    """A confirmed save must complete silently (no error field path)."""

    monkeypatch.setattr(
        database.requests,
        "post",
        lambda url, headers=None, json=None, timeout=None: (
            _FakeSupabaseResponse()
        ),
    )

    database.save_analysis(
        "test-access-token",
        "test-user-id",
        "resume text",
        "job text",
        [{"name": "Project", "description": "Built a thing."}],
        {"scores": {}, "score": 50.0},
    )


def test_save_analysis_db_error_raises(monkeypatch):
    """An HTTP-rejected save (RLS/table error) must surface, not vanish."""

    monkeypatch.setattr(
        database.requests,
        "post",
        lambda url, headers=None, json=None, timeout=None: (
            _FakeFailedSupabaseResponse()
        ),
    )

    with pytest.raises(database.DatabaseRequestError) as excinfo:
        database.save_analysis(
            "test-access-token",
            "test-user-id",
            "resume text",
            "job text",
            [{"name": "Project", "description": "Built a thing."}],
            {"scores": {}, "score": 50.0},
        )

    # The shared helper maps 42501/403 to its standard not-authorized
    # error; the contract under test is the typed, surfaced failure.
    assert excinfo.value.status_code == 403


class _FakeServerSupabaseResponse:
    """requests.Response stand-in for an unmapped 5xx save failure."""

    ok = False
    status_code = 500

    def json(self):
        return {
            "code": "XX402",
            "message": "database overloaded",
        }


def test_save_analysis_server_error_uses_save_fallback(monkeypatch):
    """An unmapped 5xx save must carry the save-specific message."""

    monkeypatch.setattr(
        database.requests,
        "post",
        lambda url, headers=None, json=None, timeout=None: (
            _FakeServerSupabaseResponse()
        ),
    )

    with pytest.raises(database.DatabaseRequestError) as excinfo:
        database.save_analysis(
            "test-access-token",
            "test-user-id",
            "resume text",
            "job text",
            [{"name": "Project", "description": "Built a thing."}],
            {"scores": {}, "score": 50.0},
        )

    assert "Unable to save the analysis." in str(excinfo.value)
    assert excinfo.value.status_code == 500


def test_save_analysis_timeout_propagates(monkeypatch):
    """A timed-out save must propagate as a requests.Timeout."""

    def fake_post(url, headers=None, json=None, timeout=None):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(
        database.requests,
        "post",
        fake_post,
    )

    with pytest.raises(requests.Timeout):
        database.save_analysis(
            "test-access-token",
            "test-user-id",
            "resume text",
            "job text",
            [{"name": "Project", "description": "Built a thing."}],
            {"scores": {}, "score": 50.0},
        )


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

EXPECTED_ANALYSIS = {
    "resume_skills": ["Python"],
    "job_skills": ["Python", "FastAPI"],
    "matched_skills": ["Python"],
    "missing_skills": ["FastAPI"],
    "score": 50.0,
}


@pytest.fixture
def analyze_client(monkeypatch):
    """Authenticated client with the deterministic analysis stubbed."""

    backend.app.dependency_overrides[
        backend.get_current_user
    ] = lambda: {
        "sub": "test-user-id",
        "email": "test@example.com",
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
        lambda resume, job_description, projects: dict(
            EXPECTED_ANALYSIS
        ),
    )

    monkeypatch.setattr(
        backend,
        "generate_career_advice",
        lambda career_gap_data: "Test AI career advice.",
    )

    monkeypatch.setattr(
        backend,
        "calculate_ats_scorecard",
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


def test_analyze_reports_save_failure_with_analysis_intact(
    analyze_client,
    monkeypatch,
):
    """A rejected save must not destroy the completed analysis."""

    backend.limiter._storage.reset()

    def failing_save(**kwargs):
        raise database.DatabaseRequestError(
            "Unable to save the analysis.",
            status_code=503,
        )

    monkeypatch.setattr(
        backend,
        "save_analysis",
        failing_save,
    )

    response = client.post(
        "/analyze",
        json=ANALYZE_PAYLOAD,
    )

    assert response.status_code == 200

    body = response.json()

    # The analysis itself is intact (fallback preserved).
    assert body["resume_skills"] == EXPECTED_ANALYSIS[
        "resume_skills"
    ]
    assert body["score"] == EXPECTED_ANALYSIS["score"]

    # The failure is reported honestly in-band.
    assert "analysis_save_error" in body
    assert "history failed" in body["analysis_save_error"]


def test_analyze_reports_save_timeout_analysis_intact(
    analyze_client,
    monkeypatch,
):
    """A timed-out save keeps the analysis and reports in-band."""

    backend.limiter._storage.reset()

    def timeout_save(**kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(
        backend,
        "save_analysis",
        timeout_save,
    )

    response = client.post(
        "/analyze",
        json=ANALYZE_PAYLOAD,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["score"] == EXPECTED_ANALYSIS["score"]
    assert "analysis_save_error" in body


def test_analyze_success_has_no_save_error(
    analyze_client,
    monkeypatch,
):
    """A successful save must not add analysis_save_error (shape)."""

    backend.limiter._storage.reset()

    monkeypatch.setattr(
        backend,
        "save_analysis",
        lambda **kwargs: None,
    )

    response = client.post(
        "/analyze",
        json=ANALYZE_PAYLOAD,
    )

    assert response.status_code == 200
    assert "analysis_save_error" not in response.json()
