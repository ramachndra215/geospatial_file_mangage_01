# Geospatial File Measurement API

A production-ready FastAPI backend designed to ingest geospatial vector files (**zipped ESRI Shapefiles** and **Google Earth KML**), extract geographic features, automatically determine appropriate metric projected Coordinate Reference Systems (CRS), calculate polygon areas ($m^2$, $km^2$) and line lengths ($m$, $km$), and persist metadata and measurement results in an SQLite database.

---

## 🌟 Key Features

- **Multi-Format Ingestion**: Supports `.kml` files and `.zip` archives containing ESRI Shapefiles (`.shp`, `.shx`, `.dbf`, `.prj`).
- **Dynamic Projected Metric Measurements**:
  - **Never calculates planar measurements in longitude/latitude degrees**.
  - Dynamically detects the optimal **UTM (Universal Transverse Mercator)** projection zone based on each feature's geographic centroid.
  - Falls back to equal-area projections (e.g., **EPSG:6933**) for extreme polar latitudes ($|\text{lat}| > 84^\circ$).
  - For pre-projected datasets, honors native projections and automatically normalizes non-metric units (e.g., feet, US survey feet) to standard SI units.
- **Strict Geometry Support & Graceful Edge Cases**:
  - **Polygons / MultiPolygons**: Area in square metres ($m^2$) and square kilometres ($km^2$).
  - **LineStrings / MultiLineStrings**: Length in metres ($m$) and kilometres ($km$).
  - **Points / MultiPoints**: Status `skipped` with clear diagnostic notes.
  - **Invalid Geometries**: Automatically repaired using `shapely.make_valid` where possible; reported with explanatory warnings if unrecoverable.
  - **Empty Geometries**: Gracefully assigned zero measurement and flagged with warnings.
- **SQLite Persistence**:
  - Automatically stores file records and individual feature measurements so APIs continue working across request boundaries and server restarts.
- **Security & Robustness**:
  - **Zip Slip & Path Traversal Protection**: Inspects all archive members, blocks absolute and relative directory escapes (`..`), and verifies destination bounds.
  - **Zip Bomb Guard**: Enforces uncompressed byte size thresholds.
  - **Upload Size Limits**: Configurable file upload size thresholds (default: 50 MB) streamed and validated in chunks.
  - **Sanitized Error Handling**: Catch-all exception handling ensuring internal server traces are never leaked to clients.
- **Interactive API Documentation**: Swagger UI (`/docs`) and ReDoc (`/redoc`) available out of the box.

---

## 🏗️ Project Architecture

```
geospatial_file_mangage_01/
├── app/
│   ├── __init__.py
│   ├── config.py                 # Application settings (Pydantic BaseSettings, limits, DB URL)
│   ├── main.py                   # FastAPI application, CORS, lifespan, and exception handlers
│   ├── api/
│   │   ├── __init__.py
│   │   ├── dependencies.py       # DB session dependency injection
│   │   ├── files.py              # File upload, status query, and measurement endpoints
│   │   └── root.py               # Welcome and /health endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── exceptions.py         # Structured application exception hierarchy
│   │   └── security.py           # Safe ZIP decompression and upload validation
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py            # SQLite engine, sessionmaker, and table initializer
│   │   └── models.py             # SQLAlchemy models (FileRecord, FeatureRecord)
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── geospatial.py         # Pydantic request and response schemas
│   └── services/
│       ├── __init__.py
│       ├── crs_service.py        # CRS resolution, UTM projection, and unit conversion
│       ├── measurement_service.py# Geometry metric measurement engine (areas, lengths, repair)
│       ├── file_parser.py        # Shapefile and KML reader with temporary cleanup
│       └── file_processor.py     # Master orchestrator integrating parsing, measurement, and DB
├── samples/
│   ├── sample_data.kml           # Valid sample KML (Polygon, LineString, Point)
│   ├── sample_shapefile.zip      # Valid multi-layer Shapefile ZIP (Polygon, Line, Point)
│   └── README.md                 # Usage documentation for sample testing
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Test database fixtures and synthetic geospatial generators
│   ├── test_api.py               # Integration tests for all endpoints and persistence
│   ├── test_measurements.py      # Unit tests for polygon/line/point/CRS measurement logic
│   └── test_security.py          # Security tests for zip slip, size limits, and invalid files
├── .env.example                  # Environment configuration template
├── .gitignore                    # Python, SQLite, and virtual environment ignore rules
├── requirements.txt              # Pinned Python package dependencies
└── README.md                     # Documentation and setup instructions
```

---

## 🛠️ Tech Stack

- **Language**: Python 3.11+
- **Web Framework**: [FastAPI](https://fastapi.tiangolo.com/) 0.111+
- **ASGI Server**: [Uvicorn](https://www.uvicorn.org/)
- **Geospatial Processing**: [GeoPandas](https://geopandas.org/), [Shapely](https://shapely.readthedocs.io/), [PyProj](https://pyproj4.github.io/pyproj/), [Fiona](https://fiona.readthedocs.io/), [Pyogrio](https://pyogrio.readthedocs.io/)
- **Database & ORM**: SQLite, [SQLAlchemy](https://www.sqlalchemy.org/) 2.0+
- **Validation & Serialization**: [Pydantic](https://docs.pydantic.dev/) v2, `pydantic-settings`
- **Testing**: [pytest](https://docs.pytest.org/), [HTTPX](https://www.python-httpx.org/)

---

## 🚀 Installation & Local Setup

### 1. Clone the Repository
```bash
git clone https://github.com/ramachndra215/geospatial_file_mangage_01.git
cd geospatial_file_mangage_01
```

### 2. Create and Activate a Virtual Environment
```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the template configuration file:
```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

---

## 🏃 Running the Application

Start the FastAPI application using Uvicorn:
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Once started:
- **Interactive Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 📡 API Specification & Endpoints

### 1. `GET /` — Welcome Landing
Returns a greeting and links to documentation.
```bash
curl -X GET "http://localhost:8000/"
```
**Response (200 OK)**:
```json
{
  "message": "Welcome to the Geospatial File Measurement API.",
  "docs_url": "/docs",
  "version": "1.0.0"
}
```

---

### 2. `GET /health` — Health Check
Checks application status and verifies SQLite connectivity.
```bash
curl -X GET "http://localhost:8000/health"
```
**Response (200 OK)**:
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
```

---

### 3. `POST /api/files/` — Upload & Measure Geospatial File
Uploads a `.kml` or `.zip` Shapefile, extracts features, calculates metric measurements, and stores them in SQLite.
```bash
curl -X POST "http://localhost:8000/api/files/" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@sample_data.kml"
```
**Response (201 Created)**:
```json
{
  "message": "File processed successfully and measurements calculated.",
  "file": {
    "id": "e73dcfc8-cd3b-445b-be7c-eb07f7167423",
    "filename": "sample_data.kml",
    "file_type": "kml",
    "file_size_bytes": 1048,
    "upload_timestamp": "2026-10-10T07:45:00Z",
    "status": "completed",
    "total_features": 3,
    "source_crs": "EPSG:4326",
    "geometry_summary": {
      "Polygon": 1,
      "LineString": 1,
      "Point": 1
    },
    "error_message": null
  }
}
```

---

### 4. `GET /api/files/{id}/` — File Metadata & Processing Status
Fetches metadata, geometry breakdowns, and processing status for an uploaded file.
```bash
curl -X GET "http://localhost:8000/api/files/e73dcfc8-cd3b-445b-be7c-eb07f7167423/"
```
**Response (200 OK)**:
```json
{
  "id": "e73dcfc8-cd3b-445b-be7c-eb07f7167423",
  "filename": "sample_data.kml",
  "file_type": "kml",
  "file_size_bytes": 1048,
  "upload_timestamp": "2026-10-10T07:45:00Z",
  "status": "completed",
  "total_features": 3,
  "source_crs": "EPSG:4326",
  "geometry_summary": {
    "Polygon": 1,
    "LineString": 1,
    "Point": 1
  },
  "error_message": null
}
```

---

### 5. `GET /api/files/{id}/measurements/` — Feature Measurement Results
Fetches every feature, its GeoJSON representation, attribute properties, source CRS, measurement CRS used, and calculated metric values.
```bash
curl -X GET "http://localhost:8000/api/files/e73dcfc8-cd3b-445b-be7c-eb07f7167423/measurements/"
```
**Response (200 OK)**:
```json
{
  "file_id": "e73dcfc8-cd3b-445b-be7c-eb07f7167423",
  "filename": "sample_data.kml",
  "source_crs": "EPSG:4326",
  "total_features": 3,
  "features": [
    {
      "id": 1,
      "feature_index": 0,
      "feature_identifier": "Sample Park Polygon",
      "geometry_type": "Polygon",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[77.59, 12.97], [77.595, 12.97], [77.595, 12.975], [77.59, 12.975], [77.59, 12.97]]]
      },
      "properties": {
        "name": "Sample Park Polygon",
        "description": "Urban green space"
      },
      "source_crs": "EPSG:4326",
      "measurement_crs": "EPSG:32643 (UTM Zone 43N)",
      "measurement_status": "success",
      "measurements": {
        "area_sq_m": 300422.7998,
        "area_sq_km": 0.300423,
        "length_m": null,
        "length_km": null
      },
      "warnings": []
    },
    {
      "id": 2,
      "feature_index": 1,
      "feature_identifier": "Sample Greenway Line",
      "geometry_type": "LineString",
      "geometry": {
        "type": "LineString",
        "coordinates": [[77.6, 12.975], [77.605, 12.978], [77.61, 12.98]]
      },
      "properties": {
        "name": "Sample Greenway Line"
      },
      "source_crs": "EPSG:4326",
      "measurement_crs": "EPSG:32643 (UTM Zone 43N)",
      "measurement_status": "success",
      "measurements": {
        "area_sq_m": null,
        "area_sq_km": null,
        "length_m": 1215.3412,
        "length_km": 1.215341
      },
      "warnings": []
    },
    {
      "id": 3,
      "feature_index": 2,
      "feature_identifier": "Waypoint Point",
      "geometry_type": "Point",
      "geometry": {
        "type": "Point",
        "coordinates": [77.605, 12.9755]
      },
      "properties": {
        "name": "Waypoint Point"
      },
      "source_crs": "EPSG:4326",
      "measurement_crs": null,
      "measurement_status": "skipped",
      "measurements": {
        "area_sq_m": null,
        "area_sq_km": null,
        "length_m": null,
        "length_km": null
      },
      "warnings": ["Point geometry does not require area or length measurement."]
    }
  ]
}
```

---

## 🧪 Automated Testing

All tests use self-contained synthetic fixtures (no external network or downloads required).

Run the full test suite with verbose output:
```bash
pytest -v
```

### Test Coverage Highlights:
- **`tests/test_api.py`**:
  - `GET /` and `GET /health` status verification.
  - KML upload (`POST /api/files/`) and metadata validation.
  - Zipped Shapefile upload and feature extraction.
  - `GET /api/files/{id}/` and `GET /api/files/{id}/measurements/` feature and metric verification.
  - Non-existent resource lookups returning HTTP 404 (`NOT_FOUND`).
  - Pre-projected metric shapefiles (UTM Zone 43N).
  - SQLite database persistence across independent query sessions.
  - Pagination (`skip` / `limit`) on `/api/files/`.
  - Malformed XML KML rejection (HTTP 400).
- **`tests/test_measurements.py`**:
  - Verification that **no planar measurements are calculated in degrees**.
  - Polygon & MultiPolygon areas ($m^2$, $km^2$) under geographic and projected systems.
  - LineString & MultiLineString lengths ($m$, $km$).
  - Points skipped with diagnostic warnings.
  - Self-intersecting "bowtie" polygon automatic repair using `shapely.make_valid`.
  - Empty geometry handling.
  - Polar latitude coordinates handling with equal-area projections (EPSG:6933).
  - GeometryCollection aggregate measurements.
- **`tests/test_security.py`**:
  - **Zip Slip protection**: Malicious paths (`../../...`) rejected with HTTP 400 (`PATH_TRAVERSAL_DETECTED`).
  - **File size enforcement**: Uploads exceeding limit rejected with HTTP 413 (`FILE_SIZE_EXCEEDED`).
  - **Extension filter**: Rejection of disallowed extensions (.exe, .sh, .txt).
  - **Corrupted files**: Corrupted archives rejected with HTTP 400 (`FILE_VALIDATION_ERROR`).
  - **Missing Shapefile**: Archives missing `.shp` files rejected with HTTP 400.

---

## 🚢 Pushing to GitHub

To commit and push the completed implementation to your repository:

```bash
# 1. Review status of modified and new files
git status

# 2. Stage all files
git add .

# 3. Create a commit
git commit -m "feat: complete Geospatial File Measurement API implementation with tests, SQLite persistence, and docs"

# 4. Push to main branch
git push origin main
```
