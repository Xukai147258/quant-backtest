import json
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Task:
    id: str
    level: str = "L2"
    title: str = ""
    instruction: str = ""
    output_file: str = ""
    tags: list = field(default_factory=list)
    strategies: list = field(default_factory=list)
    current_strategy_index: int = 0
    status: str = "pending"
    completion_history: list = field(default_factory=list)
    current_completion: float = 0.0
    budget_used: int = 0
    max_budget_pct: int = 40
    tests: list = field(default_factory=list)

    @classmethod
    def from_dict(cls, d):
        return cls(
            id=d.get("id", ""),
            level=d.get("level", "L2"),
            title=d.get("title", ""),
            instruction=d.get("instruction", ""),
            output_file=d.get("output_file", ""),
            tags=d.get("tags", []),
            strategies=d.get("strategies", []),
            max_budget_pct=d.get("max_budget_pct", 40),
        )

    def record_completion(self, score):
        self.completion_history.append(score)
        self.current_completion = score

    def marginal_gain(self):
        if len(self.completion_history) < 2:
            return 100.0
        return self.completion_history[-1] - self.completion_history[-2]

    def average_gain(self, n=3):
        recent = self.completion_history[-n:]
        if len(recent) < 2:
            return 100.0
        changes = [recent[i+1] - recent[i] for i in range(len(recent)-1)]
        return sum(changes) / len(changes) if changes else 0.0

    def next_strategy(self):
        if self.current_strategy_index + 1 < len(self.strategies):
            self.current_strategy_index += 1
            return True
        return False


class TaskQueue:
    def __init__(self):
        self.tasks: list[Task] = []
        self.current_index = 0
        self.paused_task: Optional[Task] = None

    def add_task(self, task):
        self.tasks.append(task)

    def size(self):
        return len(self.tasks)

    def next(self):
        if self.paused_task:
            t = self.paused_task
            self.paused_task = None
            return t
        while self.current_index < len(self.tasks):
            t = self.tasks[self.current_index]
            if t.status == "pending":
                t.status = "running"
                return t
            self.current_index += 1
        return None

    def pause_current(self):
        if self.current_index < len(self.tasks):
            t = self.tasks[self.current_index]
            t.status = "paused"
            self.paused_task = t

    def complete_current(self):
        if self.current_index < len(self.tasks):
            self.tasks[self.current_index].status = "completed"
            self.current_index += 1

    def fail_current(self):
        if self.current_index < len(self.tasks):
            self.tasks[self.current_index].status = "failed"
            self.current_index += 1

    @classmethod
    def from_json(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        q = cls()
        for item in data:
            q.add_task(Task.from_dict(item))
        return q

    def remaining_tasks(self):
        pending = sum(1 for t in self.tasks if t.status == "pending")
        paused = sum(1 for t in self.tasks if t.status == "paused")
        return pending + paused
