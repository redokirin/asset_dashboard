# -*- coding: utf-8 -*-
from core import data_loader


def test_clean_asset_rows_normalizes_numeric_bool_and_keys():
    rows = [
        {
            "Ticker": "VOO",
            "Name": "Vanguard S&P 500",
            "Shares": "1,234.5",
            "Cost": "",
            "Enabled": "TRUE",
            "Get_Value": "0",
            "Empty": "",
        },
        {"Ticker": "", "Name": "ignored"},
    ]

    result = data_loader._clean_asset_rows(
        rows,
        key_candidates=["Ticker", "ticker"],
        numeric_cols=["shares", "cost"],
        bool_cols=["enabled", "get_value"],
    )

    assert result == {
        "VOO": {
            "id": "VOO",
            "name": "Vanguard S&P 500",
            "shares": 1234.5,
            "cost": 0.0,
            "enabled": True,
            "get_value": False,
        }
    }


def test_clean_asset_rows_uses_fallback_key_candidate():
    result = data_loader._clean_asset_rows(
        [{"key": "FUND-A", "Units": "10", "Enabled": "YES"}],
        key_candidates=["Key", "key"],
        numeric_cols=["units"],
        bool_cols=["enabled"],
    )

    assert result["FUND-A"]["id"] == "FUND-A"
    assert result["FUND-A"]["units"] == 10.0
    assert result["FUND-A"]["enabled"] is True


def test_clean_asset_rows_invalid_numeric_becomes_zero():
    result = data_loader._clean_asset_rows(
        [{"Ticker": "2330.TW", "Shares": "not-a-number"}],
        key_candidates=["Ticker"],
        numeric_cols=["shares"],
        bool_cols=[],
    )

    assert result["2330.TW"]["shares"] == 0.0


def test_get_config_from_gsheets_returns_same_shape(monkeypatch):
    class FakeCredentials:
        @staticmethod
        def from_service_account_info(info, scopes):
            return object()

    class FakeWorksheet:
        def __init__(self, records):
            self.records = records

        def get_all_records(self):
            return self.records

    class FakeSheet:
        def worksheet(self, name):
            worksheets = {
                "radar_tickers": FakeWorksheet(
                    [{"Ticker": "USDTWD=X", "Name": "USD/TWD"}]
                ),
                "funds": FakeWorksheet(
                    [{"Key": "FUND-A", "Name": "Fund A", "Units": "2"}]
                ),
                "etfs": FakeWorksheet(
                    [{"Ticker": "VOO", "Shares": "3", "Enabled": "TRUE"}]
                ),
                "stocks": FakeWorksheet(
                    [{"Ticker": "2330.TW", "Cost": "1,000", "Get_Value": "FALSE"}]
                ),
            }
            return worksheets[name]

    class FakeGSpread:
        @staticmethod
        def authorize(creds):
            class FakeClient:
                @staticmethod
                def open_by_key(spreadsheet_id):
                    return FakeSheet()

            return FakeClient()

    monkeypatch.setattr(data_loader, "Credentials", FakeCredentials)
    monkeypatch.setattr(data_loader, "gspread", FakeGSpread)
    monkeypatch.setattr(
        data_loader,
        "get_secret",
        lambda key, default=None: {"client_email": "x"} if key == "gcp_service_account" else default,
    )

    config = data_loader.get_config_from_gsheets()

    assert config["radar_tickers"] == {"USDTWD=X": "USD/TWD"}
    assert config["funds"]["FUND-A"]["units"] == 2.0
    assert config["etfs"]["VOO"]["enabled"] is True
    assert config["stocks"]["2330.TW"]["cost"] == 1000.0
    assert config["stocks"]["2330.TW"]["get_value"] is False

