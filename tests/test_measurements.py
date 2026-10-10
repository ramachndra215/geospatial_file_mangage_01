"""Unit tests for geometry measurement, CRS transformation, and edge cases."""

import pytest
from pyproj import CRS
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPolygon,
    Point,
    Polygon,
)

from app.services.crs_service import CRSService
from app.services.measurement_service import MeasurementService


def test_polygon_measurement_in_geographic_crs():
    """Verify polygon in degrees is transformed to UTM and measured in true square metres/kilometres.

    Crucial: Must NOT calculate planar area from longitude/latitude degrees!
    """
    # ~550m x ~550m box in Bangalore (~13° N, 77.6° E)
    poly = Polygon([
        (77.5900, 12.9700),
        (77.5950, 12.9700),
        (77.5950, 12.9750),
        (77.5900, 12.9750),
        (77.5900, 12.9700),
    ])

    outcome = MeasurementService.measure_feature(poly, source_crs=CRS.from_epsg(4326))

    assert outcome.measurement_status == "success"
    assert outcome.area_sq_m is not None
    assert outcome.area_sq_km is not None
    # 0.005 x 0.005 degrees squared would be 0.000025 if wrongly calculated in degrees!
    # In reality, 550m x 550m is approximately 300,000 sq metres.
    assert outcome.area_sq_m > 250_000
    assert outcome.area_sq_m < 350_000
    assert outcome.area_sq_km > 0.25
    assert outcome.area_sq_km < 0.35
    assert "EPSG:32643" in outcome.measurement_crs
    assert outcome.length_m is None


def test_polygon_measurement_in_projected_crs():
    """Verify polygon in projected metric CRS (EPSG:32643) calculates exact planar area."""
    # 1000m x 1000m square = 1,000,000 m² = 1.0 km²
    poly = Polygon([
        (780000.0, 1435000.0),
        (781000.0, 1435000.0),
        (781000.0, 1436000.0),
        (780000.0, 1436000.0),
        (780000.0, 1435000.0),
    ])

    outcome = MeasurementService.measure_feature(poly, source_crs=CRS.from_epsg(32643))

    assert outcome.measurement_status == "success"
    assert pytest.approx(outcome.area_sq_m, rel=1e-3) == 1_000_000.0
    assert pytest.approx(outcome.area_sq_km, rel=1e-3) == 1.0
    assert outcome.length_m is None
    assert "EPSG:32643" in outcome.measurement_crs


def test_multipolygon_measurement():
    """Verify MultiPolygon sums areas of component polygons correctly."""
    p1 = Polygon([(780000.0, 1435000.0), (780500.0, 1435000.0), (780500.0, 1435500.0), (780000.0, 1435500.0), (780000.0, 1435000.0)])
    p2 = Polygon([(781000.0, 1435000.0), (781500.0, 1435000.0), (781500.0, 1435500.0), (781000.0, 1435500.0), (781000.0, 1435000.0)])
    mp = MultiPolygon([p1, p2])

    outcome = MeasurementService.measure_feature(mp, source_crs=CRS.from_epsg(32643))

    assert outcome.measurement_status == "success"
    # Each is 500x500 = 250,000 m², sum = 500,000 m² = 0.5 km²
    assert pytest.approx(outcome.area_sq_m, rel=1e-3) == 500_000.0
    assert pytest.approx(outcome.area_sq_km, rel=1e-3) == 0.5


def test_linestring_measurement_in_geographic_crs():
    """Verify LineString in degrees is projected and measured in metres and kilometres."""
    line = LineString([(77.6000, 12.9750), (77.6100, 12.9760), (77.6200, 12.9770)])

    outcome = MeasurementService.measure_feature(line, source_crs=CRS.from_epsg(4326))

    assert outcome.measurement_status == "success"
    assert outcome.length_m is not None
    assert outcome.length_km is not None
    # ~2.1 km across Bangalore
    assert outcome.length_m > 1500.0
    assert outcome.length_m < 3000.0
    assert outcome.length_km > 1.5
    assert outcome.length_km < 3.0
    assert outcome.area_sq_m is None
    assert "EPSG:32643" in outcome.measurement_crs


def test_multilinestring_measurement():
    """Verify MultiLineString sums component line lengths correctly."""
    l1 = LineString([(780000.0, 1435000.0), (781000.0, 1435000.0)])  # 1000m
    l2 = LineString([(780000.0, 1436000.0), (780500.0, 1436000.0)])  # 500m
    mls = MultiLineString([l1, l2])

    outcome = MeasurementService.measure_feature(mls, source_crs=CRS.from_epsg(32643))

    assert outcome.measurement_status == "success"
    assert pytest.approx(outcome.length_m, rel=1e-3) == 1500.0
    assert pytest.approx(outcome.length_km, rel=1e-3) == 1.5


def test_points_require_no_measurement():
    """Verify Points require no measurement and return status 'skipped'."""
    pt = Point(77.6050, 12.9755)

    outcome = MeasurementService.measure_feature(pt, source_crs=CRS.from_epsg(4326))

    assert outcome.measurement_status == "skipped"
    assert outcome.area_sq_m is None
    assert outcome.length_m is None
    assert any("Point geometry does not require" in w for w in outcome.warnings)


def test_invalid_bowtie_polygon_auto_repair():
    """Verify self-intersecting polygon (bowtie) is repaired with make_valid."""
    # Self-intersecting polygon
    bowtie = Polygon([(0, 0), (2, 2), (2, 0), (0, 2), (0, 0)])
    assert not bowtie.is_valid

    outcome = MeasurementService.measure_feature(bowtie, source_crs=CRS.from_epsg(32643))

    assert outcome.measurement_status == "success"
    assert outcome.area_sq_m is not None
    assert outcome.area_sq_m > 0
    assert any("automatically repaired using make_valid" in w for w in outcome.warnings)


def test_empty_geometry_handling():
    """Verify empty geometries are gracefully handled without exceptions."""
    empty_poly = Polygon()
    assert empty_poly.is_empty

    outcome = MeasurementService.measure_feature(empty_poly, source_crs=CRS.from_epsg(4326))

    assert outcome.measurement_status == "skipped"
    assert outcome.area_sq_m == 0.0
    assert any("Geometry is empty" in w for w in outcome.warnings)


def test_unknown_crs_with_degree_coordinates():
    """Verify geometries with None CRS in degree ranges are safely assumed EPSG:4326."""
    poly = Polygon([(10.0, 20.0), (10.1, 20.0), (10.1, 20.1), (10.0, 20.1), (10.0, 20.0)])

    # No CRS provided
    crs_obj, crs_str, warning = CRSService.resolve_source_crs(None, sample_geometry=poly)

    assert crs_str == "EPSG:4326"
    assert "assumed EPSG:4326" in warning

    outcome = MeasurementService.measure_feature(poly, source_crs=crs_obj, crs_warning=warning)
    assert outcome.measurement_status == "success"
    assert outcome.area_sq_m is not None
    assert outcome.area_sq_m > 0
    assert any("assumed EPSG:4326" in w for w in outcome.warnings)


def test_polar_geometry_uses_equal_area_projection():
    """Verify polar geometries (|lat| > 84) use EPSG:6933 World Equal Area projection."""
    poly = Polygon([(0.0, 85.0), (1.0, 85.0), (1.0, 86.0), (0.0, 86.0), (0.0, 85.0)])

    outcome = MeasurementService.measure_feature(poly, source_crs=CRS.from_epsg(4326))

    assert outcome.measurement_status == "success"
    assert "EPSG:6933" in outcome.measurement_crs
    assert outcome.area_sq_m is not None
    assert outcome.area_sq_m > 0


def test_geometry_collection_measurement():
    """Verify GeometryCollection measures aggregate area of polygons and lengths of lines."""
    poly = Polygon([(780000.0, 1435000.0), (780500.0, 1435000.0), (780500.0, 1435500.0), (780000.0, 1435500.0), (780000.0, 1435000.0)])
    line = LineString([(780000.0, 1435000.0), (781000.0, 1435000.0)])
    gc = GeometryCollection([poly, line])

    outcome = MeasurementService.measure_feature(gc, source_crs=CRS.from_epsg(32643))

    assert outcome.measurement_status == "success"
    assert pytest.approx(outcome.area_sq_m, rel=1e-3) == 250_000.0
    assert pytest.approx(outcome.length_m, rel=1e-3) == 1000.0

