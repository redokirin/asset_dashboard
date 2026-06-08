# -*- coding: utf-8 -*-
"""
補錄 2026-06-08 0052.TW missed execution 記錄。
需在 update_ohlc_zones.py 之後執行（確保 low_price 已填入）。
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import init_db, update_execution_status

init_db()

result = update_execution_status(
    report_date="2026-06-08",
    ticker="0052.TW",
    planned_order_price=58.7,
    actual_filled=False,
)

print(f"0052.TW 執行狀態：{result.get('status')}")
if result.get("note"):
    print(f"執行說明：{result.get('note')}")
if not result:
    print("無記錄，請先執行分析報告與 update_ohlc_zones。")
