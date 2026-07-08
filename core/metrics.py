# coding: utf-8
"""完整评估指标体系（>=18 项），含 DSR、PBO、滚动 Sharpe。"""
from typing import Dict, Optional

import numpy as np
import pandas as pd
from scipy import stats



def sharpe_confidence_interval(returns, ann_factor=252, risk_free=0.02, confidence=0.95):
    """计算年化 Sharpe Ratio 的 95% 置信区间 (Mertens 2002 / Lo 2002 标准误公式)。

    Parameters
    ----------
    returns : pd.Series
        收益率序列
    ann_factor : int
        年化因子 (252=日频, 12=月频)
    risk_free : float
        年化无风险利率
    confidence : float
        置信水平

    Returns
    -------
    tuple : (lower_bound, sharpe, upper_bound)
    """
    from scipy import stats as sp_stats
    n = len(returns)
    if n < 2:
        return 0.0, 0.0, 0.0
    ann_vol = float(returns.std() * np.sqrt(ann_factor))
    ann_ret = float(returns.mean() * ann_factor)
    sharpe = (ann_ret - risk_free) / ann_vol if ann_vol > 0 else 0.0
    skew = float(returns.skew())
    kurt = float(returns.kurtosis() + 3.0)
    n_years = max(n / ann_factor, 1.0)
    se = float(np.sqrt(max((1.0 + 0.5 * sharpe**2 - skew * sharpe + (kurt - 3.0) / 4.0 * sharpe**2) / n_years, 1e-10)))
    z = float(sp_stats.norm.ppf((1.0 + confidence) / 2.0))
    lower = sharpe - z * se
    upper = sharpe + z * se
    return round(lower, 6), round(sharpe, 6), round(upper, 6)

def compute_all_metrics(
    returns: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
    n_trials: int = 1,
    risk_free: float = 0.02,
) -> Dict[str, float]:
    """计算完整评估指标集（>= 20 项）。

    Parameters
    ----------
    returns : pd.Series
        策略收益率序列（日频或月频）
    benchmark_returns : pd.Series, optional
        基准收益率序列
    n_trials : int
        尝试过的策略/调参组合数（用于 DSR）
    risk_free : float
        无风险利率（年化）

    Returns
    -------
    dict : 指标名称 -> 值
    """
    # 确保无缺失
    returns = returns.dropna()
    if len(returns) < 2:
        return _empty_metrics()

    # 判断频率
    is_monthly = False
    try:
        gaps = returns.index.to_series().diff().dt.days.dropna()
        is_monthly = gaps.median() > 5 if len(gaps) > 0 else False
    except AttributeError:
        pass

    # 年化因子
    ann_factor = 12 if is_monthly else 252

    # --- 基础统计 ---
    total_return = float((1 + returns).prod() - 1)
    n_years = len(returns) / ann_factor
    if n_years > 0 and total_return > -1:
        annual_return = float((1 + total_return) ** (1 / n_years) - 1)
    else:
        annual_return = total_return / max(n_years, 1) if total_return > -1 else -1.0
    volatility = float(returns.std() * np.sqrt(ann_factor))
    sharpe = (annual_return - risk_free) / volatility if volatility > 0 else 0.0

    # --- 偏度 / 峰度 ---
    skewness = float(returns.skew())
    kurtosis = float(returns.kurtosis() + 3)  # Fisher -> regular

    # --- 最大回撤 (MDD) ---
    cum = (1 + returns).cumprod()
    running_max = cum.cummax()
    drawdown = cum / running_max - 1
    max_drawdown = float(drawdown.min())
    # 回撤持续期
    dd_duration = 0
    in_dd = False
    peak_idx = 0
    for i in range(len(drawdown)):
        if drawdown.iloc[i] < 0 and not in_dd:
            in_dd = True
            peak_idx = i
        elif drawdown.iloc[i] == 0 and in_dd:
            dd_duration = max(dd_duration, i - peak_idx)
            in_dd = False
    if in_dd:
        dd_duration = max(dd_duration, len(drawdown) - 1 - peak_idx)

    # --- Sortino ---
    downside = returns[returns < 0]
    downside_vol = float(downside.std() * np.sqrt(ann_factor)) if len(downside) > 0 else 0.0
    sortino = (annual_return - risk_free) / downside_vol if downside_vol > 0 else 0.0

    # --- Calmar ---
    calmar = annual_return / abs(max_drawdown) if max_drawdown < 0 else 0.0

    # --- 胜率 / 盈亏比 ---
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    win_rate = len(wins) / len(returns) if len(returns) > 0 else 0.0
    profit_factor = abs(wins.sum() / losses.sum()) if len(losses) > 0 and losses.sum() != 0 else np.inf

    # --- VaR / CVaR ---
    var_95 = float(returns.quantile(0.05))
    cvar_95 = float(returns[returns <= var_95].mean()) if len(returns[returns <= var_95]) > 0 else var_95

    # --- 滚动 Sharpe (12 个月) ---
    window = min(12 * (21 if not is_monthly else 1), len(returns) // 2)
    if window >= 2:
        roll_sharpe = returns.rolling(window).apply(
            lambda x: x.mean() / x.std() * np.sqrt(ann_factor) if x.std() > 0 else 0,
            raw=True,
        )
        roll_sharpe_mean = float(roll_sharpe.dropna().mean())
    else:
        roll_sharpe_mean = sharpe

    # --- DSR ---
    # n_obs must be in the same time scale as Sharpe. Sharpe is annualized, so n_obs = years.
    n_obs = max(len(returns) / ann_factor, 1.5)
    dsr_result = compute_dsr(sharpe, n_trials, n_obs, skewness, kurtosis)

    # --- 超额收益 ---
    excess_return = annual_return - risk_free
    if benchmark_returns is not None:
        bench = benchmark_returns.dropna()
        bench_cum = (1 + bench).prod()
        bench_n_years = len(bench) / ann_factor
        bench_ann = float(bench_cum ** (1 / bench_n_years) - 1) if bench_n_years > 0 else 0.0
        excess_vs_bench = annual_return - bench_ann
    else:
        excess_vs_bench = 0.0

    # --- Sharpe Confidence Interval (T7) ---
    ci_lower, _, ci_upper = sharpe_confidence_interval(returns, ann_factor, risk_free)
    metrics = {
        "total_return": round(total_return, 6),
        "annual_return": round(annual_return, 6),
        "volatility": round(volatility, 6),
        "sharpe": round(sharpe, 6),
        "sharpe_ci_lower": ci_lower,
        "sharpe_ci_upper": ci_upper,
        "sharpe_ci_level": "95%",
        "deflated_sharpe": round(dsr_result["deflated_sharpe"], 6),
        "dsr_p_value": round(dsr_result["p_value"], 6),
        "sortino": round(sortino, 6),
        "calmar": round(calmar, 6),
        "max_drawdown": round(max_drawdown, 6),
        "max_dd_duration_days": int(dd_duration),
        "win_rate": round(win_rate, 6),
        "profit_factor": round(profit_factor, 6),
        "excess_return": round(excess_return, 6),
        "excess_vs_benchmark": round(excess_vs_bench, 6),
        "skewness": round(skewness, 6),
        "kurtosis": round(kurtosis, 6),
        "rolling_sharpe_12m": round(roll_sharpe_mean, 6),
        "var_95": round(var_95, 6),
        "cvar_95": round(cvar_95, 6),
        "period_return_mean": round(float(returns.mean()), 6),
        "period_vol": round(float(returns.std()), 6),
        "freq": "monthly" if is_monthly else "daily",
    }

    return metrics


def compute_dsr(
    sharpe: float,
    n_trials: int,
    n_obs: int,
    skewness: float = 0.0,
    kurtosis: float = 3.0,
) -> Dict[str, float]:
    """计算 Deflated Sharpe Ratio（Harvey-Liu-Zhu 2016）。

    Parameters
    ----------
    sharpe : float
        年化 Sharpe Ratio
    n_trials : int
        尝试的策略/调参总数
    n_obs : int
        观测期数
    skewness : float
        收益偏度（默认 0）
    kurtosis : float
        收益峰度（默认 3，正态分布）

    Returns
    -------
    dict : {"deflated_sharpe", "p_value", "e_max"}
    """
    if n_trials <= 1:
        return {"deflated_sharpe": sharpe, "p_value": 1.0, "e_max": 0.0}

    var_SR = (1 + 0.5 * skewness * sharpe - 0.25 * (kurtosis - 3) * sharpe ** 2) / (n_obs - 1)
    sigma_SR = np.sqrt(max(var_SR, 1e-10))
    e_max = sigma_SR * np.sqrt(2 * np.log(n_trials))

    if sigma_SR <= 1e-10 or n_obs < 1.0:  # need >= 1 year of data for meaningful DSR
        return {"deflated_sharpe": sharpe, "p_value": 1.0, "e_max": 0.0}

    dsr_raw = (sharpe - e_max) / sigma_SR
    dsr = float(np.clip(dsr_raw, -50.0, 50.0))
    p_value = float(np.clip(1.0 - stats.norm.cdf(dsr_raw), 0.0, 1.0))

    return {"deflated_sharpe": round(dsr, 6), "p_value": round(p_value, 6), "e_max": round(e_max, 6)}


def compute_pbo(strategy_returns_matrix: np.ndarray, n_splits: int = 100, random_state: int = 42) -> float:
    """计算回测过拟合概率 (PBO) — CSCV 方法。"""
    n_strategies, n_obs = strategy_returns_matrix.shape
    if n_strategies < 2 or n_obs < 10:
        return 0.5

    count_below_median = 0
    rng = np.random.RandomState(random_state)
    for _ in range(n_splits):
        # Random shuffle for CSCV: each split independent, no chronological overlap
        all_idx = np.arange(n_obs)
        rng.shuffle(all_idx)
        split = rng.randint(n_obs // 3, 2 * n_obs // 3)
        is_rets = strategy_returns_matrix[:, all_idx[:split]]
        oos_rets = strategy_returns_matrix[:, all_idx[split:]]

        is_sharpe = np.nan_to_num(
            is_rets.mean(axis=1) / np.maximum(is_rets.std(axis=1), 1e-10), nan=0.0
        )
        best_idx = int(np.argmax(is_sharpe))

        oos_sharpe = np.nan_to_num(
            oos_rets.mean(axis=1) / np.maximum(oos_rets.std(axis=1), 1e-10), nan=0.0
        )

        # 如果一半以上的策略在 OOS 中表现优于最佳 IS 策略 -> 过拟合
        better_count = int((oos_sharpe > oos_sharpe[best_idx]).sum())
        if better_count >= n_strategies // 2:
            count_below_median += 1

    return count_below_median / n_splits


def estimate_effective_trials(strategy_returns):
    """使用 ONC 层次聚类估计有效独立试验数 K。"""
    try:
        from scipy.cluster.hierarchy import fcluster, linkage
        from sklearn.metrics import silhouette_score
    except ImportError:
        return max(strategy_returns.shape[0] // 2, 1)

    n_variants = strategy_returns.shape[0]
    if n_variants <= 1:
        return 1

    corr = np.corrcoef(strategy_returns)
    dist = 1 - np.abs(corr)
    triu = dist[np.triu_indices_from(dist, k=1)]
    if len(triu) == 0:
        return 1
    Z = linkage(triu, method="ward")

    best_k = 1
    best_score = -1
    max_k = min(n_variants - 1, 20)
    for k in range(2, max_k + 1):
        labels = fcluster(Z, k, criterion="maxclust")
        if len(set(labels)) < 2:
            continue
        try:
            score = silhouette_score(dist, labels, metric="precomputed")
            if score > best_score:
                best_score = score
                best_k = k
        except Exception:
            continue
    return best_k


def _empty_metrics() -> Dict[str, float]:
    """返回空的指标字典（数据不足时）。"""
    keys = [
        "total_return", "annual_return", "volatility", "sharpe",
        "deflated_sharpe", "dsr_p_value", "sortino", "calmar",
        "max_drawdown", "max_dd_duration_days", "win_rate", "profit_factor",
        "excess_return", "excess_vs_benchmark", "skewness", "kurtosis",
        "rolling_sharpe_12m", "var_95", "cvar_95", "period_return_mean",
        "period_vol", "freq",
    ]
    return {k: 0.0 for k in keys}

