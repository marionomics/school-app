import secrets

from sqlalchemy.orm import Session

from app.models import AuthSession, User


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(AuthSession(user_id=user.id, token=token))
    db.commit()
    return token


def revoke_session(db: Session, token: str) -> None:
    db.query(AuthSession).filter(AuthSession.token == token).delete()
    db.commit()
