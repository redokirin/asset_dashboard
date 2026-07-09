# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-07-09"
EVENT_TAG = "pullback_zone_close_confirmed"
EVENT_NAME = (
    "00981A收盤鎖定深度回測區，1306.T全天在pullback區拉鋸，野村中小基金完成新一輪加碼"
)
EVENT_NOTE = """\
description:
  收盤數據顯示，今天美伊地緣風險延續影響，台日股呈現分化格局，00981A、1306.T兩檔收盤前都明確落在回測加碼區，00985A則接近邊緣。

  00981A收盤確認深度回測：
  - 全天在pullback(0.87)~daily(0.62)間震盪，收盤定格pullback(0.99)——幾乎貼齊狙擊邊界，是今天執行狀態最深的標的
  - Pain Ratio 78%，29.95（+0.23）小幅翻紅
  - 這是連續第三個交易日觸及或深陷回測區

  1306.T全天在回測區拉鋸：
  - 開盤pullback(0.86)、盤中一度回升至daily(0.02)，尾盤又壓回pullback(0.85)
  - 收419.10（-7.90），Pain Ratio 16%，目前回撤擴大至-3.7%
  - 核心持倉（24.4%佔比）連續第二天收在回測區，並非單日雜訊

  00985A同樣落在回測區：
  - 收盤pullback(0.69)，Pain Ratio 69%（較早盤09:25的73%略降），21.69（+0.18）

  00988A盤中一度觸及chase，尾盤收斂：
  - 開盤daily(0.66)、最高触及chase、最低pullback(0.98)，收盤daily(0.21)
  - Pain Ratio維持100%不變，19.17（+0.02）

  1321.T、2330相對平穩：
  - 1321.T：70,280（+660），daily(0.50)，
    Pain Ratio 26%，仍與1306.T走勢分歧
  - 2330：2,415（-35），daily(0.38)，
    Pain Ratio 12%，尾盤翻黑但幅度不大

  野村中小基金（0P00006AKV）今日出現加碼：
  - 單位數由279.08增至292.02（+12.94單位），
    總成本由59,590增至66,790（新增約7,200），
    561.39（+5.02），Pain Ratio 25%→23%
  - 此為儲蓄險附加的定期性投入，非本月主動決策範圍

  整體風險係數20.6→20.9，維持🟡中低區間，高風險標的佔比6.3%（較早盤11.2%已回落）

stress_signal: 中度延續（00981A、1306.T、00985A三檔同時收在回測區內，00988A/009821持續在Pain Ratio上限，但2330/1655.T維持健康，分化格局未變）

recovery_by_close: 部分（1655.T、00981A、00985A、1321.T皆翻紅，但1306.T、2330尾盤走弱，00988A維持底部盤整）

待觀察：
  - 00981A連續第三天觸及或深陷pullback區，是本輪修正以來訊號最持續、最明確的標的之一
  - 1306.T作為核心持倉，今天全天在回測區拉鋸而非單向下跌，顯示這個價位帶存在真實的買賣拉鋸，非單純破底
  - 美伊局勢後續發展、油價走勢仍是影響1306.T的關鍵變數，需持續留意
備註：
  整體風險20.9，中低區間微幅上升，高風險標的佔比較早盤明顯回落至6.3%。
  今天最值得留意的是00981A連續第三天收在深度回測區，以及1306.T這個核心持倉全天在pullback區間反覆拉鋸——顯示這個位置已經有實質的買盤承接，而非單邊破位。
  本月「除非有好機會不然不加碼」原則下，這兩檔的訊號持續性已經比單日雜訊更值得留意，但美伊地緣風險尚未落幕，加上現金緩衝僅14.3%，是否進場仍建議謹慎評估。"""
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
