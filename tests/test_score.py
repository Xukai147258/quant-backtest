import pytest
from automation.score import ScoreEngine, TestItem


def test_passfail_all_pass():
    engine = ScoreEngine()
    items = [
        TestItem(name="compile", weight=50, scoring_mode="pass_fail", score=100, min_score=100),
        TestItem(name="test", weight=50, scoring_mode="pass_fail", score=100, min_score=100),
    ]
    total, level = engine.calculate(items)
    assert total == 100.0 and level == "S"


def test_mixed_modes():
    engine = ScoreEngine()
    items = [
        TestItem(name="hard", weight=40, scoring_mode="pass_fail", score=100, min_score=100),
        TestItem(name="quality", weight=60, scoring_mode="range", score=80, min_score=60),
    ]
    total, level = engine.calculate(items)
    assert total == 88.0 and level == "A"


def test_low_score():
    """Both items use range mode so no gate fires; weighted average is low."""
    engine = ScoreEngine()
    items = [
        TestItem(name="part_a", weight=50, scoring_mode="range", score=30, min_score=0),
        TestItem(name="part_b", weight=50, scoring_mode="range", score=30, min_score=0),
    ]
    total, level = engine.calculate(items)
    assert total == 30.0 and level == "F"


def test_level_mapping():
    engine = ScoreEngine()
    assert engine.get_level(95) == "S"
    assert engine.get_level(85) == "A"
    assert engine.get_level(70) == "B"
    assert engine.get_level(50) == "F"


def test_weight_normalization():
    engine = ScoreEngine()
    items = [
        TestItem(name="A", weight=25, scoring_mode="range", score=80, min_score=50),
        TestItem(name="B", weight=25, scoring_mode="range", score=90, min_score=50),
        TestItem(name="C", weight=25, scoring_mode="range", score=70, min_score=50),
        TestItem(name="D", weight=25, scoring_mode="range", score=60, min_score=50),
    ]
    total, level = engine.calculate(items)
    assert total == 75.0 and level == "B"


def test_min_score_gate_fail():
    """pass_fail item below min_score should zero the score."""
    engine = ScoreEngine()
    items = [
        TestItem(name="critical", weight=50, scoring_mode="pass_fail", score=0, min_score=100),
        TestItem(name="other", weight=50, scoring_mode="range", score=100, min_score=0),
    ]
    total, level = engine.calculate(items)
    assert total == 0.0 and level == "F"


def test_document_task():
    engine = ScoreEngine()
    item = engine.evaluate_document_task(90, 85, 80)
    total, level = engine.calculate([item])
    assert total == 86.0
    assert level == "A"


def test_qa_task():
    engine = ScoreEngine()
    item = engine.evaluate_qa_task(100, 70)
    total, level = engine.calculate([item])
    assert total == 88.0
    assert level == "A"


def test_detect_code_task():
    assert ScoreEngine.detect_task_type("fix CI workflow") == "code"
    assert ScoreEngine.detect_task_type("implement a function") == "code"


def test_detect_document_task():
    assert ScoreEngine.detect_task_type("write report") == "document"
    assert ScoreEngine.detect_task_type("analysis summary") == "document"


def test_detect_qa_task():
    assert ScoreEngine.detect_task_type("hello world") == "qa"


def test_evaluate_by_instruction_code():
    engine = ScoreEngine()
    item = engine.evaluate_by_instruction("fix CI", test_pass_rate=80, boundary_coverage=70, compile_ok=True)
    assert "code" in item.name
    assert item.score > 0


def test_evaluate_by_instruction_doc():
    engine = ScoreEngine()
    item = engine.evaluate_by_instruction("write document", structure_completeness=90, info_accuracy=80, format_score=70)
    assert "document" in item.name
    assert item.score > 0


def test_evaluate_by_instruction_qa():
    engine = ScoreEngine()
    item = engine.evaluate_by_instruction("what is the answer", goal_coverage=80, depth_index=60)
    assert "qa" in item.name
    assert item.score > 0


def test_empty_items():
    engine = ScoreEngine()
    total, level = engine.calculate([])
    assert total == 0.0 and level == "F"
