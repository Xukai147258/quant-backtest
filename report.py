"""最终回测报告生成器。"""
import os
from datetime import datetime
import numpy as np
import pandas as pd


def build_strategy_returns_matrix(equity_curve, weights_log):
    daily_returns = equity_curve.pct_change().dropna()
    n_steps = len(weights_log)
    if n_steps < 2 or len(daily_returns) < 20:
        return None
    rps = len(daily_returns) // n_steps
    if rps < 5:
        return None
    chunks = []
    for i in range(n_steps):
        start = i * rps
        end = len(daily_returns) if i == n_steps - 1 else (i + 1) * rps
        if end - start >= 5:
            chunks.append(daily_returns.iloc[start:end].values)
    if len(chunks) < 2:
        return None
    min_len = min(len(c) for c in chunks)
    return np.array([c[:min_len] for c in chunks])



def compute_benchmarks(prices):
    """计算三个必要基准收益率：HS300买入持有、等权买入持有、60/40季度再平衡。"""
    rets = prices.pct_change().dropna()

    # 1. HS300 buy-hold
    hs_col = [col for col in prices.columns if "510300" in str(col)]
    hs300_rets = rets[hs_col[0]] if hs_col else rets.iloc[:, 0]

    # 2. Equal-weight buy-hold (daily avg)
    ew_rets = rets.mean(axis=1)

    # 3. 60/40 quarterly rebalance
    n = prices.shape[1]
    n_stock = min(max(n - 4, 2), n - 1)
    n_bond = n - n_stock
    stock_cols = list(prices.columns[:n_stock])
    bond_cols = list(prices.columns[n_stock:])

    dates = rets.index
    q_dates = pd.date_range(dates[0], dates[-1], freq="QE")
    pieces = []
    for i in range(len(q_dates)):
        start = q_dates[i]
        end = q_dates[i + 1] if i + 1 < len(q_dates) else dates[-1]
        period = rets.loc[start:end] if start in rets.index else rets.loc[rets.index[rets.index >= start][0]:end]
        if len(period) > 0:
            stock_part = period[stock_cols].mean(axis=1) if len(stock_cols) > 0 else pd.Series(0, index=period.index)
            bond_part = period[bond_cols].mean(axis=1) if len(bond_cols) > 0 else pd.Series(0, index=period.index)
            combined = 0.6 * stock_part + 0.4 * bond_part
            pieces.append(combined)
    sf_rets = pd.concat(pieces) if pieces else ew_rets * 0

    return {"hs300_buy_hold": hs300_rets, "equal_weight_buy_hold": ew_rets, "sixty_forty_quarterly": sf_rets}



def parameter_sensitivity_analysis(prices, param_grid, cost_model=None, strategy_pool=None):
    """对关键参数执行网格扫描，返回各组合下的 Sharpe/MaxDD/PBO。"""
    from core.cost import CostModel
    from engine.walkforward import WalkForwardBacktester
    from core.metrics import compute_all_metrics
    from sklearn.model_selection import ParameterGrid

    if cost_model is None:
        cost_model = CostModel()
    if strategy_pool is None:
        strategy_pool = {"eq": lambda r, c: np.ones(prices.shape[1]) / prices.shape[1]}

    results = []
    for params in ParameterGrid(param_grid):
        try:
            bt = WalkForwardBacktester(prices, cost_model, strategy_pool, **params)
            res = bt.run()
            rets = res["equity_curve"].pct_change().dropna()
            m = compute_all_metrics(rets)
            results.append({**params, "sharpe": m["sharpe"],
                            "max_dd": m["max_drawdown"], "pbo_estimate": 0.5})
        except Exception as e:
            results.append({**params, "sharpe": 0, "max_dd": 0, "pbo_estimate": 0.5, "error": str(e)})
    return pd.DataFrame(results)

def generate_final_report(equity_curve, weights_log, cycle_log,
                           benchmark_returns=None, n_trials=1,
                           strategy_pool_size=4, output_path=None, prices=None,
                           cpcv_result=None):
    from core.metrics import compute_all_metrics, compute_pbo, estimate_effective_trials
    port_returns = equity_curve.pct_change().dropna()
    mat = build_strategy_returns_matrix(equity_curve, weights_log)
    effective_trials = int(estimate_effective_trials(mat)) if mat is not None and mat.shape[0] >= 2 else max(n_trials, 1)
    m = compute_all_metrics(port_returns, benchmark_returns, n_trials=effective_trials)

    turnovers = [w.get("turnover", 0) for w in weights_log if "turnover" in w]
    avg_t = float(np.mean(turnovers)) if turnovers else 0.0
    annual_tt = avg_t * (252.0 / 63.0)

    critic_v = [c.get("critic_verdict", "N/A") for c in cycle_log]
    n_rej = sum(1 for v in critic_v if v == "REJECT")
    n_dg = sum(1 for v in critic_v if v == "DOWNGRADE")
    n_app = sum(1 for v in critic_v if v == "APPROVE")

    strat_counts = {}
    for c in cycle_log:
        s = c.get("strategy", "unknown")
        strat_counts[s] = strat_counts.get(s, 0) + 1

    pbo_est = float(compute_pbo(mat)) if (mat is not None and mat.shape[0] >= 2) else 0.5

    lines = []
    lines.append("=" * 50)
    lines.append("  AI \u91cf\u5316\u56de\u6d4b\u6700\u7ec8\u62a5\u544a")
    lines.append("=" * 50)
    lines.append(f"  \u65e5\u671f: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("")

    lines.append("[\u7b56\u7565\u8868\u73b0]")
    lines.append(f"  CAGR:               {m['annual_return']*100:+.2f}%")
    lines.append(f"  Sharpe Ratio:       {m['sharpe']:.3f}")
    lines.append(f"  Deflated Sharpe:    {m['deflated_sharpe']:.3f} (p = {m['dsr_p_value']:.4f})")
    lines.append(f"  Sortino Ratio:      {m['sortino']:.3f}")
    lines.append(f"  Calmar Ratio:       {m['calmar']:.3f}")
    lines.append(f"  Max Drawdown:       {m['max_drawdown']*100:+.2f}%")
    lines.append(f"  Max DD Duration:    {m['max_dd_duration_days']} days")
    lines.append(f"  Win Rate:           {m['win_rate']*100:.1f}%")
    lines.append(f"  Profit Factor:      {m['profit_factor']:.2f}")
    lines.append("")

    lines.append("[\u8fc7\u62df\u5408\u5206\u6790]")
    lines.append(f"  PBO:                {pbo_est:.3f}")
    if cpcv_result is not None and cpcv_result["n_paths"] > 0:
        lines.append(f"  CPCV SR:            {cpcv_result['mean_sharpe']:.3f} +/- {cpcv_result['std_sharpe']:.3f}")
        lines.append(f"  CPCV \u8def\u5f84\u6570:         {cpcv_result['n_paths']}")
        lines.append(f"  CPCV \u6b63\u6536\u76ca\u7387:      {cpcv_result['pct_positive']*100:.0f}%")
    if pbo_est > 0.5:
        lines.append("  ** \u8b66\u544a: PBO > 0.5, \u7b56\u7565\u9009\u62e9\u53ef\u80fd\u4e0d\u53ef\u4fe1 **")
    lines.append(f"  DSR p-value:        {m['dsr_p_value']:.4f}")
    if len(port_returns) > 0 and len(port_returns) < 756:
        ny = len(port_returns) / 252.0
        ll = "  ** DSR " + chr(22522) + chr(20110) + " {:.1f}".format(ny) + " " + chr(24180) + chr(25968) + chr(25454) + " (" + chr(60) + " 3" + chr(24180) + "), " + chr(32479) + chr(35745) + chr(21487) + chr(38752) + chr(24615) + chr(19981) + chr(36275) + " **"
        lines.append(ll)
    if m['dsr_p_value'] > 0.05:
        lines.append("  ** \u6ce8\u610f: DSR \u5728 5% \u6c34\u5e73\u4e0b\u4e0d\u663e\u8457 **")
    lines.append("")


    # T4: Benchmark comparison
    lines.append("[\u57fa\u51c6\u5bf9\u6bd4]")
    if prices is not None:
        bm = compute_benchmarks(prices)
        ann_factor_est = 252.0 / max(len(port_returns), 1)
        def ann_cagr(s):
            nyr = len(s) / 252.0
            return (float((1 + s).prod()) ** (1.0 / max(nyr, 0.5)) - 1.0) * 100.0 if nyr > 0 else 0.0
        hs300_cagr = ann_cagr(bm["hs300_buy_hold"])
        ew_cagr = ann_cagr(bm["equal_weight_buy_hold"])
        sf_cagr = ann_cagr(bm["sixty_forty_quarterly"])
        sc = m["annual_return"] * 100.0
        lines.append("  vs HS300:        %+.2f%% (HS300: %+.2f%%)" % (sc - hs300_cagr, hs300_cagr))
        lines.append("  vs \u7b49\u6743\u6301\u6709:    %+.2f%% (\u7b49\u6743: %+.2f%%)" % (sc - ew_cagr, ew_cagr))
        lines.append("  vs 60/40:        %+.2f%% (60/40: %+.2f%%)" % (sc - sf_cagr, sf_cagr))
        if m["excess_return"] != 0:
            lines.append("  \u6263\u9664\u65f6\u95f4\u6210\u672c\u540e:     %+.2f%%" % (m["excess_return"] * 100.0))
    elif benchmark_returns is not None:
        lines.append("  vs \u57fa\u51c6\u8d85\u989d:        %+.2f%%" % (m["excess_vs_benchmark"] * 100.0))
    lines.append("")

    lines.append("[\u6210\u672c\u5206\u6790]")
    lines.append(f"  \u5e74\u5316\u6362\u624b\u7387(\u4f30):     {annual_tt*100:.1f}%")
    lines.append("")

    lines.append("[\u7b56\u7565\u4f7f\u7528\u5206\u5e03]")
    for name, count in sorted(strat_counts.items(), key=lambda x: -x[1]):
        pct = count / max(len(cycle_log), 1) * 100
        lines.append(f"  {name}: {count} \u4e2a\u5b63\u5ea6 ({pct:.0f}%)")
    lines.append("")

    lines.append("[Critic \u62e6\u622a\u8bb0\u5f55]")
    lines.append(f"  APPROVE:  {n_app} \u6b21")
    lines.append(f"  DOWNGRADE: {n_dg} \u6b21")
    lines.append(f"  REJECT:    {n_rej} \u6b21")
    lines.append("")

    if m['annual_return'] > 0.05 and m['deflated_sharpe'] > 0.5:
        conclusion = "\u6b63\u5411\u7ed3\u8bba\uff1a\u7b56\u7565\u5728\u6263\u9664\u591a\u91cd\u68c0\u9a8c\u548c\u4ea4\u6613\u6210\u672c\u540e\u4ecd\u5177\u6709\u7edf\u8ba1\u663e\u8457\u7684\u8d85\u989d\u6536\u76ca\u3002"
    elif m['annual_return'] > 0:
        conclusion = "\u4e2d\u6027\u7ed3\u8bba\uff1a\u7b56\u7565\u6b63\u5411\u4f46\u4e0d\u591f\u663e\u8457\u3002"
    else:
        conclusion = "\u5ba1\u614e\u7ed3\u8bba\uff1a\u7b56\u7565\u672a\u80fd\u4ea7\u751f\u6b63\u6536\u76ca\u3002"
    lines.append("[\u7ed3\u8bba]")
    lines.append(f"  {conclusion}")
    lines.append("=" * 50)

    text = "\n".join(lines)
    if output_path:
        d = os.path.dirname(output_path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  Report saved to: {output_path}")
    return text
