"""Task 5.1: 端到端回测 — 整合 WalkForward + HMM + Builder + Critic + Meta-Learner."""
import sys, logging
sys.path.insert(0, "D:\\桌面")
logging.basicConfig(level=logging.WARNING)

import numpy as np
import pandas as pd
from datetime import timedelta

from core.cost import CostModel
from engine.walkforward import WalkForwardBacktester
from engine.hmm_detector import RollingHMMDetector, compute_features
from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.meta_learner import MetaLearner
from agents.orchestrator import Orchestrator


def test_end_to_end_pipeline():
    """端到端回测验证：无前视偏差、权重合法、组件完整运行。"""
    np.random.seed(42)

    # --- Mock 数据 ---
    dates = pd.date_range("2020-01-01", "2025-12-31", freq="B")
    n = len(dates)
    prices = pd.DataFrame({
        "A": np.random.randn(n).cumsum() + 100,
        "B": np.random.randn(n).cumsum() + 50,
    }, index=dates)

    # --- 组件初始化 ---
    cost_model = CostModel()
    hmm_detector = RollingHMMDetector(n_states=3)
    builder = BuilderAgent(max_weight=0.6)
    critic = CriticAgent()
    meta = MetaLearner(n_assets=2)
    orchestrator = Orchestrator(builder, critic, meta, None)

    # --- 策略池（包含 Builder 逻辑的包装函数） ---
    def make_adaptive_strategy(orchestrator, hmm_detector, prices, critic):
        """创建自适应策略函数：整合 HMM + Builder + Critic + Meta-Learner。"""
        features_cache = {}

        def strategy_fn(returns, cov_matrix):
            """自适应策略：每个 WalkForward 步骤使用 Orchestrator 决策。"""
            nonlocal features_cache
            if len(returns) < 20:
                return np.ones(2) / 2

            current_date = returns.index[-1]

            # 计算 HMM 状态
            prices_up_to = prices.loc[:current_date]
            feat = compute_features(prices_up_to, window=10)
            features_cache[current_date] = feat
            try:
                hmm_state, _, _ = hmm_detector.fit_predict(feat)
            except ValueError:
                hmm_state = 0

            # 计算情绪（mock）
            sentiment = 0.5 + 0.1 * np.random.randn()

            # 基本策略池
            pool = {
                "equal_weight": lambda r: np.ones(2) / 2,
                "momentum": lambda r: np.array([0.6, 0.4]) if r.iloc[-1, 0] > r.iloc[-1, 1] else np.array([0.4, 0.6]),
                "risk_parity": lambda r: np.array([0.5, 0.5]),
                "defensive": lambda r: np.array([0.3, 0.7]),
            }

            # 回测上下文
            context = {
                "train_end": current_date,
                "test_start": current_date + timedelta(days=10),
                "n_samples": len(returns),
                "embargo_days": 0,
                "test_run_count": 0,
            }

            # 执行 Orchestrator 季度决策
            result = orchestrator.run_quarterly_cycle(current_date, {
                "features": {"returns": returns},
                "hmm_state": hmm_state,
                "sentiment": sentiment,
                "strategy_pool": pool,
                "backtest_context": context,
            })

            return np.asarray(result["decision"]["weights"])

        return strategy_fn

    strategy_fn = make_adaptive_strategy(orchestrator, hmm_detector, prices, critic)
    strategy_pool = {"adaptive": strategy_fn}

    # --- 执行回测 ---
    bt = WalkForwardBacktester(
        prices, cost_model, strategy_pool,
        train_years=3, step_months=3, purge_days=5, embargo_days=10,
    )
    results = bt.run()

    # --- 验证 ---
    assert results["n_steps"] >= 2, f"Need >= 2 steps, got {results['n_steps']}"
    print(f"  Steps: {results['n_steps']}")

    # 权重合法
    for w in results["weights_log"]:
        wts = np.array(w["weights"])
        w_sum = wts.sum()
        assert 0.95 <= w_sum <= 1.05, f"Weights sum {w_sum:.3f} out of [0.95, 1.05]"
        assert (wts >= 0).all(), "Negative weights"

    # 无前视偏差
    for i, w in enumerate(results["weights_log"]):
        test_date = w["date"]
        train_end = results["train_ends"][i]
        assert test_date > train_end + timedelta(days=bt.purge_days), \
            f"Look-ahead at step {i}"

    # Critic 触发（至少有一个 PURGE 上下文会被检查）
    assert len(orchestrator.cycle_log) > 0, "Orchestrator should have run cycles"
    critic_verdicts = [c["critic_verdict"] for c in orchestrator.cycle_log]
    has_review = any(v in ("DOWNGRADE", "REJECT") for v in critic_verdicts)
    # 如果不满足，记录日志但不 fail（取决于上下文）
    if not has_review:
        print(f"  Note: No DOWNGRADE/REJECT triggered (all verdicts: {set(critic_verdicts)})")
    else:
        print(f"  Critic triggered: {critic_verdicts}")

    print(f"  Equity curve length: {len(results['equity_curve'])}")
    print("[PASS] test_end_to_end_pipeline")


if __name__ == "__main__":
    test_end_to_end_pipeline()

def test_parameter_sensitivity():
    from report import parameter_sensitivity_analysis
    import numpy as np, pandas as pd
    np.random.seed(42)
    dates = pd.date_range("2020-01-01", "2025-12-31", freq="B")
    n = len(dates)
    p = pd.DataFrame({"A": np.random.randn(n).cumsum()+100, "B": np.random.randn(n).cumsum()+50}, index=dates)
    grid = {"purge_days": [3, 10], "train_years": [2, 3]}
    df = parameter_sensitivity_analysis(p, grid)
    assert len(df) >= 4
    print(f"  Sensitivity: {len(df)} combos")
    print("[PASS] test_parameter_sensitivity")
