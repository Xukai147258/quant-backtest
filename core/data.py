# coding: utf-8
"""数据获取、清洗与划分模块。"""
import time
import logging
from typing import Tuple

import pandas as pd
import numpy as np
import akshare as ak

logger = logging.getLogger(__name__)

ASSETS = [
    ("510300", "沪深300",   "sh510300"),
    ("510500", "中证500",   "sh510500"),
    ("159915", "创业板",    "sz159915"),
    ("588000", "科创50",    "sh588000"),
    ("510050", "上证50",    "sh510050"),
    ("511010", "国债ETF",   "sh511010"),
    ("511260", "十年国债",  "sh511260"),
    ("518880", "黄金ETF",   "sh518880"),
    ("511360", "短融ETF",   "sh511360"),
]


def _fetch_single(symbol, code, retries=3):
    for attempt in range(retries):
        try:
            df = ak.fund_etf_hist_sina(symbol=symbol)
            if df is None or df.empty:
                raise ValueError("Empty data for " + symbol)
            df = df.rename(columns={"date": "date", "close": code})
            df["date"] = pd.to_datetime(df["date"])
            df = df[["date", code]].copy()
            df = df.sort_values("date").set_index("date")
            df.index = pd.DatetimeIndex(df.index)
            df[code] = pd.to_numeric(df[code], errors="coerce")
            return df
        except Exception as e:
            logger.warning(f"  [RETRY] {symbol} attempt {attempt+1}/{retries}: {e}")
            time.sleep(0.5 * (attempt + 1))
    logger.error(f"  [FAIL] {symbol}")
    return pd.DataFrame()


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    数据清洗完整流水线。

    步骤：
    1. 异常值检测：标记 abs(daily_return) > 0.20 的日期
    2. 复权连续性校验：相邻日涨跌幅不超过 ±20%
    3. 停牌处理：ffill ≤ 3 天，超过则 drop 该列数据
    4. 收益率 Winsorize：clip 到 ±5σ（逐资产计算）

    Parameters
    ----------
    df : pd.DataFrame
        原始价格数据

    Returns
    -------
    pd.DataFrame
        清洗后的价格数据
    """
    result = df.copy()

    # --- Step 1 & 2: 异常值和连续性检查 ---
    returns = result.pct_change()
    for col in result.columns:
        col_returns = returns[col]
        # 极端值检测 (abs > 20%)
        extremes = col_returns.abs() > 0.20
        n_extreme = extremes.sum()
        if n_extreme > 0:
            extreme_dates = col_returns[extremes].index.strftime("%Y-%m-%d").tolist()
            logger.warning(f"  [WARN] {col}: {n_extreme} extreme returns > 20% on {extreme_dates}")

        # 连续性校验：如果极端值出现在非首日，检查是否由数据录入错误导致
        # 这里我们只记录警告，不删除数据

    # --- Step 3: 停牌处理 ---
    for col in result.columns:
        # 检测连续 4 天及以上平盘（停牌标识）
        is_flat = result[col].diff().abs() < 1e-12  # 容忍浮点误差
        flat_streaks = is_flat.astype(int).groupby((~is_flat).cumsum()).cumsum()
        bad_mask = flat_streaks >= 4

        if bad_mask.any():
            n_halt_days = bad_mask.sum()
            logger.warning(f"  [WARN] {col}: {n_halt_days} days in halt (>= 4 consecutive flat days)")
            # 将停牌期间的价格设为 NaN（后续 forward-fill 会被限制）
            result.loc[bad_mask, col] = np.nan

    # 停牌填充：最多前向填充 3 天
    result = result.ffill(limit=3)

    # 删除仍然为 NaN 的行（停牌超过 3 天的日期）
    rows_before = len(result)
    result = result.dropna(how="any")
    rows_after = len(result)
    if rows_after < rows_before:
        logger.warning(f"  [WARN] Dropped {rows_before - rows_after} rows due to excessive halts")

    # --- Step 4: Winsorize 收益率 ---
    # 在算术收益率空间直接 clip，避免 log(1+r) 在 r ≤ -1 时的数值问题
    cleaned_returns = result.pct_change().dropna()
    for col in result.columns:
        col_rets = cleaned_returns[col]
        mean = col_rets.mean()
        std = col_rets.std()
        lower = mean - 5 * std
        upper = mean + 5 * std

        n_clipped = ((col_rets < lower) | (col_rets > upper)).sum()
        if n_clipped > 0:
            logger.warning(f"  [WARN] {col}: Winsorized {n_clipped} returns (5 sigma = [{lower:.4f}, {upper:.4f}])")

        # 在算术收益率空间直接裁剪，再重建价格序列
        # 使用百分位边界作为安全网：当 5σ 边界在极端非正态分布下失效时回退
        p_lower = col_rets.quantile(0.005)  # 0.5th percentile fallback
        p_upper = col_rets.quantile(0.995)  # 99.5th percentile fallback
        clip_lower = max(lower, p_lower) if np.isfinite(lower) else p_lower
        clip_upper = min(upper, p_upper) if np.isfinite(upper) else p_upper

        clipped_rets = col_rets.clip(lower=clip_lower, upper=clip_upper)

        # 从裁剪后的算术收益率重建价格（首日收益率 NaN 填 0 = 无变化）
        base_price = result[col].iloc[0]
        cum_rets = (1.0 + clipped_rets.fillna(0.0)).cumprod()
        # Prepend 1.0 (no change on day 0) to align N-1 cumprod array with N-length DataFrame
        cum_rets_aligned = np.concatenate([[1.0], cum_rets.values])
        result[col] = base_price * cum_rets_aligned

    return result


def fetch_etf_data(days=1825):
    """
    获取 9 只 ETF 的复权收盘价，清洗后合并为 wide DataFrame。
    """
    all_data = []
    cutoff = pd.Timestamp.today() - pd.Timedelta(days=days)
    for code, name, sym in ASSETS:
        logger.info(f"Fetching {name} ({code})...")
        df = _fetch_single(sym, code)
        if df.empty:
            continue
        df = df[df.index >= cutoff]
        all_data.append(df)
        time.sleep(0.3)
    if not all_data:
        raise RuntimeError("No ETF data fetched")
    result = pd.concat(all_data, axis=1, join="outer")
    expected = [c for c, _, _ in ASSETS]
    for c in expected:
        if c not in result.columns:
            result[c] = np.nan
    result = result[expected]
    result = result.sort_index()

    # 清洗
    logger.info("Cleaning data...")
    result = clean_data(result)

    return result


def split_data(prices, train_end, val_end, purge_days=5):
    """
    训练/验证/测试划分（含 Purging gap）。

    Parameters
    ----------
    prices : pd.DataFrame
        清洗后的价格数据，index=datetime
    train_end : str
        训练集结束日期（含），如 '2024-06-30'
    val_end : str
        验证集结束日期（含），如 '2025-06-30'
    purge_days : int
        Purging gap 天数，默认 5

    Returns
    -------
    Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]
        (train, val, test)，均为 prices 的子集
    """
    train_end_dt = pd.Timestamp(train_end)
    val_end_dt = pd.Timestamp(val_end)

    # Purge boundary: train_end 前 purge_days 天作为 train 的截止
    purge_gap = pd.Timedelta(days=purge_days)

    train = prices[prices.index <= train_end_dt - purge_gap].copy()
    val = prices[(prices.index > train_end_dt) & (prices.index <= val_end_dt)].copy()
    test = prices[prices.index > val_end_dt + purge_gap].copy()

    logger.info(
        f"split_data: train={train.shape}, val={val.shape}, test={test.shape}, "
        f"train_end={train_end}, val_end={val_end}, purge_days={purge_days}"
    )
    return train, val, test


