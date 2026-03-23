"""
File Finder Tool

Find files by name or pattern in the repository.
"""

import logging
from pathlib import Path
from typing import Dict, Any, List

from .base import BaseTool, ToolError

logger = logging.getLogger(__name__)


class FileFinderTool(BaseTool):
    """
    Find files by name or pattern.

    This tool allows the Agent to discover files in the repository
    matching specific patterns or criteria.
    """

    @property
    def name(self) -> str:
        return "file_find"

    @property
    def description(self) -> str:
        return """Find files in the repository by name or pattern.

Use this tool when you need to:
- Find all files with a specific name
- List files matching a pattern (e.g., all test files)
- Discover files in a directory
- Find configuration or documentation files

The tool returns file paths relative to the repository root.
"""

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "File name pattern (supports wildcards: *, ?, **)"
                },
                "directory": {
                    "type": "string",
                    "description": "Directory to search in (relative to repo root, default: root)"
                },
                "file_type": {
                    "type": "string",
                    "description": "File extension to filter (e.g., 'py', 'java', 'js')"
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 50
                }
            },
            "required": ["pattern"]
        }

    def execute(self, input_data: Dict[str, Any]) -> str:
        """
        Execute file find.

        Args:
            input_data: Find parameters

        Returns:
            str: Find results
        """
        self.validate_input(input_data)

        pattern = input_data["pattern"]
        directory = input_data.get("directory", "")
        file_type = input_data.get("file_type")
        max_results = input_data.get("max_results", 50)

        try:
            results = self._find(
                pattern=pattern,
                directory=directory,
                file_type=file_type,
                max_results=max_results,
            )
            return self._format_results(results, pattern)
        except Exception as e:
            raise ToolError(
                f"File find failed: {str(e)}",
                tool_name=self.name
            )

    def _find(
        self,
        pattern: str,
        directory: str = "",
        file_type: str = None,
        max_results: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Find files matching the pattern.

        Args:
            pattern: File name pattern
            directory: Directory to search in
            file_type: File extension filter
            max_results: Maximum results

        Returns:
            List of file info dictionaries
        """
        # Resolve search directory
        search_dir = self.repo_path
        if directory:
            search_dir = self.repo_path / directory
            if not search_dir.exists():
                raise ToolError(
                    f"Directory not found: {directory}",
                    tool_name=self.name
                )

        # Compile pattern
        from fnmatch import fnmatch
        import re

        # Convert glob pattern to regex
        regex_pattern = self._glob_to_regex(pattern)
        regex = re.compile(regex_pattern, re.IGNORECASE)

        results = []

        # Walk through directory
        # Handle different Python versions: Path.walk() returns Path objects in 3.12+
        for item in search_dir.walk():
            # In Python 3.12+, walk() yields Path objects directly
            # In earlier versions or different implementations, it might yield tuples
            if isinstance(item, tuple):
                # Old format: (dirpath, dirs, files)
                dirpath, dirs, files = item
                for file in files:
                    if not isinstance(file, str):
                        continue

                    # Skip hidden files
                    if file.startswith('.'):
                        continue

                    # Check pattern match
                    if not regex.match(file):
                        continue

                    # Check file type
                    if file_type:
                        # Extract extension
                        if '.' in file:
                            file_ext = file.rsplit('.', 1)[-1]
                            if file_ext.lower() != file_type.lower():
                                continue
                        else:
                            continue

                    # Get file info
                    file_path = Path(dirpath) / file
                    try:
                        rel_path = file_path.relative_to(self.repo_path)
                        stat = file_path.stat()

                        results.append({
                            "path": str(rel_path).replace('\\', '/'),
                            "name": file,
                            "size": stat.st_size,
                            "is_file": True,
                        })

                        if len(results) >= max_results:
                            return results

                    except (ValueError, OSError):
                        # Skip files that can't be resolved
                        continue
            else:
                # New format: item is a Path object
                entry = item
                if not entry.is_file():
                    continue

                file = entry.name

                # Skip hidden files
                if file.startswith('.'):
                    continue

                # Check pattern match
                if not regex.match(file):
                    continue

                # Check file type
                if file_type:
                    file_ext = entry.suffix.lstrip('.')
                    if file_ext and file_ext.lower() != file_type.lower():
                        continue

                # Get file info
                try:
                    rel_path = entry.relative_to(self.repo_path)
                    stat = entry.stat()

                    results.append({
                        "path": str(rel_path).replace('\\', '/'),
                        "name": file,
                        "size": stat.st_size,
                        "is_file": entry.is_file(),
                    })

                    if len(results) >= max_results:
                        return results

                except (ValueError, OSError):
                    # Skip files that can't be resolved
                    continue

        return results

    def _glob_to_regex(self, pattern: str) -> str:
        """
        Convert glob pattern to regex.

        Args:
            pattern: Glob pattern (supports *, ?, **)

        Returns:
            str: Regex pattern
        """
        import re

        # Escape special regex characters except wildcards
        result = ""
        i = 0
        while i < len(pattern):
            char = pattern[i]

            if char == '*':
                # Check for **
                if i + 1 < len(pattern) and pattern[i + 1] == '*':
                    result += ".*"
                    i += 2
                else:
                    result += "[^/]*"
                    i += 1
            elif char == '?':
                result += "[^/]"
                i += 1
            elif char in '.^$+()[]{}|\\/':
                result += '\\' + char
                i += 1
            else:
                result += char
                i += 1

        return "^" + result + "$"

    def _format_results(self, results: List[Dict], pattern: str) -> str:
        """
        Format find results.

        Args:
            results: List of file info dictionaries
            pattern: Original search pattern

        Returns:
            str: Formatted results
        """
        if not results:
            return f"No files found matching pattern: {pattern}"

        output_lines = [f"Found {len(results)} file(s) matching '{pattern}':\n"]

        for i, file_info in enumerate(results, 1):
            path = file_info["path"]
            name = file_info["name"]
            size = file_info["size"]

            # Format size
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f} MB"

            output_lines.append(f"{i}. {path}")
            output_lines.append(f"   Size: {size_str}")
            output_lines.append("")

        return "\n".join(output_lines)
