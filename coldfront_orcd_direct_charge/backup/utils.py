# SPDX-FileCopyrightText: (C) ORCD
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Shared utilities for backup operations.

Common helper functions used across exporters and importers.
"""

from datetime import datetime, date, time
from decimal import Decimal
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


def serialize_datetime(dt: Optional[datetime]) -> Optional[str]:
    """Serialize datetime to ISO format string.
    
    Args:
        dt: Datetime object or None
        
    Returns:
        ISO format string or None
    """
    if dt is None:
        return None
    return dt.isoformat()


def serialize_date(d: Optional[date]) -> Optional[str]:
    """Serialize date to ISO format string.
    
    Args:
        d: Date object or None
        
    Returns:
        ISO format string (YYYY-MM-DD) or None
    """
    if d is None:
        return None
    return d.isoformat()


def serialize_time(t: Optional[time]) -> Optional[str]:
    """Serialize time to ISO format string.
    
    Args:
        t: Time object or None
        
    Returns:
        ISO format string (HH:MM:SS) or None
    """
    if t is None:
        return None
    return t.isoformat()


def serialize_decimal(d: Optional[Decimal]) -> Optional[str]:
    """Serialize Decimal to string.
    
    Args:
        d: Decimal object or None
        
    Returns:
        String representation or None
    """
    if d is None:
        return None
    return str(d)


def deserialize_datetime(s: Optional[str]) -> Optional[datetime]:
    """Deserialize ISO format string to datetime.
    
    Args:
        s: ISO format string or None
        
    Returns:
        Datetime object or None
    """
    if s is None or s == "":
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        logger.warning(f"Could not parse datetime: {s}")
        return None


def deserialize_date(s: Optional[str]) -> Optional[date]:
    """Deserialize ISO format string to date.
    
    Args:
        s: ISO format string (YYYY-MM-DD) or None
        
    Returns:
        Date object or None
    """
    if s is None or s == "":
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        logger.warning(f"Could not parse date: {s}")
        return None


def deserialize_decimal(s: Optional[str]) -> Optional[Decimal]:
    """Deserialize string to Decimal.
    
    Args:
        s: String representation or None
        
    Returns:
        Decimal object or None
    """
    if s is None or s == "":
        return None
    try:
        return Decimal(s)
    except Exception:
        logger.warning(f"Could not parse decimal: {s}")
        return None


def get_natural_key_value(instance) -> Any:
    """Get natural key value from a model instance.
    
    Args:
        instance: Model instance with natural_key() method
        
    Returns:
        Natural key value (usually a tuple)
    """
    if hasattr(instance, "natural_key"):
        return instance.natural_key()
    return (instance.pk,)


def resolve_foreign_key(
    model_class,
    natural_key,
    field_name: str = "pk",
) -> Optional[Any]:
    """Resolve a foreign key reference using natural key.
    
    Args:
        model_class: Django model class
        natural_key: Natural key value(s)
        field_name: Field name for error messages
        
    Returns:
        Model instance or None if not found
    """
    if natural_key is None:
        return None
    
    try:
        if hasattr(model_class.objects, "get_by_natural_key"):
            if isinstance(natural_key, (list, tuple)):
                return model_class.objects.get_by_natural_key(*natural_key)
            else:
                return model_class.objects.get_by_natural_key(natural_key)
        else:
            # Fall back to pk lookup
            if isinstance(natural_key, (list, tuple)):
                return model_class.objects.get(pk=natural_key[0])
            else:
                return model_class.objects.get(pk=natural_key)
    except model_class.DoesNotExist:
        logger.warning(
            f"Could not resolve {model_class.__name__} with key {natural_key}"
        )
        return None


def create_export_directory(base_path: str, timestamp: bool = True) -> str:
    """Create export directory with optional timestamp suffix.
    
    Args:
        base_path: Base directory path
        timestamp: Whether to add timestamp suffix
        
    Returns:
        Path to created directory
    """
    from pathlib import Path
    
    if timestamp:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_path = Path(base_path) / f"export_{ts}"
    else:
        dir_path = Path(base_path)
    
    dir_path.mkdir(parents=True, exist_ok=True)
    return str(dir_path)


def validate_import_directory(path: str) -> bool:
    """Validate that a directory is a valid export.
    
    Checks for manifest.json and basic structure.
    
    Args:
        path: Directory path to validate
        
    Returns:
        True if valid export directory
    """
    from pathlib import Path
    from .manifest import MANIFEST_FILENAME
    
    dir_path = Path(path)
    
    if not dir_path.is_dir():
        return False
    
    manifest_path = dir_path / MANIFEST_FILENAME
    if not manifest_path.exists():
        return False
    
    return True
