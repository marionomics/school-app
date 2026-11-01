from datetime import date, datetime, timezone
from decimal import Decimal

from app.models import Attachment, Post
from app.services.streak import (contribution_dates, is_contribution, level_for, local_date,
                                 next_level_at, odds, roll, streak_days, today_done)

LEVELS = [{"from_days": 3, "x2": 0.15, "x3": 0.0},
          {"from_days": 7, "x2": 0.2, "x3": 0.05},
          {"from_days": 14, "x2": 0.25, "x3": 0.1}]
D = date(2026, 10, 20)


def days(*offsets):
    return {date.fromordinal(D.toordinal() - o) for o in offsets}


def test_contribution_needs_twenty_chars_or_a_file():
    assert is_contribution("x" * 20, False)
    assert not is_contribution("   " + "x" * 19 + "   ", False)
    assert is_contribution("", True)


def test_local_date_uses_mexico_city():
    # 05:30 UTC on the 21st is 23:30 on the 20th in Mexico City.
    assert local_date(datetime(2026, 10, 21, 5, 30, tzinfo=timezone.utc)) == date(2026, 10, 20)
    assert local_date(datetime(2026, 10, 21, 5, 30)) == date(2026, 10, 20)   # naive = UTC


def test_streak_counts_back_from_today_or_yesterday():
    assert streak_days(days(0, 1, 2), D) == 3
    assert streak_days(days(1, 2), D) == 2          # today still open
    assert streak_days(days(0, 2, 3), D) == 1       # gap yesterday breaks it
    assert streak_days(days(2, 3), D) == 0
    assert today_done(days(0), D) and not today_done(days(1), D)


def test_levels_and_odds():
    assert level_for(2, LEVELS) is None
    assert level_for(3, LEVELS)["from_days"] == 3
    assert level_for(13, LEVELS)["from_days"] == 7
    assert level_for(40, LEVELS)["from_days"] == 14
    assert odds(2, LEVELS) == (Decimal("0"), Decimal("0"))
    assert odds(7, LEVELS) == (Decimal("0.2"), Decimal("0.05"))
    assert next_level_at(0, LEVELS) == 3
    assert next_level_at(7, LEVELS) == 14
    assert next_level_at(14, LEVELS) is None


def test_roll_thresholds():
    x2, x3 = Decimal("0.2"), Decimal("0.05")
    assert roll(x2, x3, 0.0) == 3
    assert roll(x2, x3, 0.0499) == 3
    assert roll(x2, x3, 0.05) == 2
    assert roll(x2, x3, 0.2499) == 2
    assert roll(x2, x3, 0.25) == 1
    assert roll(Decimal("0"), Decimal("0"), 0.0) == 1


def test_contribution_dates_ignore_short_vetoed_deleted_and_teacher(db, student, teacher):
    def post(author, content, at, status="active", files=()):
        p = Post(author_id=author.id, content=content, created_at=at, status=status)
        db.add(p)
        db.flush()
        for n in files:
            db.add(Attachment(post_id=p.id, file_key=f"k/{n}", file_name=n,
                              file_size=1, mime_type="image/jpeg"))
        return p
    t = lambda d: datetime(2026, 10, d, 18, 0, tzinfo=timezone.utc)
    post(student, "x" * 25, t(18))
    post(student, "corto", t(17))
    post(student, "", t(16), files=["f.jpg"])
    post(student, "x" * 25, t(15), status="vetoed")
    post(student, "x" * 25, t(14), status="deleted")
    post(teacher, "x" * 25, t(13))
    db.commit()
    assert contribution_dates(db, student.id) == {date(2026, 10, 18), date(2026, 10, 16)}
    assert contribution_dates(db, teacher.id) == set()
