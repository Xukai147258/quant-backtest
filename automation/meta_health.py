# automation/meta_health.py
"""Meta self-check module for the automation framework.

Evaluates the health of the framework itself:
- Module import integrity
- Test coverage trends (are tests passing?)
- Framework state consistency
- Anomaly detection (e.g. run_cycle returning errors too often)
- Suggests optimisations based on collected metrics
"""

import logging
import importlib
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    # Module check
    all_modules_loadable: bool = True
    missing_modules: list = field(default_factory=list)

    # Test check (from test run results, not running tests here)
    tests_passing: bool = True
    test_failures: int = 0
    test_total: int = 0

    # Runtime consistency
    cycles_since_last_check: int = 0
    last_check_ts: float = 0.0
    anomaly_cycles: int = 0
    total_api_errors: int = 0
    total_quota_exhaustions: int = 0
    total_force_stops: int = 0

    # Trust-check tracking
    trust_checks_run: int = 0
    trust_checks_passed: int = 0
    trust_check_health: float = 100.0

    # Framework health score
    health_score: float = 100.0
    health_level: str = "A"

    # Suggestions
    suggestions: list = field(default_factory=list)


class MetaHealthChecker:
    """Periodically evaluates the framework's own health."""

    MODULES = [
        "automation.config",
        "automation.quota",
        "automation.task_queue",
        "automation.score",
        "automation.evaluator",
        "automation.executor",
        "automation.strategy",
        "automation.core",
        "automation.meta_health",  # self-referential, OK
    ]
    LEVELS = [(90, "S"), (80, "A"), (60, "B"), (0, "F")]

    def __init__(self, check_interval: int = 600):
        self.check_interval = check_interval
        self.last_result = HealthCheckResult()
        self._last_check_time = 0.0
        self._cycle_log: list[dict] = []
        self._anomaly_log: list[dict] = []
        self._suggestion_history: list[tuple] = []

    def should_check(self) -> bool:
        return time.time() - self._last_check_time >= self.check_interval

    def force_check(self):
        """Reset timer so next should_check returns True."""
        self._last_check_time = 0.0

    def record_cycle(self, task_id: str, action: str, score: Optional[float] = None):
        """Record one framework cycle for later analysis."""
        entry = {
            "ts": time.time(),
            "task_id": task_id,
            "action": action,
            "score": score,
        }
        self._cycle_log.append(entry)
        # Keep last 200 cycles
        if len(self._cycle_log) > 200:
            self._cycle_log = self._cycle_log[-200:]

        # Track anomalies
        if action in ("api_error", "force_stop", "no_strategy"):
            self._anomaly_log.append(entry)
            if len(self._anomaly_log) > 50:
                self._anomaly_log = self._anomaly_log[-50:]

    def run_check(self) -> HealthCheckResult:
        """Run all health checks and return results."""
        result = HealthCheckResult()
        self._last_check_time = time.time()

        # 1. Module integrity
        result.all_modules_loadable, result.missing_modules = self._check_modules()

        # 2. Runtime analysis
        cycles = self._cycle_log
        result.cycles_since_last_check = len(cycles)
        result.total_api_errors = sum(1 for c in cycles if c["action"] == "api_error")
        result.total_quota_exhaustions = sum(1 for c in cycles if c["action"] == "quota_exhausted")
        result.total_force_stops = sum(1 for c in cycles if c["action"] == "force_stop")
        result.anomaly_cycles = len(self._anomaly_log)

        # 3. Compute health score
        result.health_score = self._compute_health_score(result)
        result.health_level = self._get_level(result.health_score)

        # 4. Generate suggestions
        result.suggestions = self._generate_suggestions(result)

        self.last_result = result
        return result

    def _check_modules(self) -> tuple[bool, list]:
        missing = []
        for mod_name in self.MODULES:
            try:
                importlib.import_module(mod_name)
            except (ImportError, ModuleNotFoundError) as e:
                missing.append(f"{mod_name}: {e}")
        return len(missing) == 0, missing

    def _compute_health_score(self, r: HealthCheckResult) -> float:
        """Weighted health score based on multiple dimensions."""
        penalties = 0.0

        # Module penalty (hard: up to 100)
        if not r.all_modules_loadable:
            penalties += 30.0 * len(r.missing_modules)

        # Trust-check penalty (up to 20)
        if r.trust_checks_run > 0:
            trust_pass_rate = r.trust_checks_passed / r.trust_checks_run
            if trust_pass_rate < 0.5:
                penalties += 20.0
            elif trust_pass_rate < 0.8:
                penalties += 10.0
            elif trust_pass_rate < 1.0:
                penalties += 5.0

        # Anomaly rate
        total = r.cycles_since_last_check or 1
        error_rate = (r.total_api_errors + r.total_force_stops) / total
        penalties += error_rate * 40  # up to 40

        # Force stop rate
        stop_rate = r.total_force_stops / total
        penalties += stop_rate * 20  # up to 20

        score = max(0.0, 100.0 - penalties)
        return round(score, 1)

    def _get_level(self, score: float) -> str:
        for threshold, level in self.LEVELS:
            if score >= threshold:
                return level
        return "F"

    def record_trust_check(self, passed: bool, check_count: int):
        """Record trust-check result for health analysis."""
        self.last_result.trust_checks_run += 1
        if passed:
            self.last_result.trust_checks_passed += 1

    def _generate_suggestions(self, r: HealthCheckResult) -> list:
        suggestions = []

        if r.total_api_errors > 0:
            suggestions.append(
                f"API errors: {r.total_api_errors} occurred. Check network/GML endpoint"
            )

        if r.total_force_stops > 0:
            suggestions.append(
                f"Force stops: {r.total_force_stops}. Strategies exhausted for some tasks;"
                " consider adding more strategies or lowering min threshold"
            )

        if not r.all_modules_loadable:
            suggestions.append(
                f"Missing modules: {r.missing_modules}. Reinstall dependencies"
            )

        if r.health_score < 60:
            suggestions.append("Health score critical. Consider pausing all tasks")

        if r.trust_checks_run > 0 and r.trust_checks_passed < r.trust_checks_run:
            failed_count = r.trust_checks_run - r.trust_checks_passed
            suggestions.append(
                f"Trust checks: {failed_count}/{r.trust_checks_run} failed."
                " Review latest failing checks before continuing"
            )

        if r.cycles_since_last_check == 0:
            suggestions.append("No cycles since last check. Framework might be idle/stuck")

        return suggestions

    def get_cycles_snapshot(self, n: int = 10) -> list:
        return self._cycle_log[-n:]

    def reset(self):
        self._cycle_log.clear()
        self._anomaly_log.clear()
        self._suggestion_history.clear()
        self._last_check_time = 0.0
