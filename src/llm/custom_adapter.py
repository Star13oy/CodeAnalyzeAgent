"""
Custom LLM Adapter

Custom HTTP endpoint adapter with configurable headers and format.
Supports any OpenAI-compatible or Anthropic-compatible API.
"""

import logging
from typing import List, Dict, Any, Generator
import httpx

from .base import (
    LLMProvider,
    Message,
    LLMResponse,
    ToolCall,
    Usage,
)

logger = logging.getLogger(__name__)


class CustomLLMAdapter(LLMProvider):
    """
    Adapter for custom HTTP endpoints.

    Supports both OpenAI-compatible and Anthropic-compatible formats.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        model: str = "custom",
        timeout: int = 60,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        headers: Dict[str, str] = None,
        api_format: str = "openai",  # "openai" or "anthropic"
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.api_format = api_format

        # Build default headers
        default_headers = {
            "Content-Type": "application/json",
        }
        if api_key:
            default_headers["Authorization"] = f"Bearer {api_key}"

        # Merge with custom headers
        if headers:
            default_headers.update(headers)

        self.headers = default_headers
        self.timeout = timeout

        logger.info(f"Initialized CustomLLMAdapter with base_url={base_url}, format={api_format}")

    def chat(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        if self.api_format == "anthropic":
            return self._chat_anthropic(messages, tools, **kwargs)
        else:
            return self._chat_openai(messages, tools, **kwargs)

    def _chat_openai(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        """Chat using OpenAI-compatible format"""
        api_messages = [msg.to_dict() for msg in messages]

        payload = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t.get("input_schema", {}),
                    },
                }
                for t in tools
            ]

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                return self._parse_openai_response(response.json())
        except httpx.HTTPError as e:
            logger.error(f"Custom API error: {e}")
            raise

    def _chat_anthropic(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        """Chat using Anthropic-compatible format"""
        api_messages = [msg.to_dict() for msg in messages]

        payload = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }

        if tools:
            payload["tools"] = tools

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/v1/messages",
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                return self._parse_anthropic_response(response.json())
        except httpx.HTTPError as e:
            logger.error(f"Custom API error: {e}")
            raise

    def stream_chat(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> Generator[LLMResponse, None, None]:
        # Basic streaming implementation
        if self.api_format == "anthropic":
            yield from self._stream_anthropic(messages, tools, **kwargs)
        else:
            yield from self._stream_openai(messages, tools, **kwargs)

    def _stream_openai(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> Generator[LLMResponse, None, None]:
        """Stream using OpenAI-compatible format"""
        api_messages = [msg.to_dict() for msg in messages]

        payload = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
            "stream": True,
        }

        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t.get("input_schema", {}),
                    },
                }
                for t in tools
            ]

        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if line.strip().startswith("data: "):
                            data = line.strip()[6:]
                            if data == "[DONE]":
                                break
                            try:
                                import json
                                chunk = json.loads(data)
                                if chunk.get("choices"):
                                    delta = chunk["choices"][0].get("delta", {})
                                    content = delta.get("content")
                                    if content:
                                        yield LLMResponse(content=content, finish_reason="streaming")
                            except json.JSONDecodeError:
                                continue
        except httpx.HTTPError as e:
            logger.error(f"Custom streaming error: {e}")
            raise

    def _stream_anthropic(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> Generator[LLMResponse, None, None]:
        """Stream using Anthropic-compatible format (basic implementation)"""
        # For simplicity, just do non-streaming and yield the result
        result = self._chat_anthropic(messages, tools, **kwargs)
        yield result

    def _parse_openai_response(self, data: Dict) -> LLMResponse:
        """Parse OpenAI-format response"""
        choice = data["choices"][0]
        message = choice.get("message", {})

        content = message.get("content")

        tool_calls = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                func = tc.get("function", {})
                args = func.get("arguments", "{}")
                try:
                    import json
                    args_dict = json.loads(args)
                except json.JSONDecodeError:
                    args_dict = {}

                tool_calls.append(
                    ToolCall(
                        id=tc.get("id", ""),
                        name=func.get("name", ""),
                        arguments=args_dict,
                    )
                )

        usage_data = data.get("usage", {})
        usage = Usage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
        )

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", "stop"),
            model=data.get("model", self.model),
            usage=usage,
        )

    def _parse_anthropic_response(self, data: Dict) -> LLMResponse:
        """Parse Anthropic-format response"""
        content_blocks = data.get("content", [])
        tool_calls = []
        text_parts = []

        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input", {}),
                    )
                )

        usage_data = data.get("usage", {})
        usage = Usage(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
        )

        finish_reason = data.get("stop_reason", "stop")
        if finish_reason == "end_turn":
            finish_reason = "stop"

        return LLMResponse(
            content="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model=data.get("model", self.model),
            usage=usage,
        )
