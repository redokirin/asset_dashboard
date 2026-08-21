import sys
import os
import re
import math
import time
import asyncio
import datetime
import logging
import threading
from pathlib import Path
from contextlib import asynccontextmanager
from functools import lru_cache

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.columns import (
    COL_ASSET_TYPE,
    COL_AVG_COST,
    COL_BUY_LEVELS,
    COL_CHANGE,
    COL_COST,
    COL_CURRENCY,
    COL_GET_VALUE,
    COL_KEEP_TWD,
    COL_MARKET,
    COL_MARKET_VALUE,
    COL_NAME,
    COL_PRICE,
    COL_PROFIT_LOSS,
    COL_RETURN_PCT,
    COL_TICKER,
    COL_UNITS,
    COL_WEIGHT,
)
from core.fetchers import (
    get_market_radar_data,
    fetch_historical_data,
    get_ticker_fundamental_info,
)
from core.calculators import exchange_rate, calculate_assets_data
from core.analysis.advanced import run_advanced_analysis
from core import (
    analysis_quant,
)  # facade：run_advanced_analysis() 額外會寫 save_snapshot / save_order_bands，只給每日排程用
from core.analysis.overall_risk import (
    calculate_overall_risk_score,
    get_risk_level,
    get_risk_alerts,
)
from core.daily_summary import generate_daily_summary
from core.exporters import export_for_ai, export_single_target_for_ai, save_ai_report
from core.tags import TAG_DISPLAY
from core.xray import (
    REGION_CODES,
    analyze_portfolio_exposures,
    get_ticker_holdings,
    get_ticker_sector,
)
from core.data_loader import get_etf_transactions
from db.database import (
    get_portfolio_value_history,
    update_ohlc_zones,
    add_market_event,
    get_market_events,
    update_market_event,
)

_TZ_TW = datetime.timezone(datetime.timedelta(hours=8))
_WARM_INTERVAL = 9 * 60  # 每 9 分鐘（< portfolio TTL 10 分鐘）
_SNAPSHOT_HOUR = 15  # 每日快照存檔時間（台灣時間），涵蓋台股(13:30)/日股(14:30)收盤
_SNAPSHOT_MINUTE = 0
_AI_REPORT_TIMES = [(9, 30), (13, 50), (15, 10)]  # AI 報告自動存檔時間（台灣時間，僅平日）


def _is_trading_hours() -> bool:
    """台股 09:00–13:30 / 日股 08:00–14:30（台灣時間），週一~五。"""
    now = datetime.datetime.now(tz=_TZ_TW)
    if now.weekday() >= 5:
        return False
    t = now.hour * 60 + now.minute
    return (8 * 60) <= t <= (14 * 60 + 30)


async def _cache_warmer():
    while True:
        await asyncio.sleep(_WARM_INTERVAL)
        if _is_trading_hours():
            try:
                _load_data()
            except Exception:
                pass
            try:
                _load_advanced()
            except Exception:
                pass


def _seconds_until_next_snapshot() -> float:
    now = datetime.datetime.now(tz=_TZ_TW)
    target = now.replace(
        hour=_SNAPSHOT_HOUR, minute=_SNAPSHOT_MINUTE, second=0, microsecond=0
    )
    if target <= now:
        target += datetime.timedelta(days=1)
    return (target - now).total_seconds()


async def _daily_snapshot_scheduler():
    """
    每日固定時間跑一次完整量化分析並落地 snapshot / order_bands（走 analysis_quant facade），
    緊接著補當天的 OHLC 區間位置。15:00 台灣時間台股(13:30)/日股(14:30)已收盤。
    """
    while True:
        await asyncio.sleep(_seconds_until_next_snapshot())
        try:
            df, _, _, _ = _load_data()
            analysis_quant.run_advanced_analysis(df)
        except Exception as exc:
            logging.warning(f"[snapshot] 每日排程存檔失敗：{exc}")
            continue
        try:
            update_ohlc_zones(str(datetime.date.today()))
        except Exception as exc:
            logging.warning(f"[snapshot] 每日 OHLC 區間補齊失敗：{exc}")


def _generate_and_save_ai_report() -> str:
    df, _, _, _ = _load_data()
    adv_res = _load_advanced()
    report = export_for_ai(df_res=df, adv_res=adv_res)
    try:
        save_ai_report(report)
    except Exception as exc:
        logging.warning(f"[api] AI 報告存檔失敗：{exc}")
    return report


def _seconds_until_next_weekday_time(times: list[tuple[int, int]]) -> float:
    """回傳離 times 中最近一個「平日」時間點還有幾秒，週六日自動跳過。"""
    now = datetime.datetime.now(tz=_TZ_TW)
    candidates = sorted(times)
    day_offset = 0
    while True:
        check_day = now + datetime.timedelta(days=day_offset)
        if check_day.weekday() < 5:  # 週一~五
            for hour, minute in candidates:
                target = check_day.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
                if target > now:
                    return (target - now).total_seconds()
        day_offset += 1


async def _ai_report_scheduler():
    """固定時間（09:30 / 13:50 / 15:10 台灣時間，週一~五）自動產生並存檔 AI 報告。"""
    while True:
        await asyncio.sleep(_seconds_until_next_weekday_time(_AI_REPORT_TIMES))
        try:
            _generate_and_save_ai_report()
        except Exception as exc:
            logging.warning(f"[ai_report] 排程存檔失敗：{exc}")


@asynccontextmanager
async def lifespan(app):
    tasks = [
        asyncio.create_task(_cache_warmer()),
        asyncio.create_task(_daily_snapshot_scheduler()),
        asyncio.create_task(_ai_report_scheduler()),
    ]
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Asset Tracking API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)

_PORTFOLIO_TTL = 600  # 開盤：10 分鐘
_PORTFOLIO_TTL_IDLE = 7200  # 收盤：2 小時
_ANALYSIS_TTL = 3600  # 開盤：1 小時
_ANALYSIS_TTL_IDLE = 86400  # 收盤：24 小時
_XRAY_TTL = 3600  # 開盤：1 小時（holdings 本身有 7 天 file cache）
_XRAY_TTL_IDLE = 86400  # 收盤：24 小時
_TRANSACTIONS_TTL = 3600  # 交易紀錄不會頻繁變動，固定 1 小時


def _safe(v):
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return str(v)
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return None if (np.isnan(v) or np.isinf(v)) else float(v)
    if isinstance(v, np.ndarray):
        return v.tolist()
    return v


def _df_to_records(df: pd.DataFrame) -> list:
    return [
        {k: _safe(v) for k, v in row.items()} for row in df.to_dict(orient="records")
    ]


def _safe_obj(obj):
    """遞迴將 dict / list 內的 numpy 型別轉為 JSON 可序列化型別。"""
    if isinstance(obj, dict):
        return {k: _safe_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_obj(item) for item in obj]
    return _safe(obj)


# ── Demo 模式：以固定比例縮放金額/持有數量欄位，隱藏真實持股規模 ──────────────
# 開關：環境變數 DEMO_MODE=1/true，同時也會讓 core/data_loader.py 自動切去 demo Google Sheet。
# demo Sheet 本身內容已是調整過的假資料，預設不用再疊加縮放（DEMO_SCALE 預設 1.0 = 不縮放）；
# 如果還想額外遮蔽一層，可自行覆寫 DEMO_SCALE（例如 0.4173）。
# 只縮放「絕對金額/數量」欄位；股價、報酬率、佔比等比例型欄位維持原值，兩者同乘一個係數後衍生比例不變。
DEMO_MODE = os.environ.get("DEMO_MODE", "").strip().lower() in ("1", "true", "yes", "on")
DEMO_SCALE = float(os.environ.get("DEMO_SCALE", "1.0"))

_DEMO_AMOUNT_FIELDS = {
    COL_UNITS, COL_AVG_COST, COL_COST, COL_MARKET_VALUE, COL_PROFIT_LOSS, COL_KEEP_TWD,
}
_DEMO_TRANSACTION_FIELDS = ("shares", "cost", "fee", "total", "pnl")
_DEMO_HISTORY_FIELDS = ("total_value", "total_gain", "invest_value")


def _mask_amount(v):
    """demo 模式下把金額/數量依 DEMO_SCALE 縮放；非 demo 模式或非數值原樣回傳。"""
    if not DEMO_MODE or v is None:
        return v
    if isinstance(v, bool) or not isinstance(v, (int, float, np.integer, np.floating)):
        return v
    scaled = float(v) * DEMO_SCALE
    return round(scaled) if isinstance(v, (int, np.integer)) else round(scaled, 4)


def _mask_record(rec: dict, fields) -> dict:
    if not DEMO_MODE:
        return rec
    for f in fields:
        if f in rec:
            rec[f] = _mask_amount(rec[f])
    return rec


@lru_cache(maxsize=1)
def _cached_portfolio(cache_key: int):
    """cache_key = int(time.time() // TTL)，每 TTL 秒自動失效。"""
    radar = get_market_radar_data()
    rates = exchange_rate(radar)
    df, market_share = calculate_assets_data(rates)
    return df, market_share, rates, radar


# lru_cache 本身沒有鎖：同一個 cache_key 若被多個 request 同時打中 cache miss，
# 每個都會各自重算一次（cache stampede）。這兩把鎖讓 miss 時的重算序列化，
# 後到的 request 等第一個算完後直接吃 lru_cache 命中，而不是各自重跑一次。
_portfolio_lock = threading.Lock()
_advanced_lock = threading.Lock()


def _load_data():
    try:
        ttl = _PORTFOLIO_TTL if _is_trading_hours() else _PORTFOLIO_TTL_IDLE
        key = int(time.time() // ttl)
        with _portfolio_lock:
            return _cached_portfolio(key)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@lru_cache(maxsize=1)
def _cached_advanced(cache_key: int):
    ttl = _PORTFOLIO_TTL if _is_trading_hours() else _PORTFOLIO_TTL_IDLE
    df, _, _, _ = _cached_portfolio(int(time.time() // ttl))
    return run_advanced_analysis(df)


def _load_advanced():
    try:
        ttl = _ANALYSIS_TTL if _is_trading_hours() else _ANALYSIS_TTL_IDLE
        key = int(time.time() // ttl)
        with _advanced_lock:
            return _cached_advanced(key)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@lru_cache(maxsize=16)
def _cached_xray(cache_key: int, regions: tuple[str, ...]):
    return analyze_portfolio_exposures(regions=list(regions) or None)


def _load_xray(regions: list[str] | None = None):
    try:
        ttl = _XRAY_TTL if _is_trading_hours() else _XRAY_TTL_IDLE
        key = int(time.time() // ttl)
        region_key = tuple(sorted(set(regions))) if regions else ()
        return _cached_xray(key, region_key)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/portfolio")
def get_portfolio():
    df, market_share, rates, _radar = _load_data()

    total_value = int(df[COL_MARKET_VALUE].sum()) if not df.empty else 0
    total_cost = int(df[COL_COST].sum()) if not df.empty else 0
    total_pl = int(df[COL_PROFIT_LOSS].sum()) if not df.empty else 0
    return_pct = round(total_pl / total_cost * 100, 2) if total_cost else 0

    assets = [_mask_record(rec, _DEMO_AMOUNT_FIELDS) for rec in _df_to_records(df)]

    return {
        "exchange_rates": rates,
        "assets": assets,
        "market_share": market_share,
        "summary": {
            "total_value_twd": _mask_amount(total_value),
            "total_cost_twd": _mask_amount(total_cost),
            "total_pl_twd": _mask_amount(total_pl),
            "return_pct": return_pct,
        },
        "demo_mode": DEMO_MODE,
    }


@app.get("/api/analysis/advanced")
def get_advanced_analysis():
    adv_res = _load_advanced()
    if adv_res.empty:
        return {"assets": []}
    records = _df_to_records(adv_res)
    for rec in records:
        if isinstance(rec.get("tags"), list):
            rec["tags"] = [TAG_DISPLAY.get(t, t) for t in rec["tags"]]
    return {"assets": records}


@app.get("/api/summary/daily")
def get_daily_summary():
    df, _, _, _ = _load_data()
    adv_res = _load_advanced()
    risk_data = calculate_overall_risk_score(adv_res, df)
    result = generate_daily_summary(
        df_res=df, adv_res=adv_res, risk_data=risk_data or None
    )
    return _safe_obj(result)


@app.get("/api/ticker/{ticker}/historical")
def get_ticker_historical(
    ticker: str,
    period: str = Query(default="2y", pattern="^(1mo|3mo|6mo|1y|2y)$"),
):
    try:
        df = fetch_historical_data(ticker, period=period)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"找不到 {ticker} 的歷史資料")

    df = df.copy()
    df.index = pd.to_datetime(df.index)
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    data = [
        {
            "date": idx.strftime("%Y-%m-%d"),
            "open": _safe(row.get("Open")),
            "high": _safe(row.get("High")),
            "low": _safe(row.get("Low")),
            "close": _safe(row.get("Close")),
            "volume": _safe(row.get("Volume")),
        }
        for idx, row in df.iterrows()
    ]
    return {"ticker": ticker, "period": period, "data": data}


@app.get("/api/export/ai")
def get_export_ai():
    return {"report": _generate_and_save_ai_report()}


@app.get("/api/export/ai/{ticker}")
def get_export_ai_ticker(ticker: str):
    adv_res = _load_advanced()
    if adv_res.empty:
        raise HTTPException(status_code=404, detail=f"找不到 {ticker} 的分析資料")
    rows = adv_res[adv_res["代碼"] == ticker]
    if rows.empty:
        raise HTTPException(status_code=404, detail=f"找不到 {ticker} 的分析資料")
    report = export_single_target_for_ai(rows.iloc[0])
    return {"ticker": ticker, "report": report}


@app.get("/api/ticker/{ticker}/fundamental")
def get_ticker_fundamental(ticker: str):
    info = get_ticker_fundamental_info(ticker)
    return _safe_obj(info)


class ManualAnalysisRequest(BaseModel):
    tickers: list[str]


@app.post("/api/analysis/manual")
def post_manual_analysis(req: ManualAnalysisRequest):
    tickers = [t.strip().upper() for t in req.tickers if t.strip()]
    if not tickers:
        return {"assets": []}

    manual_df = pd.DataFrame(
        [
            {
                COL_MARKET: "手動",
                COL_ASSET_TYPE: "個股",
                COL_NAME: t,
                COL_TICKER: t,
                COL_CURRENCY: "TWD",
                COL_UNITS: 0,
                COL_AVG_COST: 0.0,
                COL_CHANGE: None,
                COL_PRICE: 0.0,
                COL_BUY_LEVELS: 0.0,
                COL_COST: 0,
                COL_MARKET_VALUE: 0,
                COL_PROFIT_LOSS: 0,
                COL_RETURN_PCT: 0.0,
                COL_WEIGHT: 0.0,
                COL_GET_VALUE: True,
            }
            for t in tickers
        ]
    )

    try:
        adv = run_advanced_analysis(manual_df)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

    if adv.empty:
        return {"assets": []}

    records = _df_to_records(adv)
    for rec in records:
        if isinstance(rec.get("tags"), list):
            rec["tags"] = [TAG_DISPLAY.get(t, t) for t in rec["tags"]]
        try:
            ticker_rows = adv[adv[COL_TICKER] == rec.get("代碼")]
            if not ticker_rows.empty:
                rec["_report"] = export_single_target_for_ai(ticker_rows.iloc[0])
        except Exception:
            rec["_report"] = None

    return {"assets": records}


@app.get("/api/xray")
def get_xray(region: list[str] | None = Query(None)):
    regions = [r for r in region if r in REGION_CODES] if region else None
    data = _load_xray(regions)
    if DEMO_MODE and isinstance(data, dict) and "total_value_twd" in data:
        data = {**data, "total_value_twd": _mask_amount(data["total_value_twd"])}
    return _safe_obj(data)


@lru_cache(maxsize=64)
def _cached_ticker_holdings(ticker: str, cache_key: int) -> list:
    return get_ticker_holdings(ticker)


@lru_cache(maxsize=64)
def _cached_ticker_sector(ticker: str, cache_key: int) -> list:
    return get_ticker_sector(ticker)


@app.get("/api/holdings/{ticker}")
def get_holdings_endpoint(ticker: str):
    t = ticker.strip().upper()
    key = int(time.time() // 3600)  # 1 小時 in-memory cache（file cache 為 7 天）
    return {
        "ticker": t,
        "holdings": _safe_obj(_cached_ticker_holdings(t, key)),
        "sector_allocation": _safe_obj(_cached_ticker_sector(t, key)),
    }


@lru_cache(maxsize=1)
def _cached_transactions(cache_key: int):
    df, _, _, _ = _load_data()
    price_map = dict(zip(df[COL_TICKER], df[COL_PRICE])) if not df.empty else {}
    return get_etf_transactions(price_map)


@app.get("/api/transactions")
def get_transactions():
    """依 ticker 分組的 ETF 交易紀錄（來源：Google Sheets JPY / TWD 分頁）。"""
    key = int(time.time() // _TRANSACTIONS_TTL)
    data = _cached_transactions(key)
    if DEMO_MODE:
        data = {
            ticker: [_mask_record(dict(tx), _DEMO_TRANSACTION_FIELDS) for tx in txs]
            for ticker, txs in data.items()
        }
    return _safe_obj(data)


@app.get("/api/portfolio/history")
def get_portfolio_history(days: int = Query(default=90, ge=1, le=36500)):
    """
    資產總覽時間序列（total_value / total_gain / invest_value / total_gain_pct），
    依日期升冪排列，供折線圖使用。days 給一個很大的值（如 36500）等同於拉全部歷史。
    """
    history = get_portfolio_value_history(days)
    if DEMO_MODE:
        history = [_mask_record(dict(row), _DEMO_HISTORY_FIELDS) for row in history]
    return _safe_obj(history)


@app.get("/api/analysis/risk")
def get_risk():
    df, _, _, _ = _load_data()
    adv_res = _load_advanced()
    risk_data = calculate_overall_risk_score(adv_res, df)
    if not risk_data:
        raise HTTPException(status_code=503, detail="無法計算風險係數：資料不足")
    score = risk_data["risk_score"]
    level_label, level_advice = get_risk_level(score)
    alerts = get_risk_alerts(risk_data)
    return _safe_obj(
        {
            **risk_data,
            "risk_level": level_label,
            "risk_advice": level_advice,
            "alerts": alerts,
        }
    )


# ── Market Events 日曆 ─────────────────────────────────────────────────────────

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ANALYZE_ROOT = Path(__file__).resolve().parent.parent / "analyze"


def _require_date(value: str) -> str:
    if not _DATE_RE.match(value):
        raise HTTPException(status_code=400, detail=f"日期格式錯誤，需為 YYYY-MM-DD：{value}")
    return value


class MarketEventCreate(BaseModel):
    event_date: str
    event_tag: str
    event_name: str | None = None
    event_note: str | None = None
    is_pressure_test: int = 0


class MarketEventUpdate(BaseModel):
    event_tag: str | None = None
    event_name: str | None = None
    event_note: str | None = None
    is_pressure_test: int | None = None


@app.get("/api/market-events")
def get_market_events_endpoint(
    start: str = Query(...), end: str = Query(...)
):
    """指定日期區間（含頭尾）內的 market_events，供月曆月檢視／單日詳情共用（單日：start=end=date）。"""
    _require_date(start)
    _require_date(end)
    return _safe_obj(get_market_events(start, end))


@app.post("/api/market-events")
def post_market_event(req: MarketEventCreate):
    _require_date(req.event_date)
    event_id = add_market_event(
        event_date=req.event_date,
        event_tag=req.event_tag,
        event_name=req.event_name,
        event_note=req.event_note,
        is_pressure_test=req.is_pressure_test,
    )
    return {"id": event_id}


@app.put("/api/market-events/{event_id}")
def put_market_event(event_id: int, req: MarketEventUpdate):
    ok = update_market_event(
        event_id,
        event_tag=req.event_tag,
        event_name=req.event_name,
        event_note=req.event_note,
        is_pressure_test=req.is_pressure_test,
    )
    if not ok:
        raise HTTPException(status_code=404, detail=f"找不到 market_event id={event_id}，或未提供任何欄位")
    return {"ok": True}


@app.get("/api/reports/{date}")
def list_reports(date: str):
    """列出 analyze/{YYYYMMDD}/ 底下所有 .md 報告檔名（不假設檔名格式）。"""
    _require_date(date)
    day_dir = _ANALYZE_ROOT / date.replace("-", "")
    if not day_dir.is_dir():
        return {"files": []}
    return {"files": sorted(p.name for p in day_dir.glob("*.md"))}


@app.get("/api/reports/{date}/{filename}")
def get_report_content(date: str, filename: str):
    """讀取單一報告的原始 markdown 內容。filename 需為純檔名（無路徑分隔符）、以 .md 結尾。"""
    _require_date(date)
    if Path(filename).name != filename or not filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="檔名不合法")
    day_dir = _ANALYZE_ROOT / date.replace("-", "")
    file_path = (day_dir / filename).resolve()
    if not file_path.is_relative_to(_ANALYZE_ROOT.resolve()) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="找不到報告檔案")
    return {"content": file_path.read_text(encoding="utf-8")}
