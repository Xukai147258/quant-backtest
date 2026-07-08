
"""Test: Critic with full context produces correct verdicts (not all Auto-pass)."""
import sys
sys.path.insert(0, "D:\\桌面\\quant_backtest")

import numpy as np
from datetime import datetime
from agents.critic import CriticAgent


def _make_proposal(confidence=0.7):
    return {
        "strategy": "risk_parity",
        "weights": np.array([0.3, 0.2, 0.15, 0.1, 0.05, 0.05, 0.05, 0.05, 0.05]),
        "confidence": confidence,
        "rationale": "Neutral regime",
    }


def _make_full_context(overrides=None):
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
        "hmm_bic_value": -1234.5,
        "pbo_value": 0.15,
        "dsr_p_value": 0.01,
        "sensitivity_done": True,
        "strategy_pool_injectable": True,
        "survivorship_noted": True,
        "test_run_count": 1,
    }
    if overrides:
        ctx.update(overrides)
    return ctx


def test_critic_full_context_approve():
    """All fields present and passing -> APPROVE."""
    critic = CriticAgent()
    proposal = _make_proposal()
    ctx = _make_full_context()
    result = critic.review(proposal, ctx)
    assert result["verdict"] == "APPROVE", f"Expected APPROVE, got {result['verdict']}"
    assert result["failed"] == 0, f"Expected 0 failures, got {result['failed']}"
    print(f"  Verdict: {result['verdict']}, passed: {result['passed']}/{result['total_checks']}")
    print("[PASS] test_critic_full_context_approve")


def test_critic_full_context_reject():
    """Critical failures (purge gap < 5) -> REJECT even with full context."""
    critic = CriticAgent()
    proposal = _make_proposal()
    ctx = _make_full_context({"test_start": datetime(2024, 1, 11)})
    result = critic.review(proposal, ctx)
    assert result["verdict"] == "REJECT", f"Expected REJECT, got {result['verdict']}"
    assert result["critical_failures"] >= 1
    print(f"  Verdict: {result['verdict']}, critical: {result['critical_failures']}")
    print("[PASS] test_critic_full_context_reject")


def test_critic_full_context_downgrade():
    """Multiple non-critical failures (poor PBO, high DSR p, no sensitivity) -> DOWNGRADE."""
    critic = CriticAgent()
    proposal = _make_proposal()
    ctx = _make_full_context({
        "pbo_value": 0.5,
        "dsr_p_value": 0.5,
        "sensitivity_done": False,
        "hmm_bic_recorded": False,
    })
    result = critic.review(proposal, ctx)
    assert result["verdict"] == "DOWNGRADE", f"Expected DOWNGRADE, got {result['verdict']}"
    assert result["failed"] >= 3, f"Expected >=3 failures, got {result['failed']}"
    print(f"  Verdict: {result['verdict']}, failures: {result['failed']}")
    print("[PASS] test_critic_full_context_downgrade")


if __name__ == "__main__":
    test_critic_full_context_approve()
    test_critic_full_context_reject()
    test_critic_full_context_downgrade()
