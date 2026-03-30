"""
Agent Module

Implements the Agentic Code Assistant engine.
"""

from .core import CodeAgent
from .session import Session, SessionManager
from .context_manager import ContextManager, create_context_manager

__all__ = [
    "CodeAgent",
    "Session",
    "SessionManager",
    "ContextManager",
    "create_context_manager",
]
