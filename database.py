import os
import logging

import requests
from dotenv import load_dotenv
from supabase import create_client


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv(
    "SUPABASE_PUBLISHABLE_KEY"
)
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Logger for database errors (redacted, no secrets)
_db_logger = logging.getLogger("database")

RESUMES_TABLE = "resumes"

RESUME_LIST_COLUMNS = (
    "id,title,is_default,created_at,updated_at"
)

RESUME_COLUMNS = (
    "id,title,content,plain_text,is_default,"
    "created_at,updated_at"
)

DEFAULT_RESUME_LIMIT = 50
MAX_RESUME_LIMIT = 100


class DatabaseRequestError(Exception):
    """A Supabase request failed in a way the API must report."""

    def __init__(
        self,
        message,
        status_code=500,
    ):
        super().__init__(message)

        self.status_code = status_code
        self.detail = message


def _resumes_headers(
    access_token,
    prefer=None,
):
    """Build request headers for the caller's Supabase session.

    The access token is the end user's own token, so PostgREST applies
    RLS on every request. The service key is never used for resume
    data, which keeps the database policies meaningful.
    """

    headers = {
        "apikey": SUPABASE_PUBLISHABLE_KEY,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    if prefer:
        headers["Prefer"] = prefer

    return headers


def _resumes_url():
    return f"{SUPABASE_URL}/rest/v1/{RESUMES_TABLE}"


def _owned_params(
    user_id,
    resume_id=None,
    select=None,
):
    """Build PostgREST filters that always scope to one user.

    Ownership is also enforced by RLS. This filter keeps the intent
    explicit in the request and avoids relying on RLS alone.
    """

    params = {
        "user_id": f"eq.{user_id}",
    }

    if resume_id:
        params["id"] = f"eq.{resume_id}"

    if select:
        params["select"] = select

    return params


def _postgrest_error_code(
    response,
) -> str:
    """Extract the SQLSTATE PostgREST reported, if any.

    Also recognizes PostgREST-specific error codes like PGRST202
    (function not found) and PGRST203 (function call failed).
    """

    try:
        body = response.json()
    except Exception:
        return ""

    if isinstance(body, dict):

        code = body.get("code")

        if isinstance(code, str):

            return code

    return ""


def _raise_for_database_response(
    response,
    fallback_message,
):
    """Convert a failed Supabase response into a typed error.

    PostgREST surfaces the SQLSTATE in the JSON `code` field. The
    functions in the resume migration raise P0002 for a missing or
    unowned resume, 42501 for a caller/owner mismatch, and the partial
    unique index raises 23505 when a default conflicts. Each maps to a
    specific API status so callers get an accurate answer.

    PostgREST-specific codes:
    - PGRST202: Missing RPC function (500, logged server-side)
    - PGRST203: Function call failed (500, logged server-side)
    """

    if response.ok:

        return

    code = _postgrest_error_code(response)

    if code == "PGRST202":
        _db_logger.error(
            "PostgREST missing RPC function: status=%s code=%s",
            response.status_code,
            code,
        )
        raise DatabaseRequestError(
            "Database function unavailable.",
            status_code=500,
        )

    if code == "P0002" or response.status_code == 404:
        raise DatabaseRequestError(
            "Resume not found.",
            status_code=404,
        )

    if code == "42501" or response.status_code in (401, 403):
        raise DatabaseRequestError(
            "Not authorized for this resume.",
            status_code=403,
        )

    if code == "23505" or response.status_code == 409:
        raise DatabaseRequestError(
            "Another resume is already the default. "
            "Please try again.",
            status_code=409,
        )

    if code == "PGRST203":
        _db_logger.error(
            "PostgREST function call failed: status=%s code=%s",
            response.status_code,
            code,
        )
        raise DatabaseRequestError(
            fallback_message,
            status_code=500,
        )

    if 500 <= response.status_code < 600:
        _db_logger.error(
            "Database error: status=%s code=%s",
            response.status_code,
            code or "unknown",
        )

    raise DatabaseRequestError(
        fallback_message,
        status_code=(
            response.status_code
            if 400 <= response.status_code < 500
            else 500
        ),
    )


def _call_resume_function(
    access_token,
    function_name,
    payload,
    fallback_message,
):
    """Call one resume RPC and return the row it produced.

    Ownership is derived from the caller's token inside the function.
    caller_id is still sent so the function can verify the token
    belongs to that user; it is never trusted on its own.

    PostgREST RPC returns a single object when the function returns
    one row, or a list when it returns SETOF. Both shapes are handled.
    """

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/{function_name}",
        headers=_resumes_headers(access_token),
        json=payload,
        timeout=10,
    )

    _raise_for_database_response(
        response,
        fallback_message,
    )

    data = response.json()

    if data is None:
        raise DatabaseRequestError(fallback_message)

    if isinstance(data, list):
        if not data:
            raise DatabaseRequestError(fallback_message)
        return data[0]

    if isinstance(data, dict):
        return data

    raise DatabaseRequestError(fallback_message)


def list_resumes(
    access_token,
    user_id,
    limit=None,
):
    """Return the caller's resume summaries, newest first.

    Args:
        access_token: The caller's Supabase access token.
        user_id: The caller's user ID (from verified token claims).
        limit: Maximum number of resumes to return (default 50, max 100).
    """

    if limit is None:
        limit = DEFAULT_RESUME_LIMIT
    else:
        limit = min(max(1, limit), MAX_RESUME_LIMIT)

    response = requests.get(
        _resumes_url(),
        headers=_resumes_headers(access_token),
        params={
            **_owned_params(
                user_id,
                select=RESUME_LIST_COLUMNS,
            ),
            "order": "updated_at.desc",
            "limit": str(limit),
        },
        timeout=10,
    )

    _raise_for_database_response(
        response,
        "Unable to load resumes.",
    )

    return response.json()


def get_resume(
    access_token,
    user_id,
    resume_id,
):
    """Return one resume owned by the caller, or None when missing."""

    response = requests.get(
        _resumes_url(),
        headers=_resumes_headers(access_token),
        params=_owned_params(
            user_id,
            resume_id=resume_id,
            select=RESUME_COLUMNS,
        ),
        timeout=10,
    )

    _raise_for_database_response(
        response,
        "Unable to load the resume.",
    )

    rows = response.json()

    if not rows:
        return None

    return rows[0]


def create_resume(
    access_token,
    user_id,
    title,
    content,
    plain_text,
    is_default=False,
):
    """Insert a resume and optionally make it the default.

    The insert and the default switch run inside one database
    transaction, so a failed default switch leaves no resume behind and
    can never collide with the partial unique index.
    """

    return _call_resume_function(
        access_token,
        "create_resume",
        {
            "caller_id": user_id,
            "resume_title": title,
            "resume_content": content,
            "resume_plain_text": plain_text,
            "make_default": bool(is_default),
        },
        "Unable to save the resume.",
    )


def update_resume(
    access_token,
    user_id,
    resume_id,
    title,
    content,
    plain_text,
    is_default=False,
):
    """Update an owned resume and optionally switch the default.

    The content update and the default switch share one transaction, so
    a failed switch rolls the content change back as well.
    """

    return _call_resume_function(
        access_token,
        "update_resume",
        {
            "caller_id": user_id,
            "resume_id": resume_id,
            "resume_title": title,
            "resume_content": content,
            "resume_plain_text": plain_text,
            "make_default": bool(is_default),
        },
        "Unable to update the resume.",
    )


def set_default_resume(
    access_token,
    user_id,
    resume_id,
):
    """Make one resume the caller's default, atomically.

    The database function verifies the target exists and is owned
    before it clears the previous default, and holds a per-user
    advisory lock so concurrent switches serialize.
    """

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/set_default_resume",
        headers=_resumes_headers(access_token),
        json={
            "caller_id": user_id,
            "resume_id": resume_id,
        },
        timeout=10,
    )

    _raise_for_database_response(
        response,
        "Unable to set the default resume.",
    )


def delete_resume(
    access_token,
    user_id,
    resume_id,
):
    """Delete one resume owned by the caller.

    A PostgREST delete that matches no rows still returns 200, so the
    deleted id is requested back and a zero-row result is reported as
    a missing resume instead of a silent success.
    """

    response = requests.delete(
        _resumes_url(),
        headers=_resumes_headers(
            access_token,
            prefer="return=representation",
        ),
        params={
            **_owned_params(
                user_id,
                resume_id=resume_id,
            ),
            "select": "id",
        },
        timeout=10,
    )

    _raise_for_database_response(
        response,
        "Unable to delete the resume.",
    )

    rows = response.json()

    if not rows:
        raise DatabaseRequestError(
            "Resume not found.",
            status_code=404,
        )


def save_analysis(
    access_token,
    user_id,
    resume,
    job_description,
    projects,
    analysis,
):
    """Persist one analysis for the caller.

    Raises DatabaseRequestError on an HTTP error response so a failed
    save is observable by the caller instead of being silently
    discarded.
    """
    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/career_analyses",
        headers={
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json={
            "user_id": user_id,
            "resume_text": resume,
            "job_description": job_description,
            "projects": projects,
            "analysis": analysis,
        },
        timeout=10,
    )

    _raise_for_database_response(
        response,
        "Unable to save the analysis.",
    )

def get_analysis_history(
    access_token,
    user_id,
):
    """Return the caller's own saved analyses, newest first.

    The user_id filter mirrors _owned_params for resumes and
    interview_sessions: ownership is also enforced by RLS, but the
    filter keeps the intent explicit in the request.
    """

    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/career_analyses",
        headers={
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Authorization": f"Bearer {access_token}",
        },
        params={
            "user_id": f"eq.{user_id}",
            "select": "id,job_description,analysis,created_at",
            "order": "created_at.desc",
        },
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


def _call_interview_function(
    access_token,
    function_name,
    payload,
    fallback_message,
):
    """Call one interview RPC and return the row it produced.

    Ownership is derived from the caller's token inside the function.
    caller_id is sent so the function can verify the token belongs to that user.
    """

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/{function_name}",
        headers=_resumes_headers(access_token),
        json=payload,
        timeout=10,
    )

    _raise_for_database_response(
        response,
        fallback_message,
    )

    data = response.json()

    if data is None:
        raise DatabaseRequestError(fallback_message)

    if isinstance(data, list):
        if not data:
            raise DatabaseRequestError(fallback_message)
        return data[0]

    if isinstance(data, dict):
        return data

    raise DatabaseRequestError(fallback_message)


def _get_service_role_token():
    """Return a service role access token, or raise if not configured.

    Uses the SUPABASE_SERVICE_KEY to authenticate as the service role.
    This token bypasses RLS and is only used for privileged RPC calls
    that the backend makes on behalf of authenticated users.
    """
    if not SUPABASE_SERVICE_KEY:
        raise DatabaseRequestError(
            "Server configuration error: SUPABASE_SERVICE_KEY not set. "
            "Interview answer submission requires a service role key.",
            status_code=503,
        )

    # Use the service key to get an access token via Supabase admin API
    # The service key itself can be used as the access token for PostgREST
    # when using the service role (it acts as both apikey and bearer token)
    return SUPABASE_SERVICE_KEY


def _call_privileged_interview_function(
    function_name,
    payload,
    fallback_message,
):
    """Call an interview RPC with service role privileges.

    This bypasses RLS and is only used for submit_interview_answers
    which writes evaluation fields that users must not modify directly.
    The function validates the caller_id against the session ownership.
    """
    token = _get_service_role_token()

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/{function_name}",
        headers={
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=10,
    )

    _raise_for_database_response(
        response,
        fallback_message,
    )

    data = response.json()

    if data is None:
        raise DatabaseRequestError(fallback_message)

    if isinstance(data, list):
        if not data:
            raise DatabaseRequestError(fallback_message)
        return data[0]

    if isinstance(data, dict):
        return data

    raise DatabaseRequestError(fallback_message)


def create_interview_session(
    access_token,
    user_id,
    mode,
    target_role,
    resume_id,
    questions,
):
    return _call_interview_function(
        access_token,
        "create_interview_session",
        {
            "caller_id": user_id,
            "p_mode": mode,
            "p_target_role": target_role,
            "p_resume_id": str(resume_id) if resume_id else None,
            "p_questions": questions,
        },
        "Unable to create interview session.",
    )


def submit_interview_answers(
    user_id,
    session_id,
    answers,
    score,
    feedback,
    weak_areas,
    recommendations,
):
    """Submit interview answers using privileged service role.

    The access_token parameter is no longer used; this function now uses
    the service role key which must be configured in the environment.
    Raises DatabaseRequestError(503) if SUPABASE_SERVICE_KEY is not set.
    """
    return _call_privileged_interview_function(
        "submit_interview_answers",
        {
            "caller_id": user_id,
            "p_session_id": str(session_id),
            "p_answers": answers,
            "p_score": score,
            "p_feedback": feedback,
            "p_weak_areas": weak_areas,
            "p_recommendations": recommendations,
        },
        "Unable to submit interview answers.",
    )


def delete_interview_session(
    access_token,
    user_id,
    session_id,
):
    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/delete_interview_session",
        headers=_resumes_headers(access_token),
        json={"caller_id": user_id, "p_session_id": str(session_id)},
        timeout=10,
    )

    _raise_for_database_response(
        response,
        "Unable to delete interview session.",
    )


def get_interview_history(
    access_token,
    user_id,
    limit=20,
    offset=0,
):
    if limit is None:
        limit = 20
    else:
        limit = min(max(1, limit), 50)

    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/interview_sessions",
        headers=_resumes_headers(access_token),
        params={
            **_owned_params(
                user_id,
                select="id,mode,target_role,score,status,created_at,completed_at",
            ),
            "order": "created_at.desc",
            "limit": str(limit),
            "offset": str(offset),
        },
        timeout=10,
    )

    # Handle 404 specifically for interview_sessions table (may not exist yet)
    if response.status_code == 404:
        return []

    _raise_for_database_response(
        response,
        "Unable to load interview history.",
    )

    return response.json()


def get_interview_session(
    access_token,
    user_id,
    session_id,
):
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/interview_sessions",
        headers=_resumes_headers(access_token),
        params={
            **_owned_params(
                user_id,
                select="id,mode,target_role,resume_id,questions,answers,feedback,score,weak_areas,recommendations,status,created_at,completed_at",
            ),
            "id": f"eq.{session_id}",
        },
        timeout=10,
    )

    if response.status_code == 404:
        return None

    _raise_for_database_response(
        response,
        "Unable to load interview session.",
    )

    data = response.json()
    return data[0] if data else None


def delete_analysis(
    access_token,
    user_id,
    analysis_id,
):
    """Delete one of the caller's own analyses by id.

    Both the user_id and id filters scope the delete, mirroring
    _owned_params for resumes and interview_sessions: ownership is
    also enforced by RLS, but the filters keep the intent explicit.
    """

    response = requests.delete(
        f"{SUPABASE_URL}/rest/v1/career_analyses",
        headers={
            "apikey": SUPABASE_PUBLISHABLE_KEY,
            "Authorization": f"Bearer {access_token}",
        },
        params={
            "user_id": f"eq.{user_id}",
            "id": f"eq.{analysis_id}",
        },
        timeout=10,
    )

    response.raise_for_status()

