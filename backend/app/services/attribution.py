from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Class, Enrollment, User


def resolve_default_class(db: Session, user: User) -> Optional[int]:
    """In-session class per schedule; else the only active enrollment; else None."""
    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == user.id, Enrollment.status == "active")
        .all()
    )
    now = datetime.now(ZoneInfo(settings.timezone))
    hhmm = now.strftime("%H:%M")
    for e in enrollments:
        klass = db.get(Class, e.class_id)
        for block in (klass.schedule_json or []):
            if block.get("day") == now.weekday() and block.get("start", "") <= hhmm < block.get("end", ""):
                return e.class_id
    if len(enrollments) == 1:
        return enrollments[0].class_id
    return None
