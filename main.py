#!/usr/bin/env python
"""backtest system"""
import sys, os, logging, argparse
sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

import numpy as np, pandas as pd
from datetime import timedelta
from core.data import fetch_etf_data
from core.cost import CostModel
from engine.walkforward import WalkForwardBacktester
from engine.hmm_detector import RollingHMMDetector, compute_features, select_optimal_n_states
from agents.builder import BuilderAgent
from agents.critic import CriticAgent
from agents.meta_learner import MetaLearner
from agents.orchestrator import Orchestrator
from report import generate_final_report

def _defensive_weights(rets):
    n = rets.shape[1]; w = np.ones(n) / n
    w[-min(3,n):] *= 2; return w / w.sum()

def compute_trend_sentiment(prices_up_to, sw=50, lw=200):
    if len(prices_up_to) < lw: return 0.5
    pt = prices_up_to.mean(axis=1)
    sig = (pt.rolling(sw).mean() > pt.rolling(lw).mean()).astype(float)
    sent = sig.rolling(60).mean().iloc[-1] if len(sig) >= 60 else sig.mean()
    return float(np.clip(sent, 0.0, 1.0))

def run_backtest(prices, cost_model=None):
    if cost_model is None: cost_model = CostModel()
    hmm = RollingHMMDetector(n_states=4)
    builder = BuilderAgent(max_weight=0.4)
    critic = CriticAgent()
    meta = MetaLearner(n_assets=prices.shape[1])
    orch = Orchestrator(builder, critic, meta, None)
    def sf(returns, cov_matrix):
        if len(returns) < 30: return np.ones(prices.shape[1]) / prices.shape[1]
        cd = returns.index[-1]
        feat = compute_features(prices.loc[:cd], window=20)
        try:
            if len(feat) >= 60:
                on = select_optimal_n_states(feat, max_states=6, min_states=2)
                hmm = RollingHMMDetector(n_states=on)
            hs, _, _ = hmm.fit_predict(feat)
        except ValueError: hs = 0
        sent = compute_trend_sentiment(prices.loc[:cd])
        pool = {"eq": lambda r: np.ones(prices.shape[1]) / prices.shape[1],
                "mom": lambda r: np.abs(r.iloc[-1].values)/max(np.abs(r.iloc[-1]).sum(),1e-10),
                "rp": lambda r: (1/np.maximum(r.std(),1e-10).values)/(1/np.maximum(r.std(),1e-10)).sum(),
                "def": lambda r: _defensive_weights(r)}
        ctx = {
            "train_end": cd,
            "test_start": cd+timedelta(days=10),
            "n_samples": len(returns),
            "embargo_days": 10,
            "test_run_count": 1,
            "commission_rate": 0.00025,
            "min_commission": 5.0,
            "slippage_bps": 2.0,
            "impact_model": "sqrt",
            "annual_turnover": 0.8,
            "rolling_expanding": True,
            "hmm_global_scaling": False,
            "hmm_bic_recorded": True,
            "strategy_pool_injectable": True,
            "survivorship_noted": True,
        }
        r = orch.run_quarterly_cycle(cd, {"features": {"returns": returns},
            "hmm_state": hs, "sentiment": sent, "strategy_pool": pool, "backtest_context": ctx})
        return np.asarray(r["decision"]["weights"])
    bt = WalkForwardBacktester(prices, cost_model, {"adaptive": sf},
        train_years=3, step_months=1, purge_days=5, embargo_days=10)
    res = bt.run()
    return res, orch, cost_model

def main(realtime=False):
    if realtime: prices = fetch_etf_data(days=365*5)
    else:
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", "2025-12-31", freq="B")
        prices = pd.DataFrame({"A": np.random.randn(len(dates)).cumsum()+100,
            "B": np.random.randn(len(dates)).cumsum()+50}, index=dates) + 100
    results, orch, cm = run_backtest(prices)
    sr_arr = results["equity_curve"].pct_change().dropna()
    if len(sr_arr) > 0 and len(orch.cycle_log) > 0:
        n_all = len(sr_arr); nc = len(orch.cycle_log)
        for i, e in enumerate(orch.cycle_log):
            si = int(i*n_all/nc); ei = int((i+1)*n_all/nc) if i < nc-1 else n_all
            out = float(sr_arr.iloc[si:ei].mean()) if ei > si else 0.0
            orch.meta_learner.update({}, np.asarray(e.get("weights",[])), out)
    from report import build_strategy_returns_matrix
    from core.metrics import estimate_effective_trials
    sm = build_strategy_returns_matrix(results["equity_curve"], results["weights_log"])
    et = max(estimate_effective_trials(sm), 1) if (sm is not None and sm.shape[0]>=2) else 4
    from engine.cpcv import compute_cpcv_sharpe_distribution
    try:
        cpcv_r = compute_cpcv_sharpe_distribution(prices, cm,
            lambda r,c: np.ones(prices.shape[1])/prices.shape[1], n_groups=6, n_test=2)
    except: cpcv_r = None
    from report import parameter_sensitivity_analysis
    try:
        sdf = parameter_sensitivity_analysis(prices, {"purge_days":[3,5,10],"step_months":[1,3]}, cm)
        srange = float(sdf["sharpe"].max()-sdf["sharpe"].min())
        if srange > 0.5: logger.warning("HIGH parameter sensitivity")
        else: logger.info("LOW parameter sensitivity")
    except: pass
    report_text = generate_final_report(
        results["equity_curve"], results["weights_log"], orch.cycle_log,
        n_trials=et, strategy_pool_size=4, cpcv_result=cpcv_r)
    print(report_text)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--realtime", action="store_true")
    args = parser.parse_args()
    main(realtime=args.realtime)
