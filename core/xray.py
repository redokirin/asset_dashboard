# -*- coding: utf-8 -*-
"""
Portfolio X-Ray：穿透 ETF/基金持股，計算組合真實個股曝險比例。

主要 API：
    analyze_portfolio_exposures(assets=None, on_ticker=None) → dict

回傳結構：
    {
        "total_value_twd": float,
        "assets_count":    int,
        "exposures":       [{"symbol", "name", "weight", "sources", "ticker"}, ...],  # sorted desc；ticker：_TICKER_LABELS 對應則為「中文名(代碼)」，否則為代碼原值
        "buckets":         [{"label", "weight", "ticker"}, ...],
        "sector_exposures": [{"sector", "weight", "name"}, ...],  # sorted desc；個股用 info.sector，ETF/基金用 funds_data.sector_weightings；name：_INDUSTRY_TRANS 對應則為中文，否則為 sector 原值
        "identified_pct":  float,   # 0~1
        "unidentified_pct": float,
    }
"""
import json
import logging
import time
import warnings
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")

from core.data_loader import get_assets as _get_assets
from db.database import get_ticker_cache, set_ticker_cache

# 無法從 yfinance 取得持股的標的 → 直接貼標籤，不解析個股
MANUAL_LABELS: dict[str, str] = {
    "009821.TW": "全球戰略稀土與關鍵資源",
}

# yfinance 對 sector 的命名不一致：funds_data.sector_weightings 用 snake_case
# （如 "technology"），個股 info.sector 用 Title Case（如 "Technology"）。
# 統一正規化成同一組標籤，避免同一產業在彙總時被拆成兩筆。
_SECTOR_LABELS: dict[str, str] = {
    "basic_materials":         "Basic Materials",
    "communication_services":  "Communication Services",
    "consumer_cyclical":       "Consumer Cyclical",
    "consumer_defensive":      "Consumer Defensive",
    "energy":                  "Energy",
    "financial_services":      "Financial Services",
    "healthcare":              "Healthcare",
    "industrials":             "Industrials",
    "real_estate":             "Real Estate",
    "realestate":              "Real Estate",
    "technology":              "Technology",
    "utilities":               "Utilities",
}

_INDUSTRY_TRANS: dict[str, str] = {
    "technology":               "科技",
    "industrials":              "工業",
    "financial_services":       "金融",
    "consumer_cyclical":        "非必需消費",
    "communication_services":   "通訊服務",
    "healthcare":               "醫療保健",
    "consumer_defensive":       "必需消費",
    "basic_materials":          "基本材料",
    "energy":                   "能源",
    "real_estate":              "房地產",
    "utilities":                "公用事業",
}

_TICKER_LABELS: dict[str, str] = {
    "NVDA":     "NVIDIA",
    "AAPL":     "Apple",
    "MSFT":     "Microsoft",
    "AMZN":     "Amazon",
    "GOOGL":    "Google",
    "AVGO":     "Broadcom",
    "GOOG":     "Google",
    "MU":       "Micron",
    "META":     "Meta",
    "TSLA":     "Tesla",
    "LITE":     "Lumentum",
    "GLW":      "康寧",
    "CIEN":     "Ciena",
    "GEV":      "奇異",
    "AMD":      "AMD",
    "SNDK":     "SANDISK",
    "AMAT":     "Applied Materials",

    "2330.TW": "台積電",
    "2383.TW": "台光電",
    "2317.TW": "鴻海",
    "2303.TW": "聯電",
    "2360.TW": "致茂",
    "2382.TW": "廣達",
    "2308.TW": "台達電",
    "2395.TW": "研華",
    "2345.TW": "智邦",
    "2368.TW": "金像電",
    "3017.TW": "奇鋐",
    "3653.TW": "健策",
    "6515.TW": "穎崴",
    "3037.TW": "欣興",
    "3711.TW": "日月光投控",
    "3665.TW": "貿聯-KY",
    "2412.TW": "中華電信",
    "1216.TW": "統一",
    "4904.TW": "遠傳",
    "2881.TW": "富邦金",
    "2891.TW": "中信金",
    "2885.TW": "元大金",
    "2887.TW": "台新新光金",
    "6442.TW": "光聖",
    "3189.TW": "景碩",
    "8996.TW": "高力",
    "2454.TW": "聯發科",
    "2327.TW": "國巨",

    "6223.TWO": "旺矽",
    "5274.TWO": "信驊",
    "3293.TWO": "鈊象",
    "4749.TWO": "新應材",
    "3081.TWO": "聯亞",

    "8306.T": "三菱UFJ",
    "7203.T": "トヨタ自動車",
    "9984.T": "ソフトバンク",
    "6501.T": "日立製作所",
    "8316.T": "三井住友",
    "6758.T": "ソニーグループ",
    "8035.T": "東京エレクトロン",
    "8411.T": "みずほ",
    "8058.T": "三菱商事",
    "6787.T": "メイコー",
    "5801.T": "古河電気工業",
    "6981.T": "村田製作所",
    "285A.T": "キオクシア",
    "6976.T": "太陽誘電",
    "7270.T": "Subaru",
    "9983.T": "ファーストリテイリング",
    "6857.T": "アドバンテスト",
    "6762.T": "TDK",
    "4062.T": "イビデン",
    "6954.T": "ファナック",
    "4063.T": "信越化学",
    "9433.T": "KDDI",

    "009150.KS" : "Samsung",
}


def _normalize_sector(name: str | None) -> str | None:
    """把不同來源的 sector 命名統一成同一組標籤，查無對應表時原樣回傳。"""
    if not name:
        return name
    key = name.strip().lower().replace(" ", "_")
    return _SECTOR_LABELS.get(key, name)


def _with_industry_name(sector_row: dict) -> dict:
    """
    附加 name 欄位：_INDUSTRY_TRANS 有對應則翻譯成中文，查無對應表時回傳原值。
    _INDUSTRY_TRANS 的 key 是 snake_case（跟 _SECTOR_LABELS 一致），但 sector 欄位
    實際值可能是 _normalize_sector() 正規化後的 Title Case，也可能是尚未正規化的
    舊快取值，查表前統一轉成同一種 key 格式比對，兩種來源都能正確命中。
    """
    sec = sector_row.get("sector", "")
    key = sec.strip().lower().replace(" ", "_") if sec else sec
    return {**sector_row, "name": _INDUSTRY_TRANS.get(key, sec)}


def _with_ticker_label(holding: dict) -> dict:
    """附加 ticker 欄位：_TICKER_LABELS 有對應則顯示「中文名(代碼)」，查無對應表時回傳代碼原值。"""
    sym = holding.get("symbol", "")
    label = _TICKER_LABELS.get(sym)
    return {**holding, "ticker": f"{label}({sym})" if label else sym}

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
    """回傳 [{"symbol", "name", "ticker", "weight"}, ...]，失敗回傳空 list。"""
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
            sym    = str(row.get("Symbol") or row.get("symbol") or "").strip()
            name   = str(row.get("Name")   or row.get("name")   or sym).strip()
            wt     = float(row.get("Holding Percent") or row.get("holding percent") or 0)
            if sym and ticker:
                result.append({"symbol": sym, "name": name, "weight": wt})
        return result
    except Exception:
        return []


def _fetch_fund_sector_weightings(ticker: str) -> dict[str, float]:
    """回傳 ETF/基金整體產業配置權重 {sector: weight}，失敗回傳空 dict。"""
    try:
        fd = yf.Ticker(ticker).funds_data
        if fd is None:
            return {}
        sw = fd.sector_weightings
        if not sw:
            return {}
        result: dict[str, float] = {}
        for k, v in sw.items():
            sec = _normalize_sector(str(k))
            result[sec] = result.get(sec, 0.0) + float(v)
        return result
    except Exception:
        return {}


def _fetch_stock_sector(ticker: str) -> str | None:
    """回傳個股 sector（yfinance info.sector），失敗回傳 None。"""
    try:
        sector = yf.Ticker(ticker).info.get("sector")
        return _normalize_sector(str(sector)) if sector else None
    except Exception:
        return None


def get_fund_sector_weightings(ticker: str, cache: dict) -> dict[str, float]:
    """帶 cache 版本的 _fetch_fund_sector_weightings。"""
    key = f"sector::{ticker}"
    entry = cache.get(key)
    if entry is not None and time.time() - entry["cached_at"] <= _CACHE_TTL:
        return entry["data"]
    data = _fetch_fund_sector_weightings(ticker)
    cache[key] = {"cached_at": time.time(), "data": data}
    return data


def get_stock_sector(ticker: str, cache: dict) -> str | None:
    """帶 cache 版本的 _fetch_stock_sector。"""
    key = f"stocksector::{ticker}"
    entry = cache.get(key)
    if entry is not None and time.time() - entry["cached_at"] <= _CACHE_TTL:
        return entry["data"]
    data = _fetch_stock_sector(ticker)
    cache[key] = {"cached_at": time.time(), "data": data}
    return data


def _resolve_holdings(
    ticker: str,
    cache_get: "callable[[str], list[dict] | None]",
    cache_set: "callable[[str, list[dict]], None]",
    depth: int = 0,
) -> tuple[list[dict], str]:
    """
    取得 ETF/基金持股清單，storage-agnostic（由 cache_get/cache_set 決定快取後端）。
    偵測到包裝 ETF（單一持股 >90%）時自動往下鑽一層。

    Returns:
        (holdings, status_msg)
        status_msg 供 caller 顯示進度（terminal 或 logging）。
    """
    cached = cache_get(ticker)
    if cached is not None:
        return cached, "(cache)"

    holdings = _fetch_top_holdings(ticker)
    if not holdings:
        cache_set(ticker, [])
        return [], "無持股資料"

    if depth == 0 and len(holdings) == 1 and holdings[0]["weight"] > 0.90:
        inner = holdings[0]["symbol"]
        inner_cached = cache_get(inner)
        if inner_cached is not None:
            result = inner_cached
            msg = f"包裝 ETF: {ticker} → {inner}  (cache)"
        else:
            inner_holdings = _fetch_top_holdings(inner)
            cache_set(inner, inner_holdings)
            result = inner_holdings if inner_holdings else holdings
            msg = f"包裝 ETF: {ticker} → {inner}"
        cache_set(ticker, result)
        return result, msg

    cache_set(ticker, holdings)
    top_sum = sum(h["weight"] for h in holdings)
    return holdings, f"OK  {len(holdings)} 筆  coverage {top_sum * 100:.1f}%"


def get_holdings(ticker: str, cache: dict, depth: int = 0) -> tuple[list[dict], str]:
    """
    取得 ETF/基金持股清單（帶 file-based cache，TTL 7 天）。
    供 analyze_portfolio_exposures() 整組穿透使用。

    Returns:
        (holdings, status_msg)
    """
    return _resolve_holdings(
        ticker,
        cache_get=lambda k: _cache_get(cache, k),
        cache_set=lambda k, v: _cache_set(cache, k, v),
        depth=depth,
    )


# ── Public single-ticker query（SQLite 週度快照，供回測 holdings/sector 變化）───

def get_ticker_holdings(ticker: str) -> list[dict]:
    """
    取得單一 ETF/基金前十大持股（帶 SQLite 週度快照，同一 ISO 年週只抓一次）。

    Returns:
        [{"symbol": str, "name": str, "weight": float, "ticker": str}, ...]  最多 10 筆。
        "ticker"：_TICKER_LABELS 有對應則為「中文名(代碼)」，否則為代碼原值。
        個股或查無資料時回傳空 list。
    """
    t = ticker.upper()
    year, week, _ = date.today().isocalendar()
    holdings, _msg = _resolve_holdings(
        t,
        cache_get=lambda k: get_ticker_cache(k, "holdings", year, week),
        cache_set=lambda k, v: set_ticker_cache(k, "holdings", year, week, v),
    )
    return [_with_ticker_label(h) for h in holdings[:10]]


def get_ticker_sector(ticker: str) -> list[dict]:
    """
    取得單一標的產業配置（帶 SQLite 週度快照，同一 ISO 年週只抓一次）。

    ETF/基金：回傳 funds_data.sector_weightings 拆分後的清單（依權重排序）。
    個股：回傳單一 sector、weight 1.0 的清單。

    Returns:
        [{"sector": str, "weight": float, "name": str}, ...]  查無資料時回傳空 list。
        "name"：_INDUSTRY_TRANS 有對應則為中文翻譯，否則為 sector 原值。
    """
    t = ticker.upper()
    year, week, _ = date.today().isocalendar()

    cached = get_ticker_cache(t, "sector", year, week)
    if cached is not None:
        return [_with_industry_name(s) for s in cached]

    weightings = _fetch_fund_sector_weightings(t)
    if weightings:
        result = sorted(
            [{"sector": sec, "weight": round(w, 6)} for sec, w in weightings.items()],
            key=lambda x: x["weight"],
            reverse=True,
        )
    else:
        sector = _fetch_stock_sector(t)
        result = [{"sector": sector, "weight": 1.0}] if sector else []

    set_ticker_cache(t, "sector", year, week, result)
    return [_with_industry_name(s) for s in result]


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
            "sector_exposures": [],
            "identified_pct":   0.0,
            "unidentified_pct": 0.0,
        }

    for info in portfolio.values():
        info["port_weight"] = info["value"] / total_value

    # 2. 穿透持股
    exposures: dict[str, dict] = {}
    buckets:   list[dict]      = []
    sector_weights: dict[str, float] = {}
    cache = _load_cache()

    def _notify(ticker: str, pw: float, msg: str) -> None:
        if on_ticker:
            on_ticker(ticker, pw, msg)
        else:
            logging.info(f"[xray] {ticker}  {pw * 100:.2f}%  {msg}")

    for ticker, info in portfolio.items():
        pw = info["port_weight"]

        # sector 彙總：獨立於個股穿透，避免對每筆持股逐一呼叫 API
        # 這裡再正規化一次，讓已存在的舊 cache（尚未套用命名統一）也能立即彙總正確
        if info["sheet"] == "stocks":
            sector = _normalize_sector(get_stock_sector(ticker, cache)) or "未分類"
            sector_weights[sector] = sector_weights.get(sector, 0.0) + pw
        else:
            weightings = get_fund_sector_weightings(ticker, cache)
            if weightings:
                covered = 0.0
                for sec, w in weightings.items():
                    sec = _normalize_sector(sec)
                    sector_weights[sec] = sector_weights.get(sec, 0.0) + pw * w
                    covered += w
                leftover = max(0.0, 1.0 - covered)
                if leftover > 0.005:
                    sector_weights["未分類"] = sector_weights.get("未分類", 0.0) + pw * leftover
            else:
                sector_weights["未分類"] = sector_weights.get("未分類", 0.0) + pw

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

    sector_exposures = sorted(
        [
            _with_industry_name({"sector": sec, "weight": round(w, 6)})
            for sec, w in sector_weights.items()
        ],
        key=lambda x: x["weight"],
        reverse=True,
    )

    return {
        "total_value_twd":  total_value,
        "assets_count":     len(portfolio),
        "exposures": [
            _with_ticker_label({
                "symbol":  sym,
                "name":    info["name"],
                "weight":  round(info["weight"], 6),
                "sources": info["sources"],
            })
            for sym, info in ranked
        ],
        "buckets": merged_buckets,
        "sector_exposures": sector_exposures,
        "identified_pct":   round(identified, 6),
        "unidentified_pct": round(unidentified, 6),
    }
