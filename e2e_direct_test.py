# -*- coding: utf-8 -*-
"""Direct test: auto web search logic in _execute_task_logic"""
import asyncio
import sys
import os
import logging

logging.basicConfig(level=logging.INFO)

sys.path.insert(0, r"D:\桌面\quant_backtest")
os.environ["GLM_API_KEY"] = "sk-4Zpdt2J6aGZLxWSUH13imJPDGlJ0XpcZcLaJkx36JG9Gync6"
os.environ["GLM_API_BASE"] = "https://yuanyuaicloud.cn/v1"
os.environ["GLM_MODEL"] = "glm-5.2"

from automation.config import Config
from automation.core import AutomationFramework
from automation.task_queue import Task

async def test_auto_web_search_direct():
    config = Config()
    config.api_key = os.environ["GLM_API_KEY"]
    config.api_base = os.environ["GLM_API_BASE"]
    config.model = os.environ["GLM_MODEL"]

    fw = AutomationFramework(config)
    
    # Task that triggers auto web search
    task = Task(
        id="T1",
        level="L2",
        instruction="Find the latest AI news and summarize",
        strategies=[{"name": "default", "description": "summarize"}],
    )
    
    print("[1] Check _should_auto_search trigger...")
    triggered = fw._should_auto_search(task)
    print(f"  Triggered: {triggered}")
    assert triggered, "Auto search should trigger for 'latest'"
    
    print("[2] Check _extract_search_query...")
    query = fw._extract_search_query(task)
    print(f"  Query: {query}")
    assert len(query) > 0, "Should extract non-empty query"
    
    print("[3] Execute task logic (includes auto web search)...")
    result = await fw._execute_task_logic(task)
    print(f"  Result success: {result.get('success')}")
    print(f"  Result action: {result.get('action')}")
    print(f"  Result score: {result.get('score')}")
    
    print("[4] Verify web context was injected...")
    has_context = "[Web Context:]" in task.instruction
    print(f"  Web context auto-injected: {has_context}")
    
    if has_context:
        context_section = task.instruction.split("[Web Context:]")[1][:200]
        print(f"  Context preview: {context_section[:100]}...")
    
    print(f"\n[DONE] Quota used: {fw.quota.total_used}")
    
    await fw.executor.close_async()
    return has_context

result = asyncio.run(test_auto_web_search_direct())
print(f"\n[E2E] Auto web search test {'PASSED' if result else 'FAILED'}")
