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


def calculate_assets_data(exchange_rates):
    """資產價值核心計算"""
    results = []
    assets = get_assets()

    def process_asset(asset, category, price=None, change_val=None, update_time=None):
        rate = exchange_rates.get(asset["ccy"], 1.0)
        units = float(asset.get("units", asset.get("shares", 0)))
        if units == 0 and "investment" in asset:
            units = sum(i.get("units", i.get("shares", 0)) for i in asset["investment"])

        cost_origin = float(asset.get("cost", 0))
        if cost_origin == 0 and "investment" in asset:
            cost_origin = sum(i.get("cost", 0) for i in asset["investment"])

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
        }

    # 分開處理基金與 ETF 的價格抓取
    batch_prices = {}
    batch_changes = {}
    batch_times = {}

    def fetch_batch_prices(cat_key):
        tickers = []
        for asset in assets[cat_key].values():
            is_enabled = asset.get("enabled") is True or str(
                asset.get("enabled")
            ).upper() in ["TRUE", "1", "YES", "T"]
            is_get_val = asset.get("get_value") is True or str(
                asset.get("get_value")
            ).upper() in ["TRUE", "1", "YES", "T"]

            if is_enabled and is_get_val:
                tickers.append(asset["id"])

        if not tickers:
            return

        try:
            logging.info(f"正在抓取 {cat_key} 價格: {tickers}")
            hist_data = fetch_historical_data(tuple(tickers), period="1mo")

            for t in tickers:
                try:
                    df = None
                    if isinstance(hist_data.columns, pd.MultiIndex):
                        if t in hist_data.columns.get_level_values(0):
                            df = hist_data[t].copy()
                        else:
                            if len(tickers) == 1:
                                df = hist_data.copy()
                                df.columns = df.columns.get_level_values(1)
                    else:
                        df = hist_data.copy()

                    if df is not None and not df.empty and "Close" in df.columns:
                        close_s = df["Close"]
                        df_clean = close_s[close_s.notnull()].copy()

                        if not df_clean.empty:
                            last_val = df_clean.iloc[-1]
                            batch_prices[t] = (
                                float(last_val.iloc[0])
                                if isinstance(last_val, pd.Series)
                                else float(last_val)
                            )
                            try:
                                last_time = pd.to_datetime(df_clean.index[-1])
                                if last_time.tzinfo is None:
                                    last_time = last_time.tz_localize("UTC")
                                batch_times[t] = last_time.tz_convert(
                                    "Asia/Taipei"
                                ).strftime("%Y-%m-%d")
                            except Exception:
                                batch_times[t] = ""

                            if len(df_clean) >= 2:
                                prev_val = df_clean.iloc[-2]
                                p_val = (
                                    float(prev_val.iloc[0])
                                    if isinstance(prev_val, pd.Series)
                                    else float(prev_val)
                                )
                                batch_changes[t] = float(batch_prices[t] - p_val)
                except Exception as e:
                    logging.warning(f"解析 {t} 價格失敗: {e}")
        except Exception as e:
            logging.error(f"批次抓取 {cat_key} 失敗: {e}")

    fetch_batch_prices("etfs")
    fetch_batch_prices("stocks")
    fetch_batch_prices("funds")

    for cat_key, cat_name in [("etfs", "ETF"), ("stocks", "個股"), ("funds", "基金")]:
        for asset in assets[cat_key].values():
            if not asset.get("enabled", True):
                continue

            price, change_val, update_time = None, None, None
            if asset.get("get_value"):
                price = batch_prices.get(asset["id"])
                update_time = batch_times.get(asset["id"], "")
                # 無論是 ETF 還是個股，都讀取漲跌幅
                if cat_key in ["etfs", "stocks"]:
                    change_val = batch_changes.get(asset["id"])

            res = process_asset(asset, cat_name, price, change_val, update_time)
            if res:
                results.append(res)

    df = pd.DataFrame(results)
    if df.empty:
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
        ]
        return pd.DataFrame(columns=columns), {}

    total_val = df[COL_MARKET_VALUE].sum()
    df[COL_WEIGHT] = df[COL_MARKET_VALUE] / total_val * 100
    market_sum = df.groupby(COL_MARKET)[COL_MARKET_VALUE].sum()
    market_share = pd.DataFrame(
        {
            COL_MARKET_VALUE: market_sum,
            COL_WEIGHT: (market_sum / total_val * 100).round(1),
        }
    ).to_dict(orient="index")
    return df, market_share
