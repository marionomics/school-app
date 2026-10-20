import logging

from app import storage
from app.models import Attachment
from app.schemas import AttachmentOut

# What a browser can show in an <img> on any phone. HEIC (Android can't) and
# SVG stay chips; so does everything that isn't an image.
DISPLAYABLE = {"image/jpeg", "image/png", "image/webp", "image/gif"}

LINK_SECONDS = 3600


def attachment_out(att: Attachment) -> AttachmentOut:
    """An attachment as the API sends it. Displayable images carry a signed
    R2 link valid for an hour; signing is local, so a page of posts costs no
    network calls. On R2 errors, the photo degrades to a chip."""
    url = None
    if att.mime_type in DISPLAYABLE and storage.is_r2_configured():
        try:
            url = storage.generate_presigned_url(att.file_key, expires=LINK_SECONDS)
        except Exception:
            logging.getLogger(__name__).exception(
                f"Failed to generate presigned URL for {att.file_key}")
    return AttachmentOut(id=att.id, file_name=att.file_name,
                         mime_type=att.mime_type, url=url)
