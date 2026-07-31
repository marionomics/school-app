from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Class, Enrollment, User


def resolve_default_class(db: Session, user: User) -> Optional[int]:
    """In-session class per schedule; else the only candidate class; else None.

    Candidates are the user's active enrollments plus, for a teacher, the
    classes they teach — a teacher owns classes without ever being enrolled
    in one, so enrollments alone would leave them with no default at all.
    """
    class_ids = [
        e.class_id
        for e in db.query(Enrollment)
        .filter(Enrollment.user_id == user.id, Enrollment.status == "active")
        .all()
    ]
    for klass in db.query(Class).filter(Class.teacher_id == user.id).all():
        if klass.id not in class_ids:
            class_ids.append(klass.id)

    now = datetime.now(ZoneInfo(settings.timezone))
    hhmm = now.strftime("%H:%M")
    for class_id in class_ids:
        klass = db.get(Class, class_id)
        for block in (klass.schedule_json or []):
            if block.get("day") == now.weekday() and block.get("start", "") <= hhmm < block.get("end", ""):
                return class_id
    if len(class_ids) == 1:
        return class_ids[0]
    return None
