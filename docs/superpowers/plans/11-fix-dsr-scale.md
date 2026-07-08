# Task: Fix DSR Formula Scale Mismatch

> For agentic workers: Fix a bug in compute_dsr where annualized Sharpe is used with daily observation count, causing inflated DSR values.

**Goal:** Fix `assert 18.104034 < (0.957651 - 0.1)` — DSR should always be lower than Sharpe, but it's 18x higher because the variance formula assumes Sharpe and T are on the same time scale.

**Root cause:** In `compute_all_metrics` at line 148: `n_obs = len(returns)` — this is the number of DAILY observations (e.g., 500 days). But `sharpe` at line 102 is ANNUALIZED. The DSR formula `Var(SR) = (1 + ...) / (n_obs - 1)` assumes Sharpe and n_obs use the same time scale.

**Fix:** Convert n_obs from days to years: `n_years = len(returns) / ann_factor` before passing to `compute_dsr`.

**Files:**
- Modify: `core/metrics.py` line 148-149
- Verify: `pytest tests/test_metrics.py::test_dsr_uses_real_n_trials -v`

**Current code (lines 146-149):**
```python
# --- DSR ---
# n_obs = 观测数量（日频≈252/年），Harvey-Liu-Zhu (2016) 公式使用观测数
n_obs = len(returns)
dsr_result = compute_dsr(sharpe, n_trials, n_obs, skewness, kurtosis)
```

**Fix:**
```python
# --- DSR ---
# n_obs must be in the same time scale as Sharpe. Sharpe is annualized, so n_obs = years.
n_obs = max(len(returns) / ann_factor, 1.5)
dsr_result = compute_dsr(sharpe, n_trials, n_obs, skewness, kurtosis)
```

Also update the guard in `compute_dsr` at line 228 — change `n_obs < 1.5` to `n_obs < 1.0` since we now pass years directly.

**Steps:**
- [ ] Read `core/metrics.py` lines 146-149 and `compute_dsr` function at line 195
- [ ] Apply fix to convert n_obs from days to years
- [ ] Update the guard clause in compute_dsr line 228
- [ ] Run `pytest tests/test_metrics.py::test_dsr_uses_real_n_trials -v`
- [ ] Run `pytest tests/test_metrics.py -v` — all tests should PASS
- [ ] Commit: `git commit -m "fix: align DSR n_obs time scale with annualized Sharpe"`
