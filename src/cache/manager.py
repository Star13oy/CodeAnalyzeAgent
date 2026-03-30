"""
Cache Manager

High-level cache management with multiple backends and namespaced caches.
"""

import hashlib
import json
import logging
from typing import Any, Optional, Dict, List, Callable
from functools import wraps

from .backend import CacheBackend
from .memory_backend import MemoryBackend
from .disk_backend import DiskBackend

logger = logging.getLogger(__name__)


class CacheNamespace:
    """
    A namespaced cache for isolating different types of cached data.
    """

    def __init__(self, name: str, backend: CacheBackend):
        """
        Initialize a cache namespace.

        Args:
            name: Namespace prefix for all keys
            backend: Cache backend to use
        """
        self.name = name
        self.backend = backend

    def _make_key(self, key: str) -> str:
        """Create a namespaced key."""
        return f"{self.name}:{key}"

    def get(self, key: str) -> Optional[Any]:
        """Get a value from this namespace."""
        return self.backend.get(self._make_key(key))

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in this namespace."""
        return self.backend.set(self._make_key(key), value, ttl)

    def delete(self, key: str) -> bool:
        """Delete a value from this namespace."""
        return self.backend.delete(self._make_key(key))

    def clear(self) -> bool:
        """Clear all entries in this namespace."""
        # Delete all keys with this namespace prefix
        keys = self.backend.keys(f"{self.name}:*")
        return self.backend.delete_many(keys) > 0

    def keys(self) -> List[str]:
        """Get all keys in this namespace (without namespace prefix)."""
        pattern = f"{self.name}:*"
        all_keys = self.backend.keys(pattern)
        # Remove namespace prefix
        prefix_len = len(self.name) + 1
        return [k[prefix_len:] for k in all_keys]


class CacheManager:
    """
    High-level cache manager with multiple backends and namespaces.
    """

    # Default namespace names
    NS_TOOL_RESULTS = "tool"
    NS_LLM_RESPONSES = "llm"
    NS_SYMBOL_INDEX = "symbol"
    NS_FILE_CONTENT = "file"

    def __init__(
        self,
        backend: Optional[CacheBackend] = None,
        default_ttl: Optional[int] = None,
    ):
        """
        Initialize cache manager.

        Args:
            backend: Cache backend to use (defaults to MemoryBackend)
            default_ttl: Default TTL for cache entries in seconds
        """
        if backend is None:
            backend = MemoryBackend(default_ttl=default_ttl, max_size=1000)

        self.backend = backend
        self.default_ttl = default_ttl
        self._namespaces: Dict[str, CacheNamespace] = {}

        # Create default namespaces
        self._create_default_namespaces()

    def _create_default_namespaces(self):
        """Create standard cache namespaces."""
        for ns_name in [
            self.NS_TOOL_RESULTS,
            self.NS_LLM_RESPONSES,
            self.NS_SYMBOL_INDEX,
            self.NS_FILE_CONTENT,
        ]:
            self._namespaces[ns_name] = CacheNamespace(ns_name, self.backend)

    def namespace(self, name: str) -> CacheNamespace:
        """
        Get or create a cache namespace.

        Args:
            name: Namespace name

        Returns:
            CacheNamespace instance
        """
        if name not in self._namespaces:
            self._namespaces[name] = CacheNamespace(name, self.backend)
        return self._namespaces[name]

    def get(self, key: str, namespace: str = NS_TOOL_RESULTS) -> Optional[Any]:
        """Get a value from cache."""
        ns = self.namespace(namespace)
        return ns.get(key)

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        namespace: str = NS_TOOL_RESULTS,
    ) -> bool:
        """Set a value in cache."""
        ns = self.namespace(namespace)
        return ns.set(key, value, ttl)

    def delete(self, key: str, namespace: str = NS_TOOL_RESULTS) -> bool:
        """Delete a value from cache."""
        ns = self.namespace(namespace)
        return ns.delete(key)

    def clear_namespace(self, namespace: str) -> bool:
        """Clear all entries in a namespace."""
        ns = self.namespace(namespace)
        return ns.clear()

    def clear_all(self) -> bool:
        """Clear all cached data."""
        return self.backend.clear()

    def get_stats(self):
        """Get cache statistics."""
        return self.backend.get_stats()

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        return self.backend.cleanup_expired()

    @staticmethod
    def make_key(*args, **kwargs) -> str:
        """
        Generate a cache key from arguments.

        Args:
            *args: Positional arguments to include in key
            **kwargs: Keyword arguments to include in key

        Returns:
            Hash-based cache key
        """
        # Create a deterministic string representation
        key_parts = []

        for arg in args:
            if isinstance(arg, (str, int, float, bool)):
                key_parts.append(str(arg))
            else:
                # For complex objects, use JSON
                key_parts.append(json.dumps(arg, sort_keys=True, default=str))

        for k, v in sorted(kwargs.items()):
            if isinstance(v, (str, int, float, bool)):
                key_parts.append(f"{k}={v}")
            else:
                key_parts.append(f"{k}={json.dumps(v, sort_keys=True, default=str)}")

        key_string = ":".join(key_parts)

        # Hash for compact keys
        return hashlib.sha256(key_string.encode()).hexdigest()[:32]

    def cached(
        self,
        ttl: Optional[int] = None,
        namespace: str = NS_TOOL_RESULTS,
        key_func: Optional[Callable] = None,
    ):
        """
        Decorator for caching function results.

        Args:
            ttl: Time-to-live in seconds
            namespace: Cache namespace to use
            key_func: Custom function to generate cache key

        Returns:
            Decorator function
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                if key_func:
                    cache_key = key_func(*args, **kwargs)
                else:
                    # Use function name and arguments
                    func_name = func.__name__
                    args_key = self.make_key(*args, **kwargs)
                    cache_key = f"{func_name}:{args_key}"

                # Try to get from cache
                cached_value = self.get(cache_key, namespace=namespace)
                if cached_value is not None:
                    logger.debug(f"Cache hit for {cache_key}")
                    return cached_value

                # Call function and cache result
                logger.debug(f"Cache miss for {cache_key}")
                result = func(*args, **kwargs)
                self.set(cache_key, result, ttl=ttl, namespace=namespace)

                return result

            # Add cache management methods to wrapper
            wrapper.cache_key = lambda *a, **kw: (
                key_func(*a, **kw) if key_func
                else f"{func.__name__}:{self.make_key(*a, **kw)}"
            )
            wrapper.cache_clear = lambda: self.clear_namespace(namespace)
            wrapper.cache_namespace = namespace

            return wrapper

        return decorator


# Global cache manager instance
_global_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance."""
    global _global_manager
    if _global_manager is None:
        _global_manager = CacheManager()
    return _global_manager


def set_cache_manager(manager: CacheManager):
    """Set the global cache manager instance."""
    global _global_manager
    _global_manager = manager
