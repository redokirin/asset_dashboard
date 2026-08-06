# -*- coding: utf-8 -*-
import datetime
from pathlib import Path

import pandas as pd

from core.tags import TAG_DISPLAY
from core.columns import (
    COL_ASSET_TYPE,
    COL_AVG_COST,
    COL_CHANGE,
    COL_COMFORT_SCORE,
    COL_COST,
    COL_CURRENCY,
    COL_HOLD_ABILITY_SCORE,
    COL_MARKET,
    COL_MARKET_VALUE,
    COL_NAME,
    COL_PRICE,
    COL_PROFIT_LOSS,
    COL_RETURN_PCT,
    COL_TECH_DIAGNOSIS,
    COL_TICKER,
    COL_UNITS,
    COL_WEIGHT,
)

_SUGGESTION_PATH = Path(__file__).parent / "ai_analysis_suggestion.md"
_ANALYZE_DIR = Path(__file__).parent.parent / "analyze"


def save_ai_report(text: str, now: datetime.datetime | None = None) -> Path:
    """
    將 AI 診斷報告存成檔案：analyze/YYYYMMDD/report_YYYYMMDDHHMMSS.md。
    Returns: 寫入的檔案路徑。
    """
    now = now or datetime.datetime.now()
    analyze_dir = _ANALYZE_DIR / now.strftime("%Y%m%d")
    analyze_dir.mkdir(parents=True, exist_ok=True)
    report_path = analyze_dir / f"report_{now.strftime('%Y%m%d%H%M%S')}.md"
    report_path.write_text(text, encoding="utf-8")
    return report_path


def check_data_freshness(ticker, last_update_time):
    """
    檢查資料新鮮度，超過 5 分鐘標記延遲警告。
    last_update_time 接受 datetime 物件或 "HH:MM" 字串。
    特別處理台股開盤緩衝期（09:00–09:25）。
    """
    import datetime

    now = datetime.datetime.now()

    if isinstance(last_update_time, str) and last_update_time.strip():
        try:
            t = datetime.datetime.strptime(last_update_time.strip(), "%H:%M")
            last_update_time = now.replace(
                hour=t.hour, minute=t.minute, second=0, microsecond=0
            )
        except (ValueError, TypeError):
            return None

    if not isinstance(last_update_time, datetime.datetime):
        return None

    delay_minutes = (now - last_update_time).total_seconds() / 60

    if delay_minutes > 5:
        return "⚠️ 即時資料可能延遲，開盤前 20 分鐘訊號僅供參考，請以既定掛單規則優先。"

    ticker_str = str(ticker)
    if ticker_str.endswith(".TW") or ticker_str.endswith(".TWO"):
        open_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        buffer_end = now.replace(hour=9, minute=25, second=0, microsecond=0)
        if open_time <= now <= buffer_end:
            return "⚠️ 台股開盤緩衝期，前 20 分鐘資料僅供參考。"

    return None


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
    """導出結構化的診斷報告（盤後模式：OHLC zone、Pain Ratio 變化、市場事件）。"""
    now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    report = [f"# 診斷報告｜{now_str}\n"]
    report.append(f"> 🕒 製表時間: {now_str}\n")

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

    if adv_res is not None and not adv_res.empty:
        try:
            from core.analysis.overall_risk import (
                build_risk_report_section,
                calculate_overall_risk_score,
            )

            risk_data = calculate_overall_risk_score(adv_res, df_res)
            risk_section = build_risk_report_section(risk_data)
            if risk_section:
                report.append(risk_section)
                report.append("-" * 30 + "\n")
        except Exception:
            pass

    if not bank_df.empty:
        report.append("## 銀行現金")
        for _, row in bank_df.iterrows():
            keep_twd = row.get("keepTwd", 0) or 0
            total_twd = row.get(COL_MARKET_VALUE, 0) or 0
            investable_twd = total_twd - keep_twd
            keep_note = (
                f" / 可投入 ${investable_twd:,.0f} + 保留金 ${keep_twd:,.0f}"
                if keep_twd > 0
                else ""
            )
            report.append(
                f"- [{row.get(COL_TICKER, '-')}] {row.get(COL_NAME, '-')}: "
                f"${total_twd:,.0f} TWD"
                f" / {row.get(COL_UNITS, 0):,.2f} {row.get(COL_CURRENCY, '')}"
                f" / 佔比 {row.get(COL_WEIGHT, 0):.1f}%"
                f"{keep_note}"
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
                + f"- **診斷標籤**: {' '.join(TAG_DISPLAY.get(t, t) for t in row['tags']) if isinstance(row.get('tags'), list) else '-'}\n"
                + f"- **AI 診斷建議**: {diag}"
            )
            report.append(quant_info)

        report.append("")  # 換行

    _append_diagnosis_sections(report)
    _append_risk_balance_section(report, investment_df, adv_res, bank_df)

    return "\n".join(report)


def _append_risk_balance_section(
    report: list,
    investment_df: pd.DataFrame,
    adv_res,
    bank_df: pd.DataFrame | None = None,
) -> None:
    """在報告末尾附加風險加權配置分析區塊（含資金加權欄位，若有銀行資料）。"""
    try:
        from core.analysis.risk_balance import build_comparison_df, build_region_df

        work = investment_df.copy()
        if adv_res is not None and not adv_res.empty and COL_TICKER in adv_res.columns:
            cols = adv_res.columns.difference(work.columns.difference([COL_TICKER]))
            work = pd.merge(work, adv_res[cols], on=COL_TICKER, how="left")

        if "annualizedVol" in work.columns:
            valid = work[work["annualizedVol"].notna()]
        else:
            valid = pd.DataFrame()

        if valid.empty:
            return

        has_bank = bank_df is not None and not bank_df.empty
        comp_df = build_comparison_df(valid, bank_df=bank_df if has_bank else None)
        reg_df = build_region_df(
            valid,
            region_targets={"台股": 0.31, "日股": 0.31, "美股": 0.31, "全球": 0.07},
            bank_df=bank_df if has_bank else None,
        )
        has_acct_col = "理論(資金加權)" in comp_df.columns

        report.append("\n## 風險加權配置分析\n")
        if has_acct_col:
            report.append(
                "| 標的 | 波動率 | 理論(波動率) | 理論(資金加權) | 實際配置 | 差異(資金加權) |"
            )
            report.append(
                "|------|--------|-------------|--------------|---------|--------------|"
            )
        else:
            report.append(
                "| 標的 | 波動率 | 理論(波動率) | 理論(綜合) | 實際配置 | 差異(波動率) |"
            )
            report.append(
                "|------|--------|-------------|-----------|---------|-------------|"
            )

        for _, r in comp_df.iterrows():
            if has_acct_col:
                acct = r.get("理論(資金加權)", 0) or 0
                diff = r.get("差異(資金加權)") or 0
                arrow = "↑" if diff > 0.03 else ("↓" if diff < -0.03 else "≈")
                report.append(
                    f"| {r['標的']} | {r['波動率']} "
                    f"| {r['理論(波動率)']:.1%} | {acct:.1%} "
                    f"| {r['實際配置']:.1%} | {diff:+.1%} {arrow} |"
                )
            else:
                diff = r["差異(波動率)"]
                arrow = "↑" if diff > 0.03 else ("↓" if diff < -0.03 else "≈")
                report.append(
                    f"| {r['標的']} | {r['波動率']} "
                    f"| {r['理論(波動率)']:.1%} | {r['理論(綜合)']:.1%} "
                    f"| {r['實際配置']:.1%} | {diff:+.1%} {arrow} |"
                )

        has_acct_reg = "理論(資金加權)" in reg_df.columns
        report.append("\n### 區域配置對比\n")
        if has_acct_reg:
            report.append("| 區域 | 理論(波動率) | 理論(資金加權) | 實際 | 現有目標 |")
            report.append("|------|-------------|--------------|------|---------|")
        else:
            report.append("| 區域 | 理論(波動率) | 理論(綜合) | 實際 | 現有目標 |")
            report.append("|------|-------------|-----------|------|---------|")

        for _, r in reg_df.iterrows():
            target_str = f"{r['現有目標']:.1%}" if pd.notnull(r["現有目標"]) else "—"
            if has_acct_reg:
                acct_r = r.get("理論(資金加權)", 0) or 0
                report.append(
                    f"| {r['區域']} | {r['理論(波動率)']:.1%} | {acct_r:.1%} "
                    f"| {r['實際配置']:.1%} | {target_str} |"
                )
            else:
                report.append(
                    f"| {r['區域']} | {r['理論(波動率)']:.1%} | {r['理論(綜合)']:.1%} "
                    f"| {r['實際配置']:.1%} | {target_str} |"
                )
    except Exception as exc:
        report.append(f"\n> (風險加權配置分析載入失敗: {exc})")


def export_single_target_for_ai(row) -> str:
    """導出單一標的的量化分析報告（供手動分析頁下載用）。"""
    now_str = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    ticker = row.get(COL_TICKER, "-")
    name = row.get(COL_NAME, ticker)
    asset_type = row.get(COL_ASSET_TYPE, "個股")

    report = [
        f"# AI 診斷報告｜{ticker}｜{now_str}\n",
        f"> 🕒 製表時間: {now_str}\n",
        f"## 📈 {name} ({ticker})\n",
    ]

    change_val = row.get(COL_CHANGE, 0)
    try:
        change_str = f"{float(change_val):+.2f}" if pd.notnull(change_val) else "0.00"
    except (TypeError, ValueError):
        change_str = "0.00"
    try:
        price = float(row.get(COL_PRICE, 0) or 0)
        price_str = f"{price:,.2f}"
    except (TypeError, ValueError):
        price_str = str(row.get(COL_PRICE, "-"))
    report.append(
        f"- **資產現況**: 類型 {asset_type}, 股價 [{price_str}] ({change_str})"
    )

    if COL_TECH_DIAGNOSIS in row and pd.notnull(row[COL_TECH_DIAGNOSIS]):
        eps = row.get("EPS", "-")
        pe = row.get("PE", "-")
        yield_val = row.get("殖利率", "-")
        peg = row.get("PEG", "-")
        bias = row.get("乖離率 (Bias)", "-")
        vol_ratio = row.get("量比", "-")
        diag = str(row.get(COL_TECH_DIAGNOSIS, "-")).replace("\n", " ")

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

        risk_line = None
        if pd.notnull(mdd):
            pain_pct = f"{pain * 100:.0f}%" if pd.notnull(pain) else "-"
            hold_str = f"{hold_ability * 100:.0f}%" if pd.notnull(hold_ability) else "-"
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

        quant_info = (
            f"- **基本面**: EPS {eps} | P/E {pe} | 殖利率 {yield_val} | PEG {peg}\n"
            f"- **量化指標**: RS百分位 {row.get('RS 百分位', '-')} | 乖離率 {bias} | 量比 {vol_ratio} | RSI {row.get('RSI', 0):.1f} | 夏普值 {row.get('夏普值', '-')} | α勝率 {row.get('Alpha 勝率', '-')}\n"
            + (f"{risk_line}\n" if risk_line else "")
            + f"- **診斷標籤**: {' '.join(TAG_DISPLAY.get(t, t) for t in row['tags']) if isinstance(row.get('tags'), list) else '-'}\n"
            + f"- **AI 診斷建議**: {diag}"
        )
        report.append(quant_info)

    return "\n".join(report)


def _append_diagnosis_sections(report: list) -> None:
    """在診斷模式報告末尾附加 OHLC zone、市場事件與 Pain Ratio 變化。"""
    from datetime import date

    today_str = str(date.today())
    try:
        from db.database import _get_connection, init_db

        init_db()
        with _get_connection() as conn:
            ohlc_rows = conn.execute(
                """SELECT ticker,
                          open_zone, open_position, high_zone, high_position,
                          low_zone, low_position, close_zone, close_position,
                          execution_status
                   FROM order_bands WHERE report_date = ? ORDER BY ticker""",
                (today_str,),
            ).fetchall()
            event_rows = conn.execute(
                """SELECT event_tag, event_name, event_note, is_pressure_test
                   FROM market_events WHERE event_date = ?""",
                (today_str,),
            ).fetchall()

        if ohlc_rows:

            def _zp(zone, pos):
                if zone is None:
                    return "-"
                return f"{zone}({pos:.2f})" if pos is not None else zone

            report.append("\n## OHLC Zone 落點\n")
            report.append("| 標的 | 開盤 | 最高 | 最低 | 收盤 | 執行狀態 |")
            report.append("|------|------|------|------|------|----------|")
            for r in ohlc_rows:
                report.append(
                    f"| {r['ticker']} "
                    f"| {_zp(r['open_zone'], r['open_position'])} "
                    f"| {_zp(r['high_zone'], r['high_position'])} "
                    f"| {_zp(r['low_zone'], r['low_position'])} "
                    f"| {_zp(r['close_zone'], r['close_position'])} "
                    f"| {r['execution_status'] or '-'} |"
                )

        if event_rows:
            report.append("\n## 市場事件\n")
            for e in event_rows:
                pt = " [壓力測試]" if e["is_pressure_test"] else ""
                report.append(f"- **{e['event_tag']}**{pt}: {e['event_name'] or ''}")
                if e["event_note"]:
                    first_line = e["event_note"].strip().splitlines()[0]
                    report.append(f"  > {first_line}")

    except Exception as exc:
        report.append(f"\n> (診斷資料載入失敗: {exc})")

    try:
        from db.database import get_latest_two_snapshots

        latest, previous = get_latest_two_snapshots()
        if latest.get("assets") and previous.get("assets"):
            prev_map = {
                a["ticker"]: a["pain_ratio"]
                for a in previous["assets"]
                if a.get("pain_ratio") is not None
            }
            pain_lines = []
            for a in latest["assets"]:
                if a.get("pain_ratio") is not None and a["ticker"] in prev_map:
                    delta = a["pain_ratio"] - prev_map[a["ticker"]]
                    arrow = "⬆️" if delta > 0.01 else ("⬇️" if delta < -0.01 else "→")
                    pain_lines.append(
                        f"- **{a['ticker']}**: {a['pain_ratio']:.2f} "
                        f"{arrow} (前: {prev_map[a['ticker']]:.2f})"
                    )
            if pain_lines:
                report.append("\n## Pain Ratio 變化\n")
                report.extend(pain_lines)
    except Exception:
        pass
