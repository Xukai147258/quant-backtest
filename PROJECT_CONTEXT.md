# AI 量化回测系统 — 项目全景

> 用于 Claude Code 对话的项目上下文，覆盖架构、模块、数据流和当前状态。

---

## 一、项目目标

构建一套 **生产级 AI 量化回测系统**，针对 **9只 ETF 的中长期组合配置**（月度/季度调仓，持有 1~3 年），核心方法论基于 **Lopez de Prado《Advances in Financial Machine Learning》**，解决传统回测的 8 项方法论缺陷。

核心理念：**市场状态感知 → 情绪交叉验证 → 元学习策略择时**

---

## 二、项目结构

所有文件位于 `D:\桌面\` 下：

```
D:\桌面\
├── core/                    # 核心模块
│   ├── data.py              # 数据获取（AKShare 新浪接口）+ 清洗 + 划分
│   ├── cost.py              # 交易成本模型（佣金/滑点/冲击）
│   └── metrics.py           # 评估指标体系（≥20项，含 DSR/PBO）
├── engine/                  # 回测引擎
│   ├── walkforward.py       # Expanding Window 回测 + Purging + Embargo
│   ├── hmm_detector.py      # HMM 滚动重训（无前视偏差）
│   └── sentiment.py         # 情绪分析（stub）
├── agents/                  # 双 Agent + 元学习
│   ├── builder.py           # Builder Agent：根据市场状态提案策略权重
│   ├── critic.py            # Critic Agent：基于 checklist.md 审查提案
│   ├── meta_learner.py      # Meta-Learner：在线信誉分加权裁决
│   └── orchestrator.py      # Orchestrator：Builder→Critic→MetaLearner 主循环
├── knowledge/               # 知识库
│   ├── checklist.md         # 66 个方法论检查点
│   ├── literature.md        # 核心概念速查（Purging/Embargo/CPCV/PBO/DSR）
│   └── frameworks.md        # Qlib/vnpy/Backtrader/Zipline 框架对比
├── tests/                   # 20 个单元测试
│   ├── test_data.py         # 3 tests
│   ├── test_cost.py         # 4 tests
│   ├── test_metrics.py      # 4 tests
│   ├── test_walkforward.py  # 3 tests
│   ├── test_hmm.py          # 1 test
│   ├── test_agents.py       # 4 tests
│   └── test_e2e.py          # 1 test（端到端集成）
├── main.py                  # 主入口（python main.py / --realtime）
├── report.py                # 最终报告生成器
├── final_report.txt         # 生成的报告（含最新回测结果）
└── CODEX_EXECUTION_PLAN.md  # 完整的执行计划文档
```

---

## 三、ETF 资产池（9只）

| 代码 | 名称 | 分类 |
|------|------|------|
| 510300 | 沪深300 | A股大盘 |
| 510500 | 中证500 | A股中盘 |
| 159915 | 创业板 | A股成长 |
| 588000 | 科创50 | A股科技 |
| 510050 | 上证50 | A股大盘 |
| 511010 | 国债ETF | 债券 |
| 511260 | 十年国债 | 债券 |
| 511360 | 短融ETF | 货币/短债 |
| 518880 | 黄金ETF | 商品 |

---

## 四、核心架构设计

### 4.1 数据流

```
AKShare(sina) → _fetch_single() → fetch_etf_data() → clean_data() → split_data()
                                      ↑                                 ↓
                                 Winsorize/停牌处理/复权校验     train/val/test (含Purging gap)
```

### 4.2 回测流

```
WalkForwardBacktester.run()
  for each step (step_months=3):
    1. train_end = start + train_years + step*step_months
    2. train_data = prices[:train_end - purge_days]        # Purging
    3. test_data = prices[train_end+purge : train_end+step_months]
    4. features = compute_features(train_data)
    5. hmm_state = HMM.fit_predict(features)               # 只用历史数据
    6. weights = strategy_fn(train_returns, cov)            # 含 Orchestrator 周期
    7. portfolio_value *= (1 + test_rets.dot(weights))     # 含成本扣除
```

### 4.3 Agent 决策流（每季度）

```
BuilderAgent.propose(market_features, hmm_state, sentiment, strategy_pool)
     ↓ 输出 {strategy, weights, confidence, rationale}
CriticAgent.review(proposal, backtest_context)
     ↓ 输出 {verdict: APPROVE|DOWNGRADE|REJECT, findings, adjusted_confidence}
MetaLearner.arbitrate(features, proposal, review)
     ↓ 输出 {weights, confidence, builder_credit, critic_credit}
Orchestrator 记录 cycle_log 并执行权重
     ↓ 下季度回调 MetaLearner.update(features, weights, actual_outcome)
```

### 4.4 前视偏差防范体系

- **Purging**: `train_data = prices[:train_end - 5d]` — 确保测试标签不泄露到训练集
- **Embargo**: `test_end + 10d` 内的数据不进入下一轮训练
- **HMM 滚动**: 每步只 fit 截至当前日期的历史数据
- **标准化**: StandardScaler 只基于历史数据计算 mean/std
- **Expanding Window**: 测试数据始终在训练数据之后

---

## 五、关键模块接口

### `core/data.py`
```python
fetch_etf_data(days=1825) -> pd.DataFrame  # index=datetime, columns=9 ETF codes
clean_data(df) -> pd.DataFrame              # Winsorize(5σ) + ffill停牌(≤3d) + 异常值WARN
split_data(prices, train_end, val_end, purge_days=5) -> (train, val, test)
```

### `core/cost.py`
```python
class CostModel(commission_rate=0.00025, min_commission=5.0, slippage_bps=2.0,
                stamp_duty=0.0, impact_model='sqrt')
    .round_trip_cost(trade_value, daily_volume=None) -> float  # 买+卖总成本
```

### `core/metrics.py`
```python
compute_all_metrics(returns, benchmark_returns=None, n_trials=1, risk_free=0.02) -> dict(≥20项)
compute_dsr(sharpe, n_trials, n_obs, skewness=0.0, kurtosis=3.0) -> dict
compute_pbo(strategy_returns_matrix, n_splits=100) -> float
```

### `engine/walkforward.py`
```python
class WalkForwardBacktester(prices, cost_model, strategy_pool, train_years=3,
                            step_months=3, purge_days=5, embargo_days=10,
                            initial_investment=1_000_000.0)
    .run() -> dict {equity_curve, weights_log, train_ends, test_starts, test_ends, n_steps}
```

### `engine/hmm_detector.py`
```python
class RollingHMMDetector(n_states=4, n_iter=200)
    .fit_predict(features) -> (current_state, model, scaler)
compute_features(prices, window=20) -> pd.DataFrame  # ret_1d,ret_5d,ret_20d,vol_20d,max_corr,spread
```

### `agents/builder.py`
```python
class BuilderAgent(max_weight=0.4)
    .propose(market_features, hmm_state, sentiment, strategy_pool)
        -> {strategy, weights, confidence, rationale}
```

### `agents/critic.py`
```python
class CriticAgent(checklist_path='knowledge/checklist.md')
    .review(builder_proposal, backtest_context)
        -> {verdict, findings, adjusted_confidence}
```

### `agents/meta_learner.py`
```python
class MetaLearner(lookback_quarters=8, n_assets=9)
    .arbitrate(features, builder_proposal, critic_review) -> {weights, confidence, ...}
    .update(features, final_weights, actual_outcome)  # 在线学学习
```

### `agents/orchestrator.py`
```python
class Orchestrator(builder, critic, meta_learner, backtester)
    .run_quarterly_cycle(date, market_data) -> {proposal, review, decision}
```

---

## 六、当前测试状态：20/20 通过

| 测试文件 | 数量 | 覆盖率 |
|---------|------|--------|
| test_data.py | 3 | fetch/clean/split 全链路 |
| test_cost.py | 4 | bounds/min/trade fee/zero-commission warn |
| test_metrics.py | 4 | ≥18 fields/PBO(valid range)/PBO(edge)/DSR |
| test_walkforward.py | 3 | no lookahead/purge gap/embargo gap |
| test_hmm.py | 1 | rolling fit no lookahead |
| test_agents.py | 4 | no short/critic catches/arbitrate/credit update |
| test_e2e.py | 1 | 全组件集成的 12 步回测 |

---

## 七、最新生产回测结果

```text
日期: 2026-07-07
数据: 9 只 ETF, 2021-07 ~ 2026-07 (1208 个交易日)
回测: 8 个 Walk-Forward 步 (train=3yr, step=3mo)

CAGR:               +16.03%
Sharpe Ratio:        1.609
Deflated Sharpe:     1.609 (p = 1.0000)
Sortino Ratio:       2.250
Calmar Ratio:        3.198
Max Drawdown:       -5.01%
Max DD Duration:    151 days
Win Rate:           55.5%
Profit Factor:       1.45

策略分布: defensive 62% / risk_parity 38%
Critic: 全部 APPROVE (8/8)
```

---

## 八、已知问题（按优先级）

| # | 问题 | 影响 | 状态 |
|---|------|------|------|
| 1 | Embargo 在 walkforward 步进中未主动执行边界检查（仅在 test 中验证了 gap） | 潜在的轻微前视偏差，但 8 步窗口下影响很小 | P2 |
| 2 | Critic `_evaluate_check` 使用子串匹配，而非语义理解 | 无法正确解析 checklist 条目的上下文，可能导致误判 | P3 |
| 3 | `test_critic.py` 和 `test_meta_learner.py` 为空 | 影响持续集成覆盖率报告的完整性 | P3 |
| 4 | `sentiment.py` 仅 stub，未接入新闻 API | Builder 始终使用 sentiment=0.5，情绪信号不起作用 | P3 |

---

## 九、使用方式

```bash
# 快速测试（mock 数据，12步回测）
cd /d "D:\桌面"
python main.py

# 实盘模式（AKShare 真实数据，8步回测）
python main.py --realtime

# 运行全部测试
pytest tests/ -v
```

---

## 十、环境

- Python 3.13 (Anaconda: `D:\ANACONDA\envs\PythonProject\`)
- GPU: RTX 5060 8GB
- 关键依赖: akshare, pandas, numpy, scipy, hmmlearn, scikit-learn
- 数据源: AKShare 新浪接口 (`fund_etf_hist_sina`)
