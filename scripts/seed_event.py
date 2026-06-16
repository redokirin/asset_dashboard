# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-06-16"
EVENT_TAG = "orderly_pullback"
EVENT_NAME = "日央升息1%符合預期，利空出盡，日股收復跌幅"
EVENT_NOTE = """\
日本央行宣布升息至1.0%，符合市場預期。

市場反應符合「利空出盡」模式：
- 上午：日經在 69,400 附近整理（升息前觀望）
- 公布後：日經垂直噴升至 70,010（+1.11%）
- 70,000 整數關卡遇到賣壓，略作整理後收在69,400

1306.T 走勢：
- 今日小跌 -1.40（-0.3%），全日在 daily 0.70~0.91 之間
- 收盤 daily 0.77，未跌入回測區
- 升息壓制效果有限，午盤隨日經反彈守住日常區中段
- Pain Ratio 維持極低（1%）

1655.T 走勢：
- 穩步上漲 +2.60（+0.3%），收在 daily 0.92
- S&P 500 曝險標的持續受惠油價下跌和降息預期

整體狀況：
- 整體風險係數 12.6，六月最低
- 全組合 Pain Ratio 幾乎歸零
- 0052.TW、00988A、2330.TW 收在追價警戒
- 量縮上漲問題仍存在，00985A 量比 0.39

六大關卡進度：
✅ 6/10 CPI（符合預期）
✅ 6/11 PPI（高於預期，市場消化）
✅ 6/16 日央（升息1%，利空出盡）
⏳ 6/17 台指結算
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
