# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-06-18"
EVENT_TAG = "recovery"
EVENT_NAME = "FOMC鷹派完全消化，台股連假前收強"
EVENT_NOTE = """\
  昨夜 FOMC Warsh 鷹派訊號（通膨預期上修至3.6%、
  年底降息渺茫），市場預期今日台股承壓。
  實際走勢完全相反，台股加權指數盤中觸及 46,440。

  注意：美股四巫日為今晚（美東6/19），
  台股需連假後 6/23 才反映，日股明日（6/19）先反映。
  目前台股收盤數據不含四巫日軋倉結果。

  OHLC 收盤落點（14:01）：
  - 0052.TW：全日維持追價區
  - 00981A：開盤日常區，收盤升入追價區
  - 1306.T：全日追價區，量比回升至 0.94
  - 2330.TW：開盤 daily(0.98)，收盤追價區
  - 1655.T：日常區 daily(0.57)，為唯一可執行標的
  - 00988A：追價警戒第四天

  Pain Ratio 全面淨化：
  - 00985A：0.23 → 0.07
  - 00981A：0.15 → 0.00（完全清零）
  - 00988A：0.05 → 0.00（完全清零）
  - 整體風險分數：12.2 🟢（六月壓力測試以來最低）

  執行記錄：
  - 1655.T @867 × 200股（掛單成交）
  - 持倉 3,000 → 3,200，均價 799.29

六大關卡進度：
✅ 6/10 CPI（符合預期）
✅ 6/11 PPI（高於預期，市場消化）
✅ 6/16 日央（升息1%，利空出盡）
✅ 6/17 台指結算
✅ 6/18 FOMC
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
