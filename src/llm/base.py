"""
LLM Provider Base Interface

Defines the abstract interface for all LLM providers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass, field
from enum import Enum


class MessageRole(str, Enum):
    """Message role types"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """Chat message"""
    role: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        """Convert to API format"""
        return {"role": self.role, "content": self.content}


@dataclass
class ToolCall:
    """Tool call from LLM"""
    id: str
    name: str
    arguments: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API format"""
        return {
            "id": self.id,
            "name": self.name,
            "input": self.arguments
        }


@dataclass
class Usage:
    """Token usage information"""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens used"""
        return self.input_tokens + self.output_tokens


@dataclass
class LLMResponse:
    """Response from LLM"""
    content: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    model: str = ""
    usage: Usage = field(default_factory=Usage)

    @property
    def has_content(self) -> bool:
        """Check if response has text content"""
        return self.content is not None and len(self.content) > 0

    @property
    def has_tool_calls(self) -> bool:
        """Check if response has tool calls"""
        return len(self.tool_calls) > 0


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.

    All LLM providers must implement this interface to ensure
    compatibility with the Agent engine.
    """

    @abstractmethod
    def chat(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        """
        Send a chat request and get a response.

        Args:
            messages: List of chat messages
            tools: List of tool definitions available to the LLM
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse: The response from the LLM
        """
        pass

    @abstractmethod
    def stream_chat(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> Generator[LLMResponse, None, None]:
        """
        Send a chat request and stream the response.

        Args:
            messages: List of chat messages
            tools: List of tool definitions available to the LLM
            **kwargs: Additional provider-specific parameters

        Yields:
            LLMResponse: Streaming chunks of the response
        """
        pass

    def validate_tools(self, tools: List[Dict[str, Any]]) -> bool:
        """
        Validate tool definitions.

        Args:
            tools: List of tool definitions

        Returns:
            bool: True if all tools are valid
        """
        required_fields = {"name", "description", "input_schema"}
        for tool in tools:
            if not required_fields.issubset(tool.keys()):
                return False
        return True
