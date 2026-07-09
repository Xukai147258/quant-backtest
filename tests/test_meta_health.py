# tests/test_meta_health.py
import pytest
import time
from automation.meta_health import MetaHealthChecker


def test_init():
    m = MetaHealthChecker()
    assert m.last_result.health_score == 100.0
    assert m.last_result.health_level == "A"


def test_should_check():
    m = MetaHealthChecker(check_interval=0)
    assert m.should_check() is True


def test_should_check_false():
    m = MetaHealthChecker(check_interval=99999)
    m._last_check_time = time.time()  # mark as just checked
    assert m.should_check() is False


def test_force_check():
    m = MetaHealthChecker(check_interval=99999)
    m.force_check()
    assert m.should_check() is True


def test_record_cycle():
    m = MetaHealthChecker()
    m.record_cycle("T1", "continue", 85.0)
    m.record_cycle("T2", "api_error", 0.0)
    assert len(m._cycle_log) == 2
    assert len(m._anomaly_log) == 1
    assert m._anomaly_log[0]["action"] == "api_error"


def test_run_check_normal():
    m = MetaHealthChecker()
    for i in range(10):
        m.record_cycle(f"T{i}", "continue", 80.0 + i)
    r = m.run_check()
    assert r.cycles_since_last_check == 10
    assert r.total_api_errors == 0
    assert r.total_force_stops == 0
    assert r.health_score >= 90.0
    assert r.health_level == "S"


def test_run_check_with_errors():
    m = MetaHealthChecker()
    for i in range(20):
        action = "api_error" if i % 4 == 0 else "continue"
        m.record_cycle(f"T{i}", action)
    r = m.run_check()
    assert r.total_api_errors == 5
    assert r.health_score < 100.0


def test_run_check_force_stops():
    m = MetaHealthChecker()
    for i in range(20):
        action = "force_stop" if i < 5 else "continue"
        m.record_cycle(f"T{i}", action)
    r = m.run_check()
    assert r.total_force_stops == 5
    assert r.health_score < 100.0


def test_reset():
    m = MetaHealthChecker()
    m.record_cycle("T1", "continue")
    assert len(m._cycle_log) == 1
    m.reset()
    assert len(m._cycle_log) == 0
    assert len(m._anomaly_log) == 0


def test_get_cycles_snapshot():
    m = MetaHealthChecker()
    for i in range(5):
        m.record_cycle(f"T{i}", "continue")
    snap = m.get_cycles_snapshot(3)
    assert len(snap) == 3
    assert snap[-1]["task_id"] == "T4"


def test_module_check_pass():
    m = MetaHealthChecker()
    ok, missing = m._check_modules()
    assert ok is True
    assert len(missing) == 0
