# Changelog

## v0.2.1 (2026-07-09) - P0/P1 Critical Fixes

### P0 Blocking Issues Resolved
- [WKF-001] Fixed Embargo semantic error: exclusion interval now correctly uses `[prev_test_end, prev_test_end + embargo_days]`
- [CI-001] Fixed CI pipeline: added Python version verification, removed `continue-on-error`, triggers on task/** branches

### P1 High Priority Issues Resolved
- [CI-002] CI pull_request trigger now includes `task/**` branches
- [GIT-001] CONTRIBUTING.md now includes `task/` prefix as standard branch naming convention
- [GIT-002] master synced with origin/master
- [COST-001] stamp_duty verified as 0.0005 (already correct in code)

### P2 Medium Priority Issues Resolved
- [TEST-001] Empty test files deleted (test_critic.py, test_meta_learner.py)
- [CI-003] Coverage integrated into CI workflow (`--cov-fail-under=60`)
- [GIT-003/GIT-004] Temp debug files cleaned (fix_*.py, patch_*.py, etc.)

### Engineering Review Report
- Generated comprehensive review report: `docs/ENGINEERING_REVIEW_REPORT.md`
- Total score: 22.6/100 (F level) due to P0 blockers
- All 153 unit tests passing after fixes

## v0.2.0 (2026-07-08)

### Trust-Check Framework
- Added 4-phase trust-check system (29 checks total)
- Phase 1A: 6 lookahead-bias prevention checks
- Phase 1B: 5 structural overfitting checks
- Phase 2: 6 engineering implementation checks
- Phase 3: 8 strategy reasonableness checks
- Serial execution with fail-fast on any check failure
- Supports dev/full/final three modes

### Runtime Probes
- WalkForward: added embargo_log (step-level embargo exclusion tracking)
- WalkForward: added signal_log (step-level signal recording)
- HMM Detector: added fit_start/fit_end date tracking
- HMM Detector: added scaler lifecycle tracking (mean/scale per fit)

### Automation Integration
- NEW: automation/trust_gate.py — adapter bridging trust-check into automation loop
- TrustGate runs 4-phase checks as optional gating step before API calls
- meta_health.py now tracks trust-check results for health evaluation
- Configurable trust_mode and trust_gate_enabled in automation config

### Bug Fixes
- [P0] Embargo boundary now actively enforced in walkforward runner
- [P0] CI stamp_duty edge case fixed
- [P1] WalkForward edge case tests added
- [P2] .gitignore updated for log/temp/backup artifacts
- [P3] Temp file cleanup in trust-check tests
- Fixed phase2.py C2 data_alignment check (missing pandas import, broken isinstance)
- Fixed phase1a.py A6 check to handle string dates

### Infrastructure
- main.py run_backtest() now importable as from main import run_backtest
- Git branch naming standardized: feat/fix/refactor/docs/chore prefixes
- CONTRIBUTING.md added with PR workflow and code style guidelines

### Testing
- 153/153 unit tests passing across all modules
- Check-trust framework: 11 dedicated tests
- Trust-gate integration: 6 end-to-end tests
- WalkForward integration tests covering embargo + signal logs
