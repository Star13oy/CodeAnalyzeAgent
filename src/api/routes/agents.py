"""
Agent Routes

API endpoints for agent interactions.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse

from ...schemas.agent import (
    AskRequest,
    AskResponse,
    TroubleshootRequest,
    TroubleshootResponse,
)
from ...schemas.common import ErrorResponse
from ...services.repo_service import RepositoryService
from ...services.agent_service import AgentService
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


async def get_agent_service() -> AgentService:
    """Get agent service from app state"""
    from ..main import agent_service
    if agent_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return agent_service


async def get_session_service() -> SessionService:
    """Get session service from app state"""
    from ..main import session_service
    if session_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return session_service


@router.post(
    "/repos/{repo_id}/ask",
    response_model=AskResponse,
    summary="Ask a question",
    description="Ask a question about the codebase and get an AI-powered answer",
)
async def ask_question(
    repo_id: str,
    request: AskRequest,
    repo_service: RepositoryService = Depends(get_repo_service),
    agent_service: AgentService = Depends(get_agent_service),
    session_service: SessionService = Depends(get_session_service),
) -> AskResponse:
    """
    Ask a question about the repository.

    The agent will explore the codebase using various tools to
    provide a detailed, accurate answer with source references.

    - **repo_id**: Repository identifier
    - **question**: Your question about the codebase
    - **session_id**: Optional session ID for multi-turn conversations
    """
    # Debug: Check LLM before processing
    llm = agent_service._get_llm()
    logger.info(f"LLM type: {type(llm).__name__}, model: {llm.model}")

    # Get repository
    repo = repo_service.get(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )

    try:
        # Get or create session
        session = None
        if request.session_id:
            session = session_service.get(request.session_id)
            if not session:
                # Create new session with provided ID
                session = session_service.create(repo_id, request.session_id)
        else:
            # Create new session
            session = session_service.create(repo_id)

        # Execute agent
        result = agent_service.ask(
            repo_id=repo_id,
            repo_path=repo["path"],
            question=request.question,
            session_id=session.session_id,
        )

        return AskResponse(**result)

    except Exception as e:
        logger.exception(f"Failed to process question for repo {repo_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process question: {str(e)}",
        )


@router.post(
    "/repos/{repo_id}/troubleshoot",
    response_model=TroubleshootResponse,
    summary="Troubleshoot an error",
    description="Get help diagnosing and fixing errors in your code",
)
async def troubleshoot(
    repo_id: str,
    request: TroubleshootRequest,
    repo_service: RepositoryService = Depends(get_repo_service),
    agent_service: AgentService = Depends(get_agent_service),
) -> TroubleshootResponse:
    """
    Troubleshoot an error.

    The agent will analyze the error log, stack trace, and codebase
    to diagnose the issue and suggest fixes.

    - **repo_id**: Repository identifier
    - **error_log**: Error message or log
    - **stack_trace**: Optional full stack trace
    - **context**: Additional context information
    """
    # Get repository
    repo = repo_service.get(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )

    try:
        result = agent_service.troubleshoot(
            repo_id=repo_id,
            repo_path=repo["path"],
            error_log=request.error_log,
            stack_trace=request.stack_trace,
            context=request.context,
        )

        return TroubleshootResponse(**result)

    except Exception as e:
        logger.exception(f"Failed to troubleshoot for repo {repo_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to troubleshoot: {str(e)}",
        )


@router.post(
    "/repos/{repo_id}/ask/stream",
    summary="Ask a question (streaming)",
    description="Ask a question and receive real-time progress updates via Server-Sent Events",
)
async def ask_question_stream(
    repo_id: str,
    request: AskRequest,
    repo_service: RepositoryService = Depends(get_repo_service),
    agent_service: AgentService = Depends(get_agent_service),
    session_service: SessionService = Depends(get_session_service),
):
    """
    Ask a question with real-time progress updates.

    Returns a Server-Sent Events stream with events:
    - {"type": "start", "session_id": "...", "max_iterations": 15}
    - {"type": "progress", "iteration": 1, "max_iterations": 15, "status": "thinking"}
    - {"type": "tool_call", "tool": "file_read", "arguments": {...}}
    - {"type": "tool_result", "tool": "file_read", "success": true, "result_preview": "..."}
    - {"type": "complete", "result": {...}}
    - {"type": "error", "message": "..."}
    """
    # Get repository
    repo = repo_service.get(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )

    def event_generator():
        try:
            for event in agent_service.ask_stream(
                repo_id=repo_id,
                repo_path=repo["path"],
                question=request.question,
                session_id=request.session_id,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.exception(f"Stream error for repo {repo_id}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
