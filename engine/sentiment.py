# engine/sentiment.py -- Real sentiment analysis using AKShare EastMoney news
#                       with keyword-based scoring.

import logging
from typing import Any, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


BULLISH_KEYWORDS: List[str] = [
    "上涨", "利好", "突破", "反弹", "增长",
    "创新高", "放量", "强势", "提振",
    "超预期", "牛市", "拉升", "涨幅",
    "盈利", "向上", "看涨", "做多",
    "增持", "买入", "推荐", "景气",
    "复苏", "扩张", "回升", "改善",
    "加速", "红盘", "领涨", "上扬",
    "飙涨", "走强",
]

BEARISH_KEYWORDS: List[str] = [
    "下跌", "利空", "破位", "回调", "下滑",
    "创新低", "缩量", "弱势", "拖累",
    "不及预期", "熊市", "暴跌", "跌幅",
    "亏损", "向下", "看跌", "做空",
    "减持", "卖出", "回避", "衰退",
    "收缩", "低迷", "回落", "恶化",
    "减速", "绿盘", "领跌", "下挛",
    "重挛", "走弱",
]


class RollingSentimentAnalyzer:
    def __init__(self, window: int = 20) -> None:
        self.window = window
        self.default_symbols = ["510300", "159919", "510050"]

    def compute_index(self, news_data: Any) -> float:
        try:
            if isinstance(news_data, dict) and "symbols" in news_data:
                symbols = news_data["symbols"]
                news_df = self._fetch_news(symbols)
            elif isinstance(news_data, list):
                return self._score_texts(news_data)
            elif isinstance(news_data, pd.DataFrame):
                news_df = news_data
            else:
                news_df = self._fetch_news(self.default_symbols)

            if news_df is None or news_df.empty:
                logger.warning("No news data; returning neutral 0.5")
                return 0.5

            scores = self._score_news_df(news_df)
            if not scores:
                return 0.5
            return float(np.mean(scores))

        except Exception as exc:
            logger.error("Sentiment computation failed: %s", exc)
            return 0.5

    def _fetch_news(self, symbols: List[str]) -> Optional[pd.DataFrame]:
        try:
            import akshare
        except ImportError:
            logger.warning("akshare not installed; falling back to neutral")
            return None

        dfs: List[pd.DataFrame] = []
        for sym in symbols:
            try:
                df = akshare.stock_news_em(sym)
                if df is not None and not df.empty:
                    dfs.append(df)
            except Exception as exc:
                logger.debug("Failed to fetch news for %s: %s", sym, exc)

        return pd.concat(dfs, ignore_index=True) if dfs else None

    def _score_news_df(self, news_df: pd.DataFrame) -> List[float]:
        texts: List[str] = []
        if "新闻标题" in news_df.columns:
            texts.extend(news_df["新闻标题"].dropna().tolist())
        if "新闻内容" in news_df.columns:
            texts.extend(news_df["新闻内容"].dropna().tolist())
        return [self._score_text(t) for t in texts]

    def _score_texts(self, texts: List[str]) -> float:
        if not texts:
            return 0.5
        return float(np.mean([self._score_text(t) for t in texts]))

    @staticmethod
    def _score_text(text: str) -> float:
        if not text or not isinstance(text, str):
            return 0.5
        pos = sum(1 for kw in BULLISH_KEYWORDS if kw in text)
        neg = sum(1 for kw in BEARISH_KEYWORDS if kw in text)
        total = pos + neg
        return 0.5 if total == 0 else pos / total
