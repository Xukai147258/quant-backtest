# Task: Issue Templates Setup

> **For agentic workers:** This is a standalone project management task.

**Goal:** Create `.github/ISSUE_TEMPLATE/bug_report.md` and `.github/ISSUE_TEMPLATE/feature_request.md`.

**Context:** https://github.com/Xukai147258/quant-backtest

- Branch strategy: feat/fix/refactor/docs/chore prefixes
- Commit format: conventional commits
- 20/20 tests pass

<br> /* Horizontal rule between sections */

### Files to Create

**File 1:** `.github/ISSUE_TEMPLATE/bug_report.md`
 - Description of the bug
 - Steps to reproduce
 - Expected vs actual behavior
 - Environment (Version, OS, deps)
 - Priority suggestion (P0-P3)
 - Pre-submit checklist (secrets, debug artifacts)

**File 2:** `.github/ISSUE_TEMPLATE/feature_request.md`
 - Feature description and motivation
 - Proposed solution
 - Alternatives considered
 - Methodological impact check

**Steps:**
 - [ ] Create directories `.github/ISSUE_TEMPLATE/`
 - [ ] Write `bug_report.md`
 - [ ] Write `feature_request.md`
 - [ ] `git add .github/`
 - [ ] `git commit -m "docs: add issue templates"`