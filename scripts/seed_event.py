# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-07-03"
EVENT_TAG = "correction_absorption"
EVENT_NAME = "台股補跌後止穩，00988A盤中觸及回測區完成消化，1321.T掛單擦身而過"
EVENT_NOTE = """\
description:
  延續早盤補跌走勢，午後多數標的收斂回穩，
  一週來的SOX大幅波動（週三-6.27%、週四回穩、
  週五-5.44%）在台股完成消化，未出現進一步惡化。

  OHLC全天走勢（09:28→15:11）：
  - 2330：全天在daily(0.63)~chase震盪，
    收盤daily(0.94)，逼近追價邊界，
    今日低點守住daily(0.63)未破
  - 0052：低點daily(0.54)，收盤回升至
    daily(0.88)，日內波段完整
  - 00985A：低點daily(0.16)，接近回測邊界
    但未觸及，收盤daily(0.62)
  - 00981A：全天在daily(0.60)~chase，
    收盤又回到chase
  - 1655.T：全天在daily(0.33)~0.46區間，
    相對疲弱但穩定，Pain Ratio維持2%健康
  - 1306.T：431.70（+6.00）逆勢走強，
    低點daily(0.43)、收盤daily(0.86)

  00988A今日出現關鍵訊號——盤中低點觸及
  pullback(0.95)，短暫進入回測加碼區邊緣，
  隨後收斂至daily(0.68)：
  - Pain Ratio持續惡化 0.56→0.71（連續第三天上升），目前回撤-10.1%
  - 診斷標籤「🔴破線轉弱」延續，但AI建議未再提及帶量下殺或恐慌賣壓字眼，量比1.16屬正常範圍
  - ⚠️歷史僅8個月，Pain Ratio解讀需保守，但連續惡化趨勢值得持續觀察

  009821（衛星倉）Pain Ratio 0.98→0.93，
    小幅回穩，收盤14.41（+0.19），
    但仍列sniper(0.00)最低檔，不列入加碼考量

  整體風險係數17.0→16.0，回落至保守區間，
  高風險標的佔比維持4.8%（僅00988A）

stress_signal: 輕度趨緩（00988A仍是唯一持續惡化
  標的，但盤中觸及回測區後收斂，未進一步失控；
  其餘主流標的皆止穩或轉強）

recovery_by_close: Yes（多數標的午後收斂回升，
  2330、0052、1306.T皆收在較高位置）

待觀察：
  - 1321.T日常波動帶已上移至68,758.94~
    71,823.25，今日盤中在71,500附近，
    試掛71,000×10股屬日常區偏低位置，
    僅一步之差未成交即反彈走高——
    系統先前記錄的回測區評估（約
    68,000~69,000）已隨行情上移，
    下次掛單需以最新波動帶為準，
    而非舊有回測區間
  - 00988A連續三日Pain Ratio惡化且今日
    短暫觸及回測區，若後續持續探底，
    可能是本輪唯一提供加碼機會的標的，
    但需持續留意8個月短歷史對數字的失真效應
  - 2330收在daily(0.94)逼近chase邊界，
    若明日續漲有機會重新進入追價區

備註：
  這週最終以「觀望」收尾，今日僅有的操作是
  1321.T試掛未成交，沒有實際加碼。整體風險
  16.0，保守區，現金部位17.7%維持穩定。
  一週的雙巴震盪（SOX -6.27%→反彈→-5.44%→
  今日止穩）大致驗證了左側交易「不追價、
  等待確認」的邏輯——這週選擇觀望而非追進
  中途的每一次反彈或急殺，避免了在雜訊中
  頻繁進出。00988A是唯一還在惡化的標的，
  下週如果持續探底、真正跌破回測邊界，
  會是相對明確的進場訊號。"""
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
