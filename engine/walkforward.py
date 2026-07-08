# coding: utf-8
"""Expanding Window 回测框架，含 Purging + Embargo。"""
import logging
from typing import Dict, Callable, Optional, List, Any
from datetime import timedelta

import pandas as pd
import numpy as np
from core.cost import CostModel

logger = logging.getLogger(__name__)


class WalkForwardBacktester:
    """Expanding Window Walk-Forward 回测器。

    Parameters
    ----------
    prices : pd.DataFrame
        清洗后的价格数据，index=datetime
    cost_model : CostModel
        交易成本模型
    strategy_pool : dict
        {name: callable(returns, cov) -> np.array(weights)}
    train_years : int
        初始训练窗口年数
    step_months : int
        每步前进月数
    purge_days : int
        Purging gap 天数
    embargo_days : int
        Embargo gap 天数
    """

    def __init__(
        self,
        prices: pd.DataFrame,
        cost_model: CostModel,
        strategy_pool: Dict[str, Callable],
        train_years: int = 3,
        step_months: int = 3,
        purge_days: int = 5,
        embargo_days: int = 10,
        initial_investment: float = 1_000_000.0,
    ):
        self.prices = prices
        self.cost_model = cost_model
        self.strategy_pool = strategy_pool
        self.train_years = train_years
        self.step_months = step_months
        self.purge_days = purge_days
        self.embargo_days = embargo_days
        self.initial_investment = initial_investment

    def run(self) -> Dict[str, Any]:
        """运行 Expanding Window 回测。

        Returns
        -------
        dict : {
            "equity_curve": pd.Series,   # 净值曲线
            "weights_log": list[dict],   # 权重日志，每条含 date, weights
            "signal_log": list[dict],    # 信号日志
            "train_ends": list,          # 每步的 train_end 日期
            "test_starts": list,         # 每步的 test_start 日期
            "test_ends": list,           # 每步的 test_end 日期
        }
        """
        idx = self.prices.index
        start_date = idx[0]

        # 初始 train_end = start + train_years
        first_train_end = start_date + pd.DateOffset(years=self.train_years)
        first_train_end_idx = idx.searchsorted(first_train_end)
        if first_train_end_idx >= len(idx):
            raise ValueError("Not enough data for initial training window")

        equity_series = []
        equity_dates = []
        weights_log: list = []
        signal_log: list = []
        train_ends: list = []
        test_starts: list = []
        test_ends: list = []

        step = 0
        prev_test_end_date = None
        portfolio_value = 1.0
        prev_weights: Optional[np.ndarray] = None

        max_steps = 100
        while True:
            if step >= max_steps:
                logger.warning("WalkForward exceeded %d steps", max_steps)
                break
            current_train_end_date = first_train_end + pd.DateOffset(months=step * self.step_months)
            train_end_idx = idx.searchsorted(current_train_end_date)
            if train_end_idx >= len(idx):
                break
            train_end_date = idx[train_end_idx]

            # Purging: 训练集截至 train_end - purge_days
            train_cutoff = train_end_date - timedelta(days=self.purge_days)
            train_mask = idx <= train_cutoff
            # T1: Embargo exclusion — 排除上一轮测试期及其前后的数据
            if prev_test_end_date is not None:
                embargo_start = prev_test_end_date  # Lopez de Prado: embargo starts AT test_end, not test_end - purge
                embargo_end = prev_test_end_date + timedelta(days=self.embargo_days)
                train_mask = train_mask & ~((idx >= embargo_start) & (idx <= embargo_end))

            if train_mask.sum() < 20:
                break
            train_data = self.prices.loc[idx[train_mask]]

            # Test 起始：train_end 之后 > purge_days 的第一个交易日
            test_start_mask = idx > train_end_date + timedelta(days=self.purge_days)
            if not test_start_mask.any():
                break
            test_start_date = idx[test_start_mask][0]
            assert (test_start_date - train_end_date).days >= self.purge_days, \
                f"Purge/Embargo violation: test_start={test_start_date}, train_end={train_end_date}, purge_days={self.purge_days}"

            # Test 结束：test_start + step_months
            test_end_candidate = test_start_date + pd.DateOffset(months=self.step_months)
            test_end_idx = min(idx.searchsorted(test_end_candidate), len(idx) - 1)
            test_end_date = idx[test_end_idx]
            test_data = self.prices.loc[test_start_date:test_end_date]

            if len(test_data) < 2:
                break

            # --- 训练期计算 ---
            train_returns = train_data.pct_change().dropna()
            if len(train_returns) < 5:
                break
            train_cov = train_returns.cov()

            # --- 执行策略 ---
            pool_items = list(self.strategy_pool.items())
            strategy_name, strategy_fn = pool_items[0]
            weights = strategy_fn(train_returns, train_cov)
            weights = np.asarray(weights, dtype=float)
            if not np.all(np.isfinite(weights)):
                n_a = self.prices.shape[1]
                weights = np.ones(n_a) / n_a

            if prev_weights is not None:
                turnover = np.abs(weights - prev_weights).sum()
                # Use nominal trade value = initial_investment * current portfolio_value * turnover
                trade_value = self.initial_investment * portfolio_value * turnover
                abs_cost = self.cost_model.round_trip_cost(trade_value)
                cost_pct = abs_cost / max(self.initial_investment * portfolio_value, self.initial_investment)
                cost_pct = min(cost_pct, 0.005)  # cap at 0.5% of portfolio
                portfolio_value *= (1.0 - cost_pct)
                equity_series.append(portfolio_value)
                equity_dates.append(test_data.index[0])
                cost = abs_cost
            else:
                turnover = 0.0
                cost = 0.0

            # --- 测试期收益 ---
            test_rets = test_data.pct_change().iloc[1:]
            port_rets = test_rets.dot(weights)
            for dt_idx, r in port_rets.items():
                portfolio_value *= (1 + r)
                equity_series.append(portfolio_value)
                equity_dates.append(dt_idx)

            weights_log.append({
                "date": test_start_date,
                "strategy": strategy_name,
                "weights": weights.tolist(),
                "turnover": turnover,
                "train_count": int(train_mask.sum()),
            })
            train_ends.append(train_end_date)
            test_starts.append(test_start_date)
            test_ends.append(test_end_date)
            prev_weights = weights
            prev_test_end_date = test_end_date  # store for next iteration's embargo
            step += 1

        equity_curve = pd.Series(equity_series, index=pd.DatetimeIndex(equity_dates)) if len(equity_dates) > 0 else pd.Series(equity_series, dtype=float)


        return {
            "equity_curve": equity_curve,
            "weights_log": weights_log,
            "signal_log": signal_log,
            "train_ends": train_ends,
            "test_starts": test_starts,
            "test_ends": test_ends,
            "n_steps": step,
        }


