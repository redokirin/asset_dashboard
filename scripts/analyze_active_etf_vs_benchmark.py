# -*- coding: utf-8 -*-
"""
分析台股主動式 ETF 00985A.TW / 00981A.TW 自掛牌以來相對大盤的表現，
並檢驗「近期落後是否只是這波大盤下跌造成的短期現象」。

用法：
  .venv/Scripts/python.exe scripts/analyze_active_etf_vs_benchmark.py

輸出：
  - 終端機列印：全期間表現總表、(a)/(b) 分段超額報酬與 Beta 對照表、白話結論
  - analyze/active_etf_vs_benchmark_rolling.png：60 日滾動相對 0050.TW 超額報酬圖
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
# os.environ 設定對已開啟的 stdout 無效（编码在 interpreter 啟動時就固定了），
# 部分 Windows 主控台（cp950）遇到 emoji 會直接噴 UnicodeEncodeError，這裡強制重設
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib

matplotlib.use("Agg")  # 無頭環境（無 GUI）存 png 用
matplotlib.rcParams["font.sans-serif"] = [
    "Microsoft JhengHei",
    "Microsoft YaHei",
    "SimHei",
    "Arial Unicode MS",
]
matplotlib.rcParams["axes.unicode_minus"] = (
    False  # 中文字型常沒有全形負號，避免軸標籤缺字
)
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy import stats

from core.data_sources.patches import apply_yahoo_price_patches
from core.data_sources.yahoo import normalize_yfinance_columns
from core.analysis.technical import get_clean_col

# ── 設定 ──────────────────────────────────────────────────────────────────────

TODAY = "2026-07-09"
SPLIT_DATE = "2026-06-22"  # (a) 掛牌 ~ 這天（含）；(b) 這天次日 ~ 今天
RISK_FREE_RATE = 0.0  # Sharpe 用的無風險利率假設：0%（未扣掉台幣定存/國庫券利率）
ROLLING_WINDOW = 60  # 交易日

ETF_LISTING_DATES = {
    "00985A.TW": "2025-07-21",
    "00981A.TW": "2025-05-27",
    # 0052.TW 真實上市日是 2006 年，但這裡是要跟兩檔新主動式 ETF 同窗口比較，
    # 不是要看它完整歷史，故意用跟 00981A.TW 一樣的起計日；本身歷史上有 1:7 分割，
    # fetch_close() 會套用 core/data_sources/patches.py 既有的修正
    "0052.TW": "2025-05-27",
}
BENCHMARKS = ["0050.TW", "^TWII"]

OUT_DIR = Path(__file__).parent.parent / "analyze"
OUT_PNG = OUT_DIR / "active_etf_vs_benchmark_rolling.png"


# ── 資料抓取 ──────────────────────────────────────────────────────────────────


def fetch_close(ticker: str, start: str, end: str) -> pd.Series:
    """
    抓取單一標的每日收盤價。yfinance auto_adjust=True 已還原除權息，
    等同含息報酬（total return）序列。
    end 用 yfinance 慣例是不含當天，這裡自動 +1 天確保抓到 TODAY。
    """
    end_inclusive = (pd.Timestamp(end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    df = yf.download(
        ticker, start=start, end=end_inclusive, auto_adjust=True, progress=False
    )
    if df is None or df.empty:
        raise RuntimeError(
            f"{ticker} 查無資料（{start} ~ {end}），請確認代碼或網路連線"
        )
    # yf.download 對單一 ticker 回傳的 MultiIndex 是 (欄位, ticker) 順序，
    # apply_yahoo_price_patches() 是照主程式慣例預期 (ticker, 欄位)，要先 normalize
    # 再套用修正，否則像 0052.TW 1:7 分割這種已知問題會被靜默略過、抓不到符合的欄位。
    df = normalize_yfinance_columns(df)
    df = apply_yahoo_price_patches(df, [ticker])
    close = get_clean_col(df, ticker, "Close")
    close.name = ticker
    return close.dropna().sort_index()


# ── 指標計算 ──────────────────────────────────────────────────────────────────


def annualized_vol(daily_returns: pd.Series) -> float:
    if daily_returns.empty:
        return float("nan")
    return float(daily_returns.std() * np.sqrt(252))


def sharpe_ratio(daily_returns: pd.Series, rf: float = 0.0) -> float:
    if daily_returns.empty:
        return float("nan")
    ann_return = float(daily_returns.mean() * 252)
    ann_vol = annualized_vol(daily_returns)
    return (ann_return - rf) / ann_vol if ann_vol else float("nan")


def cumulative_return(close: pd.Series) -> float:
    if len(close) < 2:
        return float("nan")
    return float(close.iloc[-1] / close.iloc[0] - 1)


def max_drawdown(close: pd.Series) -> float:
    if close.empty:
        return float("nan")
    running_max = close.cummax()
    drawdown = close / running_max - 1
    return float(drawdown.min())


def capm_alpha_beta(
    asset_close: pd.Series, bench_close: pd.Series
) -> tuple[float, float]:
    """
    簡單 CAPM 迴歸：日報酬 asset = alpha_daily + beta * bench + 誤差。
    回傳 (年化 alpha, beta)。資料點不足 10 筆時回傳 (nan, nan)。
    """
    common_idx = asset_close.index.intersection(bench_close.index)
    a_ret = asset_close.loc[common_idx].sort_index().pct_change().dropna()
    b_ret = bench_close.loc[common_idx].sort_index().pct_change().dropna()
    aligned = pd.concat([a_ret, b_ret], axis=1, join="inner").dropna()
    if len(aligned) < 10:
        return float("nan"), float("nan")
    result = stats.linregress(aligned.iloc[:, 1].values, aligned.iloc[:, 0].values)
    beta = float(result.slope)
    alpha_annualized = float(result.intercept) * 252
    return alpha_annualized, beta


def own_metrics(close: pd.Series) -> dict:
    """跟基準無關的自身指標：累積報酬率／年化波動率／Sharpe／MDD。"""
    daily_ret = close.pct_change().dropna()
    return {
        "累積報酬率": cumulative_return(close),
        "年化波動率": annualized_vol(daily_ret),
        "Sharpe": sharpe_ratio(daily_ret, RISK_FREE_RATE),
        "MDD": max_drawdown(close),
    }


def slice_period(close: pd.Series, start: str, end: str) -> pd.Series:
    return close.loc[
        (close.index >= pd.Timestamp(start)) & (close.index <= pd.Timestamp(end))
    ]


# ── 主流程 ────────────────────────────────────────────────────────────────────


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n抓取資料中（Sharpe 無風險利率假設 = {RISK_FREE_RATE:.0%}）...\n")

    etf_close: dict[str, pd.Series] = {}
    for ticker, listing_date in ETF_LISTING_DATES.items():
        etf_close[ticker] = fetch_close(ticker, listing_date, TODAY)
        print(f"  {ticker}  掛牌 {listing_date}  抓到 {len(etf_close[ticker])} 筆")

    bench_close: dict[str, pd.Series] = {}
    earliest_listing = min(ETF_LISTING_DATES.values())
    for ticker in BENCHMARKS:
        bench_close[ticker] = fetch_close(ticker, earliest_listing, TODAY)
        print(f"  {ticker}  抓到 {len(bench_close[ticker])} 筆")

    # ── 總表：各 ETF 自掛牌以來 vs 兩個基準 ──────────────────────────────────
    rows = []
    for etf, listing_date in ETF_LISTING_DATES.items():
        etf_c = etf_close[etf]
        etf_row = {
            "標的": etf,
            "角色": "主動式ETF",
            "期間起": listing_date,
            "期間迄": TODAY,
        }
        etf_row.update(own_metrics(etf_c))
        for bench in BENCHMARKS:
            bench_c_window = slice_period(bench_close[bench], listing_date, TODAY)
            alpha, beta = capm_alpha_beta(etf_c, bench_c_window)
            short = "0050" if bench == "0050.TW" else "TWII"
            etf_row[f"Alpha vs {short}(年化)"] = alpha
            etf_row[f"Beta vs {short}"] = beta
        rows.append(etf_row)

        # 同一窗口下基準自己的表現，方便對照（Alpha/Beta 欄位留空，對自己沒有意義）
        for bench in BENCHMARKS:
            bench_c_window = slice_period(bench_close[bench], listing_date, TODAY)
            bench_row = {
                "標的": f"{bench}（{etf} 窗口）",
                "角色": "基準",
                "期間起": listing_date,
                "期間迄": TODAY,
            }
            bench_row.update(own_metrics(bench_c_window))
            rows.append(bench_row)

    summary_df = pd.DataFrame(rows)
    pct_cols = [
        c
        for c in summary_df.columns
        if ("報酬" in c or "波動" in c or "Alpha" in c or c == "MDD")
    ]
    print("\n" + "=" * 100)
    print("  自掛牌以來總表")
    print("=" * 100)
    with pd.option_context("display.width", 160, "display.max_columns", None):
        print(summary_df.round(4).to_string(index=False))

    # ── (a)/(b) 分段：相對 0050.TW 的超額報酬與 Beta ─────────────────────────
    period_rows = []
    for etf, listing_date in ETF_LISTING_DATES.items():
        etf_c = etf_close[etf]
        bench_c = bench_close["0050.TW"]
        period_bounds = {
            "(a) 掛牌→修正前": (listing_date, SPLIT_DATE),
            "(b) 修正後→今天": (
                (pd.Timestamp(SPLIT_DATE) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                TODAY,
            ),
        }
        for label, (p_start, p_end) in period_bounds.items():
            etf_seg = slice_period(etf_c, p_start, p_end)
            bench_seg = slice_period(bench_c, p_start, p_end)
            if len(etf_seg) < 2 or len(bench_seg) < 2:
                continue
            etf_cum = cumulative_return(etf_seg)
            bench_cum = cumulative_return(bench_seg)
            _, beta = capm_alpha_beta(etf_seg, bench_seg)
            period_rows.append(
                {
                    "標的": etf,
                    "區段": label,
                    "起": p_start,
                    "迄": p_end,
                    "ETF累積報酬": etf_cum,
                    "0050.TW累積報酬": bench_cum,
                    "超額報酬(vs 0050)": etf_cum - bench_cum,
                    "Beta(vs 0050)": beta,
                }
            )

    period_df = pd.DataFrame(period_rows)
    print("\n" + "=" * 100)
    print(f"  分段比較（切點：{SPLIT_DATE}）")
    print("=" * 100)
    with pd.option_context("display.width", 160, "display.max_columns", None):
        print(period_df.round(4).to_string(index=False))

    # ── 60 日滾動相對 0050.TW 超額報酬圖 ─────────────────────────────────────
    bench_0050 = bench_close["0050.TW"]
    rolling_series = {}
    for etf in ETF_LISTING_DATES:
        etf_c = etf_close[etf]
        common_idx = etf_c.index.intersection(bench_0050.index)
        etf_aligned = etf_c.loc[common_idx].sort_index()
        bench_aligned = bench_0050.loc[common_idx].sort_index()
        etf_roll = etf_aligned / etf_aligned.shift(ROLLING_WINDOW) - 1
        bench_roll = bench_aligned / bench_aligned.shift(ROLLING_WINDOW) - 1
        rolling_series[etf] = (etf_roll - bench_roll).dropna()

    fig, ax = plt.subplots(figsize=(11, 5))
    for etf, series in rolling_series.items():
        ax.plot(series.index, series.values * 100, label=etf, linewidth=1.6)
    ax.axhline(0, color="#888888", linewidth=0.8, linestyle="--")
    ax.axvline(
        pd.Timestamp(SPLIT_DATE),
        color="#e11d48",
        linewidth=1,
        linestyle=":",
        label=f"分段切點 {SPLIT_DATE}",
    )
    ax.set_title(f"{ROLLING_WINDOW} 日滾動相對 0050.TW 累積超額報酬")
    ax.set_ylabel("超額報酬 (%)")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax.legend(loc="best", fontsize=9)
    ax.grid(alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(OUT_PNG, dpi=150)
    print(f"\n✅ 已存圖：{OUT_PNG}")

    # ── 白話結論 ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 100)
    print("  白話結論")
    print("=" * 100)
    for etf in ETF_LISTING_DATES:
        rows_etf = period_df[period_df["標的"] == etf]
        row_a = rows_etf[rows_etf["區段"].str.startswith("(a)")]
        row_b = rows_etf[rows_etf["區段"].str.startswith("(b)")]
        if row_a.empty or row_b.empty:
            print(f"\n[{etf}] 資料不足，無法比較兩段期間。")
            continue
        excess_a = row_a["超額報酬(vs 0050)"].iloc[0]
        excess_b = row_b["超額報酬(vs 0050)"].iloc[0]
        beta_a = row_a["Beta(vs 0050)"].iloc[0]
        beta_b = row_b["Beta(vs 0050)"].iloc[0]

        beta_jumped = beta_b > beta_a + 0.1  # 下跌段 beta 明顯放大
        lagged_before = excess_a < 0  # 上漲段本來就落後
        lagged_after = excess_b < 0  # 下跌段落後

        print(f"\n[{etf}]")
        print(f"  (a) 掛牌→{SPLIT_DATE}：超額報酬 {excess_a:+.2%}，Beta {beta_a:.2f}")
        print(f"  (b) {SPLIT_DATE}後→今天：超額報酬 {excess_b:+.2%}，Beta {beta_b:.2f}")

        if lagged_after and beta_jumped and not lagged_before:
            verdict = "(i) 主要是下跌段 Beta 較高、跌得比較兇造成的——上漲段其實沒有落後，是最近這波修正才被放大跌幅。"
        elif lagged_after and lagged_before and not beta_jumped:
            verdict = "(ii) 主要是它在上漲段本來就漲得比較少——下跌段的 Beta 沒有明顯放大，落後是長期趨勢延續，不是這波下跌才出現的。"
        elif lagged_after and lagged_before and beta_jumped:
            verdict = (
                "(iii) 兩者都有：上漲段本來就落後，下跌段 Beta 又放大跌幅，雙重不利。"
            )
        elif not lagged_after:
            verdict = "近期（區段 b）相對 0050.TW 其實沒有落後，如果觀察到的「落後」是來自其他比較基準或時間窗口，建議重新確認比較區間。"
        else:
            verdict = "落後幅度小或訊號不明顯，建議搭配上面的分段數字自行判斷，不要只看單一結論。"

        print(f"  → {verdict}")

    print()


if __name__ == "__main__":
    main()
