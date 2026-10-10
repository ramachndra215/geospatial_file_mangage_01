"""Custom exception classes for application error handling."""

from fastapi import status


class GeospatialAppException(Exception):
    """Base exception for Geospatial File Measurement API."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST, error_code: str = "ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class FileValidationError(GeospatialAppException):
    """Raised when an uploaded file fails validation (unsupported type, missing shapefile parts, etc.)."""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="FILE_VALIDATION_ERROR",
        )


class FileSizeExceededError(GeospatialAppException):
    """Raised when an uploaded file exceeds the configured maximum size limit."""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            error_code="FILE_SIZE_EXCEEDED",
        )


class PathTraversalError(GeospatialAppException):
    """Raised when a zip archive contains filenames attempting path traversal (Zip Slip)."""

    def __init__(self, message: str = "Potential path traversal attempt detected in archive."):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="PATH_TRAVERSAL_DETECTED",
        )


class EntityNotFoundError(GeospatialAppException):
    """Raised when a requested resource (e.g. file ID) cannot be found."""

    def __init__(self, message: str = "Resource not found."):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="NOT_FOUND",
        )


class ProcessingError(GeospatialAppException):
    """Raised when a file cannot be processed or contains unrecoverable geospatial errors."""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="PROCESSING_ERROR",
        )
