# tests/test_quota.py
import pytest
from automation.quota import QuotaManager

def test_initial_state():
    q = QuotaManager(max_calls=1000, refresh_hours=5)
    assert q.remaining == 1000 and q.total_used == 0

def test_consume():
    q = QuotaManager(max_calls=1000, refresh_hours=5)
    assert q.consume() == True
    assert q.remaining == 999 and q.total_used == 1

def test_exhausted():
    q = QuotaManager(max_calls=3, refresh_hours=5)
    for _ in range(3): q.consume()
    assert q.remaining == 0 and q.consume() == False

def test_refresh():
    q = QuotaManager(max_calls=3, refresh_hours=5)
    for _ in range(3): q.consume()
    q._force_refresh()
    assert q.remaining == 3

def test_state_report():
    q = QuotaManager(max_calls=3, refresh_hours=5)
    q.consume()
    s = q.get_state()
    assert s["remaining"] == 2 and s["total_used"] == 1
