"""
Symbol Index

Fast in-memory symbol index for code exploration.

Uses tree-sitter for accurate parsing and supports incremental updates.
"""

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class Symbol:
    """A code symbol (function, class, method, variable, etc.)"""
    name: str
    kind: str  # function, class, method, variable, etc.
    language: str
    file_path: str
    line: int
    column: int
    end_line: Optional[int] = None
    parent: Optional[str] = None  # Parent class/module
    signature: Optional[str] = None
    docstring: Optional[str] = None

    def __hash__(self):
        return hash((self.name, self.file_path, self.line))

    def __eq__(self, other):
        if not isinstance(other, Symbol):
            return False
        return (self.name == other.name and
                self.file_path == other.file_path and
                self.line == other.line)


@dataclass
class FileIndex:
    """Index metadata for a single file."""
    path: str
    size: int
    mtime: float  # Modification time
    hash: str
    indexed_at: datetime
    symbol_count: int


class SymbolIndex:
    """
    Fast in-memory symbol index.

    Features:
    - O(1) symbol lookup by name
    - O(1) file-to-symbols lookup
    - Incremental updates based on file modification
    - Multi-language support via tree-sitter
    """

    def __init__(self, repo_path: str, persistent_path: Optional[str] = None):
        """
        Initialize the symbol index.

        Args:
            repo_path: Path to the code repository
            persistent_path: Optional path to persistent index database
        """
        self.repo_path = Path(repo_path)
        self.persistent_path = persistent_path

        # In-memory indices
        self._symbols_by_name: Dict[str, List[Symbol]] = defaultdict(list)
        self._symbols_by_file: Dict[str, List[Symbol]] = defaultdict(list)
        self._symbols_by_kind: Dict[str, List[Symbol]] = defaultdict(list)
        self._file_metadata: Dict[str, FileIndex] = {}

        # Thread safety
        self._lock = threading.RLock()

        # Statistics
        self._total_symbols = 0
        self._last_update = None

        logger.info(f"Initialized SymbolIndex for {repo_path}")

    def build(self, force: bool = False) -> int:
        """
        Build the symbol index from scratch.

        Args:
            force: Force rebuild even if index exists

        Returns:
            Number of symbols indexed
        """
        with self._lock:
            logger.info(f"Building symbol index for {self.repo_path}")

            # Clear existing index
            if force:
                self.clear()

            count = 0

            # Scan for code files
            for file_path in self._scan_code_files():
                if self._should_index_file(file_path):
                    symbols = self._index_file(file_path)
                    count += len(symbols)

            self._total_symbols = count
            self._last_update = datetime.now()

            logger.info(f"Symbol index built: {count} symbols from {len(self._file_metadata)} files")

            return count

    def update(self, changed_files: Optional[List[str]] = None) -> int:
        """
        Update the index with changed files.

        Args:
            changed_files: List of changed file paths (None = detect changes)

        Returns:
            Number of symbols updated
        """
        with self._lock:
            if changed_files is None:
                # Detect changes
                changed_files = self._detect_changes()

            if not changed_files:
                return 0

            logger.info(f"Updating index for {len(changed_files)} changed files")

            updated = 0

            for file_path in changed_files:
                # Remove old symbols
                self._remove_file_symbols(file_path)

                # Re-index
                if self._should_index_file(file_path):
                    symbols = self._index_file(file_path)
                    updated += len(symbols)

            self._last_update = datetime.now()

            return updated

    def lookup(self, name: str, kind: Optional[str] = None) -> List[Symbol]:
        """
        Look up symbols by name.

        Args:
            name: Symbol name (supports partial matching)
            kind: Optional symbol kind filter

        Returns:
            List of matching symbols
        """
        with self._lock:
            if kind:
                return [s for s in self._symbols_by_name.get(name, [])
                        if s.kind == kind]
            return self._symbols_by_name.get(name, [])

    def lookup_prefix(self, prefix: str, kind: Optional[str] = None, limit: int = 100) -> List[Symbol]:
        """
        Look up symbols by name prefix.

        Args:
            prefix: Name prefix to search
            kind: Optional symbol kind filter
            limit: Maximum results

        Returns:
            List of matching symbols
        """
        with self._lock:
            results = []
            prefix_lower = prefix.lower()

            for name, symbols in self._symbols_by_name.items():
                if name.lower().startswith(prefix_lower):
                    if kind:
                        results.extend(s for s in symbols if s.kind == kind)
                    else:
                        results.extend(symbols)

                if len(results) >= limit:
                    break

            return results[:limit]

    def get_file_symbols(self, file_path: str) -> List[Symbol]:
        """
        Get all symbols in a file.

        Args:
            file_path: Path to file

        Returns:
            List of symbols in the file
        """
        with self._lock:
            return self._symbols_by_file.get(file_path, [])

    def find_definitions(self, file_path: str, line: int, column: int) -> Optional[Symbol]:
        """
        Find the symbol definition at a specific location.

        Args:
            file_path: Path to file
            line: Line number (1-indexed)
            column: Column number (0-indexed)

        Returns:
            Symbol at the location or None
        """
        with self._lock:
            for symbol in self._symbols_by_file.get(file_path, []):
                if (symbol.line <= line <=
                    (symbol.end_line if symbol.end_line else symbol.line)):
                    return symbol
            return None

    def get_statistics(self) -> Dict:
        """Get index statistics."""
        with self._lock:
            by_kind = {}
            for kind, symbols in self._symbols_by_kind.items():
                by_kind[kind] = len(symbols)

            return {
                "total_symbols": self._total_symbols,
                "total_files": len(self._file_metadata),
                "by_kind": by_kind,
                "last_update": self._last_update.isoformat() if self._last_update else None,
            }

    def clear(self):
        """Clear all indexed data."""
        with self._lock:
            self._symbols_by_name.clear()
            self._symbols_by_file.clear()
            self._symbols_by_kind.clear()
            self._file_metadata.clear()
            self._total_symbols = 0
            self._last_update = None

    def _scan_code_files(self) -> List[Path]:
        """Scan repository for code files."""
        extensions = {
            # Python
            '.py', '.pyw',
            # JavaScript/TypeScript
            '.js', '.jsx', '.ts', '.tsx', '.mjs',
            # Java
            '.java',
            # C/C++
            '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx',
            # Go
            '.go',
            # Rust
            '.rs',
            # Ruby
            '.rb',
            # PHP
            '.php',
            # Shell
            '.sh', '.bash',
            # Config
            '.yaml', '.yml', '.json', '.toml', '.ini',
        }

        files = []
        for ext in extensions:
            files.extend(self.repo_path.rglob(f"*{ext}"))

        # Filter out large files and common exclude patterns
        exclude_dirs = {
            'node_modules', '.git', '__pycache__', 'venv', 'env',
            'dist', 'build', '.venv', 'virtualenv',
        }

        result = []
        for file in files:
            if not file.is_file():
                continue

            # Check exclude dirs
            if any(excluded in file.parts for excluded in exclude_dirs):
                continue

            # Skip large files (>1MB)
            if file.stat().st_size > 1_000_000:
                continue

            result.append(file)

        return result

    def _should_index_file(self, file_path: Path) -> bool:
        """Check if a file should be indexed."""
        # Skip hidden files
        if file_path.name.startswith('.'):
            return False

        # Skip test files (optional, can be configured)
        # if 'test' in file_path.parts:
        #     return False

        return True

    def _detect_changes(self) -> List[str]:
        """Detect files that have changed since last index."""
        changed = []

        for file_path in self._scan_code_files():
            file_str = str(file_path.relative_to(self.repo_path))

            # Check if file needs indexing
            if file_str not in self._file_metadata:
                changed.append(file_str)
                continue

            # Check modification time
            metadata = self._file_metadata[file_str]
            current_mtime = file_path.stat().st_mtime

            if current_mtime > metadata.mtime:
                changed.append(file_str)

        return changed

    def _index_file(self, file_path: Path) -> List[Symbol]:
        """
        Index a single file.

        Args:
            file_path: Path to the file

        Returns:
            List of symbols found
        """
        try:
            # Try tree-sitter first
            symbols = self._index_with_tree_sitter(file_path)

            if not symbols:
                # Fallback to regex-based parsing
                symbols = self._index_with_regex(file_path)

            # Store symbols
            self._store_symbols(str(file_path.relative_to(self.repo_path)), symbols)

            return symbols

        except Exception as e:
            logger.warning(f"Failed to index {file_path}: {e}")
            return []

    def _index_with_tree_sitter(self, file_path: Path) -> List[Symbol]:
        """Index file using tree-sitter parser."""
        try:
            import tree_sitter

            # Get language for file
            language = self._get_tree_sitter_language(file_path)
            if language is None:
                return []

            parser = tree_sitter.Parser()
            parser.set_language(language)

            source_code = file_path.read_text(encoding='utf-8', errors='ignore')
            tree = parser.parse(bytes(source_code, 'utf-8'))

            symbols = []
            self._extract_symbols_from_tree(tree.root_node, str(file_path), source_code, symbols)

            return symbols

        except ImportError:
            # tree-sitter not available
            return []
        except Exception as e:
            logger.debug(f"tree-sitter parsing failed: {e}")
            return []

    def _extract_symbols_from_tree(
        self,
        node,
        file_path: str,
        source: str,
        symbols: List[Symbol],
        parent: Optional[str] = None,
    ):
        """Extract symbols from tree-sitter syntax tree."""
        from tree_sitter import Node

        # Define symbol node types by language
        symbol_types = {
            'function_definition',
            'class_definition',
            'method_definition',
            'variable_declaration',
            'const_declaration',
            'interface_definition',
            'type_definition',
            'enum_declaration',
        }

        if node.type in symbol_types:
            # Extract symbol info
            name_node = node.child_by_field_name('name')
            if name_node:
                name = source[name_node.start_byte:name_node.end_byte]

                # Determine kind
                kind = node.type.replace('_definition', '').replace('_declaration', '')

                symbol = Symbol(
                    name=name,
                    kind=kind,
                    language=self._get_language_from_path(file_path),
                    file_path=file_path,
                    line=node.start_point[0] + 1,
                    column=node.start_point[1],
                    end_line=node.end_point[0] + 1,
                    parent=parent,
                )

                symbols.append(symbol)

                # Recurse into children with this symbol as parent
                for child in node.children:
                    self._extract_symbols_from_tree(
                        child, file_path, source, symbols, parent=name
                    )
                return

        # Recurse into children
        for child in node.children:
            self._extract_symbols_from_tree(child, file_path, source, symbols, parent)

    def _index_with_regex(self, file_path: Path) -> List[Symbol]:
        """Index file using regex-based parsing (fallback)."""
        import re

        # Simple regex patterns for common languages
        patterns = {
            'function': [
                (r'def\s+(\w+)\s*\(', ['python']),
                (r'function\s+(\w+)\s*\(', ['javascript']),
                (r'(\w+)\s*\([^)]*\)\s*{', ['c', 'cpp']),
            ],
            'class': [
                (r'class\s+(\w+)', ['python']),
                (r'class\s+(\w+)\s*{', ['javascript', 'java']),
            ],
        }

        source = file_path.read_text(encoding='utf-8', errors='ignore')
        symbols = []
        language = self._get_language_from_path(str(file_path))

        for kind, lang_patterns in patterns.items():
            for pattern, langs in lang_patterns:
                if language in langs:
                    for match in re.finditer(pattern, source):
                        name = match.group(1)
                        line_num = source[:match.start()].count('\n') + 1

                        symbols.append(Symbol(
                            name=name,
                            kind=kind,
                            language=language,
                            file_path=str(file_path.relative_to(self.repo_path)),
                            line=line_num,
                            column=match.start() - source.rfind('\n', 0, match.start()) - 1,
                        ))

        return symbols

    def _store_symbols(self, file_path: str, symbols: List[Symbol]):
        """Store symbols in the index."""
        # Remove old symbols for this file
        self._remove_file_symbols(file_path)

        # Store file metadata
        full_path = self.repo_path / file_path
        stat = full_path.stat()

        self._file_metadata[file_path] = FileIndex(
            path=file_path,
            size=stat.st_size,
            mtime=stat.st_mtime,
            hash=self._hash_file(full_path),
            indexed_at=datetime.now(),
            symbol_count=len(symbols),
        )

        # Index by name
        for symbol in symbols:
            self._symbols_by_name[symbol.name].append(symbol)
            self._symbols_by_file[file_path].append(symbol)
            self._symbols_by_kind[symbol.kind].append(symbol)

    def _remove_file_symbols(self, file_path: str):
        """Remove all symbols for a file."""
        # Get old symbols
        old_symbols = self._symbols_by_file.get(file_path, [])

        # Remove from name index
        for symbol in old_symbols:
            if symbol in self._symbols_by_name[symbol.name]:
                self._symbols_by_name[symbol.name].remove(symbol)
            if symbol in self._symbols_by_kind[symbol.kind]:
                self._symbols_by_kind[symbol.kind].remove(symbol)

        # Remove from file index
        if file_path in self._symbols_by_file:
            del self._symbols_by_file[file_path]

        # Remove metadata
        if file_path in self._file_metadata:
            del self._file_metadata[file_path]

    def _get_tree_sitter_language(self, file_path: Path):
        """Get tree-sitter language for file."""
        try:
            import tree_sitter

            language_map = {
                '.py': tree_sitter.Language(tree_sitter.Language.PYTHON),
                '.js': tree_sitter.Language(tree_sitter.Language.JAVASCRIPT),
                '.ts': tree_sitter.Language(tree_sitter.Language.TYPESCRIPT),
                '.jsx': tree_sitter.Language(tree_sitter.Language.JAVASCRIPT),
                '.tsx': tree_sitter.Language(tree_sitter.Language.TYPESCRIPT),
                '.go': tree_sitter.Language(tree_sitter.Language.GO),
                '.rs': tree_sitter.Language(tree_sitter.Language.RUST),
                '.c': tree_sitter.Language(tree_sitter.Language.C),
                '.cpp': tree_sitter.Language(tree_sitter.Language.CPP),
                '.cc': tree_sitter.Language(tree_sitter.Language.CPP),
                '.h': tree_sitter.Language(tree_sitter.Language.C),
                '.hpp': tree_sitter.Language(tree_sitter.Language.CPP),
                '.java': tree_sitter.Language(tree_sitter.Language.JAVA),
            }

            return language_map.get(file_path.suffix)

        except ImportError:
            return None
        except Exception:
            return None

    def _get_language_from_path(self, file_path: str) -> str:
        """Get language name from file path."""
        ext = Path(file_path).suffix.lower()

        language_map = {
            '.py': 'python',
            '.pyw': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.go': 'go',
            '.rs': 'rust',
            '.rb': 'ruby',
            '.php': 'php',
            '.sh': 'shell',
            '.bash': 'shell',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.json': 'json',
            '.toml': 'toml',
        }

        return language_map.get(ext, 'unknown')

    def _hash_file(self, file_path: Path) -> str:
        """Calculate file hash for change detection."""
        # Use mtime + size as a fast hash
        stat = file_path.stat()
        return f"{stat.st_mtime}:{stat.st_size}"
