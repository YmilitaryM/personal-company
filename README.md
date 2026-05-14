# AI Dev Team Plugin

运行在 Claude Code 中的完整 AI 开发团队 —— 多 Agent 软件组织，自主协作从需求到交付。

**当前版本**: v0.3.0

## 理念

传统 AI 辅助开发是「单人 + AI 助手」模式。AI Dev Team 切换为「人类干系人 + 完整 AI 团队」—— 你提需求和接受交付，CTO、PM、架构师、TL、工程师、设计师、DevOps、审查员团队自主组织执行。

## 安装

### 前提条件

- **Claude Code** v2.0+（`claude --version` 验证）
- **Python 3.12+**（MCP Server 运行需要）- [下载](https://www.python.org/downloads/)
- **Git**（版本控制工具需要）

```bash
# 确认版本
claude --version   # ≥ 2.0.0
python3.14 --version
git --version
```

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/YmilitaryM/personal-company.git ~/ai-dev-team
cd ~/ai-dev-team

# 2. 安装 Python 依赖
pip install -r mcp-server/requirements.txt

# 3. 验证 MCP Server 能启动
python3.14 -c "from mcp.server import Server; print('MCP OK')"
```

### 加载插件

**方式一：临时加载（推荐测试用）**

```bash
claude --plugin-dir ~/ai-dev-team
```

**方式二：永久安装（所有会话生效）**

```bash
claude plugin install --scope user ~/ai-dev-team
```

> **注意**：如果你没有 python3.14，请在 `.mcp.json` 中将 `command` 改成你的 python 路径，并确保该 python 安装了 `mcp` 包。

### 验证安装

进入 Claude Code 后，输入 `/` 查看可用命令列表，应该能看到：

```
/cto           → CTO 技术决策
/pm            → 产品需求分析
/tech-lead     → 技术方案设计
/architect     → 架构治理
/designer      → UI/UX 设计
/review        → 3轮辩论式评审
/dashboard     → 多层仪表盘
/project       → 项目管理
/pipeline      → 全流程自动化
/market        → 市场情报
/devops        → CI/CD 管道
/tdd           → 测试驱动开发
```

或者直接执行 `/dashboard company` 测试。

## 使用指南

### 干系人命令（你最常用的 6 个）

| 命令 | 用途 | 示例 |
|------|------|------|
| `/pipeline start <name>` | **一键全流程自动化**：立项→调研→PRD→架构→CTO审批→方案→开发→评审→交付 | `/pipeline start my-app` |
| `/dashboard company` | 全公司项目总览：进度、状态、风险 | `/dashboard company` |
| `/dashboard project <name>` | 单项目详情：任务、评审、阻塞 | `/dashboard project my-app` |
| `/project new <name>` | 提交新需求，自动创建全套模板 | `/project new smart-factory` |
| `/review <project> <gate>` | 触发 3人辩论式评审（DG1~DG4），含CTO僵局仲裁 | `/review my-app DG1` |
| `/cto <directive>` | CTO：立项审批、架构审批、资源调配、僵局仲裁、交付签署 | `/cto 评估用Rust重写数据管道` |

> **使用优先级**：新项目直接用 `/pipeline start` 一键跑完9阶段全流程；已有项目调用单独的角色命令。管道中断后 `/pipeline resume` 从断点继续。所有管理决策自动记录在 `.pipeline-state.json` 的 `decisions` 数组中，形成完整决策追溯链。 |

### 角色命令（按需调用）

| 命令 | 谁 | 做什么 |
|------|----|--------|
| `/pipeline start <name>` | 流水线编排器 | 一键从立项跑完 9 阶段到交付 |
| `/pipeline resume <name>` | 流水线编排器 | 从断点恢复中断的流水线 |
| `/pipeline status <name>` | 流水线编排器 | 查看流水线当前进度 |
| `/pm <direction>` | 产品经理 | 需求分析、PRD 撰写 |
| `/architect review` | 架构师 | 技术标准治理、架构评审 |
| `/tech-lead <project>` | Tech Lead | 组建团队、技术方案、任务分配、代码审查 |
| `/designer ui <project>` | 设计师 | UI/UX 设计（内置 Figma MCP 直接画图） |
| `/devops ci <project>` | DevOps | CI/CD 流水线生成 |
| `/tdd <task>` | TDD 工程师 | Red-Green-Refactor 测试驱动开发（基于现有工程师） |
| `/market <topic>` | 市场经理 | 市场分析、竞品情报 |
| `/tdd <task>` | TDD 工程师 | 测试驱动开发（Red-Green-Refactor） |

### 模型配置

编辑 `config/models.json` 可为每个角色分配不同智能等级：

```json
{
  "roles": {
    "cto": "opus",
    "architect": "opus",
    "reviewer-r1": "opus",
    "senior-engineer": "inherit",
    ...
  }
}
```

可选模型：

- **内置模型**：`opus`（最强推理）、`sonnet`（性价比）、`haiku`（最快）、`inherit`（继承调用方）
- **自定义模型**：直接填写任意模型 ID，例如 `claude-opus-4-7`、`deepseek-v4-pro` 等。sync 脚本会原样写入 agent 定义，不做限制。

改完后同步到 agent 定义：

```bash
python3.14 scripts/sync-models.py            # 应用
python3.14 scripts/sync-models.py --dry-run  # 预览
```

### 第三方模型配置（DeepSeek / OpenAI 等）

1. 复制并编辑 API key：`cp config/.env.example .env`
2. 编辑 `config/litellm.yaml` 增删模型
3. 启动网关：`bash scripts/start.sh`
4. 打开 `http://localhost:8080/config` 为每个角色分配模型
5. 启动 Claude Code：`ANTHROPIC_BASE_URL=http://localhost:4000 claude --plugin-dir ~/ai-dev-team`

网关会根据模型名自动路由到不同后端。以下是直接使用环境变量的方式（不用网关）：

Claude Code 支持通过 `ANTHROPIC_BASE_URL` 路由到任何 Anthropic 兼容的后端：

```bash
# DeepSeek（原生支持 Anthropic 格式）
export ANTHROPIC_BASE_URL="https://api.deepseek.com/anthropic"
export ANTHROPIC_API_KEY="sk-your-deepseek-key"
claude --plugin-dir ~/ai-dev-team
```

```bash
# OpenRouter（290+ 模型，Bearer token 认证）
export ANTHROPIC_BASE_URL="https://openrouter.ai/api"
export ANTHROPIC_AUTH_TOKEN="sk-or-your-key"
export ANTHROPIC_DEFAULT_OPUS_MODEL="anthropic/claude-opus-4-7"
export ANTHROPIC_DEFAULT_SONNET_MODEL="deepseek/deepseek-v4-pro"
export ANTHROPIC_DEFAULT_HAIKU_MODEL="qwen/qwen3-coder"
claude --plugin-dir ~/ai-dev-team
```

```bash
# LiteLLM 本地网关（兼容性最好，推荐生产使用）
export ANTHROPIC_BASE_URL="http://localhost:4000"
export ANTHROPIC_AUTH_TOKEN="sk-litellm-key"
claude --plugin-dir ~/ai-dev-team
```

**方式二：OpenAI 兼容模式**

```bash
# OpenAI
export CLAUDE_CODE_USE_OPENAI=1
export OPENAI_API_KEY="sk-your-openai-key"
export OPENAI_MODEL="gpt-4o"
claude --plugin-dir ~/ai-dev-team

# DeepSeek（OpenAI 格式）
export CLAUDE_CODE_USE_OPENAI=1
export OPENAI_API_KEY="sk-your-deepseek-key"
export OPENAI_BASE_URL="https://api.deepseek.com/v1"
export OPENAI_MODEL="deepseek-chat"
claude --plugin-dir ~/ai-dev-team
```

**在 `models.json` 中对应使用**：

```json
{
  "roles": {
    "cto":            "claude-opus-4-7",
    "reviewer-r1":    "claude-opus-4-7",
    "reviewer-r2":    "deepseek-chat",
    "reviewer-r3":    "qwen3-coder",
    "senior-engineer": "inherit"
  }
}
```

> **重要提示**：
> - **MCP 工具**和视觉/图片输入依赖 Anthropic 原生 streaming tool-call 协议，第三方后端可能不完全支持。LiteLLM 是目前兼容性最好的网关方案
> - `ANTHROPIC_API_KEY` 发 `x-api-key` header，`ANTHROPIC_AUTH_TOKEN` 发 `Authorization: Bearer` header，用错会导致认证失败
> - DeepSeek 成本约为 Anthropic 的 1/17（$0.44 vs $3/M input tokens）
python3.14 scripts/sync-models.py --dry-run  # 预览
```

### 一键自动化流水线

`/pipeline start <project>` 运行完整 9 阶段流程，无需人工介入：

```
Phase 0: 立项       — CTO 创建项目、分配 PM、记录立项决策
Phase 1: 市场调研    — Market Manager 市场分析、竞品矩阵、差异化策略
Phase 2: 需求       — PM 基于市场调研撰写 PRD
Phase 3: 架构       — Architect 对照 tech-standards.json 评审
Phase 3.5: CTO审批  — CTO 审批架构方案（批准/有条件批准/驳回），记录决策
Phase 4: 方案       — Tech Lead 组建团队、技术方案设计、任务分解与分配
Phase 5: 开发       — TL 驱动开发循环：分配任务→工程师实现→后台代码审查→合并
Phase 6: 质量       — DG1→DG2→DG3→DG4 门禁评审（3轮辩论+CTO僵局仲裁）
Phase 7: 交付       — CTO 最终签署、交付报告、干系人验收
```

- `/pipeline resume <project>` — 中断后从断点恢复
- `/pipeline status <project>` — 查看流水线进度
- `/pipeline cancel <project>` — 取消流水线

流水线状态保存在 `projects/<name>/.pipeline-state.json`，包含完整的 **决策追溯链**（每个管理决策记录上下文、备选方案、理由、接受的风险、可逆性、结果验证计划）。

### 一键启动所有服务

```bash
bash scripts/start.sh
```

自动启动两个服务：

| 服务 | 地址 | 用途 |
|------|------|------|
| Web Dashboard | `http://localhost:8080` | 项目监控、进度、评审 |
| 模型配置页 | `http://localhost:8080/config` | 可视化配置每角色用哪个模型 |
| Model Gateway | `http://localhost:4000` | 多模型路由（DeepSeek/OpenAI/Anthropic） |

然后启动 Claude Code：

```bash
ANTHROPIC_BASE_URL=http://localhost:4000 claude --plugin-dir ~/ai-dev-team
```

> Ctrl+C 一键停止所有服务。

### Web Dashboard 视图

- **公司视图** — 所有项目卡片、进度条、评审状态、活跃流水线
- **部门视图** — AI/ML、IoT、App&Web 分类查看
- **项目视图** — 点击进入详情：任务面板、评审门禁、流水线阶段
- **自动刷新** — 每 30 秒拉取最新数据，无需手动刷新

### CTO 与 Tech Lead 的管理职责

**CTO**（公司级资源调配者和最终技术仲裁者）：
- **立项审批**：评估战略契合度、资源可用性、风险，记录审批决策
- **架构审批**（Phase 3.5）：批准/有条件批准/驳回架构方案
- **僵局仲裁**：当3位评审员出现 1:1:1 僵局时，按Gate类型加权做出绑定裁决
- **交付签署**：验证所有门禁通过、所有任务完成、所有风险检查后签署交付
- **不直接分配人员** — 这是 TL 的职责

**Tech Lead**（管理者-工程师混合体）：
- **组建团队**：查询资源池，按技能匹配选择工程师，记录团队组建决策
- **后台代码审查**：工程师提交代码后异步审查（检查AC覆盖率、测试≥80%、技术标准合规），不阻塞下一位工程师
- **进度监控**：Sprint燃尽、速率计算、瓶颈检测
- **内部预审**：DG2前自我评估（信心点、不确定点、已知问题）
- **任务状态流转**：todo → assigned → in_progress → submitted → reviewed_pass/reviewed_fail

详细决策记录格式见 `skills/pipeline/SKILL.md` 中的 Decision Record Schema。

### 手动工作流

如果需要精细控制每个阶段：

1. 干系人提交需求 → CTO 创建项目、记录立项决策
2. Market Manager 市场调研竞品分析 → PM 基于调研填写 PRD
3. 架构师审核技术选型 → CTO 审批架构方案（批准/有条件批准/驳回）
4. TL 组建团队 → 技术方案设计 → 任务分解 → 分配工程师
5. 工程师：`git_create_branch` → 实现 → `git_commit` → TL 后台代码审查 → `git_merge_branch`
6. DG1-DG4 阶段门禁 → 3人并行评审 → 交叉辩论 → 合议裁决（僵局时CTO仲裁）
7. 分析自动追踪进度、质量、周期时间，异常预警
8. 日报、周报自动生成
9. 全部门禁通过 → CTO 签署交付 → 干系人验收

### 4 阶段门禁评审（3轮辩论式）

```
DG1 (方案设计完成)  → ≥6.0/10  架构、UX、任务分解
DG2 (核心开发完成)  → ≥7.0/10  代码质量、设计还原、测试
DG3 (质量保证完成)  → ≥7.5/10  性能、安全、Bug率
DG4 (待交付)       → ≥8.0/10  部署、文档、验收标准
```

**3轮评审流程**：

1. **Round 1 — 独立评审**：R1（架构）/ R2（产品）/ R3（工程）并行隔离评审所有方面（"Lens, Not Boundary"）
2. **Round 2 — 交叉辩论**：审查者互相挑战发现、识别冲突、让步或辩护、修订分数
3. **Round 3 — 合议裁决**：综合共识与分歧，≥2 approve → PASS，1:1:1僵局 → **CTO仲裁**（根据Gate类型加权偏向：DG1→R1, DG2→R3, DG3→R3, DG4→R2）

完整评分细则见 `docs/review-rubric.md`，评审记录模板见 `docs/review-template.md`。

## Agent 角色

| 角色 | 模型 | 职责 |
|------|------|------|
| CTO | opus | 立项审批、资源调配、架构审批、僵局仲裁、交付签署 |
| Architect | opus | 技术标准、架构治理 |
| PM | opus | 产品需求（AI/ML、IoT、App&Web） |
| Tech Lead | opus | 组建团队、任务分配、后台代码审查、进度监控、预审 |
| Senior Engineer | inherit | 主力开发 |
| Domain Engineer | inherit | ML、IoT、Agent 专家 |
| Designer | opus | UI/UX 设计（Figma MCP） |
| DevOps/SRE | inherit | CI/CD、基础设施 |
| Market Manager | inherit | 市场分析、竞品情报 |
| Reviewer R1/R2/R3 | opus | 独立评审（并行隔离运行） |

## 插件能力一览

- **12 个 Slash 命令** — 按角色调用 + 全流程自动流水线 + TDD
- **11 个 Agent 角色** — 含 3 个独立 Reviewer（context: fork 并行）
- **19 个 MCP 工具** — 项目/任务/评审/知识库/报表/Git
- **9 阶段自动流水线** — 一键 `/pipeline start` 从立项到交付，支持断点恢复、决策追溯链
- **Web Dashboard** — 浏览器实时监控，公司/部门/项目三级视图，30s 自动刷新
- **4 阶段门禁评审** — DG1-DG4，3轮辩论式（独立评审→交叉辩论→合议裁决），僵局时CTO仲裁
- **市场调研集成** — Market Manager 竞品分析、市场定位，PRD 数据驱动
- **Figma MCP 集成** — Designer 直接操作 Figma 画 UI
- **Git 版本控制** — 分支/提交/合并，MCP 工具封装
- **文件锁并发保护** — fcntl flock + 文件冲突检测
- **数据双写** — .index.json 主数据 + .md 文件可读
- **自动化分析** — 进度追踪、质量指标、预测预警、日报周报

## 项目结构

```
├── .claude-plugin/    # 插件清单（plugin.json）
├── skills/            # 11 个 Slash Command 定义（含 pipeline）
├── agents/            # 11 个 Agent 角色定义
├── mcp-server/        # MCP Server — 27 个工具
│   ├── server.py      # 核心 12 工具 + 入口
│   ├── extended.py    # 扩展 15 工具（Sprint/会议/Git/交接）
│   └── requirements.txt
├── config/
│   ├── models.json    # 每角色模型配置
│   └── tech-standards.json  # 公司技术标准
├── scripts/           # 分析、报表、同步、项目初始化、Web Dashboard
│   ├── web_dashboard.py   # Web 实时 Dashboard 服务器
│   ├── collect-dashboard.py # Dashboard 数据采集
│   └── ...
├── templates/         # PRD、技术方案、测试计划模板
├── docs/              # 组织架构、角色、流程、评审文档
├── design-system/     # 设计 Token
├── hooks/             # 质量门禁、自动采集
├── monitors/          # Dashboard 刷新、截止日期跟踪
├── tests/             # 单元测试（25 tests）
├── .mcp.json          # MCP Server 注册
└── .gitignore
```

## 产品方向

- ML 算法
- IoT 应用
- Agent / 知识库
- App & Web

## 故障排查

**"Unknown command: /dashboard"**

1. 确认你在别的目录下运行（不要在插件目录内）
2. 确认 `git pull` 已拉取最新代码
3. 确认 `.mcp.json` 中 Python 路径存在：`which python3.14`
4. 确认 mcp 包已安装：`python3.14 -c "import mcp; print('OK')"`

**MCP Server 启动失败**

```bash
# 手动测试 server 能否启动
python3.14 mcp-server/server.py
# 如果不报错直接挂起就说明正常。Ctrl+C 退出。
```

**Python 版本问题**

如果你的 python 不是 3.14，有两种办法：
- 安装 python 3.14：`brew install python@3.14`
- 修改 `.mcp.json` 的 `command` 和 `.claude/settings.local.json` 的 bash 权限为你自己的 python 路径

**Web Dashboard 无法访问**

```bash
# 直接用一键脚本启动所有服务
bash scripts/start.sh
# 如果端口被占用，设置环境变量换端口
WEB_PORT=9090 GATEWAY_PORT=4001 bash scripts/start.sh
```

**流水线中断后无法恢复**

```bash
# 查看流水线状态文件
cat projects/<name>/.pipeline-state.json
# 手动修复后重新标记阶段为 done，然后 resume
```

## License

MIT
