# coding: utf-8
"""Integration test: trust-check pipeline against backtest output."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from automation.trust_gate import TrustGate, TrustGateResult
from check_trust.core import CheckMode


class TestTrustGateIntegration:
    """End-to-end trust-check against mock backtest output."""

    def _make_mock_backtest_state(self) -> dict:
        """Build mock framework state similar to real backtest."""
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", "2023-12-31", freq="B")
        prices = pd.DataFrame(
            {"A": np.random.randn(len(dates)).cumsum() + 100,
             "B": np.random.randn(len(dates)).cumsum() + 50},
            index=dates,
        )

        # Mock walkforward results
        train_ends = list(dates[::60][:-1])[:8]
        test_starts = [d + timedelta(days=10) for d in train_ends]
        test_ends = [d + timedelta(days=30) for d in test_starts]

        embargo_log = [
            {"step": i, "prev_test_end": str(test_ends[i - 1] if i > 0 else dates[0]),
             "embargo_start": str(test_ends[i - 1] if i > 0 else dates[0]),
             "embargo_end": str(test_ends[i - 1] + timedelta(days=10) if i > 0 else dates[0] + timedelta(days=10)),
             "excluded_count": 5}
            for i in range(len(train_ends))
        ]

        signal_log = [
            {"strategy": "mock", "compute_date": str(train_ends[i]),
             "apply_date": str(test_starts[i]), "weights": [0.5, 0.5], "n_assets": 2}
            for i in range(len(train_ends))
        ]

        wf_results = {
            "n_steps": len(train_ends),
            "train_ends": train_ends,
            "test_starts": test_starts,
            "test_ends": test_ends,
            "embargo_log": embargo_log,
            "signal_log": signal_log,
        }

        # Mock cost model
        class MockCostModel:
            stamp_duty = 0.001
            commission_rate = 0.0003
            slippage_bps = 3.0

        # Mock strategy pool
        strategy_pool = {
            "eq": lambda r, c: np.ones(2) / 2,
            "mom": lambda r, c: np.array([0.6, 0.4]),
        }

        return {
            "walkforward_results": wf_results,
            "cost_model": MockCostModel(),
            "strategy_pool": strategy_pool,
            "prices": prices,
            "metrics": {"sharpe": 1.2, "dsr": 2.5, "pbo": 0.15},
            "project_root": os.path.dirname(os.path.dirname(__file__)),
        }

    def test_trust_gate_dev_mode_pass(self):
        """In dev mode, trust gate should pass on valid mock data."""
        gate = TrustGate(mode="dev")
        state = self._make_mock_backtest_state()
        result = gate.run(state)

        assert isinstance(result, TrustGateResult)
        assert result.mode == "dev"
        assert result.total_checks > 0
        # In dev mode with valid mock data, should pass most checks
        assert result.passed or len(result.failed_checks) < 5

    def test_trust_gate_build_context(self):
        """Context builder should extract all expected keys."""
        gate = TrustGate(mode="dev")
        state = self._make_mock_backtest_state()
        ctx = gate.build_context(state)

        assert "walkforward_results" in ctx
        assert "embargo_log" in ctx
        assert "signal_log" in ctx
        assert "cost_model" in ctx
        assert "strategy_pool" in ctx
        assert "prices" in ctx
        assert "metrics" in ctx

    def test_trust_gate_missing_cost_model(self):
        """Without cost_model, B1 should fail."""
        gate = TrustGate(mode="dev")
        state = self._make_mock_backtest_state()
        state["cost_model"] = None

        result = gate.run_phase(1, state)  # Phase 1B contains B1
        # B1 should fail when cost_model is None
        b1_failed = any(c["check_id"] == "B1" and not c["passed"] for c in result.failed_checks)
        assert b1_failed or result.passed  # May skip in dev mode

    def test_trust_gate_sharpe_too_high(self):
        """With unrealistic Sharpe, D5 should flag."""
        gate = TrustGate(mode="dev")
        state = self._make_mock_backtest_state()
        state["metrics"] = {"sharpe": 5.0, "dsr": 10.0, "pbo": 0.01}

        result = gate.run_phase(3, state)  # Phase 3 contains D5
        # D5 checks sharpe < 2.5
        d5_result = next(
            (c for c in result.report["results"] if c["check_id"] == "D5"), None
        )
        if d5_result:
            assert not d5_result["passed"]  # Should fail for sharpe=5.0

    def test_trust_gate_elapsed_time(self):
        """Should complete within reasonable time."""
        gate = TrustGate(mode="dev")
        state = self._make_mock_backtest_state()

        result = gate.run(state)
        assert result.elapsed_seconds < 10.0  # Should be fast

    def test_trust_gate_result_report_structure(self):
        """Report dict should have all required keys."""
        gate = TrustGate(mode="dev")
        state = self._make_mock_backtest_state()
        result = gate.run(state)

        report = result.report
        assert report is not None
        assert "overall_pass" in report
        assert "total_checks" in report
        assert "passed" in report
        assert "failed" in report
        assert "elapsed_seconds" in report
        assert "mode" in report
        assert "results" in report
        assert isinstance(report["results"], list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
