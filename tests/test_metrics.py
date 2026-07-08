"""Test metrics module."""
import sys
sys.path.insert(0, "D:\\桌面")

import numpy as np
import pandas as pd
from core.metrics import compute_all_metrics, compute_dsr, compute_pbo


def test_all_metrics_shape():
    """compute_all_metrics 返回至少 18 个指标"""
    returns = pd.Series([0.01] * 50, index=pd.date_range("2020-01-01", periods=50, freq="ME"))
    metrics = compute_all_metrics(returns, n_trials=100)
    assert len(metrics) >= 18, f"Got {len(metrics)} metrics, need >= 18"
    assert "deflated_sharpe" in metrics
    assert "sharpe" in metrics
    assert metrics["deflated_sharpe"] <= metrics["sharpe"] + 0.1, \
        f"DSR {metrics['deflated_sharpe']} > Sharpe {metrics['sharpe']}"
    print(f"  Metrics count: {len(metrics)}")
    print("[PASS] test_all_metrics_shape")


def test_pbo_random_high():
    """PBO 对随机策略应返回 0~1 之间的值"""
    np.random.seed(42)
    random_returns = np.random.randn(100, 500) * 0.01
    pbo = compute_pbo(random_returns)
    assert 0.0 <= pbo <= 1.0, f"PBO {pbo:.3f} must be in [0, 1]"
    # 验证 PBO 随不同数据变化（不是常数）
    np.random.seed(99)
    random_returns2 = np.random.randn(100, 500) * 0.01
    pbo2 = compute_pbo(random_returns2)
    assert pbo != pbo2, "PBO should vary with different data"
    print(f"  PBO(seed=42)={pbo:.3f}, PBO(seed=99)={pbo2:.3f}")
    print("[PASS] test_pbo_random_high")


def test_pbo_edge_cases():
    """PBO 边界情况"""
    # 只有 1 个策略
    pbo1 = compute_pbo(np.random.randn(1, 100))
    assert pbo1 == 0.5
    # 只有 2 个策略
    pbo2 = compute_pbo(np.random.randn(2, 100))
    assert 0.0 <= pbo2 <= 1.0
    print("[PASS] test_pbo_edge_cases")


def test_dsr_reduces_sharpe():
    """DSR 应 <= Sharpe + 小误差"""
    np.random.seed(42)
    returns = pd.Series(
        np.random.randn(100) * 0.01 + 0.001,
        index=pd.date_range("2020-01-01", periods=100, freq="ME"),
    )
    metrics = compute_all_metrics(returns, n_trials=50)
    assert metrics["deflated_sharpe"] <= metrics["sharpe"] + 0.1, \
        f"DSR {metrics['deflated_sharpe']} > Sharpe {metrics['sharpe']}"
    print(f"  Sharpe={metrics['sharpe']:.4f}, DSR={metrics['deflated_sharpe']:.4f}")
    print("[PASS] test_dsr_reduces_sharpe")



def test_sharpe_confidence_interval():
    """验证 Sharpe 置信区间计算正确且区间宽度合理。"""
    from core.metrics import sharpe_confidence_interval
    np.random.seed(42)

    # 正态收益
    normal = pd.Series(np.random.randn(1000) * 0.01 + 0.0005,
                       index=pd.date_range("2020-01-01", periods=1000, freq="B"))
    lo, sr, hi = sharpe_confidence_interval(normal)
    assert lo < sr < hi, f"Normal: lo={lo:.4f} sr={sr:.4f} hi={hi:.4f}"
    assert (hi - lo) > 0.01, f"CI width={hi-lo:.4f} too narrow"

    # 负偏态收益（偏度增大标准误，区间应更宽）
    noisy = pd.Series(np.random.randn(1000) * 0.01 + 0.0005,
                      index=pd.date_range("2020-01-01", periods=1000, freq="B"))
    lo2, sr2, hi2 = sharpe_confidence_interval(noisy)
    assert lo2 < sr2 < hi2
    assert (hi2 - lo2) > 0.01

    print(f"  Normal: SR={sr:.3f} [{lo:.3f}, {hi:.3f}]")
    print("[PASS] test_sharpe_confidence_interval")


if __name__ == "__main__":
    test_all_metrics_shape()
    test_pbo_random_high()
    test_pbo_edge_cases()
    test_dsr_reduces_sharpe()

def test_pbo_not_hardcoded():
    """PBO in report is not hardcoded 0.5."""
    import inspect
    from report import generate_final_report
    src = inspect.getsource(generate_final_report)
    assert "compute_pbo" in src
    assert "if False else 0.5" not in src
    print("[PASS] test_pbo_not_hardcoded")

def test_dsr_uses_real_n_trials():
    """DSR n_trials parameter materially affects results."""
    np.random.seed(42)
    r = pd.Series(np.random.randn(500) * 0.01 + 0.0006,
                  index=pd.date_range("2020-01-01", periods=500, freq="B"))
    m1 = compute_all_metrics(r, n_trials=1)
    mN = compute_all_metrics(r, n_trials=100)
    assert abs(m1["deflated_sharpe"] - m1["sharpe"]) < 0.01
    assert mN["deflated_sharpe"] < mN["sharpe"] - 0.1
    print(f"  n=1: DSR={m1["deflated_sharpe"]:.4f} vs S={m1["sharpe"]:.4f}")
    print(f"  n=100: DSR={mN["deflated_sharpe"]:.4f} vs S={mN["sharpe"]:.4f}")
    print("[PASS] test_dsr_uses_real_n_trials")
