"""
Common Schemas

Shared models used across multiple endpoints.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class ErrorDetail(BaseModel):
    """Error detail"""
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: ErrorDetail

    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "code": "REPO_NOT_FOUND",
                    "message": "Repository not found",
                    "details": {"repo_id": "unknown-repo"},
                }
            }
        }


class ComponentStatus(BaseModel):
    """Component health status"""
    database: str = "healthy"
    llm: str = "healthy"
    indexer: str = "healthy"


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    version: str = "0.1.0"
    uptime: int = Field(..., description="Uptime in seconds")
    components: ComponentStatus

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "version": "0.1.0",
                "uptime": 3600,
                "components": {
                    "database": "healthy",
                    "llm": "healthy",
                    "indexer": "healthy",
                },
            }
        }
