# -*- coding: utf-8 -*-
import asyncio
import sys
sys.path.insert(0, r"D:\桌面\quant_backtest")
from automation.web_search import WebSearchEngine

async def test():
    w = WebSearchEngine(cache_enabled=False)
    print("Testing SearXNG search...")
    result = await w.search("Python asyncio", n=3)  # Use n instead of max_results
    print(f"Engine: {result.engine}")
    print(f"Results: {len(result.results)}")
    print(f"Error: {result.error}")
    for r in result.results[:3]:
        print(f"  - {r.title}: {r.snippet[:50]}...")
    await w.close()

asyncio.run(test())
