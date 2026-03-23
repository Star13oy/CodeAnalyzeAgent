"""
Repository Schemas

Models for repository management APIs.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


class RepositoryCreate(BaseModel):
    """Request to create a new repository"""
    id: str = Field(..., description="Unique repository identifier", min_length=1)
    name: str = Field(..., description="Repository display name", min_length=1)
    path: str = Field(..., description="Absolute path to the repository")

    @field_validator("id")
    def validate_id(cls, v):
        """Validate repository ID format"""
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Repository ID must contain only alphanumeric characters, hyphens, and underscores")
        return v


class RepositoryUpdate(BaseModel):
    """Request to update a repository"""
    reindex: bool = Field(default=False, description="Whether to rebuild the index")


class RepositoryInfo(BaseModel):
    """Repository information"""
    id: str
    name: str
    path: str
    language: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    indexed: bool
    file_count: Optional[int] = None
    symbol_count: Optional[int] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class RepositoryListResponse(BaseModel):
    """Response listing all repositories"""
    repos: List[RepositoryInfo]
    total: int

    class Config:
        json_schema_extra = {
            "example": {
                "repos": [
                    {
                        "id": "user-service",
                        "name": "User Service",
                        "path": "/path/to/user-service",
                        "language": "Java",
                        "created_at": "2026-03-20T10:00:00Z",
                        "updated_at": "2026-03-20T10:05:00Z",
                        "indexed": True,
                        "file_count": 1250,
                        "symbol_count": 8500,
                    }
                ],
                "total": 1,
            }
        }
