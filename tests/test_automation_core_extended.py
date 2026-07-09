# tests/test_automation_core_extended.py
"""Extended tests for automation/core.py - coverage improvement."""

import pytest
from unittest.mock import MagicMock, patch
from automation.core import AutomationFramework
from automation.config import Config
from automation.task_queue import Task, TaskQueue
from automation.quota import QuotaManager


@pytest.fixture
def config():
    c = Config()
    c.api_key = "test-key"
    return c


@pytest.fixture
def framework(config):
    return AutomationFramework(config)


class TestInit:
    def test_default_state(self, framework):
        assert framework.state == "idle"
        assert framework.trust_gate_enabled is False

    def test_custom_config(self):
        c = Config()
        c.api_key = "custom-key"
        c.model = "glm-5.2"
        f = AutomationFramework(c)
        assert f.config.model == "glm-5.2"


class TestTaskQueue:
    def test_set_task_queue(self, framework):
        q = TaskQueue()
        q.add_task(Task(id="T1", level="L2", instruction="test"))
        framework.set_task_queue(q)
        assert framework.queue.size() == 1

    def test_no_tasks_returns_all_completed(self, framework):
        result = framework.run_cycle(dry_run=True)
        assert result == "all_tasks_completed"


class TestQuota:
    def test_quota_exhausted(self, framework):
        framework.quota = QuotaManager(max_calls=0, refresh_hours=5)
        result = framework.run_cycle(dry_run=True)
        assert result == "quota_exhausted"

    def test_quota_consume_one(self, framework):
        q = TaskQueue()
        q.add_task(Task(id="T1", level="L2", instruction="test",
                        strategies=[{"name": "s1", "description": "d"}]))
        framework.set_task_queue(q)
        before = framework.quota.remaining
        with patch.object(framework.executor, "execute", return_value={
            "choices": [{"message": {"content": "test output"}}],
            "usage": {"total_tokens": 100},
        }):
            framework.run_cycle(dry_run=False)
        after = framework.quota.remaining
        assert after == before - 1


class TestApiError:
    def test_api_error_returns_api_error(self, framework):
        q = TaskQueue()
        q.add_task(Task(id="T1", level="L2", instruction="test",
                        strategies=[{"name": "s1", "description": "d"}]))
        framework.set_task_queue(q)
        with patch.object(framework.executor, "execute", return_value={"error": "API timeout"}):
            result = framework.run_cycle(dry_run=False)
        assert result == "api_error"

    def test_api_error_finalizes_task(self, framework):
        q = TaskQueue()
        t = Task(id="T1", level="L2", instruction="test",
                 strategies=[{"name": "s1", "description": "d"}])
        q.add_task(t)
        framework.set_task_queue(q)
        with patch.object(framework.executor, "execute", return_value={"error": "API timeout"}):
            framework.run_cycle(dry_run=False)
        assert framework.current_task is None


class TestDryRun:
    def test_dry_run_returns_would_execute(self, framework):
        q = TaskQueue()
        t = Task(id="T1", level="L2", instruction="test",
                 strategies=[{"name": "s1", "description": "d"}])
        q.add_task(t)
        framework.set_task_queue(q)
        result = framework.run_cycle(dry_run=True)
        assert result == "would_execute"

    def test_dry_run_consumes_quota(self, framework):
        # Note: run_cycle consumes quota before checking dry_run
        q = TaskQueue()
        q.add_task(Task(id="T1", level="L2", instruction="test",
                        strategies=[{"name": "s1", "description": "d"}]))
        framework.set_task_queue(q)
        before = framework.quota.remaining
        framework.run_cycle(dry_run=True)
        after = framework.quota.remaining
        # Quota is consumed (actual behavior)
        assert after == before - 1


class TestFinalization:
    def test_task_finalized_on_fail(self, framework):
        q = TaskQueue()
        q.add_task(Task(id="T1", level="L2", instruction="test",
                        strategies=[{"name": "s1", "description": "d"}]))
        framework.set_task_queue(q)
        with patch.object(framework.executor, "execute", return_value={"error": "fail"}):
            framework.run_cycle(dry_run=False)
        assert framework.current_task is None


class TestMetaHealth:
    def test_meta_health_available(self, framework):
        assert framework.meta_health is not None

    def test_adaptive_tuner_available(self, framework):
        assert framework.tuner is not None
        assert framework.tuner.enabled is True

    def test_scheduler_available(self, framework):
        assert framework.scheduler is not None
        assert framework.scheduler.max_concurrent_runs == 10


class TestMetrics:
    def test_compute_metrics_basic(self, framework):
        result = {
            "choices": [{"message": {"content": "test output with code"}}],
            "usage": {"total_tokens": 100},
        }
        metrics = framework._compute_metrics(result)
        assert "test_pass_rate" in metrics
        assert "boundary_coverage" in metrics
        assert "compile_ok" in metrics

    def test_compute_metrics_empty_response(self, framework):
        result = {"choices": []}
        metrics = framework._compute_metrics(result)
        assert metrics["test_pass_rate"] == 0.0
        assert metrics["boundary_coverage"] == 0.0

    def test_compute_metrics_error_response(self, framework):
        result = {"error": "some error"}
        metrics = framework._compute_metrics(result)
        assert metrics["compile_ok"] is False
