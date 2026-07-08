# coding: utf-8
"""Builder Agent：根据市场状态提案策略权重。"""
import numpy as np
from typing import Dict, Any


class BuilderAgent:
    """策略提案 Agent：输入市场快照，输出权重提案。

    支持策略：
    - equal_weight: 等权
    - momentum: 动量加权
    - risk_parity: 风险平价（逆波动率）
    - defensive: 防御型（偏向债券）

    Parameters
    ----------
    max_weight : float
        单标的最大权重，默认 0.4
    """

    def __init__(self, max_weight: float = 0.4):
        self.max_weight = max_weight

    def propose(self, market_features: Dict, hmm_state: Any,
                sentiment: float, strategy_pool: Dict) -> Dict:
        """根据市场状态从策略池中选择策略并提案。

        Parameters
        ----------
        market_features : dict
            市场特征，至少包含 "returns" -> pd.DataFrame
        hmm_state : int or str
            HMM 检测到的市场状态 ID
        sentiment : float
            情绪指数 0~1
        strategy_pool : dict
            {name: callable(rets) -> weights}

        Returns
        -------
        dict : {"strategy", "weights", "confidence", "rationale"}
        """
        rets = market_features.get("returns")
        n_assets = rets.shape[1] if rets is not None else 0

        # 基于 HMM 状态和情绪选择策略
        if isinstance(hmm_state, int):
            is_bear = hmm_state == 0  # T5: state 0 = 最低收益率 = 空头
        else:
            is_bear = str(hmm_state).upper() in ("BEAR", "0", "HIGH_VOL")  # T5: state 0 = bear

        if is_bear or sentiment < 0.3:
            strategy_name = "defensive"
            confidence = 0.6
            rationale = f"Bearish regime (state={hmm_state}) or low sentiment ({sentiment:.2f})"
        elif sentiment > 0.6:
            strategy_name = "momentum"
            confidence = 0.8
            rationale = f"Bullish regime + high sentiment ({sentiment:.2f})"
        else:
            strategy_name = "risk_parity"
            confidence = 0.7
            rationale = f"Neutral regime, using risk parity (sentiment={sentiment:.2f})"

        # 从池中选取策略
        if strategy_name in strategy_pool:
            weights = np.asarray(strategy_pool[strategy_name](rets), dtype=float)
        else:
            # fallback: 第一个可用策略
            weights = np.asarray(list(strategy_pool.values())[0](rets), dtype=float)
            strategy_name = list(strategy_pool.keys())[0]

        # 约束：不做空，不超过 max_weight
        weights = np.clip(weights, 0.0, self.max_weight)
        if weights.sum() > 0:
            weights = weights / weights.sum()
        else:
            weights = np.ones(n_assets) / max(n_assets, 1)

        return {
            "strategy": strategy_name,
            "weights": weights,
            "confidence": confidence,
            "rationale": rationale,
        }
