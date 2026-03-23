# CodeAgent 项目规则

## 核心原则 🎯

### 文档先行
- **任何功能实现前，必须先完成设计文档**
- 设计文档包括：接口定义、数据模型、错误处理
- 文档评审通过后才能开始编码

### 测试驱动
- 单元测试覆盖率 ≥ 95%
- 使用 TDD：红 → 绿 → 重构
- 提交前必须运行 `pytest`

## 会话启动时

每次新会话开始时，请：
1. 阅读当前的 [CHANGELOG.md](CHANGELOG.md) 了解最新进度
2. 继续上次未完成的工作
3. 完成任务后更新 CHANGELOG.md

## 进度记录

所有重要进展必须记录在 [CHANGELOG.md](CHANGELOG.md) 中：
- 新功能实现
- Bug 修复
- 设计变更
- 待解决问题

## 开发规范

- 代码规范：PEP 8 + Black 格式化
- 类型检查：mypy
- 提交前：运行 `pytest` 确保测试通过

## 技术栈

- Python 3.11+
- FastAPI
- Anthropic SDK (公司中转站)
- SQLAlchemy (多数据库支持)
- ripgrep, universal-ctags, tree-sitter

## 公司 API 配置

```bash
# 公司中转站 (Anthropic 兼容)
export ANTHROPIC_BASE_URL="https://your-company-gateway.com"
export ANTHROPIC_AUTH_TOKEN="your-api-key-here"
```

**注意**：环境变量名是 `ANTHROPIC_AUTH_TOKEN` 而非 `ANTHROPIC_API_KEY`

## 当前阶段

- **Phase 1**: 核心框架 + LLM 适配 (已完成)
- **Phase 2**: 代码探索工具集 (进行中)
- **Phase 3**: Agent 引擎 + API (待开始)
- **Phase 4**: 测试 + 文档完善 (待开始)
