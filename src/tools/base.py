"""
Tool Base Interface

Defines the abstract interface for all tools.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from dataclasses import dataclass
from enum import Enum


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

    def __init__(self, repo_path: str):
        """
        Initialize the tool.

        Args:
            repo_path: Path to the code repository
        """
        from pathlib import Path
        self.repo_path = Path(repo_path)
        self._validate_repo()

    def _validate_repo(self) -> None:
        """Validate that the repository path exists"""
        if not self.repo_path.exists():
            raise ToolError(
                f"Repository path does not exist: {self.repo_path}",
                tool_name=self.name,
            )

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
