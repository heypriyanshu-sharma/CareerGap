from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials
import backend
import pytest


client = TestClient(backend.app)
@pytest.fixture(autouse=True)
def authenticated_user(monkeypatch):
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

def test_home_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "CareerGap API is running",
        "status": "ok",
    }


def test_analyze_accepts_valid_request(monkeypatch):
    expected_result = {
        "resume_skills": ["Python"],
        "job_skills": ["Python", "FastAPI"],
        "matched_skills": ["Python"],
        "missing_skills": ["FastAPI"],
        "score": 50.0,
    }

    monkeypatch.setattr(
        backend,
        "run_careergap",
        lambda resume, job_description, projects: expected_result,
    )

    monkeypatch.setattr(
        backend,
        "generate_career_advice",
        lambda career_gap_data: "Test AI career advice.",
    )

    payload = {
        "resume": "I know Python.",
        "job_description": "Required: Python FastAPI.",
        "projects": [
            {
                "name": "Test API",
                "description": "A Python API project.",
            }
        ],
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 200

    assert response.json() == {
        **expected_result,
        "ai_advice": "Test AI career advice.",
    }


def test_analyze_rejects_empty_resume():
    payload = {
        "resume": "",
        "job_description": "Required: Python.",
        "projects": [
            {
                "name": "Test Project",
                "description": "A Python project.",
            }
        ],
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 422


def test_analyze_rejects_empty_job_description():
    payload = {
        "resume": "Python developer.",
        "job_description": "",
        "projects": [
            {
                "name": "Test Project",
                "description": "A Python project.",
            }
        ],
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 422


def test_analyze_rejects_empty_projects():
    payload = {
        "resume": "Python developer.",
        "job_description": "Required: Python.",
        "projects": [],
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 422


def test_analyze_rejects_empty_project_name():
    payload = {
        "resume": "Python developer.",
        "job_description": "Required: Python.",
        "projects": [
            {
                "name": "",
                "description": "A Python project.",
            }
        ],
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 422


def test_analyze_rejects_empty_project_description():
    payload = {
        "resume": "Python developer.",
        "job_description": "Required: Python.",
        "projects": [
            {
                "name": "Test Project",
                "description": "",
            }
        ],
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 422


def test_analyze_returns_400_for_careergap_value_error(monkeypatch):
    def fake_run_careergap(
        resume,
        job_description,
        projects,
    ):
        raise ValueError("Invalid CareerGap input.")

    monkeypatch.setattr(
        backend,
        "run_careergap",
        fake_run_careergap,
    )

    payload = {
        "resume": "Python developer.",
        "job_description": "Required: Python.",
        "projects": [
            {
                "name": "Test Project",
                "description": "A Python project.",
            }
        ],
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid CareerGap input."


def test_analyze_returns_500_for_unexpected_error(monkeypatch):
    def fake_run_careergap(
        resume,
        job_description,
        projects,
    ):
        raise RuntimeError("Unexpected failure.")

    monkeypatch.setattr(
        backend,
        "run_careergap",
        fake_run_careergap,
    )

    payload = {
        "resume": "Python developer.",
        "job_description": "Required: Python.",
        "projects": [
            {
                "name": "Test Project",
                "description": "A Python project.",
            }
        ],
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "CareerGap analysis failed unexpectedly."
    )


def test_analyze_rate_limit_blocks_excessive_requests(monkeypatch):
    expected_result = {
        "status": "ok",
    }

    monkeypatch.setattr(
        backend,
        "run_careergap",
        lambda resume, job_description, projects: expected_result,
    )

    monkeypatch.setattr(
        backend,
        "generate_career_advice",
        lambda career_gap_data: "Test AI career advice.",
    )

    # Reset the in-memory rate-limit storage so this test
    # starts with a clean rate-limit window.
    backend.limiter._storage.reset()

    payload = {
        "resume": "Python developer.",
        "job_description": "Required: Python.",
        "projects": [
            {
                "name": "Test Project",
                "description": "A Python project.",
            }
        ],
    }

    responses = [
        client.post("/analyze", json=payload)
        for _ in range(10)
    ]

    assert all(
        response.status_code == 200
        for response in responses
    )

    blocked_response = client.post(
        "/analyze",
        json=payload,
    )

    assert blocked_response.status_code == 429

def test_analyze_requires_authentication():
    backend.app.dependency_overrides.pop(
        backend.get_current_user,
        None,
    )

    payload = {
        "resume": "Python developer.",
        "job_description": "Required: Python.",
        "projects": [
            {
                "name": "Test Project",
                "description": "A Python project.",
            }
        ],
    }

    response = client.post(
        "/analyze",
        json=payload,
    )

    assert response.status_code == 401

def test_delete_analysis(monkeypatch):
    called = {}

    monkeypatch.setattr(
        backend,
        "delete_analysis",
        lambda **kwargs: called.update(kwargs),
    )

    response = client.delete(
        "/analyses/test-analysis-id"
    )

    assert response.status_code == 204
    assert called["access_token"] == (
        "test-access-token"
    )
    assert called["analysis_id"] == (
        "test-analysis-id"
    )


def test_analyze_preserves_curated_resources(monkeypatch):
    curated_data = [
        {
            "skill": "FastAPI",
            "type": "Documentation",
            "title": "FastAPI Official Documentation",
            "url": "https://fastapi.tiangolo.com/",
            "description": "Official guide and interactive tutorial.",
        },
        {
            "skill": "FastAPI",
            "type": "Practice",
            "title": "FastAPI User Guide Tutorial",
            "url": "https://fastapi.tiangolo.com/tutorial/",
            "description": "Hands-on guide building endpoints.",
        },
        {
            "skill": "FastAPI",
            "type": "YouTube Tutorial Search",
            "title": "FastAPI Tutorial Search",
            "url": "https://www.youtube.com/results?search_query=FastAPI+tutorial",
            "description": "Search results for FastAPI tutorials on YouTube.",
        },
    ]

    expected_result = {
        "resume_skills": ["Python"],
        "job_skills": ["Python", "FastAPI"],
        "matched_skills": ["Python"],
        "missing_skills": ["FastAPI"],
        "score": 50.0,
        "curated_resources": curated_data,
        "github_recommendations": [],
    }

    monkeypatch.setattr(
        backend,
        "run_careergap",
        lambda resume, job_description, projects: expected_result,
    )
    monkeypatch.setattr(
        backend,
        "generate_career_advice",
        lambda career_gap_data: None,
    )

    backend.limiter._storage.reset()

    payload = {
        "resume": "I know Python.",
        "job_description": "Required: Python FastAPI.",
        "projects": [
            {
                "name": "Test API",
                "description": "A Python API project.",
            }
        ],
    }

    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "curated_resources" in data
    assert data["curated_resources"] == curated_data
