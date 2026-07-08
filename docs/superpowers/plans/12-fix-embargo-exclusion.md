# Task: Fix Embargo Exclusion in Walkforward

> For agentic workers: Fix the embargo zone exclusion so it actually reduces training data.

**Goal:** Make `test_embargo_actually_excludes_data` pass: `AssertionError: Step 1: embargo=303 >= no_embargo=303`.

**Root cause:** The training data cutoff is computed as `train_cutoff = train_end_date - purge_days`, which places the training window BEFORE the previous test_end. The embargo zone `[prev_test_end, prev_test_end + embargo]` starts AFTER the training cutoff, so the exclusion has no effect.

**Fix:** Change the training data computation to use ALL data up to `train_end_date` (no purge cutoff), then apply Purging and Embargo as exclusion masks WITHIN that range. This way the training window extends past the previous test_end, and the embargo zone can actually overlap with training data.

**Files:**
- Modify: `engine/walkforward.py` lines 102-113
- Verify: `pytest tests/test_walkforward.py::test_embargo_actually_excludes_data -v`
- Verify all existing walkforward tests still pass

**Current code (lines 102-113):**
```python
# Purging: 训练集截至 train_end - purge_days
train_cutoff = train_end_date - timedelta(days=self.purge_days)
train_mask = idx <= train_cutoff
# T1: Embargo exclusion
if prev_test_end_date is not None:
    embargo_start = prev_test_end_date
    embargo_end = prev_test_end_date + timedelta(days=self.embargo_days)
    train_mask = train_mask & ~((idx >= embargo_start) & (idx <= embargo_end))

if train_mask.sum() < 20:
    break
train_data = self.prices.loc[idx[train_mask]]
```

**Fix:**
```python
# Lopez de Prado: training includes ALL data up to train_end_date
# Then Purging removes labels overlapping with test, Embargo removes serial corr zone
train_mask = idx <= train_end_date

# Purging: 排除与测试集标签重叠的数据
purge_start = train_end_date - timedelta(days=self.purge_days)
train_mask = train_mask & ~((idx >= purge_start) & (idx <= train_end_date))

# T1: Embargo exclusion — 排除上一轮测试结束后的序列相关区间
if prev_test_end_date is not None:
    embargo_start = prev_test_end_date
    embargo_end = prev_test_end_date + timedelta(days=self.embargo_days)
    train_mask = train_mask & ~((idx >= embargo_start) & (idx <= embargo_end))
```

**Important:** The test_start computation (line 116) still uses `train_end_date + purge_days` and is unchanged. This ensures test data is properly separated from training.

**Steps:**
- [ ] Read `engine/walkforward.py` lines 96-130 to understand the full run loop
- [ ] Apply the fix to change purge from cutoff to exclusion mask
- [ ] Run `pytest tests/test_walkforward.py -v` — all 4 tests should PASS
- [ ] Run `pytest tests/test_e2e.py -v` — ensure e2e still passes
- [ ] Commit: `git commit -m "fix: apply purge as exclusion mask so embargo can affect training window"`
