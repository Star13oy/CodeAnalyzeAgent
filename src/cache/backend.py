"""
Cache Backend Interface

Abstract base class for cache implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Dict, List
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class CacheEntry:
    """A cache entry with value and metadata."""
    key: str
    value: Any
    ttl: Optional[int] = None  # Time to live in seconds
    created_at: datetime = None
    access_count: int = 0
    last_accessed: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.last_accessed is None:
            self.last_accessed = datetime.now()

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.ttl is None:
            return False
        return (datetime.now() - self.created_at).total_seconds() > self.ttl

    def touch(self):
        """Update last accessed time and increment access count."""
        self.last_accessed = datetime.now()
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0

    @property
    def total_requests(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    def reset(self):
        """Reset all statistics."""
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.evictions = 0


class CacheBackend(ABC):
    """
    Abstract cache backend.

    Implementations must provide thread-safe operations.
    """

    def __init__(self, default_ttl: Optional[int] = None, max_size: Optional[int] = None):
        """
        Initialize cache backend.

        Args:
            default_ttl: Default time-to-live for entries in seconds
            max_size: Maximum number of entries (None for unlimited)
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._stats = CacheStats()

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default_ttl if None)

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete a value from the cache.

        Args:
            key: Cache key

        Returns:
            True if the key was deleted
        """
        pass

    @abstractmethod
    def clear(self) -> bool:
        """
        Clear all entries from the cache.

        Returns:
            True if successful
        """
        pass

    @abstractmethod
    def keys(self, pattern: Optional[str] = None) -> List[str]:
        """
        Get all cache keys, optionally filtered by pattern.

        Args:
            pattern: Optional glob pattern (e.g., "tool:*")

        Returns:
            List of keys
        """
        pass

    @abstractmethod
    def get_stats(self) -> CacheStats:
        """
        Get cache statistics.

        Returns:
            CacheStats object
        """
        pass

    @abstractmethod
    def cleanup_expired(self) -> int:
        """
        Remove expired entries.

        Returns:
            Number of entries removed
        """
        pass

    def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values at once.

        Args:
            keys: List of cache keys

        Returns:
            Dictionary mapping keys to values
        """
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result

    def set_many(self, items: Dict[str, Any], ttl: Optional[int] = None) -> int:
        """
        Set multiple values at once.

        Args:
            items: Dictionary of key-value pairs
            ttl: Time-to-live in seconds

        Returns:
            Number of items successfully set
        """
        count = 0
        for key, value in items.items():
            if self.set(key, value, ttl):
                count += 1
        return count

    def delete_many(self, keys: List[str]) -> int:
        """
        Delete multiple keys at once.

        Args:
            keys: List of cache keys

        Returns:
            Number of keys deleted
        """
        count = 0
        for key in keys:
            if self.delete(key):
                count += 1
        return count

    def _get_effective_ttl(self, ttl: Optional[int]) -> Optional[int]:
        """Get the effective TTL, using default if not specified."""
        return ttl if ttl is not None else self.default_ttl

    def _record_hit(self):
        """Record a cache hit."""
        self._stats.hits += 1

    def _record_miss(self):
        """Record a cache miss."""
        self._stats.misses += 1

    def _record_set(self):
        """Record a cache set operation."""
        self._stats.sets += 1

    def _record_delete(self):
        """Record a cache delete operation."""
        self._stats.deletes += 1

    def _record_eviction(self):
        """Record a cache eviction."""
        self._stats.evictions += 1
