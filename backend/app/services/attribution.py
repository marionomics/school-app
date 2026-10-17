from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Class, Enrollment, User


def _last_block_start(klass: Class, now: datetime) -> Optional[datetime]:
    """When this class last started per its weekly schedule, at or before now."""
    latest = None
    for block in (klass.schedule_json or []):
        try:
            h, m = map(int, block.get("start", "").split(":"))
            day = int(block["day"])
        except (KeyError, ValueError):
            continue
        days_back = (now.weekday() - day) % 7
        start = (now - timedelta(days=days_back)).replace(
            hour=h, minute=m, second=0, microsecond=0)
        if start > now:
            start -= timedelta(days=7)
        if latest is None or start > latest:
            latest = start
    return latest


def resolve_default_class(db: Session, user: User, now: Optional[datetime] = None,
                          fallback_to_recent: bool = False) -> Optional[int]:
    """In-session class per schedule; else the only candidate; else None —
    or, with fallback_to_recent, the class you had most recently.

    Candidates are the user's active enrollments plus, for a teacher, the
    classes they teach — a teacher owns classes without ever being enrolled
    in one, so enrollments alone would leave them with no default at all.

    None means "ask": a tarea must never land in a guessed class. A regular
    post has no picker, though, and None there meant the aura it received
    counted for nobody — so it asks for the fallback: the class whose last
    scheduled block is the latest (posting at night after the 6 pm class
    counts for that class). A class whose term is over ranks below one in
    term, and a class with no schedule below one that has it; the newest
    class breaks ties.
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
    if not class_ids:
        return None
    classes = [db.get(Class, cid) for cid in class_ids]

    now = now or datetime.now(ZoneInfo(settings.timezone))
    hhmm = now.strftime("%H:%M")
    for klass in classes:
        for block in (klass.schedule_json or []):
            if block.get("day") == now.weekday() and block.get("start", "") <= hhmm < block.get("end", ""):
                return klass.id
    if len(classes) == 1:
        return classes[0].id
    if not fallback_to_recent:
        return None

    def rank(klass: Class):
        in_term = klass.start_date <= now.date() <= klass.end_date
        last = _last_block_start(klass, now)
        return (in_term, last is not None,
                last.timestamp() if last else 0.0, klass.id)

    return max(classes, key=rank).id
