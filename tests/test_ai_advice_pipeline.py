"""Focused tests for the AI advice pipeline.

These cover the path from Gemini output to the JSON payload the
frontend renders: advice attached, failures reported instead of
silently dropped, and the deterministic CareerGap analysis untouched.
"""

from fastapi.security import HTTPAuthorizationCredentials
import pytest


try:
    import backend
except Exception as error:  # pragma: no cover - environment dependent
    pytest.skip(
        "Backend is not importable in this environment: "
        f"{type(error).__name__}.",
        allow_module_level=True,
    )


client = pytest.importorskip("fastapi.testclient").TestClient(
    backend.app
)


PAYLOAD = {
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


@pytest.fixture(autouse=True)
def analysis_environment(monkeypatch):
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
        "save_analysis",
        lambda **kwargs: None,
    )

    backend.limiter._storage.reset()

    yield

    backend.app.dependency_overrides.pop(
        backend.get_current_user,
        None,
    )

    backend.app.dependency_overrides.pop(
        backend.security,
        None,
    )


def test_successful_advice_reaches_the_frontend(monkeypatch):
    monkeypatch.setattr(
        backend,
        "generate_career_advice",
        lambda career_gap_data: "1. Close the Docker gap.",
    )

    response = client.post("/analyze", json=PAYLOAD)

    assert response.status_code == 200

    data = response.json()

    assert data["ai_advice"] == "1. Close the Docker gap."
    assert "ai_advice_error" not in data


def test_successful_advice_does_not_change_the_analysis(monkeypatch):
    monkeypatch.setattr(
        backend,
        "generate_career_advice",
        lambda career_gap_data: "Advice.",
    )

    data = client.post("/analyze", json=PAYLOAD).json()

    for key, value in EXPECTED_ANALYSIS.items():
        assert data[key] == value


def test_saved_record_keeps_the_advice(monkeypatch):
    """History rows must carry the advice the saved view renders."""
    saved = {}

    monkeypatch.setattr(
        backend,
        "generate_career_advice",
        lambda career_gap_data: "Stored advice.",
    )

    def capture(**kwargs):
        saved.update(kwargs)

    monkeypatch.setattr(
        backend,
        "save_analysis",
        capture,
    )

    client.post("/analyze", json=PAYLOAD)

    assert saved["analysis"]["ai_advice"] == "Stored advice."


def test_advisor_exception_is_reported(monkeypatch):
    monkeypatch.setattr(
        backend,
        "generate_career_advice",
        _raise(RuntimeError("quota exceeded")),
    )

    response = client.post("/analyze", json=PAYLOAD)

    assert response.status_code == 200

    data = response.json()

    assert data["ai_advice"] is None
    assert "unavailable" in data["ai_advice_error"].lower()


def test_advisor_exception_does_not_change_the_analysis(monkeypatch):
    monkeypatch.setattr(
        backend,
        "generate_career_advice",
        _raise(RuntimeError("quota exceeded")),
    )

    data = client.post("/analyze", json=PAYLOAD).json()

    assert data["score"] == EXPECTED_ANALYSIS["score"]
    assert data["matched_skills"] == EXPECTED_ANALYSIS["matched_skills"]
    assert data["missing_skills"] == EXPECTED_ANALYSIS["missing_skills"]


def test_advisor_exception_still_saves_the_analysis(monkeypatch):
    saved = {}

    monkeypatch.setattr(
        backend,
        "generate_career_advice",
        _raise(RuntimeError("quota exceeded")),
    )

    def capture(**kwargs):
        saved.update(kwargs)

    monkeypatch.setattr(
        backend,
        "save_analysis",
        capture,
    )

    client.post("/analyze", json=PAYLOAD)

    assert saved["analysis"]["ai_advice"] is None
    assert "ai_advice_error" in saved["analysis"]
    assert saved["analysis"]["score"] == EXPECTED_ANALYSIS["score"]


def test_advisor_failure_is_logged(monkeypatch, capsys):
    monkeypatch.setattr(
        backend,
        "generate_career_advice",
        _raise(RuntimeError("quota exceeded")),
    )

    client.post("/analyze", json=PAYLOAD)

    logged = capsys.readouterr().out

    assert "AI ADVISOR ERROR" in logged
    assert "RuntimeError" in logged
    assert "quota exceeded" in logged


def test_advisor_failure_log_does_not_expose_the_api_key(
    monkeypatch,
    capsys,
):
    secret = "test-secret-key-value"

    monkeypatch.setenv(
        "GEMINI_API_KEY",
        secret,
    )

    monkeypatch.setattr(
        backend,
        "generate_career_advice",
        _raise(
            RuntimeError(
                "request to https://generativelanguage.googleapis.com/"
                f"v1beta/models?key={secret} failed"
            )
        ),
    )

    client.post("/analyze", json=PAYLOAD)

    logged = capsys.readouterr().out

    assert "AI ADVISOR ERROR" in logged
    assert secret not in logged


def test_backend_no_longer_depends_on_the_advisor_at_import(
    monkeypatch,
):
    """A missing advisor config must not stop analyses from running."""
    monkeypatch.setattr(
        backend,
        "generate_career_advice",
        _raise(
            RuntimeError("GEMINI_API_KEY is not configured.")
        ),
    )

    response = client.post("/analyze", json=PAYLOAD)

    assert response.status_code == 200

    data = response.json()

    assert data["score"] == EXPECTED_ANALYSIS["score"]


def _raise(error):
    def failing(career_gap_data):
        raise error

    return failing