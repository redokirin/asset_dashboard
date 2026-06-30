# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-06-29"
EVENT_TAG = "orderly_pullback"
EVENT_NAME = "台股被壓在44999.90，Pain Ratio全面下降，台積電連兩日反彈"
EVENT_NOTE = """\
description:
  台股加權指數收 44,999.90，差0.10點
  守不住45,000，疑似空方刻意壓盤維持
  技術面弱勢格局。

  台積電籌碼觀察：
  - 收盤集合競價 8,788張 綠色（賣單）
  - 但股價從2,330開盤漲至2,370收盤（+40）
  - 賣壓仍在，但買盤更強，完全吃掉賣壓

  Pain Ratio 全面下降（第二日）：
  - 00985A：0.93 → 0.88 ⬇️
  - 00981A：0.79 → 0.78 ⬇️
  - 0052：0.23 → 0.19 ⬇️
  - 1655.T：0.10 → 0.07 ⬇️
  - 2330：0.22 → 0.18 ⬇️

  OHLC 關鍵落點：
  - 00985A：開盤 pullback(0.90)，收 daily(0.07)
    日內完整V型反彈
  - 1655.T：低點 daily(0.02)，收 daily(0.17)
  - 1306.T：低點 daily(0.08)，收 daily(0.28)
  - 2330：開盤 daily(0.03)，收 daily(0.46)

  掛單結果：
  - 1655.T @851 × 400股：未成交（低點未達）
  - 1306.T @414 × 600股：未成交（低點未達）

stress_signal: None（方向轉好）
recovery_by_close: 部分

待觀察：
  - 45,000 能否明日收復
  - 台積電尾盤賣單是否持續縮量
  - 1655.T/1306.T 掛單明日繼續
  - 0052 Pain Ratio 接近0.10時考慮進場"""
IS_PRESSURE = 0

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
