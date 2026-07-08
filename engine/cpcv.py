"""CPCV: Combinatorial Purged Cross-Validation (De Prado 2018 Ch.12)."""
from itertools import combinations
import numpy as np


class CombinatorialPurgedCV:
    def __init__(self, n_groups=6, n_test_groups=2, purge_days=5, embargo_days=10):
        self.n_groups = n_groups
        self.n_test_groups = n_test_groups
        self.purge_days = purge_days
        self.embargo_days = embargo_days
        from math import comb
        self.n_splits = comb(n_groups, n_test_groups)
        # 回测路径数 = 所有 test group 组合数 (De Prado 2018 Ch.12)
        self.n_paths = int(self.n_splits)

    def split(self, timestamps):
        n = len(timestamps)
        gs = n // self.n_groups
        groups = [np.arange(i*gs, min((i+1)*gs, n)) for i in range(self.n_groups)]
        for tc in combinations(range(self.n_groups), self.n_test_groups):
            test_idx = np.concatenate([groups[i] for i in tc])
            train_parts = []
            for i in range(self.n_groups):
                if i in tc:
                    continue
                idx = groups[i]
                if (i-1) in tc:
                    cut = min(self.purge_days, len(idx))
                    idx = idx[:-cut] if cut > 0 else idx
                if (i+1) in tc:
                    cut = min(self.embargo_days, len(idx))
                    idx = idx[cut:] if cut > 0 else idx
                if len(idx) > 0:
                    train_parts.append(idx)
            train_idx = np.concatenate(train_parts) if train_parts else np.array([], dtype=int)
            yield train_idx, test_idx, tc



def compute_cpcv_sharpe_distribution(prices, cost_model, strategy_fn, n_groups=6, n_test=2):
    """使用 CPCV 计算 Sharpe Ratio 分布。
    
    将价格数据分为 n_groups 组，生成 C(n_groups, n_test) 条 train/test 路径，
    对每条路径计算策略的 Sharpe Ratio，返回分布。
    
    Returns
    -------
    dict : {"sharpe_values": list, "mean_sharpe": float, "median_sharpe": float,
            "std_sharpe": float, "pct_positive": float, "n_paths": int}
    """
    cpcv = CombinatorialPurgedCV(n_groups=n_groups, n_test_groups=n_test)
    sharpe_values = []
    
    for train_idx, test_idx, tc in cpcv.split(prices.index):
        train_prices = prices.iloc[train_idx]
        test_prices = prices.iloc[test_idx]
        if len(train_prices) < 20 or len(test_prices) < 2:
            continue
        train_rets = train_prices.pct_change().dropna()
        test_rets = test_prices.pct_change().dropna()
        if len(train_rets) < 5 or len(test_rets) < 2:
            continue
        cov = train_rets.cov()
        weights = strategy_fn(train_rets, cov)
        weights = np.asarray(weights, dtype=float)
        if not np.all(np.isfinite(weights)):
            weights = np.ones(prices.shape[1]) / prices.shape[1]
        port_rets = test_rets.dot(weights)
        sr = float(port_rets.mean() / max(port_rets.std(), 1e-10) * np.sqrt(252))
        sharpe_values.append(sr)
    
    if not sharpe_values:
        return {"sharpe_values": [], "mean_sharpe": 0.0, "median_sharpe": 0.0,
                "std_sharpe": 0.0, "pct_positive": 0.0, "n_paths": 0}
    
    arr = np.array(sharpe_values)
    return {
        "sharpe_values": sharpe_values,
        "mean_sharpe": float(np.mean(arr)),
        "median_sharpe": float(np.median(arr)),
        "std_sharpe": float(np.std(arr)),
        "pct_positive": float((arr > 0).mean()),
        "n_paths": len(sharpe_values),
    }
