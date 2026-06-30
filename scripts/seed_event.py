# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-06-30"
EVENT_TAG = "recovery"
EVENT_NAME = "季底反彈確認，台股+2.50%收46,125，Pain Ratio大幅修復，本輪壓力測試收尾"
EVENT_NOTE = """\
description:
  美股三日連續反彈（SOX三天+1.57%→+3.83%→
  續強，TSM ADR三日累計+10%+）效應完整
  反映到台股，加權指數收46,125.91（+1,126，
  +2.50%）。

  台積電籌碼面：
  - 收盤集合競價18,704張（季度調整大量，
    非單純買賣方角力）
  - 6/30為MSCI季度再平衡日，技術性事件
  - 大盤仍強勢收漲，賣壓被輕鬆吸收
  - 2330收2,410（+35），daily(0.73)

  OHLC 收盤落點（14:37）：
  - 0052：daily(0.89)，量比0.68（量能不足警示）
  - 00988A：daily(0.95)，接近追價區
  - 00981A：daily(0.81)
  - 00985A：daily(0.33)，相對保守
  - 1655.T：daily(0.50)，乖離率轉正+0.84%
  - 1306.T：daily(0.44)
  - 2330：daily(0.73)，季調賣壓後收復

  Pain Ratio 全面大幅修復：
  - 00985A：0.88 → 0.48（單日-0.40，最大改善）
  - 00981A：0.78 → 0.32（單日-0.46，本輪最大改善）
  - 00988A：0.67 → 0.43
  - 0052：0.19 → 0.09
  - 整體風險：18.2 → 16.4（本輪最低）

  本輪壓力測試總結（6/23-6/30）：
  - 起點：台股47,100 → 最低44,571（-5.4%）
  - 終點：台股回升至46,125（距起點僅-2.1%）
  - 觸發因子：AI估值修正+BofA升息預測+
    韓國槓桿ETF爆雷+KOSPI熔斷
  - 轉折訊號：美光財報大超預期+台積電
    籌碼由賣轉買+VOO進入狙擊區
  - 掛單結果：1655.T@851/1306.T@414
    全程未成交（最低點分別為pullback(0.48)
    和pullback(1.00)，僅觸邊界未深入）

stress_signal: None（壓力測試已收尾）

recovery_by_close: Yes

待觀察：
  - 多檔標的量能不足，反彈動能是否能延續
    或進入橫盤整理
  - 下次回測機會：等待量縮反彈後的自然回落
  - 0052/00985A/00981A 錯過本輪最佳進場窗口，
    等下一次真正回測再評估
  - 1655.T/1306.T 掛單因應反彈確認，
    暫停掛單，等新的回測區形成

備註：
  本輪壓力測試完整驗證系統設計：
  Pain Ratio從歷史高位（0.93/0.79）快速
  消化至中位數（0.48/0.32），驗證了
  「左側交易，等待而非追漲」的核心邏輯。
  現金仍充裕（約65萬TWD+37萬JPY），
  子彈留待下次真正的回測機會。"""
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
