# tests/test_core.py
import pytest
from automation.core import AutomationFramework
from automation.config import Config
from automation.task_queue import Task, TaskQueue
from automation.quota import QuotaManager


def test_framework_init():
    config = Config()
    config.api_key = "test-key"
    framework = AutomationFramework(config)
    assert framework.config.api_key == "test-key"
    assert framework.state == "idle"


def test_framework_load_tasks():
    config = Config()
    config.api_key = "test-key"
    framework = AutomationFramework(config)
    q = TaskQueue()
    q.add_task(Task(id="T1", level="L2", instruction="test"))
    framework.set_task_queue(q)
    assert framework.queue.size() == 1


def test_framework_quota_exhausted():
    config = Config()
    config.api_key = "test-key"
    framework = AutomationFramework(config)
    framework.quota = QuotaManager(max_calls=0, refresh_hours=5)
    result = framework.run_cycle(dry_run=True)
    assert result == "quota_exhausted"
