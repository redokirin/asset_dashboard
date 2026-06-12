# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-06-12"
EVENT_TAG = "orderly_pullback"
EVENT_NAME = "量縮反彈第二日，Pain Ratio 持續改善"
EVENT_NOTE = """\
SOX +7.91% 大反彈後的第二個交易日，
市場延續反彈但量能持續偏低。

全組合幾乎所有標的出現量縮上漲：
- 00985A 量比 0.42，0052 量比 0.46
- 1306.T 量比 1.42（今日組合中唯一量能正常標的）
- 00981A 量比 0.79，接近正常

Pain Ratio 持續改善：
- 00985A: 84% → 63%
- 00981A: 77% → 47%
- 00988A: 87% → 55%
- 台股主動型全面回到警戒門檻以下

1306.T 盤中觸及日常區最下緣（zone_position 0.00），
收盤守回 0.14，顯示日常區下緣有承接。
1655.T 收在 daily 0.30，日常區偏低位置穩定。

整體風險係數 15.4，維持本月低位。
量縮反彈的品質仍需觀察，
下週六大關卡（6/16 日央、6/18 FOMC）
才是真正的方向確認時機。"""
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
