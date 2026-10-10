"""SQLAlchemy ORM models for geospatial file records and measurement features."""

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Text,
    ForeignKey,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class FileRecord(Base):
    """Represents an uploaded geospatial file and its overall processing status."""

    __tablename__ = "files"

    id = Column(String(36), primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # 'kml' or 'shapefile_zip'
    file_size_bytes = Column(Integer, nullable=False)
    upload_timestamp = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    status = Column(String(50), nullable=False, default="completed")  # 'completed', 'failed'
    total_features = Column(Integer, nullable=False, default=0)
    source_crs = Column(String(100), nullable=True)
    geometry_summary = Column(Text, nullable=False, default="{}")  # JSON string: {"Polygon": 1, ...}
    error_message = Column(Text, nullable=True)

    # Relationships
    features = relationship(
        "FeatureRecord",
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="FeatureRecord.feature_index",
    )

    def get_geometry_summary_dict(self) -> Dict[str, int]:
        """Deserialize geometry summary JSON to a dict."""
        try:
            return json.loads(self.geometry_summary) if self.geometry_summary else {}
        except Exception:
            return {}

    def set_geometry_summary_dict(self, summary: Dict[str, int]) -> None:
        """Serialize geometry summary dict to JSON."""
        self.geometry_summary = json.dumps(summary)


class FeatureRecord(Base):
    """Represents an individual geospatial feature and its measurement outcomes."""

    __tablename__ = "features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(
        String(36),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_index = Column(Integer, nullable=False)
    feature_identifier = Column(String(255), nullable=True)
    geometry_type = Column(String(50), nullable=False)
    geojson_geometry = Column(Text, nullable=False)  # JSON-encoded GeoJSON dict
    properties = Column(Text, nullable=False, default="{}")  # JSON-encoded properties dict
    source_crs = Column(String(100), nullable=True)
    measurement_crs = Column(String(100), nullable=True)

    # Measurements
    area_sq_m = Column(Float, nullable=True)
    area_sq_km = Column(Float, nullable=True)
    length_m = Column(Float, nullable=True)
    length_km = Column(Float, nullable=True)

    measurement_status = Column(String(50), nullable=False, default="success")  # 'success', 'skipped', 'failed'
    warnings = Column(Text, nullable=False, default="[]")  # JSON array of warning strings

    # Relationship
    file = relationship("FileRecord", back_populates="features")

    def get_geojson(self) -> Dict[str, Any]:
        """Deserialize GeoJSON geometry text to dictionary."""
        try:
            return json.loads(self.geojson_geometry) if self.geojson_geometry else {}
        except Exception:
            return {}

    def get_properties(self) -> Dict[str, Any]:
        """Deserialize properties text to dictionary."""
        try:
            return json.loads(self.properties) if self.properties else {}
        except Exception:
            return {}

    def get_warnings(self) -> List[str]:
        """Deserialize warnings text to list of strings."""
        try:
            return json.loads(self.warnings) if self.warnings else []
        except Exception:
            return []
