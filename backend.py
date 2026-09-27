from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from auth import get_current_user
from career_gap import run_careergap
from ai_advisor import generate_career_advice
from file_upload import (
    MAX_FILE_SIZE,
    process_uploaded_file,
)


# ---------------------------------------------------------------------------
# Security limits
# ---------------------------------------------------------------------------

MAX_UPLOAD_REQUEST_SIZE = MAX_FILE_SIZE + (512 * 1024)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="CareerGap API",
    description="Evidence-Based Career Readiness Engine",
    version="1.0.0",
)

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler,
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SlowAPIMiddleware)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ProjectInput(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=200,
    )
    description: str = Field(
        min_length=1,
        max_length=5_000,
    )


class CareerGapRequest(BaseModel):
    resume: str = Field(
        min_length=1,
        max_length=20_000,
    )
    job_description: str = Field(
        min_length=1,
        max_length=20_000,
    )
    projects: list[ProjectInput] = Field(
        min_length=1,
        max_length=10,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def validate_upload_request_size(request: Request) -> None:
    content_length = request.headers.get("content-length")

    if content_length is None:
        return

    try:
        request_size = int(content_length)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="Invalid Content-Length header.",
        ) from error

    if request_size > MAX_UPLOAD_REQUEST_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Upload request is too large.",
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "CareerGap API is running",
        "status": "ok",
    }

@app.get("/auth/me")
def auth_me(
    claims: dict = Depends(get_current_user),
):
    return {
        "user_id": claims["sub"],
        "email": claims.get("email"),
    }

@app.post("/analyze")
@limiter.limit("10/minute")
def analyze(
    request: Request,
    career_gap_request: CareerGapRequest,
    claims: dict = Depends(get_current_user),
):
    projects = [
        {
            "name": project.name,
            "description": project.description,
        }
        for project in career_gap_request.projects
    ]

    try:
        results = run_careergap(
            career_gap_request.resume,
            career_gap_request.job_description,
            projects,
        )

        # AI advice is an additional interpretation layer.
        # The deterministic CareerGap analysis remains the source of truth.
        try:
            results["ai_advice"] = generate_career_advice(results)
        except Exception as error:
            print("AI ADVISOR ERROR:", error)
            results["ai_advice"] = None

        return results

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="CareerGap analysis failed unexpectedly.",
        )


@app.post("/upload")
@limiter.limit("5/minute")
async def upload_file(
    request: Request,
    claims: dict = Depends(get_current_user),
):
    validate_upload_request_size(request)

    try:
        form = await request.form(
            max_files=1,
            max_fields=0,
            max_part_size=MAX_FILE_SIZE,
        )
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail="Invalid multipart upload.",
        ) from error

    uploaded_file = form.get("file")

    if uploaded_file is None:
        raise HTTPException(
            status_code=400,
            detail="No file was provided.",
        )

    if not hasattr(uploaded_file, "filename"):
        raise HTTPException(
            status_code=400,
            detail="Invalid uploaded file.",
        )

    filename = uploaded_file.filename

    if not filename:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must have a filename.",
        )

    try:
        file_data = await uploaded_file.read(
            MAX_FILE_SIZE + 1
        )

        extracted_text = process_uploaded_file(
            filename,
            file_data,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except UnicodeDecodeError as error:
        raise HTTPException(
            status_code=400,
            detail="Text file must use valid UTF-8 encoding.",
        ) from error

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Unable to process the uploaded file.",
        )

    return {
        "filename": filename,
        "text": extracted_text,
    }