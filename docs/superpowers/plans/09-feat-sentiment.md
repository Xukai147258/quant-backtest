# Task: Connect Real Sentiment Data

> **For agentic workers:** Replace the sentiment stub with real news-based sentiment.

**Goal:** Make `engine/sentiment.py` produce non-trivial signals by connecting AKShare EastMoney news.

**Files:** `Modify: engine/sentiment.py` / Verify: `tests/test_e2e.py`

**Current state:** Sentiment is a stub. The orchestrator always receives `sentiment=0.5`.

**Approach:** Use AKShare's `stock_news_em` api to fetch news for ETFs, then score with keyword matching.

---

### Steps
1. Read `engine/sentiment.py` - understand the stub interface
2. Implement: `Fetch_news()` (AKShare EastMoney) + `score_sentiment()` (keyword-based)
3. Keep existing function signature for backward compatibility
4. Return float in [0, 1] (<0.4 bearish, 0.4-0.6 neutral, >0.6 bullish)
5. Run `pytest tests/test_e2e.py -v`
6. commit: `git commit -m "feat(sentiment): connect AKShare news API for real sentiment data"`