# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-06-24"
EVENT_TAG = "stress_pullback"
EVENT_NAME = "AI估值修正第二日，大盤觸底45903後反彈，美光財報待驗證"
EVENT_NOTE = """\
  延續6/23亞股全面修正，台股開盤承壓，
  盤中一度跌破46,000整數關卡至45,903（-1,197點），
  觸底後買盤承接，尾盤反彈收46,216（-884點，-1.88%）。
  整體呈現「跌破整數關卡→快速拉回」假跌破形態。

  市場背景：
  - BofA預測Fed年內升息3次（主要催化劑）
  - AI估值疑慮持續發酵（連續第二日）
  - 韓國槓桿ETF管控消息放大昨日跌幅
  - 台股融資餘額破6000億，槓桿籌碼去化中
  - 美光財報今晚美東時間公布（最關鍵催化劑）

  OHLC 關鍵落點（14:41收盤）：
  - 1655.T：日內最低 daily(0.11)，收 daily(0.19)
    乖離率 -0.54%，跌破月線但未進回測區
  - 1306.T：日內最低 daily(0.12)，收 daily(0.33)
    盤中觸及回測區邊緣後拉回，量比1.48偏高
  - 2330.TW：從追價區大幅回落至 daily(0.69)
    帶量下殺（量比1.89），-100元單日大跌
  - 00988A：全日追價區，帶量下殺持續

  Pain Ratio 盤中高點 vs 收盤：
  - 00985A：0.52（早盤）→ 0.41（收盤）⬇️
  - 00981A：0.46（早盤）→ 0.25（收盤）⬇️
  - 00988A：0.44（早盤）→ 0.35（收盤）⬇️
  - 1655.T：0.08 → 0.07 持平
  - 1306.T：0.12 → 0.13 微升

  整體風險：16.1 → 15.7（盤中高點後回落）

  執行記錄：無（觀望，等美光財報）

stress_signal:
  - 1306.T 盤中觸及回測區邊緣（daily 0.12）
  - 2330.TW 帶量下殺 -100元
  - 00988A 帶量下殺第二日
  - 台股融資去化持續中

recovery_by_close: 部分
  - 大盤從45,903反彈收46,216，守住關鍵支撐
  - 多數標的 Pain Ratio 從早盤高點回落
  - 00981A 尾盤強力反彈 daily(0.55)→daily(0.91)

待觀察：
  - 今晚美光財報（台灣週四凌晨4-5點）
  - 美光好 → 明日日股/台股反彈，1306.T/1655.T
    回到日常區中段，觀察是否形成retest確認
  - 美光差 → 1655.T/1306.T 正式進入回測區，
    屆時考慮第二批加碼
  - 台股融資餘額是否持續下降（去槓桿進度）

備註：
  今日觀望決策正確。
  現金可投入：約84萬TWD + 45萬JPY，子彈充足。
  兩筆JPY持倉（1655.T @804.10、1306.T @407.27）
  均為左側第一批，等回測區確認再考慮第二批。"""
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
