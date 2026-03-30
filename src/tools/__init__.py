"""
Code Exploration Tools

Provides tools for exploring and understanding code repositories.
"""

from .base import BaseTool, ToolResult, ToolError
from .code_search import CodeSearchTool
from .file_reader import FileReadTool
from .symbol_lookup import SymbolLookupTool
from .file_finder import FileFinderTool
from .fast_symbol_lookup import FastSymbolLookupTool

__all__ = [
    "BaseTool",
    "ToolResult",
    "ToolError",
    "CodeSearchTool",
    "FileReadTool",
    "SymbolLookupTool",
    "FileFinderTool",
    "FastSymbolLookupTool",
]


def get_all_tools(repo_path: str, use_index: bool = True) -> list:
    """
    Get all available tools for a repository.

    Args:
        repo_path: Path to the code repository
        use_index: Use indexed tools when available (faster)

    Returns:
        List of tool instances
    """
    tools = [
        CodeSearchTool(repo_path),
        FileReadTool(repo_path),
        SymbolLookupTool(repo_path),
        FileFinderTool(repo_path),
    ]

    # Add fast indexed tools
    if use_index:
        try:
            tools.append(FastSymbolLookupTool(repo_path))
        except Exception:
            pass  # Index not available, skip

    return tools


def get_tool_definitions(repo_path: str, use_index: bool = True) -> list:
    """
    Get tool definitions for LLM API.

    Args:
        repo_path: Path to the code repository
        use_index: Use indexed tools when available

    Returns:
        List of tool definitions in LLM format
    """
    tools = get_all_tools(repo_path, use_index=use_index)
    return [tool.to_dict() for tool in tools]
