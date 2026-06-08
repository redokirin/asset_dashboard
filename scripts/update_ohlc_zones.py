# -*- coding: utf-8 -*-
"""
收盤後補齊指定日期的 open/high/low 區間位置。

用法：
  .venv/Scripts/python.exe scripts/update_ohlc_zones.py --date 2026-06-08
  .venv/Scripts/python.exe scripts/update_ohlc_zones.py            # 預設今日
"""
import argparse
import os
import sys
from datetime import date
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import update_ohlc_zones


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=str(date.today()), help="日期 YYYY-MM-DD")
    args = parser.parse_args()

    print(f"正在補齊 {args.date} 的 OHLC 區間位置...")
    rows = update_ohlc_zones(args.date)

    if not rows:
        print("無資料或全部失敗，請確認當日有執行過分析報告。")
        return

    def fp(v):
        return f"{v:.4f}" if v is not None else "  -  "

    header = (
        f"{'ticker':<14}"
        f" {'open_z':<10} {'o_pos':<7}"
        f" {'low_z':<10} {'l_pos':<7}"
        f" {'close_z':<10} {'c_pos':<7}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['ticker']:<14}"
            f" {(r['open_zone']  or 'NULL'):<10} {fp(r['open_position']):<7}"
            f" {(r['low_zone']   or 'NULL'):<10} {fp(r['low_position']):<7}"
            f" {(r['close_zone'] or 'NULL'):<10} {fp(r['close_position']):<7}"
        )

    filled = sum(1 for r in rows if r.get("open_zone"))
    print(f"\n完成：{filled}/{len(rows)} 筆成功補齊 OHLC zone。")


if __name__ == "__main__":
    main()
