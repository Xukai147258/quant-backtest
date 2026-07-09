# tests/test_persistence.py
import pytest
import time
import tempfile
import os
from automation.persistence import CheckpointManager, FrameworkCheckpoint
from automation.config import Config
from automation.core import AutomationFramework
from automation.task_queue import TaskQueue, Task
from automation.quota import QuotaManager


@pytest.fixture
def tmp_checkpoint_dir(tmpdir):
    return str(tmpdir)


def test_save_and_load(tmp_checkpoint_dir):
    mgr = CheckpointManager(checkpoint_dir=tmp_checkpoint_dir, max_versions=3)
    cp = FrameworkCheckpoint(
        timestamp=time.time(),
        framework_state="running",
        current_task_id="T1",
        quota_remaining=500,
        quota_total_used=500,
        quota_max_calls=1000,
        current_index=1,
        tasks=[{"id": "T1", "status": "running", "current_strategy_index": 0}],
    )
    path = mgr.save(cp)
    assert os.path.exists(path)

    loaded = mgr.load()
    assert loaded is not None
    assert loaded.framework_state == "running"
    assert loaded.current_task_id == "T1"
    assert loaded.quota_remaining == 500


def test_latest_version(tmp_checkpoint_dir):
    mgr = CheckpointManager(checkpoint_dir=tmp_checkpoint_dir, max_versions=3)
    cp1 = FrameworkCheckpoint(timestamp=100.0, framework_state="idle")
    cp2 = FrameworkCheckpoint(timestamp=200.0, framework_state="running")
    mgr.save(cp1)
    mgr.save(cp2)
    loaded = mgr.load()
    assert loaded.framework_state == "running"


def test_no_checkpoint(tmp_checkpoint_dir):
    mgr = CheckpointManager(checkpoint_dir=tmp_checkpoint_dir)
    loaded = mgr.load()
    assert loaded is None


def test_clean_old_versions(tmp_checkpoint_dir):
    mgr = CheckpointManager(checkpoint_dir=tmp_checkpoint_dir, max_versions=2)
    for i in range(5):
        mgr.save(FrameworkCheckpoint(timestamp=float(i)))
    assert len(os.listdir(tmp_checkpoint_dir)) <= 2


def test_build_checkpoint(tmp_checkpoint_dir):
    config = Config()
    config.api_key = "test-key"
    framework = AutomationFramework(config)
    q = TaskQueue()
    q.add_task(Task(id="T1", level="L2", instruction="test", strategies=[{"name": "A", "description": "test"}]))
    framework.set_task_queue(q)

    mgr = CheckpointManager(checkpoint_dir=tmp_checkpoint_dir, max_versions=2)
    framework.meta_health.record_cycle("T1", "continue", 85.0)
    framework.state = "running"

    cp = mgr.build_checkpoint(framework)
    assert cp.framework_state == "running"
    assert cp.current_task_id == "T1" or cp.current_task_id is None
    assert len(cp.tasks) == 1


def test_apply_checkpoint(tmp_checkpoint_dir):
    config = Config()
    config.api_key = "test-key"
    framework = AutomationFramework(config)
    q = TaskQueue()
    q.add_task(Task(id="T1", level="L2", instruction="test", strategies=[{"name": "A", "description": "test"}]))
    framework.set_task_queue(q)

    cp = FrameworkCheckpoint(
        framework_state="running",
        tasks=[{"id": "T1", "status": "completed", "current_strategy_index": 0, "current_completion": 85.0, "completion_history": [85.0], "budget_used": 3}],
        current_index=0,
        quota_remaining=900,
        quota_total_used=100,
    )

    mgr = CheckpointManager(checkpoint_dir=tmp_checkpoint_dir, max_versions=2)
    mgr.apply_checkpoint(framework, cp)
    assert framework.state == "running"
    assert framework.queue.tasks[0].status == "completed"
    assert framework.queue.tasks[0].current_completion == 85.0
    assert framework.quota.remaining == 900


def test_save_load_roundtrip(tmp_checkpoint_dir):
    config = Config()
    config.api_key = "test-key"
    framework = AutomationFramework(config)
    q = TaskQueue()
    q.add_task(Task(id="T1", level="L2", instruction="test", strategies=[{"name": "A", "description": "test"}]))
    q.add_task(Task(id="T2", level="L2", instruction="test2"))
    framework.set_task_queue(q)

    mgr = CheckpointManager(checkpoint_dir=tmp_checkpoint_dir, max_versions=2)
    framework.state = "running"
    framework.meta_health.record_cycle("T1", "continue", 85.0)
    framework.quota.consume()
    framework.quota.consume()

    cp = mgr.build_checkpoint(framework)
    mgr.save(cp)

    # Create a fresh framework and apply
    fresh_config = Config()
    fresh_config.api_key = "test-key"
    fresh_framework = AutomationFramework(fresh_config)
    fresh_q = TaskQueue()
    fresh_q.add_task(Task(id="T1", level="L2", instruction="test", strategies=[{"name": "A", "description": "test"}]))
    fresh_q.add_task(Task(id="T2", level="L2", instruction="test2"))
    fresh_framework.set_task_queue(fresh_q)

    loaded_cp = mgr.load()
    mgr.apply_checkpoint(fresh_framework, loaded_cp)
    assert fresh_framework.state == "running"
    assert fresh_framework.quota.remaining == 998
    assert fresh_framework.quota.total_used == 2
    assert len(fresh_framework.meta_health._cycle_log) == 1
