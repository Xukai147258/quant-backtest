# coding: utf-8
"""HMM 滚动重训：每步只用历史数据 fit，避免前视偏差。"""
import warnings
from typing import Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from hmmlearn import hmm


class RollingHMMDetector:
    """滚动 HMM 状态检测器。

    每步 fit 时只使用截至当前日期的历史数据，
    标准化参数（mean/std）也仅基于历史数据计算。

    Parameters
    ----------
    n_states : int
        隐状态数量，默认 4
    n_iter : int
        EM 迭代次数，默认 200
    random_state : int
        随机种子，默认 42
    """

    def __init__(self, n_states: int = 4, n_iter: int = 200, random_state: int = 42):
        self.n_states = n_states
        self.n_iter = n_iter
        self.random_state = random_state
        self.history: list = []  # 记录每次 fit 的信息

    def fit_predict(self, features: pd.DataFrame) -> Tuple[int, object, StandardScaler]:
        """用历史数据 fit HMM，返回当前状态。

        Parameters
        ----------
        features : pd.DataFrame
            特征数据，index=datetime，columns=特征名。
            仅使用截至当前日期的所有数据。

        Returns
        -------
        tuple : (current_state, model, scaler)
            current_state : int — 最新观测的状态 ID
            model : GaussianHMM — 训练好的模型
            scaler : StandardScaler — 拟合的标准化器
        """
        if len(features) < self.n_states * 5:
            raise ValueError(
                f"Need at least {self.n_states * 5} obs, got {len(features)}"
            )

        # 标准化（仅基于历史数据）
        scaler = StandardScaler()
        scaled = scaler.fit_transform(features.values)

        # 训练 HMM
        model = hmm.GaussianHMM(
            n_components=self.n_states,
            covariance_type="diag",
            n_iter=self.n_iter,
            random_state=self.random_state,
        )
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=DeprecationWarning)
            model.fit(scaled)

        # 状态序列
        states = model.predict(scaled)

        # T5: HMM state remapping — order by mean return (0=lowest/bear, max=highest/bull)
        port_rets_col = features["ret_1d"].values if "ret_1d" in features.columns else None
        if port_rets_col is not None:
            state_means = {}
            for s in range(self.n_states):
                mask = states == s
                state_means[s] = float(port_rets_col[mask].mean()) if mask.sum() > 0 else -1e10
            sorted_states = sorted(state_means.items(), key=lambda x: x[1])
            mapping = {old: new for new, (old, _) in enumerate(sorted_states)}
            states = np.array([mapping[s] for s in states])
            model.state_means_sorted = [v for _, v in sorted_states]

        current_state = int(states[-1])

        # BIC 计算
        n_params = self.n_states * self.n_states - 1  # 转移矩阵
        n_params += self.n_states * features.shape[1]  # 均值
        n_params += self.n_states * features.shape[1]  # 对角方差
        log_likelihood = model.score(scaled)
        bic = -2 * log_likelihood + n_params * np.log(len(features))

        # 记录
        self.history.append({
            "n_obs": len(features),
            "bic": bic,
            "log_likelihood": log_likelihood,
            "n_params": n_params,
            "states_distribution": {
                str(s): int((states == s).sum()) for s in range(self.n_states)
            },
        })

        return current_state, model, scaler



def select_optimal_n_states(features, max_states=8, min_states=2):
    """使用 BIC 自动选择最优 HMM 状态数。每个状态数训练一次，BIC 最低者胜出。"""
    import warnings
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    scaled = scaler.fit_transform(features.values)
    best_bic = float("inf")
    best_n = min_states
    for n in range(min_states, max_states + 1):
        model = hmm.GaussianHMM(n_components=n, covariance_type="diag", n_iter=200, random_state=42)
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=DeprecationWarning)
                model.fit(scaled)
            ll = model.score(scaled)
            n_params = n * n - 1 + 2 * n * features.shape[1]
            bic = -2 * ll + n_params * np.log(len(features))
            if bic < best_bic:
                best_bic, best_n = bic, n
        except Exception:
            continue
    return best_n


def compute_features(prices: pd.DataFrame, window: int = 20) -> pd.DataFrame:
    """计算 HMM 输入特征（滚动统计量）。

    Parameters
    ----------
    prices : pd.DataFrame
        价格数据，index=datetime
    window : int
        滚动窗口大小，默认 20

    Returns
    -------
    pd.DataFrame
        特征矩阵
    """
    returns = prices.pct_change().dropna()

    features = pd.DataFrame(index=returns.index)
    # 等权组合收益率
    port_rets = returns.mean(axis=1)
    features["ret_1d"] = port_rets
    features["ret_5d"] = port_rets.rolling(5).mean()
    features["ret_20d"] = port_rets.rolling(20).mean()
    features["vol_20d"] = port_rets.rolling(window).std()
    # max_corr: rolling max pairwise correlation across all assets
    max_corr_vals = []
    for i in range(window - 1, len(returns)):
        w = returns.iloc[i - window + 1 : i + 1]
        cm = w.corr().values
        n = cm.shape[0]
        if n > 1:
            off_diag = cm[np.triu_indices(n, k=1)]
            max_corr_vals.append(off_diag.max())
        else:
            max_corr_vals.append(0.0)
    features["max_corr"] = pd.Series(max_corr_vals, index=returns.index[window - 1:])
    features["spread"] = returns.std(axis=1)

    return features.dropna()
