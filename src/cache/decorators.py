"""
Cache Decorators

Convenient decorators for caching tool results and LLM responses.
"""

import functools
import logging
from typing import Optional, Callable, Any

from .manager import CacheManager, get_cache_manager

logger = logging.getLogger(__name__)


def cached_tool(
    ttl: Optional[int] = None,
    key_func: Optional[Callable] = None,
    ignore_args: Optional[list] = None,
):
    """
    Decorator for caching tool execution results.

    Args:
        ttl: Time-to-live in seconds (None = use default)
        key_func: Custom function to generate cache key
        ignore_args: Argument names to ignore when generating key

    Example:
        @cached_tool(ttl=3600)  # Cache for 1 hour
        def file_read(path: str) -> str:
            ...

        @cached_tool(ttl=600, ignore_args=['session_id'])
        def search(query: str, session_id: str) -> List[str]:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache_manager()
            namespace = CacheManager.NS_TOOL_RESULTS

            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Build key from function name and filtered arguments
                key_parts = [func.__name__]

                # Filter out ignored arguments
                filtered_kwargs = {
                    k: v for k, v in kwargs.items()
                    if k not in (ignore_args or [])
                }

                # Add positional args (convert to string)
                for arg in args[:3]:  # Limit to first 3 args for key size
                    key_parts.append(str(arg)[:100])

                # Add filtered kwargs
                if filtered_kwargs:
                    key_parts.append(str(sorted(filtered_kwargs.items())))

                cache_key = ":".join(key_parts)

            # Try cache
            cached_result = cache.get(cache_key, namespace=namespace)
            if cached_result is not None:
                logger.debug(f"Tool cache HIT: {func.__name__}")
                return cached_result

            logger.debug(f"Tool cache MISS: {func.__name__}")

            # Execute tool
            result = func(*args, **kwargs)

            # Cache result (if not too large)
            result_size = len(str(result))
            if result_size < 100_000:  # Skip caching very large results
                cache.set(cache_key, result, ttl=ttl, namespace=namespace)
            else:
                logger.debug(f"Skipping cache for large result ({result_size} bytes)")

            return result

        # Add cache control methods
        wrapper.cache_key = lambda *a, **kw: (
            key_func(*a, **kw) if key_func
            else f"{func.__name__}:{CacheManager.make_key(*a, **kw)}"
        )
        wrapper.cache_clear = lambda: cache.clear_namespace(namespace)
        wrapper.cache_invalidate = lambda *a, **kw: cache.delete(
            wrapper.cache_key(*a, **kw),
            namespace=namespace
        )

        return wrapper

    return decorator


def cached_llm(
    ttl: Optional[int] = None,
    key_func: Optional[Callable] = None,
):
    """
    Decorator for caching LLM responses.

    LLM responses are cached based on:
    - Model name
    - System prompt
    - User messages
    - Temperature

    Args:
        ttl: Time-to-live in seconds (default: 86400 = 1 day)
        key_func: Custom function to generate cache key

    Example:
        @cached_llm(ttl=86400)  # Cache for 1 day
        def call_llm(messages: List[Message]) -> str:
            ...
    """
    if ttl is None:
        ttl = 86400  # Default: 1 day

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache_manager()
            namespace = CacheManager.NS_LLM_RESPONSES

            # Generate cache key from LLM parameters
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Extract LLM parameters for key generation
                # Try to get messages from args or kwargs
                messages = kwargs.get('messages')
                if messages is None and args:
                    messages = args[0] if args else None

                # Try to get model
                model = kwargs.get('model', getattr(args[1] if len(args) > 1 else None, 'model', 'default'))

                # Create key from model + message content
                if messages:
                    # Hash the messages for compact key
                    import hashlib
                    import json

                    # Normalize messages for consistent hashing
                    normalized = json.dumps([
                        {"role": m.get('role'), "content": m.get('content')[:500]}
                        for m in (messages if isinstance(messages, list) else [messages])
                    ], sort_keys=True)

                    msg_hash = hashlib.md5(normalized.encode()).hexdigest()[:16]
                    cache_key = f"llm:{model}:{msg_hash}"
                else:
                    cache_key = CacheManager.make_key(func.__name__, *args, **kwargs)

            # Try cache
            cached_result = cache.get(cache_key, namespace=namespace)
            if cached_result is not None:
                logger.debug(f"LLM cache HIT: {cache_key[:50]}...")
                return cached_result

            logger.debug(f"LLM cache MISS: {cache_key[:50]}...")

            # Execute LLM call
            result = func(*args, **kwargs)

            # Cache result
            cache.set(cache_key, result, ttl=ttl, namespace=namespace)

            return result

        # Add cache control methods
        wrapper.cache_clear = lambda: cache.clear_namespace(namespace)

        return wrapper

    return decorator


# Import for type reference
from .manager import CacheManager
