from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, conint, confloat, constr
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.types import ASGIApp, Receive, Scope, Send
from typing import Annotated, NoReturn, Optional, List, Dict, Literal
from uuid import UUID
from datetime import datetime
import os
import json
import asyncio
import ipaddress
import requests
from supabase import create_client
from pathlib import Path
from dotenv import load_dotenv

# Load the external secrets file used by local development
SECRETS_PATH = Path(r"C:\Users\ASUS\OneDrive\Documents\careergap_secrets\.env")
if SECRETS_PATH.exists():
    load_dotenv(SECRETS_PATH)
else:
    load_dotenv()

from auth import get_current_user, security
from career_gap import run_careergap
from ai_advisor import DEFAULT_MODEL, build_client, generate_career_advice, safe_error_detail
from ats_match import extract_job_keywords, calculate_ats_scorecard, analyze_resume_pdf
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
    create_interview_session,
    submit_interview_answers,
    delete_interview_session,
    get_interview_history,
    get_interview_session,
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

# ---------------------------------------------------------------------------
# Supabase Admin Client (for account deletion)
# ---------------------------------------------------------------------------
#
# The service key is read lazily instead of at import time. A missing key is
# a configuration problem for one feature, not a reason to stop the whole
# API from starting, so only the delete-account route reports it.

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv(
    "SUPABASE_PUBLISHABLE_KEY"
)
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

_supabase_admin = None


def get_supabase_admin():
    """Return a Supabase admin client, or None when unconfigured.

    The service key is never sent to the browser: it is only used
    server-side to delete the caller's own account.
    """

    global _supabase_admin

    if _supabase_admin is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            return None

        _supabase_admin = create_client(
            SUPABASE_URL,
            SUPABASE_SERVICE_KEY,
        )

    return _supabase_admin


# ---------------------------------------------------------------------------
# Profile models
# ---------------------------------------------------------------------------

PROFILE_COLUMNS = (
    "id,avatar_url,full_name,target_role,"
    "experience_level,created_at,updated_at"
)

EXPERIENCE_LEVELS = (
    "student",
    "junior",
    "mid",
    "senior",
    "lead",
)

MAX_FULL_NAME_LENGTH = 120
MAX_TARGET_ROLE_LENGTH = 120
MAX_AVATAR_URL_LENGTH = 500


class ProfileUpdateRequest(BaseModel):
    """Fields a user may change about their own profile.

    Extra fields are rejected rather than ignored, so a payload
    containing `id` or `user_id` fails with 422 instead of being
    silently dropped.
    """

    model_config = ConfigDict(extra="forbid")

    full_name: Optional[str] = Field(
        default=None,
        max_length=MAX_FULL_NAME_LENGTH,
    )
    target_role: Optional[str] = Field(
        default=None,
        max_length=MAX_TARGET_ROLE_LENGTH,
    )
    experience_level: Optional[str] = None
    avatar_url: Optional[str] = Field(
        default=None,
        max_length=MAX_AVATAR_URL_LENGTH,
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

def get_client_key(request):
    """Rate-limit key for one request.

    On Render every public request transits Cloudflare (Render's DDoS
    protection provider), which supplies CF-Connecting-IP as a single
    edge-computed value. X-Forwarded-For is deliberately never key
    material: Render appends to it without clearing client-supplied
    values, so it is spoofable there and any XFF-derived key would let
    one client rotate its own limit bucket. The header value must parse
    as an IP address, so an invalid or malicious value can never become
    a limiter key (it falls back instead). Without the header (local
    development, private-network or health-check traffic) the true peer
    address is used, matching the pre-fix behavior.
    """
    cf_ip = request.headers.get("cf-connecting-ip", "").strip()

    if cf_ip:
        try:
            return str(ipaddress.ip_address(cf_ip))
        except ValueError:
            pass  # not an IP: never use it as a limiter key

    return get_remote_address(request)


limiter = Limiter(key_func=get_client_key)


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
# Interview Studio models
# ---------------------------------------------------------------------------

class InterviewQuestion(BaseModel):
    type: Literal["technical", "behavioral", "project"]
    text: str = Field(min_length=1, max_length=1000)


class InterviewGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["quick", "full"]
    target_role: Optional[str] = Field(default=None, max_length=120)
    resume_id: Optional[UUID] = None



class InterviewAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: List[Annotated[str, Field(min_length=1, max_length=5000)]]


class CategoryFeedback(BaseModel):
    score: Annotated[int, Field(ge=0, le=100)]
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    area: str = Field(min_length=1, max_length=120)
    action: str = Field(min_length=1, max_length=500)
    resources: List[str] = Field(default_factory=list)


class InterviewFeedbackResponse(BaseModel):
    session_id: UUID
    score: Annotated[float, Field(ge=0, le=100)]
    feedback: Dict[Literal["technical", "behavioral", "project"], CategoryFeedback]
    weak_areas: List[str] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    completed_at: datetime



class InterviewSessionResponse(BaseModel):
    id: UUID
    mode: Literal["quick", "full"]
    target_role: Optional[str]
    resume_id: Optional[UUID]
    questions: List[InterviewQuestion]
    answers: Optional[List[str]] = None
    feedback: Optional[Dict[Literal["technical", "behavioral", "project"], CategoryFeedback]] = None
    score: Optional[float] = None
    weak_areas: Optional[List[str]] = None
    recommendations: Optional[List[Recommendation]] = None
    status: Literal["pending", "completed"]
    created_at: datetime
    completed_at: Optional[datetime] = None


class InterviewHistoryItem(BaseModel):
    id: UUID
    mode: Literal["quick", "full"]
    target_role: Optional[str]
    score: Optional[float]
    status: Literal["pending", "completed"]
    created_at: datetime
    completed_at: Optional[datetime]


# Rebuild models to resolve forward references
InterviewQuestion.model_rebuild()
CategoryFeedback.model_rebuild()
Recommendation.model_rebuild()
InterviewFeedbackResponse.model_rebuild()
InterviewSessionResponse.model_rebuild()
InterviewHistoryItem.model_rebuild()


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


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
#
# The caller's own access token is forwarded to Supabase so row level
# security applies, and every request is additionally scoped to the user
# id taken from the verified token. Ownership therefore comes from the
# token, never from anything the client sent: the write model rejects
# unknown fields, so a payload carrying `id` or `user_id` is refused
# with 422 instead of being silently ignored.


def _profile_headers(
    access_token,
    prefer=None,
):
    """Headers for a PostgREST call made as the signed-in user.

    The service key is deliberately not used here so the RLS policies
    stay meaningful for profile data.
    """

    headers = {
        "apikey": SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    if prefer:
        headers["Prefer"] = prefer

    return headers


def _normalize_profile_text(value):
    """Trim a submitted string, mapping blank input to NULL."""

    trimmed = value.strip()

    return trimmed or None


def _select_profile(
    access_token,
    user_id,
):
    """Return the caller's profile row, or None when it has none yet."""

    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/profiles",
        headers=_profile_headers(access_token),
        params={
            "id": f"eq.{user_id}",
            "select": PROFILE_COLUMNS,
        },
        timeout=10,
    )

    if not response.ok:
        return None

    rows = response.json()

    if not rows:
        return None

    return rows[0]


def _write_profile(
    access_token,
    user_id,
    updates,
):
    """Insert or update the caller's profile row.

    PostgREST upsert is used so a user who signed up before the profiles
    table existed still gets a row on their first edit, instead of the
    update silently matching nothing.
    """

    payload = {
        "id": user_id,
        **updates,
    }

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/profiles",
        headers=_profile_headers(
            access_token,
            prefer="resolution=merge-duplicates,return=representation",
        ),
        params={"on_conflict": "id"},
        json=payload,
        timeout=10,
    )

    if not response.ok:
        return None

    rows = response.json()

    if not rows:
        return None

    return rows[0]


def _ensure_profile_row(access_token, user_id):
    """Create the caller's profile row when it does not exist yet.

    The on_auth_user_created trigger only covers users created after
    0002_create_profiles.sql was applied, so an account that predates
    the table has no row at all. Reading the Profile page therefore
    creates one on the spot.

    The row is created with the same PostgREST upsert the edit path
    uses, so on_conflict=id plus resolution=merge-duplicates means a
    repeated call merges into the existing row instead of adding a
    second one. Only the id is sent, so an existing row's columns are
    never overwritten by this.

    Returns None when the row cannot be created, which lets the caller
    fall back to an empty profile rather than failing the request.
    """

    try:
        return _write_profile(access_token, user_id, {})

    except Exception as error:
        # Creating the row is a convenience. Losing it must not stop
        # the profile page from loading, so this is logged and the
        # caller reports empty fields instead.
        print(
            "PROFILE CREATE ERROR:",
            type(error).__name__,
            safe_error_detail(error),
        )

        return None


@app.get("/auth/profile")
def get_profile(
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):
    """Return the caller's identity together with their profile.

    A missing profile row is reported as null fields rather than an
    error, so a user who signed up before the table existed can still
    use the page and create their profile.
    """

    user_id = claims["sub"]

    try:
        profile = _select_profile(
            credentials.credentials,
            user_id,
        )

    except Exception as error:
        print(
            "PROFILE READ ERROR:",
            type(error).__name__,
            safe_error_detail(error),
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to load profile.",
        )

    if profile is None:
        profile = _ensure_profile_row(
            credentials.credentials,
            user_id,
        )

    if profile is None:
        profile = {
            "id": user_id,
            "avatar_url": None,
            "full_name": None,
            "target_role": None,
            "experience_level": None,
            "created_at": None,
            "updated_at": None,
        }

    return {
        "user_id": user_id,
        "email": claims.get("email"),
        "profile": profile,
    }


@app.put("/auth/profile")
@limiter.limit("10/minute")
def update_profile(
    request: Request,
    profile_update: ProfileUpdateRequest,
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):
    """Update the caller's own profile."""

    user_id = claims["sub"]

    if (
        profile_update.experience_level is not None
        and profile_update.experience_level
        not in EXPERIENCE_LEVELS
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Experience level must be one of: "
                + ", ".join(EXPERIENCE_LEVELS)
                + "."
            ),
        )

    if (
        profile_update.avatar_url is not None
        and profile_update.avatar_url
        and not profile_update.avatar_url.startswith(
            ("http://", "https://")
        )
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Avatar URL must start with http:// "
                "or https://."
            ),
        )

    # Only the fields the client actually sent are written, so one
    # update never blanks out the others.
    updates = {}

    for field in (
        "full_name",
        "target_role",
        "avatar_url",
    ):
        value = getattr(profile_update, field)

        if value is not None:
            updates[field] = _normalize_profile_text(
                value
            )

    if profile_update.experience_level is not None:
        updates["experience_level"] = (
            _normalize_profile_text(
                profile_update.experience_level
            )
        )

    if not updates:
        raise HTTPException(
            status_code=400,
            detail="No profile fields to update.",
        )

    try:
        profile = _write_profile(
            credentials.credentials,
            user_id,
            updates,
        )

    except Exception as error:
        print(
            "PROFILE WRITE ERROR:",
            type(error).__name__,
            safe_error_detail(error),
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to update profile.",
        )

    if profile is None:
        raise HTTPException(
            status_code=500,
            detail="Unable to update profile.",
        )

    return profile


# ---------------------------------------------------------------------------
# Account deletion
# ---------------------------------------------------------------------------
#
# The target account comes from the verified token claims only. There is
# no user id in the request model at all, so a caller cannot ask the API
# to delete somebody else's account, and an extra field is rejected with
# 422 rather than ignored.
#
# Deleting the auth user cascades in the database: `profiles.id` and
# `resumes.user_id` are declared `references auth.users (id) on delete
# cascade`, so the profile and every resume are removed with the account.


@app.delete("/auth/delete-account", status_code=204)
@limiter.limit("3/minute")
def delete_account(
    request: Request,
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):
    """Delete the authenticated user's account and its user-owned data."""

    user_id = claims["sub"]

    admin = get_supabase_admin()

    if admin is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Account deletion is not available right now."
            ),
        )

    try:
        admin.auth.admin.delete_user(user_id)

    except Exception as error:
        # Only the exception type is logged. The Supabase SDK error
        # can embed the service key in its request URL, so the message
        # is redacted before it reaches the log.
        print(
            "DELETE ACCOUNT ERROR:",
            type(error).__name__,
            safe_error_detail(error),
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to delete account.",
        )

    # The caller's own session is now invalid. The client is expected to
    # sign out locally and leave the page.
    return Response(status_code=204)


@app.get("/analyses")
def get_analyses(
     claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(
        security
    ),
):
    try:
        return get_analysis_history(
            credentials.credentials,
            user_id=claims["sub"],
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

        # Calculate ATS scorecard
        job_keywords = extract_job_keywords(career_gap_request.job_description)
        try:
            results["ats_scorecard"] = calculate_ats_scorecard(
                resume_text=career_gap_request.resume,
                job_text=career_gap_request.job_description,
                job_keywords=job_keywords,
                projects=projects,
            )
        except Exception as error:
            print(
                "ATS SCORECARD ERROR:",
                type(error).__name__,
                safe_error_detail(error),
            )
            results["ats_scorecard"] = None

        # Persist the analysis for the caller's history. A failed or
        # timed-out save must not destroy the completed analysis (the
        # deterministic result is the source of truth), so the failure
        # is logged and reported in-band instead of failing the request.
        try:
            save_analysis(
                access_token=credentials.credentials,
                user_id=claims["sub"],
                resume=career_gap_request.resume,
                job_description=career_gap_request.job_description,
                projects=projects,
                analysis=results,
            )

        except Exception as error:
            # safe_error_detail strips the Gemini API key from exception
            # text (the project-wide redaction standard shared with the
            # handlers above). In this path the realistic errors carry
            # no keys — DatabaseRequestError messages are hardcoded
            # strings and requests errors never embed headers — so this
            # is defense-in-depth for the log.
            print(
                "ANALYSIS SAVE ERROR:",
                type(error).__name__,
                safe_error_detail(error),
            )
            results["analysis_save_error"] = (
                "Your analysis is complete, but saving it to your "
                "history failed. It is not available in Saved Analyses."
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


class ATSResumeAnalyzeRequest(BaseModel):
    """Request model for PDF resume analysis."""
    job_description: Optional[str] = Field(default=None, max_length=20_000)
    # Optional resume_id to analyze a saved resume's PDF
    resume_id: Optional[UUID] = None


@app.post("/ats/analyze-resume")
@limiter.limit("10/minute")
async def ats_analyze_resume(
    request: Request,
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Analyze a resume PDF for ATS readiness.

    Accepts either:
    - A file upload (multipart/form-data with 'file' field)
    - A resume_id to analyze an existing saved resume (generates PDF server-side)

    Optional job_description for job-specific alignment scoring.
    """
    validate_upload_request_size(request)

    try:
        form = await request.form(max_files=1, max_fields=2, max_part_size=MAX_FILE_SIZE)
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail="Invalid multipart upload.",
        ) from error

    uploaded_file = form.get("file")
    job_description = form.get("job_description")
    resume_id_str = form.get("resume_id")

    pdf_bytes = None

    if uploaded_file and hasattr(uploaded_file, "filename"):
        # File upload path
        if not uploaded_file.filename:
            raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

        try:
            file_data = await uploaded_file.read(MAX_FILE_SIZE + 1)
            # Reuse existing file validation and extraction
            from file_upload import (
                validate_extension,
                validate_file_size,
                validate_file_signature,
                extract_text,
            )
            from pathlib import Path
            import tempfile

            extension = Path(uploaded_file.filename).suffix.lower()
            validate_extension(uploaded_file.filename)
            validate_file_size(len(file_data))

            with tempfile.TemporaryDirectory() as temp_directory:
                temp_path = Path(temp_directory) / "uploaded_file"
                temp_path.write_bytes(file_data)
                validate_file_signature(temp_path, extension)

                if extension != ".pdf":
                    raise HTTPException(
                        status_code=400,
                        detail="ATS resume analysis currently only supports PDF files. Please upload a PDF."
                    )

                pdf_bytes = file_data

        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="Unable to process the uploaded PDF file.")

    elif resume_id_str:
        # Saved resume path - generate PDF from stored resume
        try:
            from uuid import UUID
            resume_id = UUID(resume_id_str)
            resume = get_resume(credentials.credentials, claims["sub"], str(resume_id))
        except Exception as error:
            raise HTTPException(status_code=404, detail="Resume not found.")

        if resume is None:
            raise HTTPException(status_code=404, detail="Resume not found.")

        try:
            pdf_bytes = generate_resume_pdf(resume)
        except Exception as error:
            print("PDF GENERATION ERROR:", error)
            raise HTTPException(status_code=500, detail="Failed to generate PDF from saved resume.")

    else:
        raise HTTPException(
            status_code=400,
            detail="Either 'file' (PDF upload) or 'resume_id' must be provided."
        )

    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="No PDF data available for analysis.")

    # Analyze the PDF
    try:
        result = analyze_resume_pdf(
            pdf_bytes=pdf_bytes,
            job_text=job_description if job_description else None,
            projects=None,  # Could be extended to accept projects
        )
    except Exception as error:
        print("ATS PDF ANALYSIS ERROR:", type(error).__name__, safe_error_detail(error))
        raise HTTPException(status_code=500, detail="ATS analysis failed.")

    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# ---------------------------------------------------------------------------
# Interview Studio
# ---------------------------------------------------------------------------

# Mode-specific question distribution
INTERVIEW_QUESTION_CONFIG = {
    "quick": {"technical": 2, "behavioral": 2, "project": 1},
    "full": {"technical": 5, "behavioral": 5, "project": 5},
}


def build_interview_prompt(mode: str, target_role: Optional[str], resume_text: str, job_description: str, projects: list) -> str:
    """Build prompt for generating interview questions."""
    config = INTERVIEW_QUESTION_CONFIG[mode]
    total = sum(config.values())
    role_line = f"Target role: {target_role}" if target_role else "Target role: Not specified"

    return f"""
You are an expert technical interviewer for CareerGap's Interview Studio.

Generate {total} interview questions for a {mode} practice session.

{role_line}

Candidate context:
- Resume: {resume_text[:3000]}
- Target job: {job_description[:3000]}
- Projects: {json.dumps([p.get('description', '')[:500] for p in projects[:3]])}

Question distribution:
- Technical: {config['technical']}
- Behavioral: {config['behavioral']}
- Project-based: {config['project']}

Rules:
- Questions must be specific to the candidate's background and target role
- Technical questions should probe depth in relevant technologies
- Behavioral questions should use STAR format (Situation, Task, Action, Result)
- Project questions should reference the candidate's actual projects
- No generic "tell me about yourself" questions
- Each question must be a single clear sentence

Return JSON only:
{{
  "questions": [
    {{"type": "technical", "text": "..."}},
    {{"type": "behavioral", "text": "..."}},
    {{"type": "project", "text": "..."}}
  ]
}}
""".strip()


def build_feedback_prompt(mode: str, target_role: Optional[str], resume_text: str, job_description: str, projects: list, questions: list, answers: list) -> str:
    """Build prompt for evaluating interview answers."""
    qa_pairs = [
        {"question": q.text, "type": q.type, "answer": a}
        for q, a in zip(questions, answers)
    ]
    qa_json = json.dumps(qa_pairs, indent=2)
    projects_json = json.dumps([p.get('description', '')[:500] for p in projects[:3]])

    return f"""
You are an expert interview evaluator for CareerGap's Interview Studio.

Evaluate a {mode} interview session.

Target role: {target_role or 'Not specified'}

Candidate context:
- Resume: {resume_text[:3000]}
- Target job: {job_description[:3000]}
- Projects: {projects_json}

Interview Q&A:
{qa_json}

CRITICAL EVALUATION RULES:
1. GROUND ALL FEEDBACK IN THE ACTUAL ANSWERS PROVIDED. Do not invent technical details, skills, or concepts not mentioned in the candidate's answers.
2. If an answer is generic, placeholder text (e.g., "test", "N/A", "idk"), or irrelevant, score it LOW and note "Insufficient evidence in answer" in gaps.
3. Scores MUST reflect the quality and relevance of the actual answers. Do not give moderate scores to empty/placeholder responses.
4. Weak areas and recommendations must be directly traceable to gaps observed IN THE ANSWERS.
5. If answers lack STAR format, say so explicitly. If answers lack technical depth, say so explicitly.

Provide structured feedback:

Scoring (0-100 per category, overall 0-100):
- Technical: knowledge depth, problem-solving (based ONLY on technical answers given)
- Behavioral: communication, STAR usage, self-awareness (based ONLY on behavioral answers given)
- Project: ownership, impact, technical depth (based ONLY on project-based answers given)

Weak areas: specific skill gaps observed IN THE ANSWERS
Recommendations: actionable next steps with resources, grounded in answer gaps

Return JSON only:
{{
  "score": 75.5,
  "feedback": {{
    "technical": {{"score": 80, "strengths": ["..."], "gaps": ["..."]}},
    "behavioral": {{"score": 70, "strengths": ["..."], "gaps": ["..."]}},
    "project": {{"score": 75, "strengths": ["..."], "gaps": ["..."]}}
  }},
  "weak_areas": ["Docker", "System Design"],
  "recommendations": [
    {{"area": "Docker", "action": "Add Dockerfile to Project X", "resources": ["https://docs.docker.com"]}}
  ]
}}
""".strip()

def parse_gemini_json(raw: str) -> dict:
    """Parse JSON returned by Gemini, including Markdown-fenced responses."""
    raw = raw.strip()

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        if raw.rstrip().endswith("```"):
            raw = raw.rstrip()[:-3].strip()

    return json.loads(raw)

async def generate_interview_questions(mode: str, target_role: Optional[str], resume_text: str, job_description: str, projects: list) -> List[InterviewQuestion]:
    """Generate interview questions via Gemini."""
    client = build_client()
    prompt = build_interview_prompt(mode, target_role, resume_text, job_description, projects)
    model = os.getenv("GEMINI_MODEL") or DEFAULT_MODEL

    # Set timeout based on mode: 35s for quick (5 questions), 125s for full (15 questions)
    # These are set slightly below frontend timeouts (45s/135s) so backend timeout fires first
    # if model is slow, allowing frontend to show proper error. If network is slow, frontend timeout fires.
    timeout_seconds = 35 if mode == "quick" else 125

    def _sync_call():
        interaction = client.interactions.create(
            model=model,
            input=prompt,
            generation_config={"temperature": 0.3, "max_output_tokens": 4096},
        )
        # Try multiple response attributes for SDK compatibility
        raw = (
            getattr(interaction, "output_text", None)
            or getattr(interaction, "text", None)
            or getattr(interaction, "output", None)
            or ""
        )
        raw = raw.strip() if raw else ""
        if not raw:
            raise RuntimeError("Gemini returned no questions text.")
        return raw

    try:
        # Run synchronous SDK call in thread pool with timeout
        raw = await asyncio.wait_for(asyncio.to_thread(_sync_call), timeout=timeout_seconds)

        data = parse_gemini_json(raw)
        questions = [InterviewQuestion(**q) for q in data.get("questions", [])]

        if not questions:
            raise ValueError("No questions generated")

        return questions

    except asyncio.TimeoutError:
        raise RuntimeError(f"Question generation timed out after {timeout_seconds} seconds.")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Gemini questions output: {e}")
    except Exception as e:
        raise RuntimeError(f"Question generation failed: {safe_error_detail(e)}")


async def evaluate_interview_answers(
    mode: str,
    target_role: Optional[str],
    resume_text: str,
    job_description: str,
    projects: list,
    questions: List[InterviewQuestion],
    answers: List[str],
) -> dict:
    """Evaluate interview answers via Gemini. Returns dict with feedback data."""
    client = build_client()
    prompt = build_feedback_prompt(mode, target_role, resume_text, job_description, projects, questions, answers)
    model = os.getenv("GEMINI_MODEL") or DEFAULT_MODEL

    # Match question generation timeout: 30s for quick (5 questions), 120s for full (15 questions)
    timeout_seconds = 30 if mode == "quick" else 120

    def _sync_call():
        interaction = client.interactions.create(
            model=model,
            input=prompt,
            generation_config={"temperature": 0.3, "max_output_tokens": 4096},
        )
        # Try multiple response attributes for SDK compatibility
        raw = (
            getattr(interaction, "output_text", None)
            or getattr(interaction, "text", None)
            or getattr(interaction, "output", None)
            or ""
        )
        raw = raw.strip() if raw else ""
        if not raw:
            raise RuntimeError("Gemini returned no feedback text.")
        return raw

    try:
        # Run synchronous SDK call in thread pool with timeout
        raw = await asyncio.wait_for(asyncio.to_thread(_sync_call), timeout=timeout_seconds)

        data = parse_gemini_json(raw)

        # Validate required keys
        required_feedback_keys = {"technical", "behavioral", "project"}
        if not required_feedback_keys.issubset(data.get("feedback", {}).keys()):
            raise ValueError("Missing feedback categories")

        return data

    except asyncio.TimeoutError:
        raise RuntimeError(f"Feedback generation timed out after {timeout_seconds} seconds.")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Gemini feedback output: {e}")
    except Exception as e:
        raise RuntimeError(f"Feedback generation failed: {safe_error_detail(e)}")


# ---------------------------------------------------------------------------
# Interview Studio Routes
# ---------------------------------------------------------------------------

@app.post("/interview/generate")
@limiter.limit("5/minute")
async def interview_generate(
    request: Request,
    interview_request: InterviewGenerateRequest,
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = claims["sub"]

    # Validate resume_id if provided
    if interview_request.resume_id:
        resume = get_resume(credentials.credentials, user_id, str(interview_request.resume_id))
        if not resume:
            raise HTTPException(status_code=404, detail="Resume not found or not owned.")

    # Get user profile for target_role context
    profile = None
    try:
        profile_resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/profiles",
            headers={
                "apikey": SUPABASE_PUBLISHABLE_KEY,
                "Authorization": f"Bearer {credentials.credentials}",
            },
            params={"id": f"eq.{user_id}", "select": "target_role"},
            timeout=10,
        )
        if profile_resp.ok:
            rows = profile_resp.json()
            if rows:
                profile = rows[0]
    except Exception:
        pass

    target_role = interview_request.target_role or (profile.get("target_role") if profile else None)

    # Get resume text for context
    resume_text = ""
    if interview_request.resume_id:
        resume = get_resume(credentials.credentials, user_id, str(interview_request.resume_id))
        if resume:
            resume_text = resume.get("plain_text", "")

    # We need job description - for interview studio, we can use a generic one or ask user
    # For now, construct from target_role
    job_description = f"Role: {target_role or 'Software Engineer'}. " \
        "We are looking for a candidate with strong technical skills, " \
        "problem-solving ability, and relevant project experience."

    # Get user's projects from resume if available
    projects = []
    if interview_request.resume_id and resume:
        content = resume.get("content", {})
        resume_projects = content.get("projects", [])
        for p in resume_projects[:3]:
            if isinstance(p, dict):
                projects.append({
                    "name": p.get("name", ""),
                    "description": p.get("description", "")[:500]
                })

    # Generate questions
    try:
        questions = await generate_interview_questions(
            mode=interview_request.mode,
            target_role=target_role,
            resume_text=resume_text,
            job_description=job_description,
            projects=projects,
        )
    except RuntimeError as e:
        if "GEMINI_API_KEY" in str(e):
            raise HTTPException(status_code=503, detail="AI service unavailable: API key not configured.")
        if "timeout" in str(e).lower():
            raise HTTPException(status_code=504, detail="AI request timed out.")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Question generation failed: {safe_error_detail(e)}")

    # Create session
    questions_json = [q.model_dump() for q in questions]
    try:
        session = create_interview_session(
            access_token=credentials.credentials,
            user_id=user_id,
            mode=interview_request.mode,
            target_role=target_role,
            resume_id=str(interview_request.resume_id) if interview_request.resume_id else None,
            questions=questions_json,
        )
    except DatabaseRequestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        print("CREATE SESSION ERROR:", type(e).__name__, safe_error_detail(e))
        raise HTTPException(status_code=500, detail="Unable to create interview session.")

    return InterviewSessionResponse(
        id=UUID(session["id"]),
        mode=session["mode"],
        target_role=session.get("target_role"),
        resume_id=UUID(session["resume_id"]) if session.get("resume_id") else None,
        questions=questions,
        status=session["status"],
        created_at=session["created_at"],
    )


@app.post("/interview/{session_id}/answer")
@limiter.limit("10/minute")
async def interview_answer(
    request: Request,
    session_id: UUID,
    answer_request: InterviewAnswerRequest,
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = claims["sub"]

    # Validate answer count will be checked in RPC, but we can pre-validate
    if not answer_request.answers:
        raise HTTPException(status_code=400, detail="At least one answer is required.")

    # We need the session data to build the evaluation prompt
    # Fetch session first
    try:
        session_resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/interview_sessions",
            headers={
                "apikey": SUPABASE_PUBLISHABLE_KEY,
                "Authorization": f"Bearer {credentials.credentials}",
            },
            params={
                "id": f"eq.{session_id}",
                "user_id": f"eq.{user_id}",
                "select": "id,mode,target_role,resume_id,questions,status",
            },
            timeout=10,
        )
        if not session_resp.ok:
            raise HTTPException(status_code=500, detail="Unable to load session.")

        sessions = session_resp.json()
        if not sessions:
            raise HTTPException(status_code=404, detail="Session not found.")

        session = sessions[0]
    except HTTPException:
        raise
    except Exception as e:
        print("LOAD SESSION ERROR:", type(e).__name__, safe_error_detail(e))
        raise HTTPException(status_code=500, detail="Unable to load session.")

    if session["status"] != "pending":
        raise HTTPException(status_code=400, detail="Session already completed.")

    questions = session["questions"]
    if len(answer_request.answers) != len(questions):
        raise HTTPException(status_code=400, detail="Answer count must match question count.")

    # Get context for evaluation
    target_role = session.get("target_role")
    resume_text = ""
    if session.get("resume_id"):
        resume = get_resume(credentials.credentials, user_id, str(session["resume_id"]))
        if resume:
            resume_text = resume.get("plain_text", "")

    job_description = f"Role: {target_role or 'Software Engineer'}. " \
        "We are looking for a candidate with strong technical skills, " \
        "problem-solving ability, and relevant project experience."

    projects = []
    if session.get("resume_id"):
        resume = get_resume(credentials.credentials, user_id, str(session["resume_id"]))
        if resume:
            content = resume.get("content", {})
            resume_projects = content.get("projects", [])
            for p in resume_projects[:3]:
                if isinstance(p, dict):
                    projects.append({
                        "name": p.get("name", ""),
                        "description": p.get("description", "")[:500]
                    })

    # Evaluate answers
    try:
        feedback = await evaluate_interview_answers(
            mode=session["mode"],
            target_role=target_role,
            resume_text=resume_text,
            job_description=job_description,
            projects=projects,
            questions=[InterviewQuestion(**q) for q in questions],
            answers=answer_request.answers,
        )
    except RuntimeError as e:
        if "GEMINI_API_KEY" in str(e):
            raise HTTPException(status_code=503, detail="AI service unavailable: API key not configured.")
        if "timeout" in str(e).lower():
            raise HTTPException(status_code=504, detail="AI request timed out.")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Feedback generation failed: {safe_error_detail(e)}")

    # Persist answers and feedback
    try:
        updated_session = submit_interview_answers(
            user_id=user_id,
            session_id=str(session_id),
            answers=answer_request.answers,
            score=feedback["score"],
            feedback={k: CategoryFeedback(**v).model_dump() for k, v in feedback["feedback"].items()},
            weak_areas=feedback["weak_areas"],
            recommendations=[Recommendation(**r).model_dump() for r in feedback["recommendations"]],
        )
    except DatabaseRequestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        print("SUBMIT ANSWERS ERROR:", type(e).__name__, safe_error_detail(e))
        raise HTTPException(status_code=500, detail="Unable to submit interview answers.")

    # Build complete response with session_id and completed_at from database
    return InterviewFeedbackResponse(
        session_id=UUID(updated_session["id"]),
        score=feedback["score"],
        feedback={k: CategoryFeedback(**v) for k, v in feedback["feedback"].items()},
        weak_areas=feedback["weak_areas"],
        recommendations=[Recommendation(**r) for r in feedback["recommendations"]],
        completed_at=updated_session["completed_at"],
    )


@app.get("/interview/history")
def interview_history(
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    limit: int = 20,
    offset: int = 0,
):
    user_id = claims["sub"]

    try:
        history = get_interview_history(
            access_token=credentials.credentials,
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
    except DatabaseRequestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        print("HISTORY ERROR:", type(e).__name__, safe_error_detail(e))
        raise HTTPException(status_code=500, detail="Unable to load interview history.")

    return [InterviewHistoryItem(**item) for item in history]


@app.delete("/interview/{session_id}", status_code=204)
@limiter.limit("10/minute")
def interview_delete(
    request: Request,
    session_id: UUID,
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user_id = claims["sub"]

    try:
        delete_interview_session(
            access_token=credentials.credentials,
            user_id=user_id,
            session_id=str(session_id),
        )
    except DatabaseRequestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        print("DELETE SESSION ERROR:", type(e).__name__, safe_error_detail(e))
        raise HTTPException(status_code=500, detail="Unable to delete interview session.")

    return Response(status_code=204)


@app.get("/interview/{session_id}")
@limiter.limit("30/minute")
def interview_get_session(
    request: Request,
    session_id: UUID,
    claims: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get a single interview session by ID for review."""
    user_id = claims["sub"]

    try:
        session = get_interview_session(
            access_token=credentials.credentials,
            user_id=user_id,
            session_id=str(session_id),
        )
    except DatabaseRequestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    except Exception as e:
        print("GET SESSION ERROR:", type(e).__name__, safe_error_detail(e))
        raise HTTPException(status_code=500, detail="Unable to load interview session.")

    if session is None:
        raise HTTPException(status_code=404, detail="Interview session not found.")

    return InterviewSessionResponse(**session)


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
            user_id=claims["sub"],
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