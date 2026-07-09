"""DeerFlow 2.0 并发调度模式 — lease-based 抢注 + budget cap + overlap policy.

核心设计模式从 bytedance/deer-flow 提取:
1. Lease-based 任务抢注 — 多实例不冲突
2. Budget cap — max_concurrent_runs 控制并发上限
3. Overlap policy — skip/queue/parallel 处理碰撞
4. Run completion hook — 异步回调闭环
5. Stale sweep — 启动时清理死任务
"""
import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class OverlapPolicy(Enum):
    SKIP = "skip"
    QUEUE = "queue"
    PARALLEL = "parallel"


@dataclass
class LeaseClaim:
    """任务租约 — 抢注成功后持有"""
    task_id: str
    lease_owner: str
    lease_seconds: int
    claimed_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 60)
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at
    
    def extend(self, extra_seconds: int = 30):
        self.expires_at = time.time() + extra_seconds


@dataclass
class RunRecord:
    """运行记录 — 追踪任务执行状态"""
    run_id: str
    task_id: str
    thread_id: str
    status: Literal["queued", "running", "success", "failed", "interrupted", "skipped"]
    error: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    metadata: dict = field(default_factory=dict)


class DeerFlowScheduler:
    """DeerFlow 2.0 风格的并发调度器。
    
    核心能力:
    - Lease-based 任务抢注（避免多实例冲突）
    - Budget cap（max_concurrent_runs 控制并发）
    - Overlap policy（skip/queue/parallel）
    - Run completion hook（异步回调）
    - Stale sweep（清理死任务）
    """
    
    def __init__(
        self,
        max_concurrent_runs: int = 10,
        lease_seconds: int = 300,
        overlap_policy: OverlapPolicy = OverlapPolicy.SKIP,
        poll_interval: int = 5,
    ):
        self.max_concurrent_runs = max_concurrent_runs
        self.lease_seconds = lease_seconds
        self.overlap_policy = overlap_policy
        self.poll_interval = poll_interval
        self._lease_owner = f"{uuid.uuid4().hex}"
        
        # 内部状态
        self._active_runs: dict[str, RunRecord] = {}
        self._leases: dict[str, LeaseClaim] = {}
        self._lock = asyncio.Lock()
        self._stop_event = asyncio.Event()
        self._scheduler_task: Optional[asyncio.Task] = None
    
    async def claim_task(self, task_id: str) -> Optional[LeaseClaim]:
        """抢注任务 — lease-based 竞争"""
        async with self._lock:
            # 检查是否已有租约
            existing = self._leases.get(task_id)
            if existing and not existing.is_expired():
                if existing.lease_owner == self._lease_owner:
                    # 自己的租约，延长
                    existing.extend(self.lease_seconds)
                    return existing
                else:
                    # 别人的租约还在，无法抢注
                    return None
            
            # 检查 overlap policy
            if self.overlap_policy == OverlapPolicy.SKIP:
                if task_id in self._active_runs:
                    logger.info(f"Task {task_id} already active (skip policy)")
                    return None
            
            # 抢注成功
            lease = LeaseClaim(
                task_id=task_id,
                lease_owner=self._lease_owner,
                lease_seconds=self.lease_seconds,
                expires_at=time.time() + self.lease_seconds,
            )
            self._leases[task_id] = lease
            logger.debug(f"Claimed task {task_id} (lease expires in {self.lease_seconds}s)")
            return lease
    
    async def release_lease(self, task_id: str):
        """释放租约"""
        async with self._lock:
            if task_id in self._leases:
                lease = self._leases.pop(task_id)
                if lease.lease_owner == self._lease_owner:
                    logger.debug(f"Released lease for {task_id}")
    
    async def start_run(self, task_id: str, thread_id: str = None) -> RunRecord:
        """启动运行记录"""
        thread_id = thread_id or f"thread-{uuid.uuid4().hex}"
        run_id = f"run-{uuid.uuid4().hex}"
        
        async with self._lock:
            record = RunRecord(
                run_id=run_id,
                task_id=task_id,
                thread_id=thread_id,
                status="queued",
                started_at=time.time(),
            )
            self._active_runs[run_id] = record
            logger.info(f"Started run {run_id} for task {task_id}")
            return record
    
    async def update_run_status(
        self,
        run_id: str,
        status: Literal["running", "success", "failed", "interrupted", "skipped"],
        error: Optional[str] = None,
    ):
        """更新运行状态"""
        async with self._lock:
            if run_id in self._active_runs:
                record = self._active_runs[run_id]
                record.status = status
                record.error = error
                if status in ("success", "failed", "interrupted", "skipped"):
                    record.finished_at = time.time()
                    # 释放租约
                    await self.release_lease(record.task_id)
                    logger.info(f"Run {run_id} finished with status={status}")
    
    async def count_active_runs(self) -> int:
        """统计活跃运行数"""
        async with self._lock:
            return sum(
                1 for r in self._active_runs.values()
                if r.status in ("queued", "running")
            )
    
    async def has_budget(self) -> bool:
        """检查是否还有并发预算"""
        active = await self.count_active_runs()
        return active < self.max_concurrent_runs
    
    async def sweep_stale_runs(self, max_age_seconds: int = 600) -> int:
        """清理超时的死运行"""
        async with self._lock:
            now = time.time()
            stale_ids = []
            for run_id, record in self._active_runs.items():
                if record.status in ("queued", "running"):
                    age = now - (record.started_at or now)
                    if age > max_age_seconds:
                        stale_ids.append(run_id)
            
            for run_id in stale_ids:
                record = self._active_runs[run_id]
                record.status = "interrupted"
                record.error = "run timed out (stale sweep)"
                record.finished_at = now
                await self.release_lease(record.task_id)
            
            if stale_ids:
                logger.warning(f"Swept {len(stale_ids)} stale run(s)")
            return len(stale_ids)
    
    async def dispatch_task(
        self,
        task_id: str,
        execute_fn,
        thread_id: str = None,
    ) -> dict:
        """调度执行单个任务"""
        # 1. 检查预算
        if not await self.has_budget():
            return {"outcome": "no_budget", "error": "max concurrent runs reached"}
        
        # 2. 抢注任务
        lease = await self.claim_task(task_id)
        if not lease:
            return {"outcome": "skip", "error": "task already claimed or active"}
        
        # 3. 创建运行记录
        record = await self.start_run(task_id, thread_id)
        
        try:
            # 4. 执行
            await self.update_run_status(record.run_id, "running")
            result = await execute_fn()
            
            # 5. 完成
            if "error" in result:
                await self.update_run_status(record.run_id, "failed", result.get("error"))
                return {"outcome": "failed", "run_id": record.run_id, "error": result.get("error")}
            else:
                await self.update_run_status(record.run_id, "success")
                return {"outcome": "success", "run_id": record.run_id, "result": result}
        
        except asyncio.CancelledError:
            await self.update_run_status(record.run_id, "interrupted", "cancelled")
            return {"outcome": "interrupted", "run_id": record.run_id}
        
        except Exception as e:
            await self.update_run_status(record.run_id, "failed", str(e))
            return {"outcome": "failed", "run_id": record.run_id, "error": str(e)}
    
    async def run_concurrent_batch(
        self,
        tasks: list[str],
        execute_fn_factory,
        max_batch_size: int = None,
    ) -> list[dict]:
        """并发执行一批任务"""
        max_batch_size = max_batch_size or self.max_concurrent_runs
        batch_size = min(len(tasks), max_batch_size, await self.count_budget_available())
        
        if batch_size <= 0:
            return []
        
        async with asyncio.TaskGroup() as tg:
            dispatch_tasks = []
            for task_id in tasks[:batch_size]:
                execute_fn = execute_fn_factory(task_id)
                dispatch_tasks.append(
                    tg.create_task(self.dispatch_task(task_id, execute_fn))
                )
        
        return [t.result() for t in dispatch_tasks]
    
    async def count_budget_available(self) -> int:
        """计算剩余并发预算"""
        active = await self.count_active_runs()
        return max(0, self.max_concurrent_runs - active)
    
    def get_stats(self) -> dict:
        """获取调度器统计"""
        return {
            "max_concurrent_runs": self.max_concurrent_runs,
            "active_runs": len(self._active_runs),
            "leases": len(self._leases),
            "overlap_policy": self.overlap_policy.value,
            "lease_owner": self._lease_owner,
        }
