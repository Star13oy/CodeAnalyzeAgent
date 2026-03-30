"""
In-Memory LRU Cache Backend

Fast in-memory cache with LRU eviction policy.
"""

import threading
from typing import Any, Optional, List
from collections import OrderedDict

from .backend import CacheBackend, CacheEntry, CacheStats


class MemoryBackend(CacheBackend):
    """
    In-memory LRU cache implementation.

    Features:
    - O(1) get/set operations
    - LRU eviction when max_size is reached
    - Thread-safe operations
    - Optional TTL per entry
    """

    def __init__(
        self,
        default_ttl: Optional[int] = None,
        max_size: Optional[int] = 1000,
    ):
        """
        Initialize memory cache.

        Args:
            default_ttl: Default time-to-live in seconds (None = no expiration)
            max_size: Maximum number of entries (default: 1000)
        """
        super().__init__(default_ttl=default_ttl, max_size=max_size)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache, moving it to the end (most recently used)."""
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._record_miss()
                return None

            # Check expiration
            if entry.is_expired():
                del self._cache[key]
                self._record_miss()
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.touch()
            self._record_hit()

            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache."""
        with self._lock:
            effective_ttl = self._get_effective_ttl(ttl)

            # Update existing key
            if key in self._cache:
                self._cache[key] = CacheEntry(key=key, value=value, ttl=effective_ttl)
                self._cache.move_to_end(key)
                self._record_set()
                return True

            # Check if we need to evict
            if self.max_size and len(self._cache) >= self.max_size:
                self._evict_lru()

            # Add new entry
            self._cache[key] = CacheEntry(key=key, value=value, ttl=effective_ttl)
            self._record_set()
            return True

    def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._record_delete()
                return True
            return False

    def clear(self) -> bool:
        """Clear all entries from cache."""
        with self._lock:
            self._cache.clear()
            return True

    def keys(self, pattern: Optional[str] = None) -> List[str]:
        """Get all cache keys, optionally filtered by pattern."""
        with self._lock:
            all_keys = list(self._cache.keys())

            if pattern is None:
                return all_keys

            # Simple glob pattern matching
            import fnmatch
            return [k for k in all_keys if fnmatch.fnmatch(k, pattern)]

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        with self._lock:
            # Return a copy to prevent external modification
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                sets=self._stats.sets,
                deletes=self._stats.deletes,
                evictions=self._stats.evictions,
            )

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        with self._lock:
            expired_keys = [
                k for k, v in self._cache.items()
                if v.is_expired()
            ]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)

    def _evict_lru(self):
        """Evict the least recently used entry."""
        if self._cache:
            self._cache.popitem(last=False)  # Remove from front (LRU)
            self._record_eviction()

    @property
    def size(self) -> int:
        """Current number of entries in cache."""
        with self._lock:
            return len(self._cache)

    def __len__(self) -> int:
        """Return current cache size."""
        return self.size

    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache (and is not expired)."""
        return self.get(key) is not None
