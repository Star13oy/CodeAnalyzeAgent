"""
Symbol Lookup Tool

Find symbols (functions, classes, methods) using ctags.
"""

import logging
import subprocess
from pathlib import Path
from typing import Dict, Any, List

from .base import BaseTool, ToolError

logger = logging.getLogger(__name__)


class SymbolLookupTool(BaseTool):
    """
    Look up symbols (functions, classes, methods) using ctags.

    This tool provides fast symbol lookup capabilities by using
    universal-ctags to index the codebase.
    """

    TAGS_FILE = ".tags"

    def __init__(self, repo_path: str):
        super().__init__(repo_path)
        self.tags_file = self.repo_path / self.TAGS_FILE
        self._ensure_index()

    @property
    def name(self) -> str:
        return "symbol_lookup"

    @property
    def description(self) -> str:
        return """Look up symbols (functions, classes, methods, variables) in the codebase.

Use this tool when you need to:
- Find where a function, class, or method is defined
- Locate all definitions of a symbol
- Find symbols of a specific type (e.g., only functions)
- Understand the structure of the codebase

The tool returns the file path and line number where each symbol is defined.
"""

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "Symbol name to look up (function name, class name, etc.)"
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
                        "struct",
                        "interface",
                        "enum",
                    ]
                },
                "exact_match": {
                    "type": "boolean",
                    "description": "Whether to require exact symbol name match",
                    "default": True
                },
                "language": {
                    "type": "string",
                    "description": "Filter by programming language (e.g., 'Python', 'Java')"
                }
            },
            "required": ["symbol"]
        }

    def execute(self, input_data: Dict[str, Any]) -> str:
        """
        Execute symbol lookup.

        Args:
            input_data: Lookup parameters

        Returns:
            str: Lookup results
        """
        self.validate_input(input_data)

        symbol = input_data["symbol"]
        kind = input_data.get("kind")
        exact_match = input_data.get("exact_match", True)
        language = input_data.get("language")

        try:
            results = self._lookup(
                symbol=symbol,
                kind=kind,
                exact_match=exact_match,
                language=language,
            )
            return self._format_results(results, symbol)
        except Exception as e:
            raise ToolError(
                f"Symbol lookup failed: {str(e)}",
                tool_name=self.name
            )

    def _ensure_index(self) -> None:
        """
        Ensure the tags index exists.

        Creates the index if it doesn't exist or is outdated.
        """
        if not self.tags_file.exists():
            logger.info(f"Creating ctags index at {self.tags_file}")
            self._build_index()

    def _build_index(self) -> None:
        """Build the ctags index."""
        cmd = [
            "ctags",
            "-R",
            "--fields=+ne",
            "--output-format=json",
            "-o", str(self.tags_file),
            str(self.repo_path),
        ]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                timeout=300,  # 5 minutes timeout for large repos
            )
            logger.info(f"Successfully created ctags index")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create ctags index: {e.stderr}")
            # Don't raise - the tool can still work with partial results
        except FileNotFoundError:
            logger.warning("ctags not found, symbol lookup will be limited")
            self.tags_file = None

    def _lookup(
        self,
        symbol: str,
        kind: str = None,
        exact_match: bool = True,
        language: str = None,
    ) -> List[Dict]:
        """
        Look up symbols in the tags file.

        Returns:
            List of symbol dictionaries
        """
        if not self.tags_file or not self.tags_file.exists():
            return []

        # Build grep pattern
        if exact_match:
            pattern = f"^{symbol}\t"
        else:
            pattern = symbol

        cmd = ["grep", "-E", pattern, str(self.tags_file)]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return []

            return self._parse_tags_output(result.stdout, kind, language)

        except subprocess.TimeoutExpired:
            logger.warning("Symbol lookup timed out")
            return []
        except Exception as e:
            logger.error(f"Symbol lookup error: {e}")
            return []

    def _parse_tags_output(
        self,
        output: str,
        kind_filter: str = None,
        language_filter: str = None,
    ) -> List[Dict]:
        """
        Parse ctags output.

        Args:
            output: Raw ctags output
            kind_filter: Filter by symbol kind
            language_filter: Filter by language

        Returns:
            List of symbol dictionaries
        """
        symbols = []

        for line in output.strip().split('\n'):
            if not line:
                continue

            # Parse tags line format: symbol<TAB>file<TAB>address;"<TAB>kind
            parts = line.split('\t')
            if len(parts) < 4:
                continue

            symbol = {
                "name": parts[0],
                "path": parts[1],
                "address": parts[2] if len(parts) > 2 else "",
            }

            # Parse extra fields (format: key:value)
            for part in parts[3:]:
                if ':' in part:
                    key, value = part.split(':', 1)
                    symbol[key] = value

            # Apply filters
            if kind_filter and symbol.get("kind") != kind_filter:
                continue

            if language_filter and symbol.get("language") != language_filter:
                continue

            symbols.append(symbol)

        return symbols

    def _format_results(self, symbols: List[Dict], symbol: str) -> str:
        """
        Format lookup results.

        Args:
            symbols: List of symbol dictionaries
            symbol: Original search symbol

        Returns:
            str: Formatted results
        """
        if not symbols:
            return f"Symbol '{symbol}' not found in the codebase."

        output_lines = [f"Found {len(symbols)} definition(s) for '{symbol}':\n"]

        # Group by file
        by_file = {}
        for s in symbols:
            path = s.get("path", "unknown")
            if path not in by_file:
                by_file[path] = []
            by_file[path].append(s)

        # Format results
        for path, path_symbols in by_file.items():
            output_lines.append(f"📄 {path}")

            for s in path_symbols:
                kind = s.get("kind", "unknown")
                line = s.get("line", "?")
                language = s.get("language", "")

                kind_emoji = self._get_kind_emoji(kind)
                output_lines.append(f"   {kind_emoji} {kind} at line {line}")
                if language:
                    output_lines.append(f"      Language: {language}")

            output_lines.append("")

        return "\n".join(output_lines)

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
