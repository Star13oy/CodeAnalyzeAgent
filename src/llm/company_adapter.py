"""
Company LLM Adapter

Adapts the company's API gateway (which is Anthropic-compatible)
to the LLMProvider interface.
"""

import logging
import os
from typing import List, Dict, Any, Generator
import anthropic
import httpx

from .base import (
    LLMProvider,
    Message,
    LLMResponse,
    ToolCall,
    Usage,
)

logger = logging.getLogger(__name__)


class CompanyLLMAdapter(LLMProvider):
    """
    Adapter for the company's API gateway.

    The company gateway is fully compatible with the Anthropic API format,
    so we can use the official Anthropic SDK with just a custom base_url.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://your-company-gateway.com",
        model: str = "claude-sonnet-4-6",
        timeout: int = 60,
        max_retries: int = 3,
    ):
        """
        Initialize the adapter.

        Args:
            api_key: API key for authentication
            base_url: Base URL of the API gateway
            model: Model name to use (will be mapped by gateway)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries
        """
        self.model = model

        # Clear all proxy environment variables
        for var in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']:
            os.environ.pop(var, None)

        # Create a custom httpx client without proxy support
        # This prevents httpx from using system proxy settings
        custom_http_client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            trust_env=False,  # Important: don't use environment variables for proxy
        )

        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            http_client=custom_http_client,
        )
        logger.info(f"Initialized CompanyLLMAdapter with model={model}, base_url={base_url}")

    def chat(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        """
        Send a chat request.

        Args:
            messages: List of chat messages
            tools: List of tool definitions
            **kwargs: Additional parameters (max_tokens, temperature, etc.)

        Returns:
            LLMResponse: The response from the LLM
        """
        # Convert messages to API format
        api_messages = [msg.to_dict() for msg in messages]

        # Prepare parameters
        params = {
            "model": self.model,
            "messages": api_messages,
            "tools": tools,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        # Add optional parameters
        if "temperature" in kwargs:
            params["temperature"] = kwargs["temperature"]
        if "top_p" in kwargs:
            params["top_p"] = kwargs["top_p"]
        if "stop_sequences" in kwargs:
            params["stop_sequences"] = kwargs["stop_sequences"]

        logger.debug(f"Sending chat request with {len(messages)} messages and {len(tools)} tools")

        try:
            response = self.client.messages.create(**params)
            return self._parse_response(response)
        except anthropic.APIError as e:
            logger.error(f"API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    def stream_chat(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> Generator[LLMResponse, None, None]:
        """
        Send a streaming chat request.

        Args:
            messages: List of chat messages
            tools: List of tool definitions
            **kwargs: Additional parameters

        Yields:
            LLMResponse: Streaming chunks of the response
        """
        api_messages = [msg.to_dict() for msg in messages]

        params = {
            "model": self.model,
            "messages": api_messages,
            "tools": tools,
            "max_tokens": kwargs.get("max_tokens", 4096),
        }

        if "temperature" in kwargs:
            params["temperature"] = kwargs["temperature"]

        try:
            with self.client.messages.stream(**params) as stream:
                for text in stream.text_stream:
                    yield LLMResponse(content=text, finish_reason="streaming")
        except anthropic.APIError as e:
            logger.error(f"Streaming API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected streaming error: {e}")
            raise

    def _parse_response(self, response) -> LLMResponse:
        """
        Parse Anthropic API response into LLMResponse.

        Args:
            response: Raw response from Anthropic API

        Returns:
            LLMResponse: Parsed response
        """
        content_blocks = response.content
        tool_calls = []
        text_parts = []

        for block in content_blocks:
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

        # Build usage info
        usage = Usage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

        # Determine finish reason
        # Anthropic uses "end_turn" for stop, "tool_use" for tool calls
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


class ClaudeDirectAdapter(LLMProvider):
    """
    Direct Anthropic API adapter (for testing/fallback).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        timeout: int = 60,
    ):
        self.model = model
        self.client = anthropic.Anthropic(
            api_key=api_key,
            timeout=timeout,
        )

    def chat(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        api_messages = [msg.to_dict() for msg in messages]

        response = self.client.messages.create(
            model=self.model,
            messages=api_messages,
            tools=tools,
            max_tokens=kwargs.get("max_tokens", 4096),
        )

        return CompanyLLMAdapter._parse_response(None, response)

    def stream_chat(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> Generator[LLMResponse, None, None]:
        raise NotImplementedError("Streaming not implemented for direct adapter")
