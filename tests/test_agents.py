"""Test Dual-Agent + Meta-Learner modules."""
import sys
sys.path.insert(0, "D:\\桌面")

import numpy as np
import pandas as pd
from datetime import datetime

from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.meta_learner import MetaLearner
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
    from agents.meta_learner import EGMetaLearner
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
