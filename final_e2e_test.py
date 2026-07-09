# -*- coding: utf-8 -*-
import asyncio, sys, os, logging
logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")

sys.path.insert(0, r"D:\桌面\quant_backtest")
os.environ["GLM_API_KEY"] = "sk-4Zpdt2J6aGZLxWSUH13imJPDGlJ0XpcZcLaJkx36JG9Gync6"
os.environ["GLM_API_BASE"] = "https://yuanyuaicloud.cn/v1"
os.environ["GLM_MODEL"] = "glm-5.2"

from automation.config import Config
from automation.core import AutomationFramework
from automation.task_queue import Task

async def test():
    config = Config()
    config.api_key = os.environ["GLM_API_KEY"]
    config.api_base = os.environ["GLM_API_BASE"]
    config.model = os.environ["GLM_MODEL"]
    fw = AutomationFramework(config)

    # Task with "latest" trigger word
    task = Task(
        id="E2E-001", level="L2",
        instruction="Explain the latest Python features",
        strategies=[{"name": "default", "description": "explain"}],
    )

    print("[TEST] Executing task with auto web search...")
    print("  should_auto_search:", fw._should_auto_search(task))

    result = await fw._execute_task_logic(task)
    print("[RESULT] success:", result.get("success"))
    print("[RESULT] score:", result.get("score"))
    print("[RESULT] action:", result.get("action"))

    # Key: task should complete even if web search fails
    if result.get("success"):
        print("[PASS] Task completed successfully (web search gracefully degraded)")
    else:
        print("[FAIL] Task failed despite web search degradation")

    await fw.executor.close_async()

asyncio.run(test())
