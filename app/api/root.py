"""Root and health check endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.config import settings
from app.schemas.geospatial import HealthResponse, RootResponse

router = APIRouter(tags=["General"])


@router.get(
    "/",
    response_model=RootResponse,
    summary="Root welcome endpoint",
)
def root() -> RootResponse:
    """Return welcome message, documentation link, and application version."""
    return RootResponse(
        message=f"Welcome to the {settings.APP_NAME}.",
        docs_url="/docs",
        version=settings.APP_VERSION,
    )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Application health check",
)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    """Check application readiness and SQLite database connectivity."""
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        database=db_status,
        version=settings.APP_VERSION,
    )
