"""Test walkforward backtester — Purging & Embargo."""
import sys
sys.path.insert(0, "D:\\桌面")

import numpy as np
import pandas as pd
from datetime import timedelta

from core.cost import CostModel
from engine.walkforward import WalkForwardBacktester


def _make_mock_prices():
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", "2025-12-31", freq="B")
    prices = pd.DataFrame({
        "A": np.random.randn(len(dates)).cumsum() + 100,
        "B": np.random.randn(len(dates)).cumsum() + 50,
    }, index=dates)
    return prices


def test_expanding_window_no_lookahead():
    """任何 test 日期的数据都不应在 train 中出现"""
    prices = _make_mock_prices()
    bt = WalkForwardBacktester(
        prices, CostModel(),
        {"equal": lambda rets, cov: np.array([0.5, 0.5])},
        train_years=3, step_months=3, purge_days=5, embargo_days=10,
    )
    results = bt.run()
    assert results["n_steps"] >= 2

    for i, w in enumerate(results["weights_log"]):
        test_date = w["date"]
        train_end = results["train_ends"][i]
        min_allowed = train_end + timedelta(days=bt.purge_days)
        assert test_date > min_allowed, \
            f"Step {i}: test_date={test_date.date()} <= train_end+purge={min_allowed.date()}"
        wts = np.array(w["weights"])
        assert abs(wts.sum() - 1.0) < 0.01

    print(f"  Steps: {results['n_steps']}")
    print("[PASS] test_expanding_window_no_lookahead")


def test_purge_removes_overlap():
    """训练集最后一天和测试集第一天之间有 purge gap"""
    prices = _make_mock_prices()
    bt = WalkForwardBacktester(
        prices, CostModel(),
        {"equal": lambda rets, cov: np.array([0.5, 0.5])},
        train_years=3, step_months=3, purge_days=5,
    )
    results = bt.run()
    for i in range(results["n_steps"]):
        train_end = results["train_ends"][i]
        test_start = results["test_starts"][i]
        gap = (test_start - train_end).days
        assert gap >= bt.purge_days, \
            f"Step {i}: gap {gap}d < purge {bt.purge_days}d"
    print("[PASS] test_purge_removes_overlap")


def test_embargo_removes_post_test():
    """测试集之后的 embargo 期不在下一次训练中"""
    prices = _make_mock_prices()
    bt = WalkForwardBacktester(
        prices, CostModel(),
        {"equal": lambda rets, cov: np.array([0.5, 0.5])},
        train_years=3, step_months=3, purge_days=5, embargo_days=10,
    )
    results = bt.run()
    for i in range(1, results["n_steps"]):
        prev_test_end = results["test_ends"][i - 1]
        curr_train_end = results["train_ends"][i]
        # 下一次训练不应包含 previous_test_end + embargo 内的数据
        emb_boundary = prev_test_end + timedelta(days=bt.embargo_days)
        assert curr_train_end <= emb_boundary, \
            f"Step {i}: train_end={curr_train_end.date()} > prev_test_end+embargo={emb_boundary.date()}"
    print("[PASS] test_embargo_removes_post_test")


if __name__ == "__main__":
    test_expanding_window_no_lookahead()
    test_purge_removes_overlap()
    test_embargo_removes_post_test()



def test_embargo_actually_excludes_data():
    """Verifies embargo excludes data from training set (compare train_count)."""
    np.random.seed(42)
    # Small data (2 yr) to keep test fast
    dates = pd.date_range("2020-01-01", "2022-03-31", freq="B")
    prices = pd.DataFrame({
        "A": np.random.randn(len(dates)).cumsum() + 100,
        "B": np.random.randn(len(dates)).cumsum() + 50,
    }, index=dates)

    strat = {"eq": lambda r, c: np.array([0.5, 0.5])}

    bt_em = WalkForwardBacktester(prices, CostModel(), strat,
        train_years=1, step_months=2, purge_days=3, embargo_days=10)
    r_em = bt_em.run()

    bt_no = WalkForwardBacktester(prices, CostModel(), strat,
        train_years=1, step_months=2, purge_days=3, embargo_days=0)
    r_no = bt_no.run()

    assert r_em["n_steps"] >= 2, "Need >=2 steps for embargo test"
    assert r_no["n_steps"] >= 2, "Need >=2 steps for no-embargo test"

    ok = True
    for i in range(1, min(r_em["n_steps"], r_no["n_steps"])):
        tc_em = r_em["weights_log"][i].get("train_count", 0)
        tc_no = r_no["weights_log"][i].get("train_count", 0)
        if tc_em >= tc_no and tc_no > 0:
            ok = False
            raise AssertionError(
                f"Step {i}: embargo={tc_em} >= no_embargo={tc_no}. "
                "Embargo zone NOT excluded from training!"
            )
    print("[PASS] test_embargo_actually_excludes_data")
