import sys
import os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from core.columns import COL_MARKET_VALUE, COL_COST, COL_PROFIT_LOSS
from core.fetchers import get_market_radar_data
from core.calculators import exchange_rate, calculate_assets_data

app = FastAPI(title="Asset Tracking API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _safe(v):
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    if isinstance(v, pd.Timestamp):
        return str(v)
    return v


def _df_to_records(df: pd.DataFrame) -> list:
    return [{k: _safe(v) for k, v in row.items()} for row in df.to_dict(orient="records")]


def _load_data():
    try:
        radar = get_market_radar_data()
        rates = exchange_rate(radar)
        df, market_share = calculate_assets_data(rates)
        return df, market_share, rates
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/portfolio")
def get_portfolio():
    df, market_share, rates = _load_data()

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
