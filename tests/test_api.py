"""Integration tests for all REST API endpoints and SQLite persistence."""

import pytest


def test_root_endpoint(client):
    """Verify GET / returns welcome message and documentation links."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Welcome" in data["message"]
    assert data["docs_url"] == "/docs"
    assert "version" in data


def test_health_endpoint(client):
    """Verify GET /health returns application and database status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_upload_kml_file(client, synthetic_kml_bytes):
    """Verify POST /api/files/ processes KML and returns 201 with summary."""
    response = client.post(
        "/api/files/",
        files={"file": ("sample_places.kml", synthetic_kml_bytes, "application/vnd.google-earth.kml+xml")},
    )
    assert response.status_code == 201
    data = response.json()
    file_info = data["file"]

    assert file_info["filename"] == "sample_places.kml"
    assert file_info["file_type"] == "kml"
    assert file_info["status"] == "completed"
    assert file_info["total_features"] == 3
    assert file_info["source_crs"] == "EPSG:4326"
    assert file_info["geometry_summary"].get("Polygon") == 1
    assert file_info["geometry_summary"].get("LineString") == 1
    assert file_info["geometry_summary"].get("Point") == 1


def test_upload_shapefile_zip(client, synthetic_shapefile_zip):
    """Verify POST /api/files/ processes Shapefile ZIP and returns 201 with summary."""
    response = client.post(
        "/api/files/",
        files={"file": ("bangalore_features.zip", synthetic_shapefile_zip, "application/zip")},
    )
    assert response.status_code == 201
    data = response.json()
    file_info = data["file"]

    assert file_info["filename"] == "bangalore_features.zip"
    assert file_info["file_type"] == "shapefile_zip"
    assert file_info["status"] == "completed"
    assert file_info["total_features"] == 3
    assert file_info["source_crs"] == "EPSG:4326"


def test_get_file_metadata(client, synthetic_kml_bytes):
    """Verify GET /api/files/{id}/ returns metadata of an existing uploaded file."""
    # 1. Upload file
    upload_res = client.post(
        "/api/files/",
        files={"file": ("metadata_test.kml", synthetic_kml_bytes, "application/vnd.google-earth.kml+xml")},
    )
    file_id = upload_res.json()["file"]["id"]

    # 2. Retrieve metadata
    meta_res = client.get(f"/api/files/{file_id}/")
    assert meta_res.status_code == 200
    meta_data = meta_res.json()

    assert meta_data["id"] == file_id
    assert meta_data["filename"] == "metadata_test.kml"
    assert meta_data["total_features"] == 3
    assert meta_data["status"] == "completed"


def test_get_file_measurements(client, synthetic_kml_bytes):
    """Verify GET /api/files/{id}/measurements/ returns every feature and its calculations."""
    # 1. Upload KML containing Polygon, LineString, and Point
    upload_res = client.post(
        "/api/files/",
        files={"file": ("measure_test.kml", synthetic_kml_bytes, "application/vnd.google-earth.kml+xml")},
    )
    file_id = upload_res.json()["file"]["id"]

    # 2. Query measurements
    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    meas_data = meas_res.json()

    assert meas_data["file_id"] == file_id
    assert meas_data["total_features"] == 3
    features = meas_data["features"]
    assert len(features) == 3

    # Check Polygon feature
    polygon_feats = [f for f in features if f["geometry_type"] == "Polygon"]
    assert len(polygon_feats) == 1
    poly = polygon_feats[0]
    assert poly["measurement_status"] == "success"
    assert poly["measurements"]["area_sq_m"] > 250_000
    assert poly["measurements"]["area_sq_km"] > 0.25
    assert poly["measurements"]["length_m"] is None
    assert "EPSG:32643" in poly["measurement_crs"]
    assert poly["geometry"]["type"] == "Polygon"

    # Check LineString feature
    line_feats = [f for f in features if f["geometry_type"] == "LineString"]
    assert len(line_feats) == 1
    line = line_feats[0]
    assert line["measurement_status"] == "success"
    assert line["measurements"]["length_m"] > 1000
    assert line["measurements"]["length_km"] > 1.0
    assert line["measurements"]["area_sq_m"] is None
    assert "EPSG:32643" in line["measurement_crs"]

    # Check Point feature
    point_feats = [f for f in features if f["geometry_type"] == "Point"]
    assert len(point_feats) == 1
    point = point_feats[0]
    assert point["measurement_status"] == "skipped"
    assert point["measurements"]["area_sq_m"] is None
    assert point["measurements"]["length_m"] is None
    assert any("Point geometry does not require" in w for w in point["warnings"])


def test_non_existent_file_returns_404(client):
    """Verify requesting non-existent file ID returns HTTP 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    res1 = client.get(f"/api/files/{fake_id}/")
    assert res1.status_code == 404
    assert res1.json()["error_code"] == "NOT_FOUND"

    res2 = client.get(f"/api/files/{fake_id}/measurements/")
    assert res2.status_code == 404
    assert res2.json()["error_code"] == "NOT_FOUND"


def test_projected_shapefile_measurements(client, synthetic_projected_shapefile_zip):
    """Verify upload and measurement of projected metric shapefile (EPSG:32643)."""
    upload_res = client.post(
        "/api/files/",
        files={"file": ("projected_grid.zip", synthetic_projected_shapefile_zip, "application/zip")},
    )
    assert upload_res.status_code == 201
    file_id = upload_res.json()["file"]["id"]

    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    data = meas_res.json()

    assert data["total_features"] == 2
    poly1 = [f for f in data["features"] if f["feature_index"] == 0][0]
    assert pytest.approx(poly1["measurements"]["area_sq_m"], rel=1e-3) == 1_000_000.0
    assert pytest.approx(poly1["measurements"]["area_sq_km"], rel=1e-3) == 1.0

    poly2 = [f for f in data["features"] if f["feature_index"] == 1][0]
    assert pytest.approx(poly2["measurements"]["area_sq_m"], rel=1e-3) == 500_000.0
    assert pytest.approx(poly2["measurements"]["area_sq_km"], rel=1e-3) == 0.5


def test_persistence_across_multiple_queries(client, synthetic_kml_bytes):
    """Verify that file and feature records persist in SQLite across separate requests."""
    # Step 1: Upload
    upload_res = client.post(
        "/api/files/",
        files={"file": ("persist_test.kml", synthetic_kml_bytes, "application/vnd.google-earth.kml+xml")},
    )
    file_id = upload_res.json()["file"]["id"]

    # Step 2: Query metadata immediately
    meta1 = client.get(f"/api/files/{file_id}/").json()

    # Step 3: Query measurements
    meas1 = client.get(f"/api/files/{file_id}/measurements/").json()

    # Step 4: Query list of all files
    list_res = client.get("/api/files/").json()
    assert any(f["id"] == file_id for f in list_res)

    # Step 5: Query metadata again (confirming persistence in SQLite)
    meta2 = client.get(f"/api/files/{file_id}/").json()
    assert meta1["id"] == meta2["id"]
    assert meta1["total_features"] == meta2["total_features"]
    assert len(meas1["features"]) == 3


def test_malformed_kml_upload_returns_400(client, malformed_kml_bytes):
    """Verify that uploading malformed/corrupted XML as .kml returns HTTP 400."""
    res = client.post(
        "/api/files/",
        files={"file": ("broken.kml", malformed_kml_bytes, "application/vnd.google-earth.kml+xml")},
    )
    assert res.status_code == 400
    data = res.json()
    assert data["error_code"] == "FILE_VALIDATION_ERROR"


def test_list_files_pagination(client, synthetic_kml_bytes):
    """Verify pagination support (skip, limit) on GET /api/files/."""
    # Upload 2 files
    client.post("/api/files/", files={"file": ("f1.kml", synthetic_kml_bytes, "application/xml")})
    client.post("/api/files/", files={"file": ("f2.kml", synthetic_kml_bytes, "application/xml")})

    res = client.get("/api/files/?skip=0&limit=1")
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_upload_committed_sample_kml(client):
    """Verify that the committed sample KML file processes successfully."""
    import os
    kml_path = os.path.join(os.path.dirname(__file__), "..", "samples", "sample_data.kml")
    with open(kml_path, "rb") as f:
        res = client.post("/api/files/", files={"file": ("sample_data.kml", f, "application/vnd.google-earth.kml+xml")})

    assert res.status_code == 201
    file_id = res.json()["file"]["id"]
    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    features = meas_res.json()["features"]
    assert len(features) == 3
    types = {f["geometry_type"] for f in features}
    assert types == {"Polygon", "LineString", "Point"}


def test_upload_committed_sample_shapefile_zip(client):
    """Verify that the committed sample Shapefile ZIP archive processes successfully."""
    import os
    zip_path = os.path.join(os.path.dirname(__file__), "..", "samples", "sample_shapefile.zip")
    with open(zip_path, "rb") as f:
        res = client.post("/api/files/", files={"file": ("sample_shapefile.zip", f, "application/zip")})

    assert res.status_code == 201
    file_id = res.json()["file"]["id"]
    meas_res = client.get(f"/api/files/{file_id}/measurements/")
    assert meas_res.status_code == 200
    features = meas_res.json()["features"]
    assert len(features) == 3
    types = {f["geometry_type"] for f in features}
    assert types == {"Polygon", "LineString", "Point"}

