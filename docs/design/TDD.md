# CodeAgent 技术设计文档 (TDD)

## 1. 系统架构

### 1.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         客户端系统                              │
└─────────────────────────────┬───────────────────────────────────┘
                              │ REST / gRPC
┌─────────────────────────────▼───────────────────────────────────┐
│                      API Gateway (FastAPI)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  /ask API    │  │ /troubleshoot│  │  /admin API  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                      Service Layer                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  CodeAgent Service                       │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │    │
│  │  │ Repo Mgr   │  │Session Mgr │  │Agent Pool  │        │    │
│  │  └────────────┘  └────────────┘  └────────────┘        │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                      Agent Engine                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  Agentic Loop                            │    │
│  │                                                          │    │
│  │  1. 接收问题 → 2. 规划探索 → 3. 调用工具                 │    │
│  │       ↓                                                  │    │
│  │  4. 分析结果 → 5. 决策下一步 → 6. 生成答案               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│  ┌───────────────────────────▼──────────────────────────────┐   │
│  │                    Tool Layer                            │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │   │
│  │  │code_grep │ │file_read │ │symbol_id │ │ast_analy │    │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐                │   │
│  │  │call_graph│ │dep_graph │ │find_ref  │                │   │
│  │  └──────────┘ └──────────┘ └──────────┘                │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                    LLM Abstraction Layer                        │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              LLMProvider Interface                       │    │
│  │  - chat(messages, tools) → Response                     │    │
│  │  - stream_chat(messages, tools) → Generator             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐ │
│  │ Company  │ │Anthropic │ │  OpenAI  │ │  Azure   │ │Custom│ │
│  │ Gateway  │ │  Claude  │ │ / Compatible│ OpenAI │ │ HTTP │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                    Database Layer (SQLAlchemy)                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐ │
│  │ SQLite   │ │  MySQL   │ │PostgreSQL│ │ GaussDB  │ │Golden│ │
│  │          │ │          │ │          │ │          │ │  DB  │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────┘ │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                      Storage Layer                              │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐               │
│  │ Symbol DB  │  │ AST Cache  │  │ Session DB │               │
│  │ (Multi-DB) │  │ (File)     │  │ (Multi-DB) │               │
│  └────────────┘  └────────────┘  └────────────┘               │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 核心组件

| 组件 | 职责 | 技术选型 |
|------|------|----------|
| **API Gateway** | 暴露 REST API，处理请求验证 | FastAPI |
| **Service Layer** | 业务逻辑，会话管理 | Python Class |
| **Agent Engine** | Agentic 循环，工具调度 | Custom + Anthropic SDK |
| **Tool Layer** | 代码探索工具集 | ripgrep, ctags, tree-sitter |
| **LLM Layer** | 多厂商 LLM 抽象和适配 | Anthropic SDK, OpenAI SDK |
| **Database Layer** | 多数据库支持 (SQLAlchemy) | SQLite, MySQL, PostgreSQL, GaussDB, GoldenDB |
| **Storage Layer** | 数据持久化 | SQLAlchemy + File |

---

## 2. 核心模块设计

### 2.1 LLM 抽象层

#### 2.1.1 接口定义

```python
# src/llm/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Generator
from dataclasses import dataclass

@dataclass
class Message:
    role: str  # user | assistant | system
    content: str

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any]

@dataclass
class ToolResult:
    tool_call_id: str
    content: str

@dataclass
class LLMResponse:
    content: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"  # stop | tool_calls | length
    model: str = ""
    usage: Dict[str, int] = field(default_factory=dict)

class LLMProvider(ABC):
    """LLM 提供者抽象接口"""

    @abstractmethod
    def chat(
        self,
        messages: List[Message],
        tools: List[Dict],
        **kwargs
    ) -> LLMResponse:
        """同步聊天"""
        pass

    @abstractmethod
    def stream_chat(
        self,
        messages: List[Message],
        tools: List[Dict],
        **kwargs
    ) -> Generator[LLMResponse, None, None]:
        """流式聊天"""
        pass
```

#### 2.1.2 公司中转站适配器

```python
# src/llm/company_adapter.py
import anthropic
from .base import LLMProvider, LLMResponse, Message, ToolCall

class CompanyLLMAdapter(LLMProvider):
    """
    公司 API 中转站适配器
    完全兼容 Anthropic API 格式
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://your-company-gateway.com",
        model: str = "claude-sonnet-4-6"
    ):
        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model

    def chat(
        self,
        messages: List[Message],
        tools: List[Dict],
        **kwargs
    ) -> LLMResponse:
        # 转换消息格式
        api_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

        # 调用 API
        response = self.client.messages.create(
            model=self.model,
            messages=api_messages,
            tools=tools,
            max_tokens=kwargs.get("max_tokens", 4096),
        )

        # 解析响应
        return self._parse_response(response)

    def _parse_response(self, response) -> LLMResponse:
        content = response.content
        tool_calls = []
        text_content = []

        for block in content:
            if block.type == "text":
                text_content.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input
                ))

        return LLMResponse(
            content="\n".join(text_content) if text_content else None,
            tool_calls=tool_calls,
            finish_reason=response.stop_reason,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        )
```

#### 2.1.3 多厂商 LLM 支持

```python
# src/llm/factory.py
from enum import Enum

class LLMProvider(str, Enum):
    """支持的 LLM 厂商"""
    ANTHROPIC = "anthropic"     # Anthropic Claude 官方
    OPENAI = "openai"           # OpenAI / 兼容 API
    AZURE = "azure"             # Azure OpenAI
    COMPANY = "company"         # 公司中转站
    CUSTOM = "custom"           # 自定义 HTTP 端点

# 厂商适配器注册表
PROVIDER_REGISTRY = {
    LLMProvider.ANTHROPIC: AnthropicAdapter,
    LLMProvider.OPENAI: OpenAIAdapter,
    LLMProvider.AZURE: AzureOpenAIAdapter,
    LLMProvider.COMPANY: CompanyLLMAdapter,
    LLMProvider.CUSTOM: CustomLLMAdapter,
}

def create_llm_provider(provider: LLMProvider, config: Dict) -> LLMProvider:
    """根据配置创建 LLM 提供者"""
    provider_class = PROVIDER_REGISTRY.get(provider)
    return provider_class(**config)
```

**支持的厂商：**

| 厂商 | 适配器 | 说明 |
|------|--------|------|
| 公司中转站 | `CompanyLLMAdapter` | Anthropic 兼容格式 |
| Anthropic | `AnthropicAdapter` | 官方 Claude API |
| OpenAI | `OpenAIAdapter` | OpenAI 或兼容 API |
| Azure OpenAI | `AzureOpenAIAdapter` | 微软 Azure OpenAI 服务 |
| 自定义 | `CustomLLMAdapter` | 任意 HTTP 端点 |

**配置方式：**

```bash
# .env - 切换 LLM 厂商
LLM_PROVIDER=company  # anthropic | openai | azure | company | custom

# 公司中转站
COMPANY_LLM_BASE_URL=https://your-company-gateway.com
COMPANY_LLM_API_KEY=your-key
COMPANY_LLM_MODEL=claude-sonnet-4-6

# OpenAI
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4

# Azure OpenAI
AZURE_OPENAI_API_KEY=xxx
AZURE_OPENAI_ENDPOINT=https://xxx.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4
```

### 2.2 数据库层设计

#### 2.2.1 多数据库支持

```python
# src/db/base.py
from sqlalchemy import create_engine
from ..config import DatabaseType

def get_engine():
    """根据配置创建数据库引擎"""
    db_type = settings.database.db_type

    if db_type == DatabaseType.SQLITE:
        url = f"sqlite:///{settings.database.db_sqlite_path}"
        return create_engine(url, connect_args={"check_same_thread": False})

    elif db_type in (DatabaseType.MYSQL, DatabaseType.GAUSSDB_MYSQL, DatabaseType.GOLDENDB):
        # MySQL 协议兼容数据库
        url = (
            f"mysql+pymysql://{settings.database.db_mysql_user}:"
            f"{settings.database.db_mysql_password}@"
            f"{settings.database.db_mysql_host}:{settings.database.db_mysql_port}/"
            f"{settings.database.db_mysql_name}?charset=utf8mb4"
        )
        return create_engine(url, pool_size=5, max_overflow=10)

    elif db_type in (DatabaseType.POSTGRESQL, DatabaseType.GAUSSDB_POSTGRES):
        # PostgreSQL 协议兼容数据库
        url = (
            f"postgresql+psycopg://{settings.database.db_postgres_user}:"
            f"{settings.database.db_postgres_password}@"
            f"{settings.database.db_postgres_host}:{settings.database.db_postgres_port}/"
            f"{settings.database.db_postgres_name}"
        )
        return create_engine(url, pool_size=5, max_overflow=10)
```

**支持的数据库：**

| 数据库 | 协议 | Python 驱动 | 状态 |
|--------|------|------------|------|
| SQLite | 内置 | aiosqlite | ✅ |
| MySQL | MySQL | PyMySQL | ✅ |
| PostgreSQL | PostgreSQL | psycopg | ✅ |
| GaussDB | MySQL/PostgreSQL | PyMySQL/psycopg | ✅ |
| GoldenDB | MySQL | PyMySQL | ✅ |

**配置方式：**

```bash
# .env - 切换数据库类型
DB_TYPE=mysql  # sqlite | mysql | postgresql | gaussdb_mysql | goldendb

# MySQL / GoldenDB 配置
DB_MYSQL_HOST=localhost
DB_MYSQL_PORT=3306
DB_MYSQL_NAME=codeagent
DB_MYSQL_USER=root
DB_MYSQL_PASSWORD=secret

# PostgreSQL / GaussDB 配置
DB_POSTGRES_HOST=localhost
DB_POSTGRES_PORT=5432
DB_POSTGRES_NAME=codeagent
DB_POSTGRES_USER=postgres
DB_POSTGRES_PASSWORD=secret
```

#### 2.2.2 数据库模型 (SQLAlchemy ORM)

```python
# src/db/models.py
from sqlalchemy import String, Integer, Boolean, DateTime, JSON, ForeignKey, Text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    """所有模型的基类"""
    pass

class Repository(Base):
    """代码库模型 - 兼容多数据库"""
    __tablename__ = "repositories"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    # ... 其他字段

    # 关系
    symbols: Mapped[list["Symbol"]] = relationship(
        "Symbol", back_populates="repository", cascade="all, delete-orphan"
    )

class Symbol(Base):
    """符号索引模型 - 兼容多数据库"""
    __tablename__ = "symbols"

    # 使用自增 ID，兼容所有数据库
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_id: Mapped[str] = mapped_column(String(100), ForeignKey("repositories.id"))
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    # JSON 类型在多数据库中自动适配
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # 复合索引
    __table_args__ = (
        Index("idx_symbols_repo_name", "repo_id", "name"),
    )
```

### 2.3 工具层设计

#### 2.2.1 工具抽象

```python
# src/tools/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseTool(ABC):
    """工具基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述（用于 LLM 理解）"""
        pass

    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """输入参数 JSON Schema"""
        pass

    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> str:
        """执行工具"""
        pass

    def to_dict(self) -> Dict[str, Any]:
        """转换为 LLM 工具格式"""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema
        }
```

#### 2.2.2 代码搜索工具

```python
# src/tools/code_search.py
import subprocess
from pathlib import Path
from .base import BaseTool

class CodeSearchTool(BaseTool):
    """基于 ripgrep 的代码搜索工具"""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)

    @property
    def name(self) -> str:
        return "code_search"

    @property
    def description(self) -> str:
        return "在代码库中搜索关键词或正则表达式"

    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或正则表达式"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "文件模式，如 *.java, **/*.py"
                },
                "context_lines": {
                    "type": "integer",
                    "description": "显示上下文行数",
                    "default": 3
                }
            },
            "required": ["query"]
        }

    def execute(self, input_data: Dict) -> str:
        query = input_data["query"]
        pattern = input_data.get("file_pattern")
        context = input_data.get("context_lines", 3)

        cmd = [
            "rg",
            query,
            str(self.repo_path),
            "-C", str(context),
            "--json"
        ]

        if pattern:
            cmd.extend(["-g", pattern])

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return f"搜索失败: {result.stderr}"

        return self._parse_output(result.stdout)

    def _parse_output(self, output: str) -> str:
        """解析 ripgrep JSON 输出"""
        import json
        results = []
        for line in output.strip().split('\n'):
            try:
                data = json.loads(line)
                if data.get("type") == "match":
                    results.append(
                        f"{data['path']}:{data['lines']['text']}"
                    )
            except json.JSONDecodeError:
                continue
        return "\n".join(results) if results else "未找到匹配结果"
```

#### 2.2.3 符号索引工具

```python
# src/tools/symbol_index.py
import subprocess
from pathlib import Path
from .base import BaseTool

class SymbolIndexTool(BaseTool):
    """基于 ctags 的符号索引工具"""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path)
        self._ensure_index()

    def _ensure_index(self):
        """确保符号索引存在"""
        tags_file = self.repo_path / ".tags"
        if not tags_file.exists():
            self._build_index()

    def _build_index(self):
        """构建符号索引"""
        subprocess.run(
            ["ctags", "-R", "-o", ".tags", str(self.repo_path)],
            cwd=self.repo_path,
            capture_output=True
        )

    @property
    def name(self) -> str:
        return "symbol_lookup"

    @property
    def description(self) -> str:
        return "查找函数、类、方法的定义位置"

    @property
    def input_schema(self) -> Dict:
        return {
            "type": "object",
            "properties": {
                "symbol": {
                    "type": "string",
                    "description": "符号名称（函数名、类名等）"
                },
                "kind": {
                    "type": "string",
                    "description": "符号类型: function, class, method, variable",
                    "enum": ["function", "class", "method", "variable", ""]
                }
            },
            "required": ["symbol"]
        }

    def execute(self, input_data: Dict) -> str:
        symbol = input_data["symbol"]
        kind = input_data.get("kind", "")

        # 查询 tags 文件
        cmd = ["grep", f"^{symbol}\t", str(self.repo_path / ".tags")]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return f"未找到符号: {symbol}"

        return self._parse_tags(result.stdout, kind)

    def _parse_tags(self, tags_output: str, kind_filter: str) -> str:
        """解析 ctags 输出"""
        results = []
        for line in tags_output.split('\n'):
            if not line:
                continue
            parts = line.split('\t')
            if len(parts) >= 4:
                name, path, pattern, kind = parts[:4]
                if kind_filter and kind != kind_filter:
                    continue
                results.append(f"{name} → {path} (类型: {kind})")

        return "\n".join(results) if results else "未找到匹配符号"
```

### 2.4 Agent 引擎设计

```python
# src/agent/core.py
from typing import List, Dict, Optional
from ..llm.base import LLMProvider, Message
from ..tools.base import BaseTool

class CodeAgent:
    """代码探索 Agent"""

    def __init__(
        self,
        repo_path: str,
        llm: LLMProvider,
        tools: List[BaseTool],
        max_iterations: int = 10
    ):
        self.repo_path = repo_path
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.max_iterations = max_iterations

    def ask(self, question: str) -> Dict[str, Any]:
        """
        回答问题

        Returns:
            {
                "answer": str,
                "sources": List[str],
                "tool_calls": List[Dict],
                "confidence": float
            }
        """
        messages = [Message(role="user", content=question)]
        tool_calls_history = []

        for iteration in range(self.max_iterations):
            # 调用 LLM
            response = self.llm.chat(
                messages=messages,
                tools=[t.to_dict() for t in self.tools.values()]
            )

            # 记录工具调用
            if response.tool_calls:
                tool_calls_history.extend([
                    {
                        "name": tc.name,
                        "arguments": tc.arguments,
                        "iteration": iteration
                    }
                    for tc in response.tool_calls
                ])

            # 检查是否完成
            if response.finish_reason == "stop":
                return {
                    "answer": response.content,
                    "sources": self._extract_sources(messages),
                    "tool_calls": tool_calls_history,
                    "confidence": self._calculate_confidence(tool_calls_history)
                }

            # 执行工具调用
            messages.append({
                "role": "assistant",
                "content": response.content or ""
            })

            for tool_call in response.tool_calls:
                result = self._execute_tool(tool_call)
                messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": result
                    }]
                })

        return {
            "answer": "达到最大迭代次数，未能完成分析",
            "sources": [],
            "tool_calls": tool_calls_history,
            "confidence": 0.0
        }

    def _execute_tool(self, tool_call) -> str:
        """执行工具"""
        tool = self.tools.get(tool_call.name)
        if not tool:
            return f"工具 {tool_call.name} 不存在"

        try:
            return tool.execute(tool_call.arguments)
        except Exception as e:
            return f"工具执行失败: {str(e)}"

    def _extract_sources(self, messages: List) -> List[str]:
        """从消息中提取源代码位置"""
        sources = set()
        for msg in messages:
            if isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if block.get("type") == "tool_result":
                        # 解析文件路径和行号
                        content = block.get("content", "")
                        # 简化实现：提取类似 file.py:123 的模式
                        import re
                        matches = re.findall(r'[\w.]+:\d+', content)
                        sources.update(matches)
        return list(sources)

    def _calculate_confidence(self, tool_calls: List[Dict]) -> float:
        """计算置信度"""
        if not tool_calls:
            return 0.5

        # 基于工具调用次数和类型计算
        successful_calls = sum(1 for tc in tool_calls if "失败" not in str(tc))
        return min(0.95, 0.5 + successful_calls * 0.1)
```

---

## 3. 数据模型设计

> **注意**：数据库 Schema 已通过 SQLAlchemy ORM 实现，自动适配多种数据库类型。

### 3.1 数据库模型

```sql
-- 代码库表
CREATE TABLE repositories (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    language TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    indexed BOOLEAN DEFAULT FALSE
);

-- 符号索引表
CREATE TABLE symbols (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_id TEXT NOT NULL,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    file_path TEXT NOT NULL,
    line_number INTEGER NOT NULL,
    FOREIGN KEY (repo_id) REFERENCES repositories(id)
);

CREATE INDEX idx_symbols_repo_name ON symbols(repo_id, name);
CREATE INDEX idx_symbols_kind ON symbols(kind);

-- 会话表
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    repo_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    messages JSON,
    FOREIGN KEY (repo_id) REFERENCES repositories(id)
);
```

### 3.2 API 数据模型

```python
# src/schemas/repo.py
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class RepositoryCreate(BaseModel):
    """创建代码库请求"""
    id: str = Field(..., description="代码库唯一标识")
    name: str = Field(..., description="代码库名称")
    path: str = Field(..., description="代码库路径")

class RepositoryInfo(BaseModel):
    """代码库信息"""
    id: str
    name: str
    path: str
    language: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    indexed: bool
    file_count: Optional[int] = None
    symbol_count: Optional[int] = None

# src/schemas/agent.py
class AskRequest(BaseModel):
    """问答请求"""
    question: str = Field(..., description="用户问题")
    session_id: Optional[str] = Field(None, description="会话ID")

class AskResponse(BaseModel):
    """问答响应"""
    answer: str
    sources: List[str] = []
    tool_calls: List[dict] = []
    confidence: float = 0.0
    session_id: str

class TroubleshootRequest(BaseModel):
    """排障请求"""
    error_log: str = Field(..., description="错误日志")
    stack_trace: Optional[str] = Field(None, description="堆栈追踪")
    context: dict = Field(default_factory=dict, description="上下文信息")

class TroubleshootResponse(BaseModel):
    """排障响应"""
    diagnosis: str
    root_cause: str
    fix_suggestion: str
    related_code: List[str]
    confidence: float
```

---

## 4. API 设计

### 4.1 REST API 端点

```
# 代码库管理
POST   /api/v1/repos              # 创建代码库
GET    /api/v1/repos              # 列出所有代码库
GET    /api/v1/repos/{id}         # 获取代码库详情
PUT    /api/v1/repos/{id}         # 更新索引
DELETE /api/v1/repos/{id}         # 删除代码库

# 问答接口
POST   /api/v1/repos/{id}/ask                    # 提问
POST   /api/v1/repos/{id}/troubleshoot           # 排障
POST   /api/v1/repos/{id}/sessions               # 创建会话
GET    /api/v1/repos/{id}/sessions/{session_id}  # 获取会话历史

# 健康检查
GET    /health                    # 健康检查
GET    /metrics                   # 指标（可选）
```

---

## 5. 测试策略

### 5.1 单元测试

```python
# tests/unit/test_llm_adapter.py
import pytest
from src.llm.company_adapter import CompanyLLMAdapter
from src.llm.base import Message

class TestCompanyLLMAdapter:
    """公司 LLM 适配器测试"""

    @pytest.fixture
    def adapter(self):
        return CompanyLLMAdapter(
            api_key="test-key",
            base_url="https://test.com"
        )

    def test_chat_simple(self, adapter, mocker):
        """测试简单对话"""
        # Mock API 响应
        mock_response = mocker.Mock()
        mock_response.content = [mocker.Mock(type="text", text="Hello")]
        mock_response.stop_reason = "end_turn"

        adapter.client.messages.create = mocker.Mock(
            return_value=mock_response
        )

        response = adapter.chat(
            messages=[Message(role="user", content="Hi")],
            tools=[]
        )

        assert response.content == "Hello"
        assert response.finish_reason == "end_turn"

    def test_chat_with_tool_use(self, adapter, mocker):
        """测试工具调用"""
        mock_tool = mocker.Mock()
        mock_tool.type = "tool_use"
        mock_tool.id = "call_123"
        mock_tool.name = "code_search"
        mock_tool.input = {"query": "test"}

        mock_response = mocker.Mock()
        mock_response.content = [mock_tool]
        mock_response.stop_reason = "tool_calls"

        adapter.client.messages.create = mocker.Mock(
            return_value=mock_response
        )

        response = adapter.chat(
            messages=[Message(role="user", content="Search code")],
            tools=[]
        )

        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].name == "code_search"
```

### 5.2 集成测试

```python
# tests/integration/test_agent_flow.py
import pytest
from src.agent.core import CodeAgent
from src.llm.company_adapter import CompanyLLMAdapter
from src.tools.code_search import CodeSearchTool

class TestAgentFlow:
    """Agent 流程集成测试"""

    @pytest.fixture
    def agent(self, test_repo_path):
        llm = CompanyLLMAdapter(
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL")
        )
        tools = [CodeSearchTool(test_repo_path)]
        return CodeAgent(
            repo_path=test_repo_path,
            llm=llm,
            tools=tools
        )

    def test_simple_qa(self, agent):
        """测试简单问答"""
        result = agent.ask("这个项目是用什么语言写的？")

        assert "answer" in result
        assert len(result["answer"]) > 0
        assert result["confidence"] > 0.5
```

### 5.3 测试覆盖率目标

| 模块 | 目标覆盖率 |
|------|-----------|
| LLM 层 | 100% |
| 工具层 | 95% |
| Agent 层 | 95% |
| API 层 | 90% |
| **总体** | **≥ 95%** |

---

## 6. 部署设计

### 6.1 Docker 配置

```dockerfile
# Dockerfile
FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ripgrep \
    universal-ctags \
    tree-sitter \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6.2 环境变量

```bash
# ============================================
# LLM Configuration - 支持多厂商
# ============================================
# 厂商类型: anthropic, openai, azure, company, custom
LLM_PROVIDER=company

# Company LLM (公司中转站)
COMPANY_LLM_BASE_URL=https://your-company-gateway.com
COMPANY_LLM_API_KEY=your-api-key-here
COMPANY_LLM_MODEL=claude-sonnet-4-6

# Anthropic Claude (官方)
ANTHROPIC_API_KEY=
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_MODEL=claude-sonnet-4-6

# OpenAI / OpenAI 兼容
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4

# Azure OpenAI
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4

# ============================================
# Database Configuration - 支持多数据库
# ============================================
# 数据库类型: sqlite, mysql, postgresql, gaussdb, goldendb
DB_TYPE=sqlite

# SQLite
DB_SQLITE_PATH=./codeagent.db

# MySQL / GaussDB / GoldenDB (MySQL 协议兼容)
DB_MYSQL_HOST=localhost
DB_MYSQL_PORT=3306
DB_MYSQL_NAME=codeagent
DB_MYSQL_USER=root
DB_MYSQL_PASSWORD=

# PostgreSQL / GaussDB (PostgreSQL 协议兼容)
DB_POSTGRES_HOST=localhost
DB_POSTGRES_PORT=5432
DB_POSTGRES_NAME=codeagent
DB_POSTGRES_USER=postgres
DB_POSTGRES_PASSWORD=

# ============================================
# Agent Configuration
# ============================================
MAX_TOOL_ITERATIONS=10
API_TIMEOUT=60
AGENT_TEMPERATURE=0.7
AGENT_MAX_TOKENS=4096

# ============================================
# API Configuration
# ============================================
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=false

# ============================================
# Logging
# ============================================
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## 7. 性能优化

### 7.1 缓存策略

| 缓存类型 | 实现方式 | TTL |
|---------|---------|-----|
| 符号索引 | SQLite | 永久 |
| AST 解析 | 文件缓存 | 永久 |
| LLM 响应 | Redis (可选) | 1h |
| 搜索结果 | 内存缓存 | 5min |

### 7.2 并发处理

- 使用 asyncio 处理并发请求
- Agent 池管理（预创建实例）
- 工具执行使用线程池（IO 密集型）

---

*文档版本: v1.1*
*最后更新: 2026-03-20*
*更新内容: 新增多数据库支持和多LLM厂商支持*
