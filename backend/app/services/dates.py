from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def next_sunday_due(now: datetime, tz_name: str) -> datetime:
    """Next Sunday at 23:59 local time, returned in UTC.

    If `now` is already Sunday the result is the FOLLOWING Sunday — a tarea
    created on Sunday is never due the same night.
    """
    tz = ZoneInfo(tz_name)
    local = now.astimezone(tz)
    days_ahead = (6 - local.weekday()) % 7  # Monday=0 … Sunday=6
    if days_ahead == 0:
        days_ahead = 7
    due_local = (local + timedelta(days=days_ahead)).replace(
        hour=23, minute=59, second=0, microsecond=0
    )
    return due_local.astimezone(timezone.utc)
