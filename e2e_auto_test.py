# -*- coding: utf-8 -*-
"""E2E test: auto web search + concurrent scheduling"""
import asyncio
import sys
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(message)s")

sys.path.insert(0, r"D:\桌面\quant_backtest")

os.environ["GLM_API_KEY"] = "sk-4Zpdt2J6aGZLxWSUH13imJPDGlJ0XpcZcLaJkx36JG9Gync6"
os.environ["GLM_API_BASE"] = "https://yuanyuaicloud.cn/v1"
os.environ["GLM_MODEL"] = "glm-5.2"

from automation.config import Config
from automation.core import AutomationFramework
from automation.task_queue import TaskQueue, Task

async def test_auto_search_e2e():
    config = Config()
    config.api_key = os.environ["GLM_API_KEY"]
    config.api_base = os.environ["GLM_API_BASE"]
    config.model = os.environ["GLM_MODEL"]

    fw = AutomationFramework(config)
    
    # Create a task that triggers auto web search (contains "latest")
    task = Task(
        id="TEST-WEB-001",
        level="L2",
        title="Test auto web search",
        instruction="Find the latest Python async features and write a summary",
        strategies=[
            {"name": "default", "description": "Write a summary of latest Python async features"}
        ],
    )
    
    q = TaskQueue()
    q.add_task(task)
    fw.set_task_queue(q)
    
    print("=" * 60)
    print("[TEST] Starting auto web search integration test")
    print("=" * 60)
    
    # Run the concurrent method
    report = await fw.run_async_concurrent(max_concurrent=1)
    
    print("=" * 60)
    print("[RESULT] Task executed with auto web search")
    print(f"  Total tasks: {report['total']}")
    print(f"  Completed: {report['completed']}")
    print(f"  Failed: {report['failed']}")
    print(f"  Quota used: {report['quota_used']}")
    
    # Verify task was auto-enhanced with web context
    print(f"\n[CHECK] Task instruction includes web context:")
    has_web_context = "[Web Context:]" in task.instruction
    print(f"  Web context auto-injected: {has_web_context}")
    
    # Verify task status
    print(f"\n[DONE] Framework state: {fw.state}")
    print(f"  Scheduler stats: {fw.scheduler.get_stats()}")
    
    await fw.executor.close_async()
    
    return has_web_context

result = asyncio.run(test_auto_search_e2e())
print(f"\n\\n[E2E] Auto web search test {'PASSED' if result else 'FAILED'}")
