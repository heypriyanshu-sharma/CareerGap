import pytest
from fastapi import HTTPException

import auth


def _stub_get_user_ok(monkeypatch):
    user = type("User", (), {"id": "test-user-id"})()
    response = type("UserResponse", (), {"user": user})()
    monkeypatch.setattr(
        auth.supabase.auth, "get_user", lambda token: response
    )


def test_get_current_user_returns_verified_claims(monkeypatch):
    expected_claims = {
        "sub": "test-user-id",
        "email": "test@example.com",
    }

    monkeypatch.setattr(
        auth.supabase.auth,
        "get_claims",
        lambda token: {"claims": expected_claims},
    )
    _stub_get_user_ok(monkeypatch)

    credentials = type(
        "Credentials",
        (),
        {"credentials": "test-token"},
    )()

    result = auth.get_current_user(credentials)

    assert result == expected_claims


def test_get_current_user_rejects_missing_claims(monkeypatch):
    monkeypatch.setattr(
        auth.supabase.auth,
        "get_claims",
        lambda token: None,
    )
    _stub_get_user_ok(monkeypatch)

    credentials = type(
        "Credentials",
        (),
        {"credentials": "test-token"},
    )()

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user(credentials)

    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_invalid_token(monkeypatch):
    def fake_get_claims(token):
        raise ValueError("Invalid token")

    monkeypatch.setattr(
        auth.supabase.auth,
        "get_claims",
        fake_get_claims,
    )
    _stub_get_user_ok(monkeypatch)

    credentials = type(
        "Credentials",
        (),
        {"credentials": "test-token"},
    )()

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user(credentials)

    assert exc_info.value.status_code == 401

def _credentials(token="test-token"):
    return type("Credentials", (), {"credentials": token})()


def _user_response(user_id="test-user-id"):
    user = type("User", (), {"id": user_id})()
    return type("UserResponse", (), {"user": user})()


def _mock_valid(monkeypatch, user_id="test-user-id"):
    monkeypatch.setattr(
        auth.supabase.auth,
        "get_claims",
        lambda token: {
            "claims": {"sub": user_id, "email": "test@example.com"}
        },
    )
    monkeypatch.setattr(
        auth.supabase.auth,
        "get_user",
        lambda token: _user_response(user_id),
    )


def test_get_current_user_confirms_account_exists(monkeypatch):
    _mock_valid(monkeypatch)

    result = auth.get_current_user(_credentials())

    assert result["sub"] == "test-user-id"


def test_get_current_user_rejects_deleted_account(monkeypatch):
    from supabase_auth.errors import AuthApiError

    _mock_valid(monkeypatch)

    def fake_get_user(token):
        raise AuthApiError("User from sub claim in JWT does not exist", 403, "user_not_found")

    monkeypatch.setattr(auth.supabase.auth, "get_user", fake_get_user)

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user(_credentials())

    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_missing_user(monkeypatch):
    _mock_valid(monkeypatch)
    monkeypatch.setattr(
        auth.supabase.auth, "get_user", lambda token: None
    )

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user(_credentials())

    assert exc_info.value.status_code == 401


def test_get_current_user_rejects_user_id_mismatch(monkeypatch):
    _mock_valid(monkeypatch, user_id="test-user-id")
    monkeypatch.setattr(
        auth.supabase.auth,
        "get_user",
        lambda token: _user_response("someone-else"),
    )

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user(_credentials())

    assert exc_info.value.status_code == 401


def test_get_current_user_fails_closed_on_auth_server_error(
    monkeypatch,
):
    from supabase_auth.errors import AuthApiError

    _mock_valid(monkeypatch)

    def fake_get_user(token):
        raise AuthApiError("Internal error", 500, "unexpected_failure")

    monkeypatch.setattr(auth.supabase.auth, "get_user", fake_get_user)

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user(_credentials())

    assert exc_info.value.status_code == 503


def test_get_current_user_fails_closed_on_transport_error(monkeypatch):
    _mock_valid(monkeypatch)

    def fake_get_user(token):
        raise ConnectionError("network unreachable")

    monkeypatch.setattr(auth.supabase.auth, "get_user", fake_get_user)

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user(_credentials())

    assert exc_info.value.status_code == 503
