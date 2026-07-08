# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-07-08"
EVENT_TAG = "pullback_zone_consolidation"
EVENT_NAME = "台股全天弱勢震盪收斂，00981A/00985A鎖定回測區，TISA月扣款到位"
EVENT_NOTE = """\
description:
  延續今早的量縮探底走勢，午後多數標的持續
  在回測區間震盪，2330午後翻紅至daily(0.92)
  逼近追價邊界，與台股整體弱勢形成分歧。

  00981A、00985A收盤雙雙落在回測加碼區：
  - 00981A：全天在daily(0.23)~pullback(0.98)
    間震盪，收盤定格pullback(0.98)，
    Pain Ratio 0.82→0.85，29.75（-0.10），
    目前回撤-7.8%
  - 00985A：早盤一度深探daily(0.05)~0.10，
    午後回升至pullback(0.68)，Pain Ratio
    0.76→0.78，21.52（-0.04），回撤-6.3%
  - 兩者皆連續第二個交易日停留在回測區，
    非單日雜訊

  00988A早盤一度觸及pullback(0.97)，尾盤
    收斂回daily(0.19)，量比升至1.14
    （今日最高），Pain Ratio維持100%
    上限不變，19.15（-0.50），回撤-19.3%

  1321.T持續破底：
  - 收69,640（-1,460），目前回撤擴大至
    -8.3%（本輪新低），Pain Ratio 31%→33%
  - 落點daily(0.21)，已接近日常波動帶下緣
    （68,758.94~71,823.25），距下緣約1.3%

  2330午後由弱轉強：
  - 收2,465（+15），翻紅，落點daily(0.92)，
    Pain Ratio降至6%（本輪最低），延續
    連日抗跌韌性，與台股大盤弱勢脫鉤

  1655.T、1306.T維持健康：
  - 1655.T：Pain Ratio僅1%，877.90（-1.50）
  - 1306.T：426.50（-5.50），Pain Ratio
    小幅升至9%，仍屬低檔

  野村台灣動力（0P00009PAQ）本月TISA定期
  定額已到位：
  - 單位數由81.39增至91.33（+9.94單位），
    總成本由16,000增至18,000（新增2,000，
    對應約14,000元扣款按當日淨值換算單位），
    落點轉為pullback(0.98)，Pain Ratio
    0.12→0.26——此為被動扣款自然入場，
    非主動決策

  區域配置目標已更新為台31/日31/美31/
  全球7，本次報告首次採用新目標：
  - 台股28.9%（缺口-2.1%）
  - 日股31.8%（超出+0.8%）
  - 美股32.1%（超出+1.1%）
  - 全球7.2%（超出+0.2%，已相當貼近）
  三者差距已明顯收斂，與新目標大致吻合

  整體風險係數20.9→20.8，持平於🟡中低區間，
  高風險標的佔比11.1%

stress_signal: 中度延續（00981A、00985A連兩日
  停留回測區，00988A盤中觸及但收斂，1321.T
  持續破底，但2330、1655.T、1306.T維持健康，
  分化格局延續未惡化）

recovery_by_close: 部分（2330午後翻紅，但
  00981A/00985A/1321.T收盤仍處弱勢或回測區）

待觀察：
  - 00981A、00985A連續兩日鎖定回測加碼區，
    是本月「除非有好機會」原則下持續觀察
    的候選名單，但兩者皆有短歷史標籤
    （12~13個月），Pain Ratio需保守解讀
  - 1321.T回撤持續擴大，距日常波動帶下緣
    僅約1.3%，留意是否觸及更深回測訊號
  - 2330連日抗跌且今日翻紅，若延續強勢，
    7/16法說會前的關注度可能提升
  - 00988A盤中觸及pullback後尾盤回升，
    量比升高但未轉為恐慌性賣壓，續觀察

備註：
  整體風險20.8，中低區間持平。今天最實質
  的變化是00981A、00985A確認連續第二天
  停留在回測加碼區，而非單日雜訊；同時
  TISA定期定額本月扣款已自動執行，被動
  補足台股配置，不受本月觀望決策影響。
  區域配置在新目標（31/31/31/7）下已相當
  接近，缺口大幅收斂。本月維持「除非有
  明確好機會不然不加碼」的立場，00981A/
  00985A雖觸及回測訊號，但仍需結合現金
  緩衝（14.4%）與訊號穩定性綜合判斷，
  非自動觸發進場。"""
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
