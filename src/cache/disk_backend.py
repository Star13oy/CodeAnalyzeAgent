"""
Disk Cache Backend

Persistent cache using SQLite storage.
"""

import sqlite3
import threading
import json
from typing import Any, Optional, List
from pathlib import Path
from datetime import datetime

from .backend import CacheBackend, CacheStats


class DiskBackend(CacheBackend):
    """
    Persistent disk cache using SQLite.

    Features:
    - Persistent storage across restarts
    - Automatic cleanup of expired entries
    - Thread-safe operations
    - Efficient key-based lookups
    """

    def __init__(
        self,
        cache_path: str = "./cache.db",
        default_ttl: Optional[int] = None,
        max_size: Optional[int] = None,
    ):
        """
        Initialize disk cache.

        Args:
            cache_path: Path to SQLite database file
            default_ttl: Default time-to-live in seconds
            max_size: Maximum number of entries (soft limit)
        """
        super().__init__(default_ttl=default_ttl, max_size=max_size)
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                str(self.cache_path),
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_entries (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_expires_at
            ON cache_entries(expires_at)
        """)
        conn.commit()

    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT value, expires_at FROM cache_entries WHERE key = ?",
            (key,)
        )
        row = cursor.fetchone()

        if row is None:
            self._record_miss()
            return None

        # Check expiration
        if row["expires_at"] is not None:
            expires_at = datetime.fromisoformat(row["expires_at"])
            if datetime.now() > expires_at:
                self.delete(key)
                self._record_miss()
                return None

        # Update access stats
        conn.execute(
            """UPDATE cache_entries
               SET access_count = access_count + 1,
                   last_accessed = CURRENT_TIMESTAMP
               WHERE key = ?""",
            (key,)
        )
        conn.commit()

        self._record_hit()
        return json.loads(row["value"])

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set a value in cache."""
        import datetime as dt

        effective_ttl = self._get_effective_ttl(ttl)
        expires_at = None
        if effective_ttl is not None:
            expires_at = (datetime.now() + dt.timedelta(seconds=effective_ttl)).isoformat()

        conn = self._get_connection()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO cache_entries
                   (key, value, expires_at, created_at)
                   VALUES (?, ?, ?, COALESCE((SELECT created_at FROM cache_entries WHERE key = ?), CURRENT_TIMESTAMP))""",
                (key, json.dumps(value), expires_at, key)
            )
            conn.commit()

            # Soft limit: cleanup if over max_size
            if self.max_size:
                self._enforce_size_limit()

            self._record_set()
            return True
        except Exception:
            return False

    def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM cache_entries WHERE key = ?",
            (key,)
        )
        conn.commit()
        if cursor.rowcount > 0:
            self._record_delete()
            return True
        return False

    def clear(self) -> bool:
        """Clear all entries from cache."""
        conn = self._get_connection()
        conn.execute("DELETE FROM cache_entries")
        conn.commit()
        return True

    def keys(self, pattern: Optional[str] = None) -> List[str]:
        """Get all cache keys, optionally filtered by pattern."""
        conn = self._get_connection()
        if pattern is None:
            cursor = conn.execute("SELECT key FROM cache_entries")
        else:
            # SQLite GLOB pattern matching
            cursor = conn.execute(
                "SELECT key FROM cache_entries WHERE key GLOB ?",
                (pattern,)
            )
        return [row["key"] for row in cursor.fetchall()]

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT
                SUM(CASE WHEN value IS NOT NULL THEN 1 ELSE 0 END) as total_keys,
                SUM(access_count) as total_accesses
            FROM cache_entries
        """)
        row = cursor.fetchone()

        return CacheStats(
            hits=self._stats.hits,
            misses=self._stats.misses,
            sets=self._stats.sets,
            deletes=self._stats.deletes,
            evictions=self._stats.evictions,
        )

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        conn = self._get_connection()
        cursor = conn.execute(
            "DELETE FROM cache_entries WHERE expires_at IS NOT NULL AND expires_at < ?",
            (datetime.now().isoformat(),)
        )
        conn.commit()
        return cursor.rowcount

    def _enforce_size_limit(self):
        """Enforce max size by removing oldest entries."""
        conn = self._get_connection()
        # Count current entries
        cursor = conn.execute("SELECT COUNT(*) as count FROM cache_entries")
        count = cursor.fetchone()["count"]

        if count > self.max_size:
            # Delete oldest entries (by created_at)
            to_delete = count - self.max_size
            conn.execute("""
                DELETE FROM cache_entries
                WHERE key IN (
                    SELECT key FROM cache_entries
                    ORDER BY created_at ASC
                    LIMIT ?
                )
            """, (to_delete,))
            conn.commit()

    def close(self):
        """Close database connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    def __del__(self):
        """Cleanup on deletion."""
        self.close()
