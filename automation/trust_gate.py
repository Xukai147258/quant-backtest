# automation/trust_gate.py
"""Bridges trust-check framework into automation loop.

Provides TrustGate — an adapter that:
- Extracts backtest context from automation framework state
- Runs trust-check phases with configurable thresholds per mode
- Reports structured results (pass/fail per check, serial stop)
- Supports dev/full/final three modes with different strictness
"""

import time
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from check_trust.core import TrustCheckRunner, CheckMode
from check_trust.phase1a import Phase1A
from check_trust.phase1b import Phase1B
from check_trust.phase2 import Phase2
from check_trust.phase3 import Phase3

logger = logging.getLogger(__name__)


@dataclass
class TrustGateResult:
    """Structured result from a trust-gate evaluation."""
    passed: bool
    mode: str
    total_checks: int = 0
    failed_checks: List[Dict] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    report: Optional[Dict] = None


class TrustGate:
    """Adapter that runs trust-check pipeline as a gating step."""

    def __init__(self, mode: str = "dev"):
        self.mode = CheckMode(mode) if isinstance(mode, str) else mode
        self._runner: Optional[TrustCheckRunner] = None
        self._last_result: Optional[TrustGateResult] = None

    def build_context(self, framework_state: Dict[str, Any]) -> Dict[str, Any]:
        """Extract trust-check context from automation framework state."""
        ctx: Dict[str, Any] = {}

        # Collect walkforward results if available
        wf_results = framework_state.get("walkforward_results", {})
        if wf_results:
            ctx["walkforward_results"] = wf_results
            ctx["embargo_log"] = wf_results.get("embargo_log", [])
            ctx["signal_log"] = wf_results.get("signal_log", [])

            # Build test_intervals from walkforward results
            train_ends = wf_results.get("train_ends", [])
            test_starts = wf_results.get("test_starts", [])
            test_ends = wf_results.get("test_ends", [])
            if train_ends and test_starts and test_ends:
                intervals = []
                for i in range(min(len(train_ends), len(test_starts), len(test_ends))):
                    intervals.append({
                        "train_end": train_ends[i],
                        "test_start": test_starts[i],
                        "test_end": test_ends[i],
                    })
                ctx["walkforward_test_intervals"] = intervals

        # Collect HMM history
        hmm_detector = framework_state.get("hmm_detector")
        if hmm_detector and hasattr(hmm_detector, "history"):
            ctx["hmm_history"] = hmm_detector.history

        # Collect cost model
        cost_model = framework_state.get("cost_model")
        if cost_model:
            ctx["cost_model"] = cost_model

        # Collect strategy pool
        strategy_pool = framework_state.get("strategy_pool", {})
        if strategy_pool:
            ctx["strategy_pool"] = strategy_pool

        # Collect prices
        prices = framework_state.get("prices")
        if prices is not None:
            ctx["prices"] = prices

        # Collect agent histories
        for key in ("builder_history", "critic_history", "meta_history"):
            val = framework_state.get(key)
            if val:
                ctx[key] = val

        # Collect metrics
        metrics = framework_state.get("metrics", {})
        if metrics:
            ctx["metrics"] = metrics

        # CPCV results
        cpcv = framework_state.get("cpcv_results", [])
        if cpcv:
            ctx["cpcv_results"] = cpcv

        # Project root for subprocess-based checks (C1)
        ctx["project_root"] = framework_state.get("project_root", None)

        return ctx

    def run(self, framework_state: Dict[str, Any]) -> TrustGateResult:
        """Execute trust-check pipeline and return gating result."""
        t0 = time.time()

        self._runner = TrustCheckRunner(mode=self.mode)
        self._runner.add_phase(Phase1A(mode=self.mode))
        self._runner.add_phase(Phase1B(mode=self.mode))
        self._runner.add_phase(Phase2(mode=self.mode))
        self._runner.add_phase(Phase3(mode=self.mode))

        context = self.build_context(framework_state)
        overall_pass = self._runner.run(context)
        report = self._runner.generate_report()

        failed = [r for r in report.get("results", []) if not r["passed"]]
        elapsed = time.time() - t0

        self._last_result = TrustGateResult(
            passed=overall_pass,
            mode=self.mode.value,
            total_checks=report.get("total_checks", 0),
            failed_checks=failed,
            elapsed_seconds=round(elapsed, 3),
            report=report,
        )
        return self._last_result

    def run_phase(self, phase_index: int, framework_state: Dict[str, Any]) -> TrustGateResult:
        """Run a single phase (0-3) in isolation for debugging."""
        phases = [Phase1A, Phase1B, Phase2, Phase3]
        if phase_index < 0 or phase_index >= len(phases):
            raise ValueError(f"Phase index {phase_index} out of range [0-3]")
        phase_cls = phases[phase_index]

        t0 = time.time()
        context = self.build_context(framework_state)
        phase = phase_cls(mode=self.mode)
        results = phase.run_all(context)

        passed = all(r.passed for r in results)
        report = {
            "overall_pass": passed,
            "total_checks": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "elapsed_seconds": round(time.time() - t0, 3),
            "mode": self.mode.value,
            "results": [{
                "check_id": r.check_id, "name": r.name,
                "passed": r.passed, "message": r.message,
                "duration_ms": round(r.duration_ms, 1),
            } for r in results],
        }

        elapsed = time.time() - t0
        failed = [r for r in report["results"] if not r["passed"]]
        self._last_result = TrustGateResult(
            passed=passed, mode=self.mode.value,
            total_checks=len(results), failed_checks=failed,
            elapsed_seconds=round(elapsed, 3), report=report,
        )
        return self._last_result

    @property
    def last_result(self) -> Optional[TrustGateResult]:
        return self._last_result
