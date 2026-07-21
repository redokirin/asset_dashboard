# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-07-17"
EVENT_TAG = "black_friday_record_selloff"
EVENT_NAME = "黑色星期五收盤，台股史上最大單日跌點、四檔衛星倉齊登Pain Ratio 100%"
EVENT_NOTE = """\
description：
大盤層面： 台股收盤 -2,953.71點、-6.47%，刷新史上單日最大跌點紀錄（此前最高為2025/4/7的-2,065.87點）；
跌幅百分比則排在歷史第18名左右，落後1990年代常態觸及跌停年代的-6.5%~-6.8%區間。
導火線是台積電法說會後市場對Q3毛利率／資本支出解讀轉負，加上費半重挫4.29%、美伊衝突升溫，形成內外雙重賣壓。
韓股今日因制憲節休市，本輪跌勢首次在沒有韓股同步連動下獨立發生。
核心持倉，首見真正帳損：

1306.T 收 407.90（-11.70），正式跌破均價成本410.11，是三批建倉以來第一次真實虧損；盤中一度殺入 sniper(0.00)，收盤拉回 pullback(0.51)；標籤新增「🔻帶量下殺」，Pain Ratio 8%→20%
1321.T 收 66,960（-2,290，-6.95%），盤中同樣觸及 sniper(0.00)（建倉以來首次），收盤回到 pullback(0.76)；Pain Ratio 34%→47%
1655.T 全天最抗跌，開盤到收盤都沒離開過 daily 區間，Pain Ratio 僅4%，是今天唯一的防禦性資產

台股衛星倉——四檔 Pain Ratio 全部鎖死在100%（00985A、00981A、00988A、009821），從今早持續到收盤沒有鬆動；
00981A回撤-18.1%、00988A回撤-31.6%，持續刷新自身歷史MDD。
2330.TW：收 2,290（-175，-7.10%，跌幅超過大盤），全天開盤到中段都在 chase 區（追價警戒，代表早盤價位仍偏貴），尾盤才真正殺入 pullback(0.99)；
「😱異常爆量」（量比2.82倍）加上「淨值嚴重溢價」（PB 10.08）標籤同時存在，尾盤更出現你觀察到的212億巨額委託單（判斷為外資程式化尾盤操作，非護盤或鉅額交易）。

stress_signal： 極高。這是本波修正（甚至可能是系統建置以來）風险分数最高、廣度最深的一天——核心持倉出現首次帳損、狙擊區首次被觸及、四檔衛星倉同步頂格、且台股大盤創下史上最大跌點紀錄，多項指標同時創下追蹤紀錄以來的新高/新低。
recovery_by_close： 否。風險分數當天單向走高（22.6→23.3→23.5），沒有出現任何收斂跡象，跟7/16那次「盤中恐慌但尾盤有量縮止穩訊號」的樣貌不同——今天標籤是「🔻帶量下殺」而非「⚪量縮止跌」，代表賣壓是真實放量、非竭盡型的。
待觀察：

週末無台日股交易，但美股/中東情勢仍會發展，下週一(7/20)韓股恢復交易，須觀察是否補跌
你今天驗證過的容忍帶回測顯示：現行4%版本是唯一在7/16~7/17判定1306.T、1321.T進入retest的版本，比更嚴格版本更早、更準確反映風險——這次系統的即時性又添一次實戰佐證
1306.T的帳損狀態、1321.T的sniper觸及紀錄，都是建倉以來的里程碑事件，值得留意後續能否修復

備註： 你今天全程維持「不進場接刀、先觀望」的立場，配合稍早驗證的回測結果（收緊容忍帶會讓系統晚於現行版本才承認風險），這個決策在數據上站得住腳——現行系統已經即時且相對保守地標出了這次修正的嚴重性，你不需要额外的手動判斷去補強它。
"""
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
