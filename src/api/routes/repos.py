"""
Repository Routes

API endpoints for repository management.
"""

import logging
from typing import List

from fastapi import APIRouter, HTTPException, status, Depends

from ...schemas.repo import (
    RepositoryCreate,
    RepositoryUpdate,
    RepositoryInfo,
    RepositoryListResponse,
)
from ...schemas.common import ErrorResponse, ErrorDetail
from ...services.repo_service import RepositoryService

logger = logging.getLogger(__name__)

router = APIRouter()


# Dependency to get repo_service
async def get_repo_service() -> RepositoryService:
    """Get repository service from app state"""
    from fastapi import Request
    # This will be called during request, so app state is available
    import sys
    from ..main import repo_service
    if repo_service is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    return repo_service


@router.post(
    "/repos",
    response_model=RepositoryInfo,
    status_code=status.HTTP_201_CREATED,
    summary="Create a repository",
    description="Create and index a new code repository",
)
async def create_repo(
    repo: RepositoryCreate,
    service: RepositoryService = Depends(get_repo_service)
) -> RepositoryInfo:
    """
    Create a new repository and build its index.

    - **id**: Unique repository identifier
    - **name**: Repository display name
    - **path**: Absolute path to the repository
    """
    try:
        result = service.create(repo.id, repo.name, repo.path)
        return RepositoryInfo(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Failed to create repository {repo.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create repository: {str(e)}",
        )


@router.get(
    "/repos",
    response_model=RepositoryListResponse,
    summary="List all repositories",
    description="Get a list of all indexed repositories",
)
async def list_repos(
    service: RepositoryService = Depends(get_repo_service)
) -> RepositoryListResponse:
    """
    List all repositories.

    Returns information about all indexed repositories.
    """
    repos = service.list_all()
    return RepositoryListResponse(
        repos=[RepositoryInfo(**r) for r in repos],
        total=len(repos),
    )


@router.get(
    "/repos/{repo_id}",
    response_model=RepositoryInfo,
    summary="Get repository details",
    description="Get detailed information about a specific repository",
)
async def get_repo(
    repo_id: str,
    service: RepositoryService = Depends(get_repo_service)
) -> RepositoryInfo:
    """
    Get repository details.

    - **repo_id**: Repository identifier
    """
    repo = service.get(repo_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )
    return RepositoryInfo(**repo)


@router.put(
    "/repos/{repo_id}",
    response_model=RepositoryInfo,
    summary="Update a repository",
    description="Update repository index or metadata",
)
async def update_repo(
    repo_id: str,
    update: RepositoryUpdate,
    service: RepositoryService = Depends(get_repo_service)
) -> RepositoryInfo:
    """
    Update a repository.

    - **repo_id**: Repository identifier
    - **reindex**: Whether to rebuild the index
    """
    repo = service.update(repo_id, reindex=update.reindex)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )
    return RepositoryInfo(**repo)


@router.delete(
    "/repos/{repo_id}",
    summary="Delete a repository",
    description="Delete a repository and its index",
)
async def delete_repo(
    repo_id: str,
    service: RepositoryService = Depends(get_repo_service)
):
    """
    Delete a repository.

    - **repo_id**: Repository identifier
    """
    if not service.delete(repo_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository not found: {repo_id}",
        )
    return {"message": "Repository deleted", "id": repo_id}
