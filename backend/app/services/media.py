import logging
import threading
import time

from app import storage
from app.models import Attachment
from app.schemas import AttachmentOut

logger = logging.getLogger(__name__)

# What a browser can show in an <img> on any phone. HEIC (Android can't) and
# SVG stay chips; so does everything that isn't an image.
DISPLAYABLE = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# A link is signed for two hours and handed out again for its first hour, so
# every link a client receives still has at least an hour of life (the spec's
# "valid one hour" is the floor). Reusing it keeps the URL identical across
# feed refetches, so the browser cache hits instead of downloading the photo
# again on mobile data.
SIGN_SECONDS = 7200
REUSE_SECONDS = 3600
MAX_CACHED = 5000

_now = time.monotonic
_cache: "dict[str, tuple[str, float]]" = {}
_lock = threading.Lock()


def clear_signed_cache() -> None:
    with _lock:
        _cache.clear()


def forget(key: str) -> None:
    """Drop a deleted object's cached link so it is never handed out again."""
    with _lock:
        _cache.pop(key, None)


def _signed(key: str) -> str:
    """A signed GET link for `key`, reused while it is under REUSE_SECONDS old."""
    now = _now()
    with _lock:
        hit = _cache.get(key)
        if hit is not None and now - hit[1] < REUSE_SECONDS:
            return hit[0]
    url = storage.generate_presigned_url(key, expires=SIGN_SECONDS)
    with _lock:
        if len(_cache) >= MAX_CACHED:
            # Drop what is past reuse; if everything is fresh, start over.
            for k in [k for k, (_, t) in _cache.items() if now - t >= REUSE_SECONDS]:
                del _cache[k]
            if len(_cache) >= MAX_CACHED:
                _cache.clear()
        _cache[key] = (url, now)
    return url


def attachment_out(att: Attachment) -> AttachmentOut:
    """An attachment as the API sends it. Displayable images carry a signed
    R2 link with at least an hour left; signing is local, so a page of posts
    costs no network calls. On R2 errors, the photo degrades to a chip."""
    url = None
    if att.mime_type in DISPLAYABLE and storage.is_r2_configured():
        try:
            url = _signed(att.file_key)
        except Exception:
            logger.exception("Failed to generate presigned URL for %s", att.file_key)
    return AttachmentOut(id=att.id, file_name=att.file_name,
                         mime_type=att.mime_type, url=url)


def avatar_for(user) -> "str | None":
    """A signed link to the user's own photo if they uploaded one and R2 is
    configured; otherwise their Google photo. A storage error degrades to the
    Google photo — avatars are on every post, so they must never break a page."""
    if user.avatar_key and storage.is_r2_configured():
        try:
            return _signed(user.avatar_key)
        except Exception:
            logger.exception("Failed to generate presigned URL for %s", user.avatar_key)
    return user.avatar_url
