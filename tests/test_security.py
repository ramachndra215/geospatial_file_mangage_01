"""Security tests for safe zip extraction, path traversal, file limits, and extensions."""

import io
import zipfile
import pytest
from app.config import settings


def test_zip_slip_path_traversal_protection(client, zip_slip_bytes):
    """Verify that archives with path traversal entries ('..') are rejected."""
    response = client.post(
        "/api/files/",
        files={"file": ("malicious.zip", zip_slip_bytes, "application/zip")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "PATH_TRAVERSAL_DETECTED"
    assert "traversal" in data["detail"].lower()


def test_upload_size_limit_enforced(client, monkeypatch):
    """Verify that uploads exceeding MAX_UPLOAD_SIZE_BYTES are rejected with HTTP 413."""
    # Temporarily set upload limit to 100 KB for test
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 100 * 1024)

    large_content = b"0" * (150 * 1024)  # 150 KB
    response = client.post(
        "/api/files/",
        files={"file": ("oversized.kml", large_content, "application/vnd.google-earth.kml+xml")},
    )
    assert response.status_code == 413
    data = response.json()
    assert data["error_code"] == "FILE_SIZE_EXCEEDED"


def test_disallowed_extension_rejected(client):
    """Verify that files with unapproved extensions (e.g. .exe, .sh, .txt) are rejected."""
    response = client.post(
        "/api/files/",
        files={"file": ("script.sh", b"#!/bin/bash\necho hello", "text/plain")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "FILE_VALIDATION_ERROR"
    assert "Unsupported file extension" in data["detail"]


def test_empty_file_rejected(client):
    """Verify that uploading an empty 0-byte file returns HTTP 400."""
    response = client.post(
        "/api/files/",
        files={"file": ("empty.kml", b"", "application/vnd.google-earth.kml+xml")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "FILE_VALIDATION_ERROR"
    assert "empty" in data["detail"].lower()


def test_corrupted_zip_archive_rejected(client, corrupted_zip_bytes):
    """Verify that corrupted zip files return HTTP 400."""
    response = client.post(
        "/api/files/",
        files={"file": ("corrupted.zip", corrupted_zip_bytes, "application/zip")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "FILE_VALIDATION_ERROR"


def test_zip_without_shp_file_rejected(client):
    """Verify that zip archives without any .shp files return HTTP 400."""
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("readme.txt", b"Just a text file, no shapefiles here.")

    response = client.post(
        "/api/files/",
        files={"file": ("no_shp.zip", zip_buf.getvalue(), "application/zip")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "FILE_VALIDATION_ERROR"
    assert ".shp" in data["detail"]
