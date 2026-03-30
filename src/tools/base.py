"""
Tool Base Interface

Defines the abstract interface for all tools.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ToolStatus(str, Enum):
    """Tool execution status"""
    SUCCESS = "success"
    ERROR = "error"
    NOT_FOUND = "not_found"


@dataclass
class ToolResult:
    """Result of tool execution"""
    status: ToolStatus
    content: str
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "status": self.status.value,
            "content": self.content,
            "metadata": self.metadata,
        }


class ToolError(Exception):
    """Exception raised when tool execution fails"""

    def __init__(self, message: str, tool_name: str = "", details: Dict[str, Any] = None):
        self.message = message
        self.tool_name = tool_name
        self.details = details or {}
        super().__init__(f"{tool_name}: {message}" if tool_name else message)


class BaseTool(ABC):
    """
    Abstract base class for all tools.

    All tools must implement this interface to be used by the Agent.
    """

    # Class-level cache manager (shared across all instances)
    _cache_manager = None

    def __init__(self, repo_path: str, enable_cache: Optional[bool] = None):
        """
        Initialize the tool.

        Args:
            repo_path: Path to the code repository
            enable_cache: Enable caching for this tool (None = use global setting)
        """
        from pathlib import Path
        self.repo_path = Path(repo_path)
        self._validate_repo()
        self._enable_cache = enable_cache

    def _validate_repo(self) -> None:
        """Validate that the repository path exists"""
        if not self.repo_path.exists():
            raise ToolError(
                f"Repository path does not exist: {self.repo_path}",
                tool_name=self.name,
            )

    @classmethod
    def set_cache_manager(cls, cache_manager):
        """Set the global cache manager for all tools."""
        cls._cache_manager = cache_manager

    def _get_cache_manager(self):
        """Get the cache manager instance."""
        return self._cache_manager

    def _is_cache_enabled(self) -> bool:
        """Check if caching is enabled for this tool."""
        if self._enable_cache is not None:
            return self._enable_cache
        # Check global setting
        if self._cache_manager:
            return True
        return False

    def _make_cache_key(self, input_data: Dict[str, Any]) -> str:
        """Generate a cache key for the given input."""
        import hashlib
        import json

        key_data = {
            "tool": self.name,
            "input": input_data,
        }
        key_hash = hashlib.md5(
            json.dumps(key_data, sort_keys=True, default=str).encode()
        ).hexdigest()
        return f"{self.name}:{key_hash}"

    def _cache_get(self, input_data: Dict[str, Any]) -> Optional[str]:
        """Get cached result if available."""
        if not self._is_cache_enabled():
            return None

        cache = self._get_cache_manager()
        if cache is None:
            return None

        cache_key = self._make_cache_key(input_data)
        result = cache.get(cache_key, namespace="tool")

        if result is not None:
            logger.debug(f"Tool cache HIT: {self.name}")

        return result

    def _cache_set(self, input_data: Dict[str, Any], result: str, ttl: Optional[int] = None) -> None:
        """Cache the result."""
        if not self._is_cache_enabled():
            return

        cache = self._get_cache_manager()
        if cache is None:
            return

        # Skip large results
        if len(result) > 100_000:
            logger.debug(f"Tool result too large to cache: {self.name} ({len(result)} bytes)")
            return

        cache_key = self._make_cache_key(input_data)
        cache.set(cache_key, result, ttl=ttl, namespace="tool")
        logger.debug(f"Tool cached: {self.name}")

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Tool name (used for tool calls).

        Must be unique across all tools.
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """
        Tool description (helps the LLM understand when to use this tool).

        Should be clear and concise, explaining:
        - What the tool does
        - When to use it
        - What inputs it needs
        """
        pass

    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """
        JSON Schema for tool input parameters.

        Defines the structure of the `arguments` field in tool calls.
        """
        pass

    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> str:
        """
        Execute the tool with given inputs.

        Args:
            input_data: Tool input parameters

        Returns:
            str: Tool execution result (will be sent back to LLM)

        Raises:
            ToolError: If tool execution fails
        """
        pass

    def run(self, input_data: Dict[str, Any], ttl: Optional[int] = None) -> str:
        """
        Run the tool with caching support.

        Args:
            input_data: Tool input parameters
            ttl: Cache TTL in seconds (None = use default)

        Returns:
            str: Tool execution result
        """
        self.validate_input(input_data)

        # Try cache first
        cached_result = self._cache_get(input_data)
        if cached_result is not None:
            return cached_result

        # Execute tool
        result = self.execute(input_data)

        # Cache result
        self._cache_set(input_data, result, ttl=ttl)

        return result

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert tool to LLM tool format.

        Returns:
            Dictionary in the format expected by the LLM API
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """
        Validate tool input parameters.

        Args:
            input_data: Tool input parameters

        Returns:
            bool: True if input is valid

        Raises:
            ToolError: If input is invalid
        """
        # Check required fields
        required = self.input_schema.get("required", [])
        for field in required:
            if field not in input_data:
                raise ToolError(
                    f"Missing required field: {field}",
                    tool_name=self.name,
                    details={"input_data": input_data},
                )

        # Type validation could be added here
        return True

    def format_result(self, content: str, status: ToolStatus = ToolStatus.SUCCESS, **metadata) -> str:
        """
        Format tool execution result.

        Args:
            content: Result content
            status: Execution status
            **metadata: Additional metadata

        Returns:
            str: Formatted result
        """
        result = ToolResult(status=status, content=content, metadata=metadata)
        return result.content  # For LLM, we just return the content
