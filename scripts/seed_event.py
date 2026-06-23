# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-06-23"
EVENT_TAG = "stress_pullback"
EVENT_NAME = "連AI估值疑慮引爆亞股全面修正，KOSPI熔斷，台日同步承壓"
EVENT_NOTE = """\
  全球AI題材大漲後迎來系統性估值修正。
  美伊和談削弱地緣政治風險溢價，資金大舉
  撤離科技股，亞洲股市首當其衝。

  市場事件：
  - KOSPI -9.99%（觸發熔斷），SK海力士 -10%
  - NI225 -3.55%，鎧俠 -16%（2025年11月來最大單日跌幅）
  - TOPIX -2.56%
  - 台股 47,100 -640點（-1.34%），開高48,218走低
  - 台股融資餘額突破6000億（市場過熱警訊）
  - 標普500期貨 -0.8%，那指期貨 -1.3%
  - 美光財報即將公布（AI需求驗證關鍵）

  OHLC 收盤落點（15:14最終）：
  - 1655.T：daily(0.26)，乖離率 -0.42%（跌破月線）
  - 1306.T：daily(0.48)，量比 1.32，Pain Ratio → 0.12
  - 00988A：全日追價區 + 帶量下殺（量比1.60）
  - 0052.TW：追價區但Pain Ratio僅0.03，相對抗跌
  - 009821.TW：15.70（-1.60%），建倉首日水下

  Pain Ratio 異動（全日累計）：
  - 1306.T：0.00 → 0.12 ⬆️
  - 00988A：0.00 → 0.24 ⬆️（帶量下殺最值得警戒）
  - 00985A：0.07 → 0.22 ⬆️
  - 00981A：0.00 → 0.21 ⬆️
  - 整體風險：11.9 → 14.8（單日+2.9，仍屬保守）

  執行記錄：
  - 1655.T @867 × 200股（早盤掛單成交）
    持倉 3,200 → 3,400，均價 799.29 → 804.10
  - 1306.T @432 × 300股（追價區回落日常區觸發）
    持倉 4,900 → 5,200，均價 405.60 → 407.27
  - 009821.TW @15.96 × 2,000股（衛星倉建立）
  - JPY帳戶：5,637,839 → 5,331,309（-306,530 JPY）

stress_signal: 
  - KOSPI熔斷（極端市場訊號）
  - AI估值系統性修正（非個別事件）
  - 00988A帶量下殺
  - 台股融資過熱疊加外部利空

recovery_by_close: No

待觀察：
  - 美光財報（AI需求驗證，最關鍵催化劑）
  - 今晚美股對亞股修正的反應
  - 台股融資餘額是否開始快速去化
  - 日圓干預風險（財務大臣已與美方通話）
  - 1306.T 進一步下探回測區的可能性

備註：
  兩筆JPY加碼均為掛單觸發，成本合理。
  美光財報落地前暫停加碼，觀察為主。
  整體風險14.8，現金充裕（可投入約84萬TWD），
  若後續進入回測區仍有子彈可用。"""
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
