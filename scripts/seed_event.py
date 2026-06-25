# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-06-25"
EVENT_TAG = "orderly_pullback"
EVENT_NAME = "美光財報大幅超預期，台股「利多不漲」，籌碼消化中"
EVENT_NOTE = """\
  美光 FY2026 Q3 財報全面大幅超預期：
  - 營收 $414.56億（預期$356.31億，+16%）
  - EPS $25.11（預期$20.49，+22%）
  - 數據中心 $115.24億（預期$68.04億，+69%）
  - 毛利率 84.9%（預期81.83%）
  
  台指期財報後大漲 +1,778點（45,063→46,841），
  但台股開盤後未能延續漲勢，呈現「利多不漲」
  型態，全日震盪偏弱收盤。

  核心矛盾：
  - 美光數據中心 +69% 超預期（AI需求確認）
  - BofA預測Fed年內升息3次（估值壓制）
  兩者拉鋸，升息預期暫時壓過財報利多。

  OHLC 收盤落點（14:52）：
  - 1655.T：daily(0.36)，乖離率 +0.01% 守住月線
  - 1306.T：daily(0.61)，量比 1.38，結構穩定
  - 00985A：daily(0.41)，Pain Ratio 0.44 仍偏高
  - 00988A：追價區，Pain Ratio 0.20 ⬇️（改善最多）
  - 009821：-8.44% 累計跌幅，與AI修正連動

  Pain Ratio 三快照對比（09:40→10:35→14:52）：
  - 1655.T：0.07 → 0.07 → 0.05 ⬇️
  - 1306.T：0.09 → 0.09 → 0.09 持平
  - 00985A：0.33 → 0.50 → 0.44（盤中惡化後收斂）
  - 00988A：0.27 → 0.29 → 0.20 ⬇️（最大改善）
  - 整體風險：15.8 → 16.3 → 15.8（盤中高點後收斂）

  執行記錄（昨晚財報後決策，今日確認）：
  - 1655.T +300股，均價 804.10 → 810.00
    持倉 3,400 → 3,700
  - 1306.T +400股，均價 407.27 → 408.92
    持倉 5,200 → 5,600
  - JPY帳戶：5,331,309 → 4,896,077（-435,232 JPY）

stress_signal:
  - 00985A Pain Ratio 盤中觸及 0.50（需持續觀察）
  - 009821 累計 -8.44%（稀土衛星倉承壓）
  - 「利多不漲」型態確認短期籌碼偏弱

recovery_by_close: 部分
  - 1655.T 守住月線（乖離率回正）
  - 00988A Pain Ratio 從0.35大幅降至0.20

待觀察：
  - 00985A Pain Ratio 是否持續消化
    （目前0.44仍是全組合最高警戒值）
  - 美股今晚是否承接美光財報反彈
  - BofA升息預期 vs AI需求確認的拉鋸
    何時形成新的方向共識
  - 009821 稀土倉位：等地緣催化劑，
    短期承壓屬預期內，長期邏輯不變

備註：
  兩批加碼成本均在水上（1655.T 866.3 > 810.0，
  1306.T 425.9 > 408.92），結構健康。
  現金可投入：約64萬TWD + 37萬JPY，
  子彈仍充足，等市場方向明確再行動。"""
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
