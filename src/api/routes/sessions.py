"""
Session Routes

API endpoints for session management.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, status, Depends

from ...schemas.session import (
    SessionCreateResponse,
    SessionDetailResponse,
    SessionInfo,
)
from ...services.repo_service import RepositoryService
from ...services.session_service import SessionService

logger = logging.getLogger(__name__)

router = APIRouter()


# Dependencies
async def get_repo_service() -> RepositoryService:
    """Get repository service from app state"""
    from ..main import repo_service
    if repo_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return repo_service


async def get_session_service() -> SessionService:
    """Get session service from app state"""
    from ..main import session_service
    if session_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return session_service


@router.post(
    "/repos/{repo_id}/sessions",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a session",
    description="Create a new conversation session for a repository",
)
async def create_session(
    repo_id: str,
    repo_service: RepositoryService = Depends(get_repo_service),
    session_service: SessionService = Depends(get_session_service),
) -> SessionCreateResponse:
    """
    Create a new session.

    - **repo_id**: Repository identifier
    """
    # Verify repository exists
    repo = repo_service.get(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )

    session = session_service.create(repo_id)

    return SessionCreateResponse(
        session_id=session.session_id,
        repo_id=session.repo_id,
        created_at=session.created_at,
        message_count=session.message_count,
    )


@router.get(
    "/repos/{repo_id}/sessions/{session_id}",
    response_model=SessionDetailResponse,
    summary="Get session details",
    description="Get detailed information and message history for a session",
)
async def get_session(
    repo_id: str,
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
) -> SessionDetailResponse:
    """
    Get session details.

    - **repo_id**: Repository identifier
    - **session_id**: Session identifier
    """
    session = session_service.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    if session.repo_id != repo_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session {session_id} does not belong to repository {repo_id}",
        )

    return SessionDetailResponse(
        session_id=session.session_id,
        repo_id=session.repo_id,
        created_at=session.created_at,
        messages=[m.to_dict() for m in session.messages],
        message_count=session.message_count,
    )


@router.delete(
    "/repos/{repo_id}/sessions/{session_id}",
    summary="Delete a session",
    description="Delete a session and its history",
)
async def delete_session(
    repo_id: str,
    session_id: str,
    session_service: SessionService = Depends(get_session_service),
):
    """
    Delete a session.

    - **repo_id**: Repository identifier
    - **session_id**: Session identifier
    """
    session = session_service.get(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    if session.repo_id != repo_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session {session_id} does not belong to repository {repo_id}",
        )

    if not session_service.delete(session_id):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session",
        )

    return {"message": "Session deleted", "session_id": session_id}
