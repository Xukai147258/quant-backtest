 # 核心概念速查：Lopez de Prado 回测方法论
 
 > 本文档是执行计划第三章知识库的扩展版，包含完整定义、数学公式和 Python 伪代码。
 
 ---
 
 ## 1. Purging（清洗泄漏）
 
 ### 定义
 从训练集中删除任何标签区间与测试集标签区间有重叠的样本。
 
 ### 为什么
 在金融时间序列中，一个训练标签（如未来 5 天收益）可能和测试标签的窗口重叠，导致模型"看到未来"。
 
 ### 怎么做
 在训练集末尾和测试集开头之间设置一个 `purge_days` 的间隙，将该间隙内的样本从训练集中移除。
 
 ### Python 伪代码
 ```python
 import pandas as pd
 from datetime import timedelta
 
 def purge_train(train: pd.DataFrame, test_start: pd.Timestamp, purge_days: int = 5) -> pd.DataFrame:
     """
     从训练集中删除与测试集时间窗口重叠的样本。
     
     Parameters
     ----------
     train : DataFrame
         原始训练数据（含日期索引）
     test_start : Timestamp
         测试集开始日期
     purge_days : int
         清洗窗口（交易日数）
     
     Returns
     -------
     DataFrame : 清洗后的训练数据
     """
     purge_boundary = test_start - timedelta(days=purge_days)
     return train[train.index <= purge_boundary].copy()
 ```
 
 ---
 
 ## 2. Embargo（禁运区）
 
 ### 定义
 在测试集之后额外设置一段"禁运区"，该区域的数据也不能进入训练集。
 
 ### 为什么
 即使标签不重叠，市场反应滞后或序列自相关仍可导致泄漏。Embargo 提供了额外的安全边际。
 
 ### 怎么做
 设置 `embargo_days = purge_days * 1%`（通常 5~10 天），在每次滚动时确保测试集结束后的 embargo 期内数据不被用于下一次训练。
 
 ### Python 伪代码
 ```python
 def apply_embargo(train: pd.DataFrame, test_end: pd.Timestamp, embargo_days: int = 10) -> pd.DataFrame:
     """
     从训练集中排除测试集结束后 embargo 期内的样本。
     
     Parameters
     ----------
     train : DataFrame
         原始训练数据
     test_end : Timestamp
         测试集结束日期
     embargo_days : int
         禁运天数
     
     Returns
     -------
     DataFrame : 应用禁运后的训练数据
     """
     embargo_boundary = test_end + timedelta(days=embargo_days)
     return train[train.index <= embargo_boundary].copy()
 ```
 
 ---
 
 ## 3. Combinatorial Purged Cross-Validation (CPCV)
 
 ### 定义
 不使用单一时间路径，而是用 C(N,k) 种组合生成多条回测路径。每条路径在不同的 train/test 组合上评估。
 
 ### 为什么
 单次 Walk-Forward 的回测结果高度依赖起点和窗口大小。CPCV 给出 **Sharpe 的分布**，而不是单点估计。
 
 ### 数学公式
 将数据分为 N 组，选择 k 组作为测试集，共有 C(N, k) 种组合。每种组合：
 - 训练集 = 除这 k 组外的其余 N-k 组（并应用 purging/embargo）
 - 测试集 = 这 k 组
 对于每种组合，计算策略在测试集上的 Sharpe Ratio，得到 Sharpe 的分布。
 
 ### 推荐配置
 - N = 6 组（总组数）
 - k = 2（测试组数）
 - 生成 C(6,2) = 15 条路径
 
 ### Python 伪代码
 ```python
 import itertools
 import numpy as np
 
 def cp_cv_sharpe_distribution(returns_series, n_groups=6, n_test=2):
     """
     使用 CPCV 方法计算 Sharpe Ratio 的分布。
     
     Parameters
     ----------
     returns_series : array-like
         策略的日收益率序列
     n_groups : int
         总组数
     n_test : int
         每组中作为测试的组数
     
     Returns
     -------
     list : 每条路径的 Sharpe Ratio 列表
     """
     np.random.shuffle(returns_series)
     groups = np.array_split(returns_series, n_groups)
     indices = list(range(n_groups))
     sharpe_list = []
     
     for test_idx in itertools.combinations(indices, n_test):
         test = np.concatenate([groups[i] for i in test_idx])
         train_idx = [i for i in indices if i not in test_idx]
         # train 需要应用 purging（略）
         sharpe = test.mean() / test.std() * np.sqrt(252)
         sharpe_list.append(sharpe)
     
     return sharpe_list
 ```
 
 ---
 
 ## 4. Probability of Backtest Overfitting (PBO)
 
 ### 定义
 在 CSCV（对称交叉验证）框架下，"训练集表现最好"的策略在测试集中排名低于中位数的概率。
 
 ### 阈值
 - PBO > 0.5 → 策略选择本质上是随机的，不可用
 - PBO < 0.3 → 过拟合概率低
 
 ### 数学公式
 ```
 PBO = (1 / N_splits) * Σ I[rank_OOS(Strategy_best_IS) > N_strategies / 2]
 ```
 其中 I[·] 是指示函数。
 
 ### Python 伪代码
 ```python
 def compute_pbo(strategy_returns_matrix, n_splits=100):
     """
     计算回测过拟合概率 (PBO)。
     
     Parameters
     ----------
     strategy_returns_matrix : ndarray, shape (n_strategies, n_obs)
         每个策略的收益序列
     n_splits : int
         CSCV 随机分割次数
     
     Returns
     -------
     float : PBO 值 (0~1)
     """
     n_strategies, n_obs = strategy_returns_matrix.shape
     count_below_median = 0
     
     for _ in range(n_splits):
         # 随机分割样本内/样本外
         split_point = np.random.randint(n_obs // 3, 2 * n_obs // 3)
         is_returns = strategy_returns_matrix[:, :split_point]
         oos_returns = strategy_returns_matrix[:, split_point:]
         
         # 样本内排名
         is_sharpe = is_returns.mean(axis=1) / is_returns.std(axis=1)
         best_idx = np.argmax(is_sharpe)
         
         # 样本外排名
         oos_sharpe = oos_returns.mean(axis=1) / oos_returns.std(axis=1)
         oos_rank = np.argsort(oos_sharpe).tolist().index(best_idx)
         
         if oos_rank >= n_strategies / 2:
             count_below_median += 1
     
     return count_below_median / n_splits
 ```
 
 ---
 
 ## 5. Deflated Sharpe Ratio (DSR)
 
 ### 定义
 考虑多重检验后的 Sharpe Ratio。如果你试了 100 种策略，最高 Sharpe 的"真空"期望值是 ~√(2×ln(100)) × σ。
 
 ### 公式
 ```
 DSR = P[Sharpe* > E[max(Sharpe_1, ..., Sharpe_N)]]
     ≈ Φ( (Sharpe* - E[max]) / σ_sharpe )
 ```
 其中 E[max] ≈ σ × √(2 × ln(N_trials))（极值理论）。
 更精确的公式（Harvey-Liu-Zhu 2016）考虑偏度和峰度：
 ```
 E[max] = σ_SR × (1 - γ) × Φ^{-1}(1 - 1/N) + γ × Φ^{-1}(1 - 1/N × e^{-1})
 ```
 
 ### 阈值
 DSR 对应的 p-value < 0.05 才算显著。
 
 ### Python 伪代码
 ```python
 from scipy import stats
 import numpy as np
 
 def compute_dsr(sharpe: float, n_trials: int, n_obs: int,
                 skewness: float = 0.0, kurtosis: float = 3.0) -> dict:
     """
     计算 Deflated Sharpe Ratio (DSR)。
     
     Parameters
     ----------
     sharpe : float
         策略的年化 Sharpe Ratio
     n_trials : int
         尝试的策略总数（含调参组合）
     n_obs : int
         观测期数（年化后的期数）
     skewness : float
         收益偏度（默认 0，正态分布）
     kurtosis : float
         收益峰度（默认 3，正态分布）
     
     Returns
     -------
     dict : {'deflated_sharpe': float, 'p_value': float, 'e_max': float}
     """
     # Sharpe 的标准误差（考虑偏度和峰度）
     var_SR = (1 + 0.5 * skewness * sharpe - 
               0.25 * (kurtosis - 3) * sharpe**2) / (n_obs - 1)
     sigma_SR = np.sqrt(var_SR)
     
     # E[max] 近似
     e_max = sigma_SR * np.sqrt(2 * np.log(n_trials))
     
     # DSR
     if sigma_SR <= 0:
         return {'deflated_sharpe': sharpe, 'p_value': 1.0, 'e_max': 0}
     
     dsr = (sharpe - e_max) / sigma_SR
     p_value = 1 - stats.norm.cdf(dsr)
     
     return {
         'deflated_sharpe': dsr,
         'p_value': p_value,
         'e_max': e_max
     }
 ```
 
 ---
 
 ## 6. 7 Deadly Sins of Backtesting 速查
 
 | Sin | 问题 | 解决方案 |
 |-----|------|----------|
 | Survivorship Bias | 只回测现在还活着的标的 | 使用历史成分列表 |
 | Look-Ahead Bias | 训练数据包含了未来信息 | Purging + Embargo |
 | Data Snooping | 在同一数据集上反复调参 | PBO + DSR 检验 |
 | Ignoring Transaction Costs | 假设零成本交易 | CostModel 建模 |
 | Outlier-Driven Success | 少数极端日贡献了大部分收益 | Winsorize + 鲁棒检验 |
 | Shorting Constraints | 假设能做空但不计成本 | 权重约束 ≥ 0 |
 | Storytelling | 数据挖掘穿上了叙事的外衣 | 数学依据 + 基准对比 |
 
 ---
 
 ## 参考文献
 - Lopez de Prado, M. (2018). *Advances in Financial Machine Learning*. Wiley.
 - Harvey, C. R., Liu, Y., & Zhu, H. (2016). "...and the Cross-Section of Expected Returns". *Review of Financial Studies*.
 - Bailey, D. H., & Lopez de Prado, M. (2014). "The Deflated Sharpe Ratio: Correcting for Multiple Testing".
 - Bailey, D. H., et al. (2016). "The Probability of Backtest Overfitting".
