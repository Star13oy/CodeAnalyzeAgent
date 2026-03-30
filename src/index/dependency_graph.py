"""
Dependency Graph

Tracks relationships between code elements for intelligent exploration.
"""

import logging
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


@dataclass
class Node:
    """A node in the dependency graph."""
    id: str  # Unique identifier (e.g., "file:src/main.py" or "symbol:MyClass")
    name: str
    kind: str  # "file", "class", "function", "module"
    language: str
    file_path: Optional[str] = None
    line: Optional[int] = None

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        return self.id == other.id


@dataclass
class Edge:
    """An edge in the dependency graph."""
    source: str  # Node ID
    target: str  # Node ID
    kind: str  # "imports", "calls", "extends", "implements", "uses"
    weight: int = 1  # Strength of relationship

    def __hash__(self):
        return hash((self.source, self.target, self.kind))

    def __eq__(self, other):
        if not isinstance(other, Edge):
            return False
        return (self.source == other.source and
                self.target == other.target and
                self.kind == other.kind)


class DependencyGraph:
    """
    Dependency graph for code analysis.

    Features:
    - Track import/call relationships
    - Find callers/callees
    - Detect circular dependencies
    - Calculate dependency depth
    """

    def __init__(self):
        """Initialize the dependency graph."""
        self._nodes: Dict[str, Node] = {}
        self._edges: Dict[str, List[Edge]] = defaultdict(list)
        self._reverse_edges: Dict[str, List[Edge]] = defaultdict(list)

        logger.info("Initialized DependencyGraph")

    def add_node(self, node: Node):
        """Add a node to the graph."""
        self._nodes[node.id] = node

    def add_edge(self, edge: Edge):
        """Add an edge to the graph."""
        self._edges[edge.source].append(edge)
        self._reverse_edges[edge.target].append(edge)

    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        return self._nodes.get(node_id)

    def get_dependencies(self, node_id: str, kind: Optional[str] = None) -> List[Node]:
        """
        Get nodes that this node depends on.

        Args:
            node_id: Source node ID
            kind: Optional edge kind filter

        Returns:
            List of target nodes
        """
        edges = self._edges.get(node_id, [])
        if kind:
            edges = [e for e in edges if e.kind == kind]

        return [self._nodes[e.target] for e in edges if e.target in self._nodes]

    def get_dependents(self, node_id: str, kind: Optional[str] = None) -> List[Node]:
        """
        Get nodes that depend on this node.

        Args:
            node_id: Target node ID
            kind: Optional edge kind filter

        Returns:
            List of source nodes
        """
        edges = self._reverse_edges.get(node_id, [])
        if kind:
            edges = [e for e in edges if e.kind == kind]

        return [self._nodes[e.source] for e in edges if e.source in self._nodes]

    def find_path(self, source: str, target: str) -> Optional[List[str]]:
        """
        Find a path from source to target using BFS.

        Args:
            source: Source node ID
            target: Target node ID

        Returns:
            List of node IDs forming a path, or None if no path exists
        """
        if source not in self._nodes or target not in self._nodes:
            return None

        queue = deque([(source, [source])])
        visited = {source}

        while queue:
            current, path = queue.popleft()

            if current == target:
                return path

            for edge in self._edges.get(current, []):
                if edge.target not in visited:
                    visited.add(edge.target)
                    queue.append((edge.target, path + [edge.target]))

        return None

    def find_shortest_path(self, source: str, target: str) -> Optional[List[str]]:
        """Alias for find_path (BFS guarantees shortest path)."""
        return self.find_path(source, target)

    def detect_cycles(self) -> List[List[str]]:
        """
        Detect circular dependencies using DFS.

        Returns:
            List of cycles (each cycle is a list of node IDs)
        """
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for edge in self._edges.get(node, []):
                if edge.target in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(edge.target)
                    cycles.append(path[cycle_start:] + [edge.target])
                elif edge.target not in visited:
                    dfs(edge.target, path.copy())

            path.pop()
            rec_stack.remove(node)

        for node_id in self._nodes:
            if node_id not in visited:
                dfs(node_id, [])

        return cycles

    def calculate_depth(self, node_id: str) -> int:
        """
        Calculate the maximum dependency depth for a node.

        Args:
            node_id: Node ID to analyze

        Returns:
            Maximum depth (0 = no dependencies)
        """
        visited = set()

        def dfs(n: str) -> int:
            if n in visited:
                return 0
            visited.add(n)

            max_depth = 0
            for edge in self._edges.get(n, []):
                if edge.target in self._nodes:
                    depth = dfs(edge.target)
                    max_depth = max(max_depth, depth + 1)

            return max_depth

        return dfs(node_id)

    def get_statistics(self) -> Dict:
        """Get graph statistics."""
        edge_counts = defaultdict(int)
        for edges in self._edges.values():
            for edge in edges:
                edge_counts[edge.kind] += 1

        node_kinds = defaultdict(int)
        for node in self._nodes.values():
            node_kinds[node.kind] += 1

        return {
            "total_nodes": len(self._nodes),
            "total_edges": sum(len(e) for e in self._edges.values()),
            "by_edge_kind": dict(edge_counts),
            "by_node_kind": dict(node_kinds),
        }

    def clear(self):
        """Clear all nodes and edges."""
        self._nodes.clear()
        self._edges.clear()
        self._reverse_edges.clear()

    def build_from_symbols(self, symbols: List):
        """
        Build the graph from a list of symbols.

        Args:
            symbols: List of Symbol objects
        """
        from .symbol_index import Symbol

        # Create nodes
        for symbol in symbols:
            node_id = f"symbol:{symbol.file_path}:{symbol.line}:{symbol.name}"
            node = Node(
                id=node_id,
                name=symbol.name,
                kind=symbol.kind,
                language=symbol.language,
                file_path=symbol.file_path,
                line=symbol.line,
            )
            self.add_node(node)

        # Create file nodes
        file_nodes = set()
        for symbol in symbols:
            file_id = f"file:{symbol.file_path}"
            if file_id not in file_nodes:
                node = Node(
                    id=file_id,
                    name=symbol.file_path,
                    kind="file",
                    language=symbol.language,
                    file_path=symbol.file_path,
                )
                self.add_node(node)
                file_nodes.add(file_id)

            # Link symbol to file
            self.add_edge(Edge(
                source=f"symbol:{symbol.file_path}:{symbol.line}:{symbol.name}",
                target=file_id,
                kind="defined_in",
            ))

        logger.info(f"Built dependency graph: {len(self._nodes)} nodes")

    def to_dot(self) -> str:
        """
        Export graph to DOT format for visualization.

        Returns:
            DOT format string
        """
        lines = ["digraph dependencies {"]
        lines.append("  rankdir=LR;")

        # Add nodes
        for node in self._nodes.values():
            label = f"{node.name} ({node.kind})" if node.kind != "file" else node.name
            lines.append(f'  "{node.id}" [label="{label}"];')

        # Add edges
        for source, edges in self._edges.items():
            for edge in edges:
                lines.append(f'  "{source}" -> "{edge.target}" [label="{edge.kind}"];')

        lines.append("}")
        return "\n".join(lines)
