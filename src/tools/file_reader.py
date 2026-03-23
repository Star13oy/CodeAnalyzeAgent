"""
File Reader Tool

Read file contents from the repository.
"""

import logging
from pathlib import Path
from typing import Dict, Any

from .base import BaseTool, ToolError

logger = logging.getLogger(__name__)


class FileReadTool(BaseTool):
    """
    Read file contents.

    This tool allows the Agent to read the actual contents of files
    in the repository for detailed analysis.
    """

    @property
    def name(self) -> str:
        return "file_read"

    @property
    def description(self) -> str:
        return """Read the contents of a file in the repository.

Use this tool when you need to:
- Read the full content of a specific file
- Examine implementation details
- Understand how a function or class is implemented
- Read configuration files

The tool returns the file content with optional line range filtering.
"""

    @property
    def input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Relative path to the file from repository root"
                },
                "start_line": {
                    "type": "integer",
                    "description": "Starting line number (1-indexed, inclusive)",
                    "minimum": 1
                },
                "end_line": {
                    "type": "integer",
                    "description": "Ending line number (1-indexed, inclusive)",
                    "minimum": 1
                },
                "max_lines": {
                    "type": "integer",
                    "description": "Maximum number of lines to return (default: 500)",
                    "default": 500
                }
            },
            "required": ["path"]
        }

    def execute(self, input_data: Dict[str, Any]) -> str:
        """
        Execute file read.

        Args:
            input_data: Read parameters

        Returns:
            str: File content
        """
        self.validate_input(input_data)

        file_path = input_data["path"]
        start_line = input_data.get("start_line")
        end_line = input_data.get("end_line")
        max_lines = input_data.get("max_lines", 500)

        try:
            full_path = self._resolve_path(file_path)
            content = self._read_file(
                full_path,
                start_line=start_line,
                end_line=end_line,
                max_lines=max_lines,
            )
            return self._format_content(content, file_path, start_line)
        except FileNotFoundError:
            raise ToolError(
                f"File not found: {file_path}",
                tool_name=self.name
            )
        except Exception as e:
            raise ToolError(
                f"Failed to read file: {str(e)}",
                tool_name=self.name
            )

    def _resolve_path(self, relative_path: str) -> Path:
        """
        Resolve relative path to absolute path within repository.

        Args:
            relative_path: Relative path from repository root

        Returns:
            Path: Resolved absolute path

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        # Remove leading slash if present (LLM sometimes generates paths like /src/file.py)
        if relative_path.startswith('/'):
            relative_path = relative_path[1:]

        # Prevent path traversal attacks
        resolved = (self.repo_path / relative_path).resolve()
        if not str(resolved).startswith(str(self.repo_path.resolve())):
            raise ToolError(
                "Invalid path: path traversal detected",
                tool_name=self.name
            )

        if not resolved.exists():
            raise FileNotFoundError(f"File not found: {relative_path}")

        if not resolved.is_file():
            raise ToolError(
                f"Not a file: {relative_path}",
                tool_name=self.name
            )

        return resolved

    def _read_file(
        self,
        file_path: Path,
        start_line: int = None,
        end_line: int = None,
        max_lines: int = 500,
    ) -> str:
        """
        Read file content with optional line range.

        Args:
            file_path: Path to the file
            start_line: Starting line number (1-indexed)
            end_line: Ending line number (1-indexed)
            max_lines: Maximum lines to return

        Returns:
            str: File content
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            if start_line is not None or end_line is not None:
                # Convert to 0-indexed
                start = (start_line - 1) if start_line else 0
                end = end_line if end_line else len(lines)
                lines = lines[start:end]

            # Limit lines
            if len(lines) > max_lines:
                lines = lines[:max_lines]
                truncated = True
            else:
                truncated = False

            content = ''.join(lines)

            if truncated:
                content += f"\n... (truncated, showing first {max_lines} lines)"

            return content

        except UnicodeDecodeError:
            # Try with different encoding
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    lines = f.readlines()
                return ''.join(lines[:max_lines])
            except Exception:
                raise ToolError(
                    f"Could not decode file: {file_path}",
                    tool_name=self.name
                )

    def _format_content(self, content: str, file_path: str, start_line: int = None) -> str:
        """
        Format file content for display.

        Args:
            content: File content
            file_path: Original file path
            start_line: Starting line number if range was used

        Returns:
            str: Formatted content
        """
        output = [f"File: {file_path}"]
        if start_line:
            output.append(f"Starting from line: {start_line}")
        output.append("")
        output.append(content)
        return "\n".join(output)
