"""Test Dual-Agent + Meta-Learner modules."""
import sys
sys.path.insert(0, "D:\\桌面")

import numpy as np
import pandas as pd
from datetime import datetime

from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.meta_learner import MetaLearner
from agents.meta_learner import EGMetaLearner
from agents.orchestrator import Orchestrator


def _make_mock_data():
    rets = pd.DataFrame(np.random.randn(100, 9) * 0.01,
                        index=pd.date_range("2020-01-01", periods=100, freq="B"))
    pool = {
        "equal_weight": lambda r: np.ones(9) / 9,
        "momentum": lambda r: np.abs(r.iloc[-1].values) / max(np.abs(r.iloc[-1]).sum(), 1e-10),
        "risk_parity": lambda r: (1 / np.maximum(r.std(), 1e-10)) / (1 / np.maximum(r.std(), 1e-10)).sum(),
        "defensive": lambda r: np.array([0.05] * 6 + [0.25, 0.25, 0.10]),
    }
    features = {"returns": rets.iloc[-60:]}
    return rets, pool, features


def test_builder_never_short():
    """中长线组合不做空"""
    _, pool, features = _make_mock_data()
    builder = BuilderAgent(max_weight=0.4)
    proposal = builder.propose(features, "BULL", 0.6, pool)
    assert (proposal["weights"] >= 0).all(), "Negative weights detected"
    assert abs(proposal["weights"].sum() - 1.0) < 0.01, f"Weights sum to {proposal['weights'].sum()}"
    assert "strategy" in proposal
    assert "confidence" in proposal
    assert "rationale" in proposal
    print(f"  Strategy: {proposal['strategy']}, weights sum={proposal['weights'].sum():.2f}")
    print("[PASS] test_builder_never_short")


def test_critic_catches_no_purge():
    """如果回测没有 purge gap，Critic 必须报 RED"""
    _, pool, features = _make_mock_data()
    builder = BuilderAgent()
    proposal = builder.propose(features, "BULL", 0.6, pool)

    # 回测上下文：train_end 和 test_start 没有间隔 -> 违反 Purging
    bad_context = {
        "train_end": datetime(2024, 1, 1),
        "test_start": datetime(2024, 1, 2),
        "n_samples": 500,
        "embargo_days": 0,
    }
    critic = CriticAgent()
    result = critic.review(proposal, bad_context)

    purge_failures = [f for f in result["findings"] if not f["pass"] and "Purging" in f["check"]]
    assert len(purge_failures) > 0, "Should catch purge gap violation"
    assert result["verdict"] in ("DOWNGRADE", "REJECT"), \
        f"Expected DOWNGRADE/REJECT, got {result['verdict']}"
    print(f"  Verdict: {result['verdict']}, failures: {result['failed']}")
    print("[PASS] test_critic_catches_no_purge")


def test_arbitrate_downweights_rejected():
    """被 Critic 否决的提案，最终权重应大幅降权"""
    _, pool, features = _make_mock_data()
    meta = MetaLearner(n_assets=9)

    proposal = {"weights": np.array([0.4, 0.3, 0.1, 0.05, 0.05, 0.05, 0.025, 0.025, 0.0]),
                "confidence": 0.8}
    review = {"verdict": "REJECT", "findings": [], "adjusted_confidence": 0.0}

    result = meta.arbitrate(features, proposal, review)
    assert result["confidence"] < 0.3, f"Confidence {result['confidence']} should be < 0.3"
    assert abs(result["weights"].sum() - 1.0) < 0.01
    assert all(result["weights"] >= 0)
    print(f"  Confidence: {result['confidence']:.2f}, weights sum: {result['weights'].sum():.2f}")
    print("[PASS] test_arbitrate_downweights_rejected")


def test_meta_credit_update():
    """update 后信誉分发生变化"""
    meta = MetaLearner(n_assets=9)
    init_b = meta.builder_credit
    init_c = meta.critic_credit

    # 正收益 -> Builder 加分
    meta.update({}, np.ones(9) / 9, 0.02)
    assert meta.builder_credit > init_b, "Builder credit should rise on positive outcome"
    assert meta.critic_credit < init_c, "Critic credit should fall on positive outcome"

    # 负收益 -> Builder 减分, Critic 加分
    after_pos_b = meta.builder_credit
    after_pos_c = meta.critic_credit
    meta.update({}, np.ones(9) / 9, -0.02)
    assert meta.builder_credit < after_pos_b, "Builder credit should fall on negative outcome"
    assert meta.critic_credit > after_pos_c, "Critic credit should rise on negative outcome"

    print(f"  Builder: {init_b:.2f} -> {after_pos_b:.2f} -> {meta.builder_credit:.2f}")
    print("[PASS] test_meta_credit_update")


if __name__ == "__main__":
    test_builder_never_short()
    test_critic_catches_no_purge()
    test_arbitrate_downweights_rejected()
    test_meta_credit_update()

def test_eg_meta_learner_regret_property():
    import numpy as np
    meta = EGMetaLearner(n_strategies=4, learning_rate=0.1)
    assert np.allclose(meta.get_strategy_weights(), np.ones(4)/4)
    for t in range(100):
        r = np.array([0.02, -0.01, 0.005, 0.0]) + np.random.randn(4)*0.005
        meta.update(r)
    fw = meta.get_strategy_weights()
    assert fw[0] > fw[1], f"Best {fw[0]:.3f} vs worst {fw[1]:.3f}"
    assert (fw >= 0).all() and abs(fw.sum()-1.0) < 0.001
    print(f"  EG weights: {fw}")
    print("[PASS] test_eg_meta_learner_regret_property")
def test_critic_approve_verdict():
    """All checks pass -> APPROVE, confidence preserved."""
    critic = CriticAgent()
    proposal = {"weights": np.array([0.3, 0.2, 0.15, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05]), "confidence": 0.75}
    ctx = {
        "train_end": datetime(2024, 1, 10),
        "test_start": datetime(2024, 1, 20),
        "n_samples": 500,
        "embargo_days": 15,
        "commission_rate": 0.0003,
        "min_commission": 5.0,
        "slippage_bps": 2.0,
        "impact_model": "sqrt",
        "annual_turnover": 0.8,
        "rolling_expanding": True,
        "hmm_global_scaling": False,
        "hmm_bic_recorded": True,
        "pbo_value": 0.15,
        "dsr_p_value": 0.01,
        "sensitivity_done": True,
        "strategy_pool_injectable": True,
        "survivorship_noted": True,
        "test_run_count": 1,
    }
    result = critic.review(proposal, ctx)
    assert result["verdict"] == "APPROVE", f"Expected APPROVE, got {result['verdict']}"
    assert result["adjusted_confidence"] == 0.75, "Confidence should be preserved on APPROVE"
    assert result["critical_failures"] == 0
    assert result["failed"] == 0
    print(f"  Verdict: {result['verdict']}, passed: {result['passed']}/{result['total_checks']}")
    print("[PASS] test_critic_approve_verdict")


def test_critic_reject_on_critical():
    """Purge gap < 5 days -> Purging critical failure -> REJECT."""
    critic = CriticAgent()
    proposal = {"weights": np.array([0.3, 0.2, 0.15, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05]), "confidence": 0.7}
    ctx = {
        "train_end": datetime(2024, 1, 10),
        "test_start": datetime(2024, 1, 11),
        "n_samples": 500,
        "embargo_days": 15,
    }
    result = critic.review(proposal, ctx)
    assert result["verdict"] == "REJECT", f"Expected REJECT, got {result['verdict']}"
    assert result["adjusted_confidence"] == 0.0
    assert result["critical_failures"] >= 1
    print(f"  Verdict: {result['verdict']}, critical: {result['critical_failures']}")
    print("[PASS] test_critic_reject_on_critical")


def test_critic_downgrade_multiple_failures():
    """>=3 non-critical failures -> DOWNGRADE, confidence * 0.5."""
    critic = CriticAgent()
    proposal = {"weights": np.array([0.3, 0.2, 0.15, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05]), "confidence": 0.8}
    ctx = {
        "train_end": datetime(2024, 1, 10),
        "test_start": datetime(2024, 1, 20),
        "n_samples": 50,
        "embargo_days": 2,
        "commission_rate": 0.0001,
        "annual_turnover": 5.0,
        "hmm_bic_recorded": False,
        "pbo_value": 0.5,
        "dsr_p_value": 0.5,
        "sensitivity_done": False,
    }
    result = critic.review(proposal, ctx)
    assert result["verdict"] == "DOWNGRADE", f"Expected DOWNGRADE, got {result['verdict']}"
    assert result["failed"] >= 3, f"Expected >=3 failures, got {result['failed']}"
    assert abs(result["adjusted_confidence"] - 0.4) < 0.01, (
        f"Expected 0.4, got {result['adjusted_confidence']}")
    print(f"  Verdict: {result['verdict']}, failures: {result['failed']}, adj_conf: {result['adjusted_confidence']:.2f}")
    print("[PASS] test_critic_downgrade_multiple_failures")


def test_critic_embargo_check():
    """Embargo < 10 days triggers failure."""
    critic = CriticAgent()
    proposal = {"weights": np.array([0.2] * 9), "confidence": 0.5}
    ctx = {"train_end": datetime(2024, 1, 10), "test_start": datetime(2024, 1, 20),
           "n_samples": 300, "embargo_days": 3}
    result = critic.review(proposal, ctx)
    embargo_fails = [f for f in result["findings"] if not f["pass"] and "embargo" in f["check"].lower()]
    assert len(embargo_fails) > 0, "Should flag embargo < 10 days"
    print(f"  Embargo check failure: {embargo_fails[0]['detail'] if embargo_fails else 'none'}")
    print("[PASS] test_critic_embargo_check")


def test_meta_approve_path():
    """APPROVE verdict -> weights pass through, confidence adjusted by builder_credit."""
    meta = MetaLearner(n_assets=9)
    meta.builder_credit = 0.8
    proposal = {"weights": np.array([0.3, 0.2, 0.15, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05]), "confidence": 0.7}
    review = {"verdict": "APPROVE", "findings": [], "adjusted_confidence": 0.7}
    result = meta.arbitrate({}, proposal, review)
    expected_conf = 0.7 * (0.5 + 0.5 * 0.8)
    assert abs(result["confidence"] - expected_conf) < 0.01, (
        f"Expected {expected_conf:.3f}, got {result['confidence']:.3f}")
    assert np.allclose(result["weights"], proposal["weights"])
    assert abs(result["weights"].sum() - 1.0) < 0.01
    print(f"  Verdict: APPROVE, conf: {result['confidence']:.3f}")
    print("[PASS] test_meta_approve_path")


def test_meta_downgrade_path():
    """DOWNGRADE verdict -> blend with defense weights."""
    meta = MetaLearner(n_assets=9)
    proposal = {"weights": np.array([0.5, 0.2, 0.1, 0.05, 0.05, 0.05, 0.025, 0.025, 0.0]), "confidence": 0.8}
    review = {"verdict": "DOWNGRADE", "findings": [], "adjusted_confidence": 0.4}
    result = meta.arbitrate({}, proposal, review)
    defense = np.ones(9) / 9
    expected_w = 0.7 * proposal["weights"] + 0.3 * defense
    expected_w = expected_w / expected_w.sum()
    assert np.allclose(result["weights"], expected_w, atol=1e-6)
    assert abs(result["confidence"] - 0.48) < 0.01
    print(f"  Verdict: DOWNGRADE, conf: {result['confidence']:.3f}")
    print("[PASS] test_meta_downgrade_path")


def test_meta_credit_cap():
    """Builder credit saturates at 1.0 and critic at 1.0."""
    meta = MetaLearner(n_assets=9)
    meta.builder_credit = 0.95
    meta.critic_credit = 0.0
    for _ in range(10):
        meta.update({}, np.ones(9) / 9, 0.01)
    assert meta.builder_credit <= 1.0, f"Builder credit {meta.builder_credit} > 1.0"
    assert meta.critic_credit >= 0.0, f"Critic credit {meta.critic_credit} < 0.0"
    print(f"  Builder credit cap: {meta.builder_credit:.2f}, Critic credit floor: {meta.critic_credit:.2f}")
    print("[PASS] test_meta_credit_cap")


def test_meta_history_trim():
    """History list respects lookback_quarters limit."""
    meta = MetaLearner(lookback_quarters=3, n_assets=9)
    for i in range(10):
        meta.update({}, np.ones(9) / 9, 0.01 if i % 2 == 0 else -0.01)
    assert len(meta.history) <= 3, f"History length {len(meta.history)} > 3"
    print(f"  History length: {len(meta.history)} (cap=3)")
    print("[PASS] test_meta_history_trim")


def test_eg_strategy_weights():
    """EGMetaLearner gradually shifts weight toward winning strategy."""
    eg = EGMetaLearner(n_strategies=4, learning_rate=0.1)
    assert np.allclose(eg.get_strategy_weights(), np.ones(4) / 4)
    for _ in range(50):
        eg.update([0.05, -0.02, 0.01, 0.0])
    fw = eg.get_strategy_weights()
    assert fw[0] > fw[1], f"Winning strategy 0 ({fw[0]:.3f}) should exceed losing 1 ({fw[1]:.3f})"
    assert abs(fw.sum() - 1.0) < 0.001
    print(f"  EG weights: {[f'{x:.3f}' for x in fw]}")
    print("[PASS] test_eg_strategy_weights")


def test_eg_portfolio_weights():
    """EGMetaLearner.get_portfolio_weights returns valid ensemble."""
    eg = EGMetaLearner(n_strategies=2, n_assets=3)
    sw_dict = {"strat_a": np.array([0.6, 0.3, 0.1]),
               "strat_b": np.array([0.2, 0.3, 0.5])}
    pw = eg.get_portfolio_weights(sw_dict)
    assert pw.shape == (3,), f"Expected shape (3,), got {pw.shape}"
    assert abs(pw.sum() - 1.0) < 0.01
    assert (pw >= 0).all()
    print(f"  Portfolio weights: {[f'{x:.3f}' for x in pw]}")
    print("[PASS] test_eg_portfolio_weights")

