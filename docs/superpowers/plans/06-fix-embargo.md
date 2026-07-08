# Task: Fix Embargo Boundary Enforcement

> **For agentic workers:** Fix a P2 bug in the walkforward engine.

**Goal:** Add runtime boundary enforcement in `engine/walkforward.py` to ensure Purge and Embargo gaps are actively checked.
**Files:** `Modify: engine/walkforward.py` / Verify: `tests/test_walkforward.py`

**Context:** THE project uses Walk-Forward with Purging (5d) and Embargo (10d). This is a runtime safety check.

---

### Steps
1. Read `engine/walkforward.py` - focus on the `run()` method
2. After computing train end, test start, and test end for each step, add:
   `assert (test_start - train_end).days >= purge_days` 3. Run `pytest tests/test_walkforward.py -v`
4. commit: `git commit -m "fix(engine): add Purge/Embargo runtime enforcement"`