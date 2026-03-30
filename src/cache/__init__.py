"""
Cache Layer

Provides caching functionality for tool results and LLM responses.

Components:
- CacheBackend: Abstract interface for cache implementations
- MemoryBackend: In-memory LRU cache (fast, volatile)
- DiskBackend: SQLite persistent cache (slower, durable)
- CacheManager: High-level cache management interface
"""

from .backend import CacheBackend, CacheEntry, CacheStats
from .config import CacheBackendType
from .memory_backend import MemoryBackend
from .disk_backend import DiskBackend
from .manager import CacheManager
from .decorators import cached_tool, cached_llm

__all__ = [
    "CacheBackend",
    "CacheBackendType",
    "CacheEntry",
    "CacheStats",
    "MemoryBackend",
    "DiskBackend",
    "CacheManager",
    "cached_tool",
    "cached_llm",
]
