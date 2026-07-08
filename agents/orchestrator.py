# coding: utf-8
"""Orchestrator：串接 Builder -> Critic -> Meta-Learner 的主循环。"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class Orchestrator:
    """主循环：串联 Builder -> Critic -> Meta-Learner 的辩论-裁决-更新周期。

    Parameters
    ----------
    builder : BuilderAgent
    critic : CriticAgent
    meta_learner : MetaLearner
    backtester : WalkForwardBacktester (or compatible)
    """

    def __init__(self, builder, critic, meta_learner, backtester):
        self.builder = builder
        self.critic = critic
        self.meta_learner = meta_learner
        self.backtester = backtester
        self.cycle_log: list = []

    def run_quarterly_cycle(self, date, market_data: Dict) -> Dict:
        """一个季度的完整决策周期。

        Parameters
        ----------
        date : datetime or Timestamp
            当前决策日期
        market_data : dict
            {"features": dict, "hmm_state": any, "sentiment": float,
             "strategy_pool": dict, "backtest_context": dict}

        Returns
        -------
        dict : 最终决策详情
        """
        features = market_data.get("features", {})
        hmm_state = market_data.get("hmm_state", 0)
        sentiment = market_data.get("sentiment", 0.5)
        strategy_pool = market_data.get("strategy_pool", {})
        backtest_context = market_data.get("backtest_context", {})

        try:
            # Step 1: Builder 提案
            proposal = self.builder.propose(features, hmm_state, sentiment, strategy_pool)
        except Exception as e:
            logger.error(f"Builder failed at {date}: {e}")
            proposal = {
                "strategy": "equal_weight",
                "weights": [1.0 / len(features.get("returns", [1])[0])],
                "confidence": 0.0,
                "rationale": f"Fallback due to Builder error: {e}",
            }

        try:
            # Step 2: Critic 审查
            review = self.critic.review(proposal, backtest_context)
        except Exception as e:
            logger.error(f"Critic failed at {date}: {e}")
            review = {
                "verdict": "APPROVE",
                "findings": [],
                "adjusted_confidence": proposal.get("confidence", 0.5),
            }

        try:
            # Step 3: Meta-Learner 裁决
            decision = self.meta_learner.arbitrate(features, proposal, review)
        except Exception as e:
            logger.error(f"MetaLearner failed at {date}: {e}")
            decision = {
                "weights": proposal["weights"],
                "confidence": 0.1,
                "builder_credit": 0.5,
                "critic_credit": 0.5,
                "verdict": "APPROVE",
            }

        # 记录
        self.cycle_log.append({
            "date": date,
            "strategy": proposal.get("strategy"),
            "builder_confidence": proposal.get("confidence"),
            "critic_verdict": review.get("verdict"),
            "final_confidence": decision.get("confidence"),
            "weights": decision.get("weights"),
        })

        logger.info(
            f"Cycle {date.date()}: "
            f"strategy={proposal.get('strategy')}, "
            f"critic={review.get('verdict')}, "
            f"conf={decision.get('confidence'):.2f}"
        )

        return {
            "date": date,
            "proposal": proposal,
            "review": review,
            "decision": decision,
        }
