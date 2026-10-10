"""Security utilities for file validation, size limits, and safe zip extraction."""

import io
import os
import zipfile
from typing import List, Tuple
from fastapi import UploadFile

from app.core.exceptions import (
    FileSizeExceededError,
    FileValidationError,
    PathTraversalError,
)


def validate_file_extension(filename: str, allowed_extensions: List[str]) -> str:
    """Validate that the uploaded filename ends with an allowed extension.

    Returns the normalized lowercased extension.
    """
    if not filename or "." not in filename:
        raise FileValidationError("Invalid filename: missing extension.")

    ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext not in [e.lower() for e in allowed_extensions]:
        allowed_str = ", ".join(allowed_extensions)
        raise FileValidationError(
            f"Unsupported file extension '{ext}'. Allowed extensions are: {allowed_str}"
        )
    return ext


async def validate_and_read_upload(
    upload_file: UploadFile,
    max_size_bytes: int,
    chunk_size: int = 1024 * 1024,
) -> bytes:
    """Read an uploaded file in chunks, enforcing the maximum upload size limit."""
    content = bytearray()
    total_bytes = 0

    while True:
        chunk = await upload_file.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > max_size_bytes:
            raise FileSizeExceededError(
                f"File size exceeds the allowed limit of {max_size_bytes / (1024 * 1024):.1f} MB."
            )
        content.extend(chunk)

    if total_bytes == 0:
        raise FileValidationError("Uploaded file is empty.")

    return bytes(content)


def safe_extract_zip(
    zip_bytes: bytes,
    target_dir: str,
    max_uncompressed_bytes: int = 200 * 1024 * 1024,
) -> List[str]:
    """Safely extract a zip archive to target_dir with strict path traversal and zip-bomb guards.

    Returns list of absolute extracted file paths.
    """
    target_dir_abs = os.path.abspath(target_dir)

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        raise FileValidationError("Uploaded zip file is corrupted or not a valid archive.") from e

    extracted_files: List[str] = []
    total_uncompressed_size = 0

    with zf:
        infolist = zf.infolist()
        if not infolist:
            raise FileValidationError("Zip archive is empty.")

        for member in infolist:
            # Check for path traversal markers
            filename = member.filename
            if os.path.isabs(filename) or filename.startswith(("/", "\\")):
                raise PathTraversalError(f"Absolute path detected in zip archive: {filename}")

            parts = os.path.normpath(filename).replace("\\", "/").split("/")
            if ".." in parts:
                raise PathTraversalError(f"Directory traversal ('..') detected in zip archive: {filename}")

            # Check uncompressed size limit
            total_uncompressed_size += member.file_size
            if total_uncompressed_size > max_uncompressed_bytes:
                raise FileSizeExceededError(
                    f"Uncompressed archive size exceeds limit of {max_uncompressed_bytes / (1024 * 1024):.1f} MB."
                )

            # Check target destination path
            dest_path = os.path.abspath(os.path.join(target_dir_abs, filename))
            try:
                common_prefix = os.path.commonpath([target_dir_abs, dest_path])
            except ValueError:
                raise PathTraversalError(f"Illegal path target detected in zip: {filename}")

            if common_prefix != target_dir_abs:
                raise PathTraversalError(f"Archive entry escapes destination directory: {filename}")

            if member.is_dir():
                os.makedirs(dest_path, exist_ok=True)
                continue

            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with zf.open(member) as source, open(dest_path, "wb") as target:
                target.write(source.read())

            extracted_files.append(dest_path)

    return extracted_files
