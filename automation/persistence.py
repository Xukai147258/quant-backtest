# automation/persistence.py
"""Checkpoint persistence for the automation framework.

Saves and loads framework state to/from JSON files so the framework
can resume after crash or restart without losing task progress.
"""

import json
import time
import os
import logging
from dataclasses import dataclass, field, asdict
from typing import Optional
from automation.task_queue import TaskQueue, Task

logger = logging.getLogger(__name__)


@dataclass
class FrameworkCheckpoint:
    """Serializable snapshot of framework state."""
    timestamp: float = 0.0
    framework_state: str = "idle"
    current_task_id: Optional[str] = None
    quota_remaining: int = 0
    quota_total_used: int = 0
    quota_max_calls: int = 1000
    quota_next_refresh: float = 0.0
    current_index: int = 0
    tasks: list = field(default_factory=list)
    meta_cycle_log: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "framework_state": self.framework_state,
            "current_task_id": self.current_task_id,
            "quota_remaining": self.quota_remaining,
            "quota_total_used": self.quota_total_used,
            "quota_max_calls": self.quota_max_calls,
            "quota_next_refresh": self.quota_next_refresh,
            "current_index": self.current_index,
            "tasks": self.tasks,
            "meta_cycle_log": self.meta_cycle_log[-100:],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FrameworkCheckpoint":
        return cls(
            timestamp=d.get("timestamp", 0.0),
            framework_state=d.get("framework_state", "idle"),
            current_task_id=d.get("current_task_id"),
            quota_remaining=d.get("quota_remaining", 0),
            quota_total_used=d.get("quota_total_used", 0),
            quota_max_calls=d.get("quota_max_calls", 1000),
            quota_next_refresh=d.get("quota_next_refresh", 0.0),
            current_index=d.get("current_index", 0),
            tasks=d.get("tasks", []),
            meta_cycle_log=d.get("meta_cycle_log", []),
        )


class CheckpointManager:
    """Manages saving/loading framework checkpoints."""

    def __init__(self, checkpoint_dir: str = "checkpoints", max_versions: int = 5):
        self.checkpoint_dir = checkpoint_dir
        self.max_versions = max_versions
        self._version_counter = 0
        os.makedirs(checkpoint_dir, exist_ok=True)

    def _checkpoint_path(self, version: int) -> str:
        return os.path.join(self.checkpoint_dir, f"framework_state_v{version}.json")

    @property
    def latest_path(self) -> Optional[str]:
        """Find the latest checkpoint file by version number."""
        versions = []
        for fname in os.listdir(self.checkpoint_dir):
            if fname.startswith("framework_state_v") and fname.endswith(".json"):
                try:
                    v = int(fname.replace("framework_state_v", "").replace(".json", ""))
                    versions.append((v, os.path.join(self.checkpoint_dir, fname)))
                except ValueError:
                    continue
        if not versions:
            return None
        versions.sort(key=lambda x: x[0])
        return versions[-1][1]

    def save(self, checkpoint: FrameworkCheckpoint) -> str:
        """Save checkpoint to disk."""
        self._version_counter += 1
        path = self._checkpoint_path(self._version_counter)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(checkpoint.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Checkpoint saved: {path}")
        # Clean old versions
        self._clean_old()
        return path

    def load(self, version: Optional[int] = None) -> Optional[FrameworkCheckpoint]:
        """Load a checkpoint. If version is None, load the latest."""
        if version is not None:
            path = self._checkpoint_path(version)
        else:
            path = self.latest_path
        if not path or not os.path.exists(path):
            logger.warning(f"No checkpoint found" if version is None else f"Checkpoint {path} not found")
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info(f"Checkpoint loaded: {path}")
        return FrameworkCheckpoint.from_dict(data)

    def _clean_old(self):
        """Remove old checkpoints beyond max_versions."""
        versions = []
        for fname in os.listdir(self.checkpoint_dir):
            if fname.startswith("framework_state_v") and fname.endswith(".json"):
                try:
                    v = int(fname.replace("framework_state_v", "").replace(".json", ""))
                    versions.append(v)
                except ValueError:
                    continue
        versions.sort()
        while len(versions) > self.max_versions:
            old_v = versions.pop(0)
            old_path = self._checkpoint_path(old_v)
            try:
                os.remove(old_path)
                logger.debug(f"Removed old checkpoint: {old_path}")
            except OSError:
                pass

    def build_checkpoint(self, framework) -> FrameworkCheckpoint:
        """Build a checkpoint from the framework's current state."""
        cp = FrameworkCheckpoint()
        cp.timestamp = time.time()
        cp.framework_state = framework.state
        cp.current_task_id = framework.current_task.id if framework.current_task else None
        cp.quota_remaining = framework.quota.remaining
        cp.quota_total_used = framework.quota.total_used
        cp.quota_max_calls = framework.quota.max_calls
        cp.quota_next_refresh = framework.quota._next_refresh
        cp.current_index = framework.queue.current_index
        cp.tasks = [
            {
                "id": t.id,
                "level": t.level,
                "status": t.status,
                "current_strategy_index": t.current_strategy_index,
                "current_completion": t.current_completion,
                "completion_history": t.completion_history,
                "budget_used": t.budget_used,
            }
            for t in framework.queue.tasks
        ]
        cp.meta_cycle_log = framework.meta_health._cycle_log
        return cp

    def apply_checkpoint(self, framework, cp: FrameworkCheckpoint):
        """Apply a checkpoint to a framework instance."""
        framework.state = cp.framework_state
        # Restore task states
        for saved_task in cp.tasks:
            for t in framework.queue.tasks:
                if t.id == saved_task["id"]:
                    t.status = saved_task.get("status", t.status)
                    t.current_strategy_index = saved_task.get("current_strategy_index", 0)
                    t.current_completion = saved_task.get("current_completion", 0.0)
                    t.completion_history = saved_task.get("completion_history", [])
                    t.budget_used = saved_task.get("budget_used", 0)
                    break
        framework.queue.current_index = cp.current_index
        # Restore quota
        framework.quota.remaining = cp.quota_remaining
        framework.quota.total_used = cp.quota_total_used
        framework.quota._next_refresh = cp.quota_next_refresh
        # Restore meta cycle log
        if cp.meta_cycle_log:
            framework.meta_health._cycle_log = cp.meta_cycle_log
