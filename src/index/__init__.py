"""
Code Indexing Module

Provides intelligent indexing for fast code exploration.

Components:
- SymbolIndex: Fast symbol lookup using pre-built index
- DependencyGraph: Code dependency relationship tracking
- IndexManager: Manages index lifecycle and updates
"""

from .symbol_index import SymbolIndex, Symbol
from .dependency_graph import DependencyGraph
from .manager import IndexManager

__all__ = [
    "SymbolIndex",
    "Symbol",
    "DependencyGraph",
    "IndexManager",
]
