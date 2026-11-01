from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import DEFAULT_STREAK_LEVELS, Enrollment, User
from app.services.grades import get_config
from app.services.streak import (contribution_dates, level_for, local_today, next_level_at,
                                 odds, streak_days, today_done)

router = APIRouter(prefix="/api/streak", tags=["streak"])


@router.get("/me")
def my_streak(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The top bar's fire chip. Odds come from the student's first active
    class — the one the composer defaults to; each real roll uses its post's
    class."""
    enr = (db.query(Enrollment)
           .filter(Enrollment.user_id == user.id, Enrollment.status == "active")
           .order_by(Enrollment.id).first())
    if user.role == "teacher" or enr is None:
        return {"days": 0, "today_done": False, "level": None, "next_level_at": None,
                "odds": {"x2": 0.0, "x3": 0.0}, "levels": DEFAULT_STREAK_LEVELS}
    levels = get_config(db, enr.class_id).streak_levels
    dates = contribution_dates(db, user.id)
    today = local_today()
    days = streak_days(dates, today)
    x2, x3 = odds(days, levels)
    return {"days": days, "today_done": today_done(dates, today),
            "level": level_for(days, levels), "next_level_at": next_level_at(days, levels),
            "odds": {"x2": float(x2), "x3": float(x3)}, "levels": levels}
