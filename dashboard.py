# -*- coding: utf-8 -*-
import sys
import argparse
import pandas as pd
import dashboard_logic
from dashboard_ui import plot_asset_allocation, show_jupyter, show_console_rich


def get_env():
    # 檢查是否在 Jupyter Notebook
    try:
        from IPython.core.getipython import get_ipython

        if get_ipython().__class__.__name__ == "ZMQInteractiveShell":
            return "jupyter"
    except Exception:
        pass

    # 檢查是否由 Streamlit 啟動 (雖然建議改用 streamlit run dashboard_st.py)
    if "streamlit" in " ".join(sys.argv).lower():
        return "streamlit"

    return "console"


if __name__ == "__main__":
    env = get_env()

    if env == "streamlit":
        # 如果用戶仍然用 streamlit run dashboard.py 執行，則導向新的進入點
        import runpy

        runpy.run_path("dashboard_st.py", run_name="__main__")
        sys.exit()

    # 原有的 argparse (與 CLI 共用)
    parser = argparse.ArgumentParser(description="全球資產監控分流器")
    parser.add_argument("--ai", action="store_true")
    parser.add_argument("--analyze", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument(
        "--code", type=str, nargs="+", help="指定一個或多個代碼進行分析"
    )
    args, _ = parser.parse_known_args()

    if not any([args.ai, args.analyze, args.report]):
        args.report = True

    # 數據獲取
    radar = dashboard_logic.get_market_radar_data()
    exchange_rates = dashboard_logic.exchange_rate(radar)
    df_res, market_share_data = dashboard_logic.calculate_assets_data(exchange_rates)

    if env == "jupyter":
        # 針對 Jupyter 的特殊處理 (現有分析 Notebook 常用)
        print("--- Jupyter 模式啟動 ---")
        show_jupyter(df_res, radar, exchange_rates)
        # plot_asset_allocation(df_res, exchange_rates) # show_jupyter 已內建
    else:
        # CLI 模式 (預設)
        if args.analyze:
            # 如果指定了 --code，則僅針對該代碼進行進階分析
            if args.code:
                # 篩選已存在的資產
                df_to_analyze = df_res[df_res["代碼"].isin(args.code)].copy()

                # 如果輸入了不在資產清單中的代碼，手動建立臨時記錄
                existing_codes = df_res["代碼"].tolist()
                for c in args.code:
                    if c not in existing_codes:
                        mock_record = {
                            "市場": "自選",
                            "類型": "ETF",  # 設為 ETF 以通過進階分析的類型過濾
                            "名稱": c,
                            "代碼": c,
                            "幣別": "TWD",
                            "單位數": 0,
                            "平均成本": 0.0,
                            "股價": 0.0,
                            "市值": 0,
                            "損益": 0,
                        }
                        df_to_analyze = pd.concat(
                            [df_to_analyze, pd.DataFrame([mock_record])],
                            ignore_index=True,
                        )
            else:
                df_to_analyze = df_res

            advanced_results = dashboard_logic.run_advanced_analysis(df_to_analyze)
        else:
            advanced_results = None

        show_console_rich(
            df_res,
            radar,
            market_share_data,
            advanced_results,
            show_report=args.report,
        )
