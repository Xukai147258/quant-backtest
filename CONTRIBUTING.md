# Contributing

## Branch Naming Convention

Use one of the following prefixes:

- ``task/`` — All development branches (project tasks and issues)
- `feat/` — New features or enhancements
- `fix/` — Bug fixes
- `refactor/` — Code restructuring without behavior change
- `docs/` — Documentation-only changes
- `chore/` — Build process, CI, or tooling changes

Examples: `feat/walkforward-embargo`, `fix/stamp-duty-edge-case`, `refactor/trust-check-phases`

The ``task/`` prefix is the standard convention for this project.

## PR Workflow

1. Create a branch from `master` with the appropriate prefix
2. Make your changes and ensure all tests pass: `pytest tests/ -v --tb=short`
3. Update CHANGELOG.md with the changes under the appropriate version heading
4. Open a pull request against `master` with a descriptive title

## Code Style

- Python 3.13+, UTF-8 encoding
- Import order: stdlib -> third-party -> local
- Type annotations on all public functions and methods
- Docstrings on all public modules, classes, and functions
- Line length: 120 characters max
- Use pathlib for file path operations

## Testing

- Run the full test suite before opening a PR: `pytest tests/ -v --tb=short`
- New features should include tests
- Bug fixes should include a regression test
- Minimum coverage threshold: 60%

## Trust-Check Framework

When adding a new check to the trust framework:

1. Add the check method to the appropriate phase module
2. Register it in the phase's `checks` list
3. Add a test in `tests/test_trust_check.py`
4. Verify the check runs in isolation and as part of the full pipeline

