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
            work_df = pd.merge(work_df, adv_res[cols_to_use], on="代碼", how="left")

    for _, row in work_df.iterrows():
        ticker = row["代碼"]
        name = row["名稱"]
        asset_type = row.get("類型", "個股")

        # 基礎狀況
        change_val = row.get("漲跌", 0)
        change_str = f"{change_val:+.2f}" if pd.notnull(change_val) else "0.00"

        base_info = (
            f"### [{ticker}] {name} ({asset_type})\n"
            f"- **資產現況**: 類型 {asset_type}, 股價 {row.get('股價', '-')}({change_str}), 報酬率 {row.get('報酬率', 0):.2f}%, 佔比 {row.get('佔比', 0):.1f}%\n"
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
            bias = row.get("乖離率 (Bias)", "-")
            vol_ratio = row.get("量比", "-")
            diag = str(row.get("技術診斷", "-")).replace("\n", " ")

            # 量價背離警語
            warning = ""
            if "🔴 量能不足" in diag:
                warning = "\n> 🔴 **量價背離警語**: 目前處於價漲量縮狀態，反彈動能可能衰竭，請謹慎追高。"

            quant_info = (
                f"- **基本面**: EPS {eps} | P/E {pe} | 殖利率 {yield_val} | PEG {peg}\n"
                f"- **量化指標**: RS百分位 {row.get('RS 百分位', '-')} | 乖離率 {bias} | 量比 {vol_ratio} | RSI {row.get('RSI', 0):.1f} | 夏普值 {row.get('夏普值', '-')} | α勝率 {row.get('Alpha 勝率', '-')}\n"
                f"- **掛單策略**: 日常 {row.get('日常波段', '-')} | 回測 {row.get('技術回測', '-')} | 狙擊 {row.get('狙擊位', '-')}\n"
                f"- **診斷標籤**: {' '.join(row['tags']) if isinstance(row.get('tags'), list) else '-'}\n"
                f"- **AI 診斷建議**: {diag}{warning}"
            )
            report.append(quant_info)

        report.append("")  # 換行

    report.append("\n" + "=" * 50)
    report.append(
        """
### 💡 給 AI 的分析指南：
1. **智能基準 (Smart Benchmarks) 與 RS 解讀**：本報表採用「區域自動對標」邏輯。
   - **台股**對點 [0050.TW]；**美股與全球資產**對標 [VOO] (S&P 500)；**日股**對標 [1306.T] (TOPIX)。
   - **指數型 ETF**：RS 進入「價值/深水區」意味著該區域市場相對於其歷史長期趨勢處於低位，是跨市場再平衡的潛在買點。
   - **個股與主動型 ETF**：高 RS 代表其表現超越所屬市場大盤，具備真實的動能領先。
2. **Alpha 的專業意義**：Alpha 現在反映的是標的相對於「自身所屬市場」的超額報酬能力，請以此判斷主動型基金與經理人的選股實力。
3. **基本面與掛單**：請結合 PEG 比例與建議掛單位階。低位階且 PEG < 1 的標的具備極高安全邊際。
4. **帳戶類型**: 日幣和台幣有分別帳戶，互不影響，基金皆為定期定額投資(野村中小基金為儲蓄險附加，有獨立帳戶，已長期持有約20年)。

請 AI 根據以上數據，分析目前的投資組合健康度，各標的的占比與價值，並針對各標的長線及短線分別給予「加碼、減碼或觀望」的具體建議。
"""
    )

    return "\n".join(report)
