# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
import pandas as pd

MarketModel = Literal["ATV_US", "ATV_JP", "ATV_TW"]
Regime = Literal["bull", "neutral", "bear"]

# US ETFs listed on Tokyo Stock Exchange — should use ATV_US, not ATV_JP
_US_ON_TSE = {"1655", "2558", "2521"}


@dataclass(frozen=True)
class TrendWeights:
    ma20: float
    ma60: float
    ma120: float


@dataclass(frozen=True)
class LevelMultipliers:
    daily: float
    pullback: float
    sniper: float


@dataclass(frozen=True)
class RegimeAdjustment:
    bull_sniper: Optional[float] = None
    neutral_sniper: Optional[float] = None
    bear_sniper: Optional[float] = None


@dataclass(frozen=True)
class Guardrails:
    use_ma_floor: bool = False
    daily_floor: Optional[str] = None
    pullback_floor: Optional[str] = None
    sniper_floor: Optional[str] = None
    min_gap_pct: float = 0.015
    price_ceiling_pct: float = 0.995
    atr_cap_pct: Optional[float] = None


@dataclass(frozen=True)
class ATVModelConfig:
    name: MarketModel
    weights: TrendWeights
    multipliers: LevelMultipliers
    guardrails: Guardrails
    regime_adjustment: RegimeAdjustment


@dataclass(frozen=True)
class MarketData:
    price: float
    ma20: float
    ma60: float
    ma120: float
    atr20: float


# ── Market Configs ───────────────────────────────────────────────────────────

ATV_CONFIGS: dict[str, ATVModelConfig] = {
    "ATV_US": ATVModelConfig(
        name="ATV_US",
        weights=TrendWeights(ma20=0.5, ma60=0.3, ma120=0.2),
        multipliers=LevelMultipliers(daily=0.5, pullback=-1.0, sniper=-2.5),
        guardrails=Guardrails(min_gap_pct=0.015, price_ceiling_pct=0.995),
        regime_adjustment=RegimeAdjustment(
            bull_sniper=-2.0, neutral_sniper=-2.5, bear_sniper=-3.0
        ),
    ),
    "ATV_JP": ATVModelConfig(
        name="ATV_JP",
        weights=TrendWeights(ma20=0.5, ma60=0.3, ma120=0.2),
        multipliers=LevelMultipliers(daily=0.4, pullback=-1.2, sniper=-2.7),
        guardrails=Guardrails(
            min_gap_pct=0.015, price_ceiling_pct=0.995, atr_cap_pct=0.10
        ),
        regime_adjustment=RegimeAdjustment(
            bull_sniper=-2.2, neutral_sniper=-2.7, bear_sniper=-3.2
        ),
    ),
    "ATV_TW": ATVModelConfig(
        name="ATV_TW",
        weights=TrendWeights(ma20=0.3, ma60=0.4, ma120=0.3),
        multipliers=LevelMultipliers(daily=-0.5, pullback=-1.5, sniper=-3.0),
        guardrails=Guardrails(
            use_ma_floor=True,
            daily_floor="MA20",
            pullback_floor="MA60",
            sniper_floor="MA120",
            min_gap_pct=0.018,
            price_ceiling_pct=0.995,
            atr_cap_pct=0.08,
        ),
        regime_adjustment=RegimeAdjustment(
            bull_sniper=-2.2, neutral_sniper=-3.0, bear_sniper=-3.5
        ),
    ),
}


# ── Core Functions ───────────────────────────────────────────────────────────

def compute_atr20(df: pd.DataFrame) -> float:
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift(1)).abs()
    lc = (df["Low"] - df["Close"].shift(1)).abs()
    return float(pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(20).mean().iloc[-1])


def detect_regime(data: MarketData) -> Regime:
    if data.ma20 > data.ma60 > data.ma120:
        return "bull"
    if data.ma20 < data.ma60 < data.ma120:
        return "bear"
    return "neutral"


def select_atv_model(asset: dict) -> MarketModel:
    """Three-layer routing: asset override → market field → ticker suffix."""
    if asset.get("atv_model"):
        return asset["atv_model"]

    market = str(asset.get("市場") or asset.get("market") or "")
    ticker = str(asset.get("代碼") or asset.get("id") or "").upper()

    # US ETFs cross-listed on TSE must be caught before the .T check
    if ticker.endswith(".T") and any(p in ticker for p in _US_ON_TSE):
        return "ATV_US"

    if "美股" in market:
        return "ATV_US"
    if "日股" in market or ticker.endswith(".T"):
        return "ATV_JP"
    if "台股" in market or ticker.endswith(".TW") or ticker.endswith(".TWO"):
        return "ATV_TW"

    return "ATV_US"


def _apply_ma_floor(value: float, floor_name: Optional[str], data: MarketData) -> float:
    if floor_name == "MA20":
        return max(value, data.ma20)
    if floor_name == "MA60":
        return max(value, data.ma60)
    if floor_name == "MA120":
        return max(value, data.ma120)
    return value


def get_buy_levels(
    asset: dict,
    data: MarketData,
    rs_p10_price: Optional[float] = None,
) -> Optional[dict]:
    """
    Returns buy levels dict or None when MA data is insufficient.
    Output keys: 日常波段, 技術回測, 狙擊位, model, regime, trend_center, atr20.
    The first three keys are backward-compatible with calculate_buffered_entries_v2().
    """
    if any(
        v is None or (isinstance(v, float) and np.isnan(v))
        for v in [data.ma20, data.ma60, data.ma120, data.atr20]
    ):
        return None

    model_name = select_atv_model(asset)
    config = ATV_CONFIGS[model_name]
    g = config.guardrails
    ra = config.regime_adjustment

    trend_center = (
        data.ma20 * config.weights.ma20
        + data.ma60 * config.weights.ma60
        + data.ma120 * config.weights.ma120
    )

    atr20 = data.atr20
    if g.atr_cap_pct:
        atr20 = min(atr20, trend_center * g.atr_cap_pct)

    regime = detect_regime(data)

    sniper_mult = config.multipliers.sniper
    if regime == "bull" and ra.bull_sniper is not None:
        sniper_mult = ra.bull_sniper
    elif regime == "bear" and ra.bear_sniper is not None:
        sniper_mult = ra.bear_sniper
    elif regime == "neutral" and ra.neutral_sniper is not None:
        sniper_mult = ra.neutral_sniper

    daily    = trend_center + config.multipliers.daily    * atr20
    pullback = trend_center + config.multipliers.pullback * atr20
    sniper   = trend_center + sniper_mult                 * atr20

    if g.use_ma_floor:
        daily    = _apply_ma_floor(daily,    g.daily_floor,    data)
        pullback = _apply_ma_floor(pullback, g.pullback_floor, data)
        sniper   = _apply_ma_floor(sniper,   g.sniper_floor,   data)

    # RS P10 as hard floor on sniper (preserves existing RS logic)
    if rs_p10_price:
        sniper = max(sniper, rs_p10_price)

    # Price ceiling applied to all tiers
    ceiling  = data.price * g.price_ceiling_pct
    daily    = min(daily,    ceiling)
    pullback = min(pullback, ceiling)
    sniper   = min(sniper,   ceiling)

    # Enforce tier ordering with minimum gap
    pullback = min(pullback, daily    * (1 - g.min_gap_pct))
    sniper   = min(sniper,   pullback * (1 - g.min_gap_pct))

    return {
        "日常波段":     round(daily,        2),
        "技術回測":     round(pullback,      2),
        "狙擊位":       round(sniper,        2),
        "model":        model_name,
        "regime":       regime,
        "trend_center": round(trend_center, 2),
        "atr20":        round(atr20,        2),
    }
