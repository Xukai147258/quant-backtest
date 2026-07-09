# coding: utf-8
"""Phase 1A: Lookahead bias defense (6 checks)."""
import time, logging
from typing import List
from .core import PhaseBase, CheckResult, CheckMode

logger = logging.getLogger(__name__)


class Phase1A(PhaseBase):
    def run_all(self, context: dict) -> List[CheckResult]:
        self.results.clear()
        test_intervals = context.get("walkforward_test_intervals", [])
        embargo_log = context.get("embargo_log", [])
        hmm_history = context.get("hmm_history", [])
        signal_log = context.get("signal_log", [])

        self._check_a1_purge(test_intervals)
        self._check_a2_embargo(embargo_log)
        self._check_a3_hmm_no_lookahead(hmm_history, test_intervals)
        self._check_a4_scaler_fit_range(hmm_history, test_intervals)
        self._check_a5_test_no_overlap(test_intervals)
        self._check_a6_signal_t1(signal_log)

        return self.results

    def _check_a1_purge(self, test_intervals):
        t0 = time.time()
        if not test_intervals:
            self.results.append(CheckResult("A1", "Purging gap", True, "No intervals to check"))
            return
        gaps = [(iv["test_start"] - iv["train_end"]).days for iv in test_intervals if iv.get("train_end") and iv.get("test_start")]
        if not gaps:
            self.results.append(CheckResult("A1", "Purging gap", True, "No valid intervals"))
            return
        min_gap = min(gaps)
        passed = min_gap >= 3
        msg = "Min gap=%dd PASS" % min_gap if passed else "Min gap=%dd < 3d FAIL" % min_gap
        self.results.append(CheckResult("A1", "Purging gap >= 3d", passed, msg, (time.time() - t0) * 1000, {"min_gap": min_gap}))

    def _check_a2_embargo(self, embargo_log):
        t0 = time.time()
        if not embargo_log:
            self.results.append(CheckResult("A2", "Embargo exclusion", True, "No embargo entries"))
            return
        ok = True
        for entry in embargo_log:
            if entry.get("prev_test_end") and entry.get("embargo_start"):
                if str(entry["embargo_start"]) != str(entry["prev_test_end"]):
                    ok = False
        msg = "All %d embargo entries OK" % len(embargo_log) if ok else "Embargo zone mismatch"
        self.results.append(CheckResult("A2", "Embargo exclusion", ok, msg, (time.time() - t0) * 1000, {"entries": len(embargo_log)}))

    def _check_a3_hmm_no_lookahead(self, hmm_history, test_intervals):
        t0 = time.time()
        if not hmm_history or not test_intervals:
            self.results.append(CheckResult("A3", "HMM no lookahead", True, "No HMM history"))
            return
        ok = True
        import pandas as pd
        for entry in hmm_history:
            fit_end = entry.get("fit_end")
            if fit_end:
                if isinstance(fit_end, str):
                    try:
                        fit_end = pd.Timestamp(fit_end[:10])
                    except Exception:
                        continue
                for iv in test_intervals:
                    train_end = iv.get("train_end")
                    if isinstance(train_end, str):
                        try:
                            train_end = pd.Timestamp(train_end[:10])
                        except Exception:
                            continue
                    if train_end and fit_end > train_end:
                        ok = False
                        break
        msg = "All HMM fits within train period" if ok else "HMM fit extends beyond train_end"
        self.results.append(CheckResult("A3", "HMM no lookahead", ok, msg, (time.time() - t0) * 1000, {"count": len(hmm_history)}))

    def _check_a4_scaler_fit_range(self, hmm_history, test_intervals):
        t0 = time.time()
        if not hmm_history:
            self.results.append(CheckResult("A4", "Scaler fit range", True, "No scaler history"))
            return
        ok = True
        import pandas as pd
        for entry in hmm_history:
            se = entry.get("scaler_fit_end")
            if se:
                if isinstance(se, str):
                    try:
                        se = pd.Timestamp(se[:10])
                    except Exception:
                        continue
                for iv in test_intervals:
                    train_end = iv.get("train_end")
                    if isinstance(train_end, str):
                        try:
                            train_end = pd.Timestamp(train_end[:10])
                        except Exception:
                            continue
                    if train_end and se > train_end:
                        ok = False
                        break
        msg = "All scaler fits within train period" if ok else "Scaler fit extends beyond train_end"
        self.results.append(CheckResult("A4", "Scaler fit range", ok, msg, (time.time() - t0) * 1000, {"count": len(hmm_history)}))

    def _check_a5_test_no_overlap(self, test_intervals):
        t0 = time.time()
        if len(test_intervals) < 2:
            self.results.append(CheckResult("A5", "Test set overlap", True, "Less than 2 intervals"))
            return
        ok = True
        import pandas as pd
        for i in range(len(test_intervals) - 1):
            te = test_intervals[i]["test_end"]
            ts = test_intervals[i + 1]["test_start"]
            if isinstance(te, str):
                te = pd.Timestamp(te)
            if isinstance(ts, str):
                ts = pd.Timestamp(ts)
            if te >= ts:
                ok = False
                break
        msg = "No test interval overlap" if ok else "Test intervals overlap detected"
        self.results.append(CheckResult("A5", "Test set overlap", ok, msg, (time.time() - t0) * 1000, {"count": len(test_intervals)}))

    def _check_a6_signal_t1(self, signal_log):
        t0 = time.time()
        if len(signal_log) < 2:
            self.results.append(CheckResult("A6", "Signal T+0 bias", True, "Insufficient signal data"))
            return
        from datetime import datetime
        ok = True
        for i in range(len(signal_log) - 1):
            curr = signal_log[i]
            nxt = signal_log[i + 1]
            cd = curr.get("compute_date")
            ad = nxt.get("apply_date")
            if cd and ad:
                # Handle string dates
                if isinstance(cd, str):
                    cd = datetime.strptime(cd[:10], "%Y-%m-%d")
                if isinstance(ad, str):
                    ad = datetime.strptime(ad[:10], "%Y-%m-%d")
                try:
                    gap = (ad - cd).days
                    if gap < 1:
                        ok = False
                        break
                except Exception:
                    pass  # Skip unparseable dates
        msg = "Signal compute-to-apply gap >= 1d" if ok else "T+0 signal bias detected"
        self.results.append(CheckResult("A6", "Signal T+0 bias", ok, msg, (time.time() - t0) * 1000, {"count": len(signal_log)}))
