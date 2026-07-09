# -*- coding: utf-8 -*-

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str
    rank: int = 0
    timestamp: float = field(default_factory=time.time)

@dataclass
class SearchResponse:
    query: str
    results: list
    engine: str
    latency_ms: float
    cached: bool = False
    error: Optional[str] = None

class WebSearchEngine:
    def __init__(self, glm_executor=None, cache_enabled=True, ttl=3600):
        self.glm_executor = glm_executor
        self.cache_enabled = cache_enabled
        self.ttl = ttl
        self._cache = {}
        self._ts = {}

    def check_cache(self, q):
        if not self.cache_enabled:
            return None
        key = q.lower().strip()
        if key in self._cache and time.time() - self._ts.get(key, 0) < self.ttl:
            r = self._cache[key]
            r.cached = True
            return r
        return None

    def save_cache(self, q, r):
        if self.cache_enabled:
            key = q.lower().strip()
            self._cache[key] = r
            self._ts[key] = time.time()

    async def search(self, query, n=5, engines=None):
        cached = self.check_cache(query)
        if cached:
            return cached

        if not self.glm_executor:
            return SearchResponse(query, [], "fallback", 0, error="no GLM executor configured")

        start = time.time()
        try:
            prompt = f"Search the web for: {query}. Return top {n} results as JSON array with title, url, snippet fields."
            messages = [{"role": "user", "content": prompt}]
            result = await self.glm_executor.execute_async(messages, max_tokens=1024)

            if "error" in result:
                return SearchResponse(query, [], "glm", 0, error=result["error"])

            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            results = self._parse_glm_response(content, n)

            resp = SearchResponse(query, results, "glm", (time.time() - start) * 1000)
            self.save_cache(query, resp)
            return resp
        except Exception as e:
            return SearchResponse(query, [], "glm", 0, error=str(e))

    def _parse_glm_response(self, content, n):
        import json
        import re
        results = []
        try:
            if "`json" in content:
                content = content.split("`json")[1].split("`")[0]
            elif "`" in content:
                content = content.split("`")[1].split("`")[0]
            data = json.loads(content.strip())
            for i, item in enumerate(data[:n]):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    source="glm",
                    rank=i
                ))
        except (json.JSONDecodeError, TypeError):
            urls = re.findall(r"https?://[^\s]+", content)
            titles = re.findall(r"title[:\s]+([^\n]+)", content, re.IGNORECASE)
            for i in range(min(len(urls), n)):
                results.append(SearchResult(
                    title=titles[i] if i < len(titles) else urls[i][:50],
                    url=urls[i],
                    snippet="",
                    source="glm",
                    rank=i
                ))
        return results

    async def search_batch(self, queries, n=3):
        return await asyncio.gather(*[self.search(q, n) for q in queries])

    def get_stats(self):
        return {"cache_size": len(self._cache), "cache_enabled": self.cache_enabled}