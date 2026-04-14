import argparse
import io
import os
import pandas as pd
import dashboard_logic
from rich.console import Console
from dashboard_ui import show_console_rich


def generate_markdown_report(df, adv_results):
    # """生成符合 Markdown 與 HTML 顏色規範的報告"""
    lines = []

    if adv_results is not None and not adv_results.empty:
        groups = [
            ("過熱", "### 🔥 過熱區 (極端動能，建議觀望/分批停利)"),
            ("動能", "### 🚀 動能區 (趨勢領先，續抱觀察)"),
            ("深水", "### 🔵 價值/深水區 (長線佈局點)"),
            ("中軸", "### ⚪ 趨勢中軸 (盤整與穩定)"),
        ]

        for status_key, title in groups:
            # 修正：由於重構後狀態存放在 tags (list) 中，需改用 apply 檢查
            subset = adv_results[
                adv_results["tags"].apply(
                    lambda x: (
                        any(status_key in str(t) for t in x)
                        if isinstance(x, list)
                        else False
                    )
                )
            ]
            if subset.empty:
                continue

            lines.append(f"\n{title}")
            for _, row in subset.iterrows():
                lines.append(f"#### 🔍 {row['名稱']} ({row['代碼']})")
                lines.append(
                    f"- **當前股價**: {row['股價']} | **乖離率**: {row.get('乖離率 (Bias)', '-')}"
                )

                eps_val = row.get("EPS", 0)
                pe_val = row.get("PE", 0)
                eps_str = (
                    f"{eps_val:.2f}"
                    if isinstance(eps_val, (int, float))
                    else str(eps_val)
                )
                pe_str = (
                    f"{pe_val:.1f}" if isinstance(pe_val, (int, float)) else str(pe_val)
                )

                lines.append(
                    f"- **EPS**: {eps_str} | **PE**: {pe_str} | **量能比**: {row.get('量比', '-')}"
                )
                diag = str(row.get("技術診斷", "-")).replace("\n", " ")
                lines.append(f"> **技術診斷**: {diag}")
                if "🔴 量能不足" in diag:
                    lines.append(
                        f"> 🔴 **量價背離警語**: 目前處於價漲量縮狀態，反彈動能可能衰竭，請謹慎追高。"
                    )
                lines.append("\n---")
    return "\n".join(lines)


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

    # 當同時指定 --ai 與 --analyze 時，合併結果並寫入檔案 ai_report.md
    if args.ai and args.analyze:
        ai_text = dashboard_logic.export_for_ai(df_final, adv_res=advanced_results)
        string_io = io.StringIO()
        file_console = Console(file=string_io, force_terminal=False, width=120)
        show_console_rich(
            df_final,
            radar,
            market_share_data,
            advanced_results,
            show_report=False,
            console=file_console,
            is_list_mode=True,
        )
        # 改回 md 檔案擴充名以配合 dashboard.py 邏輯
        markdown_report = generate_markdown_report(df_res, advanced_results)
        with open("ai_report.md", "w", encoding="utf-8") as f:
            f.write(ai_text + "\n\n" + markdown_report)
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
