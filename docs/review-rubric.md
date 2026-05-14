# 评审评分细则 v2.0 (Review Rubric)

本评分细则与 reviewer agent 定义中的维度名称和权重保持一致。每个审查者有固定的核心维度，权重随 Gate 变化。

---

## R1: 架构专家 (Architecture Expert)

### 维度定义

所有 Gate 使用相同维度名，权重因 Gate 而异：

| 维度 | 含义 |
|------|------|
| **technical_rationality** | 技术选型是否有充分理由？是否符合公司技术标准？ |
| **architecture_quality** | 架构设计是否合理、模块化、可扩展、松耦合？ |
| **security_risk** | 安全风险是否识别和缓解？威胁面、数据保护、认证授权？ |
| **maintainability** | 系统是否易于理解和修改？技术债务是否受控？ |
| **compliance_standards** | (仅 DG3/DG4) 是否符合行业标准和合规要求？ |

### 权重矩阵

| 维度 | DG1 | DG2 | DG3 | DG4 |
|------|-----|-----|-----|-----|
| technical_rationality | 40% | 35% | 20% | 15% |
| architecture_quality | 30% | 25% | 15% | 10% |
| security_risk | 15% | 20% | 25% | 15% |
| maintainability | 15% | 20% | 20% | 10% |
| compliance_standards | — | — | 20% | 15% |

### 各 Gate 检查要点

#### DG1 — 方案设计阶段
- **technical_rationality**: 技术选型是否对比过替代方案？是否符合 `config/tech-standards.json`？非标技术是否有 ADR？
- **architecture_quality**: 系统分层是否清晰？模块边界是否明确？依赖方向是否单向？
- **security_risk**: 安全威胁是否建模？敏感数据如何保护？认证授权方案是否定义？
- **maintainability**: 是否有技术文档？代码规范是否定义？测试框架和目录结构是否指定？

#### DG2 — 核心开发阶段
- **technical_rationality**: 实现是否偏离设计？技术选型在实际中是否有问题？
- **architecture_quality**: 架构分层是否被遵守？是否有跨层调用？循环依赖？
- **security_risk**: OWASP Top10 是否检查？输入验证、权限控制、敏感数据保护是否到位？
- **maintainability**: 代码是否有足够文档？错误处理是否一致？日志策略？

#### DG3 — 质量保证阶段
- **technical_rationality**: 技术选型在生产环境表现如何？
- **architecture_quality**: 性能瓶颈是否与架构设计一致？
- **security_risk**: 安全扫描是否清零？渗透测试是否通过？依赖漏洞是否修补？
- **maintainability**: 技术债务是否有偿还计划？代码复杂度是否受控？
- **compliance_standards**: 是否符合行业规范（GDPR/SOC2等）？

#### DG4 — 交付阶段
- **technical_rationality**: 最终技术栈是否与审批一致？
- **architecture_quality**: 部署架构是否可行？回滚方案是否准备？
- **security_risk**: 生产环境安全配置是否到位？
- **maintainability**: 运维手册是否完整？故障处理流程是否定义？
- **compliance_standards**: 合规审查是否通过？

---

## R2: 产品专家 (Product Quality Expert)

### 维度定义

| 维度 | 含义 |
|------|------|
| **requirements_match** | 交付物是否匹配 PRD 定义？每个验收标准是否满足？ |
| **ux_usability** | 产品是否直观、易用、可访问？用户体验是否达标？ |
| **completeness** | 是否有功能缺口？未覆盖的场景？未文档化的行为？ |
| **design_fidelity** | 实现是否匹配设计规范和设计系统？ |

### 权重矩阵

| 维度 | DG1 | DG2 | DG3 | DG4 |
|------|-----|-----|-----|-----|
| requirements_match | 30% | 20% | 25% | 30% |
| ux_usability | 30% | 25% | 20% | 20% |
| completeness | 25% | 25% | 25% | 25% |
| design_fidelity | 15% | 30% | 30% | 25% |

### 各 Gate 检查要点

#### DG1 — 方案设计阶段
- **requirements_match**: PRD 的 Must Have 需求是否全部有对应设计方案？验收标准是否可测量？
- **ux_usability**: 用户流程是否有原型？关键交互是否定义？
- **completeness**: 边界情况是否考虑？错误状态是否设计？
- **design_fidelity**: 设计稿是否完整？设计系统是否遵循？

#### DG2 — 核心开发阶段
- **requirements_match**: 所有 Must Have 功能是否实现？AC 是否通过？
- **ux_usability**: UI 是否匹配设计稿？交互是否流畅？加载/空/错误状态是否处理？
- **completeness**: 边界情况是否处理？异常路径是否覆盖？
- **design_fidelity**: 像素级还原度？响应式适配？深色模式？

#### DG3 — 质量保证阶段
- **requirements_match**: 所有 AC（包括 Should/Nice to have）是否通过？回归测试？
- **ux_usability**: 真实用户场景是否流畅？错误提示是否友好？性能是否达标？
- **completeness**: 兼容性测试是否覆盖（浏览器/设备）？
- **design_fidelity**: 设计评审是否通过？动画和过渡效果是否实现？

#### DG4 — 交付阶段
- **requirements_match**: 所有 AC 100% 满足？需求方确认？
- **ux_usability**: 整体体验打磨程度？可访问性审计？
- **completeness**: 用户文档是否完整？API 文档是否更新？
- **design_fidelity**: 最终设计审查是否通过？

---

## R3: 工程效率专家 (Engineering Efficiency Expert)

### 维度定义

| 维度 | 含义 |
|------|------|
| **code_test_quality** | 代码是否整洁、规范、类型安全？TDD 合规？ |
| **test_coverage** | 测试覆盖率是否达标？边界条件和错误路径是否覆盖？ |
| **maintainability** | 代码是否易于理解和修改？是否过度抽象？ |
| **risk_assessment** | 部署风险、数据迁移风险、破坏性变更、性能退化？ |
| **deployment_readiness** | (仅 DG4) 是否可安全部署？回滚方案？ |

### 权重矩阵

| 维度 | DG1 | DG2 | DG3 | DG4 |
|------|-----|-----|-----|-----|
| code_test_quality | 20% | 35% | 40% | 20% |
| test_coverage | 10% | 20% | 25% | 20% |
| maintainability | 35% | 25% | 15% | 10% |
| risk_assessment | 35% | 20% | 20% | 25% |
| deployment_readiness | — | — | — | 25% |

### 各 Gate 检查要点

#### DG1 — 方案设计阶段
- **code_test_quality**: TDD 策略是否定义？测试框架是否选定？
- **test_coverage**: 覆盖率目标是否设定（≥80%）？测试目录结构是否规划？
- **maintainability**: 任务分解是否合理？每个任务是否有清晰 AC？
- **risk_assessment**: 时间估算是否现实？依赖是否清晰？是否有单点风险？

#### DG2 — 核心开发阶段
- **code_test_quality**: TDD 是否遵守（测试先于实现）？代码命名、结构、DRY？
- **test_coverage**: 新代码覆盖率 ≥80%？每个 AC 有对应测试？边界和错误路径测试？
- **maintainability**: 模块化程度？文档质量？是否有过度"聪明"的代码？
- **risk_assessment**: 是否有未测试的关键路径？是否有硬编码配置？

#### DG3 — 质量保证阶段
- **code_test_quality**: Bug 修复率 ≥95%？无 P0/P1 遗留？代码审查发现是否修复？
- **test_coverage**: 单元 ≥80%、集成 ≥70%、E2E 关键路径？回归测试全部通过？
- **maintainability**: 代码质量趋势是否改善？技术债务是否减少？
- **risk_assessment**: 性能测试是否满足指标？安全扫描是否清零？

#### DG4 — 交付阶段
- **code_test_quality**: 无临时方案、无调试代码、无 TODO 标记
- **test_coverage**: 所有测试（单元+集成+E2E）绿色
- **maintainability**: 技术文档是否完整？是否有知识传承记录？
- **risk_assessment**: 部署方案是否经过演练？数据迁移是否有回滚计划？
- **deployment_readiness**: CI/CD 是否就绪？一键部署/回滚？监控告警配置？

---

## 评分标准

所有审查者使用统一的 0-10 评分：

| 分数 | 等级 | 含义 |
|------|------|------|
| 9-10 | 卓越 | 超出预期，无可挑剔 |
| 7-8 | 良好 | 符合标准，小幅改进即可 |
| 4-6 | 一般 | 可用但有明显缺陷或债务 |
| 1-3 | 不足 | 存在根本性问题，必须重做 |

## 投票规则

**Round 1 投票**: overall_score ≥7.0 → approve, 4.0-6.9 → changes_requested, <4.0 → reject

**Round 2 投票**: 辩论后修订的 overall_score，相同阈值

**最终表决**（使用 Round 2 修订后的投票）:

| 票数 | 结果 |
|------|------|
| ≥2 approve | ✅ PASS |
| ≥2 reject | ❌ REJECT |
| ≥2 changes_requested | 🔄 CHANGES REQUIRED |
| 1:1:1 (僵局) | ⚖️ CTO 仲裁 |

## CTO 仲裁权重指引

当 Review Board 僵局时（1 approve + 1 reject + 1 changes_requested），CTO 根据 Gate 类型偏向不同审查者：

| Gate | 偏向 | 理由 |
|------|------|------|
| DG1 | R1 (Architecture) | 设计阶段架构决策影响所有后续阶段 |
| DG2 | R3 (Engineering) | 代码质量和测试是实现质量的核心 |
| DG3 | R3 (Engineering) | 测试覆盖和性能是 QA 阶段的关键 |
| DG4 | R2 (Product) | 交付时验收标准和用户体验最重要 |

CTO 不是简单地采纳被偏向者的投票，而是：
1. 阅读所有三位审查者的发现和辩论综合
2. 以被偏向者的视角为主，评估其他两位的反对意见
3. 做出独立的绑定裁决
4. 记录仲裁决策：采纳了谁的立场、为什么、接受什么风险

## 综合评分计算

每位审查者的 Round 1 总分 = Σ(维度得分 × 权重)
Round 2 修订后总分 = 辩论调整后的总分

最终通过/不通过基于 Round 2 修订后的投票统计。
