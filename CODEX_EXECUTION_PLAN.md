# Codex 执行计划：AI 量化回测系统

---

## 一、项目背景

### 用户画像

- AI/ML 方向，对理财感兴趣，想用 AI 做中长期 ETF 组合配置
- 已用 Claude Code 完成三层概念验证（组合优化 → HMM 状态识别 → 情绪双重信号）
- 在概念验证中发现 8 个方法论文缺陷，现需从头重构为生产级系统
- **最终目标：中长期投资组合（月度/季度调仓，持有 1~3 年），不是短线交易**

### 你的角色（Codex）

你是这个项目的**批判视角执行者**。你的职责：
1. 严格按 TDD 方式实施每个任务
2. 每个任务完成后自我验证——通过的标志是什么，没通过就是没完成
3. 对之前 Claude Code 写的概念验证代码保持怀疑：数据可复用，逻辑必须重写

### 项目核心洞察：AI 时代量化回测的真正护城河

```
传统量化（低护城河）  →  AI 增强量化（高护城河）
规则策略 + 静态回测   →  市场状态感知 + 情绪交叉验证 + 元学习策略择时
人人都能做            →  模型推理深度 = 差异化来源
```

### 技术环境

| 项目 | 值 |
|------|-----|
| Python | 3.13 (Anaconda: `D:\ANACONDA\envs\PythonProject\`) |
| GPU | RTX 5060 8GB（PyTorch 当前为 CPU 版，需要时可装 CUDA 版） |
| 已装包 | akshare, pandas, numpy, scipy, backtrader, hmmlearn, snownlp, transformers |
| 工作目录 | `D:\桌面\` |
| 数据源 | AKShare（新浪接口 `fund_etf_hist_sina` + 东方财富 `stock_news_em`） |

### 现有可复用资产

| 文件 | 可复用内容 | 不可复用 |
|------|-----------|---------|
| `akshare_demo.py` | 数据获取的 API 调用方式 | — |
| `portfolio_backtest.py` | 6 种优化方法的数学实现（等权/风平/最小方差/均值方差/动量） | 回测循环（有未来函数） |
| `regime_detection.py` | 特征工程函数 | HMM fit 在全部数据上（必须改为滚动） |
| `sentiment_final.py` | 情绪指数计算逻辑 | 同样有全时段数据泄露 |
| `akshare_output/` | 历史获取的 ETF 数据 | 不可用于正式回测（需重新获取+清洗） |

---

## 二、已识别的方法论文缺陷（8 项——必须全部解决）

| # | 缺陷 | 严重度 | 曾经犯的错误 |
|---|------|:--:|------|
| 1 | 无训练/验证/测试划分 | 🔴 致命 | HMM fit 在全部 5 年数据上再"回测" |
| 2 | 无数据清洗 | 🔴 致命 | `dropna()` 就完事了 |
| 3 | 无模型评估指标 | 🟠 严重 | HMM 没有 BIC/AIC，情绪模型没有 Accuracy |
| 4 | 无机会成本/时间成本 | 🟠 严重 | 可能跑不赢等权 ETF 持有 |
| 5 | 无真实交易成本 | 🟡 中等 | 设了 `commission=0.001` 就完了 |
| 6 | 无过拟合防范 | 🔴 致命 | 6 种策略同数据比较，未做 Deflated Sharpe/PBO |
| 7 | 无滚动交叉验证 | 🔴 致命 | 固定窗口划分 |
| 8 | 无元学习模型 | 🔴 致命 | 策略选择是硬编码 if-else |

---

## 三、知识库速查（Lopez de Prado 回测方法论核心概念）

本节直接嵌入知识库，避免重复搜索。

### 3.1 Purging（清洗泄露）

**定义**：从训练集中删除任何标签区间与测试集标签区间有重叠的样本。
**为什么**：在金融时间序列中，一个训练标签（如未来 5 天收益）可能和测试标签的窗口重叠，导致模型"看到未来"。
**怎么做**：设定 `purge_days`（如 5 个交易日），在训练集末尾和测试集开头之间去掉。

```python
# 伪代码
train_end = test_start - timedelta(days=purge_days)
train_data = all_data[all_data.date <= train_end]
```

### 3.2 Embargo（禁运区）

**定义**：在测试集之后额外设置一段"禁运区"，该区域的数据也不能进入训练集。
**为什么**：即使标签不重叠，市场反应滞后或序列自相关仍可导致泄露。
**怎么做**：`embargo_days = purge_days * 1%`（通常 5~10 天）。

### 3.3 Combinatorial Purged Cross-Validation (CPCV)

**定义**：不只用一条时间路径，而是用 C(N,k) 种组合生成多条回测路径。每条路径都在不同的 train/test 组合上评估。
**为什么**：单次 Walk-Forward 的回测结果高度依赖起点和窗口大小。CPCV 给出**Sharpe 的分布**，不是单点估计。
**推荐配置**：k=2 测试组，N 组总数，生成 N-1 条路径。

### 3.4 Probability of Backtest Overfitting (PBO)

**定义**：在 CSCV（对称交叉验证）框架下，"训练集表现最好"的策略在测试集中排名低于中位数的概率。
**阈值**：PBO > 0.5 → 策略选择本质上是随机的，不可用。
**怎么做**：
```python
# 伪代码
for each split in CSCV_splits:
    is_rank = rank_strategies_by_sharpe(in_sample)
    oos_rank = rank_strategies_by_sharpe(out_of_sample)
    count_if_oos_below_median += 1
PBO = count_if_oos_below_median / total_splits
```

### 3.5 Deflated Sharpe Ratio (DSR)

**定义**：考虑多重检验后的 Sharpe Ratio。如果你试了 100 种策略，最高 Sharpe 的"真空"期望值是 ~√(2×ln(100)) × σ。
**公式**：
```
DSR = P[Sharpe* > E[max(Sharpe_1, ..., Sharpe_N)]]
    ≈ Φ( (Sharpe* - E[max]) / σ_sharpe )
```
其中 E[max] ≈ σ × √(2×ln(N_trials))（极值理论）。
**阈值**：DSR 对应的 p-value < 0.05 才算显著。

### 3.6 7 Deadly Sins of Backtesting (Lopez de Prado)

1. Survivorship Bias — 只回测现在还活着的标的
2. Look-Ahead Bias — 训练数据包含了未来信息
3. Data Snooping — 在同数据集上反复调参
4. Ignoring Transaction Costs — 假设零成本交易
5. Outlier-Driven Success — 少数极端日贡献了大部分收益
6. Shorting Constraints — 假设能做空但不计成本
7. Storytelling — 数据挖掘穿上了叙事的外衣

---

## 四、TDD 任务拆分（按优先级 + 依赖关系）

### 依赖关系图

```
Phase 0: 基础设施
  └─ Task 0.1: 知识库文件
  └─ Task 0.2: 项目结构

Phase 1: 数据管线（无依赖）
  └─ Task 1.1: 数据获取
  └─ Task 1.2: 数据清洗
  └─ Task 1.3: 训练/验证/测试划分

Phase 2: 成本 + 评估（无依赖，可并行）
  └─ Task 2.1: 成本模型
  └─ Task 2.2: 评估指标体系

Phase 3: 回测引擎（依赖 Phase 1 + Phase 2）
  └─ Task 3.1: Expanding Window 滚动回测
  └─ Task 3.2: Purging + Embargo
  └─ Task 3.3: HMM 滚动重训

Phase 4: 双 Agent + 元学习（依赖 Phase 3）
  └─ Task 4.1: Builder Agent
  └─ Task 4.2: Critic Agent (含 checklist)
  └─ Task 4.3: Meta-Learner
  └─ Task 4.4: 辩论-裁决主循环

Phase 5: 完整回测 + 验证（依赖 Phase 4）
  └─ Task 5.1: 端到端 Walk-Forward 回测
  └─ Task 5.2: PBO + DSR 计算
  └─ Task 5.3: 与旧版对比 + 最终报告
```

---

## 五、每个任务的详细规格 + 成功标准

---

### Phase 0: 基础设施

---

#### Task 0.1: 创建知识库文件

**优先级**：P0（阻塞所有后续任务）

**产出文件**：
```
D:\桌面\knowledge\
  ├── checklist.md           # 批判 Agent 检查清单
  ├── literature.md          # 核心概念速查（本文第三章的扩展版）
  └── frameworks.md          # Qlib/vnpy/Backtrader 优缺点
```

**checklist.md 内容要求**：
- 覆盖本文第二章的 8 项缺陷 + 第三章的 7 宗罪
- 每项下面有具体的检查点（是/否），不是泛泛的描述
- 格式应该是 Codex 可以直接用代码解析的

**成功标准**：
- [ ] `checklist.md` 包含 ≥ 30 个检查点
- [ ] 每个检查点都能用"是/否"或数值回答
- [ ] `literature.md` 包含 Purging/Embargo/CPCV/PBO/DSR 的定义 + Python 伪代码
- [ ] `frameworks.md` 包含 Qlib/vnpy/Backtrader/Zipline 的 Stars/优点/缺点/适用场景

---

#### Task 0.2: 创建项目结构

**优先级**：P0

**产出目录结构**：
```
D:\桌面\
  ├── core/          # 核心模块（数据、成本、指标）
  │   ├── __init__.py
  │   ├── data.py           # 数据获取+清洗
  │   ├── cost.py           # 成本模型
  │   └── metrics.py        # 评估指标
  ├── engine/        # 回测引擎
  │   ├── __init__.py
  │   ├── walkforward.py    # W-F 回测框架
  │   ├── hmm_detector.py   # HMM 滚动重训
  │   └── sentiment.py      # 情绪分析（滚动计算）
  ├── agents/        # 双 Agent + 元学习
  │   ├── __init__.py
  │   ├── builder.py        # 主 Agent
  │   ├── critic.py         # 批判 Agent
  │   ├── meta_learner.py   # 元学习裁决器
  │   └── orchestrator.py   # 主循环
  ├── knowledge/     # 知识库
  │   ├── checklist.md
  │   ├── literature.md
  │   └── frameworks.md
  ├── tests/         # 单元测试
  │   ├── test_data.py
  │   ├── test_cost.py
  │   ├── test_metrics.py
  │   ├── test_walkforward.py
  │   ├── test_hmm.py
  │   ├── test_critic.py
  │   └── test_meta_learner.py
  └── CODEX_TASK.md
```

**成功标准**：
- [ ] 所有目录和 `__init__.py` 创建完毕
- [ ] 可以执行 `from core.data import fetch_etf_data` 不报错（即使函数体是空的）

---

### Phase 1: 数据管线

---

#### Task 1.1: 数据获取 `core/data.py`

**功能**：使用 AKShare 新浪接口获取 9 只 ETF 的 5 年日线数据。

**资产池**：
```python
ASSETS = [
    ("510300", "沪深300",   "sh510300"),
    ("510500", "中证500",   "sh510500"),
    ("159915", "创业板",    "sz159915"),
    ("588000", "科创50",    "sh588000"),
    ("510050", "上证50",    "sh510050"),
    ("511010", "国债ETF",   "sh511010"),
    ("511260", "十年国债",  "sh511260"),
    ("518880", "黄金ETF",   "sh518880"),
    ("511360", "短融ETF",   "sh511360"),
]
```

**API 调用**：`ak.fund_etf_hist_sina(symbol=sym)` → rename → 筛选日期 → 合并 wide table

**TDD 测试** (`tests/test_data.py` → `test_fetch_returns_valid_data`)：
```python
def test_fetch_returns_valid_data():
    """获取的数据必须满足基本约束"""
    df = fetch_etf_data(days=365)  # 先测 1 年，速度快
    assert df.shape[0] >= 200      # 至少 200 个交易日
    assert df.shape[1] == 9        # 9 只 ETF
    assert df.index.is_monotonic_increasing  # 日期递增
    assert df.isnull().sum().sum() == 0      # 无缺失值
    assert (df > 0).all().all()              # 价格 > 0
```

**成功标准**：
- [ ] 测试通过
- [ ] 近 5 年数据 ≥ 1000 个交易日
- [ ] `fetch_etf_data()` 返回 `pd.DataFrame`，index 为 `datetime`，columns 为 ETF 代码
- [ ] 包含 rate limiting（`time.sleep(0.3)` 避免被封）

---

#### Task 1.2: 数据清洗 `core/data.py`

**功能**：在 `fetch_etf_data()` 返回之前完成清洗。

**清洗步骤**：
```
1. 异常值检测: abs(daily_return) > 0.20 → 标记 WARNING，保留但不用于回测
2. 复权校验: 前复权价格的连续性检查（相邻日涨跌不超过 ±20%）
3. 停牌处理: ffill ≤ 3 天，超过则 drop 该资产在该时段的数据
4. 收益率 Winsorize: clip 到 ±5σ（逐资产分别计算）
```

**TDD 测试** (`tests/test_data.py` → `test_clean_pipeline`)：
```python
def test_clean_pipeline():
    """清洗后数据不应有任何不合理值"""
    df = fetch_etf_data(days=365)
    returns = df.pct_change().dropna()
    
    # 无极端涨跌
    for col in returns.columns:
        assert (returns[col].abs() < 0.20).all(), f"{col} has extreme returns"
    
    # 无连续 3 天以上不变的价格（停牌标记）
    for col in df.columns:
        flat_days = (df[col].diff() == 0).rolling(4).sum()
        assert (flat_days < 4).all(), f"{col} has >3 consecutive flat days"
    
    # Winsorize 后的标准差应合理
    for col in returns.columns:
        assert returns[col].std() < 0.05, f"{col} volatility too high after winsorization"
```

**成功标准**：
- [ ] 测试通过
- [ ] `fetch_etf_data()` 返回的是清洗后的数据
- [ ] 清洗日志输出（标记了多少异常值、删除了多少停牌段）
- [ ] 清洗后的收益率 std 在合理范围内（< 5% 日度）

---

#### Task 1.3: 训练/验证/测试划分 `core/data.py`

**功能**：`split_data(df, train_ratio=0.6, val_ratio=0.2, purge_days=5)`

```python
def split_data(prices, train_end, val_end, purge_days=5):
    """
    train_end: 如 '2024-06-30'
    val_end:   如 '2025-06-30'
    
    返回:
      train: prices[prices.index <= train_end - purge_days]
      val:   prices[(train_end < prices.index) & (prices.index <= val_end)]
      test:  prices[prices.index > val_end + purge_days]
    
    注意: train 末尾和 val 开头之间有 purge_days 的 gap
          val 末尾和 test 开头之间也有 purge_days 的 gap
    """
```

**TDD 测试** (`tests/test_data.py` → `test_split_no_overlap`)：
```python
def test_split_no_overlap():
    """训练/验证/测试三段必须无日期重叠且有 purge gap"""
    df = fetch_etf_data(days=365*5)
    train, val, test = split_data(df, '2024-06-30', '2025-06-30', purge_days=5)
    
    # 无重叠
    assert train.index.max() < val.index.min()
    assert val.index.max() < test.index.min()
    
    # Purge gap 存在（至少 3 个交易日）
    assert (val.index.min() - train.index.max()).days >= 3
    assert (test.index.min() - val.index.max()).days >= 3
    
    # 三段的并集条目数 ≤ 原始数据条目数
    total = len(train) + len(val) + len(test)
    assert total <= len(df)
```

**成功标准**：
- [ ] 测试通过
- [ ] 三段数据无任何日期重叠
- [ ] Purge gap ≥ 5 个自然日（≥ 3 个交易日）
- [ ] 函数返回三个独立的 `pd.DataFrame`

---

### Phase 2: 成本 + 评估

---

#### Task 2.1: 成本模型 `core/cost.py`

**功能**：建模真实的交易成本。

```python
class CostModel:
    def __init__(self,
        commission_rate=0.00025,    # 万 2.5
        min_commission=5.0,         # 最低 5 元
        slippage_bps=2.0,           # 固定滑点 2bp
        stamp_duty=0.0,             # ETF 免印花税
        impact_model='sqrt',        # 冲击模型: sqrt(Q/V)
    ):
        ...

    def round_trip_cost(self, trade_value, daily_volume=None):
        """一次买+卖的总成本"""
        commission = max(trade_value * self.commission_rate, self.min_commission)
        slippage = trade_value * self.slippage_bps / 10000
        impact = self._sqrt_impact(trade_value, daily_volume) if daily_volume else 0
        return commission * 2 + slippage * 2 + impact  # 买+卖
    
    def _sqrt_impact(self, trade_value, daily_volume):
        """Almgren-Chriss sqrt 公式简化版"""
        if daily_volume <= 0:
            return 0
        participation_rate = trade_value / daily_volume
        return trade_value * 0.1 * np.sqrt(participation_rate)  # 10bp * sqrt(参与率)
```

**TDD 测试** (`tests/test_cost.py` → `test_round_trip_cost_bounds`)：
```python
def test_round_trip_cost_bounds():
    """交易成本在合理范围内"""
    model = CostModel()
    
    # 小交易: 成本 > 0 但不太高
    small = model.round_trip_cost(10000)
    assert small > 10  # 至少 10 元（两次最低佣金）
    assert small < 100  # 不超过 1%
    
    # 中等交易: 滑点+佣金
    medium = model.round_trip_cost(100000, daily_volume=1e8)
    assert medium > 50
    assert medium < 300
    
    # 大交易: 冲击成本非线性上升
    large = model.round_trip_cost(1000000, daily_volume=1e8)
    very_large = model.round_trip_cost(5000000, daily_volume=1e8)
    # 5倍规模 → 成本增长 > 5倍（冲击成本非线性）
    assert very_large / large > 5.0
```

**成功标准**：
- [ ] 测试通过
- [ ] `round_trip_cost()` 返回 float，单位元
- [ ] 最低佣金约束生效（min_commission=5 元）
- [ ] 冲击成本随参与率非线性增长
- [ ] 无券商手续费时会 warn（不阻断）

---

#### Task 2.2: 评估指标体系 `core/metrics.py`

**功能**：定义完整的评估指标，不是只算 Sharpe。

```python
def compute_all_metrics(returns, benchmark_returns=None, n_trials=1, risk_free=0.02):
    """
    returns: 策略的月度净值序列
    benchmark_returns: 基准的月度净值序列（可选）
    n_trials: 尝试过的策略数量（用于 DSR）
    
    返回 dict:
    {
        # 收益
        'total_return': float,
        'cagr': float,
        
        # 风险
        'max_drawdown': float,       # 百分比，如 -0.15 表示 15%
        'max_dd_duration': int,      # 回撤期天数
        'var_95': float,             # 95% VaR
        'cvar_95': float,            # 95% CVaR
        
        # 风险调整收益
        'sharpe': float,
        'sortino': float,
        'calmar': float,             # CAGR / |MaxDD|
        'information_ratio': float,
        
        # 滚动稳定性
        'rolling_sharpe_mean': float,
        'rolling_sharpe_std': float,  # 低=稳定
        
        # 统计显著性
        'deflated_sharpe': float,    # DSR
        'pbo': float,                # 过拟合概率
        
        # 成本
        'annual_turnover': float,
        'cost_ratio': float,         # 年化成本占收益的 %
        
        # 基准
        'excess_vs_benchmark': float,
        'tracking_error': float,
        
        # 分状态
        'bull_sharpe': float,
        'bear_sharpe': float,
    }
    """
```

**TDD 测试** (`tests/test_metrics.py` → `test_flat_returns_zero_sharpe`)：
```python
def test_flat_returns_zero_sharpe():
    """零收益 → Sharpe ≈ 0"""
    returns = pd.Series([1.0] * 100, index=pd.date_range('2020-01-01', periods=100, freq='ME'))
    metrics = compute_all_metrics(returns)
    assert abs(metrics['sharpe']) < 0.01

def test_known_sharpe():
    """已知的月度收益序列 → 验证 Sharpe 计算"""
    # 10 个月，每月 +1% → 年化约 12.7%，std ~0 → Sharpe 很高
    returns = pd.Series(
        [1.0, 1.01, 1.0201, 1.0303, 1.0406, 1.0510, 1.0615, 1.0721, 1.0829, 1.0937],
        index=pd.date_range('2020-01-01', periods=10, freq='ME')
    )
    metrics = compute_all_metrics(returns)
    assert metrics['sharpe'] > 1.0

def test_deflated_sharpe_lower_than_raw():
    """DSR 应该 ≤ 原始 Sharpe（多重检验惩罚）"""
    returns = pd.Series([1.0], index=[pd.Timestamp('2020-01-01')])
    # 模拟 100 次试验
    metrics = compute_all_metrics(
        pd.concat([returns] * 50),  # 50 个月
        n_trials=100
    )
    assert metrics['deflated_sharpe'] <= metrics['sharpe'] + 0.1
```

**成功标准**：
- [ ] 所有测试通过
- [ ] DSR 和 PBO 必须实现（即使简化版），不能只返回 NaN
- [ ] `compute_all_metrics()` 返回的 dict 包含 ≥ 18 个指标
- [ ] 滚动 Sharpe 用 12 个月窗口

---

### Phase 3: 回测引擎

---

#### Task 3.1: Expanding Window 回测框架 `engine/walkforward.py`

**核心类**：`WalkForwardBacktester`

```python
class WalkForwardBacktester:
    def __init__(self, prices, cost_model, strategy_pool,
                 train_years=3, step_months=3, purge_days=5, embargo_days=10):
        """
        prices: 清洗后的价格 DataFrame
        cost_model: CostModel 实例
        strategy_pool: {name: callable} 策略池
        train_years: 初始训练期长度
        step_months: 每步前进月数
        purge_days: purge gap
        embargo_days: embargo gap
        """
    
    def run(self):
        """
        主循环:
          for each step:
            1. 确定 train_end, test_start, test_end（加入 purge/embargo gap）
            2. 在 train_data 上 fit 所有需要 fit 的组件（HMM, 协方差）
            3. 在 test_data 上执行 1 步（一个季度）
            4. 记录净值、权重、信号
            5. 更新 train_end → 进入下一步
        返回: results (净值曲线 + 权重日志 + 信号日志)
        """
```

**TDD 测试** (`tests/test_walkforward.py` → `test_expanding_window`)：
```python
def test_expanding_window_no_lookahead():
    """核心测试：任何 test 日期的数据都不应在 train 中出现"""
    # 用模拟数据
    dates = pd.date_range('2020-01-01', '2025-12-31', freq='B')
    prices = pd.DataFrame({
        'A': np.random.randn(len(dates)).cumsum() + 100,
        'B': np.random.randn(len(dates)).cumsum() + 50,
    }, index=dates)
    
    bt = WalkForwardBacktester(prices, CostModel(), {'equal': lambda rets,cov: np.array([0.5,0.5])},
                               train_years=3, step_months=3)
    results = bt.run()
    
    # 验证: 每个 test 日期都不在对应的 train 集中
    for i, w in enumerate(results.weights_log):
        test_date = w['date']
        train_end = results.train_ends[i]
        assert train_end + timedelta(days=bt.purge_days) < test_date
```

**成功标准**：
- [ ] 测试通过
- [ ] 每个 test 周期的 train 数据只包含 `test_date - purge_days` 之前的日期
- [ ] 回测日志记录每次调仓的 train_end, test_start, test_end
- [ ] 策略池可注入（不硬编码策略列表）
- [ ] 结果包含净值曲线 + 每步权重 + 状态标签

---

#### Task 3.2: Purging + Embargo 验证

**功能**：独立验证 Purge/Embargo 正确性的测试。

**TDD 测试** (`tests/test_walkforward.py` → `test_purge_removes_overlap`)：
```python
def test_purge_removes_overlap():
    """训练集最后一天和测试集第一天之间有 purge gap"""
    ...
    
def test_embargo_removes_post_test():
    """测试集之后的 embargo 期不在下一次训练中"""
    ...
```

**成功标准**：
- [ ] Purge gap: train_end 和 test_start 之间 ≥ 5 个自然日
- [ ] Embargo gap: test_end 之后 ≥ 10 个自然日的数据被排除
- [ ] 测试验证每条 W-F 路径都满足约束

---

#### Task 3.3: HMM 滚动重训 `engine/hmm_detector.py`

**关键改变**：不再 `fit(all_data) → predict(all_data)`，而是每步只 fit 到 train_end。

```python
class RollingHMMDetector:
    def __init__(self, n_states=4):
        self.n_states = n_states
    
    def fit_predict(self, features_up_to_date):
        """只用 <= date 的数据 fit HMM，返回当前状态"""
        scaler = StandardScaler()
        scaled = scaler.fit_transform(features_up_to_date)  # 注意: 这里的标准化只基于历史
        model = hmm.GaussianHMM(n_components=self.n_states, 
                                covariance_type='diag',
                                n_iter=200)
        model.fit(scaled)
        states = model.predict(scaled)
        return states[-1], model, scaler  # 返回最新状态
```

**TDD 测试** (`tests/test_hmm.py` → `test_rolling_fit_no_lookahead`)：
```python
def test_rolling_fit_no_lookahead():
    """HMM 在 2023 年的预测不应依赖 2024 年的数据"""
    # 用截止 2023-12-31 的数据 fit
    # 用截止 2024-12-31 的数据 fit
    # 两次预测的 2023 年状态可能不同（因为模型参数变了），但 2023 年的状态 ID 不应由 2024 数据决定
    ...
```

**成功标准**：
- [ ] 每步只用截至当前的历史数据 fit HMM
- [ ] 标准化参数（mean/std）也仅基于历史数据
- [ ] 输出的状态标签随滚动而更新（不是全局固定）
- [ ] 记录每次 fit 的 BIC 用于后续分析

---

### Phase 4: 双 Agent + 元学习

---

#### Task 4.1: Builder Agent `agents/builder.py`

**职责**：提案策略权重（不直接执行）。

```python
class BuilderAgent:
    def propose(self, market_features, hmm_state, sentiment, strategy_pool):
        """
        输入当前市场快照 → 输出策略提议
        returns: {
            'strategy': 'equal_weight' | 'momentum' | 'risk_parity',
            'weights': np.array,
            'confidence': float,       # 0~1
            'rationale': str,          # 决策理由
        }
        """
```

**TDD 测试** (`tests/test_builder.py` → `test_builder_never_short`)：
```python
def test_builder_never_short():
    """中长期组合不做空"""
    proposal = builder.propose(features, 'BULL', 0.6, pool)
    assert (proposal['weights'] >= 0).all()
    assert abs(proposal['weights'].sum() - 1.0) < 0.01
```

**成功标准**：
- [ ] 在任何状态下都输出合法权重（非负、和为 1）
- [ ] 权重不超过单标的上限（默认 40%）
- [ ] 包含决策理由（可追溯）

---

#### Task 4.2: Critic Agent `agents/critic.py`

**职责**：反向检验 Builder 的提案。使用 `knowledge/checklist.md` 作为依据。

```python
class CriticAgent:
    def __init__(self, checklist_path):
        self.checklist = self.load_checklist(checklist_path)
    
    def review(self, builder_proposal, backtest_context):
        """
        backtest_context: 包含所有可检查的信息
            - train_end, test_start
            - 样本量
            - 参数搜索范围
            - 换手率估算
            - ...
        
        returns: {
            'verdict': 'APPROVE' | 'DOWNGRADE' | 'REJECT',
            'findings': [{'check': '...', 'pass': bool, 'detail': '...'}, ...],
            'adjusted_confidence': float,
        }
        """
```

**checklist.md 至少包含**：

```
# 方法论文档化
□ [ ] 训练/验证/测试集的日期边界是否在代码中有明确注释？
□ [ ] 是否设置了 Purging gap（≥5 交易日）？
□ [ ] HMM 是否只在训练集上 fit？（检查是否有全局标准化）
□ [ ] 滚动指标（vol, corr）是否基于扩窗历史计算？

# 数据质量
□ [ ] 异常值是否已 Winsorize（±5σ）？
□ [ ] 停牌日是否已前向填充（≤3 天）？
□ [ ] 复权是否有验证步骤？

# 统计有效性
□ [ ] 样本外测试的独立调仓次数是否 ≥ 12？
□ [ ] 是否计算了 Deflated Sharpe Ratio？
□ [ ] 是否计算了 PBO？
□ [ ] 参数敏感性分析是否完成（最佳 ±20%）？

# 成本真实性
□ [ ] 佣金是否 ≥ 万 2.5？
□ [ ] 最低佣金（5 元）是否建模？
□ [ ] 滑点是否 ≥ 2bp？
□ [ ] 冲击成本是否随参与率非线性增长？
□ [ ] 年化换手率是否 ≤ 300%？

# 基准对比
□ [ ] 是否对比了沪深 300 买入持有？
□ [ ] 是否对比了等权 ETF 组合（不调仓）？
□ [ ] 是否分牛/熊/震荡状态分别报告？
□ [ ] 是否计算了扣除时间成本后的净超额收益？

# 过拟合检查
□ [ ] 测试集是否只跑过 1 次？
□ [ ] 策略选择是否在验证集上做的（不在测试集上）？
□ [ ] 最好策略 vs 次好策略的差距是否合理（差距过大 = 过拟合）？
```

**TDD 测试** (`tests/test_critic.py` → `test_critic_catches_no_purge`)：
```python
def test_critic_catches_no_purge():
    """如果回测没有 purge gap，Critic 必须报 RED"""
    context = {'train_end': dt(2024,1,1), 'test_start': dt(2024,1,2), ...}
    result = critic.review(builder_proposal, context)
    assert result['findings'][0]['pass'] == False  # purge gap 检查失败
    assert result['verdict'] in ['DOWNGRADE', 'REJECT']
```

**成功标准**：
- [ ] 加载 `knowledge/checklist.md` 并逐项检查
- [ ] 任何检查项不通过 → 降权或否决
- [ ] 被否决的提案附带具体原因和修复建议
- [ ] 输出可追溯（每个 findings 条目有 pass/fail + 详情）

---

#### Task 4.3: Meta-Learner `agents/meta_learner.py`

**职责**：在线学习 Builder 和 Critic 的信誉分，输出概率加权决策。

```python
class MetaLearner:
    def __init__(self, lookback_quarters=8):
        self.history = []     # [(features, proposal, verdict, actual_outcome), ...]
    
    def arbitrate(self, features, builder_proposal, critic_review):
        """返回最终决策"""
        # 1. 查找历史相似情境
        similar = self._find_similar(features, k=5)
        
        # 2. 统计 Builder 和 Critic 在相似情境下的正确率
        builder_acc = self._builder_accuracy(similar)
        critic_acc = self._critic_accuracy(similar)
        
        # 3. 加权融合
        if critic_review['verdict'] == 'REJECT':
            final_weights = self._fallback_strategy()
            confidence = 0.1
        elif critic_review['verdict'] == 'DOWNGRADE':
            final_weights = 0.7 * builder_proposal['weights'] + 0.3 * defense_weights
            confidence = builder_proposal['confidence'] * 0.6
        else:  # APPROVE
            final_weights = builder_proposal['weights']
            confidence = builder_proposal['confidence']
        
        return {'weights': final_weights, 'confidence': confidence,
                'builder_credit': self.builder_credit, 'critic_credit': self.critic_credit}
    
    def update(self, features, final_weights, actual_outcome):
        """在线学习：对比预测 vs 实际，更新双方信誉分"""
        self.history.append(...)
        # 如果 Builder 提案接近最终决策且效果好 → Builder +分
        # 如果 Critic 的警告被验证（后续回撤）→ Critic +分
```

**TDD 测试** (`tests/test_meta_learner.py` → `test_arbitrate_downweights_rejected`)：
```python
def test_arbitrate_downweights_rejected():
    """被 Critic 否决的提案，最终权重应大幅降权"""
    proposal = {'weights': np.array([0.4, 0.4, 0.2, 0, ...]), 'confidence': 0.8}
    review = {'verdict': 'REJECT', 'findings': [...]}
    result = meta.arbitrate(features, proposal, review)
    assert result['confidence'] < 0.3  # 被否决后置信度极低
    # 权重应偏向防守
```

**成功标准**：
- [ ] 相似情境查找基于欧氏距离（特征空间）
- [ ] Builder/Critic 信誉分在 0~1 之间
- [ ] 被 REJECT 的提案权重自动切换到防守策略
- [ ] `update()` 后信誉分发生变化
- [ ] 至少记录 8 个季度的历史

---

#### Task 4.4: 主循环 `agents/orchestrator.py`

**职责**：串联 Builder → Critic → Meta-Learner 的辩论-裁决-更新循环。

```python
class Orchestrator:
    def __init__(self, builder, critic, meta_learner, backtester):
        ...
    
    def run_quarterly_cycle(self, date, market_data):
        """一个季度的完整决策周期"""
        # Step 1: Builder 提案
        proposal = self.builder.propose(...)
        
        # Step 2: Critic 审查
        review = self.critic.review(proposal, context)
        
        # Step 3: Meta-Learner 裁决
        decision = self.meta_learner.arbitrate(features, proposal, review)
        
        # Step 4: 执行 + 记录
        self.execute(decision['weights'], date)
        
        # Step 5: 下个季度回看 → update Meta-Learner
        if self.has_next_quarter_outcome(date):
            actual = self.actual_outcome(date)
            self.meta_learner.update(features, decision['weights'], actual)
        
        return decision
```

**成功标准**：
- [ ] 完整执行一个季度的 Builder→Critic→Meta-Learner→Execute→Update 循环
- [ ] 日志记录每个决策点的输入/输出
- [ ] 不中断运行（任何组件报错时，用等权策略 fallback）

---

### Phase 5: 完整回测 + 验证

---

#### Task 5.1: 端到端回测

**功能**：用 Orchestrator 在 5 年数据上跑完整 Walk-Forward。

```python
# main.py 或直接运行
from core.data import fetch_etf_data, split_data, clean_data
from core.cost import CostModel
from core.metrics import compute_all_metrics
from engine.walkforward import WalkForwardBacktester
from engine.hmm_detector import RollingHMMDetector
from agents.orchestrator import Orchestrator

# 1. 获取 + 清洗数据
prices = fetch_etf_data(years=5)

# 2. 训练/验证/测试切分
train, val, test = split_data(prices, '2024-06-30', '2025-06-30', purge_days=5)

# 3. 在验证集上调参
#   （如果需要的话——但不要用测试集！）

# 4. 锁定参数，在测试集上只跑 1 次
cost_model = CostModel()
orchestrator = Orchestrator(BuilderAgent(), CriticAgent(), MetaLearner(), backtester)
results = orchestrator.run_full_cycle(test)

# 5. 报告指标
metrics = compute_all_metrics(results.equity_curve, benchmark_returns, n_trials=len(STRATEGY_POOL))
print(metrics)
```

**成功标准**：
- [ ] 全程不报错
- [ ] 净值曲线 > 起始值（如果做不到，诚实报告）
- [ ] 权重总和始终在 0.95~1.05 之间
- [ ] Critic 至少触发过 1 次 DOWNGRADE 或 REJECT

---

#### Task 5.2: PBO + DSR 计算

**功能**：用完整的策略选择和调参日志计算 PBO 和 DSR。

```python
def compute_pbo(strategy_returns, n_splits=100):
    """
    CSCV 方法:
    1. 将收益率序列随机切分成 n_splits 对 (IS, OOS)
    2. 在 IS 中排名 → 在 OOS 中排名
    3. PBO = 在 IS 中最优但在 OOS 中低于中位数的概率
    """
    ...

def compute_dsr(sharpe, n_trials, n_obs, skewness, kurtosis):
    """
    Harvey-Liu-Zhu (2016) 公式:
    E[max(SR)] ≈ σ_SR × √(2 × ln(N))
    DSR = Φ((SR* - E[max]) / σ_SR)
    """
    ...
```

**TDD 测试** (`tests/test_pbo.py` → `test_random_strategies_pbo_high`)：
```python
def test_random_strategies_pbo_high():
    """100 个随机策略 → PBO 应 ~0.5（纯噪声）"""
    random_returns = np.random.randn(100, 500) * 0.01  # 100 strategies x 500 days
    pbo = compute_pbo(random_returns)
    assert 0.3 < pbo < 0.7  # 噪声的 PBO 在 0.5 附近
```

**成功标准**：
- [ ] PBO < 0.3（过拟合概率低于 30%）
- [ ] DSR 的 p-value < 0.05（Sharpe 在统计上显著）
- [ ] 如果 PBO > 0.5，必须诚实报告"策略不可信"

---

#### Task 5.3: 最终报告

**产出**：一份约 500 字的结论报告 + 关键指标表格。

**报告模板**：
```
=== AI 量化回测最终报告 ===
日期: 2026-07-07
数据: 9 只 ETF, 2021-07 ~ 2026-07

[策略表现]
CAGR:               X.XX%
Sharpe Ratio:       X.XX
Deflated Sharpe:    X.XX (p = X.XXX)
Sortino Ratio:      X.XX
Calmar Ratio:       X.XX
Max Drawdown:       -XX.X%
Max DD Duration:    XXX 天
PBO:                X.XX

[成本分析]
年化换手率:         XXX%
年化交易成本:        X.XX%
成本占收益比:        XX.X%

[基准对比]
vs 沪深300 超额:     +X.X%
vs 等权持有超额:     +X.X%
扣除时间成本后:      +X.X%

[策略使用分布]
等权:     XX 季度 (XX%)
动量:     XX 季度 (XX%)
风险平价: XX 季度 (XX%)

[Critic 拦截记录]
拦截次数: X 次
降权次数: X 次
否决次数: X 次

[结论]
(一句话总结: 策略是否优于被动持有? 是否值得实盘?)
```

**成功标准**：
- [ ] 报告包含所有指标
- [ ] 如果跑不赢被动持有，诚实说明
- [ ] 如果 PBO > 0.5，明确指出策略不可信
- [ ] 输出文件: `final_report.txt`

---

## 六、执行顺序总结

```
Day 1: Phase 0 + Phase 1
  Task 0.1 → 0.2 → 1.1 → 1.2 → 1.3

Day 2: Phase 2 + Phase 3
  Task 2.1 → 2.2 → 3.1 → 3.2 → 3.3

Day 3: Phase 4 + Phase 5
  Task 4.1 → 4.2 → 4.3 → 4.4 → 5.1 → 5.2 → 5.3
```

每个 Task 完成后:
1. 运行对应测试 → 全部通过
2. 打印一条 `[DONE] Task X.X: 描述`
3. 进入下一个 Task

---

## 七、全局禁止事项

- ❌ 不要在全量数据上 fit 任何模型再"回测"
- ❌ 不要在测试集上跑完后回头调参
- ❌ 不要用全局 mean/std 做标准化
- ❌ 不要假设能以收盘价成交
- ❌ 不要忽略最低佣金
- ❌ 不要只报告 Sharpe（必须包含 DSR 和 PBO）
- ❌ 不要编造好看的假结果——诚实比好看重要

---

**文档版本**: v1.0  
**创建日期**: 2026-07-07  
**目标受众**: Codex AI Agent（非人类读者）
