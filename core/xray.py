# -*- coding: utf-8 -*-
"""
Portfolio X-Ray：穿透 ETF/基金持股，計算組合真實個股曝險比例。

主要 API：
    analyze_portfolio_exposures(assets=None, on_ticker=None) → dict

回傳結構：
    {
        "total_value_twd": float,
        "assets_count":    int,
        "exposures":       [{"symbol", "name", "weight", "sources"}, ...],  # sorted desc
        "buckets":         [{"label", "weight", "ticker"}, ...],
        "identified_pct":  float,   # 0~1
        "unidentified_pct": float,
    }
"""
import json
import logging
import time
import warnings
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

from core.data_loader import get_assets as _get_assets

# 無法從 yfinance 取得持股的標的 → 直接貼標籤，不解析個股
MANUAL_LABELS: dict[str, str] = {
    "009821.TW": "全球戰略稀土與關鍵資源",
}

_CACHE_PATH = Path(__file__).parent.parent / "analyze" / ".xray_holdings_cache.json"
_CACHE_TTL = 7 * 86400  # 7 days


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _load_cache() -> dict:
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _cache_get(cache: dict, ticker: str) -> list[dict] | None:
    entry = cache.get(ticker)
    if not entry:
        return None
    if time.time() - entry["cached_at"] > _CACHE_TTL:
        return None
    return entry["holdings"]


def _cache_set(cache: dict, ticker: str, holdings: list[dict]) -> None:
    cache[ticker] = {"cached_at": time.time(), "holdings": holdings}


# ── Holdings fetch ────────────────────────────────────────────────────────────

def _fetch_top_holdings(ticker: str) -> list[dict]:
    """回傳 [{"symbol", "name", "weight"}, ...]，失敗回傳空 list。"""
    try:
        fd = yf.Ticker(ticker).funds_data
        if fd is None:
            return []
        h = fd.top_holdings
        if h is None:
            return []
        df = pd.DataFrame(h)
        if df.empty:
            return []
        df = df.reset_index()  # Symbol 從 index 升為欄位
        result = []
        for _, row in df.iterrows():
            sym  = str(row.get("Symbol") or row.get("symbol") or "").strip()
            name = str(row.get("Name")   or row.get("name")   or sym).strip()
            wt   = float(row.get("Holding Percent") or row.get("holding percent") or 0)
            if sym:
                result.append({"symbol": sym, "name": name, "weight": wt})
        return result
    except Exception:
        return []


def get_holdings(ticker: str, cache: dict, depth: int = 0) -> tuple[list[dict], str]:
    """
    取得 ETF/基金持股清單（帶 file-based cache，TTL 7 天）。
    偵測到包裝 ETF（單一持股 >90%）時自動往下鑽一層。

    Returns:
        (holdings, status_msg)
        status_msg 供 caller 顯示進度（terminal 或 logging）。
    """
    cached = _cache_get(cache, ticker)
    if cached is not None:
        return cached, "(cache)"

    holdings = _fetch_top_holdings(ticker)
    if not holdings:
        _cache_set(cache, ticker, [])
        return [], "無持股資料"

    if depth == 0 and len(holdings) == 1 and holdings[0]["weight"] > 0.90:
        inner = holdings[0]["symbol"]
        inner_cached = _cache_get(cache, inner)
        if inner_cached is not None:
            result = inner_cached
            msg = f"包裝 ETF: {ticker} → {inner}  (cache)"
        else:
            inner_holdings = _fetch_top_holdings(inner)
            _cache_set(cache, inner, inner_holdings)
            result = inner_holdings if inner_holdings else holdings
            msg = f"包裝 ETF: {ticker} → {inner}"
        _cache_set(cache, ticker, result)
        return result, msg

    _cache_set(cache, ticker, holdings)
    top_sum = sum(h["weight"] for h in holdings)
    return holdings, f"OK  {len(holdings)} 筆  coverage {top_sum * 100:.1f}%"


# ── Public single-ticker query ───────────────────────────────────────────────

def get_ticker_holdings(ticker: str) -> list[dict]:
    """
    取得單一 ETF/基金前十大持股（帶 7 天 file cache）。

    Returns:
        [{"symbol": str, "name": str, "weight": float}, ...]  最多 10 筆。
        個股或查無資料時回傳空 list。
    """
    cache = _load_cache()
    holdings, _ = get_holdings(ticker.upper(), cache)
    _save_cache(cache)
    return holdings[:10]


# ── Main analysis ─────────────────────────────────────────────────────────────

def analyze_portfolio_exposures(
    assets: dict | None = None,
    on_ticker: "callable[[str, float, str], None] | None" = None,
) -> dict:
    """
    穿透 ETF/基金持股，回傳組合真實個股曝險比例。

    Args:
        assets:     由 get_assets() 取得的資產配置。None 時自動載入。
        on_ticker:  進度回呼 on_ticker(ticker, port_weight, status_msg)。
                    terminal 可傳入 print wrapper；API 呼叫不傳（使用 logging.info）。
    """
    if assets is None:
        assets = _get_assets()

    # 1. 建立持倉清單（只取有市值的標的，銀行排除）
    portfolio: dict[str, dict] = {}
    total_value = 0.0

    for sheet in ["etfs", "stocks", "funds"]:
        for key, info in assets[sheet].items():
            if not info.get("enabled", True):
                continue
            value = float(info.get("value") or 0)
            if value <= 0:
                continue
            ticker = info.get("id") or key  # funds 的 key 是申購編號
            portfolio[ticker] = {
                "value":  value,
                "sheet":  sheet,
                "name":   info.get("name", ticker),
                "region": info.get("region") or "未分類",
            }
            total_value += value

    if total_value == 0:
        logging.warning("[xray] 無法取得市值資料，請確認 Google Sheets value 欄位")
        return {
            "total_value_twd":  0,
            "assets_count":     0,
            "exposures":        [],
            "buckets":          [],
            "identified_pct":   0.0,
            "unidentified_pct": 0.0,
        }

    for info in portfolio.values():
        info["port_weight"] = info["value"] / total_value

    # 2. 穿透持股
    exposures: dict[str, dict] = {}
    buckets:   list[dict]      = []
    cache = _load_cache()

    def _notify(ticker: str, pw: float, msg: str) -> None:
        if on_ticker:
            on_ticker(ticker, pw, msg)
        else:
            logging.info(f"[xray] {ticker}  {pw * 100:.2f}%  {msg}")

    for ticker, info in portfolio.items():
        pw = info["port_weight"]

        if ticker in MANUAL_LABELS:
            label = MANUAL_LABELS[ticker]
            buckets.append({"label": label, "weight": pw, "ticker": ticker, "region": info["region"]})
            _notify(ticker, pw, f"手動標籤 → {label}")
            continue

        if info["sheet"] == "stocks":
            e = exposures.setdefault(
                ticker, {"name": info["name"], "weight": 0.0, "sources": []}
            )
            e["weight"] += pw
            if ticker not in e["sources"]:
                e["sources"].append(ticker)
            _notify(ticker, pw, "個股，直接計入")
            continue

        holdings, msg = get_holdings(ticker, cache)
        _notify(ticker, pw, msg)

        if not holdings:
            buckets.append({"label": f"{ticker} 無持股資料", "weight": pw, "ticker": ticker, "region": info["region"]})
            continue

        top_sum = sum(h["weight"] for h in holdings)
        other_w = max(0.0, 1.0 - top_sum)

        for h in holdings:
            sym    = h["symbol"]
            contrib = pw * h["weight"]
            e = exposures.setdefault(sym, {"name": h["name"], "weight": 0.0, "sources": []})
            e["weight"] += contrib
            if ticker not in e["sources"]:
                e["sources"].append(ticker)

        if other_w > 0.005:
            buckets.append({
                "label":  f"{ticker} 其他持股",
                "weight": pw * other_w,
                "ticker": ticker,
                "region": info["region"],
            })

    _save_cache(cache)

    # 3. 整理回傳值
    ranked       = sorted(exposures.items(), key=lambda x: x[1]["weight"], reverse=True)
    identified   = sum(v["weight"] for v in exposures.values())
    unidentified = sum(b["weight"] for b in buckets)

    # 依 region 合併 buckets（同地區的「其他持股」加總）
    region_weights: dict[str, float] = {}
    for b in buckets:
        region = b.get("region") or "未分類"
        region_weights[region] = region_weights.get(region, 0.0) + b["weight"]

    merged_buckets = sorted(
        [
            {"label": f"{region}其他持股", "weight": round(w, 6)}
            for region, w in region_weights.items()
        ],
        key=lambda x: x["weight"],
        reverse=True,
    )

    return {
        "total_value_twd":  total_value,
        "assets_count":     len(portfolio),
        "exposures": [
            {
                "symbol":  sym,
                "name":    info["name"],
                "weight":  round(info["weight"], 6),
                "sources": info["sources"],
            }
            for sym, info in ranked
        ],
        "buckets": merged_buckets,
        "identified_pct":   round(identified, 6),
        "unidentified_pct": round(unidentified, 6),
    }
