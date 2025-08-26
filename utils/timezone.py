"""
Timezone handling utilities for consistent UTC storage and local display
"""
from datetime import datetime, timezone
import time


def utc_now():
    """Get current UTC datetime"""
    return datetime.now(timezone.utc)


def utc_timestamp():
    """Get current UTC timestamp as epoch seconds"""
    return time.time()


def format_utc_for_db():
    """Get UTC timestamp formatted for database storage"""
    return utc_now().isoformat()


def utc_from_timestamp(timestamp):
    """Convert epoch timestamp to UTC datetime"""
    return datetime.fromtimestamp(timestamp, timezone.utc)


def format_for_display(dt_or_timestamp, include_seconds=False):
    """
    Format datetime or timestamp for display (will be converted to local time by frontend JS)
    Returns ISO string that JavaScript can parse and convert to local timezone
    """
    if isinstance(dt_or_timestamp, (int, float)):
        # It's a timestamp
        dt = utc_from_timestamp(dt_or_timestamp)
    elif isinstance(dt_or_timestamp, str):
        # It's already an ISO string
        return dt_or_timestamp
    else:
        # It's a datetime object
        dt = dt_or_timestamp
    
    if include_seconds:
        return dt.isoformat()
    else:
        return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_utc_string(utc_string):
    """Parse UTC string back to datetime object"""
    if utc_string.endswith('Z'):
        utc_string = utc_string[:-1] + '+00:00'
    return datetime.fromisoformat(utc_string)