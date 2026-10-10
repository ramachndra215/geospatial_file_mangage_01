"""Endpoints for geospatial file upload, status lookup, and measurement retrieval."""

from typing import List
from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.config import settings
from app.core.exceptions import EntityNotFoundError
from app.core.security import validate_and_read_upload, validate_file_extension
from app.db.models import FeatureRecord, FileRecord
from app.schemas.geospatial import (
    FeatureListResponse,
    FeatureMeasurementResponse,
    FileMetadataResponse,
    FileUploadResponse,
    MeasurementResult,
)
from app.services.file_processor import FileProcessorService

router = APIRouter(prefix="/api/files", tags=["Files & Measurements"])


def build_file_metadata_response(file_rec: FileRecord) -> FileMetadataResponse:
    """Helper to convert FileRecord ORM model to FileMetadataResponse schema."""
    return FileMetadataResponse(
        id=file_rec.id,
        filename=file_rec.filename,
        file_type=file_rec.file_type,
        file_size_bytes=file_rec.file_size_bytes,
        upload_timestamp=file_rec.upload_timestamp,
        status=file_rec.status,
        total_features=file_rec.total_features,
        source_crs=file_rec.source_crs,
        geometry_summary=file_rec.get_geometry_summary_dict(),
        error_message=file_rec.error_message,
    )


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    response_model=FileUploadResponse,
    summary="Upload and process a geospatial file (.kml or .zip Shapefile)",
)
async def upload_and_process_file(
    file: UploadFile = File(..., description="Zipped Shapefile (.zip) or Google Earth KML file (.kml)"),
    db: Session = Depends(get_db),
) -> FileUploadResponse:
    """Upload and process a geospatial file.

    Extracts features, determines optimal projected CRS, computes metric areas and lengths,
    and persists results to SQLite.
    """
    # 1. Validate file extension
    filename = file.filename or "unknown"
    validate_file_extension(filename, settings.ALLOWED_EXTENSIONS)

    # 2. Enforce file size limit while reading content in chunks
    file_bytes = await validate_and_read_upload(file, max_size_bytes=settings.MAX_UPLOAD_SIZE_BYTES)

    # 3. Process geospatial data and persist to SQLite
    file_rec = FileProcessorService.process_and_persist(
        filename=filename,
        file_bytes=file_bytes,
        db=db,
        max_uncompressed_bytes=settings.MAX_UNCOMPRESSED_ZIP_BYTES,
    )

    metadata_resp = build_file_metadata_response(file_rec)
    return FileUploadResponse(
        message="File processed successfully and measurements calculated.",
        file=metadata_resp,
    )


@router.get(
    "/",
    response_model=List[FileMetadataResponse],
    summary="List all uploaded geospatial files",
)
def list_files(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> List[FileMetadataResponse]:
    """Return all uploaded files with pagination."""
    files = (
        db.query(FileRecord)
        .order_by(FileRecord.upload_timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [build_file_metadata_response(f) for f in files]


@router.get(
    "/{file_id}/",
    response_model=FileMetadataResponse,
    summary="Get metadata and processing status of an uploaded file",
)
def get_file_metadata(
    file_id: str,
    db: Session = Depends(get_db),
) -> FileMetadataResponse:
    """Fetch file metadata and processing status by file ID."""
    file_rec = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if not file_rec:
        raise EntityNotFoundError(f"File with ID '{file_id}' not found.")
    return build_file_metadata_response(file_rec)


@router.get(
    "/{file_id}/measurements/",
    response_model=FeatureListResponse,
    summary="Get every feature and its measurement results for an uploaded file",
)
def get_file_measurements(
    file_id: str,
    db: Session = Depends(get_db),
) -> FeatureListResponse:
    """Fetch every feature and its calculated measurements for a specific file."""
    file_rec = db.query(FileRecord).filter(FileRecord.id == file_id).first()
    if not file_rec:
        raise EntityNotFoundError(f"File with ID '{file_id}' not found.")

    features = (
        db.query(FeatureRecord)
        .filter(FeatureRecord.file_id == file_id)
        .order_by(FeatureRecord.feature_index.asc())
        .all()
    )

    feature_items: List[FeatureMeasurementResponse] = []
    for feat in features:
        item = FeatureMeasurementResponse(
            id=feat.id,
            feature_index=feat.feature_index,
            feature_identifier=feat.feature_identifier,
            geometry_type=feat.geometry_type,
            geometry=feat.get_geojson(),
            properties=feat.get_properties(),
            source_crs=feat.source_crs,
            measurement_crs=feat.measurement_crs,
            measurement_status=feat.measurement_status,
            measurements=MeasurementResult(
                area_sq_m=feat.area_sq_m,
                area_sq_km=feat.area_sq_km,
                length_m=feat.length_m,
                length_km=feat.length_km,
            ),
            warnings=feat.get_warnings(),
        )
        feature_items.append(item)

    return FeatureListResponse(
        file_id=file_rec.id,
        filename=file_rec.filename,
        source_crs=file_rec.source_crs,
        total_features=len(feature_items),
        features=feature_items,
    )
