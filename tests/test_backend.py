from fastapi.testclient import TestClient
from fastapi.security import HTTPAuthorizationCredentials
import backend
import pytest
import asyncio
import requests
from datetime import datetime
from uuid import UUID


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


# ============================================================
# Interview Studio Tests
# ============================================================

def test_interview_generate_accepts_valid_request(monkeypatch):
    """Test that /interview/generate accepts valid request and returns session."""
    expected_questions = [
        {"type": "technical", "text": "How would you implement a rate limiter in FastAPI?"},
        {"type": "technical", "text": "Explain the difference between async and sync in Python."},
        {"type": "behavioral", "text": "Describe a time you debugged a production issue under pressure."},
        {"type": "behavioral", "text": "Tell me about a conflict with a teammate and how you resolved it."},
        {"type": "project", "text": "Walk me through the architecture of your Test API project."},
    ]

    monkeypatch.setattr(
        backend,
        "generate_interview_questions",
        lambda *args, **kwargs: asyncio.sleep(0, result=[
            backend.InterviewQuestion(**q) for q in expected_questions
        ]),
    )

    # Mock profile fetch
    def mock_profile_get(*args, **kwargs):
        class MockResp:
            ok = True
            def json(self): return [{"target_role": "Backend Engineer"}]
        return MockResp()

    monkeypatch.setattr(requests, "get", mock_profile_get)

    # Mock resume fetch
    monkeypatch.setattr(
        backend,
        "get_resume",
        lambda token, user_id, resume_id: {
            "plain_text": "Python developer with FastAPI experience.",
            "content": {"projects": [{"name": "Test API", "description": "A Python API project."}]}
        },
    )

# Mock session creation
    monkeypatch.setattr(
        backend,
        "create_interview_session",
        lambda access_token, user_id, mode, target_role, resume_id, questions: {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "mode": "quick",
            "target_role": "Backend Engineer",
            "resume_id": "123e4567-e89b-12d3-a456-426614174000",
            "questions": [q for q in expected_questions],
            "status": "pending",
            "created_at": "2024-01-01T00:00:00Z",
        },
    )

    backend.limiter._storage.reset()

    payload = {
        "mode": "quick",
        "target_role": "Backend Engineer",
        "resume_id": "123e4567-e89b-12d3-a456-426614174000",
    }

    response = client.post("/interview/generate", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "123e4567-e89b-12d3-a456-426614174000"
    assert data["mode"] == "quick"
    assert data["target_role"] == "Backend Engineer"
    assert len(data["questions"]) == 5
    assert data["status"] == "pending"
    # Verify question distribution for quick mode
    types = [q["type"] for q in data["questions"]]
    assert types.count("technical") == 2
    assert types.count("behavioral") == 2
    assert types.count("project") == 1


def test_interview_generate_rejects_invalid_mode(monkeypatch):
    """Test that /interview/generate rejects invalid mode."""
    backend.limiter._storage.reset()

    payload = {
        "mode": "invalid_mode",
        "target_role": "Backend Engineer",
    }

    response = client.post("/interview/generate", json=payload)

    assert response.status_code == 422


def test_interview_generate_rejects_unowned_resume(monkeypatch):
    """Test that /interview/generate rejects resume not owned by user."""
    monkeypatch.setattr(
        backend,
        "get_resume",
        lambda token, user_id, resume_id: None,
    )

    backend.limiter._storage.reset()

    payload = {
        "mode": "quick",
        "target_role": "Backend Engineer",
        "resume_id": "123e4567-e89b-12d3-a456-426614174000",
    }

    response = client.post("/interview/generate", json=payload)

    assert response.status_code == 404


def test_interview_answer_accepts_valid_submission(monkeypatch):
    """Test that /interview/{id}/answer accepts valid answers and returns feedback."""
    # Mock session fetch
    def mock_session_get(*args, **kwargs):
        class MockResp:
            ok = True
            def json(self): return [{
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "mode": "quick",
                "target_role": "Backend Engineer",
                "resume_id": "123e4567-e89b-12d3-a456-426614174000",
                "questions": [
                    {"type": "technical", "text": "Question 1"},
                    {"type": "behavioral", "text": "Question 2"},
                    {"type": "project", "text": "Question 3"},
                    {"type": "technical", "text": "Question 4"},
                    {"type": "behavioral", "text": "Question 5"},
                ],
                "status": "pending",
            }]
        return MockResp()

    monkeypatch.setattr(requests, "get", mock_session_get)

    # Mock resume fetch
    monkeypatch.setattr(
        backend,
        "get_resume",
        lambda token, user_id, resume_id: {
            "plain_text": "Python developer with FastAPI experience.",
            "content": {"projects": [{"name": "Test API", "description": "A Python API project."}]}
        },
    )

# Mock feedback generation
    expected_feedback = {
        "session_id": "123e4567-e89b-12d3-a456-426614174000",
        "score": 78.5,
        "feedback": {
            "technical": {"score": 80, "strengths": ["Good knowledge"], "gaps": ["Docker"]},
            "behavioral": {"score": 75, "strengths": ["Clear STAR"], "gaps": ["More examples"]},
            "project": {"score": 82, "strengths": ["Ownership shown"], "gaps": ["Scale details"]},
        },
        "weak_areas": ["Docker", "System Design"],
        "recommendations": [
            {"area": "Docker", "action": "Add Dockerfile to project", "resources": ["https://docs.docker.com"]}
        ],
        "completed_at": "2024-01-01T00:00:00Z",
    }

    async def mock_evaluate(mode, target_role, resume_text, job_description, projects, questions, answers):
        return backend.InterviewFeedbackResponse(**expected_feedback)

    monkeypatch.setattr(backend, "evaluate_interview_answers", mock_evaluate)

    # Mock submit answers
    monkeypatch.setattr(
        backend,
        "submit_interview_answers",
        lambda access_token, user_id, session_id, answers, score, feedback, weak_areas, recommendations: {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "mode": "quick",
            "target_role": "Backend Engineer",
            "resume_id": "123e4567-e89b-12d3-a456-426614174000",
            "questions": [],
            "answers": ["Answer 1", "Answer 2", "Answer 3", "Answer 4", "Answer 5"],
            "score": 78.5,
            "feedback": expected_feedback["feedback"],
            "weak_areas": expected_feedback["weak_areas"],
            "recommendations": expected_feedback["recommendations"],
            "status": "completed",
            "completed_at": "2024-01-01T00:00:00Z",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        },
    )

    backend.limiter._storage.reset()

    payload = {
        "answers": [
            "Answer 1", "Answer 2", "Answer 3", "Answer 4", "Answer 5"
        ]
    }

    response = client.post("/interview/123e4567-e89b-12d3-a456-426614174000/answer", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["score"] == 78.5
    assert "technical" in data["feedback"]
    assert "behavioral" in data["feedback"]
    assert "project" in data["feedback"]
    assert data["weak_areas"] == ["Docker", "System Design"]
    assert len(data["recommendations"]) == 1


def test_interview_answer_rejects_wrong_answer_count(monkeypatch):
    """Test that answer submission rejects mismatched answer count."""
    def mock_session_get(*args, **kwargs):
        class MockResp:
            ok = True
            def json(self): return [{
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "mode": "quick",
                "target_role": "Backend Engineer",
                "resume_id": "123e4567-e89b-12d3-a456-426614174000",
                "questions": [{"type": "technical", "text": "Q1"}, {"type": "behavioral", "text": "Q2"}],
                "status": "pending",
            }]
        return MockResp()

    monkeypatch.setattr(requests, "get", mock_session_get)

    backend.limiter._storage.reset()

    payload = {
        "answers": ["Only one answer for two questions"]
    }

    response = client.post("/interview/123e4567-e89b-12d3-a456-426614174000/answer", json=payload)

    assert response.status_code == 400
    assert "count" in response.json()["detail"].lower()


def test_interview_answer_rejects_completed_session(monkeypatch):
    """Test that answer submission rejects already completed session."""
    def mock_session_get(*args, **kwargs):
        class MockResp:
            ok = True
            def json(self): return [{
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "mode": "quick",
                "questions": [{"type": "technical", "text": "Q1"}],
                "status": "completed",
            }]
        return MockResp()

    monkeypatch.setattr(requests, "get", mock_session_get)

    backend.limiter._storage.reset()

    payload = {"answers": ["Answer 1"]}

    response = client.post("/interview/123e4567-e89b-12d3-a456-426614174000/answer", json=payload)

    assert response.status_code == 400
    assert "completed" in response.json()["detail"].lower()


def test_interview_answer_rejects_empty_answers(monkeypatch):
    """Test that answer submission rejects empty answers."""
    def mock_session_get(*args, **kwargs):
        class MockResp:
            ok = True
            def json(self): return [{
                "id": "test-session-id",
                "mode": "quick",
                "questions": [{"type": "technical", "text": "Q1"}],
                "status": "pending",
            }]
        return MockResp()

    monkeypatch.setattr(requests, "get", mock_session_get)

    backend.limiter._storage.reset()

    payload = {"answers": [""]}

    response = client.post("/interview/test-session-id/answer", json=payload)

    assert response.status_code == 422


def test_interview_history_returns_sessions(monkeypatch):
    """Test that /interview/history returns user's sessions."""
    expected_history = [
        {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "mode": "quick",
            "target_role": "Backend Engineer",
            "score": 78.5,
            "status": "completed",
            "created_at": "2024-01-01T00:00:00Z",
            "completed_at": "2024-01-01T01:00:00Z",
        },
        {
            "id": "123e4567-e89b-12d3-a456-426614174001",
            "mode": "full",
            "target_role": "Frontend Engineer",
            "score": None,
            "status": "pending",
            "created_at": "2024-01-02T00:00:00Z",
            "completed_at": None,
        },
    ]

    monkeypatch.setattr(
        backend,
        "get_interview_history",
        lambda access_token, user_id, limit, offset: expected_history,
    )

    response = client.get("/interview/history")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == "123e4567-e89b-12d3-a456-426614174000"
    assert data[1]["mode"] == "full"


def test_interview_delete_removes_session(monkeypatch):
    """Test that DELETE /interview/{id} removes session."""
    deleted = {}

    monkeypatch.setattr(
        backend,
        "delete_interview_session",
        lambda access_token, user_id, session_id: deleted.update({"session_id": session_id}),
    )

    response = client.delete("/interview/123e4567-e89b-12d3-a456-426614174000")

    assert response.status_code == 204
    assert deleted["session_id"] == "123e4567-e89b-12d3-a456-426614174000"


def test_interview_delete_rejects_unowned(monkeypatch):
    """Test that DELETE rejects session not owned by user."""
    monkeypatch.setattr(
        backend,
        "delete_interview_session",
        lambda access_token, user_id, session_id: (_ for _ in ()).throw(
            backend.DatabaseRequestError("Not found.", status_code=404)
        ),
    )

    response = client.delete("/interview/123e4567-e89b-12d3-a456-426614174000")

    assert response.status_code == 404


def test_interview_generate_requires_authentication():
    """Test that /interview/generate requires authentication."""
    backend.app.dependency_overrides.pop(backend.get_current_user, None)
    backend.app.dependency_overrides.pop(backend.security, None)

    payload = {"mode": "quick", "target_role": "Backend Engineer"}

    response = client.post("/interview/generate", json=payload)

    assert response.status_code == 401

    # Restore auth
    backend.app.dependency_overrides[backend.get_current_user] = lambda: {"sub": "test-user-id", "email": "test@example.com"}
    backend.app.dependency_overrides[backend.security] = lambda: HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-access-token")


def test_interview_answer_requires_authentication():
    """Test that /interview/{id}/answer requires authentication."""
    backend.app.dependency_overrides.pop(backend.get_current_user, None)
    backend.app.dependency_overrides.pop(backend.security, None)

    payload = {"answers": ["Answer 1"]}

    response = client.post("/interview/test-session-id/answer", json=payload)

    assert response.status_code == 401

    # Restore auth
    backend.app.dependency_overrides[backend.get_current_user] = lambda: {"sub": "test-user-id", "email": "test@example.com"}
    backend.app.dependency_overrides[backend.security] = lambda: HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-access-token")


def test_interview_rate_limit_generate(monkeypatch):
    """Test rate limit on interview generate."""
    monkeypatch.setattr(
        backend,
        "generate_interview_questions",
        lambda *args, **kwargs: asyncio.sleep(0, result=[
            backend.InterviewQuestion(type="technical", text="Q")] * 5),
    )

    def mock_profile_get(*args, **kwargs):
        class MockResp:
            ok = True
            def json(self): return [{"target_role": "Engineer"}]
        return MockResp()
    monkeypatch.setattr(requests, "get", mock_profile_get)

    monkeypatch.setattr(backend, "get_resume", lambda *a, **k: {"plain_text": "dev", "content": {}})

    monkeypatch.setattr(backend, "create_interview_session", lambda *a, **k: {
        "id": "123e4567-e89b-12d3-a456-426614174000", "mode": "quick", "questions": [], "status": "pending", "created_at": "2024-01-01T00:00:00Z",
    })

    backend.limiter._storage.reset()

    payload = {"mode": "quick", "target_role": "Engineer"}

    # 5 requests should succeed
    for _ in range(5):
        response = client.post("/interview/generate", json=payload)
        assert response.status_code == 200

    # 6th should be rate limited
    response = client.post("/interview/generate", json=payload)
    assert response.status_code == 429


def test_interview_concurrent_submission_rejected(monkeypatch):
    """Test that concurrent answer submissions are rejected (second gets 400)."""
    def mock_session_get(*args, **kwargs):
        class MockResp:
            ok = True
            def json(self): return [{
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "mode": "quick",
                "questions": [{"type": "technical", "text": "Q1"}],
                "status": "pending",
            }]
        return MockResp()

    monkeypatch.setattr(requests, "get", mock_session_get)

    monkeypatch.setattr(backend, "get_resume", lambda *a, **k: {"plain_text": "dev", "content": {}})

    call_count = {"count": 0}

    async def mock_evaluate(*args, **kwargs):
        call_count["count"] += 1
        await asyncio.sleep(0.01)  # Simulate AI delay
        return backend.InterviewFeedbackResponse(
            session_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
            score=80.0,
            feedback={
                "technical": backend.CategoryFeedback(score=80, strengths=[], gaps=[]),
                "behavioral": backend.CategoryFeedback(score=80, strengths=[], gaps=[]),
                "project": backend.CategoryFeedback(score=80, strengths=[], gaps=[]),
            },
            weak_areas=[],
            recommendations=[],
            completed_at=datetime.now(),
        )

    monkeypatch.setattr(backend, "evaluate_interview_answers", mock_evaluate)

    submit_results = [
        {"id": "123e4567-e89b-12d3-a456-426614174000", "status": "completed"},
        backend.DatabaseRequestError("Session already completed.", status_code=400),
    ]

    def mock_submit(*args, **kwargs):
        if submit_results:
            result = submit_results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

    monkeypatch.setattr(backend, "submit_interview_answers", mock_submit)

    backend.limiter._storage.reset()

    payload = {"answers": ["Answer 1"]}

    # Fire two concurrent requests
    import threading
    results = []

    def make_request():
        response = client.post("/interview/123e4567-e89b-12d3-a456-426614174000/answer", json=payload)
        results.append(response.status_code)

    t1 = threading.Thread(target=make_request)
    t2 = threading.Thread(target=make_request)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # One should succeed (200), one should fail (400)
    assert 200 in results
    assert 400 in results


def test_interview_answer_handles_gemini_timeout(monkeypatch):
    """Test that answer submission handles Gemini timeout (504) and does not persist."""
    def mock_session_get(*args, **kwargs):
        class MockResp:
            ok = True
            def json(self): return [{
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "mode": "quick",
                "target_role": "Backend Engineer",
                "resume_id": "123e4567-e89b-12d3-a456-426614174000",
                "questions": [{"type": "technical", "text": "Q1"}],
                "status": "pending",
            }]
        return MockResp()

    monkeypatch.setattr(requests, "get", mock_session_get)

    monkeypatch.setattr(backend, "get_resume", lambda *a, **k: {"plain_text": "dev", "content": {}})

    async def mock_evaluate_timeout(*args, **kwargs):
        raise RuntimeError("Request timeout after 60 seconds")

    monkeypatch.setattr(backend, "evaluate_interview_answers", mock_evaluate_timeout)

    # Track if submit_interview_answers is called
    submit_called = {"called": False}

    def mock_submit(*args, **kwargs):
        submit_called["called"] = True
        return {"id": "test", "status": "completed"}

    monkeypatch.setattr(backend, "submit_interview_answers", mock_submit)

    backend.limiter._storage.reset()

    payload = {"answers": ["Answer 1"]}

    response = client.post("/interview/123e4567-e89b-12d3-a456-426614174000/answer", json=payload)

    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()
    assert not submit_called["called"], "submit_interview_answers should not be called on AI timeout"


def test_interview_answer_handles_missing_gemini_key(monkeypatch):
    """Test that answer submission handles missing GEMINI_API_KEY (503) and does not persist."""
    def mock_session_get(*args, **kwargs):
        class MockResp:
            ok = True
            def json(self): return [{
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "mode": "quick",
                "target_role": "Backend Engineer",
                "resume_id": "123e4567-e89b-12d3-a456-426614174000",
                "questions": [{"type": "technical", "text": "Q1"}],
                "status": "pending",
            }]
        return MockResp()

    monkeypatch.setattr(requests, "get", mock_session_get)

    monkeypatch.setattr(backend, "get_resume", lambda *a, **k: {"plain_text": "dev", "content": {}})

    async def mock_evaluate_missing_key(*args, **kwargs):
        raise RuntimeError("GEMINI_API_KEY not configured")

    monkeypatch.setattr(backend, "evaluate_interview_answers", mock_evaluate_missing_key)

    # Track if submit_interview_answers is called
    submit_called = {"called": False}

    def mock_submit(*args, **kwargs):
        submit_called["called"] = True
        return {"id": "test", "status": "completed"}

    monkeypatch.setattr(backend, "submit_interview_answers", mock_submit)

    backend.limiter._storage.reset()

    payload = {"answers": ["Answer 1"]}

    response = client.post("/interview/123e4567-e89b-12d3-a456-426614174000/answer", json=payload)

    assert response.status_code == 503
    assert "api key" in response.json()["detail"].lower() or "unavailable" in response.json()["detail"].lower()
    assert not submit_called["called"], "submit_interview_answers should not be called on missing API key"
