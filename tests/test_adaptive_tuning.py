# tests/test_adaptive_tuning.py
import pytest
from automation.adaptive_tuning import AdaptiveTuner, TuningSuggestion, RunSnapshot


def test_init():
    tuner = AdaptiveTuner()
    assert tuner.enabled is True
    assert len(tuner.history) == 0


def test_disable():
    tuner = AdaptiveTuner(adaptation_enabled=False)
    assert tuner.suggest_tuning() == []


def test_record():
    tuner = AdaptiveTuner()
    tuner.record("T1", 0, 85.0, 15.0, "continue", 500)
    assert len(tuner.history) == 1
    assert tuner.history[0]["task_id"] == "T1"


def test_snapshot_empty():
    tuner = AdaptiveTuner()
    snap = tuner.get_snapshot()
    assert snap.n_cycles == 0


def test_snapshot_with_data():
    tuner = AdaptiveTuner()
    for i in range(10):
        tuner.record(f"T{i}", 0, 80.0 + i, 10.0, "continue", 300)
    snap = tuner.get_snapshot()
    assert snap.n_cycles == 10
    assert snap.avg_marginal_gain == 10.0


def test_suggest_too_few_points():
    tuner = AdaptiveTuner()
    for i in range(5):
        tuner.record(f"T{i}", 0, 50.0, 5.0, "continue")
    suggestions = tuner.suggest_tuning()
    assert len(suggestions) == 0


def test_suggest_low_gain():
    tuner = AdaptiveTuner()
    for i in range(35):
        tuner.record(f"T{i}", 0, 40.0, 3.0, "continue")
    suggestions = tuner.suggest_tuning()
    assert len(suggestions) >= 1
    # Should suggest lowering low_gain_threshold
    targets = [s.parameter for s in suggestions]
    assert "low_gain_threshold" in targets


def test_suggest_high_force_stop():
    tuner = AdaptiveTuner()
    for i in range(30):
        action = "force_stop" if i < 12 else "continue"
        tuner.record(f"T{i}", 0, 30.0, 2.0, action)
    suggestions = tuner.suggest_tuning()
    params = [s.parameter for s in suggestions]
    assert "consecutive_stop_limit" in params


def test_reset():
    tuner = AdaptiveTuner()
    tuner.record("T1", 0, 80.0, 20.0, "continue")
    tuner.reset()
    assert len(tuner.history) == 0
    assert tuner._config == tuner.DEFAULT_CONFIG


def test_get_config():
    tuner = AdaptiveTuner()
    cfg = tuner.get_config()
    assert cfg["high_gain_threshold"] == 20.0
    assert cfg["low_gain_threshold"] == 5.0
