# AI Dev Team Plugin

运行在 Claude Code 中的完整 AI 开发团队 —— 33人软件组织，自主协作从需求到交付。

**当前版本**: v0.3.0

## 理念

传统 AI 辅助开发是「单人 + AI 助手」模式。AI Dev Team 切换为「人类干系人 + 完整 AI 团队」—— 你提需求和接受交付，CTO、PM、架构师、TL、工程师、设计师、DevOps、审查员团队自主组织执行。

## 安装

### 前提条件

- **Claude Code** v2.0+（`claude --version` 验证）
- **Python 3.14**（MCP Server 运行需要）- [下载](https://www.python.org/downloads/)
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
/review        → 3人独立评审
/dashboard     → 多层仪表盘
/project       → 项目管理
/pipeline      → 全流程自动化
/market        → 市场情报
/devops        → CI/CD 管道
```

或者直接执行 `/dashboard company` 测试。

## 使用指南

### 干系人命令（你最常用的 6 个）

| 命令 | 用途 | 示例 |
|------|------|------|
| `/pipeline start <name>` | **一键全流程自动化**：市场调研→PRD→架构→开发→评审→交付 | `/pipeline start my-app` |
| `/dashboard company` | 全公司项目总览：进度、状态、风险 | `/dashboard company` |
| `/dashboard project <name>` | 单项目详情：任务、评审、阻塞 | `/dashboard project my-app` |
| `/project new <name>` | 提交新需求，自动创建全套模板 | `/project new smart-factory` |
| `/review <project> <gate>` | 触发 3 人独立评审（DG1~DG4） | `/review my-app DG1` |
| `/cto <directive>` | 直接向 CTO 下达技术决策 | `/cto 评估用Rust重写数据管道` |

> **使用优先级**：新项目直接用 `/pipeline start` 一键跑完全流程；已有项目调用单独的角色命令。管道中断后 `/pipeline resume` 从断点继续。 |

### 角色命令（按需调用）

| 命令 | 谁 | 做什么 |
|------|----|--------|
| `/pipeline start <name>` | 流水线编排器 | 一键从立项跑完 7 阶段到交付 |
| `/pipeline resume <name>` | 流水线编排器 | 从断点恢复中断的流水线 |
| `/pipeline status <name>` | 流水线编排器 | 查看流水线当前进度 |
| `/pm <direction>` | 产品经理 | 需求分析、PRD 撰写 |
| `/architect review` | 架构师 | 技术标准治理、架构评审 |
| `/tech-lead <project>` | Tech Lead | 技术方案设计、任务分解 |
| `/designer ui <project>` | 设计师 | UI/UX 设计（内置 Figma MCP 直接画图） |
| `/devops ci <project>` | DevOps | CI/CD 流水线生成 |
| `/market <topic>` | 市场经理 | 市场分析、竞品情报 |

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

可选模型：`opus`（最强推理）、`sonnet`（性价比）、`haiku`（最快）、`inherit`（继承调用方）

改完后同步到 agent 定义：

```bash
python3.14 scripts/sync-models.py            # 应用
python3.14 scripts/sync-models.py --dry-run  # 预览
```

### 一键自动化流水线

`/pipeline start <project>` 运行完整 7 阶段流程，无需人工介入：

```
Phase 0: 立项      — CTO 创建项目、分配 PM、确定产品方向
Phase 1: 市场调研   — Market Manager 市场分析、竞品矩阵、差异化策略
Phase 2: 需求      — PM 基于市场调研撰写 PRD
Phase 3: 架构      — Architect 对照技术标准评审
Phase 4: 方案      — Tech Lead 技术方案设计、任务分解
Phase 5: 开发      — Senior Engineer 逐任务实现（Git 分支→提交→合并）
Phase 6: 质量      — DG1→DG2→DG3→DG4 门禁评审（每阶段 3 人独立投票）
Phase 7: 交付      — 生成交付报告，干系人验收
```

- `/pipeline resume <project>` — 中断后从断点恢复
- `/pipeline status <project>` — 查看流水线进度
- `/pipeline cancel <project>` — 取消流水线

### Web Dashboard 实时监控

在浏览器中实时查看所有项目状态：

```bash
python3 scripts/web_dashboard.py --port 8080
# 打开 http://localhost:8080
```

- **公司视图** — 所有项目卡片、进度条、评审状态、活跃流水线
- **部门视图** — AI/ML、IoT、App&Web 分类查看
- **项目视图** — 点击进入详情：任务面板、评审门禁、流水线阶段
- **自动刷新** — 每 30 秒拉取最新数据，无需手动刷新
- **零依赖** — 纯 Python 标准库，读取 `.index.json` 实时数据

### 手动工作流

如果需要精细控制每个阶段：

1. 干系人提交需求 → CTO 创建项目（模板自动初始化）
2. Market Manager 市场调研竞品分析 → PM 基于调研填写 PRD
3. 架构师审核技术选型 → TL 设计技术方案 → 任务分解 → 分配工程师
4. 工程师：`git_create_branch` → 实现 → `git_commit` → TL `git_merge_branch`
5. DG1-DG4 阶段门禁 → 3 个独立 Reviewer 并行评审
6. 分析自动追踪进度、质量、周期时间，异常预警
7. 日报、周报自动生成
8. 全部门禁通过 → 干系人验收

### 4 阶段门禁评审

```
DG1 (方案设计完成)  → ≥6.0/10  架构、UX、任务分解
DG2 (核心开发完成)  → ≥7.0/10  代码质量、设计还原、测试
DG3 (质量保证完成)  → ≥7.5/10  性能、安全、Bug率
DG4 (待交付)       → ≥8.0/10  部署、文档、验收标准
```

每个阶段 3 个独立 Reviewer 并行投票（R1 架构/R2 产品/R3 工程），≥2/3 通过。

## 团队规模（33人）

| 角色 | 人数 | 模型 | 职责 |
|------|------|------|------|
| CTO | 1 | opus | 技术战略、资源调配 |
| Architect | 1 | opus | 技术标准、架构治理 |
| PM | 3 | opus | 产品需求（AI/ML、IoT、App&Web） |
| Tech Lead | 3 | opus | 技术方案、任务分解 |
| Senior Engineer | 12 | inherit | 主力开发 |
| Domain Engineer | 6 | inherit | ML、IoT、Agent 专家 |
| Designer | 4 | opus | UI/UX 设计（Figma MCP） |
| DevOps/SRE | 2 | inherit | CI/CD、基础设施 |
| Market Manager | 1 | inherit | 市场分析、竞品情报 |
| Reviewer R1/R2/R3 | 3 | opus | 独立评审（并行隔离运行） |

## 插件能力一览

- **11 个 Slash 命令** — 按角色调用 + 全流程自动流水线
- **10 个 Agent 角色** — 含 3 个独立 Reviewer（context: fork 并行）
- **27 个 MCP 工具** — 项目/任务/评审/Sprint/会议/知识库/报表/交接/Git
- **7 阶段自动流水线** — 一键 `/pipeline start` 从立项到交付，支持断点恢复
- **Web Dashboard** — 浏览器实时监控，公司/部门/项目三级视图，30s 自动刷新
- **4 阶段门禁评审** — DG1-DG4，每个阶段 3 人独立投票
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
├── agents/            # 10 个 Agent 角色定义
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
# 确认端口未被占用
lsof -i :8080
# 尝试其他端口
python3 scripts/web_dashboard.py --port 9090
# 确认 projects/ 目录存在（Dashboard 读取 .index.json）
ls projects/.index.json
```

**流水线中断后无法恢复**

```bash
# 查看流水线状态文件
cat projects/<name>/.pipeline-state.json
# 手动修复后重新标记阶段为 done，然后 resume
```

## License

MIT
