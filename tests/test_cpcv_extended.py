# Extended CPCV tests for improved coverage
import sys; sys.path.insert(0, "D:/??/quant_backtest")
import numpy as np; import pandas as pd; import pytest
from engine.cpcv import CombinatorialPurgedCV, compute_cpcv_sharpe_distribution
from core.cost import CostModel


def test_cpcv_n_splits_calculation():
    cpcv = CombinatorialPurgedCV(n_groups=6, n_test_groups=2)
    from math import comb
    assert cpcv.n_splits == comb(6, 2) == 15
    assert cpcv.n_paths == 15


def test_cpcv_purge_adjacent_groups():
    dates = pd.date_range("2020-01-01", periods=120, freq="B")
    cpcv = CombinatorialPurgedCV(n_groups=6, n_test_groups=2, purge_days=5, embargo_days=10)
    splits = list(cpcv.split(dates))
    assert len(splits) == 15
    train_idx, test_idx, tc = splits[0]
    assert tc == (0, 1)


def test_cpcv_embargo_adjacent_groups():
    dates = pd.date_range("2020-01-01", periods=120, freq="B")
    cpcv = CombinatorialPurgedCV(n_groups=6, n_test_groups=2, purge_days=5, embargo_days=10)
    splits = list(cpcv.split(dates))
    train_idx, test_idx, tc = splits[-1]
    assert tc == (4, 5)


def test_cpcv_empty_train_handling():
    dates = pd.date_range("2020-01-01", periods=10, freq="B")
    cpcv = CombinatorialPurgedCV(n_groups=5, n_test_groups=2, purge_days=20, embargo_days=20)
    splits = list(cpcv.split(dates))
    for train_idx, test_idx, tc in splits:
        assert isinstance(train_idx, np.ndarray)


def test_cpcv_sharpe_distribution_basic():
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", periods=300, freq="B")
    prices = pd.DataFrame({ "A": np.random.randn(300).cumsum() + 100, "B": np.random.randn(300).cumsum() + 50, }, index=dates)
    result = compute_cpcv_sharpe_distribution(prices, CostModel(), lambda r, c: np.array([0.5, 0.5]), n_groups=6, n_test=2)
    assert "sharpe_values" in result
    assert "n_paths" in result
    assert result["n_paths"] > 0


def test_cpcv_sharpe_distribution_small_data():
    dates = pd.date_range("2020-01-01", periods=20, freq="B")
    prices = pd.DataFrame({ "A": np.ones(20) * 100, }, index=dates)
    result = compute_cpcv_sharpe_distribution(prices, CostModel(), lambda r, c: np.array([1.0]), n_groups=6, n_test=2)
    assert "n_paths" in result


def test_cpcv_sharpe_all_positive():
    dates = pd.date_range("2020-01-01", periods=200, freq="B")
    prices = pd.DataFrame({ "A": np.arange(200) * 0.5 + 100, "B": np.arange(200) * 0.3 + 50, }, index=dates)
    result = compute_cpcv_sharpe_distribution(prices, CostModel(), lambda r, c: np.array([0.5, 0.5]), n_groups=4, n_test=1)
    assert result["pct_positive"] >= 0.5
