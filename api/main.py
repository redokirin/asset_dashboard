import sys
import os
import math
import time
import asyncio
import datetime
import threading
from contextlib import asynccontextmanager
from functools import lru_cache

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.columns import (
    COL_ASSET_TYPE, COL_AVG_COST, COL_BUY_LEVELS, COL_CHANGE, COL_COST,
    COL_CURRENCY, COL_GET_VALUE, COL_MARKET, COL_MARKET_VALUE, COL_NAME,
    COL_PRICE, COL_PROFIT_LOSS, COL_RETURN_PCT, COL_TICKER, COL_UNITS, COL_WEIGHT,
)
from core.fetchers import get_market_radar_data, fetch_historical_data, get_ticker_fundamental_info
from core.calculators import exchange_rate, calculate_assets_data
from core.analysis.advanced import run_advanced_analysis
from core.analysis.overall_risk import calculate_overall_risk_score, get_risk_level, get_risk_alerts
from core.daily_summary import generate_daily_summary
from core.exporters import export_for_ai, export_single_target_for_ai
from core.tags import TAG_DISPLAY
from core.xray import analyze_portfolio_exposures, get_ticker_holdings, get_ticker_sector
from core.data_loader import get_etf_transactions

_TZ_TW = datetime.timezone(datetime.timedelta(hours=8))
_WARM_INTERVAL = 9 * 60  # 每 9 分鐘（< portfolio TTL 10 分鐘）

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


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(_cache_warmer())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Asset Tracking API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_PORTFOLIO_TTL      = 600    # 開盤：10 分鐘
_PORTFOLIO_TTL_IDLE = 7200  # 收盤：2 小時
_ANALYSIS_TTL       = 3600  # 開盤：1 小時
_ANALYSIS_TTL_IDLE  = 86400 # 收盤：24 小時
_XRAY_TTL           = 3600  # 開盤：1 小時（holdings 本身有 7 天 file cache）
_XRAY_TTL_IDLE      = 86400 # 收盤：24 小時
_TRANSACTIONS_TTL   = 3600  # 交易紀錄不會頻繁變動，固定 1 小時


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
    return [{k: _safe(v) for k, v in row.items()} for row in df.to_dict(orient="records")]


def _safe_obj(obj):
    """遞迴將 dict / list 內的 numpy 型別轉為 JSON 可序列化型別。"""
    if isinstance(obj, dict):
        return {k: _safe_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_safe_obj(item) for item in obj]
    return _safe(obj)


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


@lru_cache(maxsize=1)
def _cached_xray(cache_key: int):
    return analyze_portfolio_exposures()


def _load_xray():
    try:
        ttl = _XRAY_TTL if _is_trading_hours() else _XRAY_TTL_IDLE
        return _cached_xray(int(time.time() // ttl))
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/portfolio")
def get_portfolio():
    df, market_share, rates, _radar = _load_data()

    total_value = int(df[COL_MARKET_VALUE].sum()) if not df.empty else 0
    total_cost  = int(df[COL_COST].sum())         if not df.empty else 0
    total_pl    = int(df[COL_PROFIT_LOSS].sum())  if not df.empty else 0

    return {
        "exchange_rates": rates,
        "assets": _df_to_records(df),
        "market_share": market_share,
        "summary": {
            "total_value_twd": total_value,
            "total_cost_twd":  total_cost,
            "total_pl_twd":    total_pl,
            "return_pct":      round(total_pl / total_cost * 100, 2) if total_cost else 0,
        },
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
    result = generate_daily_summary(df_res=df, adv_res=adv_res, risk_data=risk_data or None)
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
            "date":   idx.strftime("%Y-%m-%d"),
            "open":   _safe(row.get("Open")),
            "high":   _safe(row.get("High")),
            "low":    _safe(row.get("Low")),
            "close":  _safe(row.get("Close")),
            "volume": _safe(row.get("Volume")),
        }
        for idx, row in df.iterrows()
    ]
    return {"ticker": ticker, "period": period, "data": data}


@app.get("/api/export/ai")
def get_export_ai():
    df, _, _, _ = _load_data()
    adv_res = _load_advanced()
    report = export_for_ai(df_res=df, adv_res=adv_res)
    return {"report": report}


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

    manual_df = pd.DataFrame([
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
    ])

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
def get_xray():
    return _safe_obj(_load_xray())


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
    return get_etf_transactions()


@app.get("/api/transactions")
def get_transactions():
    """依 ticker 分組的 ETF 交易紀錄（來源：Google Sheets JPY / TWD 分頁）。"""
    key = int(time.time() // _TRANSACTIONS_TTL)
    return _safe_obj(_cached_transactions(key))


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
    return _safe_obj({
        **risk_data,
        "risk_level": level_label,
        "risk_advice": level_advice,
        "alerts": alerts,
    })
