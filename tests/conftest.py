"""Pytest configuration, database fixtures, and synthetic geospatial file generators."""

import io
import os
import tempfile
import zipfile
import pytest
from fastapi.testclient import TestClient
import geopandas as gpd
from shapely.geometry import LineString, Point, Polygon
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.dependencies import get_db
from app.db.session import Base
from app.main import app

# Create a temporary SQLite database for test execution
TEST_DB_FILE = os.path.join(tempfile.gettempdir(), "test_geospatial.db")
TEST_DB_URL = f"sqlite:///{TEST_DB_FILE}"

test_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create test tables before test session and clean up file afterwards."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except Exception:
            pass


@pytest.fixture
def db_session():
    """Provide a clean database session per test with rollback/cleanup."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient configured with test database session override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def synthetic_shapefile_zip() -> bytes:
    """Generate in-memory zipped Shapefile containing 3 Polygons in EPSG:4326."""
    features = [
        {
            "name": "Bangalore Central Park",
            "category": "Recreation",
            "geometry": Polygon([
                (77.5900, 12.9700),
                (77.5950, 12.9700),
                (77.5950, 12.9750),
                (77.5900, 12.9750),
                (77.5900, 12.9700),
            ]),
        },
        {
            "name": "Cubbon Park East Zone",
            "category": "Recreation",
            "geometry": Polygon([
                (77.6000, 12.9750),
                (77.6050, 12.9750),
                (77.6050, 12.9800),
                (77.6000, 12.9800),
                (77.6000, 12.9750),
            ]),
        },
        {
            "name": "Lalbagh Botanical Zone",
            "category": "Botanical",
            "geometry": Polygon([
                (77.5850, 12.9500),
                (77.5920, 12.9500),
                (77.5920, 12.9580),
                (77.5850, 12.9580),
                (77.5850, 12.9500),
            ]),
        },
    ]

    gdf = gpd.GeoDataFrame(features, crs="EPSG:4326")

    with tempfile.TemporaryDirectory() as td:
        shp_path = os.path.join(td, "test_features.shp")
        gdf.to_file(shp_path)

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in os.listdir(td):
                zf.write(os.path.join(td, fname), arcname=fname)

        return zip_buf.getvalue()


@pytest.fixture
def synthetic_projected_shapefile_zip() -> bytes:
    """Generate in-memory zipped Shapefile in a projected metric CRS (EPSG:32643 - UTM Zone 43N)."""
    # Two polygon parcels: 1000m x 1000m (1,000,000 m²) and 500m x 1000m (500,000 m²)
    features = [
        {
            "name": "Metric Test Parcel Alpha",
            "category": "Commercial",
            "geometry": Polygon([
                (780000.0, 1435000.0),
                (781000.0, 1435000.0),
                (781000.0, 1436000.0),
                (780000.0, 1436000.0),
                (780000.0, 1435000.0),
            ]),
        },
        {
            "name": "Metric Test Parcel Beta",
            "category": "Industrial",
            "geometry": Polygon([
                (782000.0, 1435000.0),
                (782500.0, 1435000.0),
                (782500.0, 1436000.0),
                (782000.0, 1436000.0),
                (782000.0, 1435000.0),
            ]),
        },
    ]

    gdf = gpd.GeoDataFrame(features, crs="EPSG:32643")

    with tempfile.TemporaryDirectory() as td:
        shp_path = os.path.join(td, "projected_features.shp")
        gdf.to_file(shp_path)

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in os.listdir(td):
                zf.write(os.path.join(td, fname), arcname=fname)

        return zip_buf.getvalue()


@pytest.fixture
def synthetic_kml_bytes() -> bytes:
    """Generate valid KML file with Polygon, LineString, and Point placemarks."""
    kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Synthetic KML Sample</name>
    <Placemark>
      <name>Sample Park Polygon</name>
      <description>Urban green space</description>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              77.5900,12.9700,0
              77.5950,12.9700,0
              77.5950,12.9750,0
              77.5900,12.9750,0
              77.5900,12.9700,0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>Sample Greenway Line</name>
      <description>Bicycle path</description>
      <LineString>
        <coordinates>
          77.6000,12.9750,0
          77.6050,12.9780,0
          77.6100,12.9800,0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Waypoint Point</name>
      <description>Reference marker</description>
      <Point>
        <coordinates>77.6050,12.9755,0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>"""
    return kml_content.encode("utf-8")


@pytest.fixture
def zip_slip_bytes() -> bytes:
    """Generate malicious zip archive attempting directory traversal (Zip Slip)."""
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("../../etc/cron.d/malicious.txt", b"malicious content")
    return zip_buf.getvalue()


@pytest.fixture
def corrupted_zip_bytes() -> bytes:
    """Generate invalid/corrupted zip bytes."""
    return b"PK\x03\x04this is totally corrupted data and not a valid zip archive"


@pytest.fixture
def malformed_kml_bytes() -> bytes:
    """Generate malformed/unparseable XML bytes."""
    return b"<kml><unclosed_tag>Corrupted content without closing tags"
