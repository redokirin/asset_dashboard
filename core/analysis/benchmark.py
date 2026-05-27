# -*- coding: utf-8 -*-


def get_smart_benchmark(ticker):
    """根據標的代碼判定最適合的基準目標 (Benchmark)"""
    ticker_upper = ticker.upper()
    if ticker_upper.endswith(".T") and any(
        pattern in ticker_upper for pattern in ["1655", "2558", "2521"]
    ):
        return "VOO"

    if ticker_upper.endswith(".T"):
        return "1306.T"

    if ticker_upper.endswith(".TW") or ticker_upper.endswith(".TWO"):
        return "0050.TW"

    return "VOO"
