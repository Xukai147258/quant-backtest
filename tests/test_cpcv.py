"""Test CPCV multi-path cross-validation."""
import sys; sys.path.insert(0, "D:\\桌面")
import numpy as np; import pandas as pd
from engine.cpcv import CombinatorialPurgedCV

def test_cpcv_produces_multiple_paths():
    timestamps = pd.date_range("2020-01-01", "2024-12-31", freq="B")
    cpcv = CombinatorialPurgedCV(n_groups=6, n_test_groups=2)
    splits = list(cpcv.split(timestamps))
    assert len(splits) == 15, f"Expected 15 splits, got {len(splits)}"
    assert cpcv.n_paths == 15, f"Expected 15 paths, got {cpcv.n_paths}"
    for train_idx, test_idx, _ in splits:
        overlap = set(train_idx) & set(test_idx)
        assert len(overlap) == 0, f"Overlap: {len(overlap)}"
    print(f"  Splits: {len(splits)}, Paths: {cpcv.n_paths}")
    print("[PASS] test_cpcv_produces_multiple_paths")

def test_cpcv_no_overlap_in_indices():
    """CPCV 中任一组 train/test 不应有索引重叠。"""
    cpcv = CombinatorialPurgedCV(n_groups=6, n_test_groups=2, purge_days=3, embargo_days=3)
    timestamps = pd.date_range("2020-01-01", "2024-12-31", freq="B")
    for train_idx, test_idx, _ in cpcv.split(timestamps):
        assert len(set(train_idx) & set(test_idx)) == 0, "Train/test index overlap detected!"
    print("[PASS] test_cpcv_no_overlap_in_indices")

if __name__ == "__main__":
    test_cpcv_produces_multiple_paths()
    test_cpcv_no_data_leakage()

def test_sentiment_not_hardcoded():
    """sentiment values change with market regime."""
    from main import compute_trend_sentiment
    np.random.seed(42)
    n = 300
    bull = pd.DataFrame({"A": 100 + np.arange(n)*0.1 + np.random.randn(n)*0.5},
                         index=pd.date_range("2020-01-01", periods=n, freq="B"))
    bear = pd.DataFrame({"A": 100 - np.arange(n)*0.1 + np.random.randn(n)*0.5},
                         index=pd.date_range("2020-01-01", periods=n, freq="B"))
    s_bull = compute_trend_sentiment(bull)
    s_bear = compute_trend_sentiment(bear)
    assert s_bull > 0.5, f"Bull sentiment {s_bull:.3f} should be > 0.5"
    assert s_bear < 0.5, f"Bear sentiment {s_bear:.3f} should be < 0.5"
    assert s_bull - s_bear > 0.1, f"Spread {s_bull-s_bear:.3f} too small"
    print(f"  Bull: {s_bull:.3f}, Bear: {s_bear:.3f}")
    print("[PASS] test_sentiment_not_hardcoded")
