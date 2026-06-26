"""
Logging configuration for the Fraud Analytics Platform.
Provides structured logging with both file and console handlers.
"""
import logging
import logging.config
import json
from pathlib import Path
from datetime import datetime
from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def setup_logging() -> None:
    """
    Configure logging for the application.
    Sets up both console and file handlers with appropriate formatters.
    """
    # Create logs directory if it doesn't exist
    log_path = Path(settings.log_file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine formatter based on configuration
    if settings.log_format.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, settings.log_level.upper()))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File Handler
    file_handler = logging.FileHandler(settings.log_file_path)
    file_handler.setLevel(getattr(logging, settings.log_level.upper()))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Suppress verbose logs from external libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given module name.
    
    Args:
        name: The name of the module requesting a logger.
        
    Returns:
        A configured logger instance.
    """
    return logging.getLogger(name)
