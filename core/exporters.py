# -*- coding: utf-8 -*-
from pathlib import Path

import pandas as pd

from core.columns import (
    COL_ASSET_TYPE,
    COL_AVG_COST,
    COL_CHANGE,
    COL_COMFORT_SCORE,
    COL_COST,
    COL_CURRENCY,
    COL_DAILY_LEVEL,
    COL_HOLD_ABILITY_SCORE,
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

_GUIDE_PATH = Path(__file__).parent / "ai_analysis_guide.md"
_SUGGESTION_PATH = Path(__file__).parent / "ai_analysis_suggestion.md"


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


def export_for_ai(df_res, adv_res=None, guide_path=None):
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

            # 對 mock 標的（股價 == 0）從 adv_res 補回真實股價與名稱
            zero_price_mask = (
                pd.to_numeric(work_df[COL_PRICE], errors="coerce").fillna(0) == 0
            )
            if zero_price_mask.any() and COL_PRICE in adv_res.columns:
                adv_idx = adv_res.set_index(COL_TICKER)
                if COL_PRICE in adv_idx.columns:
                    work_df.loc[zero_price_mask, COL_PRICE] = pd.to_numeric(
                        work_df.loc[zero_price_mask, COL_TICKER].map(
                            adv_idx[COL_PRICE]
                        ),
                        errors="coerce",
                    )
                if COL_NAME in adv_idx.columns:
                    work_df[COL_NAME] = work_df[COL_NAME].astype(object)
                    work_df.loc[zero_price_mask, COL_NAME] = work_df.loc[
                        zero_price_mask, COL_TICKER
                    ].map(adv_idx[COL_NAME])

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
            hold_ability = row.get(COL_HOLD_ABILITY_SCORE)
            history_yrs = row.get("historyYears")
            bench_mdd = row.get("benchmarkMddPct")
            bench_name = row.get("benchmarkName", "-")
            ann_vol = row.get("annualizedVol")
            vol_grade = row.get("volGrade", "-")
            if pd.notnull(mdd):
                pain_pct = f"{pain * 100:.0f}%" if pd.notnull(pain) else "-"
                hold_str = (
                    f"{hold_ability * 100:.0f}%" if pd.notnull(hold_ability) else "-"
                )
                vol_str = (
                    f"{ann_vol:.1%} ({vol_grade})"
                    if ann_vol is not None and pd.notnull(ann_vol)
                    else "-"
                )
                history_note = ""
                if (
                    history_yrs is not None
                    and pd.notnull(history_yrs)
                    and float(history_yrs) < 2
                ):
                    history_months = max(1, round(float(history_yrs) * 12))
                    history_note = f"（⚠️歷史僅 {history_months} 個月）"
                bench_note = (
                    f" | 基準({bench_name}) MDD {bench_mdd:.1f}%"
                    if bench_mdd is not None and pd.notnull(bench_mdd)
                    else ""
                )
                risk_line = (
                    f"- **風險指標**: 年化波動率 {vol_str} | "
                    f"MDD {mdd:.1f}%{history_note} | "
                    f"目前回撤 {curr_dd:.1f}% | "
                    f"Pain Ratio {pain_pct} | "
                    f"舒適度 {comfort} | "
                    f"持有力 {hold_str}"
                    f"{bench_note}"
                )
            else:
                risk_line = None

            quant_info = (
                f"- **基本面**: EPS {eps} | P/E {pe} | 殖利率 {yield_val} | PEG {peg}\n"
                f"- **量化指標**: RS百分位 {row.get('RS 百分位', '-')} | 乖離率 {bias} | 量比 {vol_ratio} | RSI {row.get('RSI', 0):.1f} | 夏普值 {row.get('夏普值', '-')} | α勝率 {row.get('Alpha 勝率', '-')}\n"
                + (f"{risk_line}\n" if risk_line else "")
                + (
                    f"- **掛單策略**: 追價警戒 > {row['dailyUpper']:.2f} | 日常 {row['dailyUpper']:.2f}~{row['boundaryDailyRetest']:.2f} | 回測 {row['boundaryDailyRetest']:.2f}~{row['boundaryRetestSniper']:.2f} | 狙擊 < {row['boundaryRetestSniper']:.2f}  ·  現價 {row.get(COL_PRICE, '-')} → {row.get('entryZoneStatus', '-')}"
                    if row.get("dailyUpper") is not None and row.get("boundaryDailyRetest") is not None
                    else f"- **掛單策略**: 日常 {row.get(COL_DAILY_LEVEL, '-')} 回測 {row.get(COL_PULLBACK_LEVEL, '-')} 狙擊 {row.get(COL_SNIPER_LEVEL, '-')}"
                )
                + "\n"
                f"- **診斷標籤**: {' '.join(row['tags']) if isinstance(row.get('tags'), list) else '-'}\n"
                f"- **AI 診斷建議**: {diag}"
            )
            report.append(quant_info)

        report.append("")  # 換行

    report.append("\n" + "=" * 50)
    resolved_guide = Path(guide_path) if guide_path else _GUIDE_PATH
    report.append(resolved_guide.read_text(encoding="utf-8"))

    return "\n".join(report)
