"""Test data module."""
import sys
import logging
sys.path.insert(0, "D:\\桌面")

from core.data import fetch_etf_data, split_data


def test_fetch_returns_valid_data():
    """获取的数据必须满足基本约束"""
    logging.basicConfig(level=logging.WARNING)
    df = fetch_etf_data(days=365)

    assert df.shape[0] >= 200, f"Expected >=200 rows, got {df.shape[0]}"
    assert df.shape[1] == 9, f"Expected 9 columns, got {df.shape[1]}"
    assert df.index.is_monotonic_increasing, "Index should be sorted ascending"
    assert df.isnull().sum().sum() == 0, "No missing values allowed"
    assert (df > 0).all().all(), "All prices must be > 0"
    print("[PASS] test_fetch_returns_valid_data")


def test_clean_pipeline():
    """清洗后数据不应有任何不合理值"""
    logging.basicConfig(level=logging.WARNING)
    df = fetch_etf_data(days=365)
    returns = df.pct_change().dropna()

    for col in returns.columns:
        assert (returns[col].abs() < 0.20).all(), f"{col} has extreme returns"

    for col in df.columns:
        flat_days = (df[col].diff() == 0).rolling(4).sum().fillna(0)
        assert (flat_days < 4).all(), f"{col} has >3 consecutive flat days"

    for col in returns.columns:
        assert returns[col].std() < 0.05, f"{col} volatility too high after winsorization"

    print("[PASS] test_clean_pipeline")


def test_split_no_overlap():
    """训练/验证/测试三段必须无日期重叠且有 purge gap"""
    logging.basicConfig(level=logging.WARNING)
    df = fetch_etf_data(days=365 * 5)
    train, val, test = split_data(df, "2024-06-30", "2025-06-30", purge_days=5)

    # 无重叠
    assert train.index.max() < val.index.min(), "Train and val overlap"
    assert val.index.max() < test.index.min(), "Val and test overlap"

    # Purge gap 存在（至少 3 个交易日 ≈ 3 自然日）
    assert (val.index.min() - train.index.max()).days >= 3, "Train-val purge gap too small"
    assert (test.index.min() - val.index.max()).days >= 3, "Val-test purge gap too small"

    # 三段的并集条数 <= 原始数据条数
    total = len(train) + len(val) + len(test)
    assert total <= len(df), f"Split total {total} > original {len(df)}"

    print("[PASS] test_split_no_overlap")


if __name__ == "__main__":
    test_fetch_returns_valid_data()
    test_clean_pipeline()
    test_split_no_overlap()
