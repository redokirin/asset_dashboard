# -*- coding: utf-8 -*-
import pandas as pd

def export_for_ai(df_res, adv_res=None):
    """
    導出結構化的 AI 分析文本。
    整合資產現況 (df_res) 與進階量化指標 (adv_res)。
    """
    report = ["# 🚀 個人財務資產 AI 診斷數據摘要\n"]

    # --- 1. 整體組合摘要 ---
    total_val = df_res["市值"].sum()
    total_pl = df_res["損益"].sum()
    invested_capital = total_val - total_pl
    total_roi = (total_pl / invested_capital * 100) if invested_capital != 0 else 0

    report.append("## 📊 投資組合概覽")
    report.append(f"- **總市值**: ${total_val:,.0f} TWD")
    report.append(f"- **總盈餘**: ${total_pl:+,.0f} TWD ({total_roi:+.2f}%)")
    report.append("-" * 30 + "\n")

    # --- 2. 標的細節數據 ---
    report.append("## 📈 標的詳細數據與量化診斷")

    # 準備合併數據 (若有進階分析則進行 Join)
    work_df = df_res.copy()
    if adv_res is not None and not adv_res.empty:
        # 以代碼為 key 合併 (確保 adv_res 有代碼欄位)
        if "代碼" in adv_res.columns:
            # 移除 adv_res 中與 work_df 重複的非 key 欄位 (除了代碼)
            cols_to_use = adv_res.columns.difference(
                work_df.columns.difference(["代碼"])
            )
            work_df = pd.merge(
                work_df, adv_res[cols_to_use], on="代碼", how="left"
            )

    for _, row in work_df.iterrows():
        ticker = row["代碼"]
        name = row["名稱"]

        # 基礎狀況
        change_val = row.get("漲跌", 0)
        change_str = f"{change_val:+.2f}" if pd.notnull(change_val) else "0.00"
        
        base_info = (
            f"### [{ticker}] {name}\n"
            f"- **資產現況**: 股價 {row.get('股價', '-')}({change_str}), 報酬率 {row.get('報酬率', 0):.2f}%, 佔比 {row.get('佔比', 0):.1f}%\n"
            f"- **持倉明細**: 單位 {row.get('單位數', 0):,.2f}, 平均成本 {row.get('平均成本', 0):.2f}, 總成本 ${row.get('成本', 0):,.0f}"
        )
        report.append(base_info)

        # 進階量化數據 (若存在)
        if "技術診斷" in row and pd.notnull(row["技術診斷"]):
            # 處理基本面指標
            eps = row.get("EPS", "-")
            pe = row.get("PE", "-")
            yield_val = row.get("殖利率", "-")
            peg = row.get("PEG", "-")
            
            # 處理量化指標
            quant_info = (
                f"- **基本面**: EPS {eps} | P/E {pe} | 殖利率 {yield_val} | PEG {peg}\n"
                f"- **量化指標**: RS百分位 {row.get('RS 百分位', '-')} | 夏普值 {row.get('夏普值', '-')} | RSI {row.get('RSI', 0):.1f} | α勝率 {row.get('Alpha 勝率', '-')}\n"
                f"- **掛單策略**: 日常 {row.get('日常波段', '-')} | 回測 {row.get('技術回測', '-')} | 狙擊 {row.get('狙擊位', '-')}\n"
                f"- **診斷標籤**: {' '.join(row['tags']) if isinstance(row.get('tags'), list) else '-'}\n"
                f"- **AI 診斷建議**: {str(row['技術診斷']).replace('\n', ' ')}"
            )
            report.append(quant_info)

        report.append("")  # 換行

    report.append("\n" + "=" * 50)
    report.append(
        "請 AI 根據以上數據，分析目前的投資組合健康度，並針對各標的給予「加碼、減碼或觀望」的建議。請特別注意 PEG > 2 或 RS 百分位過高的標的風險。"
    )

    return "\n".join(report)
