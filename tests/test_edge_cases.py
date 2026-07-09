"""Edge case tests for the backtesting system."""
import sys; sys.path.insert(0, "D:/妗岄潰/quant_backtest")
import numpy as np; import pandas as pd; import pytest
from core.cost import CostModel
from core.metrics import compute_all_metrics
from engine.walkforward import WalkForwardBacktester


def _make_prices(length=500, n_assets=2):
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=length, freq="B")
    prices = pd.DataFrame({chr(65 + i): np.random.randn(length).cumsum() + 100 for i in range(n_assets)}, index=dates)
    return prices


def test_single_asset():
    prices = _make_prices(n_assets=1)
    bt = WalkForwardBacktester(prices, CostModel(), {"eq": lambda r, c: np.array([1.0])}, train_years=1, step_months=3, purge_days=5)
    r = bt.run()
    assert r["n_steps"] >= 1
    for w in r["weights_log"]:
        assert len(w["weights"]) == 1
        assert abs(w["weights"][0] - 1.0) < 1e-6


def test_constant_prices():
    dates = pd.date_range("2020-01-01", "2022-12-31", freq="B")
    prices = pd.DataFrame({"A": np.ones(len(dates)) * 100, "B": np.ones(len(dates)) * 50}, index=dates)
    bt = WalkForwardBacktester(prices, CostModel(), {"eq": lambda r, c: np.array([0.5, 0.5])}, train_years=1, step_months=3, purge_days=5)
    r = bt.run()
    assert r["n_steps"] >= 1
    assert len(r["equity_curve"]) > 0


def test_minimal_walkforward():
    dates = pd.date_range("2020-01-01", periods=100, freq="B")
    prices = pd.DataFrame({"A": np.random.randn(100).cumsum() + 100}, index=dates)
    bt = WalkForwardBacktester(prices, CostModel(), {"eq": lambda r, c: np.array([1.0])}, train_years=2, step_months=1, purge_days=5)
    try:
        r = bt.run()
        assert r["n_steps"] == 0 or len(r["equity_curve"]) > 0
    except ValueError:
        pass


def test_random_seed_stability():
    prices = _make_prices(length=400)
    strat = {"eq": lambda r, c: np.array([0.5, 0.5])}
    bt1 = WalkForwardBacktester(prices, CostModel(), strat, train_years=1, step_months=3, purge_days=5)
    bt2 = WalkForwardBacktester(prices, CostModel(), strat, train_years=1, step_months=3, purge_days=5)
    pd.testing.assert_series_equal(bt1.run()["equity_curve"], bt2.run()["equity_curve"])


def test_full_run_metrics_smoke():
    prices = _make_prices(length=600, n_assets=3)
    bt = WalkForwardBacktester(prices, CostModel(stamp_duty=0.0005), {"mom": lambda r, c: np.array([0.5, 0.3, 0.2])}, train_years=1, step_months=3, purge_days=5)
    r = bt.run()
    assert r["n_steps"] >= 2
    m = compute_all_metrics(r["equity_curve"])
    assert "sharpe" in m
    assert "max_drawdown" in m
    assert m["total_return"] is not None
