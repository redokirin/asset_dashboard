# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-07-02"
EVENT_TAG = "delayed_correction_partial_fill"
EVENT_NAME = "美股跌幅遞延反映，00988A帶量下殺轉弱，台股完成兩筆回測加碼"
EVENT_NOTE = """\
隔夜SOX -6.27%、TSM ADR -6.98%的跌幅並未在
  台股一次性反映，而是分兩日消化：09:38時
  2330僅小跌，午後才補跌至2,465（-25），
  但全天仍卡在chase區（低點僅觸daily(0.98)
  又彈回），台積電本身尚未真正回落。

  執行紀錄（今日完成兩筆回測加碼）：
  - 1306.T：加碼300股，成本墊高至410.11
    （原408.92），對應盤中低點daily(0.39)，
    落在日常區偏低位置
  - 00988A：加碼2,000股@約21.71，成本從
    19.13墊高至19.99，對應今日低點daily(0.62)

  00988A轉弱是今天最大風險訊號：
  - 量比飆高至1.56，診斷標籤新增
    「🔻帶量下殺」，AI建議明確標註
    「😱帶量下殺，反映恐慌性賣壓持續湧現」
  - Pain Ratio 0.28 → 0.56（單日+0.28，
    盤中最高見0.60），目前回撤已達-8.0%
  - ⚠️歷史僅8個月，MDD基準淺，數字需搭配
    短歷史標籤謹慎解讀，但帶量下殺是量能面
    訊號，與歷史長度無關，不可忽視

  其餘標的：
  - 0052、00981A：全天多數時間在chase，
    僅開盤短暫觸及daily區，未見回測機會
  - 00985A：早盤一度探至daily(0.14)，
    非常接近回測邊界，但未跌破，收盤回升至
    daily(0.62)，未觸發加碼
  - 1655.T：874.20（-3.00），全天在daily
    區緩步走弱（0.75→0.52），Pain Ratio
    仍僅2%，健康度無虞
  - 1306.T：426.40（+1.30），逆勢翻紅，
    盤中因跌深觸及回測區完成加碼後回彈

stress_signal: 輕度局部（00988A單一標的帶量下殺，
  其餘標的量能與Pain Ratio均在正常區間）

recovery_by_close: 部分（2330/0052/00981A收盤仍在chase，
  未見補跌到位；00988A則是唯一惡化中的標的）

待觀察：
  - 00988A帶量下殺是否延續至明日，或如09:38
    診斷所示進入「量縮止跌」——量比從0.43
    急升到1.56需持續追蹤，是判斷恐慌是否
    擴散的關鍵指標
  - 2330全天守住chase未真正補跌，若明日
    SOX/TSM ADR持續弱勢，台積電補跌空間仍在，
    留意能否終於進入日常區
  - 00985A早盤daily(0.14)已非常接近回測邊界，
    下次若再探低有機會觸發加碼
  - 1306.T加碼後成本已墊高，留意日股後續是否
    跟跌，避免連續在同一水位加碼

備註：
  整體風險15.6→16.3，仍在保守區，高風險標的
  佔比0.0%，現金部位由19.8%降至17.7%（今日
  兩筆加碼消耗現金所致）。今天呈現「美股跌幅
  分批遲滯反映」的特徵——多數台股標的仍守在
  chase/daily上緣，真正的回測壓力尚未完全釋放，
  唯獨00988A因短歷史+高波動特性率先出現帶量
  下殺，是本輪修正中第一個需要密切關注的個別
  風險點，而非全市場性訊號。"""
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
