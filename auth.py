import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client


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

    return claims