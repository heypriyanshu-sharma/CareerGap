import pytest
from fastapi.testclient import TestClient

import backend
from file_upload import MAX_FILE_SIZE

client = TestClient(backend.app)

@pytest.fixture(autouse=True)
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

def reset_rate_limit():
    backend.limiter._storage.reset()


def test_upload_txt_file():
    reset_rate_limit()

    response = client.post(
        "/upload",
        files={
            "file": (
                "resume.txt",
                b"Python developer with FastAPI experience.",
                "text/plain",
            )
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "filename": "resume.txt",
        "text": "Python developer with FastAPI experience.",
    }


def test_upload_requires_file():
    reset_rate_limit()

    response = client.post("/upload")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "No file was provided."
    )


def test_upload_rejects_unsupported_extension():
    reset_rate_limit()

    response = client.post(
        "/upload",
        files={
            "file": (
                "malware.exe",
                b"not an executable",
                "application/octet-stream",
            )
        },
    )

    assert response.status_code == 400
    assert "Unsupported file type" in (
        response.json()["detail"]
    )


def test_upload_rejects_oversized_file():
    reset_rate_limit()

    oversized_file = b"x" * (MAX_FILE_SIZE + 1)

    response = client.post(
        "/upload",
        files={
            "file": (
                "large.txt",
                oversized_file,
                "text/plain",
            )
        },
    )

    assert response.status_code in {400, 413}


def test_upload_rejects_fake_pdf():
    reset_rate_limit()

    response = client.post(
        "/upload",
        files={
            "file": (
                "resume.pdf",
                b"This is not actually a PDF.",
                "application/pdf",
            )
        },
    )

    assert response.status_code == 400
    assert "valid PDF" in response.json()["detail"]


def test_upload_rejects_fake_docx():
    reset_rate_limit()

    response = client.post(
        "/upload",
        files={
            "file": (
                "resume.docx",
                b"This is not actually a DOCX.",
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document",
            )
        },
    )

    assert response.status_code == 400
    assert "valid DOCX" in response.json()["detail"]

def test_upload_requires_authentication():
    backend.app.dependency_overrides.pop(
        backend.get_current_user,
        None,
    )

    reset_rate_limit()

    response = client.post(
        "/upload",
        files={
            "file": (
                "resume.txt",
                b"Python developer.",
                "text/plain",
            )
        },
    )

    assert response.status_code == 401