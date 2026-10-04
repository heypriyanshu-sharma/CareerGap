"""Tests for the authenticated resume CRUD API.

The Supabase store is replaced with an in-memory fake that mirrors the
transactional behaviour of the database functions, so these tests
cover authorization, ownership scoping, validation, request limits and
error mapping without a database.
"""

import os

from fastapi.security import HTTPAuthorizationCredentials
import pytest

# Only a missing configuration may skip this module. Any other import
# problem is a real application error and must fail the suite loudly.
if not (
    os.getenv("SUPABASE_URL")
    and os.getenv("SUPABASE_PUBLISHABLE_KEY")
):
    pytest.skip(
        "Supabase environment variables are not set, so the "
        "application cannot be imported.",
        allow_module_level=True,
    )

import backend
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from database import DatabaseRequestError


client = TestClient(backend.app)

USER_ID = "11111111-1111-1111-1111-111111111111"

OTHER_USER_ID = "22222222-2222-2222-2222-222222222222"

RESUME_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


VALID_CONTENT = {
    "contact": {
        "full_name": "Ada Lovelace",
        "email": "ada@example.com",
    },
    "summary": "Backend engineer.",
    "sections": [
        {
            "type": "skills",
            "heading": "Skills",
            "items": ["Python"],
        }
    ],
}


class FakeStore:
    """In-memory stand-in for the Supabase resume helpers.

    Mirrors the transactional database functions: a resume is inserted
    or updated first and the default switch happens afterwards, so a
    failed switch rolls the whole change back.
    """

    def __init__(self):
        self.rows = {}
        self.calls = []
        self.list_error = None
        self.get_error = None
        self.create_error = None
        self.update_error = None
        self.delete_error = None
        self.switch_error = None

    # -- helpers ---------------------------------------------------------

    def _own(self, user_id, resume_id):
        row = self.rows.get(resume_id)

        if row is None or row["user_id"] != user_id:
            return None

        return dict(row)

    def seed(self, resume_id, user_id, **overrides):
        row = {
            "id": resume_id,
            "user_id": user_id,
            "title": "Seed resume",
            "content": VALID_CONTENT,
            "plain_text": "seed",
            "is_default": False,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
        }
        row.update(overrides)

        self.rows[resume_id] = row

        return row

    def _switch_default(self, user_id, resume_id):
        if self.switch_error:
            raise self.switch_error

        row = self._own(user_id, resume_id)

        if row is None:
            raise DatabaseRequestError(
                "Resume not found.",
                status_code=404,
            )

        for other in self.rows.values():
            if other["user_id"] == user_id:
                other["is_default"] = False

        self.rows[resume_id]["is_default"] = True

    # -- database surface ------------------------------------------------

    def list_resumes(self, access_token, user_id, limit=None):
        self.calls.append(("list", user_id))

        if self.list_error:
            raise self.list_error

        return [
            {
                "id": row["id"],
                "title": row["title"],
                "is_default": row["is_default"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in self.rows.values()
            if row["user_id"] == user_id
        ]

    def get_resume(self, access_token, user_id, resume_id):
        self.calls.append(("get", user_id, resume_id))

        if self.get_error:
            raise self.get_error

        return self._own(user_id, resume_id)

    def create_resume(
        self,
        access_token,
        user_id,
        title,
        content,
        plain_text,
        is_default=False,
    ):
        self.calls.append(("create", user_id, title, is_default))

        if self.create_error:
            raise self.create_error

        resume_id = f"generated-{len(self.rows)}"

        # Mirrors create_resume(): the row is always inserted with
        # is_default false, then the switch runs in the same
        # transaction.
        row = self.seed(
            resume_id,
            user_id,
            title=title,
            content=content,
            plain_text=plain_text,
            is_default=False,
        )

        if is_default:

            try:
                self._switch_default(
                    user_id,
                    resume_id,
                )
            except Exception:
                # Transaction rolled back: nothing is left behind.
                del self.rows[resume_id]

                raise

        return dict(self.rows[resume_id])

    def update_resume(
        self,
        access_token,
        user_id,
        resume_id,
        title,
        content,
        plain_text,
        is_default=False,
    ):
        self.calls.append(
            ("update", user_id, resume_id, is_default)
        )

        if self.update_error:
            raise self.update_error

        row = self._own(user_id, resume_id)

        if row is None:
            raise DatabaseRequestError(
                "Resume not found.",
                status_code=404,
            )

        original = dict(row)

        row["title"] = title
        row["content"] = content
        row["plain_text"] = plain_text

        self.rows[resume_id] = row

        if is_default:

            try:
                self._switch_default(
                    user_id,
                    resume_id,
                )
            except Exception:
                # Transaction rolled back: the content change is undone.
                self.rows[resume_id] = original

                raise

        return dict(self.rows[resume_id])

    def set_default_resume(self, access_token, user_id, resume_id):
        self.calls.append(("default", user_id, resume_id))

        self._switch_default(user_id, resume_id)

    def delete_resume(self, access_token, user_id, resume_id):
        self.calls.append(("delete", user_id, resume_id))

        if self.delete_error:
            raise self.delete_error

        row = self._own(user_id, resume_id)

        if row is None:
            raise DatabaseRequestError(
                "Resume not found.",
                status_code=404,
            )

        del self.rows[resume_id]


@pytest.fixture
def store(monkeypatch):
    fake = FakeStore()

    monkeypatch.setattr(backend, "list_resumes", fake.list_resumes)
    monkeypatch.setattr(backend, "get_resume", fake.get_resume)
    monkeypatch.setattr(backend, "create_resume", fake.create_resume)
    monkeypatch.setattr(backend, "update_resume", fake.update_resume)
    monkeypatch.setattr(
        backend,
        "set_default_resume",
        fake.set_default_resume,
    )
    monkeypatch.setattr(backend, "delete_resume", fake.delete_resume)

    backend.app.dependency_overrides[
        backend.get_current_user
    ] = lambda: {
        "sub": USER_ID,
        "email": "ada@example.com",
    }

    backend.app.dependency_overrides[
        backend.security
    ] = lambda: HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="test-access-token",
    )

    backend.limiter._storage.reset()

    yield fake

    backend.app.dependency_overrides.pop(
        backend.get_current_user,
        None,
    )

    backend.app.dependency_overrides.pop(
        backend.security,
        None,
    )


# ============================================================
# CREATE
# ============================================================

def test_create_resume_returns_saved_record(store):
    response = client.post(
        "/resumes",
        json={
            "title": "Backend CV",
            "content": VALID_CONTENT,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["title"] == "Backend CV"
    assert body["user_id"] == USER_ID
    assert "Ada Lovelace" in body["plain_text"]


def test_create_resume_rejects_client_supplied_plain_text(store):
    response = client.post(
        "/resumes",
        json={
            "title": "CV",
            "content": VALID_CONTENT,
            "plain_text": "CLIENT CONTROLLED TEXT",
        },
    )

    # Unknown fields are rejected instead of ignored.
    assert response.status_code == 422


def test_create_resume_rejects_client_supplied_user_id(store):
    response = client.post(
        "/resumes",
        json={
            "title": "CV",
            "content": VALID_CONTENT,
            "user_id": OTHER_USER_ID,
        },
    )

    assert response.status_code == 422

    assert store.rows == {}


def test_create_resume_uses_claim_user_id(store):
    client.post(
        "/resumes",
        json={
            "title": "CV",
            "content": VALID_CONTENT,
        },
    )

    create_call = [
        call for call in store.calls
        if call[0] == "create"
    ][0]

    assert create_call[1] == USER_ID


def test_create_resume_normalizes_content(store):
    response = client.post(
        "/resumes",
        json={
            "title": "CV",
            "content": {
                "contact": {
                    "full_name": "  Ada  ",
                    "unknown": "dropped",
                },
                "sections": [
                    {
                        "type": "skills",
                        "items": ["Python", "  "],
                    }
                ],
            },
        },
    )

    assert response.status_code == 200

    stored = response.json()["content"]

    assert stored["contact"]["full_name"] == "Ada"
    assert "unknown" not in stored["contact"]
    assert stored["sections"][0]["items"] == ["Python"]


def test_create_resume_rejects_blank_title(store):
    response = client.post(
        "/resumes",
        json={
            "title": "   ",
            "content": VALID_CONTENT,
        },
    )

    assert response.status_code == 400


def test_create_resume_rejects_oversized_title(store):
    response = client.post(
        "/resumes",
        json={
            "title": "A" * 500,
            "content": VALID_CONTENT,
        },
    )

    assert response.status_code == 422


def test_create_resume_rejects_invalid_structure(store):
    response = client.post(
        "/resumes",
        json={
            "title": "CV",
            "content": {
                "sections": [
                    {"type": "unsupported"}
                ]
            },
        },
    )

    assert response.status_code == 400


def test_create_resume_rejects_structurally_oversized_content(store):
    oversized = {
        "sections": [
            {
                "type": "custom",
                "items": [
                    {
                        "title": f"Entry {index}",
                        "text": "B" * 4000,
                    }
                    for index in range(40)
                ],
            }
        ]
    }

    response = client.post(
        "/resumes",
        json={
            "title": "CV",
            "content": oversized,
        },
    )

    assert response.status_code == 400


def test_create_resume_maps_store_failure_to_status(store):
    store.create_error = DatabaseRequestError(
        "database offline",
        status_code=503,
    )

    response = client.post(
        "/resumes",
        json={
            "title": "CV",
            "content": VALID_CONTENT,
        },
    )

    assert response.status_code == 503


# ============================================================
# DEFAULT RESUME (transactional)
# ============================================================

def test_create_resume_as_default_when_one_already_exists(store):
    store.seed(
        "existing",
        USER_ID,
        is_default=True,
    )

    response = client.post(
        "/resumes",
        json={
            "title": "New default",
            "content": VALID_CONTENT,
            "is_default": True,
        },
    )

    assert response.status_code == 200

    created = response.json()

    assert created["is_default"] is True
    assert store.rows["existing"]["is_default"] is False
    assert store.rows[created["id"]]["is_default"] is True


def test_create_resume_leaves_nothing_when_default_switch_fails(store):
    store.switch_error = DatabaseRequestError(
        "Resume not found.",
        status_code=404,
    )

    response = client.post(
        "/resumes",
        json={
            "title": "Doomed CV",
            "content": VALID_CONTENT,
            "is_default": True,
        },
    )

    assert response.status_code == 404

    # The insert was rolled back with the failed switch.
    assert store.rows == {}


def test_create_resume_maps_default_conflict_to_409(store):
    store.switch_error = DatabaseRequestError(
        "Another resume is already the default. Please try again.",
        status_code=409,
    )

    response = client.post(
        "/resumes",
        json={
            "title": "CV",
            "content": VALID_CONTENT,
            "is_default": True,
        },
    )

    assert response.status_code == 409
    assert store.rows == {}


def test_create_resume_as_default_returns_the_store_record(store):
    """The API returns the stored row rather than rebuilding one.

    The database reloads the row after switching the default, so the
    refreshed is_default has to reach the client untouched. This guards
    the pass-through contract only; it cannot prove the reload itself.
    """

    store.seed(
        "existing",
        USER_ID,
        is_default=True,
    )

    response = client.post(
        "/resumes",
        json={
            "title": "New default",
            "content": VALID_CONTENT,
            "is_default": True,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["is_default"] is True
    assert body == store.rows[body["id"]]


# ============================================================
# LIST / READ
# ============================================================

def test_list_resumes_returns_only_owned_rows(store):
    store.seed("mine", USER_ID, title="Mine")
    store.seed("theirs", OTHER_USER_ID, title="Theirs")

    response = client.get("/resumes")

    assert response.status_code == 200

    body = response.json()

    assert [row["title"] for row in body] == ["Mine"]


def test_list_resumes_uses_claim_user_id(store):
    client.get("/resumes")

    assert store.calls[0] == ("list", USER_ID)


def test_list_resume_maps_store_failure(store):
    store.list_error = DatabaseRequestError(
        "Unable to load resumes.",
        status_code=500,
    )

    response = client.get("/resumes")

    assert response.status_code == 500


def test_get_resume_returns_record(store):
    store.seed(RESUME_ID, USER_ID)

    response = client.get(f"/resumes/{RESUME_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == RESUME_ID


def test_get_resume_hides_other_users_resume(store):
    store.seed(RESUME_ID, OTHER_USER_ID)

    response = client.get(f"/resumes/{RESUME_ID}")

    assert response.status_code == 404


def test_get_resume_returns_404_when_missing(store):
    response = client.get("/resumes/does-not-exist")

    # Not a UUID, so it never reaches the store.
    assert response.status_code == 422


def test_get_resume_returns_404_for_unknown_uuid(store):
    response = client.get(
        "/resumes/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    )

    assert response.status_code == 404


def test_get_resume_rejects_malformed_id(store):
    response = client.get("/resumes/not-a-uuid")

    assert response.status_code == 422

    assert store.calls == []


# ============================================================
# UPDATE
# ============================================================

def test_update_resume_saves_changes(store):
    store.seed(RESUME_ID, USER_ID)

    response = client.put(
        f"/resumes/{RESUME_ID}",
        json={
            "title": "Updated CV",
            "content": VALID_CONTENT,
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated CV"
    assert store.rows[RESUME_ID]["title"] == "Updated CV"


def test_update_resume_regenerates_plain_text(store):
    store.seed(RESUME_ID, USER_ID)

    client.put(
        f"/resumes/{RESUME_ID}",
        json={
            "title": "Updated CV",
            "content": {
                "contact": {"full_name": "Grace Hopper"},
                "summary": "Compiler pioneer.",
            },
        },
    )

    plain_text = store.rows[RESUME_ID]["plain_text"]

    assert "Grace Hopper" in plain_text
    assert "Compiler pioneer." in plain_text


def test_update_resume_cannot_touch_another_user(store):
    store.seed(RESUME_ID, OTHER_USER_ID)

    response = client.put(
        f"/resumes/{RESUME_ID}",
        json={
            "title": "Hijacked",
            "content": VALID_CONTENT,
        },
    )

    assert response.status_code == 404
    assert store.rows[RESUME_ID]["title"] == "Seed resume"


def test_update_resume_rejects_malformed_id(store):
    response = client.put(
        "/resumes/not-a-uuid",
        json={
            "title": "CV",
            "content": VALID_CONTENT,
        },
    )

    assert response.status_code == 422
    assert store.calls == []


def test_update_resume_can_set_default(store):
    store.seed("first", USER_ID, is_default=True)
    store.seed(RESUME_ID, USER_ID)

    response = client.put(
        f"/resumes/{RESUME_ID}",
        json={
            "title": "New default",
            "content": VALID_CONTENT,
            "is_default": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["is_default"] is True
    assert store.rows["first"]["is_default"] is False
    assert store.rows[RESUME_ID]["is_default"] is True


def test_update_resume_rolls_back_when_default_switch_fails(store):
    store.seed(RESUME_ID, USER_ID)
    store.switch_error = DatabaseRequestError(
        "Resume not found.",
        status_code=404,
    )

    response = client.put(
        f"/resumes/{RESUME_ID}",
        json={
            "title": "Should not stick",
            "content": VALID_CONTENT,
            "is_default": True,
        },
    )

    assert response.status_code == 404

    # The content update was rolled back with the failed switch.
    assert store.rows[RESUME_ID]["title"] == "Seed resume"


def test_update_resume_as_default_returns_the_store_record(store):
    """The refreshed record must not be rebuilt from local state.

    After the switch the database re-reads the row, so the response
    must be the store's own record, including is_default.
    """

    store.seed(RESUME_ID, USER_ID)

    response = client.put(
        f"/resumes/{RESUME_ID}",
        json={
            "title": "Updated default",
            "content": VALID_CONTENT,
            "is_default": True,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["is_default"] is True
    assert body == store.rows[RESUME_ID]


def test_update_resume_maps_not_authorized(store):
    store.update_error = DatabaseRequestError(
        "Not authorized for this resume.",
        status_code=403,
    )

    store.seed(RESUME_ID, USER_ID)

    response = client.put(
        f"/resumes/{RESUME_ID}",
        json={
            "title": "CV",
            "content": VALID_CONTENT,
        },
    )

    assert response.status_code == 403


# ============================================================
# DELETE
# ============================================================

def test_delete_resume_removes_record(store):
    store.seed(RESUME_ID, USER_ID)

    response = client.delete(f"/resumes/{RESUME_ID}")

    assert response.status_code == 204
    assert RESUME_ID not in store.rows


def test_delete_resume_returns_404_when_missing(store):
    response = client.delete(
        "/resumes/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    )

    assert response.status_code == 404


def test_delete_resume_cannot_remove_another_users_resume(store):
    store.seed(RESUME_ID, OTHER_USER_ID)

    response = client.delete(f"/resumes/{RESUME_ID}")

    assert response.status_code == 404
    assert RESUME_ID in store.rows


def test_delete_resume_rejects_malformed_id(store):
    response = client.delete("/resumes/not-a-uuid")

    assert response.status_code == 422
    assert store.calls == []


def test_delete_resume_maps_store_failure(store):
    store.seed(RESUME_ID, USER_ID)
    store.delete_error = DatabaseRequestError(
        "Unable to delete the resume.",
        status_code=500,
    )

    response = client.delete(f"/resumes/{RESUME_ID}")

    assert response.status_code == 500
    assert RESUME_ID in store.rows


# ============================================================
# REQUEST SIZE
# ============================================================

def oversized_payload() -> bytes:

    import json

    return json.dumps(
        {
            "title": "Huge",
            "content": {
                "summary": "A" * 300_000,
            },
        }
    ).encode("utf-8")


def test_resume_write_rejects_oversized_body(store):
    response = client.post(
        "/resumes",
        content=oversized_payload(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413


def test_resume_update_rejects_oversized_body(store):
    store.seed(RESUME_ID, USER_ID)

    response = client.put(
        f"/resumes/{RESUME_ID}",
        content=oversized_payload(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413


def test_middleware_rejects_body_without_content_length(store):
    """A chunked request with no Content-Length must still be capped."""
    import json

    def chunks():
        payload = json.dumps(
            {
                "title": "Huge",
                "content": {"summary": "A" * 300_000},
            }
        ).encode("utf-8")

        for index in range(0, len(payload), 64_000):
            yield payload[index:index + 64_000]

    request = client.build_request(
        "POST",
        "/resumes",
        content=chunks(),
        headers={"Content-Type": "application/json"},
    )

    assert "content-length" not in {
        key.lower()
        for key in request.headers.keys()
    }

    response = client.send(request)

    assert response.status_code == 413
    assert store.calls == []


def test_middleware_rejects_understated_content_length(store):
    """A Content-Length smaller than the real body must not pass."""
    import json

    payload = json.dumps(
        {
            "title": "Huge",
            "content": {"summary": "A" * 300_000},
        }
    ).encode("utf-8")

    request = client.build_request(
        "POST",
        "/resumes",
        content=iter([payload]),
        headers={
            "Content-Type": "application/json",
            "Content-Length": "10",
        },
    )

    response = client.send(request)

    assert response.status_code == 413
    assert store.calls == []


def test_resume_write_allows_body_under_the_limit(store):
    response = client.post(
        "/resumes",
        json={
            "title": "Small CV",
            "content": VALID_CONTENT,
        },
    )

    assert response.status_code == 200


# The cap exists for resume writes only. Reads, deletes and methods
# the API does not implement must still be routed normally, otherwise a
# large body on a read would be answered 413 instead of the route's own
# response.

def test_get_resume_is_not_size_limited(store):
    store.seed(RESUME_ID, USER_ID)

    response = client.request(
        "GET",
        f"/resumes/{RESUME_ID}",
        content=oversized_payload(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == RESUME_ID


def test_delete_resume_is_not_size_limited(store):
    store.seed(RESUME_ID, USER_ID)

    response = client.request(
        "DELETE",
        f"/resumes/{RESUME_ID}",
        content=oversized_payload(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 204
    assert RESUME_ID not in store.rows


def test_unsupported_method_on_a_resume_path_is_not_size_limited(store):
    """A 405 must not be masked by a 413."""

    store.seed(RESUME_ID, USER_ID)

    response = client.request(
        "PATCH",
        f"/resumes/{RESUME_ID}",
        content=oversized_payload(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 405
    assert RESUME_ID in store.rows


def test_only_the_documented_write_methods_are_limited(store):
    """The limited methods must match the routes that take a body."""

    assert backend.RESUME_WRITE_METHODS == ("POST", "PUT")


# The 413 is produced before any inner layer runs, so CORS has to sit
# outside the size limit or a browser cannot read the response.

ALLOWED_ORIGIN = "http://localhost:5500"

UNKNOWN_ORIGIN = "https://not-allowed.example"


def test_cors_is_registered_once_as_the_outermost_layer():
    """Exactly one CORS layer, and it wraps the size limit.

    A second registration was previously present inside the size limit.
    It was inert for a 413, which the inner layer never sees, but it
    rewrote the Vary header of every other response by appending a
    second Origin.
    """

    classes = [
        middleware.cls
        for middleware in backend.app.user_middleware
    ]

    assert classes.count(CORSMiddleware) == 1
    assert classes[0] is CORSMiddleware

    # The outer CORS must still enclose the size limit.
    assert classes.index(
        backend.BodySizeLimitMiddleware
    ) > classes.index(CORSMiddleware)


def test_allowed_origin_receives_cors_headers_on_a_normal_response(
    store,
):
    store.seed(RESUME_ID, USER_ID)

    response = client.get(
        f"/resumes/{RESUME_ID}",
        headers={"Origin": ALLOWED_ORIGIN},
    )

    assert response.status_code == 200
    assert response.headers[
        "access-control-allow-origin"
    ] == ALLOWED_ORIGIN
    assert response.headers[
        "access-control-allow-credentials"
    ] == "true"


def test_unknown_origin_receives_no_cors_headers_on_a_normal_response(
    store,
):
    store.seed(RESUME_ID, USER_ID)

    response = client.get(
        f"/resumes/{RESUME_ID}",
        headers={"Origin": UNKNOWN_ORIGIN},
    )

    assert response.status_code == 200
    assert (
        "access-control-allow-origin"
        not in response.headers
    )


def test_every_allowed_origin_is_accepted(store):
    """The allowlist is unchanged by the cleanup."""

    for origin in (
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "https://careergap.pages.dev",
    ):

        response = client.get(
            "/resumes",
            headers={"Origin": origin},
        )

        assert response.headers[
            "access-control-allow-origin"
        ] == origin


def test_preflight_from_an_unknown_origin_is_refused(store):
    response = client.request(
        "OPTIONS",
        "/resumes",
        headers={
            "Origin": UNKNOWN_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 400
    assert (
        "access-control-allow-origin"
        not in response.headers
    )


def test_rejection_carries_cors_headers_for_an_allowed_origin(store):
    response = client.post(
        "/resumes",
        content=oversized_payload(),
        headers={
            "Content-Type": "application/json",
            "Origin": ALLOWED_ORIGIN,
        },
    )

    assert response.status_code == 413
    assert response.headers[
        "access-control-allow-origin"
    ] == ALLOWED_ORIGIN
    assert response.headers[
        "access-control-allow-credentials"
    ] == "true"


def test_rejection_carries_no_cors_headers_for_an_unknown_origin(store):
    response = client.post(
        "/resumes",
        content=oversized_payload(),
        headers={
            "Content-Type": "application/json",
            "Origin": UNKNOWN_ORIGIN,
        },
    )

    assert response.status_code == 413
    assert (
        "access-control-allow-origin"
        not in response.headers
    )


def test_resume_preflight_is_answered_with_cors_headers(store):
    response = client.request(
        "OPTIONS",
        "/resumes",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers[
        "access-control-allow-origin"
    ] == "http://localhost:5500"


def test_analysis_route_is_not_affected_by_the_resume_limit(
    store,
    monkeypatch,
):
    """The body limit is scoped to resume writes only."""
    captured = {}

    def fake_run(resume, job_description, projects):
        captured["resume"] = resume

        return {"score": 50.0}

    monkeypatch.setattr(
        backend,
        "run_careergap",
        fake_run,
    )

    monkeypatch.setattr(
        backend,
        "generate_career_advice",
        lambda results: None,
    )

    monkeypatch.setattr(
        backend,
        "save_analysis",
        lambda **kwargs: None,
    )

    long_resume = "B" * 20_000

    response = client.post(
        "/analyze",
        json={
            "resume": long_resume,
            "job_description": "Required: Python.",
            "projects": [
                {
                    "name": "P",
                    "description": "D",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert captured["resume"] == long_resume


def test_middleware_does_not_oversized_reject_analysis(store):
    """An oversized /analyze body is validated, not size limited.

    The request is larger than MAX_RESUME_REQUEST_SIZE, so a 413 here
    would mean the middleware leaked onto an unrelated route.
    """
    import json

    payload = json.dumps(
        {
            "resume": "B" * 300_000,
            "job_description": "Required: Python.",
            "projects": [
                {
                    "name": "P",
                    "description": "D",
                }
            ],
        }
    ).encode("utf-8")

    assert len(payload) > backend.MAX_RESUME_REQUEST_SIZE

    response = client.post(
        "/analyze",
        content=payload,
        headers={"Content-Type": "application/json"},
    )

    # Rejected by the request model, never by the size middleware.
    assert response.status_code == 422
    assert store.calls == []


# ============================================================
# AUTHENTICATION
# ============================================================

RESUME_ROUTES = [
    ("get", "/resumes"),
    ("post", "/resumes"),
    ("get", f"/resumes/{RESUME_ID}"),
    ("put", f"/resumes/{RESUME_ID}"),
    ("delete", f"/resumes/{RESUME_ID}"),
]


def anonymous_client() -> TestClient:

    return TestClient(backend.app)


def send_anonymous(method, path):
    """Send a request with no credential overrides in place."""

    backend.app.dependency_overrides.pop(
        backend.get_current_user,
        None,
    )

    backend.app.dependency_overrides.pop(
        backend.security,
        None,
    )

    return anonymous_client().request(
        method.upper(),
        path,
        json={
            "title": "CV",
            "content": VALID_CONTENT,
        },
    )


@pytest.mark.parametrize(
    "method,path",
    RESUME_ROUTES,
)
def test_resume_routes_require_authentication(method, path):
    response = send_anonymous(method, path)

    assert response.status_code == 401


def test_resume_auth_behaviour_matches_existing_routes():
    """Resume routes must reject credentials exactly like /analyze."""

    backend.app.dependency_overrides.pop(
        backend.get_current_user,
        None,
    )

    backend.app.dependency_overrides.pop(
        backend.security,
        None,
    )

    anonymous = anonymous_client()

    analysis_response = anonymous.post(
        "/analyze",
        json={
            "resume": "I know Python.",
            "job_description": "Required: Python.",
            "projects": [
                {
                    "name": "P",
                    "description": "D",
                }
            ],
        },
    )

    resume_response = anonymous.get("/resumes")

    assert analysis_response.status_code == 401
    assert (
        resume_response.status_code
        == analysis_response.status_code
    )