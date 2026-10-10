"""Pydantic schemas for geospatial file metadata, features, and measurements."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class MeasurementResult(BaseModel):
    """Calculated measurements for an individual feature."""

    area_sq_m: Optional[float] = Field(
        default=None,
        description="Calculated polygon area in square metres (m²).",
    )
    area_sq_km: Optional[float] = Field(
        default=None,
        description="Calculated polygon area in square kilometres (km²).",
    )
    length_m: Optional[float] = Field(
        default=None,
        description="Calculated line length in metres (m).",
    )
    length_km: Optional[float] = Field(
        default=None,
        description="Calculated line length in kilometres (km).",
    )


class FeatureMeasurementResponse(BaseModel):
    """Structured response for an individual feature and its measurements."""

    id: int = Field(description="Database feature record ID.")
    feature_index: int = Field(description="Zero-based feature index in the source file.")
    feature_identifier: Optional[str] = Field(
        default=None,
        description="Feature ID or identifier from source data if present.",
    )
    geometry_type: str = Field(description="Geometry type name (e.g. Polygon, LineString, Point).")
    geometry: Dict[str, Any] = Field(description="GeoJSON-compatible geometry dictionary.")
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Feature attribute properties dictionary.",
    )
    source_crs: Optional[str] = Field(
        default=None,
        description="Source Coordinate Reference System identifier.",
    )
    measurement_crs: Optional[str] = Field(
        default=None,
        description="Projected CRS used for calculating true metric distance/area.",
    )
    measurement_status: str = Field(
        description="Measurement outcome: 'success', 'skipped', or 'failed'.",
    )
    measurements: MeasurementResult = Field(
        default_factory=MeasurementResult,
        description="Calculated metric area or length measurements.",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Warnings regarding CRS, geometry validity, or measurement assumptions.",
    )

    model_config = ConfigDict(from_attributes=True)


class FileMetadataResponse(BaseModel):
    """Structured response for uploaded file metadata and processing status."""

    id: str = Field(description="Unique UUID identifier of the uploaded file.")
    filename: str = Field(description="Original uploaded file name.")
    file_type: str = Field(description="Detected file type: 'kml' or 'shapefile_zip'.")
    file_size_bytes: int = Field(description="File size in bytes.")
    upload_timestamp: datetime = Field(description="UTC timestamp when the file was processed.")
    status: str = Field(description="Processing status: 'completed' or 'failed'.")
    total_features: int = Field(description="Total count of geospatial features parsed.")
    source_crs: Optional[str] = Field(
        default=None,
        description="Detected source Coordinate Reference System.",
    )
    geometry_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Breakdown of feature counts by geometry type (e.g. Polygon, LineString, Point).",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error details if processing failed.",
    )

    model_config = ConfigDict(from_attributes=True)


class FileUploadResponse(BaseModel):
    """Response returned upon successful file upload and processing."""

    message: str = Field(default="File successfully uploaded and processed.")
    file: FileMetadataResponse


class FeatureListResponse(BaseModel):
    """Response returned when fetching all features for a specific file."""

    file_id: str
    filename: str
    source_crs: Optional[str] = None
    total_features: int
    features: List[FeatureMeasurementResponse]


class HealthResponse(BaseModel):
    """Response for system health check endpoint."""

    status: str = "healthy"
    database: str = "connected"
    version: str


class RootResponse(BaseModel):
    """Response for root landing endpoint."""

    message: str
    docs_url: str
    version: str
