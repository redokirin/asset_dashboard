# -*- coding: utf-8 -*-
import argparse
from dashboard_logic import (
    get_market_radar_data,
    calculate_assets_data,
    run_advanced_analysis,
    export_for_ai,
    exchange_rate,
)
from dashboard_ui import (
    CURRENT_ENV,
    HAS_RICH,
    show_streamlit,
    show_console_rich,
    show_jupyter,
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="全球資產即時監控面板")
    parser.add_argument("--ai", action="store_true", help="導出為 AI 分析用格式")
    parser.add_argument("--analyze", action="store_true", help="執行進階量化分析 (RS & Alpha)")
    parser.add_argument("--report", action="store_true", help="顯示資產明細報表")
    args, _ = parser.parse_known_args()

    # 若未特別指示，預設給出預設報表模式
    if not any([args.ai, args.analyze, args.report]):
        args.report = True

    radar = get_market_radar_data()
    exchange_rates = exchange_rate(radar)

    df_res, market_share_data = calculate_assets_data(exchange_rates)

    if args.ai:
        export_for_ai(df_res)
    else:
        if CURRENT_ENV == "streamlit":
            show_streamlit(df_res, radar)
        elif CURRENT_ENV == "jupyter":
            show_jupyter(df_res, radar, exchange_rates)
        elif HAS_RICH:
            advanced_results = run_advanced_analysis(df_res) if args.analyze else None

            show_console_rich(
                df_res, radar, market_share_data, advanced_results, show_report=args.report
            )
        else:
            print(df_res.to_string())
