"""
Session Management

Manages conversation sessions for the CodeAgent.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class SessionMessage:
    """A message in a session"""
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class Session:
    """A conversation session"""
    session_id: str
    repo_id: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    messages: List[SessionMessage] = field(default_factory=list)

    @property
    def age(self) -> float:
        """Session age in seconds"""
        return time.time() - self.created_at

    @property
    def idle_time(self) -> float:
        """Time since last activity"""
        return time.time() - self.updated_at

    @property
    def message_count(self) -> int:
        """Number of messages in session"""
        return len(self.messages)

    def add_message(self, role: str, content: str, **metadata) -> None:
        """Add a message to the session"""
        self.messages.append(
            SessionMessage(
                role=role,
                content=content,
                metadata=metadata
            )
        )
        self.updated_at = time.time()

    def get_recent_messages(self, limit: int = 10) -> List[SessionMessage]:
        """Get recent messages"""
        return self.messages[-limit:] if self.messages else []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "session_id": self.session_id,
            "repo_id": self.repo_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "message_count": self.message_count,
            "messages": [m.to_dict() for m in self.messages],
        }


class SessionManager:
    """
    Manages conversation sessions.

    Provides session creation, retrieval, and cleanup.
    """

    def __init__(
        self,
        session_timeout: int = 3600,  # 1 hour
        max_sessions: int = 1000,
    ):
        """
        Initialize the session manager.

        Args:
            session_timeout: Session idle timeout in seconds
            max_sessions: Maximum number of active sessions
        """
        self.sessions: Dict[str, Session] = {}
        self.session_timeout = session_timeout
        self.max_sessions = max_sessions

        logger.info(
            f"Initialized SessionManager: timeout={session_timeout}s, "
            f"max_sessions={max_sessions}"
        )

    def create(self, repo_id: str, session_id: Optional[str] = None) -> Session:
        """
        Create a new session.

        Args:
            repo_id: Repository ID
            session_id: Optional session ID (auto-generated if not provided)

        Returns:
            Session: The created session
        """
        # Cleanup old sessions if at capacity
        self._cleanup_if_needed()

        # Generate session ID if not provided
        if session_id is None:
            session_id = str(uuid.uuid4())

        # Create session
        session = Session(
            session_id=session_id,
            repo_id=repo_id,
        )

        self.sessions[session_id] = session
        logger.info(f"Created session {session_id} for repo {repo_id}")

        return session

    def get(self, session_id: str) -> Optional[Session]:
        """
        Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session or None if not found
        """
        session = self.sessions.get(session_id)

        if session:
            # Check if session has expired
            if session.idle_time > self.session_timeout:
                logger.info(f"Session {session_id} expired (idle: {session.idle_time:.0f}s)")
                del self.sessions[session_id]
                return None

            # Update access time
            session.updated_at = time.time()

        return session

    def delete(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session ID

        Returns:
            bool: True if deleted, False if not found
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Deleted session {session_id}")
            return True
        return False

    def list_by_repo(self, repo_id: str) -> List[Session]:
        """
        List all sessions for a repository.

        Args:
            repo_id: Repository ID

        Returns:
            List of sessions
        """
        return [
            s for s in self.sessions.values()
            if s.repo_id == repo_id
        ]

    def cleanup_expired(self) -> int:
        """
        Remove all expired sessions.

        Returns:
            int: Number of sessions removed
        """
        now = time.time()
        expired_ids = [
            sid for sid, session in self.sessions.items()
            if now - session.updated_at > self.session_timeout
        ]

        for sid in expired_ids:
            del self.sessions[sid]

        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired sessions")

        return len(expired_ids)

    def _cleanup_if_needed(self) -> None:
        """Cleanup sessions if at capacity"""
        if len(self.sessions) >= self.max_sessions:
            # Remove oldest sessions first
            sorted_sessions = sorted(
                self.sessions.items(),
                key=lambda x: x[1].updated_at
            )

            # Remove 10% of sessions
            to_remove = int(self.max_sessions * 0.1)
            for sid, _ in sorted_sessions[:to_remove]:
                del self.sessions[sid]

            logger.info(f"Cleaned up {to_remove} old sessions (capacity reached)")

    def get_stats(self) -> Dict[str, Any]:
        """Get session statistics"""
        active = len(self.sessions)
        total_messages = sum(s.message_count for s in self.sessions.values())

        return {
            "active_sessions": active,
            "total_messages": total_messages,
            "max_capacity": self.max_sessions,
            "timeout_seconds": self.session_timeout,
        }
