import argparse
import pandas as pd
import dashboard_logic
from dashboard_ui import show_console_rich

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="全球資產即時監控 (命令列模式)")
    parser.add_argument("--ai", action="store_true", help="導出為 AI 分析用格式")
    parser.add_argument(
        "--analyze", action="store_true", help="執行進階量化分析 (RS & Alpha)"
    )
    parser.add_argument("--report", action="store_true", help="顯示資產明細報表")
    parser.add_argument(
        "--code", type=str, help="指定單一股票代碼進行分析 (例如: 2330.TW, AAPL)"
    )
    args, _ = parser.parse_known_args()

    # 若未特別指示，預設給出預設報表模式
    if not any([args.ai, args.analyze, args.report]):
        args.report = True

    radar = dashboard_logic.get_market_radar_data()
    exchange_rates = dashboard_logic.exchange_rate(radar)
    df_res, market_share_data = dashboard_logic.calculate_assets_data(exchange_rates)

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
        dashboard_logic.export_for_ai(df_res)
    else:
        advanced_results = dashboard_logic.run_advanced_analysis(df_res) if args.analyze else None
        show_console_rich(
            df_res,
            radar,
            market_share_data,
            advanced_results,
            show_report=args.report,
        )
