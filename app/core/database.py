"""
Core database module for the Fraud Analytics Platform.
Handles database connections and session management.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from typing import Generator

from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# SQLAlchemy setup
engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    poolclass=NullPool if settings.environment == "docker" else None,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.
    
    Yields:
        Database session.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Initialize database tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {str(e)}")
        raise


def drop_db() -> None:
    """Drop all database tables. Use with caution!"""
    try:
        Base.metadata.drop_all(bind=engine)
        logger.warning("All database tables dropped")
    except Exception as e:
        logger.error(f"Failed to drop database tables: {str(e)}")
        raise
