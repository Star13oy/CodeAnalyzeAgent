"""
LLM Abstraction Layer

Provides a unified interface for different LLM providers.
"""

from .base import LLMProvider, Message, LLMResponse, ToolCall
from .company_adapter import CompanyLLMAdapter
from .factory import create_llm_provider, create_from_env, create_from_config

__all__ = [
    "LLMProvider",
    "Message",
    "LLMResponse",
    "ToolCall",
    "CompanyLLMAdapter",
    "create_llm_provider",
    "create_from_env",
    "create_from_config",
]
