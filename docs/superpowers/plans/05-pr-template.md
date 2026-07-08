# Task: PR Template + Branch Protection

> **For agentic workers:** This is a standalone project management task.

**Goal:** Create `.github/PULL_REQUEST_TEMPLATE.md` and document branch protection rules.

**Context:** https://github.com/Xukai147258/quant-backtest
Merge strategy: squash merge. No force push to main. No direct commits to main.

---

### File to Create

`.github/PULL_REQUEST_TEMPLATE.md`

Sections:
- Change summary
- Related issues
- Testing done
- PR Checklist:
  - [ ] Diff under 400 lines
  - [ ] All tests pass
  - [ ] Zero debug artifacts (console.log, print, debugger)
  - [ ] Zero hardcoded secrets
  - [ ] CHANGELOG.md updated (if user-facing)

***Branch Protection:*** (document only - requires GitHub web UI)
- Require Pull Request before merging
 - Require status checks (Tests/pytest) to pass
 - Require branches to be up to date
- Do not allow bypassing
**Steps:**
- [ ] Write `.github/PULL_REQUEST_TEMPLATE.md`
- [ ] `git add .github/PULL_REQUEST_TEMPLATE.md`
- [ ] `git commit -m "docs: add PR template"`