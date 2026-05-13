# AI Dev Team Plugin

一个运行在 Claude Code 中的完整 AI 开发团队 — 33人软件组织，自主协作从需求到交付。

**当前版本**: v0.3.0

## 理念

传统的 AI 辅助开发是 "单人 + AI 助手" 模式。AI Dev Team 将模式切换为 "人类干系人 + 完整 AI 团队" — 你来提需求和接受交付，CTO、PM、架构师、TL、工程师、设计师、DevOps、审查员团队自主组织执行。

## 团队规模（33人）

| 角色 | 人数 | 说明 |
|------|------|------|
| CTO | 1 | 技术决策、资源调配 |
| Architect | 1 | 技术标准、架构治理、ADR |
| PM | 3 | 产品需求分析（AI/ML、IoT、App&Web） |
| Tech Lead | 3 | 技术方案、任务分解 |
| Senior Engineer | 12 | 主要开发力量 |
| Domain Engineer | 6 | ML、IoT、Agent 专业工程师 |
| Designer | 4 | UI/UX 设计（内置 Figma MCP） |
| DevOps/SRE | 2 | CI/CD、基础设施 |
| Market Manager | 1 | 市场分析、竞品情报 |
| Reviewer R1/R2/R3 | 3 | 独立评审（架构、产品、工程） |

## 插件能力

- **9 个 Slash 命令**（`/cto` `/pm` `/tech-lead` `/designer` `/review` `/dashboard` `/project` `/market` `/devops` / `/architect`）
- **10 个 Agent 角色**（含 3 个独立 Reviewer，并行运行）
- **27 个 MCP 工具**（项目管理、任务、评审、Sprint、会议、知识库、报表、交接、Git）
- **4 阶段门禁评审**（DG1-DG4，3人独立投票，≥2/3 通过）
- **自动化 DevOps**（CI/CD 模板生成）
- **Figma MCP 集成**（Designer 直接操作 Figma）
- **Git 版本控制**（MCP 工具封装的分支/提交/合并）
- **文件锁并发保护**（fcntl flock + 文件冲突检测）
- **数据双写**（.index.json 主数据 + .md 文件兼容）

## 快速开始

```bash
# 安装 Python 依赖
pip install -r mcp-server/requirements.txt

# 测试插件
claude --plugin-dir .

# 永久安装
claude mcp add ai-dev-team --plugin .
```

## 项目结构

```
├── agents/           # 10 个 Agent 定义（含 Reviewer R1/R2/R3）
├── skills/           # 10 个 Slash Command 定义
├── mcp-server/       # MCP Server（27 个工具）
├── config/           # 模型配置、技术标准
├── scripts/          # 分析、报表、同步、初始化工具
├── templates/        # PRD、技术方案、测试计划模板
├── docs/             # 组织架构、角色、流程、评审文档
├── design-system/    # 设计 Token
├── hooks/            # 质量门禁、自动采集
├── monitors/         # Dashboard 刷新、截止日期跟踪
└── tests/            # 单元测试
```

## 模型配置

编辑 `config/models.json` 为各角色分配模型，然后运行：

```bash
python3 scripts/sync-models.py            # 同步到 agents/
python3 scripts/sync-models.py --dry-run  # 预览变更
```

可选模型：`opus`（最强推理）、`sonnet`（性价比）、`haiku`（最快）、`inherit`（继承调用方）

## 开发工作流

1. 干系人提交需求 → CTO 创建项目（模板自动初始化）
2. PM 填写 PRD → 架构师审核技术选型
3. TL 设计技术方案 → 架构师 DG1 预审 → 任务分解 → 分配工程师
4. 工程师：`git_create_branch` → 实现 → `git_commit` → TL `git_merge_branch`
5. DG1-DG4 阶段门禁 → 3 个独立 Reviewer 并行评审
6. 分析自动追踪进度、质量、周期时间，异常预警
7. 日报、周报自动生成
8. 全部门禁通过 → 干系人验收

## 干系人常用命令

| 命令 | 用途 |
|------|------|
| `/dashboard company` | 全局项目视图 |
| `/dashboard project <name>` | 单项目详情 + 评审状态 |
| `/project new <name>` | 提交需求 → 自动初始化模板 |
| `/review <project> <gate>` | 触发独立 3 人评审 |
| `/cto <directive>` | 直接 CTO 技术决策 |

## 产品方向

- ML 算法
- IoT 应用
- Agent/知识库
- App & Web

## License

MIT
