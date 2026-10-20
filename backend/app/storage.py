from functools import lru_cache
from typing import Optional

import boto3

from app.config import settings

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv",
    "zip", "rar", "7z", "png", "jpg", "jpeg", "gif", "webp", "svg",
    "heic", "heif",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def is_r2_configured() -> bool:
    return bool(
        settings.r2_access_key_id and settings.r2_secret_access_key
        and settings.r2_endpoint and settings.r2_bucket_name
    )


@lru_cache(maxsize=1)
def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.r2_endpoint,
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def validate_file(filename: str, size: int) -> Optional[str]:
    if "." not in filename:
        return "El archivo no tiene extensión"
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return f"Tipo de archivo no permitido: .{ext}"
    if size > MAX_FILE_SIZE:
        return "El archivo es demasiado grande (máximo 10 MB)"
    return None


def upload_bytes(data: bytes, key: str, content_type: str) -> None:
    # Keys are unique per upload, so a stored object never changes: let the
    # browser keep it for good instead of re-downloading on mobile data.
    _client().put_object(Bucket=settings.r2_bucket_name, Key=key, Body=data,
                         ContentType=content_type,
                         CacheControl="private, max-age=31536000, immutable")


def delete_object(key: str) -> None:
    _client().delete_object(Bucket=settings.r2_bucket_name, Key=key)


def generate_presigned_url(key: str, expires: int = 3600) -> str:
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.r2_bucket_name, "Key": key},
        ExpiresIn=expires,
    )
