"""
Database Base Module

Provides database connection and session management
supporting multiple database types via SQLAlchemy.
"""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, pool
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from ..config import settings


# Database engine (lazy initialization)
_engine = None


def get_engine():
    """Get or create database engine"""
    global _engine
    if _engine is None:
        url = settings.database.database_url

        # Configure engine based on database type
        if settings.database.db_type.value == "sqlite":
            _engine = create_engine(
                url,
                connect_args={"check_same_thread": False},
                echo=settings.log_level == "DEBUG",
            )
        else:
            # MySQL/PostgreSQL compatible databases
            _engine = create_engine(
                url,
                pool_size=settings.database.db_pool_size,
                max_overflow=settings.database.db_max_overflow,
                pool_timeout=settings.database.db_pool_timeout,
                pool_recycle=settings.database.db_pool_recycle,
                echo=settings.log_level == "DEBUG",
            )
    return _engine


# Property for backward compatibility
engine = property(lambda self: get_engine())


def get_session_maker():
    """Get session maker"""
    return sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=get_engine()
    )


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Get database session context manager.

    Usage:
        with get_db() as db:
            db.query(Model).all()
    """
    SessionLocal = get_session_maker()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


async def get_async_db() -> Generator[Session, None, None]:
    """
    Get async database session for FastAPI dependency.

    Usage:
        @app.get("/repos")
        async def list_repos(db: Session = Depends(get_async_db)):
            return db.query(Repository).all()
    """
    SessionLocal = get_session_maker()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database tables.

    Creates all tables if they don't exist.
    """
    from .models import Base
    Base.metadata.create_all(bind=get_engine())


def close_db():
    """Close database connection and dispose engine"""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None


def check_connection() -> bool:
    """
    Check database connection health.

    Returns:
        True if connection is successful, False otherwise.
    """
    try:
        with get_db() as db:
            db.execute("SELECT 1")
        return True
    except Exception:
        return False
