from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import settings


def verify_google_token(credential: str) -> dict:
    """Verify a Google ID token. Returns {sub, email, name, picture}; raises ValueError."""
    info = id_token.verify_oauth2_token(
        credential, google_requests.Request(), settings.google_client_id
    )
    return {
        "sub": info["sub"],
        "email": info["email"],
        "name": info.get("name", info["email"]),
        "picture": info.get("picture"),
    }
