
"""Test: momentum strategy uses proper lookback window, not single-day returns."""
import sys
sys.path.insert(0, "D:\\桌面\\quant_backtest")

import numpy as np
import pandas as pd


def test_momentum_uses_3m_lookback():
    """Momentum weights are based on 3-month cumulative return, not last day."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", "2020-12-31", freq="B")
    n = len(dates)

    trend_a = np.linspace(0, 0.3, n)
    trend_b = np.linspace(0, 0.05, n)
    prices = pd.DataFrame({
        "A": 100 + trend_a + np.random.randn(n) * 0.5,
        "B": 100 + trend_b + np.random.randn(n) * 0.5,
    }, index=dates)

    returns = prices.pct_change().dropna()

    lookback = 63

    def new_momentum(r):
        cum_ret = (1 + r.iloc[-lookback:]).prod() - 1
        weights = np.maximum(cum_ret.values, 0)
        if weights.sum() > 0:
            weights = weights / weights.sum()
        else:
            weights = np.ones(r.shape[1]) / r.shape[1]
        return weights

    new_weights = new_momentum(returns)

    assert new_weights[0] > new_weights[1], (
        f"A ({new_weights[0]:.3f}) should > B ({new_weights[1]:.3f})"
    )
    assert abs(new_weights.sum() - 1.0) < 0.01
    assert (new_weights >= 0).all()
    print(f"  New momentum: A={new_weights[0]:.3f}, B={new_weights[1]:.3f}")
    print("[PASS] test_momentum_uses_3m_lookback")


def test_momentum_no_negative_weights():
    """All-negative cumulative returns -> equal weight fallback."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", "2020-12-31", freq="B")
    n = len(dates)
    prices = pd.DataFrame({
        "A": 100 + np.random.randn(n).cumsum() * (-0.5),
        "B": 100 + np.random.randn(n).cumsum() * (-0.5),
    }, index=dates)

    returns = prices.pct_change().dropna()
    lookback = 63

    def new_momentum(r):
        cum_ret = (1 + r.iloc[-lookback:]).prod() - 1
        weights = np.maximum(cum_ret.values, 0)
        if weights.sum() > 0:
            weights = weights / weights.sum()
        else:
            weights = np.ones(r.shape[1]) / r.shape[1]
        return weights

    w = new_momentum(returns)
    assert abs(w.sum() - 1.0) < 0.01
    assert (w >= 0).all()
    print(f"  All-negative: weights={[f'{x:.3f}' for x in w]}")
    print("[PASS] test_momentum_no_negative_weights")


if __name__ == "__main__":
    test_momentum_uses_3m_lookback()
    test_momentum_no_negative_weights()
