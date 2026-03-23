"""
Configuration Management

Manages application configuration from environment variables.
Supports multiple database types and LLM providers.
"""

import os
import json
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class LLMProvider(str, Enum):
    """LLM provider types"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    AZURE = "azure"
    COMPANY = "company"  # 公司中转站
    CUSTOM = "custom"


class DatabaseType(str, Enum):
    """Database types"""
    SQLITE = "sqlite"
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    GAUSSDB_MYSQL = "gaussdb_mysql"  # GaussDB MySQL 协议
    GAUSSDB_POSTGRES = "gaussdb_postgres"  # GaussDB PostgreSQL 协议
    GOLDENDB = "goldendb"  # GoldenDB (MySQL 协议兼容)


class LLMConfig(BaseSettings):
    """LLM provider configuration"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Provider selection
    provider: LLMProvider = Field(
        default=LLMProvider.COMPANY,
        description="Active LLM provider"
    )

    # Company LLM (公司中转站)
    company_llm_base_url: str = "https://your-company-gateway.com"
    company_llm_api_key: str = ""
    company_llm_model: str = "claude-sonnet-4-6"

    # Anthropic (支持 ANTHROPIC_AUTH_TOKEN)
    anthropic_api_key: str = Field(default="", alias="anthropic_auth_token")
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_model: str = "claude-sonnet-4-6"

    # OpenAI
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4"

    # Azure OpenAI
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_deployment: str = ""

    # Custom LLM
    custom_llm_base_url: str = ""
    custom_llm_api_key: str = ""
    custom_llm_model: str = ""
    custom_llm_headers: str = ""  # JSON string

    @property
    def active_config(self) -> Dict[str, Any]:
        """Get active provider configuration"""
        configs = {
            LLMProvider.ANTHROPIC: {
                "base_url": self.anthropic_base_url,
                "api_key": self.anthropic_api_key,
                "model": self.anthropic_model,
            },
            LLMProvider.OPENAI: {
                "base_url": self.openai_base_url,
                "api_key": self.openai_api_key,
                "model": self.openai_model,
            },
            LLMProvider.AZURE: {
                "endpoint": self.azure_openai_endpoint,
                "api_key": self.azure_openai_api_key,
                "api_version": self.azure_openai_api_version,
                "deployment": self.azure_openai_deployment,
            },
            LLMProvider.COMPANY: {
                "base_url": self.company_llm_base_url,
                "api_key": self.company_llm_api_key,
                "model": self.company_llm_model,
            },
            LLMProvider.CUSTOM: {
                "base_url": self.custom_llm_base_url,
                "api_key": self.custom_llm_api_key,
                "model": self.custom_llm_model,
                "headers": json.loads(self.custom_llm_headers) if self.custom_llm_headers else {},
            },
        }
        return configs.get(self.provider, {})


class DatabaseConfig(BaseSettings):
    """Database configuration supporting multiple database types"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database type selection
    db_type: DatabaseType = Field(
        default=DatabaseType.SQLITE,
        description="Database type"
    )

    # SQLite
    db_sqlite_path: str = "./codeagent.db"

    # MySQL / GaussDB (MySQL) / GoldenDB
    db_mysql_host: str = "localhost"
    db_mysql_port: int = 3306
    db_mysql_name: str = "codeagent"
    db_mysql_user: str = "root"
    db_mysql_password: str = ""

    # PostgreSQL / GaussDB (PostgreSQL)
    db_postgres_host: str = "localhost"
    db_postgres_port: int = 5432
    db_postgres_name: str = "codeagent"
    db_postgres_user: str = "postgres"
    db_postgres_password: str = ""

    # Connection pool
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 3600

    @property
    def database_url(self) -> str:
        """Generate SQLAlchemy database URL"""
        if self.db_type == DatabaseType.SQLITE:
            return f"sqlite:///{self.db_sqlite_path}"

        elif self.db_type in (DatabaseType.MYSQL, DatabaseType.GAUSSDB_MYSQL, DatabaseType.GOLDENDB):
            # MySQL 协议兼容数据库
            return (
                f"mysql+pymysql://{self.db_mysql_user}:{self.db_mysql_password}"
                f"@{self.db_mysql_host}:{self.db_mysql_port}/{self.db_mysql_name}"
                f"?charset=utf8mb4"
            )

        elif self.db_type in (DatabaseType.POSTGRESQL, DatabaseType.GAUSSDB_POSTGRES):
            # PostgreSQL 协议兼容数据库
            return (
                f"postgresql+psycopg://{self.db_postgres_user}:{self.db_postgres_password}"
                f"@{self.db_postgres_host}:{self.db_postgres_port}/{self.db_postgres_name}"
            )

        raise ValueError(f"Unsupported database type: {self.db_type}")

    @property
    def driver_name(self) -> str:
        """Get database driver name for SQLAlchemy"""
        drivers = {
            DatabaseType.SQLITE: "sqlite",
            DatabaseType.MYSQL: "mysql",
            DatabaseType.POSTGRESQL: "postgresql",
            DatabaseType.GAUSSDB_MYSQL: "mysql",
            DatabaseType.GAUSSDB_POSTGRES: "postgresql",
            DatabaseType.GOLDENDB: "mysql",
        }
        return drivers.get(self.db_type, "sqlite")


class Settings(BaseSettings):
    """Application settings"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Nested configurations
    llm: LLMConfig = Field(default_factory=LLMConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)

    # Agent Configuration
    max_tool_iterations: int = Field(
        default=25,
        ge=1,
        le=50,
        description="Maximum tool use iterations"
    )
    agent_temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Agent temperature"
    )
    agent_max_tokens: int = Field(
        default=4096,
        ge=1,
        description="Maximum tokens per response"
    )

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = Field(
        default=8000,
        ge=1,
        le=65535,
        description="API server port"
    )
    api_reload: bool = False

    # Session Configuration
    session_timeout: int = 3600
    max_sessions: int = 1000

    # Security
    api_token: str = ""
    cors_origins: List[str] = Field(default=["http://localhost:3000"])

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Repository
    repo_base_path: str = "/data/repos"

    # Cache
    enable_cache: bool = True
    cache_ttl: int = 3600

    @property
    def is_authenticated(self) -> bool:
        """Check if authentication is enabled"""
        return bool(self.api_token)


# Global settings instance
settings = Settings()
