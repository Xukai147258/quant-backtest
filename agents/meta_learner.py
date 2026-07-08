# coding: utf-8
"""Meta-Learner：在线学习 Builder/Critic 信誉分，加权裁决。"""
import numpy as np
from typing import Dict, List, Any

class MetaLearner:
    def __init__(self, lookback_quarters=8, n_assets=9):
        self.lookback_quarters = lookback_quarters
        self.n_assets = n_assets
        self.history = []
        self.builder_credit = 0.5
        self.critic_credit = 0.5

    def arbitrate(self, features, builder_proposal, critic_review):
        builder_weights = np.asarray(builder_proposal["weights"])
        confidence = builder_proposal.get("confidence", 0.5)
        critic_verdict = critic_review["verdict"]
        defense_weights = np.ones(self.n_assets) / self.n_assets
        if critic_verdict == "REJECT":
            final_weights = defense_weights.copy()
            confidence = 0.1
        elif critic_verdict == "DOWNGRADE":
            final_weights = 0.7 * builder_weights + 0.3 * defense_weights
            final_weights = final_weights / final_weights.sum()
            confidence = builder_proposal.get("confidence", 0.5) * 0.6
        else:
            final_weights = builder_weights.copy()
            confidence = builder_proposal.get("confidence", 0.5) * (0.5 + 0.5 * self.builder_credit)
        return {"weights": final_weights, "confidence": confidence,
                "builder_credit": self.builder_credit, "critic_credit": self.critic_credit,
                "verdict": critic_verdict}

    def update(self, features, final_weights, actual_outcome):
        self.history.append({"features": features, "weights": final_weights.copy(),
            "outcome": actual_outcome, "builder_credit_before": self.builder_credit,
            "critic_credit_before": self.critic_credit})
        if actual_outcome > 0:
            self.builder_credit = min(1.0, self.builder_credit + 0.01)
            self.critic_credit = max(0.0, self.critic_credit - 0.01)
        else:
            self.builder_credit = max(0.0, self.builder_credit - 0.01)
            self.critic_credit = min(1.0, self.critic_credit + 0.01)
        if len(self.history) > self.lookback_quarters:
            self.history = self.history[-self.lookback_quarters:]

class EGMetaLearner:
    def __init__(self, n_strategies, n_assets=9, learning_rate=0.05):
        self.n_strategies = n_strategies
        self.n_assets = n_assets
        self.eta = learning_rate
        self.strategy_weights = np.ones(n_strategies) / n_strategies
        self.history = []
    def get_strategy_weights(self):
        return self.strategy_weights / max(self.strategy_weights.sum(), 1e-10)
    def update(self, strategy_returns):
        self.strategy_weights = self.strategy_weights * np.exp(self.eta * np.asarray(strategy_returns))
        total = self.strategy_weights.sum()
        if total > 0: self.strategy_weights /= total
        else: self.strategy_weights = np.ones(self.n_strategies) / self.n_strategies
        self.history.append(self.get_strategy_weights().copy())
    def get_portfolio_weights(self, strategy_weights_dict):
        sw = self.get_strategy_weights()
        names = list(strategy_weights_dict.keys())
        combined = np.zeros(self.n_assets)
        for i, name in enumerate(names):
            if i < len(sw): combined += sw[i] * np.asarray(strategy_weights_dict[name])
        combined = np.clip(combined, 0, None)
        if combined.sum() > 0: combined /= combined.sum()
        else: combined = np.ones(self.n_assets) / self.n_assets
        return combined
