# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-07-01"
EVENT_TAG = "recovery_extension"
EVENT_NAME = "季底反彈延續，多數標的推離可執行區間"
EVENT_NOTE = """\
description:
  七月開門紅，台股延續季底反彈動能全面續漲，
  主動式ETF Pain Ratio大幅修復，多數標的
  被推離可執行區間。

  台積電籌碼面：
  - 收盤2,505（+55），RSI 70.4達過熱臨界
  - 全天OHLC四價均在追價警戒區
  - Pain Ratio 0.13 → 0.01，接近歸零

  OHLC 收盤落點（14:38）：
  - 0052：chase（全天四價追價警戒），量比0.63（量價背離）
  - 00988A：chase（全天四價追價警戒）
  - 00981A：chase（日內低點曾觸daily(0.95)）
  - 00985A：daily(0.58)，日常區中段，唯一台股可執行標的
  - 1655.T：daily(0.68)，日常區中段
  - 1306.T：daily(0.53)，盤中chase收盤滑回日常區
  - 2330：chase（全天四價追價警戒）

  Pain Ratio 全線下降：
  - 00981A：0.32 → 0.08（單日-0.24，修復最快）
  - 00985A：0.48 → 0.31（單日-0.17）
  - 00988A：0.43 → 0.28（單日-0.15）
  - 野村中小：0.22 → 0.13
  - 統一台灣動力：0.21 → 0.11
  - 1655.T：0.03 → 0.00（完全修復）
  - 整體風險：16.4 → 15.2（保守區，本輪最低）

  量價品質：
  - 0052、野村中小、統一台灣動力偵測到
    價漲量縮（量價背離），反彈缺乏量能確認
  - 1306.T 量比0.49（量能偏低）
  - 00985A 量比0.72（尚可）

stress_signal: None（壓力測試6/30已收尾）

recovery_by_close: Yes

待觀察：
  - 0052/00981A/00988A/2330全天chase，
    短期無可執行價位，等技術性回吐
  - 量價背離持續擴大（三檔台股標的），
    反彈可能進入橫盤消化或小幅回落
  - 可執行標的僅剩1655.T（daily 0.68）和
    00985A（daily 0.58），但複委託當日有效
    需隔日重新掛單
  - 1306.T收盤滑回daily(0.53)，若日股
    明日開盤回落可觀察
  - 009821（稀土）報酬-10.94%、風險分數0.90，
    衛星倉持有觀察，不加碼

備註：
  整體風險15.2（保守區），高風險標的佔比0.0%。
  現金充裕（TWD可投約27.9萬+JPY可投約36.7萬），
  子彈留待下次回測。六月壓力測試完整通過後，
  組合進入「等回測」狀態——多檔主動式ETF
  Pain Ratio雖快速修復但已推入追價警戒區，
  不宜追進，等待量縮反彈後的自然回落形成
  新的進場窗口。"""
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
