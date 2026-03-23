"""
Anthropic Claude Adapter

Official Anthropic Claude API adapter.
"""

import logging
from typing import List, Dict, Any, Generator
import anthropic

from .base import (
    LLMProvider,
    Message,
    LLMResponse,
    ToolCall,
    Usage,
)

logger = logging.getLogger(__name__)


class AnthropicAdapter(LLMProvider):
    """
    Adapter for Anthropic's Claude API.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.anthropic.com",
        model: str = "claude-sonnet-4-6",
        timeout: int = 60,
        max_retries: int = 3,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
        )
        logger.info(f"Initialized AnthropicAdapter with model={model}")

    def chat(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        api_messages = [msg.to_dict() for msg in messages]

        params = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }

        if tools:
            params["tools"] = tools

        if "temperature" in kwargs:
            params["temperature"] = kwargs["temperature"]
        else:
            params["temperature"] = self.temperature

        try:
            response = self.client.messages.create(**params)
            return self._parse_response(response)
        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    def stream_chat(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> Generator[LLMResponse, None, None]:
        api_messages = [msg.to_dict() for msg in messages]

        params = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
        }

        if tools:
            params["tools"] = tools

        try:
            with self.client.messages.stream(**params) as stream:
                for text in stream.text_stream:
                    yield LLMResponse(content=text, finish_reason="streaming")
        except anthropic.APIError as e:
            logger.error(f"Anthropic streaming error: {e}")
            raise

    def _parse_response(self, response) -> LLMResponse:
        tool_calls = []
        text_parts = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=dict(block.input),
                    )
                )

        usage = Usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        finish_reason = response.stop_reason
        if finish_reason == "end_turn":
            finish_reason = "stop"

        return LLMResponse(
            content="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model=response.model,
            usage=usage,
        )
