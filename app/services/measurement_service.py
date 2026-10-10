"""Service for calculating polygon areas and line lengths with unit scaling and validation."""

from typing import Any, Dict, List, Optional, Tuple
from pyproj import CRS
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
import shapely.validation

from app.services.crs_service import CRSService


class MeasurementOutcome:
    """Encapsulates the measurement results and diagnostic metadata for a geometry."""

    def __init__(
        self,
        geometry_type: str,
        geojson: Dict[str, Any],
        measurement_crs: Optional[str] = None,
        area_sq_m: Optional[float] = None,
        area_sq_km: Optional[float] = None,
        length_m: Optional[float] = None,
        length_km: Optional[float] = None,
        measurement_status: str = "success",
        warnings: Optional[List[str]] = None,
    ):
        self.geometry_type = geometry_type
        self.geojson = geojson
        self.measurement_crs = measurement_crs
        self.area_sq_m = area_sq_m
        self.area_sq_km = area_sq_km
        self.length_m = length_m
        self.length_km = length_km
        self.measurement_status = measurement_status
        self.warnings = warnings or []


class MeasurementService:
    """Performs geometry validation, metric measurement, and warning generation."""

    @classmethod
    def measure_feature(
        cls,
        geometry: Optional[BaseGeometry],
        source_crs: Optional[CRS],
        crs_warning: Optional[str] = None,
    ) -> MeasurementOutcome:
        """Measure an individual geometry feature according to its type and validity."""
        warnings: List[str] = []
        if crs_warning:
            warnings.append(crs_warning)

        # Handle None or Missing geometry
        if geometry is None:
            return MeasurementOutcome(
                geometry_type="None",
                geojson={},
                measurement_status="skipped",
                warnings=warnings + ["Geometry is null or missing."],
            )

        geom_type = geometry.geom_type

        # Generate GeoJSON mapping for the original geometry
        try:
            geojson = mapping(geometry)
        except Exception as e:
            geojson = {}
            warnings.append(f"Failed to generate GeoJSON mapping: {str(e)}")

        # Handle Empty Geometry
        if geometry.is_empty:
            return MeasurementOutcome(
                geometry_type=geom_type,
                geojson=geojson,
                area_sq_m=0.0 if "Polygon" in geom_type else None,
                area_sq_km=0.0 if "Polygon" in geom_type else None,
                length_m=0.0 if "Line" in geom_type else None,
                length_km=0.0 if "Line" in geom_type else None,
                measurement_status="skipped",
                warnings=warnings + ["Geometry is empty."],
            )

        # Handle Points and MultiPoints (requirement: Points require no measurement)
        if geom_type in ("Point", "MultiPoint"):
            return MeasurementOutcome(
                geometry_type=geom_type,
                geojson=geojson,
                measurement_status="skipped",
                warnings=warnings + ["Point geometry does not require area or length measurement."],
            )

        # Validate geometry; attempt make_valid if self-intersecting or invalid
        clean_geom = geometry
        if not clean_geom.is_valid:
            try:
                repaired = shapely.make_valid(clean_geom)
                if repaired.is_valid and not repaired.is_empty:
                    clean_geom = repaired
                    warnings.append("Geometry was invalid and was automatically repaired using make_valid.")
                else:
                    reason = shapely.validation.explain_validity(geometry)
                    warnings.append(f"Geometry is invalid ({reason}) and could not be repaired.")
                    return MeasurementOutcome(
                        geometry_type=geom_type,
                        geojson=geojson,
                        measurement_status="failed",
                        warnings=warnings,
                    )
            except Exception as e:
                warnings.append(f"Geometry repair failed: {str(e)}")
                return MeasurementOutcome(
                    geometry_type=geom_type,
                    geojson=geojson,
                    measurement_status="failed",
                    warnings=warnings,
                )

        # Transform into a suitable projected CRS (e.g. UTM) for true metric measurement
        proj_geom, meas_crs, scale, proj_warning = CRSService.transform_for_measurement(clean_geom, source_crs)
        if proj_warning:
            warnings.append(proj_warning)

        # Calculate Polygons and MultiPolygons
        if "Polygon" in geom_type:
            try:
                raw_area = proj_geom.area
                # Apply scale factor if source projected CRS had non-metre units
                area_m2 = raw_area * (scale ** 2)
                area_km2 = area_m2 / 1_000_000.0

                return MeasurementOutcome(
                    geometry_type=geom_type,
                    geojson=geojson,
                    measurement_crs=meas_crs,
                    area_sq_m=round(area_m2, 4),
                    area_sq_km=round(area_km2, 6),
                    measurement_status="success",
                    warnings=warnings,
                )
            except Exception as e:
                warnings.append(f"Polygon area calculation failed: {str(e)}")
                return MeasurementOutcome(
                    geometry_type=geom_type,
                    geojson=geojson,
                    measurement_crs=meas_crs,
                    measurement_status="failed",
                    warnings=warnings,
                )

        # Calculate LineStrings and MultiLineStrings
        if "LineString" in geom_type or "LinearRing" in geom_type:
            try:
                raw_length = proj_geom.length
                length_m = raw_length * scale
                length_km = length_m / 1000.0

                return MeasurementOutcome(
                    geometry_type=geom_type,
                    geojson=geojson,
                    measurement_crs=meas_crs,
                    length_m=round(length_m, 4),
                    length_km=round(length_km, 6),
                    measurement_status="success",
                    warnings=warnings,
                )
            except Exception as e:
                warnings.append(f"Line length calculation failed: {str(e)}")
                return MeasurementOutcome(
                    geometry_type=geom_type,
                    geojson=geojson,
                    measurement_crs=meas_crs,
                    measurement_status="failed",
                    warnings=warnings,
                )

        # Handle GeometryCollection or other compound geometries
        if geom_type == "GeometryCollection":
            try:
                total_area_m2 = 0.0
                total_len_m = 0.0
                has_polygon = False
                has_line = False

                for part in getattr(proj_geom, "geoms", []):
                    if "Polygon" in part.geom_type:
                        total_area_m2 += part.area * (scale ** 2)
                        has_polygon = True
                    elif "LineString" in part.geom_type:
                        total_len_m += part.length * scale
                        has_line = True

                warnings.append("GeometryCollection encountered: calculated aggregate area and/or length of parts.")
                return MeasurementOutcome(
                    geometry_type=geom_type,
                    geojson=geojson,
                    measurement_crs=meas_crs,
                    area_sq_m=round(total_area_m2, 4) if has_polygon else None,
                    area_sq_km=round(total_area_m2 / 1_000_000.0, 6) if has_polygon else None,
                    length_m=round(total_len_m, 4) if has_line else None,
                    length_km=round(total_len_m / 1000.0, 6) if has_line else None,
                    measurement_status="success",
                    warnings=warnings,
                )
            except Exception as e:
                warnings.append(f"GeometryCollection measurement failed: {str(e)}")
                return MeasurementOutcome(
                    geometry_type=geom_type,
                    geojson=geojson,
                    measurement_status="failed",
                    warnings=warnings,
                )

        # Fallback for any other geometry type
        warnings.append(f"Unsupported geometry type '{geom_type}' skipped.")
        return MeasurementOutcome(
            geometry_type=geom_type,
            geojson=geojson,
            measurement_status="skipped",
            warnings=warnings,
        )
