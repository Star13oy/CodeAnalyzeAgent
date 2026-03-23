"""
Session Service

Manages conversation sessions.
"""

import logging
from typing import Optional

from ..agent import Session, SessionManager
from ..config import settings

logger = logging.getLogger(__name__)


class SessionService:
    """
    Service for managing conversation sessions.
    """

    def __init__(self):
        """Initialize the session service"""
        self.manager = SessionManager(
            session_timeout=settings.session_timeout,
            max_sessions=settings.max_sessions,
        )

        logger.info("Initialized SessionService")

    def create(self, repo_id: str, session_id: Optional[str] = None) -> Session:
        """
        Create a new session.

        Args:
            repo_id: Repository ID
            session_id: Optional session ID

        Returns:
            Created session
        """
        return self.manager.create(repo_id, session_id)

    def get(self, session_id: str) -> Optional[Session]:
        """
        Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session or None
        """
        return self.manager.get(session_id)

    def delete(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session ID

        Returns:
            True if deleted
        """
        return self.manager.delete(session_id)

    def list_by_repo(self, repo_id: str) -> list:
        """
        List sessions for a repository.

        Args:
            repo_id: Repository ID

        Returns:
            List of sessions
        """
        return self.manager.list_by_repo(repo_id)

    def cleanup_expired(self) -> int:
        """
        Cleanup expired sessions.

        Returns:
            Number of sessions removed
        """
        return self.manager.cleanup_expired()

    def get_stats(self) -> dict:
        """
        Get session statistics.

        Returns:
            Statistics dictionary
        """
        return self.manager.get_stats()
