"""
Knowledge Base for Common Issues

Stores and retrieves solutions to common problems.
"""

import json
import logging
import hashlib
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class Solution:
    """A solution to a common problem."""
    problem: str
    solution: str
    tags: List[str]
    severity: str
    language: str
    related_files: List[str] = None
    code_example: Optional[str] = None

    def __post_init__(self):
        if self.related_files is None:
            self.related_files = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class KnowledgeBase:
    """
    Knowledge base for common coding issues and solutions.

    Features:
    - Problem-solution matching
    - Tag-based lookup
    - Severity-based prioritization
    - Language filtering
    """

    # Built-in knowledge base
    DEFAULT_SOLUTIONS = [
        Solution(
            problem="KeyError: 'xxx' not found",
            solution="The dictionary doesn't contain the key you're trying to access. Use dict.get(key, default) to provide a default value, or check if the key exists with 'if key in dict'.",
            tags=["key_error", "dictionary", "python"],
            severity="medium",
            language="python",
            code_example="# Safe access\nvalue = my_dict.get(key, None)\n\n# Check before access\nif key in my_dict:\n    value = my_dict[key]"
        ),
        Solution(
            problem="AttributeError: 'NoneType' object has no attribute 'xxx'",
            solution="The variable is None when you're trying to access its attribute. Add a None check or initialize the variable properly.",
            tags=["attribute_error", "none", "python"],
            severity="high",
            language="python",
            code_example="# Check for None\nif obj is not None:\n    result = obj.method()\n\n# Use or\nresult = (obj or default_obj).method()"
        ),
        Solution(
            problem="FileNotFoundError: [Errno 2] No such file or directory",
            solution="The file doesn't exist at the specified path. Verify the path is correct, the file exists, or use os.path.exists() before accessing.",
            tags=["file_not_found", "io", "python"],
            severity="medium",
            language="python",
            code_example="# Check before opening\nif os.path.exists(file_path):\n    with open(file_path) as f:\n        content = f.read()"
        ),
        Solution(
            problem="Cannot read property 'xxx' of undefined",
            solution="The object is undefined when you're trying to access its property. Use optional chaining (obj?.prop) or check if object exists.",
            tags=["undefined", "javascript", "typescript"],
            severity="high",
            language="javascript",
            code_example="# Optional chaining\nconst value = obj?.prop\n\n# Check\nif (obj && obj.prop) {\n    const value = obj.prop\n}"
        ),
        Solution(
            problem="Connection refused",
            solution="The target service is not running or not accepting connections. Check if the server is running, the host/port is correct, and firewall rules allow the connection.",
            tags=["network", "connection", "timeout"],
            severity="high",
            language="any",
            code_example="# Test connection\ntry:\n    response = requests.get(url, timeout=5)\nexcept requests.ConnectionError:\n    print(\"Service not available\")"
        ),
        Solution(
            problem="Database connection pool exhausted",
            solution="All connections in the pool are in use. This usually means connections aren't being properly closed. Make sure to use context managers or explicitly close connections.",
            tags=["database", "pool", "connection"],
            severity="critical",
            language="any",
            code_example="# Use context manager\nwith engine.connect() as conn:\n    result = conn.execute(query)"
        ),
        Solution(
            problem="List index out of range",
            solution="You're trying to access a list element at an index that doesn't exist. Lists are 0-indexed, so valid indices are 0 to len(list)-1.",
            tags=["index_error", "list", "python"],
            severity="medium",
            language="python",
            code_example="# Check bounds\nif 0 <= index < len(my_list):\n    value = my_list[index]\n\n# Use try-except\ntry:\n    value = my_list[index]\nexcept IndexError:\n    value = None"
        ),
        Solution(
            problem="ImportError: No module named 'xxx'",
            solution="The Python module is not installed or not in your PYTHONPATH. Install it with pip and make sure your virtual environment is activated.",
            tags=["import_error", "module", "python"],
            severity="medium",
            language="python",
            code_example="# Install missing package\n!pip install package_name\n\n# Or with requirements.txt\n!pip install -r requirements.txt"
        ),
        Solution(
            problem="java.lang.NullPointerException",
            solution="Attempting to use an object reference that is null. Check if the object is properly initialized before accessing its methods or fields.",
            tags=["null_pointer", "java", "exception"],
            severity="high",
            language="java",
            code_example="// Add null check\nif (object != null) {\n    object.method();\n}\n\n// Use Optional\nOptional.ofNullable(object)\n    .ifPresent(obj -> obj.method());"
        ),
    ]

    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the knowledge base.

        Args:
            storage_path: Optional path to persistent storage JSON file
        """
        self.storage_path = storage_path
        self._solutions: Dict[str, Solution] = {}
        self._tag_index: Dict[str, List[str]] = {}

        # Load built-in solutions
        for solution in self.DEFAULT_SOLUTIONS:
            self.add_solution(solution)

        # Load from storage if specified
        if storage_path and Path(storage_path).exists():
            self.load_from_file(storage_path)

        logger.info(f"Initialized KnowledgeBase with {len(self._solutions)} solutions")

    def add_solution(self, solution: Solution) -> str:
        """
        Add a solution to the knowledge base.

        Args:
            solution: Solution to add

        Returns:
            Solution ID
        """
        solution_id = self._generate_id(solution)
        self._solutions[solution_id] = solution

        # Update tag index
        for tag in solution.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = []
            if solution_id not in self._tag_index[tag]:
                self._tag_index[tag].append(solution_id)

        return solution_id

    def find_solutions(
        self,
        problem: str,
        language: Optional[str] = None,
        tags: Optional[List[str]] = None,
        severity: Optional[str] = None,
    ) -> List[Solution]:
        """
        Find solutions for a problem.

        Args:
            problem: Problem description
            language: Optional language filter
            tags: Optional tag filter
            severity: Optional severity filter

        Returns:
            List of matching solutions
        """
        results = []

        # Normalize problem for matching
        problem_lower = problem.lower()
        problem_words = set(problem_lower.split())

        for solution in self._solutions.values():
            # Language filter
            if language and solution.language != language and solution.language != "any":
                continue

            # Severity filter
            if severity and solution.severity != severity:
                continue

            # Tag filter
            if tags and not any(tag in solution.tags for tag in tags):
                continue

            # Problem matching (check if problem words overlap with solution problem)
            solution_lower = solution.problem.lower()
            solution_words = set(solution_lower.split())

            # Check if any significant words match
            intersection = problem_words & solution_words
            if intersection:
                # Calculate similarity
                similarity = len(intersection) / max(len(problem_words), len(solution_words))
                if similarity > 0.2:  # 20% overlap threshold
                    results.append((solution, similarity))

        # Sort by similarity and severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        results.sort(key=lambda x: (x[1], severity_order.get(x[0].severity, 2)))

        return [s[0] for s in results]

    def get_by_tags(self, tags: List[str]) -> List[Solution]:
        """
        Get solutions by tags.

        Args:
            tags: Tags to search for

        Returns:
            List of solutions with matching tags
        """
        solution_ids = set()

        for tag in tags:
            if tag in self._tag_index:
                solution_ids.update(self._tag_index[tag])

        return [self._solutions[sid] for sid in solution_ids]

    def save_to_file(self, path: Optional[str] = None):
        """
        Save knowledge base to file.

        Args:
            path: Path to save to (uses storage_path if None)
        """
        save_path = path or self.storage_path
        if not save_path:
            return

        data = {
            "solutions": [s.to_dict() for s in self._solutions.values()]
        }

        Path(save_path).parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved knowledge base to {save_path}")

    def load_from_file(self, path: str):
        """
        Load knowledge base from file.

        Args:
            path: Path to load from
        """
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for sol_data in data.get("solutions", []):
            solution = Solution(**sol_data)
            self.add_solution(solution)

        logger.info(f"Loaded knowledge base from {path}")

    def get_statistics(self) -> Dict:
        """Get knowledge base statistics."""
        tag_counts = {}
        for tag, ids in self._tag_index.items():
            tag_counts[tag] = len(ids)

        severity_counts = {}
        for solution in self._solutions.values():
            severity_counts[solution.severity] = severity_counts.get(solution.severity, 0) + 1

        language_counts = {}
        for solution in self._solutions.values():
            lang = solution.language
            language_counts[lang] = language_counts.get(lang, 0) + 1

        return {
            "total_solutions": len(self._solutions),
            "total_tags": len(self._tag_index),
            "by_severity": severity_counts,
            "by_language": language_counts,
            "top_tags": sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10],
        }

    def _generate_id(self, solution: Solution) -> str:
        """Generate a unique ID for a solution."""
        content = f"{solution.problem}:{solution.solution}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
