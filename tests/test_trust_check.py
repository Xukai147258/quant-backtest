# coding: utf-8
"""Tests for trust-check framework."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from check_trust.core import TrustCheckRunner, CheckResult, CheckMode, PhaseBase
from check_trust.phase1a import Phase1A
from check_trust.phase1b import Phase1B
from check_trust.phase2 import Phase2
from check_trust.phase3 import Phase3


def test_check_result():
    r = CheckResult("T1", "Test", True, "OK")
    assert r.check_id == "T1"
    assert r.passed == True


def test_runner_empty():
    runner = TrustCheckRunner(CheckMode.DEV)
    assert runner.run({}) == True
    report = runner.generate_report()
    assert report["total_checks"] == 0


def test_runner_phase_base():
    class TestPhase(PhaseBase):
        def run_all(self, ctx):
            self.results.append(CheckResult("X1", "Always pass", True, "ok"))
            return self.results
    runner = TrustCheckRunner()
    runner.add_phase(TestPhase())
    assert runner.run({}) == True
    assert runner.generate_report()["total_checks"] == 1


def test_runner_serial_stop():
    class FailPhase(PhaseBase):
        def run_all(self, ctx):
            self.results.append(CheckResult("F1", "Fail", False, "intentional"))
            return self.results
    class PassPhase(PhaseBase):
        def run_all(self, ctx):
            self.results.append(CheckResult("P1", "Pass", True, "ok"))
            return self.results
    runner = TrustCheckRunner()
    runner.add_phase(FailPhase())
    runner.add_phase(PassPhase())
    result = runner.run({})
    assert result == False  # stopped at FailPhase
    assert len(runner.all_results) == 1  # only FailPhase results


def test_phase1a_empty_context():
    p = Phase1A()
    results = p.run_all({})
    assert len(results) == 6
    assert all(r.passed for r in results)  # all skip with no data


def test_phase1a_with_intervals():
    p = Phase1A()
    ctx = {
        "walkforward_test_intervals": [
            {"train_end": datetime(2020, 1, 1), "test_start": datetime(2020, 1, 6), "test_end": datetime(2020, 2, 1)},
            {"train_end": datetime(2020, 4, 1), "test_start": datetime(2020, 4, 7), "test_end": datetime(2020, 5, 1)},
        ]
    }
    results = p.run_all(ctx)
    a1 = [r for r in results if r.check_id == "A1"][0]
    assert a1.passed == True


def test_phase1a_embargo():
    p = Phase1A()
    ctx = {
        "embargo_log": [
            {"step": 1, "prev_test_end": "2020-02-01", "embargo_start": "2020-02-01", "embargo_end": "2020-02-11", "excluded_count": 0},
        ]
    }
    results = p.run_all(ctx)
    a2 = [r for r in results if r.check_id == "A2"][0]
    assert a2.passed == True


def test_phase1b_empty():
    p = Phase1B()
    results = p.run_all({})
    b1 = [r for r in results if r.check_id == "B1"][0]
    assert b1.passed == False  # no cost model


def test_mode_enum():
    assert CheckMode.DEV.value == "dev"
    assert CheckMode.FULL.value == "full"
    assert CheckMode.FINAL.value == "final"


def test_phase2_import():
    # Phase2 requires subprocess to run pytest, just verify it imports
    from check_trust.phase2 import Phase2
    assert Phase2 is not None


def test_phase3_import():
    from check_trust.phase3 import Phase3
    assert Phase3 is not None
