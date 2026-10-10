"""FastAPI application entrypoint, middleware, exception handlers, and routing."""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.files import router as files_router
from app.api.root import router as root_router
from app.config import settings
from app.core.exceptions import GeospatialAppException
from app.db.session import init_db

# Configure application logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("geospatial_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown events."""
    logger.info("Initializing database tables...")
    init_db()
    logger.info("Application startup completed successfully.")
    yield
    logger.info("Application shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-ready Geospatial File Measurement API. "
        "Accepts zipped Shapefiles and KML files, extracts features, "
        "transforms geographic coordinates to optimal projected CRSs (e.g. UTM), "
        "calculates polygon areas (m², km²) and line lengths (m, km), "
        "and persists results in SQLite."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(GeospatialAppException)
async def handle_geospatial_app_exception(request: Request, exc: GeospatialAppException) -> JSONResponse:
    """Handle custom application exceptions with structured, safe JSON responses."""
    logger.warning("Application exception on %s %s: %s (code=%s)", request.method, request.url.path, exc.message, exc.error_code)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.message,
            "error_code": exc.error_code,
        },
    )


@app.exception_handler(Exception)
async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all unhandled exception handler to avoid leaking internal stack traces."""
    logger.error("Unhandled server exception on %s %s: %s", request.method, request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "An internal server error occurred while processing the request.",
            "error_code": "INTERNAL_SERVER_ERROR",
        },
    )


# Register API routers
app.include_router(root_router)
app.include_router(files_router)
