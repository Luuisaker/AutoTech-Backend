from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from src.config.settings import settings

UPLOAD_BASE_DIR = Path(settings.UPLOAD_DIR)


async def save_upload_file(upload_file: UploadFile, subdir: str) -> str:
    dir_path = UPLOAD_BASE_DIR / subdir
    dir_path.mkdir(parents=True, exist_ok=True)

    ext = Path(upload_file.filename or "file").suffix if upload_file.filename else ""
    unique_name = f"{uuid4()}{ext}"
    file_path = dir_path / unique_name

    content = await upload_file.read()
    file_path.write_bytes(content)

    return f"/uploads/{subdir}/{unique_name}"
