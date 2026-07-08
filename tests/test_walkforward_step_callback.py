
"""Test: WalkForward on_step_end callback is called per step."""
import sys
sys.path.insert(0, "D:\\桌面\\quant_backtest")

import numpy as np
import pandas as pd
from engine.walkforward import WalkForwardBacktester
from core.cost import CostModel


def test_step_callback_called_once_per_step():
    """on_step_end callback is called exactly once per walkforward step."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", "2025-12-31", freq="B")
    prices = pd.DataFrame({
        "A": np.cumsum(np.random.randn(len(dates))) + 100,
        "B": np.cumsum(np.random.randn(len(dates))) + 50,
    }, index=dates)

    pool = {"eq": lambda r, c: np.ones(2) / 2}
    cm = CostModel()

    call_count = 0
    call_args = []

    def cb(step_info):
        nonlocal call_count
        call_count += 1
        call_args.append(step_info)

    bt = WalkForwardBacktester(prices, cm, pool, train_years=3, step_months=6,
                               on_step_end=cb)
    res = bt.run()

    assert call_count == res["n_steps"], (
        f"Expected {res['n_steps']} calls, got {call_count}"
    )
    assert len(call_args) == res["n_steps"]
    # Check step_info has expected keys
    for info in call_args:
        assert "test_start" in info, f"Missing test_start in {info}"
        assert "test_end" in info, f"Missing test_end in {info}"
        assert "weights" in info, f"Missing weights in {info}"
        assert "portfolio_return" in info, f"Missing portfolio_return in {info}"
        assert "test_returns" in info, f"Missing test_returns in {info}"
    print(f"  Steps: {res['n_steps']}, callback called {call_count} times")
    print("[PASS] test_step_callback_called_once_per_step")


def test_step_callback_no_callback_is_noop():
    """Without on_step_end, WalkForward runs normally."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", "2025-12-31", freq="B")
    prices = pd.DataFrame({
        "A": np.cumsum(np.random.randn(len(dates))) + 100,
        "B": np.cumsum(np.random.randn(len(dates))) + 50,
    }, index=dates)

    pool = {"eq": lambda r, c: np.ones(2) / 2}
    cm = CostModel()
    bt = WalkForwardBacktester(prices, cm, pool, train_years=3, step_months=6)
    res = bt.run()
    assert res["n_steps"] > 0, "Should have at least 1 step"
    assert len(res["equity_curve"]) > 0
    print(f"  Steps: {res['n_steps']}, no callback, no crash")
    print("[PASS] test_step_callback_no_callback_is_noop")


if __name__ == "__main__":
    test_step_callback_called_once_per_step()
    test_step_callback_no_callback_is_noop()
