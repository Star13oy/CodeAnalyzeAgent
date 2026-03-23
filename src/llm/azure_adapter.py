"""
Azure OpenAI Adapter

Microsoft Azure OpenAI Service adapter.
"""

import logging
from typing import List, Dict, Any, Generator
from openai import AzureOpenAI

from .base import (
    LLMProvider,
    Message,
    LLMResponse,
    ToolCall,
    Usage,
)

logger = logging.getLogger(__name__)


class AzureOpenAIAdapter(LLMProvider):
    """
    Adapter for Azure OpenAI Service.
    """

    def __init__(
        self,
        api_key: str,
        endpoint: str,
        deployment: str,
        api_version: str = "2024-02-15-preview",
        timeout: int = 60,
        max_retries: int = 3,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ):
        self.deployment = deployment
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.client = AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
            timeout=timeout,
            max_retries=max_retries,
        )
        logger.info(f"Initialized AzureOpenAIAdapter with deployment={deployment}")

    def chat(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> LLMResponse:
        api_messages = [msg.to_dict() for msg in messages]

        openai_tools = None
        if tools:
            openai_tools = [_convert_tool_to_openai(t) for t in tools]

        params = {
            "model": self.deployment,  # Azure uses deployment as model
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
            logger.error(f"Azure OpenAI API error: {e}")
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
            "model": self.deployment,
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
            logger.error(f"Azure OpenAI streaming error: {e}")
            raise

    def _parse_response(self, response) -> LLMResponse:
        from .openai_adapter import _parse_function_arguments

        choice = response.choices[0]
        message = choice.message

        content = message.content

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

        usage = Usage(
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )

        finish_reason = choice.finish_reason or "stop"

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            model=self.deployment,
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
