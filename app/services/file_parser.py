"""Service for safely extracting and parsing zipped Shapefiles and KML files."""

import os
import tempfile
from typing import List, Tuple
import fiona
import fiona.drvsupport
import geopandas as gpd

from app.core.exceptions import FileValidationError
from app.core.security import safe_extract_zip

# Ensure Fiona KML driver support is enabled if fiona is invoked
try:
    if "KML" not in fiona.drvsupport.supported_drivers:
        fiona.drvsupport.supported_drivers["KML"] = "rw"
    if "LIBKML" not in fiona.drvsupport.supported_drivers:
        fiona.drvsupport.supported_drivers["LIBKML"] = "rw"
except Exception:
    pass


class FileParserService:
    """Handles format inspection, decompression, and GeoPandas ingestion."""

    @classmethod
    def parse_zip_shapefile(
        cls,
        zip_bytes: bytes,
        max_uncompressed_bytes: int = 200 * 1024 * 1024,
    ) -> Tuple[gpd.GeoDataFrame, str, List[str]]:
        """Safely unpacks a zip archive, verifies Shapefile components, and loads GeoDataFrame."""
        warnings: List[str] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            extracted_paths = safe_extract_zip(zip_bytes, temp_dir, max_uncompressed_bytes)

            # Locate .shp files
            shp_files = [p for p in extracted_paths if p.lower().endswith(".shp")]
            if not shp_files:
                raise FileValidationError(
                    "The zip archive does not contain any ESRI Shapefile (.shp) file."
                )

            import pandas as pd

            gdfs: List[gpd.GeoDataFrame] = []
            for shp in shp_files:
                base_no_ext = os.path.splitext(shp)[0]
                shx_exists = os.path.exists(base_no_ext + ".shx") or os.path.exists(base_no_ext + ".SHX")
                dbf_exists = os.path.exists(base_no_ext + ".dbf") or os.path.exists(base_no_ext + ".DBF")
                prj_exists = os.path.exists(base_no_ext + ".prj") or os.path.exists(base_no_ext + ".PRJ")

                shp_name = os.path.basename(shp)
                if not shx_exists:
                    warnings.append(f"Companion index file (.shx) is missing for '{shp_name}'.")
                if not dbf_exists:
                    warnings.append(f"Companion attribute table (.dbf) is missing for '{shp_name}'.")
                if not prj_exists:
                    warnings.append(f"Companion projection file (.prj) is missing for '{shp_name}'; coordinates will be treated as unprojected.")

                try:
                    layer_gdf = gpd.read_file(shp)
                    if not layer_gdf.empty:
                        gdfs.append(layer_gdf)
                except Exception as e:
                    raise FileValidationError(f"Failed to read Shapefile '{shp_name}': {str(e)}") from e

            if not gdfs:
                return gpd.GeoDataFrame([], crs=None), "shapefile_zip", warnings + ["Shapefile contains zero features."]

            if len(gdfs) == 1:
                gdf = gdfs[0]
            else:
                combined = pd.concat(gdfs, ignore_index=True)
                primary_crs = gdfs[0].crs
                gdf = gpd.GeoDataFrame(combined, crs=primary_crs)
                warnings.append(f"Combined {len(gdfs)} Shapefile layers from zip archive.")

            return gdf, "shapefile_zip", warnings

    @classmethod
    def parse_kml_file(cls, kml_bytes: bytes) -> Tuple[gpd.GeoDataFrame, str, List[str]]:
        """Parses a KML file into a GeoDataFrame using Pyogrio or Fiona engines."""
        warnings: List[str] = []

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_kml_path = os.path.join(temp_dir, "uploaded_file.kml")
            with open(temp_kml_path, "wb") as f:
                f.write(kml_bytes)

            # Attempt reading via pyogrio first, then fallback to fiona
            gdf = None
            last_err = None

            try:
                gdf = gpd.read_file(temp_kml_path, engine="pyogrio")
            except Exception as e:
                last_err = e

            if gdf is None:
                try:
                    gdf = gpd.read_file(temp_kml_path, engine="fiona")
                except Exception as e:
                    raise FileValidationError(
                        f"Failed to parse KML file. Ensure the file contains valid KML XML: {str(e)}"
                    ) from e

            # KML specifications default to WGS 84 (EPSG:4326)
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")
                warnings.append("KML specification specifies WGS 84; assigned EPSG:4326.")

            if gdf.empty:
                warnings.append("KML file contains zero features or placemarks.")

            return gdf, "kml", warnings
