"""
Main FastAPI application entry point for the Fraud Analytics Platform.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api.transactions import router as transactions_router
from app.core.config import settings
from app.core.database import init_db
from app.core.kafka import ensure_topics_exist
from app.utils.logger import setup_logging, get_logger

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
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Trusted Hosts
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],  # In production, specify allowed hosts
)

# Register API routers
app.include_router(transactions_router)


# Health check endpoint
@app.get("/health", tags=["health"])
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
        "docs": "/docs",
        "redoc": "/redoc",
    }


# Exception handlers
@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """
    Handle general exceptions.
    
    Args:
        request: The request object.
        exc: The exception that occurred.
        
    Returns:
        JSON response with error details.
    """
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if settings.debug else "An error occurred",
        },
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
