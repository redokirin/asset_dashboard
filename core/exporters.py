# -*- coding: utf-8 -*-
import pandas as pd

from core.columns import (
    COL_ASSET_TYPE,
    COL_AVG_COST,
    COL_CHANGE,
    COL_COMFORT_SCORE,
    COL_COST,
    COL_CURRENCY,
    COL_DAILY_LEVEL,
    COL_HOLDABILITY_SCORE,
    COL_MARKET,
    COL_MARKET_VALUE,
    COL_NAME,
    COL_PRICE,
    COL_PROFIT_LOSS,
    COL_PULLBACK_LEVEL,
    COL_RETURN_PCT,
    COL_SNIPER_LEVEL,
    COL_TECH_DIAGNOSIS,
    COL_TICKER,
    COL_UNITS,
    COL_WEIGHT,
)


def _bank_mask(df):
    if df.empty:
        return pd.Series(False, index=df.index)

    asset_type = (
        df[COL_ASSET_TYPE].fillna("").astype(str).str.strip().str.lower()
        if COL_ASSET_TYPE in df.columns
        else pd.Series("", index=df.index)
    )
    market = (
        df[COL_MARKET].fillna("").astype(str).str.strip().str.lower()
        if COL_MARKET in df.columns
        else pd.Series("", index=df.index)
    )
    return asset_type.eq("bank") | market.isin({"bank", "cash", "現金"})


def export_for_ai(df_res, adv_res=None):
    """
    導出結構化的 AI 分析文本。
    整合資產現況 (df_res) 與進階量化指標 (adv_res)。
    """
    report = ["# 🚀 個人財務資產 AI 診斷數據摘要\n"]
    report.append(f"> 🕒 製表時間: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n")

    # --- 1. 整體組合摘要 ---
    bank_mask = _bank_mask(df_res)
    bank_df = df_res[bank_mask].copy()
    investment_df = df_res[~bank_mask].copy()

    total_val = df_res[COL_MARKET_VALUE].sum()
    cash_val = bank_df[COL_MARKET_VALUE].sum()
    investment_val = investment_df[COL_MARKET_VALUE].sum()
    total_pl = investment_df[COL_PROFIT_LOSS].sum()
    invested_capital = investment_df[COL_COST].sum()
    total_roi = (total_pl / invested_capital * 100) if invested_capital != 0 else 0
    cash_summary_lines = [
        f"- **投資資產**: ${investment_val:,.0f} TWD",
        f"- **銀行現金**: ${cash_val:,.0f} TWD",
    ]

    report.append("## 📊 投資組合概覽")
    report.append(f"- **總市值**: ${total_val:,.0f} TWD")
    report.append(f"- **總盈餘**: ${total_pl:+,.0f} TWD ({total_roi:+.2f}%)")
    report.extend(cash_summary_lines)
    report.append("-" * 30 + "\n")

    if not bank_df.empty:
        report.append("## 銀行現金")
        for _, row in bank_df.iterrows():
            report.append(
                f"- [{row.get(COL_TICKER, '-')}] {row.get(COL_NAME, '-')}: "
                f"${row.get(COL_MARKET_VALUE, 0):,.0f} TWD"
                f" / {row.get(COL_UNITS, 0):,.2f} {row.get(COL_CURRENCY, '')}"
                f" / 佔比 {row.get(COL_WEIGHT, 0):.1f}%"
            )
        report.append("-" * 30 + "\n")

    # --- 2. 標的細節數據 ---
    report.append("## 📈 標的詳細數據與量化診斷")

    # 準備合併數據 (若有進階分析則進行 Join)
    work_df = investment_df.copy()
    if adv_res is not None and not adv_res.empty:
        # 以代碼為 key 合併 (確保 adv_res 有代碼欄位)
        if COL_TICKER in adv_res.columns:
            # 移除 adv_res 中與 work_df 重複的非 key 欄位 (除了代碼)
            cols_to_use = adv_res.columns.difference(
                work_df.columns.difference([COL_TICKER])
            )
            work_df = pd.merge(work_df, adv_res[cols_to_use], on=COL_TICKER, how="left")

    for _, row in work_df.iterrows():
        ticker = row[COL_TICKER]
        name = row[COL_NAME]
        asset_type = row.get(COL_ASSET_TYPE, "個股")

        # 基礎狀況
        change_val = row.get(COL_CHANGE, 0)
        change_str = f"{change_val:+.2f}" if pd.notnull(change_val) else "0.00"

        base_info = (
            f"### [{ticker}] {name} ({asset_type})\n"
            f"- **資產現況**: 類型 {asset_type}, 股價 [{row.get(COL_PRICE, 0):,.2f}] ({change_str}), 報酬率 {row.get(COL_RETURN_PCT, 0):.2f}%, 佔比 {row.get(COL_WEIGHT, 0):.1f}%\n"
            f"- **持倉明細**: 單位 {row.get(COL_UNITS, 0):,.2f}, 平均成本 {row.get(COL_AVG_COST, 0):.2f}, 總成本 ${row.get(COL_COST, 0):,.0f}"
        )
        report.append(base_info)

        # 進階量化數據 (若存在)
        if COL_TECH_DIAGNOSIS in row and pd.notnull(row[COL_TECH_DIAGNOSIS]):
            # 處理基本面指標
            eps = row.get("EPS", "-")
            pe = row.get("PE", "-")
            yield_val = row.get("殖利率", "-")
            peg = row.get("PEG", "-")

            # 處理量化指標
            bias = row.get("乖離率 (Bias)", "-")
            vol_ratio = row.get("量比", "-")
            diag = str(row.get(COL_TECH_DIAGNOSIS, "-")).replace("\n", " ")

            # 風險指標
            mdd = row.get("maxDrawdownPct")
            curr_dd = row.get("currentDrawdownPct")
            pain = row.get("painRatio")
            comfort = row.get(COL_COMFORT_SCORE, "-")
            holdability = row.get(COL_HOLDABILITY_SCORE)
            if pd.notnull(mdd):
                pain_pct = f"{pain * 100:.0f}%" if pd.notnull(pain) else "-"
                hold_str = (
                    f"{holdability * 100:.0f}%" if pd.notnull(holdability) else "-"
                )
                risk_line = (
                    f"- **風險指標**: MDD {mdd:.1f}% | "
                    f"目前回撤 {curr_dd:.1f}% | "
                    f"Pain Ratio {pain_pct} | "
                    f"舒適度 {comfort} | "
                    f"持有力 {hold_str}"
                )
            else:
                risk_line = None

            quant_info = (
                f"- **基本面**: EPS {eps} | P/E {pe} | 殖利率 {yield_val} | PEG {peg}\n"
                f"- **量化指標**: RS百分位 {row.get('RS 百分位', '-')} | 乖離率 {bias} | 量比 {vol_ratio} | RSI {row.get('RSI', 0):.1f} | 夏普值 {row.get('夏普值', '-')} | α勝率 {row.get('Alpha 勝率', '-')}\n"
                + (f"{risk_line}\n" if risk_line else "")
                + f"- **掛單策略**: 日常 [{row.get(COL_DAILY_LEVEL, '-')}] 回測 [{row.get(COL_PULLBACK_LEVEL, '-')}] 狙擊 [{row.get(COL_SNIPER_LEVEL, '-')}]\n"
                f"- **診斷標籤**: {' '.join(row['tags']) if isinstance(row.get('tags'), list) else '-'}\n"
                f"- **AI 診斷建議**: {diag}"
            )
            report.append(quant_info)

        report.append("")  # 換行

    report.append("\n" + "=" * 50)
    report.append(
        """
### 💡 給 AI 的分析指南與策略前提

#### 一、核心策略前提

1. **長線策略**

   * 目前投資策略為長線持有、只加不減。
   * 請不要建議賣出。
   * 若標的風險偏高、估值偏貴、短線過熱，請以「觀望」、「暫停加碼」、「降低加碼優先度」或「等待回測」表達，不要直接建議減碼。
   * 請不要推薦新標的，只針對目前持有標的進行分析。

2. **資產配置目標**

   * 區域配置目標為：台股 35%、日股 30%、美股 35%。
   * 台股內部配置目標為：主動型 / 被動型 = 1 : 1。
   * 請檢查目前加碼建議是否會違反上述配置目標。
   * 若某區域或某類型標的已明顯超配，請降低該標的的加碼優先順序。

3. **帳戶與資金限制**

   * 日幣與台幣為分別帳戶，資金互不影響。
   * 日股加碼主要使用日幣帳戶資金。
   * 台股加碼主要使用台幣帳戶資金。
   * 基金皆為定期定額投資。
   * 野村中小基金為儲蓄險附加，屬於獨立帳戶，已長期持有約 20 年，請不要與短線 ETF 操作混為一談。

4. **操作紀律**

   * 若價格高於日常掛單線，原則上不得判定為適合加碼。
   * 若標的短線強勢但尚未回測，請標記 FOMO / 追價風險。
   * 若標的已接近日常線、回測線或狙擊線，請依據位階判斷加碼優先順序。
   * 請區分「日常加碼」、「回測加碼」、「狙擊加碼」與「觀望」。
   * 建議以「幾發子彈」表達加碼強度。

---

#### 二、Smart Benchmarks 與 RS 解讀

本報表採用「區域自動對標」邏輯：

* **台股**對標：0050.TW
* **美股與全球資產**對標：VOO / S&P 500
* **日股**對標：1306.T / TOPIX

請依照標的類型解讀 RS：

1. **指數型 ETF**

   * RS 進入「價值區 / 深水區」時，代表該區域市場相對於自身歷史長期趨勢處於低位。
   * 對指數型 ETF 而言，低 RS 不一定代表弱勢，可能代表跨市場再平衡的潛在買點。
   * 請結合資產配置目標、現金水位與掛單位階判斷是否適合加碼。

2. **個股與主動型 ETF**

   * 高 RS 代表其表現優於所屬市場大盤，具備真實的相對動能。
   * 若高 RS 同時伴隨高估值或短線過熱，請標記追價風險。
   * 若高 RS 同時仍接近合理掛單位階，則可視為較佳的強勢加碼候選。

---

#### 三、Alpha 的解讀方式

Alpha 反映的是標的相對於「自身所屬市場」的超額報酬能力。

請用 Alpha 判斷：

* 主動型 ETF 是否具備選股能力。
* 基金經理人是否真正創造超額報酬。
* 標的是靠市場 Beta 上漲，還是真的有相對大盤的領先能力。
* 若 Alpha 為正且穩定，可提高長線持有信心。
* 若 Alpha 轉弱或長期落後基準，請降低加碼優先度，但不要建議賣出。

---

#### 四、基本面、PEG 與掛單位階

請結合 PEG 比例與建議掛單位階進行判斷：

* 若標的接近日常線，且 PEG 合理，可列為日常加碼候選。
* 若標的接近回測線，且基本面未惡化，可列為回測加碼候選。
* 若標的接近狙擊線，且 PEG < 1，代表安全邊際極高，可列為高優先加碼候選。
* 若標的價格明顯高於日常線，即使基本面良好，也請標記追價風險。
* 若 PEG 偏高且價格處於高位，請建議觀望或等待回測。

---

#### 五、請 AI 輸出的分析內容

請根據以上資料，分析目前投資組合健康度，並針對各標的給出具體結論。

請務必回答以下問題：

1. **目前投資組合健康度如何？**

   * 請分析整體配置、現金水位、區域占比、主動 / 被動比例、集中度與風險。

2. **各標的占比是否合理？**

   * 請檢查是否有單一市場、單一標的或單一策略過度集中。

3. **各標的成本與目前價值如何？**

   * 請比較持有成本、現價、報酬率、掛單位階與安全邊際。

4. **各標的長線建議**

   * 請針對每個標的給出：加碼、觀望、暫停加碼、降低加碼優先度。
   * 不要建議賣出。
   * 請說明理由。

5. **各標的短線建議**

   * 請依據日常線、回測線、狙擊線與目前價格位置，判斷是否適合短線加碼。
   * 請標明屬於：日常、回測、狙擊或觀望。
   * 請指出是否存在 FOMO / 追價風險。

6. **今日是否適合加碼？**

   * 若適合，請指出優先標的。
   * 請建議幾發子彈。
   * 請說明是否會違反目前資產配置目標。
   * 若不適合，請明確說明等待條件。

---

#### 六、輸出格式要求

請以以下格式輸出：

1. 投資組合健康度總結
2. 今日決策摘要
3. 各標的長線建議
4. 各標的短線建議
5. 配置風險檢查
6. FOMO / 追價風險檢查
7. 最終行動建議

請使用明確、可執行的語氣，不要只給模糊評論。

"""
    )

    return "\n".join(report)
