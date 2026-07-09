# -*- coding: utf-8 -*-
"""
00985A.TW / 00981A.TW / 0052.TW 三資產均值-變異數分析。

【前置確認】
先確認 0052.TW 過去的股票分割（yfinance 1:7 分割 bug）在 auto_adjust=True 之後
是否仍有斷崖式異常，並套用 core/data_sources/patches.py 既有修正後再次確認。

【三資產分析】
用三者共同存在的重疊期間，計算相關係數矩陣、年化報酬/波動，並用均值-變異數
框架（不做空、權重 0~100%、加總 100%）求出最大化 Sharpe Ratio 的切線投資組合，
畫出效率前緣圖，標出三個單一標的、目前實際持股權重組合、最優點。

用法：
  poetry run python scripts/analyze_mvo_3assets.py

輸出：
  - 終端機列印：分割檢查、相關係數矩陣、最優權重、目前權重對照、白話結論
  - analyze/mvo_3assets_efficient_frontier.png：效率前緣圖
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
import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "SimHei",
    "Arial Unicode MS",
]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
from scipy.optimize import minimize

from core.data_sources.patches import apply_yahoo_price_patches
from core.data_sources.yahoo import normalize_yfinance_columns
from core.analysis.technical import get_clean_col

TICKERS = ["00985A.TW", "00981A.TW", "0052.TW"]
START = "2006-01-01"  # 抓長區間，讓 0052.TW 分割檢查可以看到完整歷史
END = "2026-07-10"  # yfinance end 不含當天
SPLIT_CHECK_DATE = "2025-11-17"  # 0052.TW 實際 1:7 分割日（見下方前置確認說明）
RISK_FREE_RATE = 0.0  # 與 scripts/analyze_active_etf_vs_benchmark.py 一致：不扣無風險利率
TRADING_DAYS = 252

# 目前實際持股成本（來自 assets_config.toml），用來換算「目前實際權重」組合
CURRENT_COST = {
    "00985A.TW": 78020,
    "00981A.TW": 19950,
    "0052.TW": 184200,
}

OUT_DIR = Path(__file__).parent.parent / "analyze"
OUT_PNG = OUT_DIR / "mvo_3assets_efficient_frontier.png"


# ── 資料抓取 ──────────────────────────────────────────────────────────────────


def fetch_raw_close(ticker: str, start: str, end: str) -> pd.Series:
    """抓取單一標的 auto_adjust=True 收盤價，不套任何補丁（用於分割檢查對照）。"""
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"{ticker} 查無資料（{start} ~ {end}）")
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df["Close"].dropna().sort_index()


def fetch_patched_close(ticker: str, start: str, end: str) -> pd.Series:
    """抓取單一標的收盤價，套用 core/data_sources/patches.py 已知分割修正。"""
    df = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"{ticker} 查無資料（{start} ~ {end}）")
    df = normalize_yfinance_columns(df)
    df = apply_yahoo_price_patches(df, [ticker])
    close = get_clean_col(df, ticker, "Close")
    close.name = ticker
    return close.dropna().sort_index()


def check_0052_split():
    print("=" * 70)
    print("【前置確認】0052.TW 股票分割還原檢查")
    print("=" * 70)

    raw = fetch_raw_close("0052.TW", START, END)
    split_ts = pd.Timestamp(SPLIT_CHECK_DATE)
    idx = raw.index.get_indexer([split_ts], method="nearest")[0]
    window_raw = raw.iloc[max(0, idx - 5) : idx + 6]

    print(f"\nauto_adjust=True 原始資料，分割日 {SPLIT_CHECK_DATE} 前後 5 個交易日：")
    print(window_raw.to_string())

    ratio = window_raw.iloc[4] / window_raw.iloc[5] if len(window_raw) >= 6 else float("nan")
    has_cliff = ratio > 2.0
    print(f"\n分割日前一天 / 分割日 比值 = {ratio:.2f}", end="")
    if has_cliff:
        print("  → 確認有斷崖式異常（auto_adjust=True 未能還原此分割，為已知 yfinance bug）")
    else:
        print("  → 無斷崖式異常")

    patched = fetch_patched_close("0052.TW", START, END)
    idx2 = patched.index.get_indexer([split_ts], method="nearest")[0]
    window_patched = patched.iloc[max(0, idx2 - 5) : idx2 + 6]
    print(f"\n套用 core/data_sources/patches.py 修正（1:7 還原）後，同一區間：")
    print(window_patched.to_string())

    ratio2 = window_patched.iloc[4] / window_patched.iloc[5] if len(window_patched) >= 6 else float("nan")
    print(f"\n修正後 分割日前一天 / 分割日 比值 = {ratio2:.2f}", end="")
    if abs(ratio2 - 1.0) < 0.05:
        print("  → 修正後價格連續，無斷崖式異常，分割已正確還原 ✅")
    else:
        print("  → 修正後仍有明顯跳動，需再檢查")

    print(
        "\n※ 注意：0052.TW 實際分割日為 2025-11-17（非 2026 年），"
        "yfinance auto_adjust=True 對此已知 1:7 分割存在還原 bug，"
        "本分析後續統一使用 core/data_sources/patches.py 的修正版本。\n"
    )


# ── 均值-變異數框架 ────────────────────────────────────────────────────────────


def portfolio_perf(weights, mean_returns, cov_matrix):
    ret = float(np.dot(weights, mean_returns)) * TRADING_DAYS
    vol = float(np.sqrt(weights @ cov_matrix @ weights)) * np.sqrt(TRADING_DAYS)
    sharpe = (ret - RISK_FREE_RATE) / vol if vol > 0 else np.nan
    return ret, vol, sharpe


def neg_sharpe(weights, mean_returns, cov_matrix):
    return -portfolio_perf(weights, mean_returns, cov_matrix)[2]


def min_vol_for_target_return(weights0, mean_returns, cov_matrix, target_ret, bounds, n):
    constraints = (
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        {"type": "eq", "fun": lambda w: np.dot(w, mean_returns) * TRADING_DAYS - target_ret},
    )
    result = minimize(
        lambda w: np.sqrt(w @ cov_matrix @ w) * np.sqrt(TRADING_DAYS),
        weights0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
    )
    return result


def solve_max_sharpe(mean_returns, cov_matrix, n):
    bounds = tuple((0.0, 1.0) for _ in range(n))
    constraints = ({"type": "eq", "fun": lambda w: np.sum(w) - 1.0},)
    w0 = np.repeat(1.0 / n, n)
    result = minimize(
        neg_sharpe,
        w0,
        args=(mean_returns, cov_matrix),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
    )
    return result


def build_efficient_frontier(mean_returns, cov_matrix, n, n_points=60):
    bounds = tuple((0.0, 1.0) for _ in range(n))
    w0 = np.repeat(1.0 / n, n)

    min_vol_result = minimize(
        lambda w: np.sqrt(w @ cov_matrix @ w) * np.sqrt(TRADING_DAYS),
        w0,
        method="SLSQP",
        bounds=bounds,
        constraints=({"type": "eq", "fun": lambda w: np.sum(w) - 1.0},),
    )
    min_ret = float(np.dot(min_vol_result.x, mean_returns)) * TRADING_DAYS
    max_ret = float(np.max(mean_returns)) * TRADING_DAYS

    target_returns = np.linspace(min_ret, max_ret, n_points)
    frontier_vol = []
    frontier_ret = []
    for target in target_returns:
        res = min_vol_for_target_return(w0, mean_returns, cov_matrix, target, bounds, n)
        if res.success:
            frontier_vol.append(res.fun)
            frontier_ret.append(target)
    return np.array(frontier_ret), np.array(frontier_vol)


# ── 主流程 ────────────────────────────────────────────────────────────────────


def main():
    check_0052_split()

    print("=" * 70)
    print("【三資產分析】重疊期間相關係數矩陣、年化報酬/波動")
    print("=" * 70)

    closes = {}
    for ticker in TICKERS:
        closes[ticker] = fetch_patched_close(ticker, START, END)
        print(f"{ticker}: {closes[ticker].index.min().date()} ~ {closes[ticker].index.max().date()}"
              f"（{len(closes[ticker])} 筆）")

    price_df = pd.concat(closes, axis=1).sort_index()
    price_df = price_df.dropna(how="any")  # 三者共同存在的重疊期間
    overlap_start, overlap_end = price_df.index.min(), price_df.index.max()
    print(f"\n三者共同重疊期間：{overlap_start.date()} ~ {overlap_end.date()}"
          f"（{len(price_df)} 個交易日）")

    returns = price_df.pct_change().dropna()

    corr = returns.corr()
    print("\n日報酬率相關係數矩陣：")
    print(corr.round(4).to_string())

    mean_returns = returns.mean()
    cov_matrix = returns.cov()

    print("\n各標的年化報酬率 / 年化波動率 / Sharpe（rf=0）：")
    summary_rows = []
    for ticker in TICKERS:
        ann_ret = mean_returns[ticker] * TRADING_DAYS
        ann_vol = returns[ticker].std() * np.sqrt(TRADING_DAYS)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else np.nan
        summary_rows.append((ticker, ann_ret, ann_vol, sharpe))
        print(f"  {ticker}: 年化報酬 {ann_ret:+.2%}, 年化波動 {ann_vol:.2%}, Sharpe {sharpe:.3f}")

    n = len(TICKERS)
    mean_arr = mean_returns[TICKERS].values
    cov_arr = cov_matrix.loc[TICKERS, TICKERS].values

    # 切線投資組合（最大化 Sharpe）
    opt_result = solve_max_sharpe(mean_arr, cov_arr, n)
    opt_weights = opt_result.x
    opt_ret, opt_vol, opt_sharpe = portfolio_perf(opt_weights, mean_arr, cov_arr)

    print("\n" + "=" * 70)
    print("【最優權重】最大化 Sharpe Ratio 的切線投資組合")
    print("=" * 70)
    for ticker, w in zip(TICKERS, opt_weights):
        print(f"  {ticker}: {w:.2%}")
    print(f"  → 年化報酬 {opt_ret:+.2%}, 年化波動 {opt_vol:.2%}, Sharpe {opt_sharpe:.3f}")

    # 目前實際持股權重（用成本金額換算）
    total_cost = sum(CURRENT_COST[t] for t in TICKERS)
    current_weights = np.array([CURRENT_COST[t] / total_cost for t in TICKERS])
    cur_ret, cur_vol, cur_sharpe = portfolio_perf(current_weights, mean_arr, cov_arr)

    print("\n" + "=" * 70)
    print("【目前實際權重】依持股成本金額換算")
    print("=" * 70)
    for ticker, w in zip(TICKERS, current_weights):
        print(f"  {ticker}: {w:.2%}（成本 {CURRENT_COST[ticker]:,}）")
    print(f"  → 年化報酬 {cur_ret:+.2%}, 年化波動 {cur_vol:.2%}, Sharpe {cur_sharpe:.3f}")

    print(f"\n【差距】最優組合 - 目前組合：")
    print(f"  年化報酬差距: {opt_ret - cur_ret:+.2%}")
    print(f"  年化波動差距: {opt_vol - cur_vol:+.2%}")
    print(f"  Sharpe 差距:  {opt_sharpe - cur_sharpe:+.3f}")

    # 效率前緣
    frontier_ret, frontier_vol = build_efficient_frontier(mean_arr, cov_arr, n)

    # 目前組合在效率前緣上的兩個對照點：
    # (1) 同樣風險（cur_vol）下，前緣能拿到的最高報酬
    # (2) 同樣報酬（cur_ret）下，前緣能承擔的最低風險
    same_risk_ret = float(np.interp(cur_vol, frontier_vol, frontier_ret))
    if cur_ret <= frontier_ret.max():
        w0 = np.repeat(1.0 / n, n)
        bounds = tuple((0.0, 1.0) for _ in range(n))
        same_ret_res = min_vol_for_target_return(w0, mean_arr, cov_arr, cur_ret, bounds, n)
        same_ret_vol = float(same_ret_res.fun) if same_ret_res.success else np.nan
    else:
        same_ret_vol = np.nan  # 目前報酬已超過前緣上限（單一資產全押 00981A.TW 的報酬）

    # ── 畫圖 ──
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.plot(frontier_vol, frontier_ret, "b-", linewidth=2, label="效率前緣")

    single_vols = [returns[t].std() * np.sqrt(TRADING_DAYS) for t in TICKERS]
    single_rets = [mean_returns[t] * TRADING_DAYS for t in TICKERS]
    colors = ["#e74c3c", "#f39c12", "#27ae60"]
    for ticker, v, r, c in zip(TICKERS, single_vols, single_rets, colors):
        ax.scatter(v, r, s=140, color=c, zorder=5, label=f"{ticker}（單一標的）")
        ax.annotate(ticker, (v, r), textcoords="offset points", xytext=(8, 6), fontsize=9)

    ax.scatter(cur_vol, cur_ret, s=220, marker="D", color="#8e44ad", zorder=6,
               label="目前實際權重組合")
    ax.annotate("目前組合", (cur_vol, cur_ret), textcoords="offset points",
                xytext=(8, -14), fontsize=9, color="#8e44ad")

    ax.scatter(opt_vol, opt_ret, s=260, marker="*", color="#c0392b", zorder=7,
               label="最優點（最大 Sharpe）")
    ax.annotate("最優點", (opt_vol, opt_ret), textcoords="offset points",
                xytext=(8, 6), fontsize=9, color="#c0392b")

    ax.annotate(
        "", xy=(cur_vol, same_risk_ret), xytext=(cur_vol, cur_ret),
        arrowprops=dict(arrowstyle="->", color="#7f8c8d", lw=1.2, linestyle="dashed"),
    )

    ax.set_xlabel("年化波動率")
    ax.set_ylabel("年化報酬率")
    ax.set_title(
        f"00985A.TW / 00981A.TW / 0052.TW 效率前緣\n"
        f"重疊期間 {overlap_start.date()} ~ {overlap_end.date()}"
    )
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.0%}"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{y:.0%}"))
    ax.legend(loc="best", fontsize=9)
    ax.grid(True, alpha=0.3)

    OUT_DIR.mkdir(exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)
    print(f"\n效率前緣圖已存至：{OUT_PNG}")

    # ── 白話結論 ──
    print("\n" + "=" * 70)
    print("【白話結論】")
    print("=" * 70)
    same_risk_gap = same_risk_ret - cur_ret  # 同樣風險下，前緣能多拿的報酬
    same_ret_gap = cur_vol - same_ret_vol if not np.isnan(same_ret_vol) else np.nan  # 同樣報酬下，前緣能少擔的風險

    print(f"目前組合：年化報酬 {cur_ret:+.2%}, 年化波動 {cur_vol:.2%}")
    print(f"  同樣風險（波動 {cur_vol:.2%}）下，效率前緣的報酬上限：{same_risk_ret:+.2%}"
          f"（差距 {same_risk_gap:+.2%}）")
    if not np.isnan(same_ret_vol):
        print(f"  同樣報酬（{cur_ret:+.2%}）下，效率前緣的風險下限：{same_ret_vol:.2%}"
              f"（差距 {same_ret_gap:+.2%}）")
    else:
        print("  目前報酬已達三資產中最高單一標的（00981A.TW）附近，前緣上沒有同報酬更低風險的點可比")

    if abs(same_risk_gap) < 0.01 and (np.isnan(same_ret_gap) or abs(same_ret_gap) < 0.01):
        print("\n→ 目前的配置已經非常接近效率前緣，用均值-變異數框架來看沒有明顯可以改善的空間。")
    else:
        msgs = []
        if same_risk_gap > 0.005:
            msgs.append(f"同樣風險下可以多拿約 {same_risk_gap:.1%} 的年化報酬")
        if not np.isnan(same_ret_gap) and same_ret_gap > 0.005:
            msgs.append(f"同樣報酬下可以少承擔約 {same_ret_gap:.1%} 的年化波動")
        if msgs:
            print("\n→ 目前的配置離效率前緣有一段明顯距離，" + "；".join(msgs) + "。")
        else:
            print("\n→ 目前的配置大致落在效率前緣附近，差距不算顯著。")

    print(f"\n（全域最大 Sharpe 的切線投資組合權重：{TICKERS[0]} {opt_weights[0]:.0%} / "
          f"{TICKERS[1]} {opt_weights[1]:.0%} / {TICKERS[2]} {opt_weights[2]:.0%}，"
          f"年化報酬 {opt_ret:+.2%}／波動 {opt_vol:.2%}／Sharpe {opt_sharpe:.3f}，"
          f"風險比目前組合高，是「風險換報酬」而非「同風險更高報酬」的方向。"
          f"僅為均值-變異數框架下的數學結果，且回測區間僅一年、兩檔主動 ETF 掛牌不到 14 個月，"
          f"未考慮流動性、稅費等實務限制，解讀請保守）")


if __name__ == "__main__":
    main()
