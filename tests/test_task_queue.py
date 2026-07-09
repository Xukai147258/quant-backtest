import pytest
import tempfile
import json
from automation.task_queue import TaskQueue, Task


def test_task_from_dict():
    t = Task.from_dict({
        "id": "CI-001",
        "level": "L2",
        "title": "fix CI",
        "instruction": "analyze and fix CI",
        "strategies": [],
    })
    assert t.id == "CI-001"
    assert t.level == "L2"


def test_queue_empty():
    q = TaskQueue()
    assert q.size() == 0
    assert q.next() is None


def test_queue_add_and_next():
    q = TaskQueue()
    q.add_task(Task(id="T1", level="L2"))
    q.add_task(Task(id="T2", level="L1"))
    assert q.size() == 2
    first = q.next()
    assert first.id == "T1"


def test_queue_pause_recovery():
    q = TaskQueue()
    t = Task(id="T1", level="L2")
    t.completion_history = [0, 30, 50, 60]
    q.add_task(t)
    q.add_task(Task(id="T2", level="L2"))
    q.pause_current()
    recovered = q.next()
    assert recovered.id == "T1"


def test_queue_from_json():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump([{
            "id": "CI-001",
            "level": "L2",
            "title": "fix CI",
            "instruction": "analyze and fix CI",
            "strategies": [
                {"name": "A", "description": "fix workflow"},
                {"name": "B", "description": "fix deps"},
            ],
        }], f)
        f.flush()
        q = TaskQueue.from_json(f.name)
        assert q.size() == 1
        assert len(q.tasks[0].strategies) == 2
