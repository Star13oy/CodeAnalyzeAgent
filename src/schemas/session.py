"""
Session Schemas

Models for session management APIs.
"""

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


class SessionMessage(BaseModel):
    """A message in a session"""
    role: str
    content: str
    timestamp: datetime
    metadata: dict = {}


class SessionInfo(BaseModel):
    """Basic session information"""
    session_id: str
    repo_id: str
    created_at: datetime
    message_count: int


class SessionDetailResponse(BaseModel):
    """Detailed session information with messages"""
    session_id: str
    repo_id: str
    created_at: datetime
    messages: List[SessionMessage]
    message_count: int


class SessionCreateResponse(BaseModel):
    """Response when creating a session"""
    session_id: str
    repo_id: str
    created_at: datetime
    message_count: int = 0
