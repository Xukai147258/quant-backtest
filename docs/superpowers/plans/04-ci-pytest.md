# Task: CI Pipeline — pytest

> **For agentic workers:** This is a standalone CI/CD task. Create a GitHub Actions workflow that runs pytest on every push and PR.

**Goal:** Every push to any branch and every PR to main automatically runs the 20 tests and reports pass/fail status.

**Context:** Repository https://github.com/Xukai147258/quant-backtest
- Python 3.13
- Dependencies in equirements.txt
- Test framework: pytest
- Tests in 	ests/ — 20 tests across 7 test files

---

### File to Create

.github/workflows/test.yml

`yaml
name: Tests
on:
  push:
    branches: [ '**' ]
  pull_request:
    branches: [ master, main ]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
          cache: 'pip'
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v --tb=short
`

**Important:** The tests use AKShare for real-time mode and mock data for quick mode (python main.py uses mock, --realtime uses AKShare). Ensure CI uses mock mode by default.

**Steps:**
- [ ] Create .github/workflows/test.yml
- [ ] git add .github/workflows/test.yml
- [ ] git commit -m \"ci: add pytest workflow\"

**Note:** The CI workflow won't execute until pushed to GitHub. After push, verify the Action runs at https://github.com/Xukai147258/quant-backtest/actions
