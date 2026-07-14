# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-07-14"
EVENT_TAG = "intraday_v_reversal_sniper_touch"
EVENT_NAME = "台日股同步驗證V轉，00981A/00985A/00988A盤中同時觸及狙擊區後強彈"
EVENT_NOTE = """\
description:
  今天完整驗證了韓股KOSPI的V轉模式——台股、
  日股皆呈現「早盤重挫、尾盤強彈」的走勢，
  OHLC顯示多檔標的盤中一度觸及本輪修正
  以來最深的狙擊區，收盤前又大幅收復。

  三檔台股主動式ETF同時觸及sniper(0.00)——
  本輪首見：
  - 00981A：開盤/最高chase，最低直接探至
    sniper(0.00)（系統定義最深回測區），
    尾盤強彈至pullback(0.96)收盤。28.40
    （-0.95），Pain Ratio 99%→100%，
    回撤擴大至-12.0%（本輪新低）
  - 00985A：同樣最低觸及sniper(0.00)，
    尾盤收pullback(0.69)。21.18（-0.52），
    Pain Ratio 70%→96%（單日+26，本輪
    最大單日跳升）
  - 00988A：最低亦觸sniper(0.00)，收盤
    回升至daily(0.19)。18.49（-0.17），
    Pain Ratio維持100%

  2330罕見深探：
  - 全天多在daily(0.21)~0.44區間，但盤中
    一度探至pullback(0.98)——這是2330在
    本輪修正中少見的深度回測，隨後收斂
    至daily(0.33)，2,420（-35）

  1321.T、1306.T同步收復：
  - 1321.T：最低pullback(0.82)，收盤daily
    (0.35)，70,050（+570）翻紅，Pain Ratio
    降至29%
  - 1306.T：最低daily(0.04)，收盤daily(0.43)，
    421.30（+4.00）翻紅，Pain Ratio降至6%
    （本輪最低），呼應「東證抗跌」的持續
    觀察

  1655.T、0052維持相對穩定：
  - 1655.T：Pain Ratio維持0%，882.80
    （+0.20），全天daily(0.32~0.53)區間
  - 0052：最低曾探至pullback(0.36)，收盤
    daily(0.14)，Pain Ratio 20%

  009821維持深水區不變：
  - Pain Ratio 100%，13.08（-0.26），
    RSI 8.9持續深度超賣

  整體風險係數21.0，維持🟡中低區間，
  高風險標的佔比10.8%不變

stress_signal: 高度但短暫（三檔核心台股ETF
  加2330同時觸及本輪最深的sniper/pullback
  區間，反映美伊衝突+韓股熔斷的雙重衝擊
  達到高峰，但尾盤全面強彈收斂，顯示這是
  一次急殺急拉的閃崩模式，而非趨勢性破位）

recovery_by_close: Yes（多數標的尾盤大幅
  收復跌幅，1306.T、1321.T翻紅，00981A/
  00985A/00988A/2330皆從當日最低點顯著彈升）

待觀察：
  - 00981A、00985A、00988A今天盤中同時
    觸及sniper(0.00)是本輪修正以來首次，
    雖然收盤已回升，但確認了「這一波
    修正已經探到系統定義的最深區間」——
    若未來重新回測到類似低點，可能是
    更值得留意的訊號
    （不過sniper區稍縱即逝，如同1321.T
    先前兩次掛單擦身而過的經驗）
  - 2330罕見探至pullback(0.98)，法說會
    （7/16）前的波動加大，需持續留意
  - 韓股KOSPI型態的V轉若延續至明後兩天，
    可能代表這波「美伊衝突+韓股熔斷+
    記憶體疑慮」三重壓力的短期高點已過

備註：
  今天是本輪修正以來最劇烈的單日雙向
  波動，三檔核心台股主動式ETF與2330
  盤中同時觸及史上最深的狙擊/回測邊界，
  隨後全面強彈收復，與KOSPI的V轉走勢
  完全同步。這驗證了左側交易系統「等待
  合理區間」的邏輯確實捕捉到了今天的
  最深低點，只是這個低點停留時間極短，
  一般人為操作很難即時掛單成交。你這個月
  已表態現金留著、讓市場先跑一段，今天
  這種急殺急拉的模式再次印證了不追價、
  保持紀律的重要性——追在恐慌最深處或
  賣在反彈最高處都不容易，穩定執行既定
  的區間策略比臨場反應更可靠。"""
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
