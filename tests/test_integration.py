# tests/test_integration.py
import pytest
from automation.config import Config
from automation.core import AutomationFramework
from automation.task_queue import TaskQueue, Task
from automation.quota import QuotaManager


def test_full_flow_one_task():
    """One L2 task: load through run cycle"""
    config = Config()
    config.api_key = "test-key"

    q = TaskQueue()
    t = Task(id="TEST-001", level="L2", title="test task",
             instruction="test", strategies=[{"name": "A", "description": "test"}])
    q.add_task(t)

    framework = AutomationFramework(config)
    framework.set_task_queue(q)
    result = framework.run_cycle(dry_run=True)
    assert result in ("would_execute", "quota_exhausted", "all_tasks_completed")


def test_quota_and_queue_interaction():
    """Quota exhaustion then pause"""
    config = Config()
    config.api_key = "test-key"

    q = TaskQueue()
    q.add_task(Task(id="T1", level="L2", strategies=[{"name": "A", "description": "test"}]))
    q.add_task(Task(id="T2", level="L2", strategies=[{"name": "A", "description": "test"}]))

    framework = AutomationFramework(config)
    framework.set_task_queue(q)
    framework.quota = QuotaManager(max_calls=1, refresh_hours=5)

    result = framework.run_cycle(dry_run=True)
    assert result in ("would_execute", "quota_exhausted")

    framework.current_task = None
    result2 = framework.run_cycle(dry_run=True)
    assert result2 == "quota_exhausted"


def test_marginal_decision_chain():
    """Simulate low marginal gain -> force stop"""
    config = Config()
    config.api_key = "test-key"

    q = TaskQueue()
    t = Task(id="MARGIN-TEST", level="L2", strategies=[{"name": "A", "description": "test"}])
    q.add_task(t)

    framework = AutomationFramework(config)
    framework.set_task_queue(q)

    for i in range(5):
        if framework.current_task is None:
            framework.current_task = framework.queue.next()
        if framework.current_task is None:
            break
        framework.current_task.record_completion(float(i * 2))
        gain = framework.current_task.marginal_gain()
        action = framework.evaluator.decide_marginal(gain)["action"]
        if action == "force_stop":
            break
    else:
        pytest.fail("force_stop was never triggered")
