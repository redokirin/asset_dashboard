# -*- coding: utf-8 -*-
"""
動態容忍帶（_BASE_TOLERANCE）歷史回測。

背景：core/analysis/advanced.py 用全域常數 _BASE_TOLERANCE=0.04 放寬「分類邊界」，
決定當下該把一檔標的標記成 追價警戒／日常加碼／回測加碼／狙擊加碼。這支腳本直接
重用專案既有的 buy_levels / technical / benchmark 邏輯（不重寫演算法），回放
1306.T、1321.T 的歷史價格，比較現行 4% 與三個更嚴格候選值（3%/2.5%/2%）下，同一組
歷史交易日會被分到哪個 zone，藉此量化「現行 4% 是否放行過寬」。

純評估用途，不修改正式系統參數（core/analysis/advanced.py 完全不動）。
詳見 refactor/動態容忍帶參數回測規劃.md。

用法：
  poetry run python scripts/backtest_tolerance_band.py
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
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
matplotlib.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "SimHei"]
matplotlib.rcParams["axes.unicode_minus"] = False
import yfinance as yf

from core.analysis.benchmark import get_smart_benchmark
from core.analysis.technical import _remove_price_spikes, calculate_drawdown_metrics, calculate_moving_averages
from core.buy_levels import MarketData, compute_atr20, get_buy_levels
from core.data_sources.patches import apply_yahoo_price_patches
from core.data_sources.yahoo import normalize_yfinance_columns

TARGET_TICKER = "1306.T"
EXTRA_TICKER = "1321.T"           # 順便驗證 RS P10 floor 對非 self-benchmark 標的的影響
TICKERS = [TARGET_TICKER, EXTRA_TICKER]

TOLERANCE_VERSIONS = [("A(現行)", 0.04), ("B", 0.03), ("C", 0.025), ("D", 0.02)]
_REFERENCE_VOL = 0.25
WINDOW_DAYS = 504  # ~2 年交易日，比照正式系統 fetch_historical_data(period="2y")

BUILD_DATES = ["2026-06-08", "2026-06-10", "2026-06-18"]
RECENT_DAYS_FOR_ZONE_SHIFT = 15  # 觀察 7/16~7/17 本輪修正前後 sniper 判定時間點是否提前/延後

OUT_DIR = Path(__file__).parent.parent / "analyze"
OUT_PNG = OUT_DIR / "tolerance_band_backtest_1306T.png"

TAG_LABEL = {"chase": "🔴追價警戒", "daily": "🟡日常加碼", "retest": "🟢回測加碼", "sniper": "⭐狙擊加碼"}


def fetch_close_ohlc(ticker: str) -> pd.DataFrame:
    """單一標的日線 OHLC，套用跟正式系統一致的欄位正規化與分割修正 patch。"""
    df = yf.download(ticker, period="5y", auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"{ticker} 查無資料")
    df = normalize_yfinance_columns(df)
    df = apply_yahoo_price_patches(df, [ticker])
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(-1)
    df.index = pd.to_datetime(df.index)
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df = df[["Open", "High", "Low", "Close"]].dropna(subset=["Close"])
    # 清掉單日／連續數日的離群報價（yfinance 偶發的暫態壞資料，例如某天 Close 誤植成 1/10），
    # 跟 calculate_drawdown_metrics 內部用的是同一個清理函式，避免壞資料污染 MA/ATR/買點計算
    return _remove_price_spikes(df, label=ticker)


def rolling_window(df: pd.DataFrame, end_idx: int) -> pd.DataFrame:
    """以 t=end_idx 為終點、往前兩年的視窗；資料不足兩年則用全部可用資料（對齊正式系統 period="2y" 的行為）。"""
    start_idx = max(0, end_idx + 1 - WINDOW_DAYS)
    return df.iloc[start_idx : end_idx + 1]


def compute_rs_p10_price(target_close: pd.Series, bench_close: pd.Series) -> float | None:
    """複製 core/analysis/advanced.py 的 RS P10 floor 公式（第 182~188 行），套用在滾動視窗上。"""
    comb = pd.DataFrame({"p": target_close, "b": bench_close}).ffill().dropna()
    if len(comb) < 20:
        return None
    rs_series = comb["p"] / comb["b"]
    rs_p10 = float(np.percentile(rs_series.values, 10))
    return rs_p10 * float(comb["b"].iloc[-1])


def classify_zone(price, daily_bid, pullback_bid, sniper_bid, annualized_vol, base_tolerance):
    """完全複製 core/analysis/advanced.py 第 258~286 行的 tolerance 公式與分類順序。"""
    if annualized_vol is None or annualized_vol <= 0:
        return None
    tolerance = (_REFERENCE_VOL / annualized_vol) * base_tolerance
    daily_upper = daily_bid * (1 + tolerance)
    retest_upper = pullback_bid * (1 + tolerance)
    sniper_upper = sniper_bid * (1 + tolerance)
    boundary_daily_retest = (daily_bid + retest_upper) / 2
    boundary_retest_sniper = (pullback_bid + sniper_upper) / 2

    if price > daily_upper:
        tag = "chase"
    elif price > boundary_daily_retest:
        tag = "daily"
    elif price > boundary_retest_sniper:
        tag = "retest"
    else:
        tag = "sniper"
    return {
        "tag": tag,
        "daily_upper": daily_upper,
        "boundary_daily_retest": boundary_daily_retest,
        "boundary_retest_sniper": boundary_retest_sniper,
    }


def backtest_ticker(df: pd.DataFrame, ticker: str, bench_df: pd.DataFrame | None) -> pd.DataFrame:
    """對單一標的逐日回放，回傳每個交易日、每個版本的 zone tag 與相關數值。"""
    is_self_benchmark = get_smart_benchmark(ticker) == ticker
    rows = []

    for t in range(len(df)):
        window = rolling_window(df, t)
        if len(window) < 120:
            continue

        ma_values, _ = calculate_moving_averages(window)
        if ma_values["ma20"] is None or ma_values["ma60"] is None or ma_values["ma120"] is None:
            continue

        try:
            atr20 = compute_atr20(window)
        except Exception:
            continue
        if atr20 is None or pd.isna(atr20):
            continue

        _, _, _, _, annualized_vol, _ = calculate_drawdown_metrics(window, sharpe=0.0, label=ticker)

        rs_p10_price = None
        if not is_self_benchmark and bench_df is not None:
            bench_window = bench_df.loc[bench_df.index <= window.index[-1]].tail(WINDOW_DAYS)
            rs_p10_price = compute_rs_p10_price(window["Close"], bench_window["Close"])

        price_t = float(window["Close"].iloc[-1])
        market_data = MarketData(
            price=price_t,
            ma20=ma_values["ma20"],
            ma60=ma_values["ma60"],
            ma120=ma_values["ma120"],
            atr20=float(atr20),
        )
        entries = get_buy_levels(
            asset={"市場": "日股", "代碼": ticker},
            data=market_data,
            rs_p10_price=rs_p10_price,
        )
        if entries is None:
            continue

        daily_bid = entries["日常波段"]
        pullback_bid = entries["技術回測"]
        sniper_bid = entries["狙擊位"]

        row = {
            "date": window.index[-1],
            "price": price_t,
            "daily_bid": daily_bid,
            "pullback_bid": pullback_bid,
            "sniper_bid": sniper_bid,
            "annualized_vol": annualized_vol,
            "gap_pct_vs_daily_bid": (price_t - daily_bid) / daily_bid if daily_bid else None,
        }
        for label, base_tolerance in TOLERANCE_VERSIONS:
            result = classify_zone(price_t, daily_bid, pullback_bid, sniper_bid, annualized_vol, base_tolerance)
            row[f"zone_{label}"] = result["tag"] if result else None
            row[f"daily_upper_{label}"] = result["daily_upper"] if result else None
        rows.append(row)

    return pd.DataFrame(rows).set_index("date")


def print_table1(bt_1306: pd.DataFrame):
    print("\n=== 表1：1306.T 三個實際建倉日 × 四版本 zone tag 對照 ===")
    cols = ["price", "daily_bid", "gap_pct_vs_daily_bid"] + [f"zone_{label}" for label, _ in TOLERANCE_VERSIONS]
    for d in BUILD_DATES:
        ts = pd.Timestamp(d)
        if ts not in bt_1306.index:
            print(f"⚠️ {d} 不在資料中（非交易日或超出下載範圍），請確認建倉日期年份是否正確")
            continue
        r = bt_1306.loc[ts]
        gap = r["gap_pct_vs_daily_bid"]
        print(f"\n--- {d} ---")
        print(f"price={r['price']:.2f}  daily_bid={r['daily_bid']:.2f}  gap%={gap:+.2%}")
        for label, _ in TOLERANCE_VERSIONS:
            print(f"  版本{label}: {TAG_LABEL.get(r[f'zone_{label}'], r[f'zone_{label}'])}")


def print_table2(bt_1306: pd.DataFrame):
    print("\n=== 表2：1306.T 全歷史 zone tag 分布（四版本） ===")
    for label, _ in TOLERANCE_VERSIONS:
        counts = bt_1306[f"zone_{label}"].value_counts(normalize=True).reindex(
            ["chase", "daily", "retest", "sniper"]
        ).fillna(0.0)
        line = "  ".join(f"{TAG_LABEL[tag]} {pct:.1%}" for tag, pct in counts.items())
        print(f"版本{label}: {line}")


def print_table3(backtests: dict[str, pd.DataFrame]):
    print(f"\n=== 表3：近 {RECENT_DAYS_FOR_ZONE_SHIFT} 個交易日 zone tag（本輪 7/16~7/17 修正前後對照） ===")
    for ticker, bt in backtests.items():
        print(f"\n--- {ticker} ---")
        recent = bt.tail(RECENT_DAYS_FOR_ZONE_SHIFT)
        cols = [f"zone_{label}" for label, _ in TOLERANCE_VERSIONS]
        display = recent[cols].copy()
        display.columns = [label for label, _ in TOLERANCE_VERSIONS]
        display.index = display.index.strftime("%Y-%m-%d")
        print(display.to_string())


def plot_chart(bt_1306: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.plot(bt_1306.index, bt_1306["price"], color="black", linewidth=1.2, label="price")
    ax.plot(bt_1306.index, bt_1306["daily_bid"], color="gray", linewidth=1.0, linestyle="--", label="daily_bid")

    colors = ["#d62728", "#ff7f0e", "#2ca02c", "#1f77b4"]
    for (label, _), color in zip(TOLERANCE_VERSIONS, colors):
        ax.plot(bt_1306.index, bt_1306[f"daily_upper_{label}"], color=color, linewidth=1.0,
                label=f"daily_upper {label}")

    for d in BUILD_DATES:
        ts = pd.Timestamp(d)
        if ts in bt_1306.index:
            ax.axvline(ts, color="purple", linestyle=":", alpha=0.6)
            ax.annotate(d, (ts, bt_1306.loc[ts, "price"]), textcoords="offset points",
                        xytext=(0, 10), fontsize=8, color="purple")

    ax.set_title("1306.T：price / daily_bid / daily_upper（四個 tolerance 版本）")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PNG, dpi=150)
    print(f"\n圖表已存檔：{OUT_PNG}")


def main():
    assert get_smart_benchmark("1306.T") == "1306.T", "1306.T 應為 self-benchmark，前提假設有誤"
    assert get_smart_benchmark("1321.T") == "1306.T", "1321.T 的 benchmark 應為 1306.T，前提假設有誤"

    print("下載歷史資料中...")
    raw = {t: fetch_close_ohlc(t) for t in TICKERS}

    print("回放中...")
    backtests = {}
    backtests[TARGET_TICKER] = backtest_ticker(raw[TARGET_TICKER], TARGET_TICKER, bench_df=None)
    backtests[EXTRA_TICKER] = backtest_ticker(raw[EXTRA_TICKER], EXTRA_TICKER, bench_df=raw[TARGET_TICKER])

    bt_1306 = backtests[TARGET_TICKER]
    print_table1(bt_1306)
    print_table2(bt_1306)
    print_table3(backtests)
    plot_chart(bt_1306)

    last = bt_1306.iloc[-1]
    print(f"\n=== 驗證用：最新交易日 {bt_1306.index[-1].date()}，版本 A(現行 0.04) 判定 ===")
    print(f"zone = {TAG_LABEL.get(last['zone_A(現行)'])}  "
          f"（可對照 Vue 看板 /api/analysis/advanced 目前顯示的 1306.T entryZoneStatus 是否一致）")


if __name__ == "__main__":
    main()
