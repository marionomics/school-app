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


def encode_feed_cursor(as_of: datetime, offset: int) -> str:
    """The feed's cursor: the moment the ranking was frozen and how far in.
    Every page of one load re-ranks with the same as_of, so nothing moves."""
    raw = f"{as_of.isoformat()}|{offset}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_feed_cursor(s: str) -> Tuple[datetime, int]:
    raw = base64.urlsafe_b64decode(s.encode()).decode()
    ts, _, off = raw.rpartition("|")
    as_of = datetime.fromisoformat(ts)
    offset = int(off)
    if as_of.tzinfo is None or offset < 0:
        raise ValueError("bad feed cursor")
    return as_of, offset
