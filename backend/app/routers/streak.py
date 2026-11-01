from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import DEFAULT_STREAK_LEVELS, Enrollment, User
from app.services.attribution import resolve_default_class
from app.services.grades import get_config
from app.services.streak import (contribution_dates, level_for, local_today, next_level_at,
                                 odds, streak_days, today_done)

router = APIRouter(prefix="/api/streak", tags=["streak"])


def _active_class_id(db: Session, user: User):
    """The class the composer defaults to; else the first active enrollment."""
    active = [e.class_id for e in
              db.query(Enrollment)
              .filter(Enrollment.user_id == user.id, Enrollment.status == "active")
              .order_by(Enrollment.id).all()]
    if not active:
        return None
    default = resolve_default_class(db, user, fallback_to_recent=True)
    return default if default in active else active[0]


@router.get("/me")
def my_streak(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The top bar's fire chip. Days and today_done are the student's own,
    whatever their enrollments, so the chip agrees with the profile. Odds and
    level come from the class the composer defaults to; each real roll uses
    its post's class."""
    if user.role == "teacher":
        return {"days": 0, "today_done": False, "level": None, "next_level_at": None,
                "odds": {"x2": 0.0, "x3": 0.0}, "levels": list(DEFAULT_STREAK_LEVELS)}
    dates = contribution_dates(db, user.id)
    today = local_today()
    days = streak_days(dates, today)
    out = {"days": days, "today_done": today_done(dates, today), "level": None,
           "next_level_at": None, "odds": {"x2": 0.0, "x3": 0.0},
           "levels": list(DEFAULT_STREAK_LEVELS)}
    class_id = _active_class_id(db, user)
    if class_id is None:
        return out
    levels = get_config(db, class_id).streak_levels
    x2, x3 = odds(days, levels)
    out.update(level=level_for(days, levels), next_level_at=next_level_at(days, levels),
               odds={"x2": float(x2), "x3": float(x3)}, levels=levels)
    return out
