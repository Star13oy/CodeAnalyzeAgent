"""
OpenAI Adapter

OpenAI API and OpenAI-compatible APIs adapter.
"""

import logging
from typing import List, Dict, Any, Generator
from openai import OpenAI

from .base import (
    LLMProvider,
    Message,
    LLMResponse,
    ToolCall,
    Usage,
)

logger = logging.getLogger(__name__)


class OpenAIAdapter(LLMProvider):
    """
    Adapter for OpenAI API and OpenAI-compatible APIs.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4",
        timeout: int = 60,
        max_retries: int = 3,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
        logger.info(f"Initialized OpenAIAdapter with model={model}, base_url={base_url}")

    def chat(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        # Convert messages to OpenAI format
        api_messages = [msg.to_dict() for msg in messages]

        # Convert tools to OpenAI format
        openai_tools = None
        if tools:
            openai_tools = [_convert_tool_to_openai(t) for t in tools]

        params = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        if openai_tools:
            params["tools"] = openai_tools

        try:
            response = self.client.chat.completions.create(**params)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def stream_chat(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> Generator[LLMResponse, None, None]:
        api_messages = [msg.to_dict() for msg in messages]

        openai_tools = None
        if tools:
            openai_tools = [_convert_tool_to_openai(t) for t in tools]

        params = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": True,
        }

        if openai_tools:
            params["tools"] = openai_tools

        try:
            stream = self.client.chat.completions.create(**params)
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield LLMResponse(content=chunk.choices[0].delta.content, finish_reason="streaming")
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            raise

    def _parse_response(self, response) -> LLMResponse:
        choice = response.choices[0]
        message = choice.message

        # Parse text content
        content = message.content

        # Parse tool calls
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=_parse_function_arguments(tc.function.arguments),
                    )
                )

        # Parse usage
        usage = Usage(
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )

        # Map finish reason
        finish_reason = choice.finish_reason or "stop"
        if finish_reason == "tool_calls":
            finish_reason = "tool_calls"

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model=response.model,
            usage=usage,
        )


def _convert_tool_to_openai(tool: Dict[str, Any]) -> Dict[str, Any]:
    """Convert tool definition to OpenAI format"""
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool.get("input_schema", {}),
        },
    }


def _parse_function_arguments(args_str: str) -> Dict[str, Any]:
    """Parse function arguments from JSON string"""
    import json
    try:
        return json.loads(args_str)
    except json.JSONDecodeError:
        return {}
