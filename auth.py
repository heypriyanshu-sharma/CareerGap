import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client
from supabase_auth.errors import AuthApiError


# Load the external secrets file used by local development.
# The location is read only from CAREERGAP_SECRETS_PATH; when it
# is unset (or the file is missing), the project-root .env is
# loaded instead.
SECRETS_PATH = os.environ.get("CAREERGAP_SECRETS_PATH")
if SECRETS_PATH and Path(SECRETS_PATH).exists():
    load_dotenv(SECRETS_PATH)
else:
    load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv(
    "SUPABASE_PUBLISHABLE_KEY"
)


if not SUPABASE_URL or not SUPABASE_PUBLISHABLE_KEY:
    raise RuntimeError(
        "Supabase environment variables are not configured."
    )


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY,
)


security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Verify a Supabase access token and return its user claims."""

    try:
        response = supabase.auth.get_claims(
            credentials.credentials
        )

        if response is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired authentication token.",
                headers={
                    "WWW-Authenticate": "Bearer",
                },
            )

        claims = response["claims"]

    except HTTPException:
        raise

    except Exception as error:
        

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from error

    user_id = claims.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token does not contain a user ID.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    # get_claims validates the JWT locally: it proves the token is
    # genuine and unexpired, but not that the account still exists.
    # A deleted user's unexpired token would otherwise keep
    # authenticating until expiry. Confirm the account with the auth
    # server on every request, failing closed when it cannot answer.
    try:
        user_response = supabase.auth.get_user(
            credentials.credentials
        )
    except AuthApiError as error:
        if getattr(error, "status", 0) >= 500:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Authentication service is temporarily "
                    "unavailable. Please try again."
                ),
            ) from error
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Authentication service is temporarily "
                "unavailable. Please try again."
            ),
        ) from error

    if (
        user_response is None
        or user_response.user is None
        or str(user_response.user.id) != user_id
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    return claims
