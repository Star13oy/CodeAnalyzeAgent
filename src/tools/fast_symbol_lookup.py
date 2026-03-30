"""
Fast Symbol Lookup Tool

Uses pre-built index for instant symbol lookup.
"""

import logging
from typing import Dict, Any, List, Optional

from .base import BaseTool, ToolError

logger = logging.getLogger(__name__)


class FastSymbolLookupTool(BaseTool):
    """
    Fast symbol lookup using pre-built index.

    This tool provides O(1) symbol lookups by using an in-memory index
    instead of parsing files on each query.
    """

    def __init__(self, repo_path: str, index_manager=None):
        """
        Initialize the fast symbol lookup tool.

        Args:
            repo_path: Path to the repository
            index_manager: Optional IndexManager instance
        """
        super().__init__(repo_path)
        self._index_manager = index_manager

    def _get_index_manager(self):
        """Get or create the index manager."""
        if self._index_manager is None:
            from ..index import get_index_manager
            self._index_manager = get_index_manager(str(self.repo_path))
        return self._index_manager

    @property
    def name(self) -> str:
        return "fast_symbol_lookup"

    @property
    def description(self) -> str:
        return """Quickly look up symbols (functions, classes, methods) in the codebase.

This tool uses a pre-built index for instant lookups (O(1) time complexity).

Use this tool when you need to:
- Find where a function, class, or method is defined
- Locate all definitions of a symbol
- Find symbols by prefix (auto-complete style)
- Get all symbols in a specific file

The tool returns the file path, line number, and symbol kind for each match.

Results are returned instantly - no file scanning required."""

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name to look up (function name, class name, etc.). Supports partial matching with prefix search."
                },
                "kind": {
                    "type": "string",
                    "description": "Filter by symbol kind",
                    "enum": [
                        "function",
                        "class",
                        "method",
                        "variable",
                        "constant",
                    ]
                },
                "file": {
                    "type": "string",
                    "description": "Get all symbols in this specific file instead of looking up by name"
                },
                "prefix": {
                    "type": "boolean",
                    "description": "Use prefix matching instead of exact match (default: false)",
                    "default": False
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 50)",
                    "default": 50
                }
            },
            "required": []
        }

    def execute(self, input_data: Dict[str, Any]) -> str:
        """
        Execute fast symbol lookup.

        Args:
            input_data: Lookup parameters

        Returns:
            str: Lookup results
        """
        self.validate_input(input_data)

        index_mgr = self._get_index_manager()

        # If file is specified, get all symbols in that file
        if "file" in input_data:
            return self._get_file_symbols(index_mgr, input_data["file"])

        symbol = input_data.get("symbol")
        if not symbol:
            return "Error: Either 'symbol' or 'file' parameter is required"

        kind = input_data.get("kind")
        use_prefix = input_data.get("prefix", False)
        limit = input_data.get("limit", 50)

        try:
            # Perform lookup
            if use_prefix:
                results = index_mgr.lookup_symbol_prefix(symbol, kind=kind, limit=limit)
            else:
                results = index_mgr.lookup_symbol(symbol, kind=kind)

            return self._format_results(results, symbol)

        except Exception as e:
            raise ToolError(
                f"Symbol lookup failed: {str(e)}",
                tool_name=self.name,
            )

    def _get_file_symbols(self, index_mgr, file_path: str) -> str:
        """Get all symbols in a file."""
        try:
            symbols = index_mgr.get_file_symbols(file_path)

            if not symbols:
                return f"No symbols found in file: {file_path}"

            # Group by kind
            by_kind: Dict[str, List] = {}
            for symbol in symbols:
                if symbol.kind not in by_kind:
                    by_kind[symbol.kind] = []
                by_kind[symbol.kind].append(symbol)

            # Format results
            output = [f"Found {len(symbols)} symbol(s) in {file_path}:\n"]

            for kind in sorted(by_kind.keys()):
                output.append(f"\n{kind.upper()}:")
                for symbol in by_kind[kind]:
                    output.append(f"  - {symbol.name} (line {symbol.line})")

            return "\n".join(output)

        except Exception as e:
            return f"Error reading symbols from {file_path}: {e}"

    def _format_results(self, symbols: List, query: str) -> str:
        """Format lookup results."""
        if not symbols:
            return f"Symbol '{query}' not found in the codebase."

        output = [f"Found {len(symbols)} definition(s) for '{query}':\n"]

        # Group by file
        by_file: Dict[str, List] = {}
        for symbol in symbols:
            if symbol.file_path not in by_file:
                by_file[symbol.file_path] = []
            by_file[symbol.file_path].append(symbol)

        # Format results
        for file_path, file_symbols in sorted(by_file.items()):
            output.append(f"\n📄 {file_path}")

            for symbol in file_symbols:
                kind_emoji = self._get_kind_emoji(symbol.kind)
                output.append(f"   {kind_emoji} {symbol.kind} '{symbol.name}' at line {symbol.line}")

                if symbol.signature:
                    output.append(f"      Signature: {symbol.signature}")

                if symbol.parent:
                    output.append(f"      Parent: {symbol.parent}")

        return "\n".join(output)

    def _get_kind_emoji(self, kind: str) -> str:
        """Get emoji for symbol kind."""
        emojis = {
            "function": "ƒ",
            "method": "m",
            "class": "C",
            "variable": "v",
            "constant": "c",
            "struct": "s",
            "interface": "I",
            "enum": "E",
        }
        return emojis.get(kind, "•")
