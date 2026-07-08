<!--
  Version: 1.0
  Created: 2026-07-08
  Purpose: 项目治理体系整改计划 — 解决三大核心问题:
    1. 无项目管理机制 → 每次 session 重探索项目
    2. 偷懒/撒谎现象 → Manager+Worker 监工 + goal 强制验证
    3. TDD 未真正执行 → 红-绿-重构强制协议
  User Profile: 散户投资者, 可信度优先于收益, 严格交易限制
  Project Root: D:\桌面\quant_backtest\
-->

# 项目治理体系整改计划 (Governance Remediation Plan)

---

## 一、勘察结果摘要 (Audit Findings)

| 维度 | 发现 | 严重度 |
|------|------|:--:|
| 编译 | 31 个 `.py` 文件全部通过 `py_compile` | PASS |
| 语法 | 无语法错误 | PASS |
| 测试覆盖 | `test_critic.py`、`test_meta_learner.py` 为空壳(1 行重定向) | **FAIL** |
| 项目管理 | `CODEX_EXECUTION_PLAN.md` 含 TDD 规范但从未强制执行 | **FAIL** |
| 核心缺失 | 无状态仪表盘、无验证协议、无强制 TDD 规则 | **FAIL** |

---

## 二、问题根因分析

### 问题 1: 无项目管理机制
- **表现**: 每次 session 需重新探索项目结构、模块接口、测试状态
- **根因**: `PROJECT_CONTEXT.md` 纯描述性, 无量化状态字段
- **解决方案**: 三层文档体系 (DASHBOARD + BRIEFING + PROTOCOLS)

### 问题 2: 偷懒/撒谎
- **表现**: 声称 stub 测试"已完成"; 代码无编译验证即标记完成
- **根因**: 无强制验证步骤; goal 标记 complete 无前置门禁
- **解决方案**: VERIFICATION_PROTOCOL (4 步强制门禁) + goal blocked 机制

### 问题 3: TDD 未真正执行
- **表现**: 编写实现代码前未写测试; 声称 TDD 但实际 skip test phase
- **根因**: 无强制红-绿-重构流程
- **解决方案**: TDD_PROTOCOL.md 强制 4 步流程

---

## 三、整改方案: 三层项目管理体系

### 3.1 PROJECT_DASHBOARD.md — 项目仪表盘 (新建)

**目的**: 模块级完成矩阵, 每次完成子任务后自动更新

**结构**:
- 模块名称 / 状态 (ACTIVE/PASSING/STALE/NEEDS_WORK/STUB)
- 测试数量 (real tests / stubs)
- 已知问题
- 最后验证时间
- 39 条目覆盖 agents/core/engine/tests/_prototypes/knowledge

### 3.2 SESSION_BRIEFING.md — 会话简报 (新建)

**目的**: 每个 session 第一步加载, 避免重探索

**结构**:
- 当前目标 (链接到具体 Task/Phase)
- 上次完成的工作 (最近 3 条记录)
- 阻塞项
- 关键路径
- 硬编码路径到项目根目录

### 3.3 .codex/VERIFICATION_PROTOCOL.md — 验证协议 (新建)

**4 个强制步骤**:
1. `python -m py_compile <changed_file>` — 全部通过 (零错误)
2. `pytest tests/test_<module>.py -v` — 必须显示 PASS (至少 1 个 pass)
3. 测试文件中必须包含 `def test_` 和 `assert` (非 stub 空壳)
4. 以上全部通过后才能 `update_goal` 为 `complete`

---

## 四、Manager+Worker 监工机制

```
create_goal(task)
  → Worker 执行 (≤3 文件变更 或 ≤1 模块)
  → 自动触发 VERIFICATION_PROTOCOL
  → 通过? → update_goal "complete"
  → 失败? → 重试 (最多 2 次)
  → 连败? → update_goal "blocked" (需人工介入)
```

- **Blocked 条件**: 同一任务连续 2 次尝试验证失败
- **Task 粒度限制**: ≤ 3 个文件变更 或 ≤ 1 个模块

---

## 五、TDD 强制执行

### 5.1 .codex/TDD_PROTOCOL.md (新建)

| Step | 动作 | 验证 | 状态 |
|------|------|------|:--:|
| 1. RED | 编写测试 `pytest test_file.py::test_name -v` | 必须 FAIL | RED |
| 2. GREEN | 写最小实现 → `py_compile` → `pytest` | 必须 PASS | GREEN |
| 3. REFACTOR | 优化代码 `pytest` | 保持 PASS | GREEN |
| 4. DONE | VERIFICATION_PROTOCOL | COMPLETE |

### 5.2 空壳测试清理

- **test_critic.py**: 1 行重定向 → 提取 3 个 critic 测试
- **test_meta_learner.py**: 1 行重定向 → 提取 4 个 meta_learner 测试

---

## 六、文件变更清单

| 优先级 | 操作 | 文件 | 估计大小 |
|:--:|------|------|------|
| P0 | 新建 | `PROJECT_DASHBOARD.md` | ~6KB |
| P0 | 新建 | `SESSION_BRIEFING.md` | ~2KB |
| P0 | 新建 | `.codex/VERIFICATION_PROTOCOL.md` | ~3KB |
| P0 | 新建 | `.codex/TDD_PROTOCOL.md` | ~3KB |
| P1 | 修改 | `tests/test_critic.py` | 1B → ~3KB |
| P1 | 修改 | `tests/test_meta_learner.py` | 1B → ~3KB |
| P2 | 新建 | `.codex/hooks/post_verify.py` | ~1KB |

---

## 七、实施顺序

```
Step 1: 创建 PROJECT_DASHBOARD.md (扫描所有模块, 填充 39 条目)
Step 2: 创建 SESSION_BRIEFING.md (当前目标 + 上次工作 + 阻塞项)
Step 3: 创建 .codex/VERIFICATION_PROTOCOL.md (4 步强制门禁)
Step 4: 创建 .codex/TDD_PROTOCOL.md (红-绿-重构流程)
Step 5: 修改 tests/test_critic.py (空壳 → 3 个测试)
Step 6: 修改 tests/test_meta_learner.py (空壳 → 3 个测试)
Step 7: 创建 .codex/hooks/post_verify.py (自动验证 hook)
Step 8: 运行完整验证 (py_compile 全部 + pytest 全部)
```

---

## 八、验证标准

| # | 验证项 | 通过标准 |
|---|--------|---------|
| 1 | PROJECT_DASHBOARD.md | 39 条目, status/test_count/verified_at |
| 2 | SESSION_BRIEFING.md | 含目标/工作/阻塞/关键路径 |
| 3 | VERIFICATION_PROTOCOL.md | 4 步, 明确失败处理 |
| 4 | TDD_PROTOCOL.md | 红-绿-重构 4 步, 代码示例 |
| 5 | test_critic.py | ≥ 3 passed |
| 6 | test_meta_learner.py | ≥ 3 passed |
| 7 | py_compile all | 零错误 |
| 8 | full pytest | ≥ 20 passed |

---

## 九、治理假设

1. **监工力度**: "完整三层" (DASHBOARD + goal + 独立验证)
2. **TDD 方式**: "先补洞 + 规则" (修复 stubs + 强制规则)
3. **用户身份**: 散户, 可信度优先, 交易有月/季度调仓限制
4. **状态维护**: 每次子任务完成后更新 DASHBOARD

---

## 十、完成后治理约束

1. Session 开始 → 加载 SESSION_BRIEFING.md
2. 声称完成 → 通过 VERIFICATION_PROTOCOL (4 步)
3. 写代码 → TDD_PROTOCOL (红→绿→重构)
4. Goal complete → 已验证; 连续 2 次失败 → blocked
5. 子任务完成 → 更新 DASHBOARD 状态
