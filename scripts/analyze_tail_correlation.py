# -*- coding: utf-8 -*-
"""
00981A.TW（及台股衛星倉位）vs 1306.T 的「尾部相關性」檢查。

均值-變異數框架用的是全樣本相關係數，但若兩者在正常時期看起來分散，
卻在特定系統性壓力事件（例如 AI 估值疑慮下殺）時相關性大幅上升，
代表分散效果在最需要的時候會失效——這是全樣本相關係數矩陣看不到的風險。

計算：
  (a) 全樣本期間相關係數
  (b) 2026-06-23 ~ 2026-06-30「AI 估值疑慮」壓力測試期間相關係數

對象：
  1. 00981A.TW vs 1306.T
  2. 台股衛星倉位（00985A.TW + 00981A.TW + 0052.TW，依目前持股成本加權）vs 1306.T

用法：
  poetry run python scripts/analyze_tail_correlation.py
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import yfinance as yf

from core.data_sources.patches import apply_yahoo_price_patches
from core.data_sources.yahoo import normalize_yfinance_columns
from core.analysis.technical import get_clean_col

TICKERS = ["00985A.TW", "00981A.TW", "0052.TW", "1306.T"]
START = "2025-01-01"
END = "2026-07-10"  # yfinance end 不含當天

STRESS_START = "2026-06-23"
STRESS_END = "2026-06-30"  # inclusive
STRESS_LABEL = "AI估值疑慮壓力測試期間"

# 目前持股成本（來自 assets_config.toml），用來組出「台股衛星倉位」
SATELLITE_COST = {
    "00985A.TW": 78020,
    "00981A.TW": 19950,
    "0052.TW": 184200,
}


def fetch_patched_close(ticker: str, start: str, end: str) -> pd.Series:
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"{ticker} 查無資料（{start} ~ {end}）")
    df = normalize_yfinance_columns(df)
    df = apply_yahoo_price_patches(df, [ticker])
    close = get_clean_col(df, ticker, "Close")
    close.name = ticker
    return close.dropna().sort_index()


def corr_report(returns: pd.DataFrame, col_a: str, col_b: str, label: str, period_label: str):
    sub = returns[[col_a, col_b]].dropna()
    n = len(sub)
    corr = sub[col_a].corr(sub[col_b]) if n >= 2 else np.nan
    print(f"[{period_label}] {label}：n={n} 個交易日，相關係數 = {corr:.4f}"
          if not np.isnan(corr) else f"[{period_label}] {label}：n={n}，樣本不足無法計算")
    return corr, n


def main():
    print("=" * 70)
    print("【00981A.TW / 台股衛星倉位 vs 1306.T 尾部相關性檢查】")
    print("=" * 70)

    closes = {}
    for ticker in TICKERS:
        closes[ticker] = fetch_patched_close(ticker, START, END)

    price_df = pd.concat(closes, axis=1).sort_index().dropna(how="any")
    overlap_start, overlap_end = price_df.index.min(), price_df.index.max()
    print(f"\n全樣本重疊期間：{overlap_start.date()} ~ {overlap_end.date()}"
          f"（{len(price_df)} 個交易日）")

    returns = price_df.pct_change().dropna()

    # 台股衛星倉位：依目前成本權重加權日報酬
    total_cost = sum(SATELLITE_COST.values())
    sat_weights = {t: c / total_cost for t, c in SATELLITE_COST.items()}
    returns["台股衛星倉位"] = sum(returns[t] * w for t, w in sat_weights.items())
    print("\n台股衛星倉位權重（依目前持股成本換算）：")
    for t, w in sat_weights.items():
        print(f"  {t}: {w:.2%}")

    stress_mask = (returns.index >= pd.Timestamp(STRESS_START)) & (
        returns.index <= pd.Timestamp(STRESS_END)
    )
    stress_returns = returns.loc[stress_mask]

    print(f"\n壓力測試期間實際交易日：{list(stress_returns.index.date)}")
    if len(stress_returns) < 3:
        print("⚠ 壓力期間交易日數過少（<3），相關係數統計意義有限，僅供參考。")

    print("\n" + "-" * 70)
    print("(a) 全樣本期間 vs (b) 壓力測試期間 — 相關係數對照")
    print("-" * 70)

    pairs = [
        ("00981A.TW", "1306.T", "00981A.TW vs 1306.T"),
        ("台股衛星倉位", "1306.T", "台股衛星倉位 vs 1306.T"),
    ]

    results = []
    for col_a, col_b, label in pairs:
        full_corr, full_n = corr_report(returns, col_a, col_b, label, "全樣本(a)")
        stress_corr, stress_n = corr_report(stress_returns, col_a, col_b, label, f"壓力期間(b) {STRESS_LABEL}")
        results.append((label, full_corr, stress_corr))
        print()

    print("=" * 70)
    print("【對照總表】")
    print("=" * 70)
    print(f"{'標的組合':<28} {'(a)全樣本':>10} {'(b)壓力期間':>12} {'差距(b-a)':>10}")
    for label, full_corr, stress_corr in results:
        gap = stress_corr - full_corr if not (np.isnan(full_corr) or np.isnan(stress_corr)) else np.nan
        gap_str = f"{gap:+.4f}" if not np.isnan(gap) else "N/A"
        print(f"{label:<28} {full_corr:>10.4f} {stress_corr:>12.4f} {gap_str:>10}")

    print("\n" + "=" * 70)
    print("【白話結論】")
    print("=" * 70)
    for label, full_corr, stress_corr in results:
        if np.isnan(stress_corr):
            print(f"- {label}：壓力期間樣本不足，無法判斷尾部相關性是否上升。")
            continue
        gap = stress_corr - full_corr
        if gap > 0.15:
            print(f"- {label}：壓力期間相關係數（{stress_corr:.2f}）明顯高於全樣本（{full_corr:.2f}），"
                  f"上升 {gap:+.2f}。代表正常時期看起來有分散效果，"
                  f"但在 AI 估值疑慮這類系統性下跌時會同步失效——這是均值-變異數框架看不到的"
                  f"「尾部相關性上升」風險，分散效果在最需要的時候打折。")
        elif gap > 0.05:
            print(f"- {label}：壓力期間相關係數（{stress_corr:.2f}）略高於全樣本（{full_corr:.2f}），"
                  f"上升 {gap:+.2f}，有輕微尾部相關性上升的跡象，但不算劇烈。")
        else:
            print(f"- {label}：壓力期間相關係數（{stress_corr:.2f}）與全樣本（{full_corr:.2f}）差距不大"
                  f"（{gap:+.2f}），沒有明顯的尾部相關性上升訊號——至少在這次事件中，"
                  f"分散效果在壓力期間仍大致維持。")
    print("\n※ 提醒：壓力期間只有數個交易日，樣本量小、相關係數估計值本身波動很大，"
          "此結果應視為方向性參考，而非精確統計推論。")


if __name__ == "__main__":
    main()
