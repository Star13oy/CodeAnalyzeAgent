"""
Code Exploration Tools

Provides tools for exploring and understanding code repositories.
"""

from .base import BaseTool, ToolResult, ToolError
from .code_search import CodeSearchTool
from .file_reader import FileReadTool
from .symbol_lookup import SymbolLookupTool
from .file_finder import FileFinderTool

__all__ = [
    "BaseTool",
    "ToolResult",
    "ToolError",
    "CodeSearchTool",
    "FileReadTool",
    "SymbolLookupTool",
    "FileFinderTool",
]


def get_all_tools(repo_path: str) -> list:
    """
    Get all available tools for a repository.

    Args:
        repo_path: Path to the code repository

    Returns:
        List of tool instances
    """
    return [
        CodeSearchTool(repo_path),
        FileReadTool(repo_path),
        SymbolLookupTool(repo_path),
        FileFinderTool(repo_path),
    ]


def get_tool_definitions(repo_path: str) -> list:
    """
    Get tool definitions for LLM API.

    Args:
        repo_path: Path to the code repository

    Returns:
        List of tool definitions in LLM format
    """
    tools = get_all_tools(repo_path)
    return [tool.to_dict() for tool in tools]
