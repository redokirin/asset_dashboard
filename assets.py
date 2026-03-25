# -*- coding: utf-8 -*-
# --- 資產數據配置區 ---
ASSETS = {
    "funds": {
        "18488469A": {
            "market": "台股",
            "get_value": True,
            "id": "0P00006AKV.TW",
            "isin": "TW000T3207Y5",
            "name": "野村中小基金",
            "ccy": "TWD",
            "nav": 412.43,
            "investment": [
                {"units": 653.99889, "cost": 109708},
            ],
        },
        "00910007": {
            "market": "日股",
            "get_value": True,
            "id": "0P0001CGLL.T",
            "isin": "IE00BF4KRV02",
            "name": "野村日本策略價值基金",
            "ccy": "JPY",
            "nav": 25044.1906,
            "investment": [
                {"units": 1.9341, "cost": 50000},  # 01/23
                {"units": 5.8022, "cost": 150000},  # 02/23
                {"units": 11.8288, "cost": 300000},  # 01/27
                {"units": 12.5506, "cost": 350000},  # 02/10
                {"units": 13.2878, "cost": 350000},  # 03/10
            ],
        },
        "00010044": {
            "market": "日股",
            "get_value": False,
            "id": "00010044",
            "isin": "LU0235639324",
            "name": "JPM日本股票基金",
            "ccy": "JPY",
            "nav": 3006.0000,
            "investment": [
                {"units": 68.587, "cost": 200000},  # 02/02
                {"units": 46.714, "cost": 150000},  # 02/10
                {"units": 49.62, "cost": 150000},  # 03/10
            ],
        },
    },
    "etfs": {
        "1655.T": {
            "market": "美股",
            "market_type": "JP_ETF",
            "discount": 0.995,
            "get_value": True,
            "id": "1655.T",
            "name": "iShares S&P 500 ETF",
            "ccy": "JPY",
            "investment": [
                {"shares": 500, "cost": 382397},  # 02/12
                {"shares": 200, "cost": 150000},  # 02/23
                {"shares": 300, "cost": 225750},  # 03/09
                {"shares": 300, "cost": 229200},  # 03/16
                {"shares": 500, "cost": 383000},  # 03/17
                {"shares": 400, "cost": 304400},  # 03/19
            ],
        },
        "00985A.TW": {
            "market": "台股",
            "market_type": "TW_ETF",
            "discount": 0.990,
            "get_value": True,
            "id": "00985A.TW",
            "name": "野村臺灣增強50主動式ETF",
            "ccy": "TWD",
            "investment": [
                {"shares": 1000, "cost": 15096},  # 02/09
                {"shares": 1000, "cost": 16390},  # 03/03
                {"shares": 1000, "cost": 15130},  # 03/09
                {"shares": 1000, "cost": 15460},  # 03/10
            ],
        },
        "0052": {
            "market": "台股",
            "market_type": "TW_ETF",
            "discount": 0.985,
            "get_value": True,
            "id": "0052.TW",
            "name": "富邦科技",
            "ccy": "TWD",
            "investment": [
                {"shares": 1000, "cost": 46600},  # 02/23
                {"shares": 1000, "cost": 47600},  # 03/03
                {"shares": 1000, "cost": 46630},  # 03/05
                {"shares": 1000, "cost": 43400},  # 03/09
            ],
        },
        "2409": {
            "market": "台股",
            "market_type": "TW_ETF",
            "discount": 0.985,
            "get_value": True,
            "id": "2409.TW",
            "name": "友達",
            "ccy": "TWD",
            "investment": [
                {"shares": 1000, "cost": 15650},  # 03/03
                {"shares": 1000, "cost": 15200},  # 03/04
            ],
        },
        "2330": {
            "market": "台股",
            "market_type": "TW_ETF_HIGH",
            "discount": 0.980,
            "get_value": True,
            "id": "2330.TW",
            "name": "台積電",
            "ccy": "TWD",
            "investment": [
                {"shares": 1, "cost": 1880},  # 03/04
            ],
        },
    },
}
