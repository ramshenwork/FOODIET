"""File storage. Supabase Storage when configured; a local folder (backend/var/uploads) in development.

Files are stored under random names. The frontend never talks to storage directly.
"""
import secrets
from pathlib import Path

import httpx

from app.core.settings import ROOT, get_settings

LOCAL_ROOT = ROOT / "backend" / "var" / "uploads"

ALLOWED = {  # content type -> extension; validated server-side together with magic bytes
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf", "text/csv": ".csv",
}
MAGIC = {".jpg": [b"\xff\xd8\xff"], ".png": [b"\x89PNG"], ".webp": [b"RIFF"], ".pdf": [b"%PDF"]}
MAX_BYTES = 10 * 1024 * 1024


class StorageError(ValueError):
    pass


def validate(content_type: str, data: bytes) -> str:
    ext = ALLOWED.get((content_type or "").split(";")[0].strip())
    if ext is None:
        raise StorageError("Upload a JPEG, PNG, WebP, PDF or CSV file.")
    if len(data) > MAX_BYTES:
        raise StorageError("Files can be at most 10 MB.")
    if not data:
        raise StorageError("The file is empty.")
    if ext in MAGIC and not any(data.startswith(m) for m in MAGIC[ext]):
        raise StorageError("The file's contents don't match its type.")
    if ext == ".csv":
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            raise StorageError("The CSV must be UTF-8 text.") from e
    return ext


async def put_private(data: bytes, ext: str) -> str:
    """Store in the private bucket; returns the storage path."""
    s = get_settings()
    path = f"{secrets.token_hex(16)}{ext}"
    if s.SUPABASE_URL and s.SUPABASE_SERVICE_KEY and s.STORAGE_BUCKET_PRIVATE:
        url = f"{s.SUPABASE_URL}/storage/v1/object/{s.STORAGE_BUCKET_PRIVATE}/{path}"
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, content=data, headers={"Authorization": f"Bearer {s.SUPABASE_SERVICE_KEY}",
                                                              "x-upsert": "false"})
            if r.status_code >= 300:
                raise StorageError("The upload could not be stored. Try again.")
        return f"supabase:{path}"
    LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
    (LOCAL_ROOT / path).write_bytes(data)
    return f"local:{path}"


def read_local(path: str) -> bytes:
    kind, name = path.split(":", 1)
    if kind != "local" or "/" in name or ".." in name:
        raise StorageError("Not a local file.")
    return (LOCAL_ROOT / name).read_bytes()
