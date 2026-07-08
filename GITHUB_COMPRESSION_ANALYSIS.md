# GitHub 高星项目分析 + 上下文压缩解耦方案

生成时间: 2026-07-08

## 一、GitHub 高星项目搜索结果

### 1.1 上下文压缩相关 (核心)

| Stars | 项目 | 关键发现 |
|-------|------|---------|
| 62K | shanraisshan/claude-code-best-practice | Claude Code 最佳实践大全，含 `.codex/hooks/` PreCompact/PostCompact 钩子 |
| 9K | ykdojo/claude-code-tips | 40+ 条 Claude Code 技巧 |
| 4.3K | zebbern/claude-code-guide | Claude Code 从入门到精通 |
| 3 | **jjjorgenson/instinct8** | **最关键**：反编译 Codex `compact.rs`，评估 7 种压缩策略 |
| 1 | Effet/cxusage | Codex 用量统计 + OpenRouter 定价估算 CLI |

### 1.2 项目管理/Agent 框架相关

| Stars | 项目 | 关键发现 |
|-------|------|---------|
| 1.8K | Njengah/claude-code-cheat-sheet | Claude Code 速查 |
| 48 | MobinMithun/Claude-Project-to-n8n-Workflow | AI 项目管理工作流 |
| 6 | gosha70/code-copilot-team | 多 Agent 项目模板 |
| 1 | x0rium/aidd-starter | AI-Driven Development 模板 |

---

## 二、instinct8 项目核心发现 (Codex compact.rs 反编译分析)

### 2.1 Codex 自动压缩行为 (Strategy B)

| 指标 | 数据 |
|------|------|
| 触发阈值 | **上下文窗口的 90%** |
| gpt-5.1-codex-max 触发点 | ~245K tokens (窗口 272K) |
| gpt-4o 触发点 | ~115K tokens |
| 压缩率 | 77% (2900 -> 650 tokens) |
| 每次压缩目标漂移 | **~8%** |
| 两次压缩累积漂移 | **~20%** |
| 约束丢失率 | 0-40%/次，不可预测 |
| 最易丢失 | 预算限制、团队经验等"软约束" |

### 2.2 压缩保留 vs 丢失

| 保留 | 丢失 |
|------|------|
| 初始系统提示 | 中间对话历史 |
| Ghost snapshots | 助手回复原文 |
| 最近用户消息 (~20K tokens) | 工具调用与结果 |
| ... | **目标陈述 (不保证保留)** |

### 2.3 目标连贯性衰减曲线 (实测)

```
Goal Coherence (%)
100 |o
 95 | \
 90 |  o---- 压缩点 1 (-8%)
 85 |   \
 80 |    \
 75 |     o---- 压缩点 2 (-11%)
 70 |
    +--------------------------------
      Start   CP1     CP2     End
```

---

## 三、性价比交点计算

### 3.1 各 Token 区间的成本与能力

| Token 范围 | 每次成本 (估) | 能力 | 建议 |
|-----------|--------------|------|------|
| 0-30K | ~0.03-0.09 | 完整 | 无需 checkpoint |
| 30-60K | ~0.09-0.18 | 完整 | 子任务边界 checkpoint |
| **60-80K** | **~0.18-0.24** | **完整** | **每个子任务 checkpoint + 验证** |
| 80-245K | ~0.24-0.74 | 良好到受限 | 激进 checkpoint + 每次任务后验证 |
| 245K+ | ~0.74+ | 自动压缩触发 | 恢复协议必须执行 |

### 3.2 成本节省验证

- **不压缩** (上下文膨胀到 245K)：10 轮对话 -> 2.45M tokens -> **$7.50-20.00**
- **60-80K 主动 checkpoint**：10 轮对话 -> 700K tokens -> **$2.10-5.60**
- **节省：65-72%**

### 3.3 结论

**60-80K 是最优性价比区间**：成本可控、能力完整、距离自动压缩触发还有 3-4 倍余量。
与 instinct8 数据验证一致。

---

## 四、旧 skill 的耦合问题诊断

### 4.1 问题

旧 SKILL.md 指示模型 "Please compress context at the next natural break point"，
但模型**没有可以触发 `compact()` 的工具**——那是 Codex Rust 运行时在 90% 阈值自动执行的。

实际的三层耦合：

```
Layer 1: Codex 原生 auto-compact (compact.rs) --> 运行时 245K 强制触发
Layer 2: SKILL.md "Request compression" --> 模型读了但执行不了
Layer 3: 模型假装压缩 (自我总结) --> 浪费 tokens，和 real compaction 无关
```

### 4.2 后果

- 模型在 skill 指导下试图"请求压缩"但底层无响应
- 原生自动压缩依然在 245K 触发，无视 skill
- 模型浪费额外 tokens 做无效的自我总结
- 整体效果：虚假的掌控感 + 实际成本增加

---

## 五、解耦方案 (已实施)

### 5.1 新架构

```
SKILL (模型行为) ==结构化输出==> Codex 原生压缩 (运行时)
HOOKS (文件系统)  ==PRE/POST 保存==> checkpoints/latest.json (始终存在)
```

**核心思路**：不再试图控制压缩，而是准备能在压缩中存活的结构化信息。

### 5.2 修改的文件

| 文件 | 变更 |
|------|------|
| `~/.codex/hooks.json` | **新建** - 配置 PreCompact/PostCompact/SessionStart hooks |
| `~/.codex/hooks/config/hooks-config.json` | **新建** - enable 所有 hooks |
| `~/.codex/hooks/scripts/hooks.py` | **新建** - checkpoint 保存/验证/恢复逻辑 |
| `~/.codex/plugins/context-compression/SKILL.md` | **重写** - 删掉 "request compression"，改为结构化 checkpoint 协议 |
| `~/.codex/plugins/context-compression/.codex-plugin/plugin.json` | **更新** - v2.0.0，hooks 绑定 |

### 5.3 新 Skill 的三条规则

**Rule 1: 子任务边界输出结构化 checkpoint**

```
## [CHECKPOINT] Subtask Boundary
- Completed: [what was done - 1 line]
- Files changed: [list with paths]
- Key decisions: [1-2 decisions made]
- Next task: [what is next]
- Active constraints: [budget, timeline, user preferences]
```

**Rule 2: 压缩后检测并恢复**

读取 `~/.codex/hooks/checkpoints/latest.json`，如果 `post_compact_at > pre_compact_at`：
1. 找到最近的 CHECKPOINT 块
2. 重新声明当前目标
3. 验证约束是否存活
4. 从 checkpoint 的下一个任务继续

**Rule 3: 什么时候不输出 checkpoint**

- 活跃调试中 (输出频率太高)
- 重构进行中 (等完成后)
- 子任务中间 (只在边界 checkpoint)
- 上下文 < 30K (压缩风险低)

### 5.4 Hook 验证结果

```
PRECOMPACT:  Compact #0 pending
POSTCOMPACT: Compact #1 complete
SESSIONSTART: 注入恢复提示到 stdout -> 模型上下文

CHECKPOINT FILE:
{
  "pre_compact_at": "2026-07-08 09:27:33",
  "compact_count": 1,
  "hook_version": "2.0.0",
  "post_compact_at": "2026-07-08 09:27:33"
}
```

---

## 六、对比：旧 vs 新

| 维度 | 旧 Skill | 新 Skill |
|------|---------|---------|
| 与 Codex 原生压缩的关系 | 耦合 (试图控制但做不到) | 解耦 (接受、准备、恢复) |
| 模型能实际执行吗 | 不能 (没有 compact() 工具) | 能 (输出 checkpoint、读文件) |
| Token 浪费 | 自我总结浪费 tokens | 只输出必要 checkpoint (~50 tokens/次) |
| 压缩后恢复 | 无机制 | 自动检测 + 重新声明目标 |
| 可验证性 | 无法验证是否真的压缩了 | hooks + checkpoint 文件提供审计跟踪 |
| 架构清晰度 | 三层混乱耦合 | 明确的 SKILL-model / HOOK-filesystem 分界 |
