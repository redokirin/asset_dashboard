# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-06-17"
EVENT_TAG = "orderly_pullback"
EVENT_NAME = "台指結算日 — SOX -5.71% 利空消化，市場韌性確認"
EVENT_NOTE = """\
  昨夜美股 SOX -5.71%、TSM ADR -3.53%，
  市場預期結算日大跌，但實際走勢顯著優於預期。
  台股開盤跌幅有限，日盤反彈收復，多數標的收盤
  高於開盤，Pain Ratio 全面下降。

  關鍵數據變化（09:25 → 14:16）：
  - 0052.TW：61.35(-0.81%) → 62.15(+0.48%) 完整反轉
  - 2330.TW：2365(-1.46%) → 2385(-0.63%) 縮小跌幅
  - 00985A Pain Ratio：0.38 → 0.23
  - 00981A Pain Ratio：0.26 → 0.15
  - 整體風險分數：12.8 → 12.3

  OHLC 觀察：
  - 0052.TW 日內最高觸及追價區，收 daily(0.95) 極強
  - 1306.T 日內最高觸及追價區，收 daily(0.90)
  - 2330.TW 日內最高觸及 daily(0.98)，接近日常區頂
  - 00988A 全日停留追價警戒區（唯一異常標的）

六大關卡進度：
✅ 6/10 CPI（符合預期）
✅ 6/11 PPI（高於預期，市場消化）
✅ 6/16 日央（升息1%，利空出盡）
✅ 6/17 台指結算
⏳ 6/18 FOMC
⏳ 6/19 四巫日"""
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
