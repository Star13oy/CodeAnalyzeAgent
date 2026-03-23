# CodeAgent

> 智能代码助手 - 基于 Claude 的 Agentic Code Analysis System

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📋 项目简介

**CodeAgent** 是一个基于 **Agentic Tool Use** 的智能代码助手服务，能够主动探索代码仓库并回答开发者的代码相关问题。

### 核心特性

- 🔍 **主动探索**：Agent 自主规划代码探索路径，而非被动检索
- 📖 **精确理解**：直接阅读代码而非依赖向量相似度
- 🔄 **多轮对话**：支持上下文理解的对话系统
- 🌐 **多LLM支持**：Anthropic、OpenAI、Azure、自定义网关
- 💾 **多数据库支持**：SQLite、MySQL、PostgreSQL、GaussDB、GoldenDB
- 📡 **实时进度**：SSE 流式响应，实时显示分析进度

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/Star13oy/CodeAnalyzeAgent.git
cd CodeAnalyzeAgent
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制配置模板并编辑：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置 LLM API：

```bash
# 使用 Anthropic Claude
ANTHROPIC_API_KEY=your_anthropic_api_key
LLM_PROVIDER=anthropic

# 或使用 OpenAI
# OPENAI_API_KEY=your_openai_api_key
# LLM_PROVIDER=openai

# 或使用兼容 Anthropic 的自定义网关
# COMPANY_LLM_API_KEY=your_api_key
# COMPANY_LLM_BASE_URL=https://your-api-gateway.com
# LLM_PROVIDER=company
```

### 4. 启动服务

```bash
# 启动后端 API
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# 或使用 reload 模式（开发）
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. 访问界面

- **API 文档**: http://localhost:8000/docs
- **Web 界面**: 打开 `frontend/index.html`

## 🐳 Docker 部署

```bash
# 基础部署
docker-compose up -d

# 使用 PostgreSQL
docker-compose --profile postgres up -d

# 使用 MySQL
docker-compose --profile mysql up -d
```

## 📖 使用示例

### Python SDK

```python
from codeagent import CodeAgent
from codeagent.llm import AnthropicAdapter

# 初始化 Agent
agent = CodeAgent(
    repo_path="/path/to/your/code",
    llm=AnthropicAdapter(api_key="your_api_key"),
)

# 提问
result = agent.ask("这个项目是做什么的？")
print(result.answer)
print(result.sources)
```

### REST API

```bash
# 注册代码库
curl -X POST "http://localhost:8000/api/v1/repos" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "my-project",
    "name": "My Project",
    "path": "/path/to/code"
  }'

# 智能问答
curl -X POST "http://localhost:8000/api/v1/repos/my-project/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "用户认证是如何实现的？"
  }'
```

### 流式响应（SSE）

```bash
curl -N -X POST "http://localhost:8000/api/v1/repos/my-project/ask/stream" \
  -H "Content-Type: application/json" \
  -d '{"question": "介绍一下这个项目"}'
```

## 🏗️ 项目架构

```
CodeAgent/
├── src/
│   ├── agent/           # Agent 引擎层
│   │   ├── core.py      # 核心 Agent 实现（Agentic Loop）
│   │   └── session.py   # 会话管理
│   ├── llm/             # LLM 抽象层
│   │   ├── base.py      # 基础接口
│   │   ├── factory.py   # LLM 工厂
│   │   └── *_adapter.py # 各厂商适配器
│   ├── tools/           # 代码探索工具
│   │   ├── code_search.py    # ripgrep 搜索
│   │   ├── file_reader.py    # 文件读取
│   │   ├── symbol_lookup.py  # 符号查找
│   │   └── file_finder.py    # 文件查找
│   ├── db/              # 数据库层
│   ├── services/        # 业务服务层
│   ├── schemas/         # 数据模型
│   └── api/             # FastAPI 应用
├── frontend/            # Web 界面
├── tests/               # 测试套件
└── docs/                # 项目文档
```

## 🔧 配置说明

### LLM 配置

| Provider | 说明 |
|----------|------|
| `anthropic` | Anthropic Claude API |
| `openai` | OpenAI GPT API |
| `azure` | Azure OpenAI |
| `company` | 公司中转站（兼容 Anthropic） |
| `custom` | 自定义 HTTP 端点 |

### 数据库配置

| 类型 | 说明 |
|------|------|
| `sqlite` | 本地 SQLite（默认） |
| `mysql` | MySQL / MariaDB |
| `postgresql` | PostgreSQL |
| `gaussdb_mysql` | GaussDB（MySQL 协议） |
| `goldendb` | GoldenDB |

### Agent 配置

```bash
# 最大工具调用迭代次数
MAX_TOOL_ITERATIONS=15

# Agent 温度（0-1，越高越随机）
AGENT_TEMPERATURE=0.7

# 每次响应最大 token 数
AGENT_MAX_TOKENS=4096
```

## 📊 技术栈

- **语言**: Python 3.11+
- **Web 框架**: FastAPI
- **AI/LLM**: Anthropic Claude API (Tool Use)
- **数据库**: SQLAlchemy ORM
- **代码分析**: ripgrep, universal-ctags
- **测试**: pytest

## 🧪 运行测试

```bash
# 运行所有测试
pytest

# 运行单元测试
pytest tests/unit/

# 查看覆盖率
pytest --cov=src --cov-report=html

# 运行特定测试
pytest tests/unit/test_agent.py -v
```

## 📝 API 文档

启动服务后访问 http://localhost:8000/docs 查看完整 API 文档。

### 核心端点

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/v1/repos` | 注册代码库 |
| GET | `/api/v1/repos` | 列出代码库 |
| DELETE | `/api/v1/repos/{id}` | 删除代码库 |
| POST | `/api/v1/repos/{id}/ask` | 智能问答 |
| POST | `/api/v1/repos/{id}/ask/stream` | 流式问答（SSE） |
| GET | `/api/v1/sessions` | 列出会话 |
| GET | `/health` | 健康检查 |

## 🔐 安全说明

- **不要提交** `.env` 文件到版本控制
- **不要在日志中** 打印 API 密钥
- 生产环境建议使用 **环境变量** 或 **密钥管理服务**
- API 建议配置 **认证中间件**

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 🔗 相关链接

- [Anthropic Claude API](https://docs.anthropic.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [ripgrep](https://github.com/BurntSushi/ripgrep)
