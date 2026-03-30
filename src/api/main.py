"""
FastAPI Main Application

CodeAgent REST API server.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import settings
from ..services import RepositoryService, AgentService, SessionService
from ..schemas import (
    ErrorResponse,
    ErrorDetail,
    HealthResponse,
    ComponentStatus,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Application state
start_time = time.time()

# Services
repo_service: Optional[RepositoryService] = None
agent_service: Optional[AgentService] = None
session_service: Optional[SessionService] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting CodeAgent API...")

    global repo_service, agent_service, session_service
    repo_service = RepositoryService()
    session_service = SessionService()
    agent_service = AgentService(session_service=session_service)

    logger.info("CodeAgent API started successfully")

    yield

    # Shutdown
    logger.info("Shutting down CodeAgent API...")


# Create FastAPI app
app = FastAPI(
    title="CodeAgent API",
    description="Agentic Code Assistant Service",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
            }
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.exception(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
            }
        },
    )


# Health check
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.

    Returns the health status of the service and its components.
    """
    uptime = int(time.time() - start_time)

    # Check component health
    components = ComponentStatus()

    # Check if services are initialized
    if repo_service is None:
        components.database = "unhealthy"
    if agent_service is None:
        components.llm = "unhealthy"

    return HealthResponse(
        status="healthy" if all(
            s == "healthy" for s in [components.database, components.llm, components.indexer]
        ) else "degraded",
        version="0.1.0",
        uptime=uptime,
        components=components,
    )


# Import routes
from .routes import repos, agents, sessions

# Register routes
app.include_router(repos.router, prefix="/api/v1", tags=["Repositories"])
app.include_router(agents.router, prefix="/api/v1", tags=["Agents"])
app.include_router(sessions.router, prefix="/api/v1", tags=["Sessions"])


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "name": "CodeAgent API",
        "version": "0.1.0",
        "description": "Agentic Code Assistant Service",
        "docs": "/docs",
    }
