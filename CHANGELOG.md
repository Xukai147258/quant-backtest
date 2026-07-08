# Changelog

## v0.1.0 (2026-07-08)

### Features
- Walk-Forward backtesting engine with Purging/Embargo look-ahead prevention
- HMM rolling regime detection (4 states, no look-ahead bias)
- Triple-agent decision pipeline: Builder ? Critic ? MetaLearner
- 9-ETF portfolio (??300/??500/???/??50/??50/??ETF/????/??ETF/??ETF)

### Infrastructure
- Git repository initialized and pushed to GitHub
- .gitignore configured for Python + quant output directories
- GitHub classic PAT configured for credential storage

### Testing
- 20/20 unit tests passing across all modules
- End-to-end 12-step walk-forward integration test

### Known Issues
- [P2] Embargo boundary not actively enforced in walkforward runner
- [P3] Critic uses substring matching instead of semantic evaluation
- [P3] test_critic.py and test_meta_learner.py exist but may be incomplete
- [P3] sentiment.py is a stub ? no real news API connected
