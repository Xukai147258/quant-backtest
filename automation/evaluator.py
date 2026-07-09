# automation/evaluator.py
import json
import logging
from dataclasses import dataclass
from automation.score import ScoreEngine, TestItem
from automation.task_queue import Task

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    score: float
    level: str
    marginal_gain: float
    decision: dict
    details: dict = None


class RuleEvaluator:
    """Rule-based evaluator with marginal gain decision logic."""

    def __init__(self):
        self._consecutive_low = 0
        self.score_engine = ScoreEngine()

    def evaluate(self, task, metrics):
        test_item = self.score_engine.evaluate_by_instruction(
            task.instruction,
            test_pass_rate=metrics.get("test_pass_rate", 0),
            boundary_coverage=metrics.get("boundary_coverage", 0),
            compile_ok=metrics.get("compile_ok", False),
            structure_completeness=metrics.get("structure_completeness", 0),
            info_accuracy=metrics.get("info_accuracy", 0),
            format_score=metrics.get("format_score", 0),
            goal_coverage=metrics.get("goal_coverage", 0),
            depth_index=metrics.get("depth_index", 0),
        )
        score, level = self.score_engine.calculate([test_item])
        task.record_completion(score)
        marginal_gain = task.marginal_gain()
        decision = self.decide_marginal(marginal_gain)
        return EvaluationResult(
            score=score, level=level,
            marginal_gain=marginal_gain, decision=decision,
        )

    def decide_marginal(self, gain):
        if gain >= 20:
            self._consecutive_low = 0
            return {"action": "continue", "reason": f"high gain ({gain:.1f}%)"}
        elif gain >= 10:
            self._consecutive_low = 0
            return {"action": "continue_low_freq", "reason": f"medium gain ({gain:.1f}%)"}
        elif gain >= 5:
            self._consecutive_low += 1
            return {"action": "mark_risk", "reason": f"low gain ({gain:.1f}%)"}
        else:
            self._consecutive_low += 1
            if self._consecutive_low >= 3:
                return {"action": "force_stop", "reason": "3 consecutive low gains"}
            return {"action": "switch_strategy", "reason": f"very low gain ({gain:.1f}%)"}

    def reset_consecutive(self):
        self._consecutive_low = 0


class GLMEvaluator:
    """GLM-based evaluator for L1 tasks and L2 bottleneck analysis.

    Uses the GLM API to produce a qualitative assessment and score.
    This is more expensive but more nuanced than the rule evaluator.
    """

    def __init__(self, executor):
        self.executor = executor

    def evaluate(self, task, metrics):
        """Use GLM to evaluate task completion quality."""
        prompt = self._build_prompt(task, metrics)
        messages = [{"role": "user", "content": prompt}]
        result = self.executor.execute(messages, max_tokens=1024)

        if "error" in result:
            logger.warning(f"GLM evaluator error, falling back to rule: {result['error']}")
            return RuleEvaluator().evaluate(task, metrics)

        content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return self._parse_response(content, task)

    def _build_prompt(self, task, metrics):
        return (
            f"You are evaluating task completion quality.\n\n"
            f"Task: {task.title}\n"
            f"Instruction: {task.instruction}\n"
            f"Current strategy index: {task.current_strategy_index}\n"
            f"Current metrics:\n"
            f"  test_pass_rate: {metrics.get('test_pass_rate', 0)}\n"
            f"  boundary_coverage: {metrics.get('boundary_coverage', 0)}\n"
            f"  compile_ok: {metrics.get('compile_ok', False)}\n\n"
            f"Please respond with a JSON object containing:\n"
            f'  {{"score": <0-100>, "assessment": "<brief assessment>", '
            f'"marginal_gain_estimate": <0-100>}}\n'
            f"Where score is the estimated completion percentage."
        )

    def _parse_response(self, content, task):
        """Parse GLM response into EvaluationResult."""
        score = 50.0
        marginal = 0.0

        # Try to extract JSON from response
        try:
            # Find JSON block in markdown or plain text
            if "```" in content:
                json_str = content.split("```")[1]
                if json_str.startswith("json"):
                    json_str = json_str[4:]
            else:
                json_str = content
            data = json.loads(json_str.strip())
            score = float(data.get("score", 50))
            marginal = float(data.get("marginal_gain_estimate", 0))
        except (json.JSONDecodeError, IndexError, ValueError, TypeError):
            # Fallback: extract number from text
            import re
            scores = re.findall(r"score[\s:]*(\d+)", content, re.IGNORECASE)
            if scores:
                score = float(scores[-1])

        # Clamp
        score = max(0.0, min(100.0, score))
        marginal = max(-100.0, min(100.0, marginal))

        task.record_completion(score)
        gain = task.marginal_gain()
        if marginal == 0 and gain > 0:
            marginal = gain

        level = self._get_level(score)
        decision = RuleEvaluator().decide_marginal(marginal)

        return EvaluationResult(
            score=score, level=level,
            marginal_gain=marginal, decision=decision,
            details={"glm_assessment": True, "raw_response": content[:200]},
        )

    @staticmethod
    def _get_level(score):
        for threshold, level in [(90, "S"), (80, "A"), (60, "B")]:
            if score >= threshold:
                return level
        return "F"


class HybridEvaluator:
    """Automatically chooses RuleEvaluator or GLMEvaluator based on task level."""

    def __init__(self, glm_executor, bottleneck_threshold: float = 30.0):
        self.rule = RuleEvaluator()
        self.glm = GLMEvaluator(glm_executor)
        self.bottleneck_threshold = bottleneck_threshold

    def evaluate(self, task, metrics):
        if task.level == "L1":
            return self.glm.evaluate(task, metrics)
        elif task.level == "L2":
            # Rule by default, switch to GLM if score stagnates
            result = self.rule.evaluate(task, metrics)
            if (result.score < self.bottleneck_threshold
                    and result.marginal_gain < 10
                    and task.current_strategy_index > 0):
                logger.info(f"L2 bottleneck detected for {task.id}, switching to GLM evaluation")
                result = self.glm.evaluate(task, metrics)
            return result
        else:
            return self.rule.evaluate(task, metrics)

    def decide_marginal(self, gain):
        return self.rule.decide_marginal(gain)

    def reset_consecutive(self):
        self.rule.reset_consecutive()
