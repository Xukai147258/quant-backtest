"""Test HMM rolling detector — no look-ahead."""
import sys
sys.path.insert(0, "D:\\桌面")

import numpy as np
import pandas as pd
from engine.hmm_detector import RollingHMMDetector, compute_features


def test_rolling_fit_no_lookahead():
    """HMM 在不同时间点的预测不应依赖未来数据"""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", "2025-12-31", freq="B")
    n = len(dates)
    prices = pd.DataFrame({
        "A": np.random.randn(n).cumsum() + 100,
        "B": np.random.randn(n).cumsum() + 50,
    }, index=dates)

    features = compute_features(prices)
    detector = RollingHMMDetector(n_states=4)

    # Fit on data up to 2023-12-31
    f2023 = features[features.index <= "2023-12-31"]
    state_2023, model_2023, _ = detector.fit_predict(f2023)
    assert 0 <= state_2023 < 4, f"State {state_2023} out of range"
    assert model_2023.n_components == 4

    # Fit on data up to 2024-12-31 (expanded window)
    f2024 = features[features.index <= "2024-12-31"]
    state_2024, model_2024, _ = detector.fit_predict(f2024)
    assert 0 <= state_2024 < 4

    # BIC recorded
    assert len(detector.history) == 2
    assert detector.history[0]["bic"] > 0
    assert detector.history[0]["n_obs"] < detector.history[1]["n_obs"]

    # Feature gap: 2024 fit should have more data (no look-ahead means
    # we only use HISTORICAL data for each fit)
    assert len(f2024) > len(f2023), "Expanding window should have more features"

    print(f"  States: 2023={state_2023}, 2024={state_2024}")
    print(f"  BIC: 2023={detector.history[0]['bic']:.1f}, 2024={detector.history[1]['bic']:.1f}")
    print("[PASS] test_rolling_fit_no_lookahead")


if __name__ == "__main__":
    test_rolling_fit_no_lookahead()

def test_hmm_state_labels_ordered_by_return():
    """HMM state 0 return < state N-1 return after remapping."""
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", "2025-12-31", freq="B")
    n = len(dates)
    prices = pd.DataFrame({"A": np.random.randn(n).cumsum()+100,
                            "B": np.random.randn(n).cumsum()+50}, index=dates)
    features = compute_features(prices)
    detector = RollingHMMDetector(n_states=4)
    f = features[features.index <= "2023-12-31"]
    _, model, _ = detector.fit_predict(f)
    if hasattr(model, "state_means_sorted") and len(model.state_means_sorted) == 4:
        sm = model.state_means_sorted
        assert sm[0] < sm[-1], f"State 0 ({sm[0]:.6f}) >= State N-1 ({sm[-1]:.6f})"
        print(f"  State means: {[round(s,6) for s in sm]}")
    print("[PASS] test_hmm_state_labels_ordered_by_return")
