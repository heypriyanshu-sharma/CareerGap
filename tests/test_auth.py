import pytest
from fastapi import HTTPException

import auth


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

    credentials = type(
        "Credentials",
        (),
        {"credentials": "test-token"},
    )()

    with pytest.raises(HTTPException) as exc_info:
        auth.get_current_user(credentials)

    assert exc_info.value.status_code == 401