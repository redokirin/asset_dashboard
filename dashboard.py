# -*- coding: utf-8 -*-
import sys
from dashboard_logic import (
    get_exchange_rate,
    get_market_radar_data,
    calculate_assets_data,
    get_rs_percentile_rank,
    run_alpha_analysis,
    export_for_ai,
)
from dashboard_ui import (
    CURRENT_ENV,
    HAS_RICH,
    show_streamlit,
    show_console_rich,
    show_jupyter,
)

if __name__ == "__main__":
    alpha_results = run_alpha_analysis() if "--alpha" in sys.argv else None
    radar = get_market_radar_data()
    exchange_rates = {
        "JPY": next(
            (item["數值"] for item in radar if item["代碼"] == "JPYTWD=X"), 0.215
        ),
        "USD": next(
            (item["數值"] for item in radar if item["代碼"] == "USDTWD=X"), 32.0
        ),
        "TWD": 1,
    }
    df_res, market_share_data = calculate_assets_data(exchange_rates)

    # 跨市場 RS 分析 (選用)
    rs_results = None
    if "--rs" in sys.argv:
        # 只處理 ASSETS[etfs] 且在 df_res 中成功抓取到數據的標的
        active_tickers = df_res[df_res["類型"] == "ETF"]["代碼"].tolist()
        if active_tickers:
            rs_results = get_rs_percentile_rank(active_tickers)
        else:
            print("警告：沒有適合進行 RS 分析的 Ticker (例如 .TW 或 .T)")

    if "--ai" in sys.argv:
        export_for_ai(df_res)
    else:
        if CURRENT_ENV == "streamlit":
            show_streamlit(df_res, radar, market_share_data)
        elif CURRENT_ENV == "jupyter":
            show_jupyter(
                df_res,
                radar,
                exchange_rates,
                market_share_data,
            )
        elif HAS_RICH:
            show_console_rich(
                df_res, radar, market_share_data, alpha_results, rs_results
            )
        else:
            print(df_res.to_string())
