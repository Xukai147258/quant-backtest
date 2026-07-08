# Task: CONTRIBUTING Guide

> **For agentic workers:** Write a comprehensive CONTRIBUTING.md.

**Goal:** Enable any developer to understand dev workflow, conventions, and PR process.

**Context:** https://github.com/Xukai147258/quant-backtest

- Branch strategy: feat/fix/refactor/docs/chore prefixes
- Commit convention: conventional commits with scope
- Code review: pr-review.rules (diff <= 400 lines, zero debug artifacts)
- Merge strategy: squash merge to main
- Testing: pytest, TDD encouraged

---

### File to Create

`.github/CONTRIBUTING.md`

Sections:
1. Getting Started - Python 3.13, from requirements.txt
2. Development Workflow - branch naming, commit format, pre-commit checklist
3. Testing - pytest tests/ -v
4. PR Process - create branch, test, PR, squash merge
5. Project Architecture Summary
6. Methodological Constraints (Purging/Embargo, walk-forward only)

**Steps:**
- [ ] Write `.github/CONTRIBUTING.md`
- [ ] `git add .github/CONTRIBUTING.md`
- [ ] `git commit -m "docs: add contributing guide"`