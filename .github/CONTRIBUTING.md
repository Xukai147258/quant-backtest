# Contributing to Quant-Backtest

Thank you for considering contributing to this project. This guide covers
development setup, workflow conventions, and the PR process.

---

## Getting Started

### Prerequisites

- **Python 3.13** -- the project targets this version.
- Conda / virtual environment recommended.

### Install Dependencies

```bash
pip install -r requirements.txt
```

Key dependencies: `akshare`, `pandas`, `numpy`, `scipy`, `hmmlearn`, `scikit-learn`.

---

## Development Workflow

### Branch Naming

Use one of the following prefixes:

| Prefix     | Purpose                          |
|------------|----------------------------------|
| `feat/`    | New feature                      |
| `fix/`     | Bug fix                          |
| `refactor/`| Code restructuring               |
| `docs/`    | Documentation changes            |
| `chore/`   | Tooling, dependencies, CI        |

Examples: `feat/sentiment-signal`, `fix/embargo-gap`, `docs/api-reference`.

### Commit Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>
```

Types: `feat`, `fix`, `docs`, `refactor`, `chore`, `test`.
Scope examples: `data`, `cost`, `metrics`, `walkforward`, `hmm`, `agents`, `ci`.

Examples:

```
feat(core): add sentiment signal integration
fix(walkforward): correct embargo day offset
docs: add contributing guide
```

### Pre-Commit Checklist

- [ ] No `print()`, `breakpoint()`, or other debug artifacts.
- [ ] Diff is <= 400 lines (split large changes into multiple PRs).
- [ ] All existing tests pass: `pytest tests/ -v`
- [ ] New code includes corresponding tests.
- [ ] No sensitive data, credentials, or local paths are committed.

---

## Testing

Run the full test suite:

```bash
pytest tests/ -v
```

**TDD is encouraged.** When adding a new module or fixing a bug, write or update
tests first.

The project maintains **20+ tests** covering data pipeline, cost model, metrics,
walk-forward backtesting, HMM detector, agent orchestration, and an end-to-end
integration test.

---

## PR Process

1. **Create a branch** from `main` using the naming convention above.
2. **Implement** your change with tests.
3. **Run tests** locally to confirm all pass.
4. **Open a PR** on GitHub against `main`.
   - Title follows conventional commit format.
   - Description summarises the change and its motivation.
   - Keep the diff <= 400 lines.
5. **Code review** -- a maintainer reviews the PR against the project's
   review rules (zero debug artifacts, no lookahead bias, scope discipline).
6. **Squash merge** into `main` -- the commit message becomes the squash
   message; individual fixup commits are not preserved.

---

## Project Architecture Summary

```
quant-backtest/
+-- core/               # Data, cost model, metrics
+-- engine/             # Walk-forward backtest, HMM detector, sentiment
+-- agents/             # Builder -> Critic -> Meta-Learner orchestration
+-- knowledge/          # Checklist, literature, framework comparison
+-- tests/              # 20+ unit + integration tests
+-- main.py             # Entry point
+-- report.py           # Report generator
```

The system implements an **AI-powered quantitative backtesting framework**
for a **9-ETF portfolio** (A-share large/mid cap, tech, bonds, gold) with
monthly/quarterly rebalancing and a 1-3 year holding horizon.

**Data flow:**
AKShare -> fetch -> clean (Winsorize, fill halt) -> split -> walk-forward pipeline

**Agent decision loop (each quarter):**
```
Builder -> propose weights
   |
Critic -> review (66-point checklist)
   |
Meta-Learner -> arbitrate & record
   | (next quarter)
Orchestrator -> Meta-Learner.update()
```

---

## Methodological Constraints

This project follows the methodology from
*Advances in Financial Machine Learning* (Lopez de Prado). All contributions
must respect these constraints:

### Purging & Embargo

- **Purging:** Training data must exclude the `purge_days` (~5 trading days)
  immediately before each test period so that test-period labels cannot leak
  into the training set.
- **Embargo:** After each test period, the next `embargo_days` (~10) of data
  are excluded from the next training window.

### Walk-Forward Only

- Backtesting uses an **expanding window** (train >= 3 years, step = 3 months).
- Test data always follows the training data in time.
- No full-sample or pseudo-out-of-sample designs are permitted.

### No Lookahead Bias

- All feature computation, HMM fitting, and scaling must use **only data
  available up to the training cutoff**.
- `StandardScaler` parameters must be fit on the training set only.
- HMM must be re-fit each window with no access to future states.

### Code Review Rules

All PRs are checked against the project's review rules:
- Diff <= 400 lines.
- Zero debug artifacts (`print`, `breakpoint`, etc.).
- Zero lookahead bias.
