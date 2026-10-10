"""Service for Coordinate Reference System (CRS) inspection, UTM determination, and reprojection."""

import math
from typing import Any, Optional, Tuple
import pyproj
from pyproj import CRS, Transformer
import shapely.ops
from shapely.geometry.base import BaseGeometry


def get_linear_unit_factor(crs: CRS) -> Tuple[float, str]:
    """Determine the linear unit scale factor to metres from a CRS.

    Returns (scale_to_metres, unit_name).
    """
    try:
        if crs.axis_info and len(crs.axis_info) > 0:
            unit_name = (crs.axis_info[0].unit_name or "metre").lower()
            if "metre" in unit_name or "meter" in unit_name:
                return 1.0, "metre"
            if "us survey foot" in unit_name or "survey_ft" in unit_name:
                return 1200.0 / 3937.0, "us_survey_foot"
            if "foot" in unit_name or "ft" in unit_name:
                return 0.3048, "foot"
            if "kilometre" in unit_name or "kilometer" in unit_name:
                return 1000.0, "kilometre"
            if "mile" in unit_name:
                return 1609.344, "mile"
            if "yard" in unit_name:
                return 0.9144, "yard"
    except Exception:
        pass
    return 1.0, "metre"


def is_coordinate_in_degree_range(geometry: BaseGeometry) -> bool:
    """Check if geometry coordinates fall within valid longitude/latitude ranges [-180, 180] and [-90, 90]."""
    if geometry is None or geometry.is_empty:
        return True
    try:
        minx, miny, maxx, maxy = geometry.bounds
        return -180.0 <= minx <= 180.0 and -180.0 <= maxx <= 180.0 and -90.0 <= miny <= 90.0 and -90.0 <= maxy <= 90.0
    except Exception:
        return False


def get_optimal_utm_epsg(lon: float, lat: float) -> Tuple[int, str]:
    """Calculate the optimal UTM EPSG code and description for a given longitude and latitude.

    Clamps longitude and latitude to valid UTM ranges.
    """
    # Clamp coordinates safely
    clamped_lon = max(min(lon, 179.9999), -179.9999)
    clamped_lat = max(min(lat, 84.0), -80.0)

    utm_zone = int((clamped_lon + 180.0) / 6.0) + 1
    utm_zone = max(min(utm_zone, 60), 1)

    hemisphere = "N" if clamped_lat >= 0 else "S"
    base_epsg = 32600 if clamped_lat >= 0 else 32700
    epsg_code = base_epsg + utm_zone
    description = f"EPSG:{epsg_code} (UTM Zone {utm_zone}{hemisphere})"

    return epsg_code, description


class CRSService:
    """Provides CRS validation, transformation to suitable projected systems, and metric normalization."""

    @staticmethod
    def resolve_source_crs(raw_crs: Any, sample_geometry: Optional[BaseGeometry] = None) -> Tuple[Optional[CRS], Optional[str], Optional[str]]:
        """Normalize and resolve source CRS from GeoDataFrame CRS metadata or geometry bounds.

        Returns (crs_object, crs_string_identifier, warning_message).
        """
        if raw_crs is not None:
            try:
                crs = CRS.from_user_input(raw_crs)
                epsg = crs.to_epsg()
                crs_str = f"EPSG:{epsg}" if epsg else crs.to_string()
                return crs, crs_str, None
            except Exception as e:
                # Could not parse CRS string
                return None, None, f"Could not parse source CRS: {str(e)}"

        # If CRS is None, infer based on sample coordinate range
        if sample_geometry and is_coordinate_in_degree_range(sample_geometry):
            assumed = CRS.from_epsg(4326)
            return assumed, "EPSG:4326", "Source data has no CRS metadata; assumed EPSG:4326 (WGS 84) based on coordinate bounds."

        return None, None, "Source data has no CRS metadata and coordinates appear non-degree; planar units assumed."

    @staticmethod
    def transform_for_measurement(
        geometry: BaseGeometry,
        source_crs: Optional[CRS],
    ) -> Tuple[BaseGeometry, str, float, Optional[str]]:
        """Transform a geometry into a suitable projected CRS with linear units in metres.

        Returns:
            (projected_geometry, measurement_crs_name, linear_unit_factor_to_metres, warning_message)
        """
        if geometry is None or geometry.is_empty:
            return geometry, "N/A", 1.0, None

        # Case 1: Source CRS is explicitly provided and already projected
        if source_crs is not None and source_crs.is_projected:
            scale, unit_name = get_linear_unit_factor(source_crs)
            epsg = source_crs.to_epsg()
            crs_name = f"EPSG:{epsg}" if epsg else source_crs.name or "Projected CRS"
            warning = None
            if scale != 1.0:
                warning = f"Source projected CRS uses units '{unit_name}'; converted to standard SI metres."
            return geometry, crs_name, scale, warning

        # Case 2: Geographic CRS (degrees) or inferred EPSG:4326
        # NEVER calculate planar measurements directly in degrees! Transform to local UTM zone.
        src_crs_obj = source_crs if source_crs is not None else CRS.from_epsg(4326)
        try:
            centroid = geometry.centroid
            lon, lat = centroid.x, centroid.y
        except Exception:
            minx, miny, maxx, maxy = geometry.bounds
            lon, lat = (minx + maxx) / 2.0, (miny + maxy) / 2.0

        # Polar check: if extreme latitude, use Equal Area projection EPSG:6933
        if abs(lat) > 84.0:
            target_epsg = 6933
            measurement_crs_name = "EPSG:6933 (World Cylindrical Equal Area)"
        else:
            target_epsg, measurement_crs_name = get_optimal_utm_epsg(lon, lat)

        try:
            target_crs = CRS.from_epsg(target_epsg)
            transformer = Transformer.from_crs(src_crs_obj, target_crs, always_xy=True)

            def _transform_coords(coords):
                import numpy as np
                if coords.shape[-1] >= 3:
                    x, y, z = transformer.transform(coords[:, 0], coords[:, 1], coords[:, 2])
                    return np.column_stack([x, y, z])
                x, y = transformer.transform(coords[:, 0], coords[:, 1])
                return np.column_stack([x, y])

            projected_geom = shapely.transform(geometry, _transform_coords)
            warning = None
            if source_crs is None:
                warning = f"Unknown source CRS; assumed EPSG:4326 and projected to {measurement_crs_name} for measurement."
            return projected_geom, measurement_crs_name, 1.0, warning
        except Exception as e:
            # Fallback in case reprojection encountered an error
            return geometry, "Fallback Planar", 1.0, f"Reprojection error: {str(e)}; unprojected measurement applied."
