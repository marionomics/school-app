import secrets
import string
from datetime import date

from sqlalchemy.orm import Session

from app.models import Class

_ALPHABET = string.ascii_uppercase + string.digits


def _random_suffix() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(4))


def generate_code(db: Session, prefix: str) -> str:
    prefix = "".join(ch for ch in prefix.upper() if ch.isalnum()) or "CLASE"
    year = date.today().year
    while True:
        code = f"{prefix}{year}{_random_suffix()}"
        if db.query(Class).filter(Class.code == code).first() is None:
            return code
