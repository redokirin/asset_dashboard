# -*- coding: utf-8 -*-
import math
import logging
import pandas as pd
from core.columns import (
    COL_ASSET_TYPE,
    COL_AVG_COST,
    COL_BUY_LEVELS,
    COL_CHANGE,
    COL_COST,
    COL_CURRENCY,
    COL_GET_VALUE,
    COL_MARKET,
    COL_MARKET_VALUE,
    COL_NAME,
    COL_PRICE,
    COL_PROFIT_LOSS,
    COL_RETURN_PCT,
    COL_SETTLEMENT,
    COL_TICKER,
    COL_UNITS,
    COL_UPDATED_AT,
    COL_VALUE,
    COL_WEIGHT,
)
from core.data_loader import get_assets
from core.fetchers import fetch_historical_data


def calculate_tick_price(target_price, market_type):
    """計算符合市場規則的跳動價位 (Tick Size)"""
    if market_type == "TW_STOCK":
        ticks = [(10, 0.01), (50, 0.05), (100, 0.1), (500, 0.5), (1000, 1.0)]
        tick = 5.0
        for limit, t in ticks:
            if target_price < limit:
                tick = t
                break
        return math.floor(round(target_price / tick, 8)) * tick
    elif market_type in ["TW_ETF", "TW_ETF_HIGH"]:
        tick = 0.01 if target_price < 50 else 0.05
        return math.floor(round(target_price / tick, 8)) * tick
    return round(target_price, 2)


def exchange_rate(radar):
    """從雷達數據中提取匯率"""
    jpy_rate = next(
        (item[COL_VALUE] for item in radar if item[COL_TICKER] == "JPYTWD=X"), None
    )
    usd_rate = next(
        (item[COL_VALUE] for item in radar if item[COL_TICKER] == "USDTWD=X"), None
    )

    if jpy_rate is None:
        logging.warning("無法取得 JPY 匯率，啟用預設值 0.215！")
        jpy_rate = 0.215

    if usd_rate is None:
        logging.warning("無法取得 USD 匯率，啟用預設值 32.0！")
        usd_rate = 32.0

    return {
        "JPY": jpy_rate,
        "USD": usd_rate,
        "TWD": 1.0,
    }


def _is_enabled(value) -> bool:
    return value is True or str(value).upper() in ["TRUE", "1", "YES", "T"]


def _asset_units(asset):
    units = float(asset.get("units", asset.get("shares", 0)))
    if units == 0 and "investment" in asset:
        units = sum(i.get("units", i.get("shares", 0)) for i in asset["investment"])
    return units


def _asset_cost(asset):
    cost_origin = float(asset.get("cost", 0))
    if cost_origin == 0 and "investment" in asset:
        cost_origin = sum(i.get("cost", 0) for i in asset["investment"])
    return cost_origin


def calculate_asset_row(
    asset, category, exchange_rates, price=None, change_val=None, update_time=None
):
    rate = exchange_rates.get(asset["ccy"], 1.0)
    units = _asset_units(asset)
    cost_origin = _asset_cost(asset)
    avg_cost = cost_origin / units if units > 0 else 0
    current_price = price if price is not None else asset.get("nav", 0)

    val_twd, cost_twd = (current_price * units * rate), (cost_origin * rate)
    pl_val = val_twd - cost_twd

    return {
        COL_MARKET: asset["market"],
        COL_ASSET_TYPE: category,
        COL_NAME: asset["name"],
        COL_TICKER: asset["id"],
        COL_CURRENCY: asset["ccy"],
        COL_UNITS: units,
        COL_AVG_COST: avg_cost,
        COL_CHANGE: change_val,
        COL_PRICE: current_price,
        COL_UPDATED_AT: update_time or "",
        COL_COST: round(cost_twd),
        COL_MARKET_VALUE: round(val_twd),
        COL_PROFIT_LOSS: round(pl_val),
        COL_RETURN_PCT: (pl_val / cost_twd * 100) if cost_twd != 0 else 0,
        COL_GET_VALUE: asset.get("get_value", True),
        COL_SETTLEMENT: str(asset.get("settlement", "")).strip(),
        "region": str(asset.get("region", "")).strip(),
    }


def calculate_bank_row(asset, exchange_rates):
    ccy = str(asset.get("ccy", "TWD")).upper()
    rate = exchange_rates.get(ccy, 1.0)
    balance = float(asset.get("balance", 0))
    keep = float(asset.get("keep", 0))
    total = balance + keep
    keep_twd = round(keep * rate)

    return {
        COL_MARKET: asset.get("market", "Bank"),
        COL_ASSET_TYPE: "Bank",
        COL_NAME: asset.get("name", asset["id"]),
        COL_TICKER: asset["id"],
        COL_CURRENCY: ccy,
        COL_UNITS: total,
        COL_AVG_COST: 0,
        COL_CHANGE: None,
        COL_PRICE: 1,
        COL_UPDATED_AT: "",
        COL_COST: 0,
        COL_MARKET_VALUE: round(total * rate),
        COL_PROFIT_LOSS: 0,
        COL_RETURN_PCT: 0,
        COL_GET_VALUE: False,
        COL_SETTLEMENT: "",
        "keepTwd": keep_twd,
    }


def _empty_assets_frame():
    columns = [
        COL_MARKET,
        COL_ASSET_TYPE,
        COL_NAME,
        COL_TICKER,
        COL_CURRENCY,
        COL_UNITS,
        COL_AVG_COST,
        COL_CHANGE,
        COL_PRICE,
        COL_UPDATED_AT,
        COL_BUY_LEVELS,
        COL_COST,
        COL_MARKET_VALUE,
        COL_PROFIT_LOSS,
        COL_RETURN_PCT,
        COL_WEIGHT,
        COL_SETTLEMENT,
    ]
    return pd.DataFrame(columns=columns)


def calculate_market_share(df):
    total_val = df[COL_MARKET_VALUE].sum()
    df[COL_WEIGHT] = df[COL_MARKET_VALUE] / total_val * 100
    market_sum = df.groupby(COL_MARKET)[COL_MARKET_VALUE].sum()
    return pd.DataFrame(
        {
            COL_MARKET_VALUE: market_sum,
            COL_WEIGHT: (market_sum / total_val * 100).round(1),
        }
    ).to_dict(orient="index")


def _extract_ticker_history(hist_data, ticker, ticker_count):
    if isinstance(hist_data.columns, pd.MultiIndex):
        if ticker in hist_data.columns.get_level_values(0):
            return hist_data[ticker].copy()
        if ticker_count == 1:
            df = hist_data.copy()
            df.columns = df.columns.get_level_values(1)
            return df
        return None
    return hist_data.copy()


def fetch_batch_prices(assets, cat_key):
    batch_prices = {}
    batch_changes = {}
    batch_times = {}
    tickers = []
    for asset in assets.get(cat_key, {}).values():
        if _is_enabled(asset.get("enabled")) and _is_enabled(asset.get("get_value")):
            tickers.append(asset["id"])

    if not tickers:
        return batch_prices, batch_changes, batch_times

    try:
        logging.info(f"正在抓取 {cat_key} 價格: {tickers}")
        hist_data = fetch_historical_data(tuple(tickers), period="1mo")

        for ticker in tickers:
            try:
                df = _extract_ticker_history(hist_data, ticker, len(tickers))
                if df is None or df.empty or "Close" not in df.columns:
                    continue

                close_s = df["Close"]
                df_clean = close_s[close_s.notnull()].copy()
                if df_clean.empty:
                    continue

                last_val = df_clean.iloc[-1]
                batch_prices[ticker] = (
                    float(last_val.iloc[0])
                    if isinstance(last_val, pd.Series)
                    else float(last_val)
                )
                try:
                    last_time = pd.to_datetime(df_clean.index[-1])
                    if last_time.tzinfo is None:
                        last_time = last_time.tz_localize("UTC")
                    batch_times[ticker] = last_time.tz_convert("Asia/Taipei").strftime(
                        "%Y-%m-%d"
                    )
                except Exception:
                    batch_times[ticker] = ""

                if len(df_clean) >= 2:
                    prev_val = df_clean.iloc[-2]
                    p_val = (
                        float(prev_val.iloc[0])
                        if isinstance(prev_val, pd.Series)
                        else float(prev_val)
                    )
                    batch_changes[ticker] = float(batch_prices[ticker] - p_val)
            except Exception as e:
                logging.warning(f"解析 {ticker} 價格失敗: {e}")
    except Exception as e:
        logging.error(f"批次抓取 {cat_key} 失敗: {e}")

    return batch_prices, batch_changes, batch_times


def calculate_assets_data(exchange_rates):
    """資產價值核心計算"""
    results = []
    assets = get_assets()

    batch_prices = {}
    batch_changes = {}
    batch_times = {}
    for cat_key in ["etfs", "stocks", "funds"]:
        prices, changes, times = fetch_batch_prices(assets, cat_key)
        batch_prices.update(prices)
        batch_changes.update(changes)
        batch_times.update(times)

    for cat_key, cat_name in [("etfs", "ETF"), ("stocks", "個股"), ("funds", "基金")]:
        for asset in assets.get(cat_key, {}).values():
            if not _is_enabled(asset.get("enabled", True)):
                continue

            price, change_val, update_time = None, None, None
            if _is_enabled(asset.get("get_value", True)):
                price = batch_prices.get(asset["id"])
                update_time = batch_times.get(asset["id"], "")
                # 無論是 ETF 還是個股，都讀取漲跌幅
                # if cat_key in ["etfs", "stocks"]:
                change_val = batch_changes.get(asset["id"])

            res = calculate_asset_row(
                asset, cat_name, exchange_rates, price, change_val, update_time
            )
            if res:
                results.append(res)

    for asset in assets.get("banks", {}).values():
        if not _is_enabled(asset.get("enabled", True)):
            continue
        results.append(calculate_bank_row(asset, exchange_rates))

    df = pd.DataFrame(results)
    if df.empty:
        return _empty_assets_frame(), {}

    market_share = calculate_market_share(df)
    return df, market_share
