import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

import auth
import backend


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

    monkeypatch.setattr(
        backend,
        "get_analysis_history",
        lambda access_token: expected_history,
    )

    response = client.get(
        "/analyses",
        headers={
            "Authorization": "Bearer test-access-token",
        },
    )

    assert response.status_code == 200
    assert response.json() == expected_history


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