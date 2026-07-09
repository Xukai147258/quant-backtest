import asyncio, sys
sys.path.insert(0, r"D:\桌面\quant_backtest")
from automation.web_search import WebSearchEngine

async def test():
    w = WebSearchEngine(cache_enabled=False, timeout=15)
    print("Testing Wikipedia API...")
    result = await w.search_wikipedia("Python programming language", n=3)
    print(f"Engine: {result.engine}")
    print(f"Results: {len(result.results)}")
    print(f"Error: {result.error}")
    for r in result.results:
        print(f"  - {r.title}")
        print(f"    {r.url}")
        print(f"    {r.snippet[:80]}...")
    await w.close()

asyncio.run(test())
