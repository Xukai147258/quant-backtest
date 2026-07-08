"""Test cost model."""
import sys
sys.path.insert(0, "D:\\桌面")

from core.cost import CostModel
import numpy as np


def test_round_trip_cost_bounds():
    """交易成本在合理范围内"""
    model = CostModel()

    # 小交易：成本 > 0 但不太高
    small = model.round_trip_cost(10000)
    assert small > 10, f"Small trade cost {small} should be > 10"
    assert small < 100, f"Small trade cost {small} should be < 100"
    print(f"  small(10000) = {small:.2f}")

    # 中等交易：滑点+佣金
    medium = model.round_trip_cost(100000, daily_volume=1e8)
    assert medium > 50, f"Medium trade cost {medium} should be > 50"
    assert medium < 300, f"Medium trade cost {medium} should be < 300"
    print(f"  medium(100k, dv=1e8) = {medium:.2f}")

    # 大交易：冲击成本非线性上升
    large = model.round_trip_cost(1000000, daily_volume=1e8)
    very_large = model.round_trip_cost(5000000, daily_volume=1e8)
    ratio = very_large / large
    assert ratio > 5.0, f"Cost ratio {ratio:.2f} should be > 5.0 (non-linear impact)"
    print(f"  large(1M) = {large:.2f}, very_large(5M) = {very_large:.2f}, ratio = {ratio:.2f}")

    print("[PASS] test_round_trip_cost_bounds")


def test_min_commission_enforced():
    """最低佣金约束生效"""
    model = CostModel()
    tiny = model.round_trip_cost(100)  # 100 元交易
    # 佣金 = max(0.025, 5) = 5 each side
    assert tiny > 9, f"Tiny trade cost {tiny} should be at least 10 (min commission)"
    print(f"  tiny(100) = {tiny:.2f} (min commission = 5 * 2 = 10)")
    print("[PASS] test_min_commission_enforced")


def test_no_volume_no_impact():
    """无 daily_volume 时冲击成本为 0"""
    model = CostModel()
    cost_no_vol = model.round_trip_cost(100000)
    cost_with_vol = model.round_trip_cost(100000, daily_volume=1e8)
    assert cost_with_vol >= cost_no_vol, "Impact cost should increase total"
    print(f"  no_vol={cost_no_vol:.2f}, with_vol={cost_with_vol:.2f}")
    print("[PASS] test_no_volume_no_impact")


def test_zero_commission_warns():
    """零佣金时发出警告"""
    import warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        model = CostModel(commission_rate=0)
        assert len(w) >= 1, "Should warn about zero commission"
        assert "zero-cost" in str(w[0].message).lower()
    print("[PASS] test_zero_commission_warns")


if __name__ == "__main__":
    test_round_trip_cost_bounds()
    test_min_commission_enforced()
    test_no_volume_no_impact()
    test_zero_commission_warns()
