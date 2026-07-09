import pytest
from automation.evaluator import RuleEvaluator, HybridEvaluator
from automation.task_queue import Task
from automation.config import Config


def test_rule_evaluator_code():
    evaluator = RuleEvaluator()
    task = Task(id="T1", level="L2", instruction="fix the ci workflow")
    result = evaluator.evaluate(task, {"test_pass_rate": 80, "boundary_coverage": 70, "compile_ok": True})
    assert result.score > 0
    assert result.level in ("S", "A", "B", "F")


def test_marginal_continue():
    e = RuleEvaluator()
    d = e.decide_marginal(35.0)
    assert d["action"] == "continue"


def test_marginal_switch():
    e = RuleEvaluator()
    d = e.decide_marginal(3.0)
    assert d["action"] == "switch_strategy"


def test_marginal_consecutive_stop():
    e = RuleEvaluator()
    e.decide_marginal(3.0)
    e.decide_marginal(4.0)
    d = e.decide_marginal(2.0)
    assert d["action"] == "force_stop"


def test_marginal_mark_risk():
    e = RuleEvaluator()
    d = e.decide_marginal(7.0)
    assert d["action"] == "mark_risk"


def test_reset_consecutive():
    e = RuleEvaluator()
    e.decide_marginal(3.0)
    e.decide_marginal(3.0)
    e.reset_consecutive()
    d = e.decide_marginal(3.0)
    # After reset, consecutive count is 0, so first low gain -> switch_strategy
    assert d["action"] == "switch_strategy"


def test_hybrid_evaluator_fallback():
    """HybridEvaluator with no real executor should fallback cleanly for L1."""
    config = Config()
    config.api_key = "test-key"
    from automation.executor import GLMExecutor
    executor = GLMExecutor(config)
    hybrid = HybridEvaluator(executor)
    task = Task(id="T1", level="L1", instruction="fix ci")
    result = hybrid.evaluate(task, {"test_pass_rate": 80, "boundary_coverage": 70, "compile_ok": True})
    assert result.score > 0
