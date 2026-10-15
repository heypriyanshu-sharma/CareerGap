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


def test_analyze_returns_github_recommendations(monkeypatch):
    """Regression test: /analyze should include github_recommendations in response."""
    expected_result = {
        "resume_skills": ["Python"],
        "job_skills": ["Python", "FastAPI"],
        "matched_skills": ["Python"],
        "missing_skills": ["FastAPI"],
        "score": 50.0,
        "github_recommendations": [
            {"repo": {"full_name": "test/repo"}, "score": 90}
        ],
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

    data = response.json()
    assert "github_recommendations" in data
    assert isinstance(data["github_recommendations"], list)
    assert data["github_recommendations"] == expected_result["github_recommendations"]
    assert data["github_recommendations"][0]["repo"]["full_name"] == "test/repo"
    assert data["github_recommendations"][0]["score"] == 90


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


def test_analyze_passes_job_keywords_to_ats_scorecard(monkeypatch):
    """Regression test: /analyze should extract job keywords and pass them to ATS scorecard."""
    expected_result = {
        "resume_skills": ["Python"],
        "job_skills": ["Python", "FastAPI"],
        "matched_skills": ["Python"],
        "missing_skills": ["FastAPI"],
        "score": 50.0,
    }

    captured_keywords = {}

    def mock_run_careergap(resume, job_description, projects):
        return expected_result

    def mock_calculate_ats_scorecard(resume_text, job_text, job_keywords, projects):
        captured_keywords["job_keywords"] = job_keywords
        captured_keywords["resume_text"] = resume_text
        captured_keywords["job_text"] = job_text
        captured_keywords["projects"] = projects
        return {
            "score": 75,
            "label": "Strong",
            "breakdown": [],
            "reasons": [],
            "improvements": [],
            "disclaimer": "Test disclaimer",
        }

    monkeypatch.setattr(backend, "run_careergap", mock_run_careergap)
    monkeypatch.setattr(backend, "calculate_ats_scorecard", mock_calculate_ats_scorecard)
    monkeypatch.setattr(backend, "generate_career_advice", lambda x: None)

    backend.limiter._storage.reset()

    payload = {
        "resume": "Python developer with FastAPI experience.",
        "job_description": "Required: Python, FastAPI. Preferred: React.",
        "projects": [
            {"name": "Test Project", "description": "A Python API project."}
        ],
    }

    response = client.post("/analyze", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "ats_scorecard" in data
    assert data["ats_scorecard"]["score"] == 75

    # Verify job keywords were extracted and passed to calculate_ats_scorecard
    assert "job_keywords" in captured_keywords
    keywords = captured_keywords["job_keywords"]
    assert isinstance(keywords, list)
    assert len(keywords) > 0

    # Verify keywords contain expected terms from job description
    keyword_terms = [kw["term"] for kw in keywords]
    assert "Python" in keyword_terms
    assert "FastAPI" in keyword_terms

    # Verify the resume and job description were passed through
    assert captured_keywords["resume_text"] == payload["resume"]
    assert captured_keywords["job_text"] == payload["job_description"]
    assert captured_keywords["projects"] == payload["projects"]
