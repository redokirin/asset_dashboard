# -*- coding: utf-8 -*-
"""
Portfolio X-Ray 終端機版。

用法：
  .venv/Scripts/python.exe scripts/x-ray.py
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.xray import analyze_portfolio_exposures


def _pct(v: float) -> str:
    return f"{v * 100:6.2f}%"


def _progress(ticker: str, pw: float, msg: str) -> None:
    print(f"  [{ticker:<14}]  {_pct(pw)}  {msg}", flush=True)


def main():
    print("\n分析中，請稍候…\n")

    result = analyze_portfolio_exposures(on_ticker=_progress)

    if result["total_value_twd"] == 0:
        print("無法取得市值資料，請確認 Google Sheets value 欄位。")
        return

    total      = result["total_value_twd"]
    count      = result["assets_count"]
    exposures  = result["exposures"]
    buckets    = result["buckets"]
    sectors    = result["sector_exposures"]
    identified = result["identified_pct"]
    unresolved = result["unidentified_pct"]
    top_n      = min(30, len(exposures))

    print()
    print("=" * 70)
    print("  投資組合 X-Ray")
    print("=" * 70)
    print(f"  分析標的：{count} 支   總市值：{total:>12,.0f} TWD")
    print("=" * 70)
    print()
    print("=" * 70)
    print(f"  已識別個股曝險 Top {top_n}")
    print("=" * 70)
    print(f"  {'#':<3}  {'代碼':<14}  {'名稱':<36}  {'曝險':>7}  {'來源'}")
    print(f"  {'-'*3}  {'-'*14}  {'-'*36}  {'-'*7}  {'-'*22}")

    for i, exp in enumerate(exposures[:30], 1):
        name    = exp["name"][:34]
        sources = " + ".join(exp["sources"])
        print(f"  {i:<3}  {exp['symbol']:<14}  {name:<36}  {_pct(exp['weight'])}  {sources}")

    if buckets:
        print()
        print("=" * 70)
        print("  未解析桶")
        print("=" * 70)
        for b in buckets:
            print(f"  {b['label']:<54}  {_pct(b['weight'])}")

    if sectors:
        print()
        print("=" * 70)
        print("  產業配置")
        print("=" * 70)
        for s in sectors:
            print(f"  {s['sector']:<54}  {_pct(s['weight'])}")

    print()
    print("=" * 70)
    print(
        f"  已識別  {_pct(identified)}"
        f"  │  未解析  {_pct(unresolved)}"
        f"  │  合計  {_pct(identified + unresolved)}"
    )
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
