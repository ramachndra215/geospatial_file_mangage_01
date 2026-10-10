"""Application configuration and environment settings."""

from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings class using Pydantic Settings."""

    APP_NAME: str = "Geospatial File Measurement API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # SQLite Database URL
    DATABASE_URL: str = "sqlite:///./geospatial_measurements.db"

    # Security: File upload size limit (Default: 50MB)
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024

    # Security: Allowed extensions
    ALLOWED_EXTENSIONS: List[str] = [".kml", ".zip"]

    # Security: Maximum uncompressed extraction size (Default: 200MB)
    MAX_UNCOMPRESSED_ZIP_BYTES: int = 200 * 1024 * 1024

    # Default assumed CRS when geospatial file lacks CRS metadata
    DEFAULT_ASSUMED_CRS: str = "EPSG:4326"

    # CORS origins
    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
