# Task: Fix Data Pipeline Length Mismatch

> For agentic workers: Fix a pre-existing pandas 3.0 compatibility bug in core/data.py.

**Goal:** Fix `ValueError: Length of values (240) does not match length of index (241)` in `clean_data()` when reconstructing prices from winsorized returns.

**Root cause:** Line 107: `cleaned_returns = result.pct_change().dropna()` produces N-1 rows (first row is NaN from pct_change, then dropped). The `cumprod()` at line 130 also has N-1 values. But line 131 assigns these N-1 values to `result[col]` which has N rows.

**Fix:** Prepend the initial value (1.0, representing no change on day 0) to the cumulative returns array so lengths match.

**Files:**
- Modify: `core/data.py` line 130-131
- Verify: `pytest tests/test_data.py -v`

**Current code (lines 127-131):**
```python
base_price = result[col].iloc[0]
cum_rets = (1.0 + clipped_rets.fillna(0.0)).cumprod()
result[col] = base_price * cum_rets.values
```

**Fix:**
```python
base_price = result[col].iloc[0]
cum_rets = (1.0 + clipped_rets.fillna(0.0)).cumprod()
# Prepend 1.0 (no change on day 0) to align N-1 cumprod array with N-length DataFrame
cum_rets_aligned = np.concatenate([[1.0], cum_rets.values])
result[col] = base_price * cum_rets_aligned
```

**Steps:**
- [ ] Read `core/data.py` lines 105-135 to understand the clean_data flow
- [ ] Apply the fix at line 130-131
- [ ] Run `pytest tests/test_data.py -v` — expect 3 tests to PASS
- [ ] Commit: `git commit -m "fix: align cumprod length with DataFrame index in clean_data"`
