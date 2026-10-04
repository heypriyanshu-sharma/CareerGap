"""Store level tests for the Supabase resume client.

No request ever leaves the process: the requests module is replaced with
a recorder, so ownership scoping, the caller's access token, the RPC
payloads and the PostgREST error mapping are verified directly.
"""

import inspect

import pytest

import database
from database import DatabaseRequestError


USER_ID = "11111111-1111-1111-1111-111111111111"

OTHER_USER_ID = "22222222-2222-2222-2222-222222222222"

RESUME_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

ACCESS_TOKEN = "caller-access-token"

SUPABASE_URL = "https://project.supabase.co"

PUBLISHABLE_KEY = "sb_publishable_test"


class FakeResponse:
    def __init__(
        self,
        status_code=200,
        payload=None,
    ):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self._payload = [] if payload is None else payload

    def json(self):
        return self._payload


class FakeRequests:
    """Record every call and replay one queued response."""

    def __init__(self):
        self.calls = []
        self.response = FakeResponse()

    def reply(
        self,
        status_code=200,
        payload=None,
    ):
        self.response = FakeResponse(
            status_code=status_code,
            payload=payload,
        )

        return self

    def _record(self, method, url, **kwargs):
        self.calls.append(
            {
                "method": method,
                "url": url,
                **kwargs,
            }
        )

        return self.response

    def get(self, url, **kwargs):
        return self._record("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._record("POST", url, **kwargs)

    def delete(self, url, **kwargs):
        return self._record("DELETE", url, **kwargs)


@pytest.fixture
def http(monkeypatch):
    fake = FakeRequests()

    monkeypatch.setattr(database, "requests", fake)
    monkeypatch.setattr(
        database,
        "SUPABASE_URL",
        SUPABASE_URL,
    )
    monkeypatch.setattr(
        database,
        "SUPABASE_PUBLISHABLE_KEY",
        PUBLISHABLE_KEY,
    )

    return fake


def only_call(http):
    assert len(http.calls) == 1

    return http.calls[0]


# ============================================================
# OWNERSHIP SCOPING
# ============================================================

def test_list_resumes_scopes_to_the_caller(http):
    http.reply(
        payload=[
            {"id": RESUME_ID},
        ],
    )

    database.list_resumes(ACCESS_TOKEN, USER_ID)

    call = only_call(http)

    assert call["method"] == "GET"
    assert call["url"] == (
        f"{SUPABASE_URL}/rest/v1/resumes"
    )
    assert call["params"]["user_id"] == f"eq.{USER_ID}"
    assert call["params"]["order"] == "updated_at.desc"
    assert call["params"]["select"] == database.RESUME_LIST_COLUMNS


def test_list_resumes_never_queries_another_user(http):
    """The user filter is always built from the supplied owner."""

    database.list_resumes(ACCESS_TOKEN, OTHER_USER_ID)

    params = only_call(http)["params"]

    assert params["user_id"] == f"eq.{OTHER_USER_ID}"
    assert USER_ID not in params["user_id"]


def test_get_resume_scopes_to_caller_and_resume(http):
    http.reply(
        payload=[
            {"id": RESUME_ID},
        ],
    )

    database.get_resume(
        ACCESS_TOKEN,
        USER_ID,
        RESUME_ID,
    )

    call = only_call(http)

    assert call["params"]["user_id"] == f"eq.{USER_ID}"
    assert call["params"]["id"] == f"eq.{RESUME_ID}"
    assert call["params"]["select"] == database.RESUME_COLUMNS


def test_get_resume_returns_none_when_no_row_matches(http):
    http.reply(payload=[])

    assert database.get_resume(
        ACCESS_TOKEN,
        USER_ID,
        RESUME_ID,
    ) is None


def test_get_resume_returns_the_row(http):
    http.reply(
        payload=[
            {"id": RESUME_ID, "title": "Mine"},
        ],
    )

    resume = database.get_resume(
        ACCESS_TOKEN,
        USER_ID,
        RESUME_ID,
    )

    assert resume["title"] == "Mine"


def test_delete_resume_scopes_to_caller_and_resume(http):
    http.reply(
        payload=[
            {"id": RESUME_ID},
        ],
    )

    database.delete_resume(
        ACCESS_TOKEN,
        USER_ID,
        RESUME_ID,
    )

    call = only_call(http)

    assert call["method"] == "DELETE"
    assert call["params"]["user_id"] == f"eq.{USER_ID}"
    assert call["params"]["id"] == f"eq.{RESUME_ID}"
    assert call["params"]["select"] == "id"


def test_delete_resume_returns_when_the_row_was_removed(http):
    http.reply(
        payload=[
            {"id": RESUME_ID},
        ],
    )

    assert database.delete_resume(
        ACCESS_TOKEN,
        USER_ID,
        RESUME_ID,
    ) is None


# ============================================================
# ACCESS TOKEN
# ============================================================

def test_every_request_forwards_the_callers_token(http):
    """The end user's own token is sent so RLS stays effective."""

    for call in (
        lambda: database.list_resumes(
            ACCESS_TOKEN,
            USER_ID,
        ),
        lambda: database.get_resume(
            ACCESS_TOKEN,
            USER_ID,
            RESUME_ID,
        ),
        lambda: database.create_resume(
            ACCESS_TOKEN,
            USER_ID,
            "CV",
            {},
            "text",
        ),
        lambda: database.update_resume(
            ACCESS_TOKEN,
            USER_ID,
            RESUME_ID,
            "CV",
            {},
            "text",
        ),
        lambda: database.set_default_resume(
            ACCESS_TOKEN,
            USER_ID,
            RESUME_ID,
        ),
        lambda: database.delete_resume(
            ACCESS_TOKEN,
            USER_ID,
            RESUME_ID,
        ),
    ):
        http.calls.clear()
        http.reply(
            payload=[
                {"id": RESUME_ID},
            ],
        )

        call()

        headers = only_call(http)["headers"]

        assert headers["Authorization"] == (
            f"Bearer {ACCESS_TOKEN}"
        )
        assert headers["apikey"] == PUBLISHABLE_KEY

        # The publishable key is never used as the bearer token.
        assert headers["Authorization"] != (
            f"Bearer {PUBLISHABLE_KEY}"
        )


def test_resume_store_never_reads_a_service_role_key():
    """RLS is only meaningful if resume data skips the service key."""

    source = inspect.getsource(database)

    assert "SERVICE_ROLE" not in source


# ============================================================
# RPC PAYLOADS
# ============================================================

def test_create_resume_calls_the_transactional_function(http):
    http.reply(
        payload=[
            {
                "id": RESUME_ID,
                "is_default": True,
            },
        ],
    )

    row = database.create_resume(
        ACCESS_TOKEN,
        USER_ID,
        "Backend CV",
        {"summary": "text"},
        "plain",
        is_default=True,
    )

    call = only_call(http)

    assert call["method"] == "POST"
    assert call["url"] == (
        f"{SUPABASE_URL}/rest/v1/rpc/create_resume"
    )
    assert call["json"] == {
        "caller_id": USER_ID,
        "resume_title": "Backend CV",
        "resume_content": {"summary": "text"},
        "resume_plain_text": "plain",
        "make_default": True,
    }
    assert row["id"] == RESUME_ID


def test_create_resume_defaults_to_not_default(http):
    http.reply(
        payload=[
            {"id": RESUME_ID},
        ],
    )

    database.create_resume(
        ACCESS_TOKEN,
        USER_ID,
        "CV",
        {},
        "plain",
    )

    assert only_call(http)["json"]["make_default"] is False


def test_create_resume_coerces_truthy_default_flag(http):
    http.reply(
        payload=[
            {"id": RESUME_ID},
        ],
    )

    database.create_resume(
        ACCESS_TOKEN,
        USER_ID,
        "CV",
        {},
        "plain",
        is_default=1,
    )

    assert only_call(http)["json"]["make_default"] is True


def test_update_resume_sends_the_target_id_and_flag(http):
    http.reply(
        payload=[
            {"id": RESUME_ID},
        ],
    )

    database.update_resume(
        ACCESS_TOKEN,
        USER_ID,
        RESUME_ID,
        "Updated",
        {"summary": "text"},
        "plain",
        is_default=True,
    )

    call = only_call(http)

    assert call["url"] == (
        f"{SUPABASE_URL}/rest/v1/rpc/update_resume"
    )
    assert call["json"] == {
        "caller_id": USER_ID,
        "resume_id": RESUME_ID,
        "resume_title": "Updated",
        "resume_content": {"summary": "text"},
        "resume_plain_text": "plain",
        "make_default": True,
    }


def test_set_default_resume_sends_only_the_ids(http):
    database.set_default_resume(
        ACCESS_TOKEN,
        USER_ID,
        RESUME_ID,
    )

    call = only_call(http)

    assert call["method"] == "POST"
    assert call["url"] == (
        f"{SUPABASE_URL}/rest/v1/rpc/set_default_resume"
    )
    assert call["json"] == {
        "caller_id": USER_ID,
        "resume_id": RESUME_ID,
    }


def test_rpc_calls_send_a_timeout(http):
    """A stalled database must not hang the API worker."""

    http.reply(
        payload=[
            {"id": RESUME_ID},
        ],
    )

    database.create_resume(
        ACCESS_TOKEN,
        USER_ID,
        "CV",
        {},
        "plain",
    )

    assert only_call(http)["timeout"] == 10


def test_create_resume_rejects_an_empty_result(http):
    """No returned row is a failure, not a silent empty record."""

    http.reply(payload=[])

    with pytest.raises(DatabaseRequestError) as error:
        database.create_resume(
            ACCESS_TOKEN,
            USER_ID,
            "CV",
            {},
            "plain",
        )

    assert error.value.status_code == 500
    assert (
        error.value.detail == "Unable to save the resume."
    )


# ============================================================
# ERROR MAPPING
# ============================================================

@pytest.mark.parametrize(
    "status_code,code",
    [
        (400, "P0002"),
        (404, None),
    ],
)
def test_missing_or_unowned_resume_maps_to_404(
    http,
    status_code,
    code,
):
    http.reply(
        status_code=status_code,
        payload={"code": code} if code else {},
    )

    with pytest.raises(DatabaseRequestError) as error:
        database.update_resume(
            ACCESS_TOKEN,
            USER_ID,
            RESUME_ID,
            "CV",
            {},
            "plain",
        )

    assert error.value.status_code == 404
    assert error.value.detail == "Resume not found."


@pytest.mark.parametrize(
    "status_code,code",
    [
        (400, "42501"),
        (401, None),
        (403, None),
    ],
)
def test_authorization_failure_maps_to_403(
    http,
    status_code,
    code,
):
    http.reply(
        status_code=status_code,
        payload={"code": code} if code else {},
    )

    with pytest.raises(DatabaseRequestError) as error:
        database.delete_resume(
            ACCESS_TOKEN,
            USER_ID,
            RESUME_ID,
        )

    assert error.value.status_code == 403
    assert (
        error.value.detail
        == "Not authorized for this resume."
    )


@pytest.mark.parametrize(
    "status_code,code",
    [
        (409, "23505"),
        (409, None),
    ],
)
def test_default_conflict_maps_to_409(
    http,
    status_code,
    code,
):
    http.reply(
        status_code=status_code,
        payload={"code": code} if code else {},
    )

    with pytest.raises(DatabaseRequestError) as error:
        database.set_default_resume(
            ACCESS_TOKEN,
            USER_ID,
            RESUME_ID,
        )

    assert error.value.status_code == 409
    assert error.value.detail == (
        "Another resume is already the default. "
        "Please try again."
    )


@pytest.mark.parametrize(
    "status_code",
    [400, 413, 422, 429],
)
def test_other_client_errors_keep_their_status(
    http,
    status_code,
):
    http.reply(
        status_code=status_code,
        payload={"code": "42601"},
    )

    with pytest.raises(DatabaseRequestError) as error:
        database.list_resumes(
            ACCESS_TOKEN,
            USER_ID,
        )

    assert error.value.status_code == status_code
    assert (
        error.value.detail == "Unable to load resumes."
    )


@pytest.mark.parametrize(
    "status_code",
    [500, 502, 503],
)
def test_server_errors_map_to_500(
    http,
    status_code,
):
    http.reply(
        status_code=status_code,
        payload={"code": "08006"},
    )

    with pytest.raises(DatabaseRequestError) as error:
        database.get_resume(
            ACCESS_TOKEN,
            USER_ID,
            RESUME_ID,
        )

    assert error.value.status_code == 500
    assert (
        error.value.detail == "Unable to load the resume."
    )


def test_unparsable_error_body_uses_the_fallback(http):
    class BrokenResponse:
        status_code = 500
        ok = False

        def json(self):
            raise ValueError("not json")

    http.response = BrokenResponse()

    with pytest.raises(DatabaseRequestError) as error:
        database.delete_resume(
            ACCESS_TOKEN,
            USER_ID,
            RESUME_ID,
        )

    assert error.value.status_code == 500
    assert (
        error.value.detail == "Unable to delete the resume."
    )


def test_delete_resume_reports_zero_rows_as_missing(http):
    """PostgREST answers 200 for a delete that matched nothing."""

    http.reply(payload=[])

    with pytest.raises(DatabaseRequestError) as error:
        database.delete_resume(
            ACCESS_TOKEN,
            USER_ID,
            RESUME_ID,
        )

    assert error.value.status_code == 404
    assert error.value.detail == "Resume not found."


def test_successful_request_does_not_raise(http):
    http.reply(
        payload=[
            {"id": RESUME_ID},
        ],
    )

    assert database.delete_resume(
        ACCESS_TOKEN,
        USER_ID,
        RESUME_ID,
    ) is None
