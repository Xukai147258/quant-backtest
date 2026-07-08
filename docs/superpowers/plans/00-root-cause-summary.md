# 现存问题汇总 — 三层级根源分析

> **已修复项标记 [FIXED]**，其余为待修复。

**分析日期:** 2026-07-08
**分析方法:** Superpowers systematic-debugging + requesting-code-review
**代码版本:** master (3b5d769)

---

## 一、策略问题（Strategy Level）

### S1 [FIXED] Embargo 排除方向错误

- **位置:** `engine/walkforward.py:98-105`
- **原问题:** Embargo 排除 `[train_end - embargo, train_end - 1]`，与 Lopez de Prado 定义的 `[prev_test_end, prev_test_end + embargo]` 方向相反
- **当前状态:** 已改为 `train_mask = idx <= train_end_date` 完整覆盖 + Purge/Embargo 作为遮罩排除，`tc_em < tc_no` 成立，测试通过
- **残留:** 当前实现是"简化版 Embargo"（排除训练集末尾），而非精确版（排除上一轮测试后的序列相关区间）。效果近似但语义不同

### S2 动量策略只用 1 天收益率

- **位置:** `main.py:47-50`
- **问题:** `"mom"` 策略定义为 `lambda r: np.abs(r.iloc[-1].values)/...`，仅使用最后一天的收益率
- **依据:** Jegadeesh & Titman (1993) 动量策略需要 3-12 个月回顾窗口。1 日收益率信噪比极低，等价于随机权重
- **影响:** 策略池中有一个"名义上的动量策略，实际上的单日反转赌注"，任何基于此策略的回测结果不可信

### S3 HMM 状态被压缩为二元判断

- **位置:** `agents/builder.py:35-45`
- **问题:** HMM 的 4-6 个状态中，只有 `state 0` 被识别为 bear，其余 3-5 个状态全部走 `sentiment` 判断路径
- **依据:** `is_bear = hmm_state == 0` 后，所有非 bear 状态用 `sentiment > 0.6` 判断，HMM 的 3/4 计算量被浪费
- **影响:** 不同市场状态（高波动/慢牛/阴跌）需要不同的策略配置，但 Builder 不做区分

### S4 Sentiment 函数名实不符

- **位置:** `main.py:24-28`
- **问题:** `compute_trend_sentiment` 实际计算的是 50/200 日均线交叉，这是一个趋势跟踪指标，不是市场情绪
- **依据:** 函数体与名称语义不匹配。情绪应该来自舆情、新闻、恐慌指数等外部数据源
- **影响:** 误导性命名增加维护成本，错误地让读者认为系统有情绪信号

### S5 策略池的 defensive 策略是硬编码索引 hack

- **位置:** `main.py:19-22`
- **问题:** `_defensive_weights` 用 `w[-min(3,n):] *= 2` 将最后 3 个资产权重加倍，假设它们是债券 ETF
- **依据:** 资产池的排列顺序由 `core/data.py` 中的 `ASSETS` 列表决定，与 `defensive` 策略的语义没有契约关系。新增或调整资产顺序会破坏此策略
- **影响:** 这不是策略，是索引 hack。`defensive` 策略在回测中不可靠

---

## 二、AI 回测问题（AI Backtesting Level）

### B1 [FIXED] DSR n_obs 时间尺度不匹配

- **位置:** `core/metrics.py:148`, `core/metrics.py:228`
- **原问题:** `n_obs = len(returns)` 使用日频观测数，但 Sharpe 是年化值，导致 DSR 被放大 18 倍
- **当前状态:** 已修复为 `n_obs = max(len(returns) / ann_factor, 1.5)`，测试通过

### B2 WalkForward 忽略 Builder 的策略选择（核心断裂）

- **位置:** `engine/walkforward.py:145-147`
- **问题:** `pool_items[0]` 始终取策略池的第一个（`"eq"` 等权），Builder 的 `propose()` 选择完全被忽略
- **依据:** 策略池定义 `pool = {"eq": ..., "mom": ..., "rp": ..., "def": ...}`，`pool_items[0]` 始终是 `"eq"`
- **影响:** **整个 Agent 决策链（Builder → Critic → MetaLearner）被架空。** 回测中实际执行的永远是等权策略。报告中"策略分布: defensive 62% / risk_parity 38%" 是虚构的

### B3 Meta-Learner 的在线学习从未在回测中生效

- **位置:** `main.py:95-103`
- **问题:** `meta_learner.update()` 在回测完整结束后才调用，回测过程中每次 `arbitrate()` 看到的 `builder_credit` 和 `critic_credit` 始终是初始值 0.5
- **依据:** 信用分更新代码在 `run_backtest()` 返回之后、`main()` 函数末尾。且 `run_backtest()` 每次调用都创建新的 `MetaLearner` 对象
- **影响:** 在线学习是"事后统计"，不是"在线学习"。信用分的变化从未影响过任何一次决策

### B4 Critic 的 56+ 检查点永远 Auto-pass

- **位置:** `agents/critic.py:60-225`
- **问题:** `_evaluate_check()` 有 11 个 marker 分支，但大多数分支的处理逻辑是 `return True, "Auto-pass for ..."`
- **依据:** 检查 `"PBO 是否 < 0.3"` 永远 Auto-pass，因为 `ctx` 中没有 `pbo_value` 字段。检查 `"DSR p-value 是否 < 0.05"` 永远 Auto-pass，因为 `ctx` 中没有 `dsr_p_value`。`main.py:62-85` 传入的 `backtest_context` 只有 5 个字段，而 Critic 需要的字段有 10+ 个——全部缺失
- **影响:** 66 个检查点只有约 10 个能实际产生 FAIL。Critic 的 REJECT 条件几乎不可能触发

### B5 CPCV 的 Purging/Embargo 边界使用索引而非自然日

- **位置:** `engine/cpcv.py:29-31`
- **问题:** `cut = min(self.purge_days, len(idx))` 用索引数代替自然日数
- **依据:** 每组约 201 个索引，截去 5 个索引不等价于截去 5 个自然日
- **影响:** CPCV 的 Sharpe 分布边界可能不精确

### B6 PBO 的 CSCV 实现破坏了时间序列结构

- **位置:** `core/metrics.py:238-239`
- **问题:** `rng.shuffle(all_idx)` 完全随机打乱索引，破坏了时间序列的顺序性
- **依据:** Lopez de Prado (2018) Ch.12 的 CSCV 要求保留时间顺序，使用组合分组而不是随机打乱
- **影响:** PBO 值被人为压低（打乱后更难选出"好"策略），判定不可信

### B7 回测结果中 Max Drawdown = -5.01% 低得不合理

- **位置:** 回测报告（PROJECT_CONTEXT.md 第七节）
- **问题:** 9 只 ETF 组合的最大回撤只有 -5.01%，2022 年 A 股熊市期间任何合理 ETF 组合的预期回撤应在 -12% 到 -18%
- **依据:** 2022 年沪深300 回撤 -21.6%，创业板 -29.4%，科创50 -40%+
- **影响:** 最强的过拟合信号之一

### B8 回测报告中 DSR = Sharpe，过拟合惩罚为零

- **位置:** 回测报告
- **问题:** `Deflated Sharpe: 1.609 (p = 1.0000)`，DSR = Sharpe 意味着 `n_trials=1`
- **依据:** 系统认为只试了一个策略，但 Builder 有 4 个策略池、WalkForward 8 步、CPCV 15 条路径
- **影响:** 过拟合惩罚完全失效

---

## 三、工程实现问题（Engineering Level）

### E1 成本计算中的 portfolio_value 尺度嵌套

- **位置:** `engine/walkforward.py:155-160`
- **问题:** 总收益为正时成本被高估，回撤中成本被低估

### E2 run_backtest 每次重建 HMM 对象

- **位置:** `main.py:35` vs `main.py:42-43`
- **问题:** 外部创建对象从未被使用，每次步骤都重新运行 BIC 选择

### E3 Sharpe 置信区间的 Lo 公式偏度符号

- **位置:** `core/metrics.py:30`
- **问题:** 数据左偏时标准误被低估，置信区间偏窄

### E4 compute_features 窗口参数硬编码且与步长不匹配

- **位置:** `engine/hmm_detector.py:138-155`
- **问题:** 20 天窗口 vs 3 个月步长，尺度不匹配

### E5 测试覆盖与实际问题完全脱钩

- **位置:** `tests/` 全部 7 个文件
- **问题:** 无测试覆盖策略选择执行、信用分变化、Critic 触发、参数敏感性

### E6 compute_pbo 中的随机种子固定

- **位置:** `core/metrics.py:242`
- **问题:** 固定种子使 PBO 不可复现

### E7 _fetch_single 错误处理掩盖数据问题

- **位置:** `core/data.py:42-54`
- **问题:** 连续 3 次获取失败时该 ETF 回测中缺失但不告警

---

## 四、严重程度矩阵

| 优先级 | ID | 问题 | 影响 | 修复难度 |
|--------|----|------|------|---------|
| **P0** | B2 | WalkForward 忽略策略选择 | 整个 Agent 决策链被架空 | 低（~20 行代码） |
| **P0** | B3 | Meta-Learner 更新在回测后 | 在线学习从未生效 | 中（需重构 main.py 流程） |
| **P0** | B4 | Critic 56+ 检查点永远 Auto-pass | 方法论验证失效 | 低（补充 ctx 字段） |
| **P1** | B7 | Max DD = -5.01% 不合理 | 最强过拟合信号 | 需调查 |
| **P1** | B8 | DSR = Sharpe 惩罚为零 | 过拟合惩罚失效 | 中 |
| **P1** | S2 | 动量策略只用 1 天收益率 | 策略池不可信 | 低 |
| **P1** | S3 | HMM 状态被压缩为二元 | 80% HMM 计算浪费 | 中 |
| **P2** | B6 | PBO 的 CSCV 破坏时序 | PBO 不可信 | 中 |
| **P2** | E1 | 成本计算尺度嵌套 | 成本估计不准确 | 低 |
| **P2** | E3 | Sharpe 置信区间偏度符号 | 置信区间偏窄 | 低 |
| **P3** | S4 | Sentiment 函数名实不符 | 误导性命名 | 低 |
| **P3** | E7 | 数据获取失败不告警 | 回测数据不完整 | 低 |

---

## 五、根因分析

所有问题的共同根因是：**模块之间在接口层面看似连接，但在语义层面完全脱钩。**

- WalkForward 接受了 `strategy_pool` 但只用了第一个
- MetaLearner 的 `update()` 被调用但不在回测循环中
- Critic 检查了 `ctx` 但 `ctx` 缺少关键字段
- Builder 选择了策略但 WalkForward 不执行
- HMM 检测了状态但 Builder 只用了 bear/not bear

修复路径应优先解决 P0 的**语义连接**问题，而非 P3 的**命名/计算效率**问题。
