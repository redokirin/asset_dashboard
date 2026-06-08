# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-06-08"
EVENT_TAG = "orderly_pullback"
EVENT_NAME = "週五美股重挫後的週一亞洲市場回測"
EVENT_NOTE = """\
週五美股重挫後，週一亞洲市場未出現預期中的全面崩跌。
1655.T 落在 daily 中段，日常加碼有效。
1306.T 落在 pullback 上緣，回測加碼有效。
0052.TW 58.7 掛單未成交，台股科技開盤雖低但隨即反彈，
0052.TW 今日最低 57.9，低於掛單 58.7，
但因開盤觀望未成交，09:15 即 V 型反彈。
系統訊號正確，執行未跟上。
屬於人為判斷覆蓋系統的案例。

台日走勢出現明顯分歧：
台股開低走高，從開盤約 42,700 一路反彈至收盤 43,502（-3.48%），
收盤接近日內高點，買盤強勁，形態偏強。
日股尾盤急拉，1306.T 收 408.8（買入 407，+0.44%），
1655.T 收 855.9（買入 856，持平）。
兩檔均收在日內相對高點，日股走勢較早盤預期樂觀。
台日今日均屬 orderly_pullback，非 crash 事件。

本日應歸類為 orderly_pullback，而非 crash 或 sniper event。
台股的強勢收盤顯示今日賣壓已被充分吸收。
日股後續走勢需持續觀察 3~5 個交易日。"""
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
    conn.commit(); conn.close()
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
