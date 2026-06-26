"""
Helper utilities for the Fraud Analytics Platform.
"""
from typing import Any, Dict, Optional
from datetime import datetime, timedelta
import hashlib
import uuid


def generate_unique_id() -> str:
    """
    Generate a unique ID using UUID4.
    
    Returns:
        A unique string identifier.
    """
    return str(uuid.uuid4())


def hash_string(value: str) -> str:
    """
    Generate SHA256 hash of a string.
    
    Args:
        value: The string to hash.
        
    Returns:
        The hexadecimal hash string.
    """
    return hashlib.sha256(value.encode()).hexdigest()


def get_timestamp() -> datetime:
    """
    Get current UTC timestamp.
    
    Returns:
        Current datetime in UTC.
    """
    return datetime.utcnow()


def add_time_delta(base_time: datetime, **kwargs) -> datetime:
    """
    Add time delta to a datetime.
    
    Args:
        base_time: The base datetime.
        **kwargs: Keyword arguments for timedelta (days, hours, minutes, seconds, etc.).
        
    Returns:
        The adjusted datetime.
    """
    return base_time + timedelta(**kwargs)


def format_datetime(dt: datetime, format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format datetime to string.
    
    Args:
        dt: The datetime to format.
        format_string: The format string.
        
    Returns:
        Formatted datetime string.
    """
    return dt.strftime(format_string)


def parse_datetime(date_string: str, format_string: str = "%Y-%m-%d %H:%M:%S") -> datetime:
    """
    Parse datetime from string.
    
    Args:
        date_string: The date string to parse.
        format_string: The format string.
        
    Returns:
        Parsed datetime object.
    """
    return datetime.strptime(date_string, format_string)


def safe_get(dictionary: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    Safely get a value from dictionary with default.
    
    Args:
        dictionary: The dictionary to access.
        key: The key to retrieve.
        default: The default value if key not found.
        
    Returns:
        The value from dictionary or default.
    """
    return dictionary.get(key, default)


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge multiple dictionaries.
    
    Args:
        *dicts: Variable number of dictionaries to merge.
        
    Returns:
        Merged dictionary.
    """
    result = {}
    for d in dicts:
        if isinstance(d, dict):
            result.update(d)
    return result


def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
    """
    Flatten a nested dictionary.
    
    Args:
        d: The dictionary to flatten.
        parent_key: The parent key prefix.
        sep: The separator to use between keys.
        
    Returns:
        Flattened dictionary.
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def paginate(items: list, page: int = 1, page_size: int = 50) -> Dict[str, Any]:
    """
    Paginate a list of items.
    
    Args:
        items: The list to paginate.
        page: The page number (1-indexed).
        page_size: The number of items per page.
        
    Returns:
        Dictionary containing paginated results and metadata.
    """
    total = len(items)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    
    return {
        "data": items[start_idx:end_idx],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }
