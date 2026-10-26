import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

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
