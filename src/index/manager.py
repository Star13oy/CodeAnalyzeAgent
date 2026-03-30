"""
Index Manager

Manages the lifecycle of code indices.
"""

import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from .symbol_index import SymbolIndex, Symbol
from .dependency_graph import DependencyGraph

logger = logging.getLogger(__name__)


class IndexManager:
    """
    Manages symbol index and dependency graph for a repository.

    Features:
    - Lazy index building
    - Automatic refresh on file changes
    - Thread-safe operations
    - Persistent storage
    """

    # Index refresh interval (seconds)
    REFRESH_INTERVAL = 300  # 5 minutes

    def __init__(self, repo_path: str, auto_build: bool = True):
        """
        Initialize the index manager.

        Args:
            repo_path: Path to the code repository
            auto_build: Automatically build index on initialization
        """
        self.repo_path = Path(repo_path)
        self._symbol_index: Optional[SymbolIndex] = None
        self._dependency_graph: Optional[DependencyGraph] = None
        self._last_refresh: Optional[datetime] = None
        self._lock = threading.RLock()

        logger.info(f"Initialized IndexManager for {repo_path}")

        if auto_build:
            self.ensure_index()

    @property
    def symbol_index(self) -> SymbolIndex:
        """Get the symbol index, building if necessary."""
        with self._lock:
            if self._symbol_index is None:
                self._build_index()
            return self._symbol_index

    @property
    def dependency_graph(self) -> DependencyGraph:
        """Get the dependency graph, building if necessary."""
        with self._lock:
            if self._dependency_graph is None:
                self._build_graph()
            return self._dependency_graph

    def ensure_index(self, force_refresh: bool = False) -> bool:
        """
        Ensure the index is built and up-to-date.

        Args:
            force_refresh: Force a refresh even if index exists

        Returns:
            True if index was built/refreshed
        """
        with self._lock:
            # Check if refresh is needed
            if not force_refresh and not self._should_refresh():
                return False

            self._build_index()
            self._last_refresh = datetime.now()
            return True

    def refresh(self) -> Dict[str, int]:
        """
        Refresh the index with changed files.

        Returns:
            Dictionary with refresh statistics
        """
        with self._lock:
            stats = {"symbols_added": 0, "symbols_removed": 0, "files_updated": 0}

            if self._symbol_index:
                old_count = self._symbol_index._total_symbols
                updated = self._symbol_index.update()
                new_count = self._symbol_index._total_symbols

                stats["symbols_added"] = max(0, new_count - old_count)
                stats["symbols_removed"] = max(0, old_count - new_count)
                stats["files_updated"] = updated

            self._last_refresh = datetime.now()

            # Rebuild dependency graph
            if self._dependency_graph:
                self._dependency_graph.clear()
                self._build_graph()

            return stats

    def lookup_symbol(self, name: str, kind: Optional[str] = None) -> List[Symbol]:
        """
        Look up a symbol by name.

        Args:
            name: Symbol name
            kind: Optional symbol kind filter

        Returns:
            List of matching symbols
        """
        return self.symbol_index.lookup(name, kind=kind)

    def lookup_symbol_prefix(
        self,
        prefix: str,
        kind: Optional[str] = None,
        limit: int = 100
    ) -> List[Symbol]:
        """
        Look up symbols by name prefix.

        Args:
            prefix: Name prefix
            kind: Optional symbol kind filter
            limit: Maximum results

        Returns:
            List of matching symbols
        """
        return self.symbol_index.lookup_prefix(prefix, kind=kind, limit=limit)

    def get_file_symbols(self, file_path: str) -> List[Symbol]:
        """
        Get all symbols in a file.

        Args:
            file_path: Path to file (relative to repo root)

        Returns:
            List of symbols in the file
        """
        return self.symbol_index.get_file_symbols(file_path)

    def find_dependencies(self, symbol_name: str) -> List[Symbol]:
        """
        Find symbols that the given symbol depends on.

        Args:
            symbol_name: Name of the symbol

        Returns:
            List of dependency symbols
        """
        # Find the symbol
        symbols = self.symbol_index.lookup(symbol_name)
        if not symbols:
            return []

        # Use the first match
        symbol = symbols[0]
        node_id = f"symbol:{symbol.file_path}:{symbol.line}:{symbol.name}"

        return self.dependency_graph.get_dependencies(node_id)

    def find_dependents(self, symbol_name: str) -> List[Symbol]:
        """
        Find symbols that depend on the given symbol.

        Args:
            symbol_name: Name of the symbol

        Returns:
            List of dependent symbols
        """
        # Find the symbol
        symbols = self.symbol_index.lookup(symbol_name)
        if not symbols:
            return []

        # Use the first match
        symbol = symbols[0]
        node_id = f"symbol:{symbol.file_path}:{symbol.line}:{symbol.name}"

        return self.dependency_graph.get_dependents(node_id)

    def find_path(self, from_symbol: str, to_symbol: str) -> Optional[List[str]]:
        """
        Find a dependency path between two symbols.

        Args:
            from_symbol: Source symbol name
            to_symbol: Target symbol name

        Returns:
            List of symbol names forming a path, or None
        """
        from_symbols = self.symbol_index.lookup(from_symbol)
        to_symbols = self.symbol_index.lookup(to_symbol)

        if not from_symbols or not to_symbols:
            return None

        from_node = f"symbol:{from_symbols[0].file_path}:{from_symbols[0].line}:{from_symbols[0].name}"
        to_node = f"symbol:{to_symbols[0].file_path}:{to_symbols[0].line}:{to_symbols[0].name}"

        path = self.dependency_graph.find_path(from_node, to_node)
        if path:
            # Convert node IDs back to symbol names
            result = []
            for node_id in path:
                if node_id.startswith("symbol:"):
                    parts = node_id.split(":")
                    if len(parts) >= 4:
                        result.append(parts[3])
                else:
                    result.append(node_id)
            return result

        return None

    def get_statistics(self) -> Dict:
        """Get combined index statistics."""
        return {
            "symbol_index": self.symbol_index.get_statistics(),
            "dependency_graph": self.dependency_graph.get_statistics(),
            "last_refresh": self._last_refresh.isoformat() if self._last_refresh else None,
        }

    def _should_refresh(self) -> bool:
        """Check if the index should be refreshed."""
        if self._last_refresh is None:
            return True

        elapsed = (datetime.now() - self._last_refresh).total_seconds()
        return elapsed > self.REFRESH_INTERVAL

    def _build_index(self):
        """Build the symbol index."""
        if self._symbol_index is None:
            self._symbol_index = SymbolIndex(str(self.repo_path))

        logger.info("Building symbol index...")
        count = self._symbol_index.build()
        logger.info(f"Symbol index built: {count} symbols")

    def _build_graph(self):
        """Build the dependency graph."""
        if self._dependency_graph is None:
            self._dependency_graph = DependencyGraph()

        if self._symbol_index:
            # Get all symbols
            all_symbols = []
            for file_symbols in self._symbol_index._symbols_by_file.values():
                all_symbols.extend(file_symbols)

            logger.info("Building dependency graph...")
            self._dependency_graph.build_from_symbols(all_symbols)
            logger.info("Dependency graph built")

    def clear(self):
        """Clear all indices."""
        with self._lock:
            if self._symbol_index:
                self._symbol_index.clear()
            if self._dependency_graph:
                self._dependency_graph.clear()
            self._last_refresh = None


# Global index manager cache
_index_managers: Dict[str, IndexManager] = {}
_managers_lock = threading.Lock()


def get_index_manager(repo_path: str) -> IndexManager:
    """
    Get or create an index manager for a repository.

    Args:
        repo_path: Path to the repository

    Returns:
        IndexManager instance
    """
    with _managers_lock:
        repo_path = str(Path(repo_path).resolve())

        if repo_path not in _index_managers:
            _index_managers[repo_path] = IndexManager(repo_path)

        return _index_managers[repo_path]


def remove_index_manager(repo_path: str) -> bool:
    """
    Remove an index manager from cache.

    Args:
        repo_path: Path to the repository

    Returns:
        True if removed
    """
    with _managers_lock:
        repo_path = str(Path(repo_path).resolve())

        if repo_path in _index_managers:
            _index_managers[repo_path].clear()
            del _index_managers[repo_path]
            return True

        return False
