# automation/adaptive_tuning.py
"""Adaptive parameter tuning based on historical run data.

Observes marginal gains, API costs, and task completion rates to suggest
optimal thresholds for the evaluator and framework.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TuningSuggestion:
    """A concrete tuning recommendation."""
    parameter: str
    current_value: float
    suggested_value: float
    rationale: str
    confidence: float  # 0.0 - 1.0


@dataclass
class RunSnapshot:
    """Snapshot of accumulated run history."""
    n_cycles: int = 0
    avg_marginal_gain: float = 0.0
    avg_completion: float = 0.0
    api_efficiency: float = 0.0  # completion per API call
    force_stop_rate: float = 0.0
    strategy_switch_rate: float = 0.0
    token_usage: int = 0
    n_tasks_completed: int = 0
    n_tasks_failed: int = 0


class AdaptiveTuner:
    """Analyses historical run data and proposes tuning changes.

    Uses simple heuristic rules rather than ML to stay lightweight and
    deterministic for the local-only use case.
    """

    # Default thresholds (can be overridden by tuner suggestions)
    DEFAULT_CONFIG = {
        "high_gain_threshold": 20.0,
        "medium_gain_threshold": 10.0,
        "low_gain_threshold": 5.0,
        "consecutive_stop_limit": 3,
        "max_retries_per_strategy": 5,
    }

    def __init__(self, adaptation_enabled: bool = True):
        self.enabled = adaptation_enabled
        self.history: list[dict] = []
        self.suggestions: list[TuningSuggestion] = []
        self._config = dict(self.DEFAULT_CONFIG)
        self._min_data_points = 30  # minimum cycles before suggesting

    def record(self, task_id: str, strategy_index: int,
               completion_score: float, marginal_gain: float,
               action: str, tokens_used: int = 0):
        """Record one cycle of execution data."""
        self.history.append({
            "task_id": task_id,
            "strategy_index": strategy_index,
            "completion_score": completion_score,
            "marginal_gain": marginal_gain,
            "action": action,
            "tokens_used": tokens_used,
        })
        # Keep last 500
        if len(self.history) > 500:
            self.history = self.history[-500:]

    def get_snapshot(self) -> RunSnapshot:
        """Compute aggregate statistics from recorded history."""
        if not self.history:
            return RunSnapshot()

        n = len(self.history)
        gains = [h["marginal_gain"] for h in self.history]
        completions = [h["completion_score"] for h in self.history]
        actions = [h["action"] for h in self.history]
        tokens = sum(h["tokens_used"] for h in self.history)

        return RunSnapshot(
            n_cycles=n,
            avg_marginal_gain=sum(gains) / n if n else 0.0,
            avg_completion=sum(completions) / n if n else 0.0,
            api_efficiency=(sum(completions) / n * n) / max(tokens, 1) * 100,
            force_stop_rate=actions.count("force_stop") / n,
            strategy_switch_rate=actions.count("switch_strategy") / n,
            token_usage=tokens,
            n_tasks_completed=actions.count("continue") + actions.count("continue_low_freq"),
            n_tasks_failed=actions.count("force_stop"),
        )

    def suggest_tuning(self, snapshot: Optional[RunSnapshot] = None) -> list[TuningSuggestion]:
        """Generate tuning suggestions from run data."""
        if not self.enabled:
            return []

        if snapshot is None:
            snapshot = self.get_snapshot()

        suggestions = []

        # Not enough data
        if snapshot.n_cycles < self._min_data_points:
            return suggestions

        # --- Threshold tuning ---
        # If avg marginal gain is very low, lower thresholds
        if snapshot.avg_marginal_gain < 10.0 and snapshot.avg_marginal_gain > 0:
            new_low = max(2.0, self.DEFAULT_CONFIG["low_gain_threshold"] * 0.6)
            if new_low < self._config["low_gain_threshold"]:
                suggestions.append(TuningSuggestion(
                    parameter="low_gain_threshold",
                    current_value=self._config["low_gain_threshold"],
                    suggested_value=new_low,
                    rationale=f"Avg marginal gain {snapshot.avg_marginal_gain:.1f}% is low; lower threshold to {new_low:.1f}% to avoid premature switching",
                    confidence=0.7,
                ))

        # High force_stop rate -> relax consecutive limit
        if snapshot.force_stop_rate > 0.3:
            new_limit = min(6, self.DEFAULT_CONFIG["consecutive_stop_limit"] + 1)
            if new_limit > self._config["consecutive_stop_limit"]:
                suggestions.append(TuningSuggestion(
                    parameter="consecutive_stop_limit",
                    current_value=self._config["consecutive_stop_limit"],
                    suggested_value=new_limit,
                    rationale=f"Force stop rate {snapshot.force_stop_rate:.0%}; increase consecutive limit to {new_limit}",
                    confidence=0.6,
                ))

        # Low completion with many strategy switches -> relax thresholds
        if snapshot.avg_completion < 50 and snapshot.strategy_switch_rate > 0.2:
            new_medium = max(5.0, self.DEFAULT_CONFIG["medium_gain_threshold"] * 0.7)
            suggestions.append(TuningSuggestion(
                parameter="medium_gain_threshold",
                current_value=self._config["medium_gain_threshold"],
                suggested_value=new_medium,
                rationale=f"Low completion ({snapshot.avg_completion:.1f}) with high switch rate; lower medium threshold to {new_medium:.1f}%",
                confidence=0.5,
            ))

        self.suggestions = suggestions
        return suggestions

    def get_config(self) -> dict:
        """Return current config values (defaults + applied suggestions)."""
        return dict(self._config)

    def reset(self):
        self.history.clear()
        self.suggestions.clear()
        self._config = dict(self.DEFAULT_CONFIG)
