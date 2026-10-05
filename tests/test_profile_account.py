"""Tests for the profile and account-deletion endpoints.

Ownership is the property under test: the target user always comes from
the verified token claims, never from the request body, and every profile
query is scoped to that id so one user can never read or write another
user's row through this API.
"""

from pathlib import Path
from unittest.mock import Mock, patch
import re

import pytest
from fastapi.testclient import TestClient

import auth
import backend


client = TestClient(backend.app)


USER_ID = "11111111-1111-1111-1111-111111111111"
OTHER_USER_ID = "22222222-2222-2222-2222-222222222222"
AUTH_HEADER = {"Authorization": "Bearer test-access-token"}


@pytest.fixture
def authenticated_user():
    backend.app.dependency_overrides[
        backend.get_current_user
    ] = lambda: {
        "sub": USER_ID,
        "email": "owner@example.com",
    }

    yield

    backend.app.dependency_overrides.pop(
        backend.get_current_user,
        None,
    )


def reset_rate_limit():
    """Clear the shared limiter between tests.

    The delete route is deliberately rate limited, and the limiter is
    global, so each test starts from an empty counter.
    """

    backend.limiter._storage.reset()


def _response(
    payload=None,
    ok=True,
    status_code=200,
):
    mock = Mock()
    mock.ok = ok
    mock.status_code = status_code
    mock.json.return_value = (
        payload if payload is not None else []
    )

    return mock


# ============================================================
# GET /auth/profile
# ============================================================

class TestGetProfile:

    @patch("backend.requests.get")
    def test_returns_profile_for_token_user(
        self,
        mock_get,
        authenticated_user,
    ):
        row = {
            "id": USER_ID,
            "avatar_url": None,
            "full_name": "Priya Sharma",
            "target_role": "Backend Engineer",
            "experience_level": "mid",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-02T00:00:00+00:00",
        }

        mock_get.return_value = _response([row])

        response = client.get(
            "/auth/profile",
            headers=AUTH_HEADER,
        )

        assert response.status_code == 200

        body = response.json()

        assert body["user_id"] == USER_ID
        assert body["email"] == "owner@example.com"
        assert body["profile"]["full_name"] == (
            "Priya Sharma"
        )
        assert body["profile"]["target_role"] == (
            "Backend Engineer"
        )
        assert body["profile"]["experience_level"] == "mid"

    @patch("backend.requests.get")
    @patch("backend.requests.post")
    def test_scopes_query_to_token_user(
        self,
        mock_post,
        mock_get,
        authenticated_user,
    ):
        """The id filter must come from the token, not the client."""

        mock_get.return_value = _response([])
        mock_post.return_value = _response([])

        client.get("/auth/profile", headers=AUTH_HEADER)

        params = mock_get.call_args[1]["params"]

        assert params["id"] == f"eq.{USER_ID}"
        assert OTHER_USER_ID not in str(params)

    @patch("backend.requests.get")
    @patch("backend.requests.post")
    def test_creates_row_when_user_predates_migration(
        self,
        mock_post,
        mock_get,
        authenticated_user,
    ):
        """The signup trigger cannot have covered an account that
        existed before the profiles table, so reading the page creates
        the missing row."""

        created = {
            "id": USER_ID,
            "avatar_url": None,
            "full_name": None,
            "target_role": None,
            "experience_level": None,
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
        }

        mock_get.return_value = _response([])
        mock_post.return_value = _response([created])

        response = client.get(
            "/auth/profile",
            headers=AUTH_HEADER,
        )

        assert response.status_code == 200

        profile = response.json()["profile"]

        assert profile["id"] == USER_ID
        assert profile["created_at"] is not None

        payload = mock_post.call_args[1]["json"]

        assert payload == {"id": USER_ID}

    @patch("backend.requests.get")
    @patch("backend.requests.post")
    def test_row_creation_cannot_duplicate(
        self,
        mock_post,
        mock_get,
        authenticated_user,
    ):
        """The upsert merges on id, so a repeat read adds no second
        row and never overwrites stored columns."""

        mock_get.return_value = _response([])
        mock_post.return_value = _response(
            [{"id": USER_ID, "full_name": None}]
        )

        client.get("/auth/profile", headers=AUTH_HEADER)

        assert (
            mock_post.call_args[1]["params"]["on_conflict"]
            == "id"
        )

        prefer = mock_post.call_args[1]["headers"]["Prefer"]

        assert "resolution=merge-duplicates" in prefer

    @patch("backend.requests.get")
    @patch("backend.requests.post")
    def test_existing_row_is_not_rewritten(
        self,
        mock_post,
        mock_get,
        authenticated_user,
    ):
        """A user who already has a row must not trigger a write."""

        mock_get.return_value = _response(
            [{"id": USER_ID, "full_name": "Priya Sharma"}]
        )

        client.get("/auth/profile", headers=AUTH_HEADER)

        mock_post.assert_not_called()

    @patch("backend.requests.get")
    @patch("backend.requests.post")
    def test_falls_back_to_null_fields_when_creation_fails(
        self,
        mock_post,
        mock_get,
        authenticated_user,
    ):
        """Losing the convenience create must not break the page."""

        mock_get.return_value = _response([])
        mock_post.return_value = _response(
            ok=False, status_code=500
        )

        response = client.get(
            "/auth/profile",
            headers=AUTH_HEADER,
        )

        assert response.status_code == 200

        profile = response.json()["profile"]

        assert profile["id"] == USER_ID
        assert profile["full_name"] is None
        assert profile["target_role"] is None
        assert profile["experience_level"] is None

    @patch("backend.requests.get")
    @patch("backend.requests.post")
    def test_forwards_caller_token_for_rls(
        self,
        mock_post,
        mock_get,
        authenticated_user,
    ):
        """The caller's own token is sent so RLS stays authoritative."""

        mock_get.return_value = _response([])
        mock_post.return_value = _response([])

        client.get("/auth/profile", headers=AUTH_HEADER)

        headers = mock_get.call_args[1]["headers"]

        assert (
            headers["Authorization"]
            == "Bearer test-access-token"
        )

    def test_rejects_missing_token(self):
        response = client.get("/auth/profile")

        assert response.status_code == 401

    def test_rejects_invalid_token(self, monkeypatch):
        def fake_get_claims(access_token):
            raise RuntimeError("Invalid token.")

        monkeypatch.setattr(
            auth.supabase.auth,
            "get_claims",
            fake_get_claims,
        )

        response = client.get(
            "/auth/profile",
            headers=AUTH_HEADER,
        )

        assert response.status_code == 401


# ============================================================
# PUT /auth/profile
# ============================================================

class TestUpdateProfile:

    @patch("backend.requests.post")
    def test_updates_only_supplied_fields(
        self,
        mock_post,
        authenticated_user,
    ):
        mock_post.return_value = _response([
            {
                "id": USER_ID,
                "full_name": "Priya Sharma",
                "target_role": None,
            }
        ])

        response = client.put(
            "/auth/profile",
            headers=AUTH_HEADER,
            json={"full_name": "  Priya Sharma  "},
        )

        assert response.status_code == 200

        payload = mock_post.call_args[1]["json"]

        assert payload["full_name"] == "Priya Sharma"
        assert "target_role" not in payload
        assert "experience_level" not in payload

    @patch("backend.requests.post")
    def test_scopes_write_to_token_user(
        self,
        mock_post,
        authenticated_user,
    ):
        mock_post.return_value = _response([
            {"id": USER_ID}
        ])

        client.put(
            "/auth/profile",
            headers=AUTH_HEADER,
            json={"target_role": "Data Engineer"},
        )

        payload = mock_post.call_args[1]["json"]

        assert payload["id"] == USER_ID
        assert OTHER_USER_ID not in str(payload)

    @patch("backend.requests.post")
    def test_blank_text_becomes_null(
        self,
        mock_post,
        authenticated_user,
    ):
        mock_post.return_value = _response([
            {"id": USER_ID, "target_role": None}
        ])

        client.put(
            "/auth/profile",
            headers=AUTH_HEADER,
            json={"target_role": "   "},
        )

        assert mock_post.call_args[1]["json"][
            "target_role"
        ] is None

    @patch("backend.requests.post")
    def test_upsert_used_for_user_without_row(
        self,
        mock_post,
        authenticated_user,
    ):
        """A user created before the table exists still gets a row."""

        mock_post.return_value = _response([
            {"id": USER_ID, "full_name": "New Name"}
        ])

        response = client.put(
            "/auth/profile",
            headers=AUTH_HEADER,
            json={"full_name": "New Name"},
        )

        assert response.status_code == 200

        headers = mock_post.call_args[1]["headers"]

        assert (
            "resolution=merge-duplicates"
            in headers["Prefer"]
        )

    def test_rejects_unknown_experience_level(
        self,
        authenticated_user,
    ):
        response = client.put(
            "/auth/profile",
            headers=AUTH_HEADER,
            json={"experience_level": "wizard"},
        )

        assert response.status_code == 422

    def test_rejects_removed_principal_level(
        self,
        authenticated_user,
    ):
        """`principal` is no longer offered and must be refused."""

        reset_rate_limit()

        response = client.put(
            "/auth/profile",
            headers=AUTH_HEADER,
            json={"experience_level": "principal"},
        )

        assert response.status_code == 422

    @patch("backend.requests.post")
    @pytest.mark.parametrize(
        "level", ("student", "junior", "mid", "senior", "lead")
    )
    def test_accepts_every_supported_experience_level(
        self,
        mock_post,
        level,
        authenticated_user,
    ):
        mock_post.return_value = _response(
            [{"id": USER_ID, "experience_level": level}]
        )

        reset_rate_limit()

        response = client.put(
            "/auth/profile",
            headers=AUTH_HEADER,
            json={"experience_level": level},
        )

        assert response.status_code == 200

        assert (
            response.json()["experience_level"] == level
        )

    def test_experience_levels_match_the_migration(
        self,
        authenticated_user,
    ):
        """Backend validation and the CHECK constraint must agree, or a
        level the UI offers would be rejected by the database."""

        migration = (
            Path(__file__).resolve().parents[1]
            / "supabase"
            / "migrations"
            / "0002_create_profiles.sql"
        ).read_text(encoding="utf-8")

        constrained = re.search(
            r"check \(experience_level in \(([^)]*)\)\)",
            migration,
        )

        assert constrained is not None

        levels = re.findall(
            r"'([^']+)'", constrained.group(1)
        )

        assert tuple(levels) == backend.EXPERIENCE_LEVELS

    def test_rejects_user_id_in_payload(
        self,
        authenticated_user,
    ):
        """A client-supplied user id must not be smuggled through."""

        response = client.put(
            "/auth/profile",
            headers=AUTH_HEADER,
            json={"user_id": OTHER_USER_ID},
        )

        assert response.status_code == 422

    def test_rejects_id_field_in_payload(
        self,
        authenticated_user,
    ):
        response = client.put(
            "/auth/profile",
            headers=AUTH_HEADER,
            json={"id": OTHER_USER_ID},
        )

        assert response.status_code == 422

    def test_rejects_non_http_avatar_url(
        self,
        authenticated_user,
    ):
        """A javascript: or data: avatar URL is refused.

        The URL is rendered into a CSS background-image, so only
        absolute http(s) URLs are accepted.
        """

        response = client.put(
            "/auth/profile",
            headers=AUTH_HEADER,
            json={
                "avatar_url":
                    "javascript:alert(1)"
            },
        )

        assert response.status_code == 422

    def test_rejects_empty_payload(
        self,
        authenticated_user,
    ):
        response = client.put(
            "/auth/profile",
            headers=AUTH_HEADER,
            json={},
        )

        assert response.status_code == 400

    def test_rejects_missing_token(self):
        response = client.put(
            "/auth/profile",
            json={"full_name": "Nobody"},
        )

        assert response.status_code == 401

    def test_rejects_invalid_token(self, monkeypatch):
        def fake_get_claims(access_token):
            raise RuntimeError("Invalid token.")

        monkeypatch.setattr(
            auth.supabase.auth,
            "get_claims",
            fake_get_claims,
        )

        response = client.put(
            "/auth/profile",
            headers=AUTH_HEADER,
            json={"full_name": "Nobody"},
        )

        assert response.status_code == 401


# ============================================================
# DELETE /auth/delete-account
# ============================================================

class TestDeleteAccount:

    def test_rejects_missing_token(self):
        response = client.delete(
            "/auth/delete-account"
        )

        assert response.status_code == 401

    def test_rejects_invalid_token(self, monkeypatch):
        def fake_get_claims(access_token):
            raise RuntimeError("Invalid token.")

        monkeypatch.setattr(
            auth.supabase.auth,
            "get_claims",
            fake_get_claims,
        )

        response = client.delete(
            "/auth/delete-account",
            headers=AUTH_HEADER,
        )

        assert response.status_code == 401

    @patch("backend.get_supabase_admin")
    def test_deletes_token_user(
        self,
        mock_admin,
        authenticated_user,
    ):
        reset_rate_limit()

        admin = Mock()
        admin.auth.admin.delete_user.return_value = None
        mock_admin.return_value = admin

        response = client.delete(
            "/auth/delete-account",
            headers=AUTH_HEADER,
        )

        assert response.status_code == 204

        admin.auth.admin.delete_user.assert_called_once_with(
            USER_ID
        )

    @patch("backend.get_supabase_admin")
    def test_never_uses_client_supplied_user_id(
        self,
        mock_admin,
        authenticated_user,
    ):
        """Ownership comes from the token even when the body lies."""

        reset_rate_limit()

        admin = Mock()
        admin.auth.admin.delete_user.return_value = None
        mock_admin.return_value = admin

        client.request(
            "DELETE",
            "/auth/delete-account",
            headers=AUTH_HEADER,
            json={"user_id": OTHER_USER_ID},
        )

        deleted = (
            admin.auth.admin.delete_user.call_args[0][0]
        )

        assert deleted == USER_ID
        assert deleted != OTHER_USER_ID

    @patch("backend.get_supabase_admin")
    def test_admin_failure_returns_generic_500(
        self,
        mock_admin,
        authenticated_user,
        caplog,
    ):
        reset_rate_limit()

        admin = Mock()
        admin.auth.admin.delete_user.side_effect = (
            RuntimeError("boom")
        )
        mock_admin.return_value = admin

        response = client.delete(
            "/auth/delete-account",
            headers=AUTH_HEADER,
        )

        assert response.status_code == 500
        assert response.json()["detail"] == (
            "Unable to delete account."
        )

    @patch("backend.get_supabase_admin")
    def test_admin_failure_does_not_leak_error(
        self,
        mock_admin,
        authenticated_user,
    ):
        """The internal message must not reach the client."""

        reset_rate_limit()

        admin = Mock()
        admin.auth.admin.delete_user.side_effect = (
            RuntimeError(
                "service_role_key=super-secret-value"
            )
        )
        mock_admin.return_value = admin

        response = client.delete(
            "/auth/delete-account",
            headers=AUTH_HEADER,
        )

        assert "super-secret-value" not in response.text

    def test_reports_unavailable_when_service_key_missing(
        self,
        authenticated_user,
        monkeypatch,
    ):
        reset_rate_limit()

        monkeypatch.setattr(
            backend,
            "get_supabase_admin",
            lambda: None,
        )

        response = client.delete(
            "/auth/delete-account",
            headers=AUTH_HEADER,
        )

        assert response.status_code == 503

    def test_delete_route_is_rate_limited(
        self,
        authenticated_user,
    ):
        """Account deletion is capped so it cannot be hammered."""

        reset_rate_limit()

        admin = Mock()
        admin.auth.admin.delete_user.return_value = None

        with patch(
            "backend.get_supabase_admin",
            return_value=admin,
        ):
            statuses = [
                client.delete(
                    "/auth/delete-account",
                    headers=AUTH_HEADER,
                ).status_code
                for _ in range(4)
            ]

        assert statuses[:3] == [204, 204, 204]
        assert statuses[3] == 429


# ============================================================
# Service key handling
# ============================================================

class TestServiceKeyHandling:

    def test_service_key_never_reaches_profile_calls(self):
        """Profile reads and writes use the caller's token only."""

        headers = backend._profile_headers(
            "caller-token"
        )

        assert headers["Authorization"] == (
            "Bearer caller-token"
        )

    def test_profile_headers_support_prefer(self):
        headers = backend._profile_headers(
            "caller-token",
            prefer="return=representation",
        )

        assert headers["Prefer"] == (
            "return=representation"
        )

    def test_import_does_not_require_service_key(self):
        """A missing service key must not stop the API starting."""

        assert hasattr(
            backend, "get_supabase_admin"
        )

    def test_admin_client_is_none_without_service_key(
        self,
        monkeypatch,
    ):
        monkeypatch.setattr(
            backend, "SUPABASE_URL", None
        )
        monkeypatch.setattr(
            backend, "SUPABASE_SERVICE_KEY", None
        )
        monkeypatch.setattr(
            backend, "_supabase_admin", None
        )

        assert backend.get_supabase_admin() is None