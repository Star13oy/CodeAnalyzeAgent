# CodeAgent API 接口文档

## 基础信息

| 项目 | 说明 |
|------|------|
| Base URL | `http://localhost:8000` |
| API 版本 | v1 |
| 内容类型 | `application/json` |
| 认证方式 | Bearer Token (可选) |

---

## 目录

1. [代码库管理](#1-代码库管理)
2. [问答接口](#2-问答接口)
3. [排障接口](#3-排障接口)
   - 3.1 [故障诊断](#31-故障诊断)
   - 3.2 [告警分析](#32-告警分析新增)
4. [会话管理](#4-会话管理)
5. [健康检查](#5-健康检查)

---

## 1. 代码库管理

### 1.1 创建代码库

创建并索引一个新的代码库。

**请求**
```http
POST /api/v1/repos
Content-Type: application/json

{
  "id": "user-service",
  "name": "用户服务",
  "path": "/path/to/user-service"
}
```

**参数**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 代码库唯一标识 |
| name | string | 是 | 代码库名称 |
| path | string | 是 | 代码库绝对路径 |

**响应**
```json
{
  "id": "user-service",
  "name": "用户服务",
  "path": "/path/to/user-service",
  "language": "Java",
  "indexed": true,
  "file_count": 1250,
  "symbol_count": 8500,
  "created_at": "2026-03-20T10:00:00Z",
  "updated_at": "2026-03-20T10:05:00Z"
}
```

**状态码**
| 状态码 | 说明 |
|--------|------|
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 409 | 代码库 ID 已存在 |
| 500 | 服务器错误 |

---

### 1.2 获取代码库列表

获取所有代码库列表。

**请求**
```http
GET /api/v1/repos
```

**响应**
```json
{
  "repos": [
    {
      "id": "user-service",
      "name": "用户服务",
      "language": "Java",
      "indexed": true,
      "file_count": 1250,
      "created_at": "2026-03-20T10:00:00Z"
    },
    {
      "id": "order-service",
      "name": "订单服务",
      "language": "Python",
      "indexed": true,
      "file_count": 890,
      "created_at": "2026-03-19T15:30:00Z"
    }
  ],
  "total": 2
}
```

---

### 1.3 获取代码库详情

获取指定代码库的详细信息。

**请求**
```http
GET /api/v1/repos/{id}
```

**路径参数**
| 参数 | 类型 | 说明 |
|------|------|------|
| id | string | 代码库 ID |

**响应**
```json
{
  "id": "user-service",
  "name": "用户服务",
  "path": "/path/to/user-service",
  "language": "Java",
  "indexed": true,
  "file_count": 1250,
  "symbol_count": 8500,
  "languages": {
    "Java": 950,
    "JavaScript": 200,
    "SQL": 100
  },
  "last_indexed": "2026-03-20T10:05:00Z",
  "created_at": "2026-03-20T10:00:00Z",
  "updated_at": "2026-03-20T10:05:00Z"
}
```

---

### 1.4 更新代码库索引

重新索引代码库（代码有更新时使用）。

**请求**
```http
PUT /api/v1/repos/{id}
```

**响应**
```json
{
  "id": "user-service",
  "status": "indexing",
  "message": "索引更新中..."
}
```

---

### 1.5 删除代码库

删除指定代码库及其所有索引数据。

**请求**
```http
DELETE /api/v1/repos/{id}
```

**响应**
```json
{
  "message": "代码库已删除",
  "id": "user-service"
}
```

---

## 2. 问答接口

### 2.1 提问

向 Agent 提问关于代码库的问题。

**请求**
```http
POST /api/v1/repos/{id}/ask
Content-Type: application/json

{
  "question": "UserService 的认证逻辑是如何实现的？",
  "session_id": "sess_123456"
}
```

**参数**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| question | string | 是 | 用户问题 |
| session_id | string | 否 | 会话 ID，用于多轮对话 |

**响应**
```json
{
  "answer": "UserService 使用 JWT Token 进行认证。具体流程如下：\n\n1. 用户登录时，调用 authenticate() 方法验证用户名密码\n2. 验证成功后，使用 TokenValidator 生成 JWT Token\n3. Token 有效期为 24 小时，存储在 HttpOnly Cookie 中\n4. 后续请求通过 TokenValidator.validateToken() 验证 Token",
  "sources": [
    "UserService.java:42",
    "TokenValidator.java:15",
    "SecurityConfig.java:8"
  ],
  "tool_calls": [
    {
      "name": "symbol_lookup",
      "arguments": {"symbol": "authenticate"},
      "iteration": 0
    },
    {
      "name": "code_search",
      "arguments": {"query": "TokenValidator"},
      "iteration": 1
    }
  ],
  "confidence": 0.95,
  "session_id": "sess_123456",
  "tokens_used": {
    "input": 1250,
    "output": 380,
    "total": 1630
  }
}
```

**状态码**
| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 404 | 代码库不存在 |
| 400 | 问题格式错误 |

---

### 2.2 流式问答 (SSE)

流式返回 Agent 的思考过程和答案。

**请求**
```http
POST /api/v1/repos/{id}/ask/stream
Content-Type: application/json

{
  "question": "分析一下这个系统的架构",
  "session_id": "sess_123456"
}
```

**响应** (Server-Sent Events)
```
event: thinking
data: {"step": "正在搜索架构相关文件..."}

event: tool_call
data: {"tool": "code_search", "query": "architecture", "result": "找到 15 个匹配"}

event: thinking
data: {"step": "正在分析模块依赖关系..."}

event: content
data: "这个系统采用微服务架构..."

event: content
data: "主要包含以下模块..."

event: done
data: {"sources": [...], "confidence": 0.92}
```

---

## 3. 排障接口

### 3.1 故障诊断

根据错误日志和堆栈信息进行故障诊断。

**请求**
```http
POST /api/v1/repos/{id}/troubleshoot
Content-Type: application/json

{
  "error_log": "NullPointerException at UserService.java:42",
  "stack_trace": "java.lang.NullPointerException\n\tat com.example.UserService.authenticate(UserService.java:42)\n\tat com.example.AuthController.login(AuthController.java:25)",
  "context": {
    "user_id": "12345",
    "timestamp": "2026-03-20T13:30:00Z",
    "environment": "production"
  }
}
```

**参数**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| error_log | string | 是 | 错误日志 |
| stack_trace | string | 否 | 异常堆栈 |
| context | object | 否 | 上下文信息 |

**响应**
```json
{
  "diagnosis": "在 UserService.authenticate() 方法中发生空指针异常。通过代码分析，问题出在 tokenValidator 未正确初始化。",
  "root_cause": "SecurityConfig 配置中 TokenValidator 的 Bean 定义缺少 @Component 注解，导致 Spring 未能自动注入依赖。",
  "fix_suggestion": "在 TokenValidator 类上添加 @Component 注解：\n\n@Component\npublic class TokenValidator {\n    ...\n}\n\n或在 SecurityConfig 中显式定义 Bean：\n\n@Bean\npublic TokenValidator tokenValidator() {\n    return new TokenValidator();\n}",
  "related_code": [
    "UserService.java:42",
    "TokenValidator.java:1",
    "SecurityConfig.java:15"
  ],
  "similar_issues": [
    {
      "issue": "NullPointerException in UserService",
      "file": "UserService.java",
      "line": 42,
      "count": 5
    }
  ],
  "confidence": 0.92,
  "estimated_fix_time": "5分钟"
}
```

---

## 3.2 告警分析（新增）

智能分析代码告警和错误日志，提供根因定位和修复建议。

### 3.2.1 分析告警

**请求**
```http
POST /api/v1/repos/{id}/analyze-alert
Content-Type: application/json

{
  "alert_message": "KeyError: 'user_id' not found",
  "stack_trace": "Traceback (most recent call last):\n  File \"app.py\", line 42, in process_user\n    user_id = data['user_id']\nKeyError: 'user_id'",
  "context": {
    "environment": "production",
    "service": "user-service"
  }
}
```

**参数**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| alert_message | string | 是 | 告警/错误消息 |
| stack_trace | string | 否 | 堆栈跟踪 |
| context | object | 否 | 额外上下文 |

**响应**
```json
{
  "alert_id": "a1b2c3d4e5f6",
  "error_message": "KeyError: 'user_id' not found",
  "error_category": "key_error",
  "severity": "medium",
  "root_cause": "Error occurred in process_user at app.py:42. The dictionary doesn't contain the key 'user_id' you're trying to access.",
  "suggested_fix": "Use dict.get(key, default) to provide a default value, or check if the key exists with 'if key in dict'.",
  "related_files": ["app.py"],
  "stack_trace": [
    "at process_user (app.py:42)",
    "at handle_request (app.py:15)"
  ],
  "suggested_solutions": [
    {
      "problem": "KeyError: 'xxx' not found",
      "solution": "The dictionary doesn't contain the key you're trying to access. Use dict.get(key, default) to provide a default value, or check if the key exists with 'if key in dict'.",
      "tags": ["key_error", "dictionary", "python"],
      "code_example": "# Safe access\nvalue = my_dict.get(key, None)\n\n# Check before access\nif key in my_dict:\n    value = my_dict[key]"
    }
  ],
  "analyzed_at": "2026-03-24T10:00:00Z",
  "confidence": 0.92,
  "quick_diagnosis": "The dictionary doesn't contain the key you're trying to access. Suggestion: Use dict.get(key, default) to provide a default value."
}
```

**支持的语言**
- Python
- Java
- JavaScript / TypeScript
- Go
- Rust
- C/C++
- Ruby
- PHP

**错误分类**
| 类别 | 说明 | 严重级别 |
|------|------|----------|
| null_pointer | 空指针/None 访问 | high |
| type_error | 类型不匹配 | medium |
| file_not_found | 文件未找到 | medium |
| permission_denied | 权限拒绝 | high |
| timeout | 超时 | medium |
| connection_error | 连接错误 | high |
| out_of_memory | 内存溢出 | critical |
| index_error | 索引越界 | high |
| key_error | 键不存在 | medium |
| import_error | 模块导入失败 | medium |
| syntax_error | 语法错误 | high |
| database | 数据库错误 | high |

---

## 4. 会话管理

### 4.1 创建会话

创建一个新的对话会话。

**请求**
```http
POST /api/v1/repos/{id}/sessions
```

**响应**
```json
{
  "session_id": "sess_abc123",
  "repo_id": "user-service",
  "created_at": "2026-03-20T13:00:00Z",
  "message_count": 0
}
```

---

### 4.2 获取会话历史

获取指定会话的所有对话历史。

**请求**
```http
GET /api/v1/repos/{id}/sessions/{session_id}
```

**响应**
```json
{
  "session_id": "sess_abc123",
  "repo_id": "user-service",
  "created_at": "2026-03-20T13:00:00Z",
  "messages": [
    {
      "role": "user",
      "content": "认证逻辑是怎么实现的？",
      "timestamp": "2026-03-20T13:00:05Z"
    },
    {
      "role": "assistant",
      "content": "UserService 使用 JWT Token...",
      "timestamp": "2026-03-20T13:00:08Z",
      "sources": ["UserService.java:42"]
    },
    {
      "role": "user",
      "content": "Token 过期了怎么办？",
      "timestamp": "2026-03-20T13:00:15Z"
    },
    {
      "role": "assistant",
      "content": "Token 过期后会自动刷新...",
      "timestamp": "2026-03-20T13:00:18Z",
      "sources": ["TokenRefresher.java:20"]
    }
  ],
  "message_count": 4
}
```

---

### 4.3 删除会话

删除指定会话。

**请求**
```http
DELETE /api/v1/repos/{id}/sessions/{session_id}
```

**响应**
```json
{
  "message": "会话已删除",
  "session_id": "sess_abc123"
}
```

---

## 5. 健康检查

### 5.1 健康检查

检查服务健康状态。

**请求**
```http
GET /health
```

**响应**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 3600,
  "components": {
    "database": "healthy",
    "llm": "healthy",
    "indexer": "healthy"
  }
}
```

---

### 5.2 指标 (可选)

获取服务指标。

**请求**
```http
GET /metrics
```

**响应**
```json
{
  "requests_total": 15234,
  "requests_success": 14890,
  "requests_error": 344,
  "avg_response_time_ms": 245,
  "active_sessions": 45,
  "indexed_repos": 12,
  "llm_tokens_total": 5245000
}
```

---

## 错误响应格式

所有错误响应遵循统一格式：

```json
{
  "error": {
    "code": "REPO_NOT_FOUND",
    "message": "代码库不存在",
    "details": {
      "repo_id": "unknown-repo"
    }
  }
}
```

**常见错误码**
| 错误码 | HTTP 状态 | 说明 |
|--------|----------|------|
| REPO_NOT_FOUND | 404 | 代码库不存在 |
| INVALID_REQUEST | 400 | 请求参数错误 |
| INDEX_FAILED | 500 | 索引创建失败 |
| LLM_ERROR | 500 | LLM 调用失败 |
| SESSION_EXPIRED | 404 | 会话不存在或已过期 |

---

## 认证 (可选)

如果启用认证，需要在请求头中携带 Token：

```http
Authorization: Bearer YOUR_API_TOKEN
```

---

## SDK 使用示例

### Python SDK

```python
from codeagent import CodeAgentClient

# 初始化客户端
client = CodeAgentClient(
    base_url="http://localhost:8000",
    api_token="your-token"
)

# 创建代码库
repo = client.create_repo(
    id="user-service",
    name="用户服务",
    path="/path/to/code"
)

# 提问
answer = client.ask(
    repo_id="user-service",
    question="认证逻辑是如何实现的？"
)
print(answer.answer)

# 排障
diagnosis = client.troubleshoot(
    repo_id="user-service",
    error_log="NullPointerException at UserService.java:42"
)
print(diagnosis.fix_suggestion)
```

### JavaScript SDK

```javascript
const { CodeAgentClient } = require('@codeagent/sdk');

const client = new CodeAgentClient({
  baseUrl: 'http://localhost:8000',
  apiToken: 'your-token'
});

// 提问
const answer = await client.ask('user-service', '认证逻辑是如何实现的？');
console.log(answer.answer);

// 排障
const diagnosis = await client.troubleshoot('user-service', {
  errorLog: 'NullPointerException at UserService.java:42'
});
console.log(diagnosis.fixSuggestion);
```

---

*文档版本: v1.0*
*最后更新: 2026-03-20*
