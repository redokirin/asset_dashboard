# -*- coding: utf-8 -*-
# --- 資產數據配置區 ---
ASSETS = {
    "funds": {
        "18488469A": {
            "market": "台股",
            "enabled": True,
            "get_value": True,
            "id": "0P00006AKV.TW",
            "isin": "TW000T3207Y5",
            "name": "野村中小基金",
            "ccy": "TWD",
            "nav": 387.98,
            # "value": 223160,
            "units": 412.01931,
            "cost": 68116,
            # "investment": [
            #     {"units": 653.99889, "cost": 109708},
            # ],
        },
        "00910007": {
            "market": "日股",
            "enabled": True,
            "get_value": True,
            "id": "0P0001CGLL.T",
            "isin": "IE00BF4KRV02",
            "name": "野村日本策略價值基金",
            "ccy": "JPY",
            "nav": 25171.2972,
            "units": 45.4035,
            "cost": 1200000,
            # "investment": [
            #     {"units": 1.9341, "cost": 50000},  # 01/23
            #     {"units": 5.8022, "cost": 150000},  # 02/23
            #     {"units": 11.8288, "cost": 300000},  # 01/27
            #     {"units": 12.5506, "cost": 350000},  # 02/10
            #     {"units": 13.2878, "cost": 350000},  # 03/10
            # ],
        },
        "00010044": {
            "market": "日股",
            "enabled": True,
            "get_value": False,
            "id": "00010044",
            "isin": "LU0235639324",
            "name": "JPM日本股票基金",
            "ccy": "JPY",
            "nav": 2990.0000,
            "units": 164.921,
            "cost": 500000,
            # "investment": [
            #     {"units": 68.587, "cost": 200000},  # 02/02
            #     {"units": 46.714, "cost": 150000},  # 02/10
            #     {"units": 49.62, "cost": 150000},   # 03/10
            # ],
        },
    },
    "etfs": {
        "1655.T": {
            "market": "美股",
            "enabled": True,
            "market_type": "JP_ETF",
            "discount": 0.995,
            "get_value": True,
            "id": "1655.T",
            "name": "iShares S&P 500",
            "ccy": "JPY",
            "shares": 2200,
            "cost": 1674747,
            # "investment": [
            #     {"shares": 500, "cost": 765},   # 02/12
            #     {"shares": 200, "cost": 750},   # 02/23
            #     {"shares": 300, "cost": 752.5}, # 03/09
            #     {"shares": 300, "cost": 764},   # 03/16
            #     {"shares": 500, "cost": 766},   # 03/17
            #     {"shares": 400, "cost": 761},   # 03/19
            # ],
        },
        "1306.T": {
            "market": "日股",
            "enabled": True,
            "market_type": "JP_ETF",
            "discount": 0.995,
            "get_value": True,
            "id": "1306.T",
            "name": "NextFunds東證股價指數",
            "ccy": "JPY",
            "shares": 100,
            "cost": 378500,
            # "investment": [
            #     {"shares": 100, "cost": 3785},   # 03/27
            # ]
        },
        "00985A.TW": {
            "market": "台股",
            "enabled": True,
            "market_type": "TW_ETF",
            "discount": 0.990,
            "get_value": True,
            "id": "00985A.TW",
            "name": "主動野村台灣50",
            "ccy": "TWD",
            "shares": 5000,
            "cost": 78020,
            # "investment": [
            #     {"shares": 1000, "cost": 15.09},  # 02/09
            #     {"shares": 1000, "cost": 16.39},  # 03/03
            #     {"shares": 1000, "cost": 15.13},  # 03/09
            #     {"shares": 1000, "cost": 15.46},  # 03/10
            #     {"shares": 1000, "cost": 15.95},  # 03/10
            # ],
        },
        "00981A.TW": {
            "market": "台股",
            "enabled": True,
            "market_type": "TW_ETF",
            "discount": 0.990,
            "get_value": True,
            "id": "00981A.TW",
            "name": "主動統一台股增長",
            "ccy": "TWD",
            "shares": 1000,
            "cost": 19950,
            # "investment": [
            #     {"shares": 1000, "cost": 19.95},  # 03/24
            # ],
        },
        "0052": {
            "market": "台股",
            "enabled": True,
            "market_type": "TW_ETF",
            "discount": 0.985,
            "get_value": True,
            "id": "0052.TW",
            "name": "富邦科技",
            "ccy": "TWD",
            "shares": 4000,
            "cost": 184200,
            # "investment": [
            #     {"shares": 1000, "cost": 46.6},  # 02/23
            #     {"shares": 1000, "cost": 47.6},  # 03/03
            #     {"shares": 1000, "cost": 46.6},  # 03/05
            #     {"shares": 1000, "cost": 43.4},  # 03/09
            # ],
        },
        "2409": {
            "market": "台股",
            "enabled": True,
            "market_type": "TW_ETF",
            "discount": 0.985,
            "get_value": True,
            "id": "2409.TW",
            "name": "友達光電",
            "ccy": "TWD",
            "shares": 2000,
            "cost": 30850,
            # "investment": [
            #     {"shares": 1000, "cost": 15.65},  # 03/03
            #     {"shares": 1000, "cost": 15.20},  # 03/04
            # ],
        },
        "2330": {
            "market": "台股",
            "enabled": True,
            "market_type": "TW_ETF_HIGH",
            "discount": 0.980,
            "get_value": True,
            "id": "2330.TW",
            "name": "台積電",
            "ccy": "TWD",
            "shares": 1,
            "cost": 1880,
            # "investment": [
            #     {"shares": 1, "cost": 1880},  # 03/04
            # ],
        },
    },
}

RADAR_TICKERS = {
    "^TWII": "台灣加權指數",
    "ES=F": "S&P500 期貨",
    "VOO": "VOO",
    "2330.TW": "台積電",
    "JPY=X": "美元/日圓",
    "JPYTWD=X": "日圓/台幣",
    # "0P0001CGLL.T": "野村日本策略價值基金",
    # "0P00006AKV.TW": "野村中小基金",
}

# Alpha 穩定性分析配置
ALPHA_ANALYSIS = [
    {
        "target": ["0052.TW", "00985A.TW", "00981A.TW", "00992A.TW"],
        "benchmark": "0050.TW",
        "start": "2025-12-01",  # 00985A 上市日期
        "name": ["富邦科技", "野村臺灣增強50", "統一台股增長", "群益台灣科技創新"],
    },
]
