"""
Main FastAPI application entry point for the Fraud Analytics Platform.
"""
from time import perf_counter
from uuid import uuid4
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.alerts import router as alerts_router
from app.api.dashboard import router as dashboard_router
from app.api.fraud import router as fraud_router
from app.api.health import router as health_router
from app.api.investigations import router as investigations_router
from app.api.transactions import router as transactions_router
from app.core.config import settings
from app.core.database import init_db
from app.core.kafka import ensure_topics_exist
from app.utils.logger import setup_logging, get_logger
from app.utils.exceptions import FraudAnalyticsException
from monitoring.cloudwatch_metrics import publish_metrics_async

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for application startup and shutdown.
    """
    logger.info("Application startup")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug mode: {settings.debug}")
    init_db()

    try:
        ensure_topics_exist()
        logger.info("Kafka topic initialization completed")
    except Exception as exc:
        logger.warning("Kafka topic initialization skipped: %s", exc)

    yield
    logger.info("Application shutdown")


# Initialize FastAPI application
app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    debug=settings.debug,
    lifespan=lifespan,
    openapi_url=settings.openapi_url if settings.enable_docs else None,
    docs_url=settings.docs_url if settings.enable_docs else None,
    redoc_url=settings.redoc_url if settings.enable_docs else None,
    swagger_ui_parameters={
        "displayRequestDuration": True,
        "docExpansion": "none",
        "tryItOutEnabled": True,
    },
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods_list,
    allow_headers=settings.cors_allow_headers_list,
)

# Configure Trusted Hosts
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.trusted_hosts_list,
)

# Enable gzip compression for larger responses.
app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_minimum_size)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    """Attach a request id and response time headers to every response."""
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    start = perf_counter()
    response = await call_next(request)
    duration_ms = (perf_counter() - start) * 1000

    metrics = [
        {"name": "ApiRequests", "value": 1, "unit": "Count",
         "dimensions": {"Method": request.method}},
        {"name": "ApiLatency", "value": duration_ms, "unit": "Milliseconds",
         "dimensions": {"Method": request.method}},
    ]
    if 400 <= response.status_code < 500:
        metrics.append({"name": "ApiClientErrors", "value": 1, "unit": "Count"})
    elif response.status_code >= 500:
        metrics.append({"name": "ApiServerErrors", "value": 1, "unit": "Count"})
    publish_metrics_async(metrics)

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time-MS"] = f"{duration_ms:.2f}"
    return response


# Register API routers
app.include_router(health_router)
app.include_router(transactions_router)
app.include_router(fraud_router)
app.include_router(alerts_router)
app.include_router(investigations_router)
app.include_router(dashboard_router)


# Health check endpoint
@app.get("/health", tags=["platform"])
async def health_check():
    """
    Health check endpoint for the application.
    
    Returns:
        Status of the application.
    """
    return {
        "status": "healthy",
        "environment": settings.environment,
        "version": settings.api_version,
    }


@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint returning API information.
    
    Returns:
        API information and available endpoints.
    """
    return {
        "name": settings.api_title,
        "description": settings.api_description,
        "version": settings.api_version,
        "health_check": "/health",
        "api_prefix": settings.api_prefix,
        "docs": settings.docs_url if settings.enable_docs else None,
        "redoc": settings.redoc_url if settings.enable_docs else None,
    }


# Exception handlers
def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details=None,
) -> JSONResponse:
    """Build the common API error envelope."""
    request_id = getattr(request.state, "request_id", request.headers.get("X-Request-ID", str(uuid4())))
    content = {
        "error": {"code": code, "message": message},
        "request_id": request_id,
        "path": request.url.path,
    }
    if details is not None:
        content["error"]["details"] = details
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(content),
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return field-level validation details in the common envelope."""
    return _error_response(
        request, status_code=422, code="VALIDATION_ERROR",
        message="Request validation failed", details=exc.errors(),
    )


@app.exception_handler(FraudAnalyticsException)
async def domain_exception_handler(request: Request, exc: FraudAnalyticsException):
    """Translate domain exceptions to their declared HTTP status."""
    if exc.status_code >= 500:
        logger.error("Domain error on %s: %s", request.url.path, exc.message, exc_info=exc)
    return _error_response(
        request, status_code=exc.status_code, code=exc.code, message=exc.message,
    )


@app.exception_handler(SQLAlchemyError)
async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    """Hide database internals while retaining the exception in server logs."""
    logger.error("Database error on %s", request.url.path, exc_info=exc)
    return _error_response(
        request, status_code=500, code="DATABASE_ERROR",
        message="A database operation failed",
    )


@app.exception_handler(HTTPException)
async def api_http_exception_handler(request: Request, exc: HTTPException):
    """Normalize FastAPI HTTP exceptions while preserving custom headers."""
    response = _error_response(
        request, status_code=exc.status_code, code=f"HTTP_{exc.status_code}",
        message=exc.detail if isinstance(exc.detail, str) else "Request failed",
        details=None if isinstance(exc.detail, str) else exc.detail,
    )
    response.headers.update(exc.headers or {})
    return response


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle general exceptions.
    
    Args:
        request: The request object.
        exc: The exception that occurred.
        
    Returns:
        JSON response with error details.
    """
    logger.error("Unhandled exception on %s: %s", request.url.path, str(exc), exc_info=exc)
    return _error_response(
        request,
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        message=str(exc) if settings.debug else "An unexpected error occurred",
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )
