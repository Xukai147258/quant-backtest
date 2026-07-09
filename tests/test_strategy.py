import pytest
from automation.strategy import StrategyManager


def test_diversity_ok():
    sm = StrategyManager()
    strategies = [
        {"name": "A: fix workflow", "description": "modify YAML"},
        {"name": "B: fix deps", "description": "modify pip install"},
    ]
    assert sm.check_diversity(strategies) == True


def test_diversity_fail():
    sm = StrategyManager()
    assert sm.check_diversity([]) == False
    assert sm.check_diversity([{"name": "A", "description": "only one"}]) == False


def test_budget_exceeded():
    sm = StrategyManager()
    result = sm.calculate_budget(800, 1000)
    assert result["allowed"] == False


def test_budget_ok():
    sm = StrategyManager()
    result = sm.calculate_budget(300, 1000)
    assert result["allowed"] == True


def test_select_best():
    sm = StrategyManager()
    strategies = [{"name": "A", "description": "first"}]
    assert sm.select_best(strategies) == strategies[0]
    assert sm.select_best([]) is None
