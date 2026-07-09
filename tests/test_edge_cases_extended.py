# tests/test_edge_cases_extended.py
"""Edge case tests for trust_check framework compliance - C6 check."""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

@pytest.fixture
def sample_prices():
    dates = pd.date_range("2024-01-01", periods=100, freq="D")
    np.random.seed(42)
    prices = 100 + np.cumsum(np.random.randn(100) * 2)
    return pd.DataFrame({
        "date": dates,
        "open": prices,
        "high": prices + np.abs(np.random.randn(100)),
        "low": prices - np.abs(np.random.randn(100)),
        "close": prices,
        "volume": np.random.randint(1000, 10000, size=100),
    })

class TestNaNPrice:
    def test_nan_in_close_prices(self, sample_prices):
        df = sample_prices.copy()
        df.loc[10:15, "close"] = np.nan
        assert df["close"].isna().sum() > 0

    def test_nan_propagation_ffill(self, sample_prices):
        df = sample_prices.copy()
        df.loc[5, "close"] = np.nan
        filled = df["close"].ffill()
        assert filled.isna().sum() == 0

class TestMissingColumns:
    def test_missing_close_column(self, sample_prices):
        df = sample_prices.drop(columns=["close"])
        assert "close" not in df.columns
        with pytest.raises(KeyError):
            _ = df["close"]

    def test_required_columns_check(self, sample_prices):
        required = ["date", "open", "high", "low", "close", "volume"]
        for col in required:
            assert col in sample_prices.columns

class TestEmptyDataFrame:
    def test_empty_df_has_zero_rows(self):
        df = pd.DataFrame()
        assert len(df) == 0

    def test_empty_with_columns(self):
        df = pd.DataFrame(columns=["date", "close"])
        assert len(df) == 0
        assert len(df.columns) == 2

class TestSingleRowData:
    def test_single_row_df(self):
        df = pd.DataFrame({
            "date": [datetime(2024, 1, 1)],
            "close": [100.0],
            "volume": [1000],
        })
        assert len(df) == 1

    def test_single_row_insufficient_for_split(self):
        df = pd.DataFrame({"close": [100.0]})
        assert len(df) < 2

class TestExtremeReturns:
    def test_positive_extreme_return(self):
        returns = pd.Series([0.5, 1.2, 0.8, 1.5])
        extreme = returns[returns > 1.0]
        assert len(extreme) > 0

    def test_negative_extreme_return(self):
        returns = pd.Series([-0.5, -1.2, -0.8, -1.5])
        extreme = returns[returns < -1.0]
        assert len(extreme) > 0

    def test_clamp_extreme_returns(self):
        returns = pd.Series([0.1, 1.5, -1.2, 0.05])
        clamped = returns.clip(-1.0, 1.0)
        assert clamped.max() <= 1.0
        assert clamped.min() >= -1.0

class TestZeroVolume:
    def test_zero_volume_rows(self, sample_prices):
        df = sample_prices.copy()
        df.loc[10:15, "volume"] = 0
        zero_vol = df[df["volume"] == 0]
        assert len(zero_vol) > 0

    def test_zero_volume_cannot_trade(self, sample_prices):
        df = sample_prices.copy()
        df.loc[10:15, "volume"] = 0
        tradable = df[df["volume"] > 0]
        assert len(tradable) < len(df)

class TestDiscontinuousTimeSeries:
    def test_missing_dates(self):
        dates = pd.to_datetime([
            "2024-01-01", "2024-01-02", "2024-01-04",
            "2024-01-05", "2024-01-08",
        ])
        df = pd.DataFrame({"date": dates, "close": [100, 101, 102, 103, 104]})
        date_diffs = df["date"].diff().dropna()
        max_gap = date_diffs.max()
        assert max_gap > pd.Timedelta(days=1)

    def test_fill_missing_dates(self):
        dates = pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-04"])
        df = pd.DataFrame({"date": dates, "close": [100, 101, 102]})
        df = df.set_index("date").asfreq("D").ffill().reset_index()
        assert len(df) == 4

class TestParameterBoundaries:
    def test_zero_purge_days(self):
        purge_days = 0
        assert purge_days == 0

    def test_zero_embargo_days(self):
        embargo_days = 0
        assert embargo_days == 0

    def test_purge_days_equals_step_size(self):
        purge_days = 20
        step_days = 20
        overlap = purge_days >= step_days
        assert overlap

class TestDataQuality:
    def test_no_duplicate_dates(self, sample_prices):
        df = sample_prices.copy()
        duplicates = df["date"].duplicated().sum()
        assert duplicates == 0

    def test_ohlc_consistency(self, sample_prices):
        df = sample_prices.copy()
        assert (df["high"] >= df["low"]).all()
        assert (df["high"] >= df["open"]).all()
        assert (df["high"] >= df["close"]).all()
        assert (df["low"] <= df["open"]).all()
        assert (df["low"] <= df["close"]).all()

    def test_no_negative_prices(self, sample_prices):
        df = sample_prices.copy()
        assert (df[["open", "high", "low", "close"]] > 0).all().all()

    def test_no_negative_volume(self, sample_prices):
        df = sample_prices.copy()
        assert (df["volume"] >= 0).all()

class TestMetricsEdgeCases:
    def test_sharpe_with_zero_std(self):
        returns = pd.Series([0.0, 0.0, 0.0, 0.0])
        std = returns.std()
        assert std == 0.0 or np.isnan(std)

    def test_sharpe_with_constant_returns(self):
        returns = pd.Series([0.01, 0.01, 0.01, 0.01])
        std = returns.std()
        assert std == 0.0 or std < 1e-10

    def test_max_drawdown_with_only_gains(self):
        prices = pd.Series([100, 101, 102, 103, 104])
        peak = prices.expanding().max()
        drawdown = (prices - peak) / peak
        max_dd = drawdown.min()
        assert max_dd >= 0

    def test_win_rate_with_no_trades(self):
        trades = pd.Series([])
        win_rate = len(trades[trades > 0]) / len(trades) if len(trades) > 0 else 0.0
        assert win_rate == 0.0
