import sys
import os
import math
import time
from functools import lru_cache

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from core.columns import COL_MARKET_VALUE, COL_COST, COL_PROFIT_LOSS
from core.fetchers import get_market_radar_data, fetch_historical_data, get_ticker_fundamental_info
from core.calculators import exchange_rate, calculate_assets_data
from core.analysis.advanced import run_advanced_analysis
from core.analysis.overall_risk import calculate_overall_risk_score, get_risk_level, get_risk_alerts
from core.daily_summary import generate_daily_summary
from core.exporters import export_for_ai, export_single_target_for_ai
from core.tags import TAG_DISPLAY

app = FastAPI(title="Asset Tracking API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_PORTFOLIO_TTL = 600   # 秒：GSheets + 股價快取時間
_ANALYSIS_TTL  = 3600  # 秒：量化分析快取時間（yfinance batch 下載較慢）


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


def _load_data():
    try:
        cache_key = int(time.time() // _PORTFOLIO_TTL)
        return _cached_portfolio(cache_key)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@lru_cache(maxsize=1)
def _cached_advanced(cache_key: int):
    """cache_key = int(time.time() // _ANALYSIS_TTL)，每小時失效一次。"""
    portfolio_key = int(time.time() // _PORTFOLIO_TTL)
    df, _, _, _ = _cached_portfolio(portfolio_key)
    return run_advanced_analysis(df)


def _load_advanced():
    try:
        cache_key = int(time.time() // _ANALYSIS_TTL)
        return _cached_advanced(cache_key)
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
