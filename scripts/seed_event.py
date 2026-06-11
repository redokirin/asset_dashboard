# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-06-11"
EVENT_TAG = "stress_pullback"
EVENT_NAME = "PPI 公布日，1306.T 觸及狙擊區，1655.T 在回測區震盪"
EVENT_NOTE = """\
PPI 公布日，盤中波動明顯放大。

標的落點關鍵記錄：
- 1306.T 盤中最低觸及 sniper(0.00)，為本波調整首次碰到狙擊區，
  但收盤守回 pullback(0.73)，顯示狙擊區有承接買盤。
- 1655.T 開盤在 pullback(0.37)，盤中最高短暫觸及 daily(0.01)，
  收盤在 daily(0.01)，剛好守在日常區下緣，
  掛單 842 今日最低接近但未觸發。
- 00985A 盤中最低跌入 pullback(0.94)，收盤守回 daily(0.38)。
- 2330.TW 盤中最低觸及 pullback(0.99)，收盤守回 daily(0.43)。
- 1321.T 盤中最高觸及 chase，說明日股高點仍有追價警戒壓力。

執行記錄：
- 1655.T 842 × 300 掛單未成交，今日最低接近但未觸及。
- 今日無新成交。

Pain Ratio 觀察：
- 00985A 84%、00981A 77%、00988A 87%，台股主動型壓力持續。
- 1306.T、1655.T 維持低位（18% / 14%），日美指數型承壓但穩健。

市場分類：
維持 stress_pullback。
1306.T 觸及狙擊區是本波最重要的技術事件，
但單日觸及後快速修復，尚不構成參數調整的依據。
依壓力測試報告原則，觀察後續 3~5 個交易日是否持續下探。
六大關卡剩餘：6/16 日央、6/17 台指結算、6/18 FOMC、6/19 四巫日。"""
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
