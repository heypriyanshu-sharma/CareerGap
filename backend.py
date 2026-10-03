from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from fastapi.middleware.cors import CORSMiddleware
from auth import get_current_user, security
from career_gap import run_careergap
from ai_advisor import generate_career_advice, safe_error_detail
from ats_match import extract_job_keywords
from database import (
    get_analysis_history,
    save_analysis,
    delete_analysis,
)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "https://careergap.pages.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
        "https://careergap.pages.dev",
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

@app.get("/analyses")
def get_analyses(
     claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):
    try:
        return get_analysis_history(
            credentials.credentials
        )

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to load analysis history.",
        )

@app.post("/analyze")
@limiter.limit("10/minute")
def analyze(
    request: Request,
    career_gap_request: CareerGapRequest,
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
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
            # Log the failure so an unavailable advisor is diagnosable.
            # safe_error_detail redacts the API key, which SDK errors can
            # embed in the request URL.
            print(
                "AI ADVISOR ERROR:",
                type(error).__name__,
                safe_error_detail(error),
            )
            results["ai_advice"] = None
            results["ai_advice_error"] = (
                "AI career advice is unavailable right now. "
                "Your CareerGap analysis is complete and unaffected."
            )

        save_analysis(
    access_token=credentials.credentials,
    user_id=claims["sub"],
    resume=career_gap_request.resume,
    job_description=career_gap_request.job_description,
    projects=projects,
    analysis=results,
)

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

@app.post("/ats/keywords")
def ats_keywords(
    career_gap_request: CareerGapRequest,
    claims: dict = Depends(get_current_user),
):
    """Return ranked keywords extracted from the job description.

    This describes the job description only. It does not score the
    candidate, and it makes no claim about which keywords the resume
    satisfies. It reads nothing from the database and writes nothing.
    """

    return {
        "keywords": extract_job_keywords(
            career_gap_request.job_description
        )
    }

@app.delete(
    "/analyses/{analysis_id}",
    status_code=204
)
def delete_analysis_route(
    analysis_id: str,
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):
    try:
        delete_analysis(
            access_token=credentials.credentials,
            analysis_id=analysis_id,
        )

    except Exception as error:
        print(
            "DELETE ANALYSIS ERROR:",
            type(error).__name__,
            str(error),
        )

        if (
            hasattr(error, "response")
            and error.response is not None
        ):
            print(
                "SUPABASE STATUS:",
                error.response.status_code,
            )

            print(
                "SUPABASE BODY:",
                error.response.text,
            )

        raise HTTPException(
            status_code=500,
            detail="Unable to delete analysis.",
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