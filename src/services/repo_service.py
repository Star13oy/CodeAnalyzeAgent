"""
Repository Service

Manages code repository indexing and metadata.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from ..config import settings

logger = logging.getLogger(__name__)


class RepositoryService:
    """
    Service for managing code repositories.
    """

    def __init__(self):
        """Initialize the repository service"""
        self.repositories: Dict[str, Dict] = {}
        self.repo_base_path = Path(settings.repo_base_path)
        self.repo_base_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initialized RepositoryService with base path: {self.repo_base_path}")

    def create(self, repo_id: str, name: str, path: str) -> Dict:
        """
        Create and index a new repository.

        Args:
            repo_id: Unique repository identifier
            name: Repository display name
            path: Path to the repository

        Returns:
            Repository metadata
        """
        if repo_id in self.repositories:
            raise ValueError(f"Repository {repo_id} already exists")

        # Validate path
        repo_path = Path(path)
        if not repo_path.exists():
            raise ValueError(f"Path does not exist: {path}")

        # Create repository entry
        now = datetime.now()
        repo_data = {
            "id": repo_id,
            "name": name,
            "path": str(repo_path),
            "language": self._detect_language(repo_path),
            "created_at": now,
            "updated_at": now,
            "indexed": False,
            "file_count": 0,
            "symbol_count": 0,
        }

        # Index the repository
        self._index_repository(repo_data)

        self.repositories[repo_id] = repo_data
        logger.info(f"Created repository {repo_id} at {path}")

        return self._to_info(repo_data)

    def get(self, repo_id: str) -> Optional[Dict]:
        """
        Get repository information.

        Args:
            repo_id: Repository ID

        Returns:
            Repository info or None
        """
        repo_data = self.repositories.get(repo_id)
        return self._to_info(repo_data) if repo_data else None

    def list_all(self) -> list:
        """List all repositories"""
        return [self._to_info(r) for r in self.repositories.values()]

    def update(self, repo_id: str, reindex: bool = False) -> Optional[Dict]:
        """
        Update a repository.

        Args:
            repo_id: Repository ID
            reindex: Whether to rebuild the index

        Returns:
            Updated repository info or None
        """
        repo_data = self.repositories.get(repo_id)
        if not repo_data:
            return None

        if reindex:
            self._index_repository(repo_data)
            repo_data["updated_at"] = datetime.now()

        return self._to_info(repo_data)

    def delete(self, repo_id: str) -> bool:
        """
        Delete a repository.

        Args:
            repo_id: Repository ID

        Returns:
            True if deleted, False if not found
        """
        if repo_id in self.repositories:
            del self.repositories[repo_id]
            logger.info(f"Deleted repository {repo_id}")
            return True
        return False

    def _index_repository(self, repo_data: Dict) -> None:
        """
        Index a repository.

        Args:
            repo_data: Repository data to update
        """
        path = Path(repo_data["path"])

        # Count files
        file_count = sum(1 for _ in path.rglob("*") if _.is_file())
        repo_data["file_count"] = file_count

        # Build ctags index
        self._build_tags_index(path)

        # Count symbols
        symbol_count = self._count_symbols(path)
        repo_data["symbol_count"] = symbol_count

        repo_data["indexed"] = True
        repo_data["updated_at"] = datetime.now()

        logger.info(
            f"Indexed repository {repo_data['id']}: "
            f"{file_count} files, {symbol_count} symbols"
        )

    def _build_tags_index(self, path: Path) -> None:
        """Build ctags index"""
        import subprocess

        tags_file = path / ".tags"

        try:
            subprocess.run(
                ["ctags", "-R", "--fields=+ne", "-o", str(tags_file), str(path)],
                capture_output=True,
                timeout=300,
            )
            logger.debug(f"Built ctags index for {path}")
        except subprocess.TimeoutExpired:
            logger.warning(f"ctags indexing timed out for {path}")
        except FileNotFoundError:
            logger.warning("ctags not found, skipping symbol indexing")

    def _count_symbols(self, path: Path) -> int:
        """Count symbols in tags file"""
        tags_file = path / ".tags"

        if not tags_file.exists():
            return 0

        try:
            with open(tags_file, "r") as f:
                # Each line is a symbol
                return sum(1 for line in f if line and not line.startswith("!_"))
        except Exception:
            return 0

    def _detect_language(self, path: Path) -> Optional[str]:
        """Detect primary language of the repository"""
        extensions = {
            ".py": "Python",
            ".java": "Java",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".cpp": "C++",
            ".c": "C",
            ".h": "C/C++",
            ".go": "Go",
            ".rs": "Rust",
            ".rb": "Ruby",
            ".php": "PHP",
            ".cs": "C#",
            ".kt": "Kotlin",
            ".scala": "Scala",
        }

        counts = {}
        for file in path.rglob("*"):
            if file.is_file():
                ext = file.suffix
                if ext in extensions:
                    lang = extensions[ext]
                    counts[lang] = counts.get(lang, 0) + 1

        if counts:
            return max(counts, key=counts.get)
        return None

    def _to_info(self, repo_data: Dict) -> Dict:
        """Convert repo data to info dict"""
        return {
            "id": repo_data["id"],
            "name": repo_data["name"],
            "path": repo_data["path"],
            "language": repo_data.get("language"),
            "created_at": repo_data["created_at"],
            "updated_at": repo_data["updated_at"],
            "indexed": repo_data["indexed"],
            "file_count": repo_data["file_count"],
            "symbol_count": repo_data["symbol_count"],
        }
