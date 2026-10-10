"""Orchestration service: coordinate extraction, measurement, and SQLite persistence."""

from collections import Counter
from datetime import datetime, timezone
import json
from typing import Any, Dict, List
import uuid
from sqlalchemy.orm import Session
import geopandas as gpd

from app.core.exceptions import FileValidationError
from app.db.models import FeatureRecord, FileRecord
from app.services.crs_service import CRSService
from app.services.file_parser import FileParserService
from app.services.measurement_service import MeasurementService


def clean_properties_dict(row: Any, geometry_col: str = "geometry") -> Dict[str, Any]:
    """Extract and sanitize feature attribute properties to ensure JSON serialization."""
    properties: Dict[str, Any] = {}
    for col, val in row.items():
        if col == geometry_col:
            continue
        # Convert pandas/numpy types and NaNs to serializable primitives
        if val is None or (isinstance(val, float) and (val != val or val is None)):  # NaN check
            properties[str(col)] = None
        elif isinstance(val, (int, str, bool)):
            properties[str(col)] = val
        elif isinstance(val, float):
            properties[str(col)] = round(val, 6)
        elif hasattr(val, "isoformat"):
            properties[str(col)] = val.isoformat()
        else:
            properties[str(col)] = str(val)
    return properties


class FileProcessorService:
    """Processes uploaded files and persists measurement outcomes to the SQLite database."""

    @classmethod
    def process_and_persist(
        cls,
        filename: str,
        file_bytes: bytes,
        db: Session,
        max_uncompressed_bytes: int = 200 * 1024 * 1024,
    ) -> FileRecord:
        """Parses the file, calculates measurements for all features, and commits to SQLite."""
        ext = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""

        if ext == ".zip":
            gdf, file_type, parser_warnings = FileParserService.parse_zip_shapefile(
                file_bytes, max_uncompressed_bytes=max_uncompressed_bytes
            )
        elif ext == ".kml":
            gdf, file_type, parser_warnings = FileParserService.parse_kml_file(file_bytes)
        else:
            raise FileValidationError(f"Unsupported file extension '{ext}'. Only .kml and .zip Shapefiles are supported.")

        # Determine sample geometry to help infer CRS if missing
        sample_geom = None
        if not gdf.empty and "geometry" in gdf.columns:
            for geom in gdf.geometry:
                if geom is not None and not geom.is_empty:
                    sample_geom = geom
                    break

        # Resolve source CRS and any CRS-level warnings
        source_crs_obj, source_crs_str, crs_warning = CRSService.resolve_source_crs(
            gdf.crs, sample_geometry=sample_geom
        )

        all_file_warnings = list(parser_warnings)
        if crs_warning:
            all_file_warnings.append(crs_warning)

        # Generate unique file identifier
        file_id = str(uuid.uuid4())
        feature_records: List[FeatureRecord] = []
        geom_counter: Counter = Counter()

        total_features = len(gdf)

        if total_features > 0 and "geometry" in gdf.columns:
            for idx, row in gdf.iterrows():
                geom = row.geometry
                props = clean_properties_dict(row)

                # Feature identifier resolution (look for FID, ID, Name, or index)
                feat_id = None
                for key in ["FID", "fid", "id", "ID", "Name", "name"]:
                    if key in props and props[key] is not None:
                        feat_id = str(props[key])
                        break
                if feat_id is None:
                    feat_id = f"feat_{idx}"

                # Calculate measurements using MeasurementService
                outcome = MeasurementService.measure_feature(
                    geometry=geom,
                    source_crs=source_crs_obj,
                    crs_warning=None,
                )

                geom_type = outcome.geometry_type
                geom_counter[geom_type] += 1

                # Combine file-level warnings with feature-level warnings if applicable
                combined_warnings = list(outcome.warnings)

                feature_record = FeatureRecord(
                    file_id=file_id,
                    feature_index=int(idx),
                    feature_identifier=feat_id,
                    geometry_type=geom_type,
                    geojson_geometry=json.dumps(outcome.geojson),
                    properties=json.dumps(props),
                    source_crs=source_crs_str,
                    measurement_crs=outcome.measurement_crs,
                    area_sq_m=outcome.area_sq_m,
                    area_sq_km=outcome.area_sq_km,
                    length_m=outcome.length_m,
                    length_km=outcome.length_km,
                    measurement_status=outcome.measurement_status,
                    warnings=json.dumps(combined_warnings),
                )
                feature_records.append(feature_record)

        # Create master FileRecord
        file_record = FileRecord(
            id=file_id,
            filename=filename,
            file_type=file_type,
            file_size_bytes=len(file_bytes),
            upload_timestamp=datetime.now(timezone.utc),
            status="completed",
            total_features=total_features,
            source_crs=source_crs_str,
            geometry_summary=json.dumps(dict(geom_counter)),
            error_message="; ".join(all_file_warnings) if all_file_warnings else None,
        )

        db.add(file_record)
        for feat in feature_records:
            db.add(feat)

        db.commit()
        db.refresh(file_record)

        return file_record
