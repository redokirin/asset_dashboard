# -*- coding: utf-8 -*-
# --- Demo 專用資產數據配置區 ---
# 此檔案用於功能演示，數值皆為隨機產出的範例數據

ASSETS = {
    "funds": {
        "DEMO-FUND-001": {
            "market": "日股",
            "id": "DEMO-FUND-001",
            "name": "範例全球成長基金",
            "ccy": "JPY",
            "nav": 15200.50,
            "investment": [
                {"units": 10.5, "cost": 100000},
                {"units": 5.2, "cost": 60000},
            ],
        },
        "DEMO-FUND-002": {
            "market": "台股",
            "id": "DEMO-FUND-002",
            "name": "演示型科技平衡基金",
            "ccy": "TWD",
            "nav": 58.2,
            "investment": [
                {"units": 1500.0, "cost": 85000},
            ],
        },
    },
    "etfs": {
        "VT.US": {
            "market": "美股",
            "id": "VT",
            "name": "Vanguard 全球股票 ETF",
            "ccy": "USD",
            "investment": [
                {"shares": 50, "cost": 4500},
                {"shares": 30, "cost": 3100},
            ],
        },
        "0050.TW": {
            "market": "台股",
            "id": "0050.TW",
            "name": "元大台灣50 (Demo)",
            "ccy": "TWD",
            "investment": [
                {"shares": 2000, "cost": 150000},
            ],
        },
        "BTC-EXAMPLE": {
            "market": "加密貨幣",
            "id": "BTC",
            "name": "比特幣範例資產",
            "ccy": "USD",
            "investment": [
                {"shares": 0.1, "cost": 6500},
            ],
        },
    },
}

# 監控雷達配置：用於顯示市場大盤走勢
RADAR_TICKERS = {
    "^TWII": "台股大盤",
    "^GSPC": "標普 500 指數",
    "2330.TW": "台積電",
    "JPYTWD=X": "日圓/台幣匯率",
    "USDTWD=X": "美元/台幣匯率",
    "BTC-USD": "比特幣價格",
}
