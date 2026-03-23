"""
Agent Schemas

Models for agent interaction APIs.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class AskRequest(BaseModel):
    """Request to ask a question"""
    question: str = Field(..., description="User question about the codebase", min_length=1)
    session_id: Optional[str] = Field(None, description="Session ID for multi-turn conversations")

    class Config:
        json_schema_extra = {
            "example": {
                "question": "How is the authentication logic implemented?",
                "session_id": "sess_abc123",
            }
        }


class ToolCallSummary(BaseModel):
    """Summary of a tool call"""
    name: str
    arguments: Dict[str, Any]
    iteration: int
    success: bool


class AskResponse(BaseModel):
    """Response to a question"""
    answer: str
    sources: List[str] = Field(default_factory=list, description="List of source file references")
    tool_calls: List[ToolCallSummary] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score of the answer")
    session_id: str
    tokens_used: Dict[str, int] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "The authentication logic uses JWT tokens...",
                "sources": ["UserService.java:42", "TokenValidator.java:15"],
                "tool_calls": [
                    {
                        "name": "symbol_lookup",
                        "arguments": {"symbol": "authenticate"},
                        "iteration": 0,
                        "success": True,
                    }
                ],
                "confidence": 0.95,
                "session_id": "sess_abc123",
                "tokens_used": {"input": 1250, "output": 380, "total": 1630},
            }
        }


class TroubleshootRequest(BaseModel):
    """Request for troubleshooting"""
    error_log: str = Field(..., description="Error log or message", min_length=1)
    stack_trace: Optional[str] = Field(None, description="Full stack trace if available")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")

    class Config:
        json_schema_extra = {
            "example": {
                "error_log": "NullPointerException at UserService.java:42",
                "stack_trace": "java.lang.NullPointerException\n\tat ...",
                "context": {"user_id": "12345", "environment": "production"},
            }
        }


class RelatedCode(BaseModel):
    """Related code reference"""
    file: str
    line: int
    description: str


class SimilarIssue(BaseModel):
    """Similar historical issue"""
    issue: str
    file: str
    line: int
    count: int


class TroubleshootResponse(BaseModel):
    """Response to troubleshooting request"""
    diagnosis: str = Field(..., description="Problem diagnosis")
    root_cause: str = Field(..., description="Root cause analysis")
    fix_suggestion: str = Field(..., description="Suggested fix")
    related_code: List[str] = Field(default_factory=list)
    similar_issues: List[SimilarIssue] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    estimated_fix_time: Optional[str] = Field(None, description="Estimated time to fix")

    class Config:
        json_schema_extra = {
            "example": {
                "diagnosis": "NullPointerException in UserService.authenticate()",
                "root_cause": "TokenValidator was not initialized",
                "fix_suggestion": "Add @Component annotation to TokenValidator class",
                "related_code": ["UserService.java:42", "TokenValidator.java:1"],
                "similar_issues": [],
                "confidence": 0.92,
                "estimated_fix_time": "5 minutes",
            }
        }
