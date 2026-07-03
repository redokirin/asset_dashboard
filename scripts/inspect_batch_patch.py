# -*- coding: utf-8 -*-
"""
重現正式流程「多檔一起批次下載」的情境，比對 apply_yahoo_price_patches() 修正前後的
1306.T 資料，找出為什麼批次抓法會比單獨抓法多出更多異常價格點。

用法：
  .venv/Scripts/python.exe scripts/inspect_batch_patch.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from core.data_sources.yahoo import FETCHERS, normalize_yfinance_columns
from core.data_sources.patches import apply_yahoo_price_patches
from core.analysis.technical import get_clean_col

FACTOR = 3.0
TARGET = "1306.T"

# 模擬正式流程 all_bench_tickers 的組成：多檔基準 + 兩個匯率
BATCH_TICKERS = [TARGET, "VOO", "0050.TW", "JPYTWD=X", "USDTWD=X"]


def flag_spikes(series: pd.Series, label: str):
    df = series.to_frame("Close")
    med = df["Close"].rolling(5, center=True, min_periods=2).median()
    valid = (df["Close"] <= med * FACTOR) & (df["Close"] >= med / FACTOR)
    flagged = df[~valid].copy()
    print(f"  [{label}] 總筆數：{len(df)}　異常：{len(flagged)}")
    if not flagged.empty:
        for idx, row in flagged.iterrows():
            print(f"      {idx.date()}  {row['Close']:.2f}")
    return flagged


print("=" * 70)
print("  Step 1：批次原始下載（尚未套用 patch）")
print("=" * 70)
raw = FETCHERS["common"](BATCH_TICKERS, period="2y")
raw_norm = normalize_yfinance_columns(raw)
raw_series = get_clean_col(raw_norm, TARGET, "Close")
flag_spikes(raw_series, "批次 / patch 前")

print()
print("=" * 70)
print("  Step 2：套用 apply_yahoo_price_patches() 後")
print("=" * 70)
patched = apply_yahoo_price_patches(raw_norm, BATCH_TICKERS)
patched_series = get_clean_col(patched, TARGET, "Close")
flag_spikes(patched_series, "批次 / patch 後")

print()
print("=" * 70)
print("  對照組：單獨抓 1306.T 一檔（同樣套用 patch）")
print("=" * 70)
solo_raw = FETCHERS["common"]([TARGET], period="2y")
solo_norm = normalize_yfinance_columns(solo_raw)
solo_patched = apply_yahoo_price_patches(solo_norm, [TARGET])
solo_series = get_clean_col(solo_patched, TARGET, "Close")
flag_spikes(solo_series, "單獨 / patch 後")
