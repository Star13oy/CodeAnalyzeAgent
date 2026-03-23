"""
LLM Provider Factory - Multi-Vendor Support

Creates LLM provider instances based on configuration.
Supports: Anthropic, OpenAI, Azure, Company, Custom
"""

import logging
from typing import Dict, Any, Optional

from .base import LLMProvider
from .company_adapter import CompanyLLMAdapter
from .anthropic_adapter import AnthropicAdapter
from .openai_adapter import OpenAIAdapter
from .azure_adapter import AzureOpenAIAdapter
from .custom_adapter import CustomLLMAdapter

from ..config import LLMProvider as LLMProviderType

logger = logging.getLogger(__name__)


# Provider registry for easy extension
PROVIDER_REGISTRY: Dict[LLMProviderType, type] = {
    LLMProviderType.ANTHROPIC: AnthropicAdapter,
    LLMProviderType.OPENAI: OpenAIAdapter,
    LLMProviderType.AZURE: AzureOpenAIAdapter,
    LLMProviderType.COMPANY: CompanyLLMAdapter,
    LLMProviderType.CUSTOM: CustomLLMAdapter,
}


def create_llm_provider(
    provider: LLMProviderType,
    config: Dict[str, Any]
) -> LLMProvider:
    """
    Create an LLM provider based on type and configuration.

    Args:
        provider: Provider type (anthropic, openai, azure, company, custom)
        config: Provider-specific configuration

    Returns:
        LLMProvider: Configured provider instance

    Raises:
        ValueError: If provider type is unknown or required config is missing
    """
    provider_class = PROVIDER_REGISTRY.get(provider)

    if provider_class is None:
        raise ValueError(
            f"Unknown provider type: {provider}. "
            f"Supported providers: {list(PROVIDER_REGISTRY.keys())}"
        )

    try:
        return provider_class(**config)
    except TypeError as e:
        raise ValueError(
            f"Invalid configuration for {provider}: {e}"
        )


def create_from_config(config: Dict[str, Any]) -> LLMProvider:
    """
    Create LLM provider from configuration dictionary.

    Args:
        config: Configuration with keys:
            - provider: Provider type (default: "company")
            - [provider-specific keys]

    Returns:
        LLMProvider: Configured provider instance
    """
    provider_str = config.get("provider", "company")

    try:
        provider_type = LLMProviderType(provider_str)
    except ValueError:
        raise ValueError(
            f"Unknown provider: {provider_str}. "
            f"Supported: {[p.value for p in LLMProviderType]}"
        )

    # Extract provider-specific config based on provider type
    provider_config = _extract_provider_config(provider_type, config)

    return create_llm_provider(provider_type, provider_config)


def _extract_provider_config(provider_type: LLMProviderType, config: Dict[str, Any]) -> Dict[str, Any]:
    """Extract provider-specific configuration from the config dict."""
    # Map of config keys to provider-specific keys
    key_mappings = {
        LLMProviderType.COMPANY: {
            "base_url": "company_llm_base_url",
            "api_key": "company_llm_api_key",
            "model": "company_llm_model",
        },
        LLMProviderType.ANTHROPIC: {
            "base_url": "anthropic_base_url",
            "api_key": "anthropic_api_key",
            "model": "anthropic_model",
        },
        LLMProviderType.OPENAI: {
            "base_url": "openai_base_url",
            "api_key": "openai_api_key",
            "model": "openai_model",
        },
        LLMProviderType.AZURE: {
            "endpoint": "azure_openai_endpoint",
            "api_key": "azure_openai_api_key",
            "api_version": "azure_openai_api_version",
            "deployment": "azure_openai_deployment",
            "model": "model",  # fallback
        },
        LLMProviderType.CUSTOM: {
            "base_url": "custom_llm_base_url",
            "api_key": "custom_llm_api_key",
            "model": "custom_llm_model",
            "headers": "custom_llm_headers",
        },
    }

    mapping = key_mappings.get(provider_type, {})
    provider_config = {}

    # Map generic keys to provider-specific keys
    for generic_key, provider_key in mapping.items():
        # First try provider-specific key
        if provider_key in config:
            provider_config[generic_key] = config[provider_key]
        # Then try generic key
        elif generic_key in config:
            provider_config[generic_key] = config[generic_key]

    # Add any extra config for custom provider
    if provider_type == LLMProviderType.CUSTOM:
        if "headers" in config:
            import json
            headers_str = config["headers"]
            if isinstance(headers_str, str):
                try:
                    provider_config["headers"] = json.loads(headers_str)
                except json.JSONDecodeError:
                    provider_config["headers"] = {}

    return provider_config


def create_from_settings(settings) -> LLMProvider:
    """
    Create LLM provider from application settings.

    Args:
        settings: Application settings object with llm_config

    Returns:
        LLMProvider: Configured provider instance
    """
    provider_type = settings.llm.provider
    active_config = settings.llm.active_config.copy()

    # Add common settings that are accepted by all adapters
    active_config.setdefault("timeout", getattr(settings, "api_timeout", 60))
    active_config.setdefault("max_retries", 3)

    # Note: max_tokens and temperature are passed to chat(), not __init__()

    # Validate API key
    api_key = active_config.get("api_key")
    if not api_key and provider_type != LLMProviderType.CUSTOM:
        logger.warning(f"API key not set for provider: {provider_type}")

    return create_llm_provider(provider_type, active_config)


def get_provider_info() -> Dict[str, Dict[str, str]]:
    """
    Get information about all supported providers.

    Returns:
        Dictionary mapping provider names to their info
    """
    return {
        "anthropic": {
            "name": "Anthropic Claude",
            "description": "Official Anthropic Claude API",
            "models": ["claude-sonnet-4-6", "claude-opus-4-6", "claude-haiku-4-5"],
            "required_config": ["api_key"],
            "optional_config": ["base_url", "model", "timeout"],
        },
        "openai": {
            "name": "OpenAI / OpenAI Compatible",
            "description": "OpenAI API or compatible services",
            "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
            "required_config": ["api_key"],
            "optional_config": ["base_url", "model", "timeout"],
        },
        "azure": {
            "name": "Azure OpenAI",
            "description": "Microsoft Azure OpenAI Service",
            "models": ["gpt-4", "gpt-35-turbo"],
            "required_config": ["api_key", "endpoint", "deployment"],
            "optional_config": ["api_version"],
        },
        "company": {
            "name": "Company LLM Gateway",
            "description": "Company API gateway (Anthropic compatible)",
            "models": ["claude-sonnet-4-6", "claude-opus-4-6"],
            "required_config": ["api_key"],
            "optional_config": ["base_url", "model", "timeout"],
        },
        "custom": {
            "name": "Custom LLM",
            "description": "Custom HTTP endpoint with configurable headers",
            "models": ["any"],
            "required_config": ["base_url"],
            "optional_config": ["api_key", "model", "headers", "timeout"],
        },
    }


# Backward compatibility: create from environment variables
def create_from_env() -> LLMProvider:
    """
    Create LLM provider from environment variables (legacy).

    Environment variables:
        LLM_PROVIDER: Provider type (default: "company")
        LLM_API_KEY: API key
        LLM_BASE_URL: Base URL
        LLM_MODEL: Model name
        LLM_TIMEOUT: Request timeout

    Returns:
        LLMProvider: Configured provider instance
    """
    import os

    provider_str = os.getenv("LLM_PROVIDER", "company")

    config = {
        "provider": provider_str,
        "api_key": os.getenv("LLM_API_KEY", ""),
        "base_url": os.getenv("LLM_BASE_URL", "https://your-company-gateway.com"),
        "model": os.getenv("LLM_MODEL", "claude-sonnet-4-6"),
        "timeout": int(os.getenv("LLM_TIMEOUT", "60")),
    }

    return create_from_config(config)
