"""
Database Models

Defines SQLAlchemy ORM models for repositories, symbols, and sessions.
Compatible with multiple database types (SQLite, MySQL, PostgreSQL, etc.)
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, JSON, ForeignKey, Text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models"""
    pass


class Repository(Base):
    """
    Repository model - represents a code repository

    Supports multiple databases via SQLAlchemy ORM.
    """
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    file_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    symbol_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    symbols: Mapped[list["Symbol"]] = relationship(
        "Symbol", back_populates="repository", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="repository", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Repository(id={self.id}, name={self.name})>"


class Symbol(Base):
    """
    Symbol model - represents code symbols (functions, classes, etc.)

    Compatible with multiple databases via TEXT type for JSON fields.
    """
    __tablename__ = "symbols"

    # Use auto-increment ID for better compatibility
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    symbol_metadata: Mapped[Optional[dict]] = mapped_column("symbol_metadata", JSON, nullable=True)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="symbols")

    # Composite indexes for performance
    __table_args__ = (
        Index("idx_symbols_repo_name", "repo_id", "name"),
        Index("idx_symbols_repo_kind", "repo_id", "kind"),
        Index("idx_symbols_file", "file_path"),
    )

    def __repr__(self) -> str:
        return f"<Symbol(name={self.name}, kind={self.kind}, file={self.file_path})>"


class Session(Base):
    """
    Session model - stores conversation sessions

    Uses JSON type for messages storage (compatible across databases).
    """
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    repo_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    messages: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    session_metadata: Mapped[Optional[dict]] = mapped_column("session_metadata", JSON, nullable=True)

    # Relationships
    repository: Mapped["Repository"] = relationship("Repository", back_populates="sessions")

    __table_args__ = (
        Index("idx_sessions_repo", "repo_id"),
        Index("idx_sessions_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, repo_id={self.repo_id})>"
