# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-06-10"
EVENT_TAG = "stress_pullback"
EVENT_NAME = "六月連續三次美股下跌後的台日市場回測"
EVENT_NOTE = """\
六月以來美股第三次下跌（6/05、6/09週五、6/10），
本次與 6/08 的 orderly_pullback 性質不同：
台股今日持續性下跌，無 V 型反彈，
指數收盤 -2.32%，跌勢形態偏弱。

標的落點：
- 1306.T 跌入回測區（pullback 0.60），收盤未修復（pullback 0.83），
  為本週首次跌入回測區並收盤於回測區。
- 1655.T 收在 daily(0.22)，日常區低位。
- 0052.TW 收在 daily(0.59)，日常區底部。
- 00985A / 00981A Pain Ratio 再度跳升至 76% / 71%。
- 00988A Pain Ratio 達 88%，帶量下殺，跌深反彈區。

執行記錄：
- 0052.TW 58.8 × 1,000 股成交（日常區底部）
- 1306.T 409 × 300 單位成交（回測區加碼）
- 兩筆均為系統訊號觸發，非人工主動追價。

市場分類：
本日升級為 stress_pullback。
六月已連續四次下跌，台股韌性弱化，
日股跌入回測區，需持續觀察 3~5 個交易日確認是否修復。"""
IS_PRESSURE = 1

import sqlite3
from pathlib import Path as P

DB = P(__file__).parent.parent / "db" / "portfolio.db"


def _already_seeded():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    exists = conn.execute(
        "SELECT 1 FROM market_events WHERE event_date=? AND event_tag=?",
        (EVENT_DATE, EVENT_TAG),
    ).fetchone()
    conn.close()
    return exists is not None


init_db()

if _already_seeded():
    conn = sqlite3.connect(DB)
    conn.execute(
        """UPDATE market_events SET event_name=?, event_note=?, is_pressure_test=?
           WHERE event_date=? AND event_tag=?""",
        (EVENT_NAME, EVENT_NOTE, IS_PRESSURE, EVENT_DATE, EVENT_TAG),
    )
    conn.commit()
    conn.close()
    print(f"market_events 已更新 {EVENT_DATE}/{EVENT_TAG}")
else:
    eid = add_market_event(
        event_date=EVENT_DATE,
        event_tag=EVENT_TAG,
        event_name=EVENT_NAME,
        event_note=EVENT_NOTE,
        is_pressure_test=IS_PRESSURE,
    )
    print(f"market_events 新增成功，id={eid}")

ok = update_report_run_event(
    report_date=EVENT_DATE,
    market_event_tag=EVENT_TAG,
    market_event_note=EVENT_NOTE,
    is_pressure_test=IS_PRESSURE,
    parameter_version="v2026_06_08",
)
print(f"report_runs 更新：{'成功' if ok else '無對應記錄，跳過'}")
