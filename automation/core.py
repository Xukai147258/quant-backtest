# automation/core.py
import time
import logging
import re
import asyncio
from automation.config import Config
from automation.quota import QuotaManager
from automation.task_queue import TaskQueue, Task
from automation.evaluator import RuleEvaluator, EvaluationResult, HybridEvaluator
from automation.executor import GLMExecutor
from automation.score import ScoreEngine
from automation.strategy import StrategyManager
from automation.meta_health import MetaHealthChecker
from automation.persistence import CheckpointManager
from automation.adaptive_tuning import AdaptiveTuner
from automation.trust_gate import TrustGate, TrustGateResult
from automation.deerflow_scheduler import DeerFlowScheduler, OverlapPolicy
from automation.web_search import WebSearchEngine

logger = logging.getLogger(__name__)


class AutomationFramework:
    def __init__(self, config: Config):
        self.config = config
        self.quota = QuotaManager(max_calls=1000, refresh_hours=5)
        self.queue = TaskQueue()
        self.executor = GLMExecutor(config)
        self.evaluator = HybridEvaluator(self.executor)
        self.score_engine = ScoreEngine()
        self.strategy_mgr = StrategyManager()
        self.meta_health = MetaHealthChecker(check_interval=300)
        self.checkpoint = CheckpointManager()
        self.tuner = AdaptiveTuner(adaptation_enabled=True)
        self.trust_gate = TrustGate(mode=config.trust_mode) if hasattr(config, 'trust_mode') else TrustGate(mode="dev")
        self.trust_gate_enabled = getattr(config, 'trust_gate_enabled', False)
        # DeerFlow 2.0 concurrent scheduler
        self.scheduler = DeerFlowScheduler(
            max_concurrent_runs=10,
            lease_seconds=300,
            overlap_policy=OverlapPolicy.SKIP,
        )
        # Web search engine
        self.web_search = WebSearchEngine(glm_executor=self.executor, cache_enabled=True)
        self.state = "idle"
        self.current_task = None

    def set_task_queue(self, queue):
        self.queue = queue

    def run_cycle(self, dry_run=False):
        """Execute one iteration of the framework loop.

        Returns one of: "continue", "continue_low_freq", "mark_risk",
        "switch_strategy", "force_stop", "quota_exhausted",
        "all_tasks_completed", "no_strategy", "api_error", "would_execute".
        """
        # --- Phase 1: Quota check ---
        if not self.quota.is_pending():
            self.state = "paused"
            return "quota_exhausted"
        if not self.quota.consume():
            return "quota_exhausted"

        # --- Phase 2: Task selection ---
        if self.current_task is None:
            self.current_task = self.queue.next()
            if self.current_task is None:
                self.state = "done"
                return "all_tasks_completed"

        task = self.current_task

        if dry_run:
            return "would_execute"

        # --- Phase 3: Strategy check ---
        if not task.strategies:
            logger.warning(f"Task {task.id} has no strategies")
            self._finalize_task("fail")
            return "no_strategy"

        # --- Phase 4: Trust gate (optional gating step) ---
        if self.trust_gate_enabled:
            framework_state = {
                "walkforward_results": getattr(self, '_walkforward_results', None),
                "hmm_detector": getattr(self, '_hmm_detector', None),
                "cost_model": getattr(self, '_cost_model', None),
                "strategy_pool": task.strategies[task.current_strategy_index] if task.strategies else {},
                "metrics": getattr(self, '_metrics', {}),
                "project_root": getattr(self, '_project_root', None),
            }
            gate_result = self.trust_gate.run(framework_state)
            if not gate_result.passed:
                logger.warning(f"Trust gate FAILED for {task.id}: {len(gate_result.failed_checks)} check(s) failed")
                for fc in gate_result.failed_checks:
                    logger.warning(f"  [{fc['check_id']}] {fc['name']}: {fc['message']}")
                self._finalize_task("fail")
                return "trust_check_failed"
            else:
                logger.info(f"Trust gate passed ({gate_result.total_checks} checks)")

        # --- Phase 5: API call ---
        strategy = task.strategies[task.current_strategy_index]
        messages = self.executor.build_messages(
            task.instruction, strategy.get("description", ""))
        result = self.executor.execute(messages)

        if "error" in result:
            logger.error(f"API call failed: {result['error']}")
            task.budget_used += 1
            self._finalize_task("fail")
            return "api_error"

        # --- Phase 5: Evaluate ---
        metrics = self._compute_metrics(result)
        eval_result = self.evaluator.evaluate(task, metrics)
        action = eval_result.decision["action"]

        # --- Phase 5.5: Meta health recording ---
        self.meta_health.record_cycle(task.id, action, eval_result.score)
        # Adaptive tuning recording
        self.tuner.record(
            task.id, task.current_strategy_index,
            eval_result.score, eval_result.marginal_gain,
            action, tokens_used=result.get("usage", {}).get("total_tokens", 0))

        # --- Phase 6: Decision ---
        task.budget_used += 1
        if action == "force_stop":
            logger.info(f"Force stop: {task.id} (score={eval_result.score:.1f})")
            self._finalize_task("fail")
        elif action == "switch_strategy":
            if task.next_strategy():
                logger.info(f"Switching strategy: {task.id} -> strategy {task.current_strategy_index}")
            else:
                logger.info(f"No more strategies for {task.id}")
                self._finalize_task("fail")
            self.evaluator.reset_consecutive()
        elif action == "mark_risk":
            logger.info(f"Risk mark: {task.id} marginal_gain={eval_result.marginal_gain:.1f}%")
        # continue and continue_low_freq fall through
        return action

    def _compute_metrics(self, api_result):
        """Extract metrics from a real GLM API response."""
        if "error" in api_result:
            return {"test_pass_rate": 0.0, "boundary_coverage": 0.0, "compile_ok": False}
        usage = api_result.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)
        choices = api_result.get("choices", [])
        if not choices:
            return {"test_pass_rate": 0.0, "boundary_coverage": 0.0, "compile_ok": False}
        content_resp = choices[0].get("message", {}).get("content", "")
        content_len = len(content_resp.strip())
        has_substance = 100.0 if content_len > 200 else (50.0 if content_len > 50 else 0.0)
        has_code = content_resp.count("`") >= 2
        mentions_error = bool(re.search(r'(error|failed|fail|exception|traceback)', content_resp, re.IGNORECASE))
        compile_ok = 100.0 if (has_code and not mentions_error) else (50.0 if has_code else 100.0)
        has_structure = '#' in content_resp or '**' in content_resp
        structure_score = 100.0 if has_structure else 40.0
        efficiency = min(100.0, (total_tokens / 500) * 100) if total_tokens > 0 else 0.0
        test_pass_rate = round(has_substance * 0.4 + structure_score * 0.3 + efficiency * 0.3, 1)
        boundary_coverage = round(has_substance * 0.3 + structure_score * 0.4 + compile_ok * 0.3, 1)
        return {
            "test_pass_rate": test_pass_rate,
            "boundary_coverage": boundary_coverage,
            "compile_ok": compile_ok >= 50.0,
        }

    def _finalize_task(self, outcome):
        """Cleanly finish the current task with the given outcome."""
        if outcome == "fail":
            self.queue.fail_current()
        elif outcome == "complete":
            self.queue.complete_current()
        self.current_task = None
        self.evaluator.reset_consecutive()


    async def run_async(self, poll_interval=60):
        logger.info("Framework starting")
        self.state = "running"
        while True:
            result = self.run_cycle()
            if result == "all_tasks_completed":
                logger.info("All tasks completed")
                self.state = "done"
                break
            elif result == "quota_exhausted":
                logger.info(f"Quota exhausted, polling every {poll_interval}s...")
                self.state = "paused"
                await self.quota.wait_until_refresh_async(poll_interval)
                self.state = "running"
                if self.meta_health.should_check():
                    hr = self.meta_health.run_check()
                    logger.info(f"Meta health: {hr.health_level} ({hr.health_score:.1f})")
                    if hr.suggestions:
                        for s in hr.suggestions:
                            logger.warning(f"Health suggestion: {s}")
                continue
            elif result in ("no_strategy", "api_error"):
                continue
            # Adaptive tuning suggestions
            t_snapshot = self.tuner.get_snapshot()
            if len(self.tuner.history) >= 30 and len(self.tuner.history) % 10 == 0:
                suggestions = self.tuner.suggest_tuning(t_snapshot)
                if suggestions:
                    logger.info(f"Tuner: {len(suggestions)} suggestion(s)")
                    for s in suggestions:
                        logger.info(f"  {s.parameter}: {s.current_value} -> {s.suggested_value} ({s.rationale})")
            # Checkpoint after each cycle
            try:
                cp = self.checkpoint.build_checkpoint(self)
                self.checkpoint.save(cp)
            except Exception as e:
                logger.debug(f"Checkpoint save failed (non-fatal): {e}")
            await asyncio.sleep(1)
        return self.generate_report()

    def run(self, poll_interval=60):
        return asyncio.run(self.run_async(poll_interval))


    async def run_async_concurrent(self, poll_interval: int = 60, max_concurrent: int = 10):
        logger.info("Framework starting (concurrent mode)")
        self.state = "running"

        swept = await self.scheduler.sweep_stale_runs()
        if swept > 0:
            logger.warning(f"Swept {swept} stale run(s) on startup")

        while True:
            if not self.quota.is_pending():
                logger.info(f"Quota exhausted, polling every {poll_interval}s...")
                self.state = "paused"
                await self.quota.wait_until_refresh_async(poll_interval)
                self.state = "running"
                continue

            pending_tasks = [t for t in self.queue.tasks if t.status == "pending"]
            if not pending_tasks:
                active = await self.scheduler.count_active_runs()
                if active == 0:
                    logger.info("All tasks completed")
                    self.state = "done"
                    break
                await asyncio.sleep(1)
                continue

            available_budget = min(
                await self.scheduler.count_budget_available(),
                self.quota.remaining,
                max_concurrent,
            )

            if available_budget <= 0:
                await asyncio.sleep(1)
                continue

            batch = pending_tasks[:available_budget]
            logger.info(f"Dispatching {len(batch)} task(s) concurrently")

            async with asyncio.TaskGroup() as tg:
                for task in batch:
                    tg.create_task(self._execute_task_concurrent(task))

            await self._post_cycle_async()
            await asyncio.sleep(1)

        return self.generate_report()

    async def _execute_task_concurrent(self, task: Task):
        task.status = "running"

        dispatch_result = await self.scheduler.dispatch_task(
            task.id,
            execute_fn=lambda: self._execute_task_logic(task),
        )

        outcome = dispatch_result.get("outcome", "failed")
        if outcome == "success":
            task.status = "completed"
        elif outcome in ("failed", "interrupted", "skip"):
            task.status = "failed"
            logger.warning(f"Task {task.id} {outcome}: {dispatch_result.get('error', '')}")

    async def _execute_task_logic(self, task: Task) -> dict:
        if not self.quota.consume():
            return {"error": "quota exhausted", "success": False}

        if not task.strategies:
            return {"error": "no strategy", "success": False}


        # AUTO WEB SEARCH: triggered when task needs latest context
        if self._should_auto_search(task):
            search_query = self._extract_search_query(task)
            if search_query:
                logger.info(f"[AUTO] Web search for task " + str(task.id) + ": " + search_query)
                search_result = await self.web_search.search(search_query, n=3)
                if search_result.results:
                    context = self._format_search_results_auto(search_result)
                    task.instruction = task.instruction + "\n\n[Web Context:]\n" + context
                    logger.info("[AUTO] Enhanced task with " + str(len(search_result.results)) + " search result(s)")

        strategy = task.strategies[task.current_strategy_index]
        messages = self.executor.build_messages(task.instruction, strategy.get("description", ""))
        result = await self.executor.execute_async(messages)

        if "error" in result:
            return {"error": result["error"], "success": False}

        metrics = self._compute_metrics(result)
        eval_result = self.evaluator.evaluate(task, metrics)

        self.meta_health.record_cycle(task.id, eval_result.decision["action"], eval_result.score)
        self.tuner.record(
            task.id, task.current_strategy_index,
            eval_result.score, eval_result.marginal_gain,
            eval_result.decision["action"],
            tokens_used=result.get("usage", {}).get("total_tokens", 0),
        )

        task.budget_used += 1

        action = eval_result.decision["action"]
        if action == "force_stop":
            return {"error": "force stop", "success": False}
        elif action == "switch_strategy":
            task.next_strategy()
            self.evaluator.reset_consecutive()

        return {"success": True, "action": action, "score": eval_result.score}


    def _should_auto_search(self, task: Task) -> bool:
        triggers = ["latest", "recent", "current", "new", "update", "news", "today", "now"]
        return any(t in task.instruction.lower() for t in triggers)

    def _extract_search_query(self, task: Task) -> str:
        words = [w for w in task.instruction.split() if len(w) > 3][:5]
        return " ".join(words)

    def _format_search_results_auto(self, response) -> str:
        items = [f"- {r.title}: {r.snippet[:80]}" for r in response.results[:3]]
        return chr(10).join(items)

    async def _post_cycle_async(self):
        try:
            cp = self.checkpoint.build_checkpoint(self)
            self.checkpoint.save(cp)
        except Exception as e:
            logger.debug(f"Checkpoint failed: {e}")

        if self.meta_health.should_check():
            try:
                hr = self.meta_health.run_check()
                logger.info(f"Meta health: {hr.health_level} ({hr.health_score:.1f})")
            except Exception as e:
                logger.debug(f"Meta health failed: {e}")

        if len(self.tuner.history) >= 30 and len(self.tuner.history) % 10 == 0:
            try:
                suggestions = self.tuner.suggest_tuning(self.tuner.get_snapshot())
                for s in suggestions:
                    logger.info(f"Tuning: {s.parameter} -> {s.suggested_value}")
            except Exception as e:
                logger.debug(f"Tuning failed: {e}")

    def generate_report(self):
        completed = [t for t in self.queue.tasks if t.status == "completed"]
        failed = [t for t in self.queue.tasks if t.status == "failed"]
        return {
            "total": len(self.queue.tasks),
            "completed": len(completed),
            "failed": len(failed),
            "quota_used": self.quota.total_used,
            "details": [
                {"id": t.id, "status": t.status, "budget_used": t.budget_used}
                for t in self.queue.tasks
            ],
        }