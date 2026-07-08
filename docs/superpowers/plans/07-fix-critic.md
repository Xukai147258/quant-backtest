# Task: Upgrade Critic Evaluation Logic

> **For agentic workers:** Fix a "P3" tech-debt issue in the Critic agent.

**Goal:** Replace substring matching (`_evaluate_check`) with structured parsing of the checklist.

**Files:** `Modify: agents/critic.py` / `Modify: knowledge/checklist.md` / Verify: `tests/test_critic.py`

**Current problem:** `_evaluate_check` uses Python `in` (substring match) to check if a checklist item passes. This can miss context-dependent items.

**Solution:** Parse checklist into structured items with machine-readable fields.

---

### Steps
1. Read `agents/critic.py` and `knowledge/checklist.md`
2. Add structured markers to checklist.md (e.g. `### [PURGE] Purging gap verification`)
3. Update `_evaluate_check` to parse and compare structured values
4. Run `pytest tests/test_critic.py tests/test_agents.py -v`
5. commit: `git commit -m "refactor(critic): replace substring matching with structured parsing"`