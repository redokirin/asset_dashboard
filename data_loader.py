# -*- coding: utf-8 -*-
import gspread
import tomllib
import logging
from pathlib import Path
from google.oauth2.service_account import Credentials

# --- 配置與路徑 ---
CREDENTIALS_PATH = Path(__file__).parent / "credentials.json"


def get_secret(key, default=None):
    """安全地讀取 Secrets，避免本地端報錯"""
    try:
        import streamlit as st

        return st.secrets.get(key, default)
    except Exception:
        return default


SPREADSHEET_ID = get_secret(
    "spreadsheet_id", "1xiuVw0fuuIdqVX0a-gGf0MkEZWmwWGnsRndCoNEc-4A"
)


def get_config_from_gsheets():
    """從 Google Sheets 讀取資產配置，支援本地檔案與 Streamlit Secrets"""
    creds = None

    # 1. 優先嘗試從 Streamlit Secrets 讀取 (適合 Cloud 部署)
    gcp_info = get_secret("gcp_service_account")
    if gcp_info:
        try:
            creds_info = gcp_info
            if hasattr(creds_info, "to_dict"):
                creds_info = creds_info.to_dict()
            else:
                creds_info = dict(creds_info)

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
            logging.info("使用 Streamlit Secrets 載入 Google 憑證")
        except Exception as e:
            logging.error(f"從 Secrets 載入憑證失敗: {e}")

    # 2. 如果 Secrets 沒有，嘗試讀取本地檔案 (適合本地開發)
    if not creds and CREDENTIALS_PATH.exists():
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = Credentials.from_service_account_file(
                str(CREDENTIALS_PATH), scopes=scopes
            )
            logging.info("使用本地 credentials.json 載入 Google 憑證")
        except Exception as e:
            logging.error(f"從本地檔案載入憑證失敗: {e}")

    if not creds:
        logging.warning("找不到有效的 Google 憑證 (Secrets 或本地檔案)")
        return None

    try:
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SPREADSHEET_ID)

        config = {}

        # 1. 讀取 radar_tickers
        try:
            ws_radar = sh.worksheet("radar_tickers")
            radar_data = ws_radar.get_all_records()
            config["radar_tickers"] = {
                row["Ticker"]: row["Name"] for row in radar_data if row["Ticker"]
            }
        except Exception as e:
            logging.error(f"讀取 radar_tickers 分頁失敗: {e}")

        # 2. 讀取 funds (以 Key 為索引)
        try:
            ws_funds = sh.worksheet("funds")
            funds_data = ws_funds.get_all_records()
            funds_dict = {}
            numeric_cols = ["nav", "units", "cost", "shares"]
            bool_cols = ["enabled", "get_value"]
            for row in funds_data:
                key = str(row.pop("Key", "") or row.pop("key", "")).strip()
                if key:
                    cleaned_row = {}
                    cleaned_row["id"] = key
                    for k, v in row.items():
                        low_k = k.lower()
                        if low_k in numeric_cols:
                            try:
                                cleaned_row[low_k] = (
                                    float(str(v).replace(",", "")) if v != "" else 0.0
                                )
                            except:
                                cleaned_row[low_k] = 0.0
                        elif low_k in bool_cols:
                            val_str = str(v).upper()
                            cleaned_row[low_k] = val_str in ["TRUE", "1", "YES", "T"]
                        elif v != "":
                            cleaned_row[low_k] = v
                    funds_dict[key] = cleaned_row
            config["funds"] = funds_dict
        except Exception as e:
            logging.error(f"讀取 funds 分頁失敗: {e}")

        # 3. 讀取 etfs (以 Ticker 為索引)
        try:
            ws_etfs = sh.worksheet("etfs")
            etfs_data = ws_etfs.get_all_records()
            etfs_dict = {}
            numeric_cols = ["shares", "cost", "discount", "units"]
            bool_cols = ["enabled", "get_value"]
            for row in etfs_data:
                ticker_key = str(row.pop("Ticker", "") or row.pop("ticker", "")).strip()
                if ticker_key:
                    cleaned_row = {}
                    cleaned_row["id"] = ticker_key
                    for k, v in row.items():
                        low_k = k.lower()
                        if low_k in numeric_cols:
                            try:
                                cleaned_row[low_k] = (
                                    float(str(v).replace(",", "")) if v != "" else 0.0
                                )
                            except:
                                cleaned_row[low_k] = 0.0
                        elif low_k in bool_cols:
                            val_str = str(v).upper()
                            cleaned_row[low_k] = val_str in ["TRUE", "1", "YES", "T"]
                        elif v != "":
                            cleaned_row[low_k] = v
                    etfs_dict[ticker_key] = cleaned_row
            config["etfs"] = etfs_dict
        except Exception as e:
            logging.error(f"讀取 etfs 分頁失敗: {e}")

        # 4. 讀取 stocks (以 Ticker 為索引)
        try:
            ws_stocks = sh.worksheet("stocks")
            stocks_data = ws_stocks.get_all_records()
            stocks_dict = {}
            numeric_cols = ["shares", "cost", "discount", "units"]
            bool_cols = ["enabled", "get_value"]
            for row in stocks_data:
                ticker_key = str(row.pop("Ticker", "") or row.pop("ticker", "")).strip()
                if ticker_key:
                    cleaned_row = {}
                    cleaned_row["id"] = ticker_key
                    for k, v in row.items():
                        low_k = k.lower()
                        if low_k in numeric_cols:
                            try:
                                cleaned_row[low_k] = (
                                    float(str(v).replace(",", "")) if v != "" else 0.0
                                )
                            except:
                                cleaned_row[low_k] = 0.0
                        elif low_k in bool_cols:
                            val_str = str(v).upper()
                            cleaned_row[low_k] = val_str in ["TRUE", "1", "YES", "T"]
                        elif v != "":
                            cleaned_row[low_k] = v
                    stocks_dict[ticker_key] = cleaned_row
            config["stocks"] = stocks_dict
        except Exception as e:
            logging.error(f"讀取 stocks 分頁失敗: {e}")

        return config
    except Exception as e:
        logging.error(f"Google Sheets 讀取失敗: {e}")
        return None


def get_config():
    """
    讀取資產配置。
    邏輯：優先載入本地或 Secrets 的基礎設定（如 app_password），
    再由 Google Sheets 更新資產與雷達清單。
    """
    config = {}

    # 1. 嘗試讀取本地 assets_config.toml
    current_dir = Path(__file__).parent
    toml_path = current_dir / "assets_config.toml"
    if toml_path.exists():
        try:
            with open(toml_path, "rb") as f:
                toml_data = tomllib.load(f)
                config = dict(toml_data.get("my_assets", {}))
        except Exception as e:
            logging.error(f"本地配置讀取失敗: {e}")

    # 2. 如果本地沒讀到關鍵設定，嘗試從 Streamlit Secrets 讀取
    if not config.get("app_password"):
        try:
            secrets_data = get_secret("my_assets")
            if secrets_data:
                if hasattr(secrets_data, "to_dict"):
                    config.update(secrets_data.to_dict())
                else:
                    config.update(dict(secrets_data))
        except Exception as e:
            logging.error(f"Secrets 讀取失敗: {e}")

    # 3. 嘗試從 Google Sheets 讀取資產數據並合併
    gs_config = get_config_from_gsheets()
    if gs_config:
        # 用 GS 的內容更新資產清單與雷達清單，保留基礎設定
        config.update(gs_config)

    if not config:
        logging.error(
            "🚨 配置缺失：未偵測到 assets_config.toml 或 st.secrets['my_assets']"
        )

    return config


def _ensure_id(config_dict):
    """增加防呆機制：如果項目中沒有定義 id，則以 Key 為預設 id"""
    result = {}
    if not isinstance(config_dict, dict):
        return result
    for key, val in config_dict.items():
        if not isinstance(val, dict):
            continue
        if "id" not in val:
            val["id"] = key
        result[key] = val
    return result


def get_assets():
    """獲取最新的資產配置"""
    config = get_config()
    return {
        "etfs": _ensure_id(config.get("etfs", {})),
        "stocks": _ensure_id(config.get("stocks", {})),
        "funds": _ensure_id(config.get("funds", {})),
    }


def get_radar_tickers():
    """獲取最新的雷達標的"""
    return get_config().get("radar_tickers", {})
