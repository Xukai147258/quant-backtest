# coding: utf-8
"""Critic Agent：使用 checklist 检查 Builder 提案。"""
import os
import re
from typing import Dict, List, Any
from datetime import datetime, timedelta


class CriticAgent:
    """批判 Agent：依据 knowledge/checklist.md 审查 Builder 的提案。

    Parameters
    ----------
    checklist_path : str, optional
        指向 checklist.md 的路径
    """

    def __init__(self, checklist_path: str = None):
        if checklist_path is None:
            base = os.path.dirname(os.path.dirname(__file__))
            checklist_path = os.path.join(base, "knowledge", "checklist.md")
        self.checklist_path = checklist_path
        self.checklist_items = self._load_checklist()

    def _load_checklist(self) -> List[Dict[str, str]]:
        """从 checklist.md 加载检查项。"""
        items = []
        current_marker = ""
        try:
            with open(self.checklist_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    mm = re.match(r"^#{1,3}\s.*\[(\w+)\]", line)
                    if mm:
                        current_marker = mm.group(1)
                        continue
                    m = re.match(r"^- \[ \]\s+(.*)", line)
                    if m:
                        items.append({"check": m.group(1), "marker": current_marker, "pass": True, "detail": ""})
        except FileNotFoundError:
            items = [{"check": "checklist.md not found", "marker": "", "pass": False, "detail": "path: " + self.checklist_path}]
        return items

    def review(self, builder_proposal: Dict, backtest_context: Dict) -> Dict:
        """审查 Builder 提案，返回裁决。

        Parameters
        ----------
        builder_proposal : dict
            BuilderAgent.propose() 的输出
        backtest_context : dict
            包含回测上下文信息，如 train_end, test_start, 样本量等

        Returns
        -------
        dict : {"verdict", "findings", "adjusted_confidence"}
        """
        findings = []

        for item in self.checklist_items:
            check_text = item["check"]
            marker = item.get("marker", "")
            passed, detail = self._evaluate_check(check_text, marker, builder_proposal, backtest_context)
            findings.append({"check": check_text, "pass": passed, "detail": detail})

        # 计算 verdict
        failures = [f for f in findings if not f["pass"]]
        critical_failures = [f for f in failures if "前视偏差" in f["check"]
                             or "Purging" in f["check"] or "全局" in f["check"]
                             or "过拟合" in f["check"]]

        if critical_failures:
            verdict = "REJECT"
            adj_conf = 0.0
        elif len(failures) >= 3:
            verdict = "DOWNGRADE"
            adj_conf = builder_proposal.get("confidence", 0.5) * 0.5
        elif len(failures) > 0:
            verdict = "DOWNGRADE"
            adj_conf = builder_proposal.get("confidence", 0.5) * 0.8
        else:
            verdict = "APPROVE"
            adj_conf = builder_proposal.get("confidence", 0.5)

        return {
            "verdict": verdict,
            "findings": findings,
            "adjusted_confidence": adj_conf,
            "total_checks": len(findings),
            "passed": len(findings) - len(failures),
            "failed": len(failures),
            "critical_failures": len(critical_failures),
        }

    def _evaluate_check(self, check_text: str, marker: str, proposal: Dict, ctx: Dict) -> tuple:
        """评估单条检查项。返回 (passed: bool, detail: str)。"""
        # Purging gap 检查
        if "Purging" in check_text or "purge" in check_text.lower():
            train_end = ctx.get("train_end")
            test_start = ctx.get("test_start")
            if train_end and test_start:
                gap = (test_start - train_end).days if hasattr(test_start - train_end, "days") else 0
                if gap >= 5:
                    return True, f"Purge gap={gap}d >= 5d"
                else:
                    return False, f"Purge gap={gap}d < 5d"
            return False, "Missing train_end or test_start"

        # Embargo 检查
        if "Embargo" in check_text or "embargo" in check_text.lower():
            if ctx.get("embargo_days", 0) >= 10:
                return True, f"Embargo={ctx['embargo_days']}d >= 10d"
            return False, f"Embargo={ctx.get('embargo_days', 0)}d < 10d"

        # 做空约束
        if "做空" in check_text or "short" in check_text.lower():
            w = proposal.get("weights", [])
            if all(w >= 0):
                return True, "All weights >= 0"
            return False, "Short positions detected"

        # 权重和
        if "权重和" in check_text or "sum" in check_text.lower():
            w = proposal.get("weights", [])
            if abs(sum(w) - 1.0) < 0.01:
                return True, f"Weights sum to {sum(w):.4f}"
            return False, f"Weights sum to {sum(w):.4f}, expected 1.0"

        # 单标的上限
        if "上限" in check_text or "max" in check_text.lower():
            w = proposal.get("weights", [])
            if max(w) <= 0.4:
                return True, f"Max weight={max(w):.2f} <= 0.4"
            return False, f"Max weight={max(w):.2f} > 0.4"

        # 测试集只跑 1 次
        if "测试集" in check_text and "1 次" in check_text:
            if ctx.get("test_run_count", 0) <= 1:
                return True, f"Test run count = {ctx.get('test_run_count', 1)}"
            return False, f"Test run count = {ctx.get('test_run_count')} > 1"

        # 数据量 / 样本检查
        if "样本" in check_text:
            n = ctx.get("n_samples", 0)
            if n >= 200:
                return True, f"Samples={n} >= 200"
            return False, f"Samples={n} < 200"

        # 佣金费率检查
        if "佣金" in check_text:
            rate = ctx.get("commission_rate", 0.00025)
            if rate >= 0.00025:
                return True, f"Commission rate={rate:.5f} >= 0.00025"
            return False, f"Commission rate={rate:.5f} < 0.00025"

        # 最低佣金检查
        if "最低佣金" in check_text:
            min_comm = ctx.get("min_commission", 5.0)
            if min_comm >= 5.0:
                return True, f"Min commission={min_comm:.1f} >= 5.0"
            return False, f"Min commission={min_comm:.1f} < 5.0"

        # 滑点检查
        if "滑点" in check_text:
            slip = ctx.get("slippage_bps", 2.0)
            if slip >= 2.0:
                return True, f"Slippage={slip:.1f}bp >= 2bp"
            return False, f"Slippage={slip:.1f}bp < 2bp"

        # 冲击成本非线性检查
        if "冲击成本" in check_text or "非线性" in check_text:
            if ctx.get("impact_model", "") in ("sqrt", "almgren-chriss"):
                return True, f"Impact model={ctx['impact_model']} (nonlinear)"
            return False, "Impact model is linear or missing"

        # 年化换手率
        if "换手率" in check_text:
            ann_to = ctx.get("annual_turnover", 0)
            if ann_to <= 3.0:
                return True, f"Annual turnover={ann_to:.1%} <= 300%"
            return False, f"Annual turnover={ann_to:.1%} > 300%"

        # 前视偏差 — HMM
        if "前视偏差" in check_text and "HMM" in check_text:
            if not ctx.get("hmm_global_scaling", False):
                return True, "HMM uses rolling fit (no global scaling)"
            return False, "HMM may use global scaling → look-ahead bias risk"

        # 前视偏差 — 滚动指标
        if "前视偏差" in check_text or "扩窗" in check_text:
            if ctx.get("rolling_expanding", True):
                return True, "Rolling indicators use expanding window"
            return False, "Rolling indicators may use full-sample data"

        # HMM BIC/AIC
        if "BIC" in check_text or "AIC" in check_text:
            if ctx.get("hmm_bic_recorded", False):
                return True, f"BIC recorded: {ctx.get('hmm_bic_value', 'N/A')}"
            return False, "BIC/AIC not recorded for HMM selection"

        # PBO 检查
        if "PBO" in check_text:
            pbo = ctx.get("pbo_value", 1.0)
            if pbo < 0.3:
                return True, f"PBO={pbo:.3f} < 0.3"
            return False, f"PBO={pbo:.3f} >= 0.3 (overfitting risk)"

        # DSR p-value 检查
        if "Deflated Sharpe" in check_text or "DSR" in check_text:
            dsr_p = ctx.get("dsr_p_value", 1.0)
            if dsr_p < 0.05:
                return True, f"DSR p={dsr_p:.4f} < 0.05"
            return False, f"DSR p={dsr_p:.4f} >= 0.05 (not significant)"

        # 参数敏感性
        if "参数敏感性" in check_text or "参数搜索" in check_text:
            if ctx.get("sensitivity_done", False):
                return True, "Parameter sensitivity analysis completed"
            return False, "Parameter sensitivity analysis not done"

        # 日志记录
        if "日志" in check_text and ("train_end" in check_text or "调仓" in check_text):
            if ctx.get("train_end") and ctx.get("test_start"):
                return True, f"Log: train_end={ctx['train_end']}, test_start={ctx['test_start']}"
            return False, "Missing train_end/test_start in logs"

        # 策略池可注入
        if "策略池" in check_text:
            if ctx.get("strategy_pool_injectable", True):
                return True, "Strategy pool is injectable"
            return False, "Strategy pool is hardcoded"

        # 幸存者偏差
        if "幸存者" in check_text or "Survivorship" in check_text:
            if ctx.get("survivorship_noted", False):
                return True, "Survivorship bias acknowledged/documented"
            return False, "Survivorship bias not addressed"

        return True, "Auto-pass (no specific check rule)"
