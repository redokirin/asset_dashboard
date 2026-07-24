# -*- coding: utf-8 -*-
"""
補寫 2026-06-08 市場事件資料。可重複執行（不重複新增）。
"""

import os, sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import add_market_event, init_db, update_report_run_event

EVENT_DATE = "2026-07-24"
EVENT_TAG = "institutional_reversal_geopolitical_selloff"
EVENT_NAME = "外資單日大舉賣超662億創近期最大，改善趨勢中斷"
EVENT_NOTE = """\
description：

外資單日淨賣超609.50億，是這幾天連續追蹤下來最大的一筆賣超,直接終結了7/22（+173.44億）、7/23（+69.57億）
連續兩天的外資買超訊號——原本你我一路在觀察的「連續買超確認」在今天中斷,而且反轉力道相當猛烈。

宏觀背景： 昨晚油價因紅海危機（胡塞武裝攻擊沙烏地油輪）飆破100美元大關,加上關稅戰重啟、AI巨頭發債推升殖利率疑慮，
三條壓力線同時發酵；韓股今天再度觸發sidecar，KOSPI收跌5.25%。

個股/ETF層面全面走弱：

風險分數 22.7（前日20.8），高風險標的佔比從4.2%跳升至10.7%，本輪最大單日惡化
1321.T：跌1,710點（-7.06%），Pain Ratio 39%→50%，跌破季線持續
00985A、00988A、00981A、009821：Pain Ratio全面惡化（80%、87%、74%、90%）
OHLC顯示今天多檔劇烈來回震盪：00988A開盤daily(1.00)→盤中衝上chase（追價警戒）→最低殺到pullback(0.84)→收daily(0.21)；
00981A同樣開高衝chase後崩落至pullback(0.98~0.99)；1655.T、1306.T、2330盤中最低點都探到pullback(0.93~0.99)這種深位置，
尾盤才拉回daily區間——全天振幅劇烈

stress_signal： 高。外資單日賣超規模是近期最大，加上高風險標的佔比單日暴增超過6個百分點，是這波「持續改善」趨勢中最顯著的一次逆轉。

recovery_by_close： 否。今天是自7/21以來，風險分數與Pain Ratio首次同步全面惡化的一天。

待觀察：

外資今天的賣超是單日獲利了結（因應地緣政治風險急遽升溫的避險性調節），還是代表連續兩日買超訊號的失效，需要接下來一兩天的數據確認
油價站上100美元後的持續性，及紅海危機是否進一步升級
韓股本月累計sidecar/熔斷次數持續創紀錄，槓桿去化尚未看到真正結束的訊號

備註： 這印證了你今天稍早的感慨——這個月的走勢確實難以預測，剛建立起來的「外資轉buy」樂觀訊號，
一天之內就被新的地緣政治風險打斷。維持觀望、不隨單日數據變化而追高殺低的立場，在這種環境下依然是相對穩健的做法。
"""
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
