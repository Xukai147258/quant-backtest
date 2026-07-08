
"""Test: WalkForward actually uses the builder-selected strategy."""
import sys
sys.path.insert(0, "D:\\桌面\\quant_backtest")

import numpy as np
import pandas as pd
from engine.walkforward import WalkForwardBacktester
from core.cost import CostModel


def test_walkforward_uses_strategy_name():
    """WalkForward uses the strategy_name to select from pool, not pool_items[0]."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", "2025-12-31", freq="B")
    prices = pd.DataFrame({
        "A": np.cumsum(np.random.randn(len(dates))) + 100,
        "B": np.cumsum(np.random.randn(len(dates))) + 50,
    }, index=dates)

    # Track which strategy actually gets called
    called_strategies = []

    def eq_fn(r, c):
        called_strategies.append("eq")
        return np.ones(2) / 2
    def mom_fn(r, c):
        called_strategies.append("mom")
        return np.array([0.8, 0.2])
    def rp_fn(r, c):
        called_strategies.append("rp")
        return np.array([0.5, 0.5])
    def def_fn(r, c):
        called_strategies.append("def")
        return np.array([0.3, 0.7])

    pool = {"eq": eq_fn, "mom": mom_fn, "rp": rp_fn, "def": def_fn}
    cm = CostModel()

    # Pass a strategy_name selector that always picks "mom"
    bt = WalkForwardBacktester(
        prices, cm, pool,
        train_years=3, step_months=6, purge_days=5, embargo_days=10,
        strategy_name="mom"
    )
    res = bt.run()

    assert len(called_strategies) > 0, "No strategy was ever called"
    for name in called_strategies:
        assert name == "mom", f"Expected 'mom', got '{name}'"
    assert len(called_strategies) == res["n_steps"], (
        f"Expected {res['n_steps']} calls, got {len(called_strategies)}"
    )
    print(f"  Steps: {res['n_steps']}, all used strategy: 'mom'")
    print("[PASS] test_walkforward_uses_strategy_name")


def test_walkforward_defaults_to_first_strategy():
    """Without strategy_name, WalkForward still uses pool_items[0] for backward compat."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", "2025-12-31", freq="B")
    prices = pd.DataFrame({
        "A": np.cumsum(np.random.randn(len(dates))) + 100,
        "B": np.cumsum(np.random.randn(len(dates))) + 50,
    }, index=dates)

    called = []
    pool = {
        "first": lambda r, c: (called.append("first"), np.ones(2)/2)[1],
        "second": lambda r, c: (called.append("second"), np.array([0.9, 0.1]))[1],
    }
    cm = CostModel()
    bt = WalkForwardBacktester(prices, cm, pool, train_years=3, step_months=6)
    res = bt.run()
    for name in called:
        assert name == "first", f"Expected backward compat 'first', got '{name}'"
    print(f"  Steps: {res['n_steps']}, backward compat uses 'first'")
    print("[PASS] test_walkforward_defaults_to_first_strategy")


if __name__ == "__main__":
    test_walkforward_uses_strategy_name()
    test_walkforward_defaults_to_first_strategy()
