# -*- coding: utf-8 -*-
"""
查詢單一 ETF/基金前十大持股。

用法：
  .venv/Scripts/python.exe scripts/holdings.py VOO
  .venv/Scripts/python.exe scripts/holdings.py 1655.T
  .venv/Scripts/python.exe scripts/holdings.py          # 互動輸入
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.xray import get_ticker_holdings


def main():
    if len(sys.argv) > 1:
        ticker = sys.argv[1].strip().upper()
    else:
        ticker = input("輸入代碼（如 VOO、1655.T）：").strip().upper()

    if not ticker:
        print("未輸入代碼")
        return

    print(f"\n查詢 {ticker} 前十大持股…\n")
    holdings = get_ticker_holdings(ticker)

    if not holdings:
        print(f"  找不到 {ticker} 的持股資料（可能是個股或 yfinance 不支援）\n")
        return

    print(f"  {'#':<3}  {'代碼':<14}  {'名稱':<40}  {'比重':>7}")
    print(f"  {'-'*3}  {'-'*14}  {'-'*40}  {'-'*7}")
    for i, h in enumerate(holdings, 1):
        name = h["name"][:38]
        print(f"  {i:<3}  {h['symbol']:<14}  {name:<40}  {h['weight'] * 100:6.2f}%")
    print()


if __name__ == "__main__":
    main()
