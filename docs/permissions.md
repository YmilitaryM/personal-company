# 权限矩阵 (Permission Matrix)

## 设计原则

1. **最小权限原则**: 每个角色只能访问完成其职责所必需的工具和文件
2. **职责分离**: 开发与评审分离、设计与实现分离、管理与执行分离
3. **审计可追溯**: 所有敏感操作记录在 `.claude/activity.log`

## 工具权限矩阵

| 工具 | CTO | PM | TL | 高级工程师 | 专业工程师 | 设计师 | 市场 | DevOps | 评审员 |
|------|-----|----|----|-----------|-----------|--------|------|--------|--------|
| Read | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Glob | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Grep | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Write | ✅* | ✅* | ✅* | ✅ | ✅ | ✅ | ✅* | ✅* | ❌ |
| Edit | ✅* | ✅* | ✅* | ✅ | ✅ | ✅ | ✅* | ✅* | ❌ |
| Bash | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| TaskCreate | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| TaskUpdate | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Agent | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| WebFetch | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| WebSearch | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |

✅* = 仅限职责范围内的文件

## 文件访问范围

### CTO
```
允许写: projects/** docs/** dashboards/**
禁止写: (无特别限制，CTO拥有所有文件权限)
```

### PM
```
允许写: projects/<project>/prd.md projects/<project>/backlog.md docs/
禁止写: 源代码文件(.ts, .js, .py, .go, .java 等)
禁止写: projects/<project>/tech-spec.md (TL产出)
禁止写: 配置文件(.yml, .json, Dockerfile 等)
```

### Tech Lead
```
允许写: projects/<project>/tech-spec.md projects/<project>/tasks.md
允许写: 负责项目的源代码
禁止写: projects/<project>/prd.md (PM产出)
禁止写: 其他项目的源代码
```

### 高级工程师 / 专业工程师
```
允许写: 分配的任务对应的源代码文件
禁止写: projects/**/prd.md (PM产出)
禁止写: projects/**/tech-spec.md (TL产出)
禁止写: tasks.md status.md (TL管理)
禁止写: reviews/** (评审员产出)
```

### 设计师
```
允许写: design-system/** specs/design/**
禁止写: 源代码文件(.ts, .js, .py, .go 等)
禁止写: projects/**/reviews/**
```

### DevOps
```
允许写: .github/workflows/** Dockerfile docker-compose.* deploy/**
允许写: 基础设施配置文件(.yml, .toml, .tf)
禁止写: 业务源代码
禁止写: projects/**/prd.md
禁止写: projects/**/reviews/**
```

### 评审员
```
允许写: projects/<project>/reviews/**
禁止写: (所有其他文件)
特别禁止: 任何源代码、配置文件、项目文档
```

### 市场经理
```
允许写: reports/market/** docs/
禁止写: 源代码文件、配置文件、projects/**
```

## 阶段权限变化

### 评审期间 (评审团活跃时)
- **所有开发人员**: 被评审项目的源代码变为只读
- **TL**: 被评审项目的 tasks.md 变为只读
- **CTO**: 权限不变

### 交付验收期间
- **所有角色**: 被交付项目的文件变为只读
- **CTO**: 拥有最终修改权，但需要记录变更理由

## 审批权限

| 操作 | 审批人 | 备注 |
|------|--------|------|
| 创建项目 | CTO | 自动批准 |
| 修改PRD | PM → TL → CTO | PM修改需TL如悉，重大变更需CTO批准 |
| 修改技术方案 | TL → CTO | 架构变更需CTO批准 |
| 修改任务分配 | TL | 自主任意调整 |
| 跳过评审门禁 | CTO | 仅紧急修复可批准，需记录原因 |
| 强制部署 | CTO + DevOps | 需双人确认 |
| 访问敏感数据 | CTO | 每次需审批 |

## 安全规则

### 代码提交前强制检查
- [ ] 无硬编码密钥/Token
- [ ] 无调试代码 (console.log, print, debugger)
- [ ] 无 TODO/FIXME (需转为正式任务)
- [ ] 类型检查通过
- [ ] 测试覆盖率 ≥ 80%

### 评审独立性保障
- 评审员不得参与任何项目开发
- 评审员之间不得在投票前讨论
- 评审员的 vote 记录不可修改 (append-only)
- 评审结果公开透明，所有人可查看

### 数据保护
- 所有 MCP 数据存储在 `projects/.index.json` (json格式)
- Markdown 文件为数据副本，MCP JSON 为数据主源
- 所有操作记录在 `.claude/activity.log`