# -*- coding: utf-8 -*-
"""
檢查 yfinance funds_data 底下有沒有「持股資料截止日期」這類 metadata。

用法：
  .venv/Scripts/python.exe scripts/inspect_holdings_metadata.py VOO
  .venv/Scripts/python.exe scripts/inspect_holdings_metadata.py 1655.T
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

import yfinance as yf


def main():
    ticker = sys.argv[1] if len(sys.argv) > 1 else "VOO"
    print(f"檢查 {ticker} 的 funds_data...\n")

    fd = yf.Ticker(ticker).funds_data
    if fd is None:
        print("查無 funds_data（可能不是 ETF/基金）")
        return

    print("=" * 70)
    print("  top_holdings")
    print("=" * 70)
    print(fd.top_holdings)
    print()
    print("  index.name:", fd.top_holdings.index.name)
    print("  columns:", list(fd.top_holdings.columns))
    print()

    print("=" * 70)
    print("  funds_data 底下所有可用屬性")
    print("=" * 70)
    attrs = [a for a in dir(fd) if not a.startswith("_")]
    print(attrs)
    print()

    for attr in ["fund_overview", "fund_operations", "asset_classes", "sector_weightings"]:
        print("=" * 70)
        print(f"  {attr}")
        print("=" * 70)
        try:
            value = getattr(fd, attr)
            print(value)
        except Exception as e:
            print(f"  取得失敗: {e}")
        print()


if __name__ == "__main__":
    main()
