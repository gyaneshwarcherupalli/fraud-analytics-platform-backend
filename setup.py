"""
Setup and utility scripts for the Fraud Analytics Platform.
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import init_db
from app.utils.logger import get_logger, setup_logging

logger = get_logger(__name__)


def setup_project():
    """
    Setup the project environment.
    Creates necessary directories and initializes the database.
    """
    setup_logging()
    logger.info("Starting project setup...")
    
    # Create necessary directories
    directories = [
        "logs",
        "ml_models/artifacts",
        "ml_models/training",
        "monitoring/logs",
        "tests/api",
        "tests/unit",
        "tests/integration",
    ]
    
    for directory in directories:
        dir_path = project_root / directory
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {directory}")
    
    # Initialize database
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        raise
    
    logger.info("Project setup completed successfully!")


if __name__ == "__main__":
    setup_project()
