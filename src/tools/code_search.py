"""
Code Search Tool

Uses ripgrep for fast code searching.
"""

import json
import logging
import subprocess
from typing import Dict, Any

from .base import BaseTool, ToolError, ToolStatus

logger = logging.getLogger(__name__)


class CodeSearchTool(BaseTool):
    """
    Search code using ripgrep.

    This tool provides fast, powerful code search capabilities
    using ripgrep (rg command).
    """

    @property
    def name(self) -> str:
        return "code_search"

    @property
    def description(self) -> str:
        return """Search for code patterns in the repository.

Use this tool when you need to:
- Find where a specific function, class, or variable is used
- Search for specific text or patterns in the code
- Locate all occurrences of a keyword
- Find code that matches a regular expression

The tool returns matching lines with file paths and line numbers,
along with surrounding context for better understanding.
"""

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (text or regular expression)"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File pattern to filter (e.g., '*.py', '**/*.java'). Use '**/*' for all files."
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Number of context lines to show before and after matches",
                    "default": 3
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "Whether to use case-sensitive search",
                    "default": False
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 100
                }
            },
            "required": ["query"]
        }

    def execute(self, input_data: Dict[str, Any]) -> str:
        """
        Execute code search.

        Args:
            input_data: Search parameters

        Returns:
            str: Search results in formatted text
        """
        self.validate_input(input_data)

        query = input_data["query"]
        file_pattern = input_data.get("file_pattern")
        context_lines = input_data.get("context_lines", 3)
        case_sensitive = input_data.get("case_sensitive", False)
        max_results = input_data.get("max_results", 100)

        try:
            results = self._search(
                query=query,
                file_pattern=file_pattern,
                context_lines=context_lines,
                case_sensitive=case_sensitive,
                max_results=max_results,
            )
            return self._format_results(results)
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:
                # No results found
                return f"No matches found for query: {query}"
            raise ToolError(
                f"Search failed: {e.stderr}",
                tool_name=self.name,
                details={"exit_code": e.returncode}
            )
        except Exception as e:
            raise ToolError(
                f"Unexpected error: {str(e)}",
                tool_name=self.name
            )

    def _search(
        self,
        query: str,
        file_pattern: str = None,
        context_lines: int = 3,
        case_sensitive: bool = False,
        max_results: int = 100,
    ) -> list:
        """
        Execute code search using ripgrep or Python fallback.

        Returns:
            List of match dictionaries
        """
        # Try ripgrep first
        try:
            return self._search_with_rg(query, file_pattern, context_lines, case_sensitive, max_results)
        except FileNotFoundError:
            # ripgrep not found, use Python fallback
            logger.info("ripgrep not found, using Python search")
            return self._search_python(query, file_pattern, context_lines, case_sensitive, max_results)
        except Exception as e:
            # Other error, try Python fallback
            logger.warning(f"ripgrep failed: {e}, using Python search")
            return self._search_python(query, file_pattern, context_lines, case_sensitive, max_results)

    def _search_with_rg(
        self,
        query: str,
        file_pattern: str = None,
        context_lines: int = 3,
        case_sensitive: bool = False,
        max_results: int = 100,
    ) -> list:
        """Search using ripgrep."""
        cmd = [
            "rg",
            query,
            str(self.repo_path),
            "-C", str(context_lines),
            "--json",
            "-M", str(max_results),
        ]

        if not case_sensitive:
            cmd.append("-i")

        if file_pattern:
            cmd.extend(["-g", file_pattern])

        logger.debug(f"Running search command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode not in [0, 1]:
            raise ToolError(
                f"ripgrep error: {result.stderr}",
                tool_name=self.name
            )

        return self._parse_json_output(result.stdout)

    def _search_python(
        self,
        query: str,
        file_pattern: str = None,
        context_lines: int = 3,
        case_sensitive: bool = False,
        max_results: int = 100,
    ) -> list:
        """Search using Python (fallback for Windows without ripgrep)."""
        import re
        from pathlib import Path

        matches = []
        count = 0

        # Compile regex pattern
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(query, flags)
        except re.error:
            # If regex fails, treat as literal string
            pattern = re.compile(re.escape(query), flags)

        # Get files to search
        if file_pattern:
            # Convert glob pattern to regex
            glob_pattern = file_pattern.replace(".", r"\.").replace("*", ".*").replace("?", ".")
            file_regex = re.compile(glob_pattern, flags)
        else:
            file_regex = None

        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Filter by file pattern
            if file_regex and not file_regex.match(file_path.name):
                continue

            # Skip binary files
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(file_path, 1):
                        if pattern.search(line):
                            # Collect context lines
                            start = max(1, line_num - context_lines)
                            end = line_num + context_lines
                            context_lines_list = []

                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f2:
                                for i, ctx_line in enumerate(f2, 1):
                                    if start <= i <= end:
                                        context_lines_list.append({
                                            "line_num": i,
                                            "text": ctx_line.rstrip("\n")
                                        })

                            matches.append({
                                "path": str(file_path.relative_to(self.repo_path)),
                                "line_number": line_num,
                                "lines": {"text": "\n".join(m["text"] for m in context_lines_list)},
                            })

                            count += 1
                            if count >= max_results:
                                return matches
            except (UnicodeDecodeError, PermissionError):
                continue

        return matches

    def _parse_json_output(self, output: str) -> list:
        """
        Parse ripgrep JSON output.

        Returns:
            List of match dictionaries grouped by file
        """
        matches = []
        current_match = None

        for line in output.strip().split('\n'):
            if not line:
                continue

            try:
                data = json.loads(line)
                data_type = data.get("type")

                if data_type == "begin":
                    # Start of a new match
                    current_match = {
                        "path": data.get("path", ""),
                        "lines": {"text": data.get("lines", {}).get("text", "")},
                        "line_number": data.get("line_number", 0),
                    }
                elif data_type == "match":
                    # Actual match line
                    if current_match:
                        current_match["lines"]["text"] += data.get("lines", {}).get("text", "")
                        current_match["submatches"] = data.get("submatches", [])
                elif data_type == "end":
                    # End of current match
                    if current_match:
                        matches.append(current_match)
                    current_match = None

            except json.JSONDecodeError:
                logger.warning(f"Failed to parse ripgrep output: {line}")
                continue

        return matches

    def _format_results(self, matches: list) -> str:
        """
        Format search results for display.

        Args:
            matches: List of match dictionaries

        Returns:
            str: Formatted results
        """
        if not matches:
            return "No matches found."

        output_lines = [f"Found {len(matches)} match(es):\n"]

        for i, match in enumerate(matches, 1):
            path = match.get("path", "unknown")
            line_num = match.get("line_number", 0)
            lines_text = match.get("lines", {}).get("text", "")

            output_lines.append(f"{i}. {path}:{line_num}")
            output_lines.append(f"   {lines_text}")
            output_lines.append("")

        return "\n".join(output_lines)
