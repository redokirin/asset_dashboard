import argparse
import os
import pandas as pd
import dashboard_logic
from dashboard_ui import show_console_rich


def run_cli():
    """CLI 模式主進入點"""
    parser = argparse.ArgumentParser(description="全球資產即時監控 (命令列模式)")
    parser.add_argument("--ai", action="store_true", help="導出為 AI 分析用格式")
    parser.add_argument(
        "--analyze", action="store_true", help="執行進階量化分析 (RS & Alpha)"
    )
    parser.add_argument("--report", action="store_true", help="顯示資產明細報表")
    parser.add_argument(
        "--code", type=str, nargs="+", help="指定一個或多個代碼進行分析"
    )
    args, _ = parser.parse_known_args()

    # 若未特別指示，預設給出預設報表模式
    if not any([args.ai, args.analyze, args.report]):
        args.report = True

    radar = dashboard_logic.get_market_radar_data()
    exchange_rates = dashboard_logic.exchange_rate(radar)
    df_res, market_share_data = dashboard_logic.calculate_assets_data(exchange_rates)

    if args.code:
        df_to_analyze = df_res[df_res["代碼"].isin(args.code)].copy()
        existing_codes = df_res["代碼"].tolist()
        for c in args.code:
            if c not in existing_codes:
                mock_record = {
                    "市場": "自選",
                    "類型": "ETF",
                    "名稱": c,
                    "代碼": c,
                    "幣別": "TWD",
                    "單位數": 0,
                    "平均成本": 0.0,
                    "股價": 0.0,
                    "漲跌": None,
                    # "建議掛單": 0.0,
                    "成本": 0,
                    "市值": 0,
                    "損益": 0,
                    "報酬率": 0.0,
                    "佔比": 100.0,
                }
                df_to_analyze = pd.concat(
                    [df_to_analyze, pd.DataFrame([mock_record])], ignore_index=True
                )
        df_final = df_to_analyze
    else:
        df_final = df_res

    # 判斷是否需要執行進階分析
    advanced_results = (
        dashboard_logic.run_advanced_analysis(df_final) if args.analyze else None
    )

    # 當同時指定 --ai 與 --analyze 時，寫入整合後的 AI 報告檔案 ai_report.md
    if args.ai and args.analyze:
        ai_text = dashboard_logic.export_for_ai(df_final, adv_res=advanced_results)
        with open("ai_report.md", "w", encoding="utf-8") as f:
            f.write(ai_text)
        print(f"\n✅ AI 摘要與量化分析結果已合併寫入檔案: ai_report.md")
    elif args.ai:
        print(dashboard_logic.export_for_ai(df_final, adv_res=advanced_results))
    else:
        show_console_rich(
            df_final,
            radar,
            market_share_data,
            advanced_results,
            show_report=args.report,
        )


if __name__ == "__main__":
    run_cli()
