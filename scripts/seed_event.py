# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-06-26"
EVENT_TAG = "stress_pullback"
EVENT_NAME = (
    "亞股第二波重挫，台股跌破45,000，主動式Pain Ratio爆表，台積電收盤現5701張大買單"
)
EVENT_NOTE = """\
description:
  AI估值修正延續第四日，本週累計台股
  從47,100跌至44,571（-5.4%）。
  台股全產業翻綠含金融股，確認全面性
  去風險而非結構性輪動。

  市場事件：
  - 台股收 44,571（-1,683點，-3.64%）
  - 台股跌破 45,000 整數關卡，未能收復
  - 日經225 跌近5%（約-4,000點）
  - 本週累計：台股 -5.4%、日股 -5%+
  - 全產業翻綠含金融股（系統性去風險確認）
  - 納指盤中閃崩 -1.58%（程式單連環觸發）

  台積電籌碼重大轉折：
  - 6/23~6/25：連四天尾盤 8,000~13,000張大賣單
  - 6/26 今日：收盤集合競價 5,701張 @2,340 大買單
  - 方向由賣轉買，籌碼止穩訊號出現 🔄

  OHLC 收盤落點（15:02）：
  - 1655.T：pullback(0.73)，低點 pullback(0.48)
    正式確立在回測區，乖離率 -1.25%
  - 1306.T：daily(0.23)，低點 pullback(1.00)
    觸及回測區邊緣後彈回
  - 00985A：日內低點 pullback(0.73)，收 daily(0.09)
    Pain Ratio 0.93（回撤 -7.5% vs MDD -8.1%）
    ⚠️ 幾乎創歷史新低，歷史僅12個月樣本不足
  - 00981A：Pain Ratio 0.79，觸發高風險警示
  - 0052：daily(0.50)，Pain Ratio 0.23，相對乾淨
  - 00988A：帶量下殺，Pain Ratio 0.53

  Pain Ratio 關鍵分析：
  - 主動式高 Pain Ratio 部分為統計假象
    （歷史短、MDD樣本不足）
  - 00985A 跌幅與 0052 相近（約-7%），
    但因台積電佔比僅25%，主動選股的
    中小型科技跌更重，反而比0052（62%台積）更傷
  - 整體風險：18.3（本輪最高，仍保守區）
  - 高風險標的佔比首次觸發（6.5%）

  掛單結果：
  - 1655.T @851 × 400股：未成交
    （低點約 pullback(0.48)，未觸及851）
  - 1306.T @414 × 600股：未成交
    （低點 pullback(1.00)，剛觸邊界未深入）
  - 複委託當日有效，收盤自動取消

stress_signal:
  - 台股跌破45,000收盤（未守住）
  - 00985A Pain Ratio 0.93（歷史極值）
  - 00981A Pain Ratio 0.79（高風險警示觸發）
  - 全產業翻綠（系統性去風險）
  - 納指盤中閃崩（程式單連環觸發）

recovery_by_close: No

籌碼止穩訊號：
  台積電收盤集合競價 5,701張 @2,340
  連四天大賣單後首次出現大買單，
  為本輪最明確的籌碼轉折訊號。
  下週是否延續決定 0052 進場時機。

待觀察（下週）：
  - 台積電尾盤買單是否持續（最關鍵訊號）
  - 45,000 能否重新收復
  - 00985A/00981A Pain Ratio 開始下降
    才考慮主動式進場
  - 0052 Pain Ratio 0.23 相對乾淨，
    等回測區 + Pain Ratio < 0.10 為進場條件
  - 1655.T/1306.T 週一重新評估掛價
    （回測區確認，考慮調低掛價）
  - 今晚美股收盤定調週末方向

備註：
  主動式全部暫緩（Pain Ratio 過高）。
  現金可投入約 65萬TWD + 37萬JPY，子彈充足。
  整體風險 18.3 仍在保守區，結構健康。
  台積電收盤大買單是今天最重要的逆轉訊號，
  若下週持續，本輪壓力測試可能接近尾聲。"""
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
