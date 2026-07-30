import base64
from datetime import datetime
from typing import Tuple


def encode_cursor(last_activity_at: datetime, post_id: int) -> str:
    raw = f"{last_activity_at.isoformat()}|{post_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(s: str) -> Tuple[datetime, int]:
    raw = base64.urlsafe_b64decode(s.encode()).decode()
    ts, _, pid = raw.rpartition("|")
    return datetime.fromisoformat(ts), int(pid)
