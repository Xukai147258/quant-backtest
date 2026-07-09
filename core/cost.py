# coding: utf-8
"""交易成本模型：佣金 + 滑点 + 冲击成本（Almgren-Chriss）。"""
import warnings
import numpy as np


class CostModel:
    """真实交易成本模型。

    Parameters
    ----------
    commission_rate : float
        佣金费率，默认万 2.5 (0.00025)
    min_commission : float
        最低佣金，默认 5 元
    slippage_bps : float
        固定滑点，单位 bp，默认 2bp
    stamp_duty : float
        印花税率（ETF 免，默认 0）
    impact_model : str
        冲击模型类型，默认 'sqrt'
    """

    def __init__(self, commission_rate=0.00025, min_commission=5.0,
                 slippage_bps=2.0, stamp_duty=0.0005, impact_model="sqrt"):
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.slippage_bps = slippage_bps
        self.stamp_duty = stamp_duty
        self.impact_model = impact_model

        if commission_rate <= 0:
            warnings.warn("commission_rate <= 0, are you sure you want zero-cost trading?")

    def round_trip_cost(self, trade_value, daily_volume=None):
        """一次买+卖的总成本（元）。

        Parameters
        ----------
        trade_value : float
            单边交易金额（元）
        daily_volume : float, optional
            当日成交额（元），传入时计算冲击成本

        Returns
        -------
        float : 买+卖的总成本（元）
        """
        commission = max(trade_value * self.commission_rate, self.min_commission)
        slippage = trade_value * self.slippage_bps / 10000.0
        stamp = trade_value * self.stamp_duty

        impact = 0.0
        if daily_volume is not None:
            impact = self._sqrt_impact(trade_value, daily_volume)

        # 买+卖: commission 双边, slippage 双边, stamp 单边, impact 单边
        # 注：冲击成本仅在交易执行时发生，round-trip 中假设只有一侧有显著冲击
        # （卖出一侧通常冲击更小或与买入共享流动性），如需双边冲击，调用方自行 ×2
        total = commission * 2 + slippage * 2 + stamp + impact
        return total

    def _sqrt_impact(self, trade_value, daily_volume):
        """Almgren-Chriss sqrt 模型简化版：10bp * sqrt(参与率)。"""
        if daily_volume is None or daily_volume <= 0:
            return 0.0
        participation_rate = trade_value / float(daily_volume)
        # 10bp = 0.001
        impact_bp = 0.001 * np.sqrt(max(participation_rate, 1e-10))
        return trade_value * impact_bp
