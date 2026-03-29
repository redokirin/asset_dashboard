import argparse
import pandas as pd
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
    parser.add_argument("--analyze", action="store_true", help="執行進階量化分析")
    parser.add_argument("--report", action="store_true", help="顯示資產明細報表")
    parser.add_argument(
        "--code", type=str, help="指定單一股票代碼進行分析 (例如: 2330.TW, AAPL)"
    )
    args, _ = parser.parse_known_args()

    # 針對 Streamlit 優先執行頁面設定 (必須是第一個 st 指令)
    if CURRENT_ENV == "streamlit":
        import streamlit as st

        st.set_page_config(page_title="全球資產看板", layout="wide")

    # 若未特別指示，預設給出預設報表模式
    if not any([args.ai, args.analyze, args.report]):
        args.report = True

    radar = get_market_radar_data()
    exchange_rates = exchange_rate(radar)

    df_res, market_share_data = calculate_assets_data(exchange_rates)

    if args.code:
        code = args.code.upper()
        if code in df_res["代碼"].values:
            df_res = df_res[df_res["代碼"] == code].copy()
        else:
            mock_record = {
                "市場": "自選",
                "類型": "ETF",
                "名稱": code,
                "代碼": code,
                "幣別": "TWD",
                "單位數": 0,
                "平均成本": 0.0,
                "漲跌": None,
                "股價": 0.0,
                "建議掛單": 0.0,
                "成本": 0,
                "市值": 0,
                "損益": 0,
                "報酬率": 0.0,
                "佔比": 100.0,
            }
            df_res = pd.DataFrame([mock_record])

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
                df_res,
                radar,
                market_share_data,
                advanced_results,
                show_report=args.report,
            )
        else:
            print(df_res.to_string())
