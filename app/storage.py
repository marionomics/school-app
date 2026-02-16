"""Cloudflare R2 (S3-compatible) storage helpers."""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_s3_client = None

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "txt", "csv", "zip", "rar", "7z",
    "png", "jpg", "jpeg", "gif", "webp", "svg",
}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def is_r2_configured() -> bool:
    return all(
        os.getenv(k)
        for k in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_ENDPOINT", "R2_BUCKET_NAME")
    )


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        import boto3
        from botocore.config import Config

        _s3_client = boto3.client(
            "s3",
            endpoint_url=os.getenv("R2_ENDPOINT"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
    return _s3_client


def validate_file(filename: str, size: int) -> Optional[str]:
    """Return a Spanish error message if invalid, or None if OK."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return f"Tipo de archivo no permitido (.{ext}). Tipos aceptados: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
    if size > MAX_FILE_SIZE:
        return f"El archivo es demasiado grande ({size / 1024 / 1024:.1f} MB). Maximo: 10 MB"
    return None


def upload_file(data: bytes, key: str, content_type: str) -> None:
    bucket = os.getenv("R2_BUCKET_NAME")
    get_s3_client().put_object(
        Bucket=bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    logger.info(f"Uploaded {key} to R2 ({len(data)} bytes)")


def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    bucket = os.getenv("R2_BUCKET_NAME")
    return get_s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def delete_file(key: str) -> None:
    bucket = os.getenv("R2_BUCKET_NAME")
    try:
        get_s3_client().delete_object(Bucket=bucket, Key=key)
        logger.info(f"Deleted {key} from R2")
    except Exception as e:
        logger.warning(f"Failed to delete {key} from R2: {e}")
