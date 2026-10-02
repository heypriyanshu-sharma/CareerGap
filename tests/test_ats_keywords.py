import pytest
from fastapi.testclient import TestClient

import auth
import backend


client = TestClient(backend.app)


VALID_BODY = {
    "resume": "Built services in Python and Docker.",
    "job_description": (
        "We need a backend engineer.\n"
        "Requirements:\n"
        "- Python\n"
        "- PostgreSQL\n"
        "Nice to have: Docker"
    ),
    "projects": [
        {
            "name": "Example",
            "description": "An example project.",
        }
    ],
}


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


def test_ats_keywords_returns_ranked_keywords(
    authenticated_user,
):
    response = client.post(
        "/ats/keywords",
        json=VALID_BODY,
        headers={
            "Authorization": "Bearer test-access-token",
        },
    )

    assert response.status_code == 200

    keywords = response.json()["keywords"]

    assert keywords
    assert all(
        set(keyword) == {
            "term",
            "normalized",
            "frequency",
            "importance",
            "word_count",
        }
        for keyword in keywords
    )

    terms = [keyword["term"] for keyword in keywords]

    assert "Python" in terms
    assert "PostgreSQL" in terms

    assert all(
        keyword["importance"]
        in {"Required", "Preferred", "Mentioned"}
        for keyword in keywords
    )


def test_ats_keywords_ignores_resume_and_projects(
    authenticated_user,
):
    """The endpoint describes the job description only."""

    body = dict(VALID_BODY)
    body["resume"] = "Kubernetes Terraform Ansible Helm"
    body["projects"] = [
        {
            "name": "Infrastructure",
            "description": "Kubernetes and Terraform.",
        }
    ]

    response = client.post(
        "/ats/keywords",
        json=body,
        headers={
            "Authorization": "Bearer test-access-token",
        },
    )

    assert response.status_code == 200

    terms = {
        keyword["term"]
        for keyword in response.json()["keywords"]
    }

    assert "Kubernetes" not in terms
    assert "Terraform" not in terms


def test_ats_keywords_is_deterministic(
    authenticated_user,
):
    first = client.post(
        "/ats/keywords",
        json=VALID_BODY,
        headers={
            "Authorization": "Bearer test-access-token",
        },
    ).json()

    second = client.post(
        "/ats/keywords",
        json=VALID_BODY,
        headers={
            "Authorization": "Bearer test-access-token",
        },
    ).json()

    assert first == second


def test_ats_keywords_rejects_invalid_token(
    monkeypatch,
):
    def fake_get_claims(access_token):
        raise RuntimeError("Invalid token.")

    monkeypatch.setattr(
        auth.supabase.auth,
        "get_claims",
        fake_get_claims,
    )

    response = client.post(
        "/ats/keywords",
        json=VALID_BODY,
        headers={
            "Authorization": "Bearer invalid-token",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Invalid or expired authentication token."
    )


def test_ats_keywords_rejects_missing_token():
    response = client.post(
        "/ats/keywords",
        json=VALID_BODY,
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Not authenticated"
    )


def test_ats_keywords_validates_body(
    authenticated_user,
):
    response = client.post(
        "/ats/keywords",
        json={
            "job_description": "A role.",
        },
        headers={
            "Authorization": "Bearer test-access-token",
        },
    )

    assert response.status_code == 422
