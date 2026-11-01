"""Racha: the per-student daily streak and the 2×/3× roll (spec 2026-10-31).

Pure functions over dates and a level table, plus one query that collects the
dates a student contributed. The streak is computed, never stored; a roll is
stored once at publish (maybe_roll, Task 3).
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Post, User

MIN_CONTRIBUTION_CHARS = 20
TZ = ZoneInfo(settings.timezone)
# Far enough back for any semester; keeps the query bounded.
LOOKBACK_DAYS = 400


def is_contribution(content: str, has_files: bool) -> bool:
    return has_files or len((content or "").strip()) >= MIN_CONTRIBUTION_CHARS


def local_date(dt: datetime) -> date:
    """A naive datetime is UTC (SQLite returns naive)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ).date()


def local_today(now: Optional[datetime] = None) -> date:
    return local_date(now or datetime.now(timezone.utc))


def contribution_dates(db: Session, user_id: int) -> set:
    """Local dates on which this student made a counting contribution."""
    since = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    rows = (db.query(Post.created_at)
            .join(User, User.id == Post.author_id)
            .filter(Post.author_id == user_id,
                    User.role != "teacher",
                    Post.status == "active",
                    Post.created_at >= since,
                    or_(func.length(func.trim(Post.content)) >= MIN_CONTRIBUTION_CHARS,
                        Post.attachments.any()))
            .all())
    return {local_date(at) for (at,) in rows}


def today_done(dates: set, today: date) -> bool:
    return today in dates


def streak_days(dates: set, today: date) -> int:
    """Consecutive days ending today — or yesterday, while today is still open."""
    d = today if today in dates else today - timedelta(days=1)
    n = 0
    while d in dates:
        n += 1
        d -= timedelta(days=1)
    return n


def level_for(days: int, levels: list) -> Optional[dict]:
    found = None
    for lvl in sorted(levels, key=lambda l: l["from_days"]):
        if lvl["from_days"] <= days:
            found = lvl
    return found


def odds(days: int, levels: list) -> tuple:
    lvl = level_for(days, levels)
    if lvl is None:
        return Decimal("0"), Decimal("0")
    return Decimal(str(lvl["x2"])), Decimal(str(lvl["x3"]))


def next_level_at(days: int, levels: list) -> Optional[int]:
    later = [l["from_days"] for l in levels if l["from_days"] > days]
    return min(later) if later else None


def roll(x2: Decimal, x3: Decimal, u: float) -> int:
    """One uniform draw u in [0, 1): 3× first, then 2×, else 1×."""
    u = Decimal(str(u))
    if u < x3:
        return 3
    if u < x3 + x2:
        return 2
    return 1
