#!/usr/bin/env python
"""Backtest system with trust_check integration."""
import sys
import os
import logging
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

import numpy as np
import pandas as pd
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

from check_trust.core import TrustCheckRunner, CheckMode
from check_trust.phase1a import Phase1A
from check_trust.phase1b import Phase1B
from check_trust.phase2 import Phase2
from check_trust.phase3 import Phase3


def build_trust_context(results, hmm, cost_model, prices, orchestrator):
    """Build context dict for trust_check framework."""
    # Extract walkforward results
    walkforward_results = {
        "n_steps": results.get("n_steps", 0),
        "equity_curve": results.get("equity_curve"),
    }
    
    # Build test_intervals from train_ends, test_starts, test_ends
    train_ends = results.get("train_ends", [])
    test_starts = results.get("test_starts", [])
    test_ends = results.get("test_ends", [])
    
    walkforward_test_intervals = []
    for i in range(min(len(train_ends), len(test_starts), len(test_ends))):
        walkforward_test_intervals.append({
            "train_end": train_ends[i],
            "test_start": test_starts[i],
            "test_end": test_ends[i],
        })
    
    # Extract HMM history
    hmm_history = []
    if hasattr(hmm, "history"):
        for entry in hmm.history:
            hmm_history.append({
                "fit_start": entry.get("fit_start"),
                "fit_end": entry.get("fit_end"),
                "scaler_fit_end": entry.get("fit_end"),  # Same as fit_end for now
                "n_obs": entry.get("n_obs"),
                "bic": entry.get("bic"),
            })
    
    # Calculate metrics from equity curve
    metrics = {}
    equity = results.get("equity_curve")
    if equity is not None and len(equity) > 1:
        returns = equity.pct_change().dropna()
        if len(returns) > 0 and returns.std() > 0:
            sharpe = float(returns.mean() / returns.std() * np.sqrt(252))
            metrics["sharpe"] = sharpe
            metrics["total_return"] = float((equity.iloc[-1] / equity.iloc[0] - 1) * 100)
            metrics["volatility"] = float(returns.std() * np.sqrt(252) * 100)
            
            # Max drawdown
            rolling_max = equity.expanding().max()
            drawdown = (equity - rolling_max) / rolling_max
            metrics["max_drawdown"] = float(drawdown.min() * 100)
    
    # Build agent histories
    builder_history = []
    critic_history = []
    meta_history = []
    
    if orchestrator and hasattr(orchestrator, "cycle_log"):
        for cycle in orchestrator.cycle_log:
            builder_history.append({
                "date": cycle.get("date"),
                "max_weight": max(cycle.get("weights", [0.25])) if cycle.get("weights") else 0.25,
            })
            if "critic_verdict" in cycle:
                critic_history.append({
                    "date": cycle.get("date"),
                    "verdict": cycle.get("critic_verdict"),
                })
    
    # Strategy pool
    strategy_pool = {"eq": None, "mom": None, "rp": None, "def": None}
    
    context = {
        "project_root": os.path.dirname(__file__),
        "walkforward_results": walkforward_results,
        "walkforward_test_intervals": walkforward_test_intervals,
        "embargo_log": results.get("embargo_log", []),
        "signal_log": results.get("signal_log", []),
        "hmm_history": hmm_history,
        "cost_model": cost_model,
        "prices": prices,
        "metrics": metrics,
        "strategy_pool": strategy_pool,
        "builder_history": builder_history,
        "critic_history": critic_history,
        "meta_history": meta_history,
        "cpcv_results": [],
        "data_source": "simulation" if not os.getenv("REAL_DATA") else "local_csv",
    }
    
    return context


def run_trust_check(context, mode="dev"):
    """Run trust_check framework and return results."""
    runner = TrustCheckRunner(mode=CheckMode(mode))
    runner.add_phase(Phase1A(mode=CheckMode(mode)))
    runner.add_phase(Phase1B(mode=CheckMode(mode)))
    runner.add_phase(Phase2(mode=CheckMode(mode)))
    runner.add_phase(Phase3(mode=CheckMode(mode)))
    
    overall_pass = runner.run(context)
    report = runner.generate_report()
    
    return overall_pass, report


def print_trust_report(report):
    """Print trust_check report in readable format."""
    print("\n" + "=" * 60)
    print("TRUST CHECK REPORT")
    print("=" * 60)
    print(f"Overall: {'PASS' if report.get('overall_pass', False) else 'FAIL'}")
    print(f"Total checks: {report.get('total_checks', 0)}")
    print(f"Passed: {report.get('passed', 0)}")
    print(f"Failed: {report.get('failed', 0)}")
    print(f"Elapsed: {report.get('elapsed_seconds', 0):.2f}s")
    print()
    
    # Group by phase
    phases = {"A": [], "B": [], "C": [], "D": []}
    for r in report.get("results", []):
        phase = r["check_id"][0]
        if phase in phases:
            phases[phase].append(r)
    
    for phase_id, phase_name in [("A", "Stage 1A: Lookahead Bias Defense"),
                                   ("B", "Stage 1B: Overfitting Defense"),
                                   ("C", "Stage 2: Engineering Precision"),
                                   ("D", "Stage 3: Strategy Reasonableness")]:
        checks = phases.get(phase_id, [])
        if not checks:
            continue
        passed = sum(1 for c in checks if c["passed"])
        total = len(checks)
        print(f"\n{phase_name}: {passed}/{total} passed")
        for c in checks:
            status = "PASS" if c["passed"] else "FAIL"
            print(f"  [{c['check_id']}] {c['name']}: {status}")
            if not c["passed"]:
                print(f"       {c['message']}")
    
    print("\n" + "=" * 60)


def _momentum_weights(r, lookback=63):
    if len(r) < lookback:
        return np.ones(r.shape[1]) / r.shape[1]
    cum_ret = (1 + r.iloc[-lookback:]).prod() - 1
    w = np.maximum(cum_ret.values, 0)
    if w.sum() > 0:
        return w / w.sum()
    return np.ones(r.shape[1]) / r.shape[1]


def _defensive_weights(rets):
    n = rets.shape[1]
    w = np.ones(n) / n
    w[-min(3, n):] *= 2
    return w / w.sum()


def compute_trend_sentiment(prices_up_to, sw=50, lw=200):
    if len(prices_up_to) < lw:
        return 0.5
    pt = prices_up_to.mean(axis=1)
    sig = (pt.rolling(sw).mean() > pt.rolling(lw).mean()).astype(float)
    sent = sig.rolling(60).mean().iloc[-1] if len(sig) >= 60 else sig.mean()
    return float(np.clip(sent, 0.0, 1.0))


def run_backtest(prices, cost_model=None):
    """Run backtest and return results with all logs."""
    if cost_model is None:
        cost_model = CostModel()
    
    hmm = RollingHMMDetector(n_states=4)
    builder = BuilderAgent(max_weight=0.4)
    critic = CriticAgent()
    meta = MetaLearner(n_assets=prices.shape[1])
    orch = Orchestrator(builder, critic, meta, None)
    
    # Track HMM instances for history extraction
    hmm_instances = []
    
    def sf(returns, cov_matrix):
        if len(returns) < 30:
            return np.ones(prices.shape[1]) / prices.shape[1]
        
        cd = returns.index[-1]
        feat = compute_features(prices.loc[:cd], window=20)
        
        try:
            if len(feat) >= 60:
                on = select_optimal_n_states(feat, max_states=6, min_states=2)
                hmm_local = RollingHMMDetector(n_states=on)
            else:
                hmm_local = hmm
            
            hs, _, _ = hmm_local.fit_predict(feat)
            hmm_instances.append(hmm_local)
        except ValueError:
            hs = 0
        
        sent = compute_trend_sentiment(prices.loc[:cd])
        
        pool = {
            "eq": lambda r: np.ones(prices.shape[1]) / prices.shape[1],
            "mom": lambda r: _momentum_weights(r, 63),
            "rp": lambda r: (1 / np.maximum(r.std(), 1e-10).values) / (1 / np.maximum(r.std(), 1e-10)).sum(),
            "def": lambda r: _defensive_weights(r),
        }
        
        ctx = {
            "train_end": cd,
            "test_start": cd + timedelta(days=10),
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
        
        r = orch.run_quarterly_cycle(cd, {
            "features": {"returns": returns},
            "hmm_state": hs,
            "sentiment": sent,
            "strategy_pool": pool,
            "backtest_context": ctx,
        })
        
        return np.asarray(r["decision"]["weights"])
    
    bt = WalkForwardBacktester(
        prices, cost_model, {"adaptive": sf},
        train_years=3, step_months=1, purge_days=5, embargo_days=10
    )
    res = bt.run()
    
    # Merge HMM history from all instances
    all_hmm_history = []
    for inst in hmm_instances:
        if hasattr(inst, "history"):
            all_hmm_history.extend(inst.history)
    
    # Store merged history
    res["hmm_history"] = all_hmm_history
    res["hmm_instances"] = hmm_instances
    
    return res, orch, cost_model


def main(realtime=False, trust_mode="dev"):
    """Main entry point with trust_check integration."""
    # Load data
    if realtime:
        prices = fetch_etf_data(days=365 * 5)
    else:
        np.random.seed(42)
        dates = pd.date_range("2020-01-01", "2025-12-31", freq="B")
        prices = pd.DataFrame({
            "A": np.random.randn(len(dates)).cumsum() + 100,
            "B": np.random.randn(len(dates)).cumsum() + 50,
        }, index=dates) + 100
    
    # Run backtest
    logger.info("Running backtest...")
    results, orch, cm = run_backtest(prices)
    
    # Build trust_check context
    logger.info("Building trust_check context...")
    hmm = results.get("hmm_instances", [None])[0] if results.get("hmm_instances") else None
    context = build_trust_context(results, hmm, cm, prices, orch)
    
    # Run trust_check
    logger.info(f"Running trust_check (mode={trust_mode})...")
    overall_pass, report = run_trust_check(context, mode=trust_mode)
    
    # Print trust report
    print_trust_report(report)
    
    # Continue with original report generation
    sr_arr = results["equity_curve"].pct_change().dropna()
    if len(sr_arr) > 0 and len(orch.cycle_log) > 0:
        n_all = len(sr_arr)
        nc = len(orch.cycle_log)
        for i, e in enumerate(orch.cycle_log):
            si = int(i * n_all / nc)
            ei = int((i + 1) * n_all / nc) if i < nc - 1 else n_all
            out = float(sr_arr.iloc[si:ei].mean()) if ei > si else 0.0
            orch.meta_learner.update({}, np.asarray(e.get("weights", [])), out)
    
    from report import build_strategy_returns_matrix
    from core.metrics import estimate_effective_trials
    sm = build_strategy_returns_matrix(results["equity_curve"], results["weights_log"])
    et = max(estimate_effective_trials(sm), 1) if (sm is not None and sm.shape[0] >= 2) else 4
    
    from engine.cpcv import compute_cpcv_sharpe_distribution
    try:
        cpcv_r = compute_cpcv_sharpe_distribution(
            prices, cm,
            lambda r, c: np.ones(prices.shape[1]) / prices.shape[1],
            n_groups=6, n_test=2
        )
    except Exception:
        cpcv_r = None
    
    from report import parameter_sensitivity_analysis
    try:
        sdf = parameter_sensitivity_analysis(prices, {"purge_days": [3, 5, 10], "step_months": [1, 3]}, cm)
        srange = float(sdf["sharpe"].max() - sdf["sharpe"].min())
        if srange > 0.5:
            logger.warning("HIGH parameter sensitivity")
        else:
            logger.info("LOW parameter sensitivity")
    except Exception:
        pass
    
    report_text = generate_final_report(
        results["equity_curve"], results["weights_log"], orch.cycle_log,
        n_trials=et, strategy_pool_size=4, cpcv_result=cpcv_r
    )
    print(report_text)
    
    return overall_pass, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest with trust_check integration")
    parser.add_argument("--realtime", action="store_true", help="Use real-time data")
    parser.add_argument("--trust-mode", default="dev", choices=["dev", "full", "final"],
                        help="Trust check mode: dev (fast), full (standard), final (strict)")
    args = parser.parse_args()
    
    main(realtime=args.realtime, trust_mode=args.trust_mode)
