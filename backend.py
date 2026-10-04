from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.types import ASGIApp, Receive, Scope, Send
from typing import NoReturn
from uuid import UUID
from fastapi.middleware.cors import CORSMiddleware
from auth import get_current_user, security
from career_gap import run_careergap
from ai_advisor import generate_career_advice, safe_error_detail
from ats_match import extract_job_keywords
from database import (
    get_analysis_history,
    save_analysis,
    delete_analysis,
    DatabaseRequestError,
    create_resume,
    delete_resume,
    get_resume,
    list_resumes,
    set_default_resume,
    update_resume,
)
from file_upload import (
    MAX_FILE_SIZE,
    process_uploaded_file,
)
from resume_builder import (
    ResumeValidationError,
    build_plain_text,
    normalize_content,
)
from resume_pdf import ResumePDFError, generate_resume_pdf


# ---------------------------------------------------------------------------
# Security limits
# ---------------------------------------------------------------------------

MAX_UPLOAD_REQUEST_SIZE = MAX_FILE_SIZE + (512 * 1024)

# Structured resume documents are far smaller than an upload. The cap
# stops a single request from becoming an unbounded write.
MAX_RESUME_REQUEST_SIZE = 256 * 1024

MAX_RESUME_TITLE_LENGTH = 120

# Only resume writes are size limited. The upload route keeps its own
# limit, and analysis requests are unchanged.
RESUME_WRITE_PATHS = (
    "/resumes",
    "/resumes/{resume_id}",
)

# The two methods that carry a resume document. The other resume routes
# take no request body, so a size check on them would only reject a
# request the application was never going to read.
RESUME_WRITE_METHODS = (
    "POST",
    "PUT",
)


class BodySizeLimitMiddleware:
    """Reject oversized request bodies before they are parsed.

    FastAPI parses and validates the body before an endpoint runs, so a
    Content-Length check inside a route happens too late and can be
    bypassed by omitting or understating the header. This middleware
    counts the bytes actually received and answers 413 as soon as the
    limit is passed.

    It is scoped to the resume write methods and paths: every other
    request, including reads and deletes of the same paths, is passed
    straight through untouched. A delete that carried a large body
    would otherwise be answered 413 instead of being routed normally.
    """

    def __init__(
        self,
        app: ASGIApp,
        max_size: int,
        paths,
        methods,
    ):
        self.app = app
        self.max_size = max_size
        self.paths = tuple(paths)
        self.methods = frozenset(
            method.upper()
            for method in methods
        )

    def _applies_to(self, path: str) -> bool:

        normalized = path.rstrip("/") or "/"

        if normalized in self.paths:

            return True

        # Exactly one id segment below the collection: /resumes/<uuid>.
        segments = normalized.split("/")

        return (
            len(segments) == 3
            and segments[1] == "resumes"
            and bool(segments[2])
        )

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:

        if (
            scope["type"] != "http"
            or scope.get("method") not in self.methods
            or not self._applies_to(
                scope.get("path", "")
            )
        ):

            await self.app(
                scope,
                receive,
                send,
            )

            return

        declared = None

        for name, value in scope.get("headers", []):

            if name == b"content-length":

                try:
                    declared = int(value)
                except ValueError:
                    declared = None

                break

        if declared is not None and declared > self.max_size:

            await self._reject(send)

            return

        received = 0
        rejected = False
        response_started = False

        limited_receive: Receive

        async def limited_receive():

            nonlocal received

            message = await receive()

            if message["type"] == "http.request":

                received += len(
                    message.get("body", b"")
                )

                if received > self.max_size:

                    # Stop reading. The parser sees a disconnect and
                    # gives up instead of buffering the rest, and the
                    # response it produces is replaced below.
                    return {
                        "type": "http.disconnect"
                    }

            return message

        wrapped_send: Send

        async def wrapped_send(message) -> None:

            nonlocal rejected, response_started

            if rejected:
                # The 413 already answered this request. Everything the
                # application still sends is dropped, so exactly one
                # response body reaches the client.
                return

            if message["type"] == "http.response.start":

                response_started = True

                if received > self.max_size:

                    rejected = True

                    await self._reject(send)

                    return

            await send(message)

        try:
            await self.app(
                scope,
                limited_receive,
                wrapped_send,
            )

        finally:
            # An aborted read that produced no response at all must
            # still be answered, otherwise the client waits forever.
            if (
                received > self.max_size
                and not rejected
                and not response_started
            ):
                await self._reject(send)

    async def _reject(self, send: Send) -> None:
        body = b'{"detail":"Request is too large."}'

        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )

        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )


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
#
# Registered last on purpose. Starlette runs the most recently added
# middleware outermost, so this layer has to sit outside
# BodySizeLimitMiddleware: a 413 is produced there, before any inner
# layer runs, and a browser can only read that response when the CORS
# headers are on it. An allowed origin would otherwise see an opaque
# network error instead of "Request is too large".

app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    BodySizeLimitMiddleware,
    max_size=MAX_RESUME_REQUEST_SIZE,
    paths=RESUME_WRITE_PATHS,
    methods=RESUME_WRITE_METHODS,
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


class ResumeWriteRequest(BaseModel):
    """Create or update payload for one resume.

    Extra fields are rejected rather than ignored so a client cannot
    smuggle values such as `user_id` into a request and have them
    silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        min_length=1,
        max_length=MAX_RESUME_TITLE_LENGTH,
    )
    content: dict = Field(
        default_factory=dict,
    )
    is_default: bool = False


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


def prepare_resume_payload(
    resume_request: ResumeWriteRequest,
):
    """Validate a resume write and derive its stored plain text.

    plain_text is always generated here from the submitted structure,
    so the database never stores a client-authored ATS document.
    """

    title = resume_request.title.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Resume title is required.",
        )

    try:
        document = normalize_content(
            resume_request.content
        )
    except ResumeValidationError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    return {
        "title": title,
        "content": document,
        "plain_text": build_plain_text(document),
    }


def resume_error_response(error) -> NoReturn:
    """Translate a resume failure into an API response.

    Expected database failures carry their own status. Anything else is
    logged server-side with a redacted detail and reported to the client
    as a generic failure, so an internal error or a secret never reaches
    the response.
    """

    if isinstance(error, DatabaseRequestError):

        raise HTTPException(
            status_code=error.status_code,
            detail=error.detail,
        ) from error

    print(
        "RESUME ERROR:",
        type(error).__name__,
        safe_error_detail(error),
    )

    raise HTTPException(
        status_code=500,
        detail="Resume request failed.",
    )


# ============================================================
# PDF EXPORT
# ============================================================

import urllib.parse


def _content_disposition_filename(filename: str) -> str:
    """
    Build a standards-compliant Content-Disposition filename value.

    Uses RFC 5987 encoding (filename*) for UTF-8 support with an
    ASCII-safe fallback in the filename parameter. Replaces unsafe
    characters in the fallback with underscores.
    """
    # ASCII fallback: replace non-ASCII and unsafe characters
    ascii_fallback = "".join(
        c if 32 <= ord(c) < 127 and c not in '",;\\' else "_" for c in filename
    ).strip()

    # UTF-8 encoded filename per RFC 5987
    utf8_encoded = urllib.parse.quote(filename, safe="")

    # If fallback equals the original (all ASCII safe), just use simple form
    if ascii_fallback == filename and ascii_fallback:
        return f'attachment; filename="{ascii_fallback}"'

    # Empty filename edge case
    if not ascii_fallback:
        return 'attachment; filename=""'

    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{utf8_encoded}'


@app.get(
    "/resumes/{resume_id}/export",
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Download the resume as a PDF.",
        },
        404: {"description": "Resume not found."},
        401: {"description": "Unauthorized."},
        500: {"description": "PDF generation failed."},
    },
)
def export_resume_pdf(
    resume_id: UUID,
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Export a resume as a professional PDF.

    The PDF is generated server-side using ReportLab and includes
    all resume sections with ATS-friendly formatting.
    """
    try:
        resume = get_resume(
            credentials.credentials,
            claims["sub"],
            str(resume_id),
        )
    except Exception as error:
        resume_error_response(error)

    if resume is None:
        raise HTTPException(
            status_code=404,
            detail="Resume not found.",
        )

    try:
        pdf_bytes = generate_resume_pdf(resume)
    except ResumePDFError as error:
        print("PDF GENERATION ERROR:", error)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate PDF.",
        ) from error

    filename = f"{resume.get('title', 'resume').replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": _content_disposition_filename(filename)},
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


# ---------------------------------------------------------------------------
# Resume Builder
# ---------------------------------------------------------------------------
#
# Ownership always comes from the verified token claims. The caller's
# access token is forwarded to Supabase so row level security applies,
# and every table read, update and delete is additionally scoped by user
# id in the request itself.
#
# Resume endpoints deliberately never trust a client-supplied user id.
# The write models reject unknown fields, so a payload containing
# `user_id` is rejected with 422 instead of being silently ignored.
#
# Writes go through the transactional database functions, so a resume is
# never left created or updated when its default switch fails.

@app.get("/resumes")
def get_resumes(
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
    limit: int = 50,
):
    try:
        return list_resumes(
            credentials.credentials,
            claims["sub"],
            limit=limit,
        )

    except Exception as error:
        resume_error_response(error)


@app.post("/resumes")
@limiter.limit("30/minute")
def post_resume(
    request: Request,
    resume_request: ResumeWriteRequest,
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):
    prepared = prepare_resume_payload(resume_request)

    try:
        return create_resume(
            access_token=credentials.credentials,
            user_id=claims["sub"],
            title=prepared["title"],
            content=prepared["content"],
            plain_text=prepared["plain_text"],
            is_default=resume_request.is_default,
        )

    except Exception as error:
        resume_error_response(error)


@app.get("/resumes/{resume_id}")
def get_resume_route(
    resume_id: UUID,
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):
    try:
        resume = get_resume(
            credentials.credentials,
            claims["sub"],
            str(resume_id),
        )

    except Exception as error:
        resume_error_response(error)

    if resume is None:
        raise HTTPException(
            status_code=404,
            detail="Resume not found.",
        )

    return resume


@app.put("/resumes/{resume_id}")
@limiter.limit("30/minute")
def put_resume(
    request: Request,
    resume_id: UUID,
    resume_request: ResumeWriteRequest,
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):
    prepared = prepare_resume_payload(resume_request)

    try:
        return update_resume(
            access_token=credentials.credentials,
            user_id=claims["sub"],
            resume_id=str(resume_id),
            title=prepared["title"],
            content=prepared["content"],
            plain_text=prepared["plain_text"],
            is_default=resume_request.is_default,
        )

    except Exception as error:
        resume_error_response(error)


@app.delete(
    "/resumes/{resume_id}",
    status_code=204
)
def delete_resume_route(
    resume_id: UUID,
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):
    try:
        delete_resume(
            credentials.credentials,
            claims["sub"],
            str(resume_id),
        )

    except Exception as error:
        resume_error_response(error)