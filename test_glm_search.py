# -*- coding: utf-8 -*-
import asyncio
import sys
import os

sys.path.insert(0, r"D:\桌面\quant_backtest")

# Set API credentials
os.environ["GLM_API_KEY"] = "sk-4Zpdt2J6aGZLxWSUH13imJPDGlJ0XpcZcLaJkx36JG9Gync6"
os.environ["GLM_API_BASE"] = "https://yuanyuaicloud.cn/v1"
os.environ["GLM_MODEL"] = "glm-5.2"

from automation.config import Config
from automation.core import AutomationFramework

async def test_web_search():
    config = Config()
    config.api_key = os.environ["GLM_API_KEY"]
    config.api_base = os.environ["GLM_API_BASE"]
    config.model = os.environ["GLM_MODEL"]
    
    fw = AutomationFramework(config)
    
    print("[Testing] GLM-based web search...")
    print(f"  API: {config.api_base}")
    print(f"  Model: {config.model}")
    
    result = await fw.web_search.search("Python asyncio tutorial", n=3)
    
    print(f"\n[Result] Engine: {result.engine}")
    print(f"[Result] Latency: {result.latency_ms:.0f}ms")
    print(f"[Result] Results: {len(result.results)}")
    if result.error:
        print(f"[Result] Error: {result.error}")
    
    for i, r in enumerate(result.results):
        print(f"\n  [{i+1}] {r.title}")
        print(f"      URL: {r.url}")
        print(f"      Snippet: {r.snippet[:80]}...")
    
    await fw.executor.close_async()
    print("\n[OK] Web search test completed")

asyncio.run(test_web_search())
