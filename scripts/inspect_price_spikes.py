# -*- coding: utf-8 -*-
"""
列出 _remove_price_spikes() 判定為異常、會被過濾掉的價格點，方便肉眼確認是真異常還是誤殺。
沿用 advanced.py 實際的抓取路徑（fetch_common_data + get_clean_col），確保跟正式流程資料一致。

用法：
  .venv/Scripts/python.exe scripts/inspect_price_spikes.py 0050.TW
  .venv/Scripts/python.exe scripts/inspect_price_spikes.py 1306.T VOO   # 可一次查多檔
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from core.fetchers import fetch_common_data
from core.analysis.technical import get_clean_col

FACTOR = 3.0


def inspect(ticker: str):
    print("=" * 70)
    print(f"  {ticker}")
    print("=" * 70)

    common_raw = fetch_common_data((ticker,), period="2y")
    series = get_clean_col(common_raw, ticker, "Close")
    if series.empty:
        print("  查無資料\n")
        return

    df = series.to_frame("Close")
    med = df["Close"].rolling(5, center=True, min_periods=2).median()
    valid = (df["Close"] <= med * FACTOR) & (df["Close"] >= med / FACTOR)

    flagged = df[~valid].copy()
    flagged["rolling_median"] = med[~valid]
    flagged["ratio_to_median"] = (flagged["Close"] / flagged["rolling_median"]).round(3)

    print(f"  總筆數：{len(df)}　被判定異常：{len(flagged)}")
    print()
    if flagged.empty:
        print("  無異常點\n")
        return

    print(f"  {'日期':<12}  {'收盤價':>12}  {'5日滾動中位數':>14}  {'比值':>8}")
    print(f"  {'-'*12}  {'-'*12}  {'-'*14}  {'-'*8}")
    for idx, row in flagged.iterrows():
        print(f"  {str(idx.date()):<12}  {row['Close']:>12.2f}  {row['rolling_median']:>14.2f}  {row['ratio_to_median']:>8.2f}")
    print()


def main():
    tickers = sys.argv[1:] or ["0050.TW"]
    for t in tickers:
        inspect(t)


if __name__ == "__main__":
    main()
