"""
Cache Configuration

Configuration classes for caching system.
"""

from enum import Enum


class CacheBackendType(str, Enum):
    """Cache backend types"""
    MEMORY = "memory"
    DISK = "disk"
    HYBRID = "hybrid"
