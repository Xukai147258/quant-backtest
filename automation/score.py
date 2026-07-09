from dataclasses import dataclass
from typing import Optional


@dataclass
class TestItem:
    name: str
    weight: float
    scoring_mode: str  # "pass_fail" or "range"
    score: float = 0.0
    min_score: float = 0.0
    evaluation_criteria: list = None


class ScoreEngine:
    """Weighted scoring engine with multi-task-type support and min_score gates."""

    LEVELS = [(90, "S"), (80, "A"), (60, "B"), (0, "F")]

    def calculate(self, items):
        """Calculate weighted total score and level.

        Returns (total_score, level).
        If any pass_fail item is below its min_score, total is 0.
        """
        if not items:
            return 0.0, "F"

        # Min-score gate: any pass_fail item below min_score => F
        for item in items:
            if item.scoring_mode == "pass_fail" and item.score < item.min_score:
                return 0.0, "F"

        total_weight = sum(i.weight for i in items)
        if total_weight == 0:
            return 0.0, "F"
        weighted_sum = sum(i.score * i.weight for i in items)
        total = weighted_sum / total_weight
        level = self.get_level(total)
        return round(total, 1), level

    def get_level(self, score):
        for threshold, level in self.LEVELS:
            if score >= threshold:
                return level
        return "F"

    # --- Task-type-specific evaluators ---

    def evaluate_code_task(self, test_pass_rate, boundary_coverage, compile_ok):
        """Code/engineering task: tests 50%, boundary 30%, compile 20%."""
        compile_score = 100.0 if compile_ok else 0.0
        score = test_pass_rate * 0.5 + boundary_coverage * 0.3 + compile_score * 0.2
        return TestItem(name="code completion", weight=100, scoring_mode="range",
                        score=score, min_score=60,
                        evaluation_criteria=["test_pass_rate>=50%", "compile_ok"])

    def evaluate_document_task(self, structure_completeness, info_accuracy, format_score):
        """Document/analysis task: structure 40%, accuracy 40%, format 20%."""
        score = structure_completeness * 0.4 + info_accuracy * 0.4 + format_score * 0.2
        return TestItem(name="document quality", weight=100, scoring_mode="range",
                        score=score, min_score=60,
                        evaluation_criteria=["structure>=40%", "accuracy>=40%"])

    def evaluate_qa_task(self, goal_coverage, depth_index):
        """General Q&A task: coverage 60%, depth 40%."""
        score = goal_coverage * 0.6 + depth_index * 0.4
        return TestItem(name="qa quality", weight=100, scoring_mode="range",
                        score=score, min_score=60,
                        evaluation_criteria=["goal_coverage>=50%"])

    @staticmethod
    def detect_task_type(instruction: str) -> str:
        """Heuristic detection of task type from instruction text."""
        instruction_lower = instruction.lower()
        code_keywords = ["fix", "bug", "ci", "workflow", "refactor", "implement",
                         "write code", "function", "class", "method", "test"]
        doc_keywords = ["document", "report", "analysis", "spec", "summary",
                        "explain", "describe"]

        code_score = sum(1 for kw in code_keywords if kw in instruction_lower)
        doc_score = sum(1 for kw in doc_keywords if kw in instruction_lower)

        if code_score >= doc_score and code_score > 0:
            return "code"
        elif doc_score > 0:
            return "document"
        return "qa"

    def evaluate_by_instruction(self, instruction: str, **kwargs) -> TestItem:
        """Auto-detect task type and evaluate."""
        task_type = self.detect_task_type(instruction)
        if task_type == "code":
            return self.evaluate_code_task(
                kwargs.get("test_pass_rate", 0),
                kwargs.get("boundary_coverage", 0),
                kwargs.get("compile_ok", False),
            )
        elif task_type == "document":
            return self.evaluate_document_task(
                kwargs.get("structure_completeness", 0),
                kwargs.get("info_accuracy", 0),
                kwargs.get("format_score", 0),
            )
        else:
            return self.evaluate_qa_task(
                kwargs.get("goal_coverage", 0),
                kwargs.get("depth_index", 0),
            )
