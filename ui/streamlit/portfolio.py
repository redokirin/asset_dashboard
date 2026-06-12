# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from core import dashboard_logic
from core.columns import (
    COL_CURRENCY,
    COL_MARKET_VALUE,
    COL_NAME,
    COL_SETTLEMENT,
    COL_TICKER,
    COL_UNITS,
    COL_WEIGHT,
)
from ui.streamlit.advanced_analysis import render_advanced_analysis_ui
from ui.streamlit.components import (
    render_cost_component,
    render_title_component,
    render_tracking_metrics_row,
    render_vertical_value_tag_component,
)


CASH_MARKETS = {"bank", "cash", "現金"}


def _cash_mask(df):
    if "市場" not in df.columns:
        return pd.Series(False, index=df.index)
    market_names = df["市場"].astype(str).str.strip().str.lower()
    return market_names.isin(CASH_MARKETS)


def render_schedule_of_assets(df, investment_df):
    with st.container():
        total_pl = investment_df["損益"].sum()
        total_cost = investment_df["成本"].sum()
        roi = (total_pl / total_cost * 100) if total_cost != 0 else 0

        st.markdown(
            f"""<div class='inline-metric-label'>💰 總資產</div>
                <div class='total-pl-wrapper'>
                    <div class='inline-metric-row'>
                        <span class='inline-metric-value'>${df["市值"].sum():,}</span>
                    </div>
                    {render_vertical_value_tag_component(f"{total_pl:+,.0f}", roi)}
                </div>
            """,
            unsafe_allow_html=True,
        )


def _fmt_reason(r: str) -> str:
    import re

    m = re.match(r"Pain Ratio (\d+)%（昨日 (\d+)%）", r)
    if m:
        return f"Pain Ratio {m.group(2)}% > {m.group(1)}%"
    return r


@st.dialog("⚡ 風險儀表板", width="large")
def _show_risk_dashboard_dialog(risk_data):
    from core.analysis.overall_risk import get_risk_level
    from db.database import get_prev_risk_score, get_risk_score_history

    from ui.streamlit.components import render_analysis_metrics_row

    score = risk_data["risk_score"]
    level_label, level_advice = get_risk_level(score)
    prev_score = get_prev_risk_score()

    _risk_colors = {
        "保守": "#00c853",
        "中低": "#a8d08d",
        "中等": "#ffc107",
        "中高": "#ff9800",
        "高風險": "#ff4b4b",
    }
    score_color = next((v for k, v in _risk_colors.items() if k in level_label), None)

    score_display = f"{score} / 100"
    if prev_score is not None:
        delta = score - prev_score
        delta_color = "#ff4b4b" if delta > 0 else "#00c853"
        score_display = (score_display, score_color)
        delta_display = (f"{delta:+.1f}", delta_color)
    else:
        score_display = (score_display, score_color)
        delta_display = "—"

    metrics = {
        "整體風險係數": score_display,
        "日變動": delta_display,
        "風險等級": level_label,
        "投資比例": f"{risk_data['invested_ratio']:.1%}",
        "現金緩衝": f"{risk_data['cash_buffer_ratio']:.1%}",
    }
    st.markdown(
        render_analysis_metrics_row(metrics, title=f"建議：{level_advice}"),
        unsafe_allow_html=True,
    )

    history = get_risk_score_history(30)
    if len(history) >= 2:
        hist_df = pd.DataFrame(history)[["snapshot_date", "overall_risk_score"]].rename(
            columns={"snapshot_date": "日期", "overall_risk_score": "風險係數"}
        )
        hist_df["日期"] = pd.to_datetime(hist_df["日期"])
        hist_df = hist_df.set_index("日期")
        st.markdown("##### 風險係數趨勢（近 30 天）")
        st.line_chart(hist_df)

    breakdown = risk_data.get("asset_breakdown", [])
    if breakdown:
        st.markdown("##### 標的風險貢獻")
        bd_df = pd.DataFrame(breakdown)[
            ["ticker", "weighted_contribution", "risk_score", "weight"]
        ]
        bd_df.columns = ["標的", "加權貢獻", "風險分數", "市值佔比"]
        st.bar_chart(bd_df.set_index("標的")["加權貢獻"])

        st.markdown("##### 風險分解明細")
        bd_df["市值佔比"] = bd_df["市值佔比"].map("{:.1%}".format)
        bd_df["風險分數"] = bd_df["風險分數"].map("{:.2f}".format)
        bd_df["加權貢獻"] = bd_df["加權貢獻"].map("{:.3f}".format)
        st.dataframe(bd_df, hide_index=True, width="stretch")


@st.dialog("📋 今日行動摘要", width="large")
def _show_daily_summary_dialog(summary):
    st.caption(summary["timestamp"])

    risk_data = summary.get("risk_data")
    risk_alerts = summary.get("risk_alerts", [])
    if risk_data and risk_alerts:
        from core.analysis.overall_risk import get_risk_level

        score = risk_data["risk_score"]
        level_label, _ = get_risk_level(score)
        st.warning(
            f"**整體風險係數 {score} / 100　{level_label}**\n\n"
            + "\n\n".join(risk_alerts)
        )

    hold_off = summary.get("hold_off", [])

    if summary["actionable"] or summary["warnings"] or hold_off:
        st.markdown("##### 【標的摘要】")
        warn_map = {w["ticker"]: w for w in summary["warnings"]}
        rendered = set()

        for item in summary["actionable"]:
            ticker = item["ticker"]
            rendered.add(ticker)
            zone_str = f"區間 {item['zone_range']}" if item.get("zone_range") else ""
            if item.get("fib_price") is not None:
                fib_str = f"最近支撐 {item['fib_price']:.2f}"
            elif zone_str:
                price_val = item.get("current_price")
                price_display = f"{price_val:.2f}" if price_val is not None else "—"
                fib_str = f"現價({price_display})近下緣，位置偏佳"
            else:
                fib_str = ""
            detail = "｜".join(p for p in [zone_str, fib_str] if p)
            quality_note = item.get("quality_note")

            w = warn_map.get(ticker)
            if w:
                header = f"● **{ticker}** ｜ {w['advice']}"
                reasons = "｜".join(_fmt_reason(r) for r in w["reasons"])
                parts = [p for p in [detail, reasons, quality_note] if p]
                st.warning("\n\n".join([header] + parts))
            else:
                header = f"● **{ticker}** ｜ {item['signal']}"
                body_parts = [p for p in [detail, quality_note] if p]
                body = "\n\n".join(body_parts)
                st.success(f"{header}\n\n{body}" if body else header)

        for item in summary["warnings"]:
            if item["ticker"] not in rendered:
                reasons = "｜".join(_fmt_reason(r) for r in item["reasons"])
                st.warning(f"⚠️ **{item['ticker']}** ｜ {item['advice']}\n\n{reasons}")

        if hold_off:
            st.markdown("##### 【觀望（量價異常）】")
            for item in hold_off:
                rendered.add(item["ticker"])
                zone_str = (
                    f"區間 {item['zone_range']}"
                    if item.get("zone_range")
                    else item.get("signal", "")
                )
                reason = item.get("quality_note") or "量縮上漲，不追"
                st.info(f"⚪ **{item['ticker']}** ｜ {zone_str}\n\n{reason}")

    if summary["region_gaps"]:
        st.markdown("##### 【配置缺口】")
        for g in summary["region_gaps"]:
            emoji = "🔴" if g["gap_pct"] < 0 else "🟠"
            st.error(
                f"{emoji} **{g['region']}** {g['current_pct'] * 100:.1f}%"
                f" ｜ 目標 {g['target_pct'] * 100:.0f}%"
                f" ｜ 缺口 {g['gap_pct'] * 100:+.1f}%"
            )

    if not any(
        [summary["actionable"], hold_off, summary["warnings"], summary["region_gaps"]]
    ):
        st.success("✅ 今日無須特別行動，所有標的均正常")

    with st.expander("📄 純文字版本"):
        st.code(summary["text"], language=None)


def render_report_component(df):
    has_report = "ai_report" in st.session_state
    row1 = st.columns(5)

    with row1[0]:
        if st.button("📊 配置分析", width="stretch"):
            st.session_state["show_allocation"] = True
            st.rerun()

    with row1[1]:
        if st.button("🎯 行動摘要", width="stretch"):
            with st.spinner("正在分析今日摘要..."):
                from core.analysis.overall_risk import calculate_overall_risk_score
                from core.daily_summary import generate_daily_summary

                adv_res = dashboard_logic.run_advanced_analysis(df)
                st.session_state["_adv_res_cache"] = adv_res
                risk_data = (
                    calculate_overall_risk_score(adv_res, df)
                    if not adv_res.empty
                    else {}
                )
                summary = generate_daily_summary(df, adv_res, risk_data=risk_data)
            _show_daily_summary_dialog(summary)

    with row1[2]:
        has_cache = st.session_state.get("_adv_res_cache") is not None
        if st.button("🔄 清除快取", width="stretch", disabled=not has_cache):
            st.session_state.pop("_adv_res_cache", None)
            st.rerun()

    with row1[3]:
        if st.button("⚡ 風險儀表", width="stretch"):
            with st.spinner("計算整體風險係數..."):
                from core.analysis.overall_risk import calculate_overall_risk_score

                adv_res = st.session_state.get("_adv_res_cache")
                if adv_res is None or adv_res.empty:
                    adv_res = dashboard_logic.run_advanced_analysis(df)
                    st.session_state["_adv_res_cache"] = adv_res
                risk_data = (
                    calculate_overall_risk_score(adv_res, df)
                    if not adv_res.empty
                    else {}
                )
            if risk_data:
                _show_risk_dashboard_dialog(risk_data)
            else:
                st.warning("無法計算風險係數，請確認進階分析資料是否載入。")
    with row1[4]:
        if st.button("📋 盤後診斷", width="stretch"):
            with st.spinner("正在產生診斷報告..."):
                from core import exporters

                adv_res = dashboard_logic.run_advanced_analysis(df)
                st.session_state["_adv_res_cache"] = adv_res
                st.session_state["ai_report"] = exporters.export_for_ai(df, adv_res)

    if has_report:
        from datetime import date

        st.download_button(
            label="⬇️ 下載報告 (.md)",
            data=st.session_state["ai_report"],
            file_name=f"ai_report_diagnosis_{date.today().strftime('%Y%m%d')}.md",
            mime="text/markdown",
            width="stretch",
        )


def render_market_card(investment_df, radar_data):
    market_stats = investment_df.groupby("市場").agg({"損益": "sum", "成本": "sum"})
    market_stats = market_stats.sort_values("損益", ascending=False)

    market_items = []
    for market, row in market_stats.iterrows():
        market_pl = row["損益"]
        market_roi = market_pl / row["成本"] * 100 if row["成本"] != 0 else 0
        market_items.append({"名稱": market, "數值": market_pl, "漲跌幅": market_roi})

    for i in range(0, len(market_items), 4):
        st.markdown(
            render_tracking_metrics_row(market_items[i : i + 4]),
            unsafe_allow_html=True,
        )
    indices = [item for item in radar_data]
    for i in range(0, len(indices), 3):
        st.markdown(
            render_tracking_metrics_row(indices[i : i + 3]),
            unsafe_allow_html=True,
        )


def render_profit_and_loss_component(df, radar_data):
    cash_mask = _cash_mask(df)
    investment_df = df[~cash_mask]

    render_schedule_of_assets(df, investment_df)

    render_liquidity_component(df)

    render_market_card(investment_df, radar_data)


def _settlement_values(frame):
    if COL_SETTLEMENT not in frame.columns:
        return pd.Series("", index=frame.index)
    return frame[COL_SETTLEMENT].fillna("").astype(str).str.strip()


def render_liquidity_component(df):
    if COL_MARKET_VALUE not in df.columns:
        return

    total_value = df[COL_MARKET_VALUE].sum()
    if total_value == 0:
        return

    cash_mask = _cash_mask(df)
    cash_df = df[cash_mask].copy()
    investment_df = df[~cash_mask].copy()
    settlement_values = _settlement_values(investment_df)

    bank_rows = {
        str(row[COL_TICKER]).strip(): row
        for _, row in cash_df.iterrows()
        if str(row.get(COL_TICKER, "")).strip()
    }
    settlement_keys = [key for key in settlement_values.unique() if key]
    group_keys = list(bank_rows.keys())
    group_keys.extend(key for key in settlement_keys if key not in bank_rows)
    if settlement_values.eq("").any():
        group_keys.append("")

    keep_color = "#36494f"
    bar_palettes = [
        ("#2563eb", "#93c5fd"),
        ("#059669", "#86efac"),
        ("#7c3aed", "#c4b5fd"),
        ("#0f766e", "#99f6e4"),
    ]

    bank_blocks = ""
    legend_items = ""
    any_keep = False

    for idx, bank_key in enumerate(group_keys):
        investment_color, cash_color = bar_palettes[idx % len(bar_palettes)]
        bank_row = None
        if bank_key:
            bank_row = bank_rows.get(bank_key)
            title = (
                str(bank_row.get(COL_NAME, bank_key))
                if bank_row is not None
                else bank_key
            )
            matched_investments = investment_df[settlement_values == bank_key]
            matched_cash = cash_df[
                cash_df[COL_TICKER].fillna("").astype(str).str.strip() == bank_key
            ]
        else:
            title = "未指定交割銀行"
            matched_investments = investment_df[settlement_values == ""]
            matched_cash = cash_df.iloc[0:0]

        investment_value = matched_investments[COL_MARKET_VALUE].sum()
        cash_value = matched_cash[COL_MARKET_VALUE].sum()
        if investment_value + cash_value == 0:
            continue

        keep_twd = int(bank_row.get("keepTwd", 0)) if bank_row is not None else 0
        investable = cash_value - keep_twd
        bank_total_full = investment_value + investable + keep_twd

        investment_pct = (
            investment_value / bank_total_full * 100 if bank_total_full else 0
        )
        cash_pct = investable / bank_total_full * 100 if bank_total_full else 0
        keep_pct = keep_twd / bank_total_full * 100 if bank_total_full else 0

        if keep_twd > 0:
            any_keep = True
            keep_val_html = (
                f'<div style="text-align:right;" class="asset-value-label">'
                f'<span class="asset-price-main">${keep_twd:,.0f}</span>'
                f"</div>"
            )
            keep_bar_html = (
                f'<div title="保留金 {keep_pct:.1f}%"'
                f' style="width:{keep_pct:.4f}%; background:{keep_color};"></div>'
            )
        else:
            keep_val_html = "<div></div>"
            keep_bar_html = ""

        bank_blocks += (
            f'<div style="padding:0 0.5rem; margin-top:6px;">'
            f'<div style="display:flex; height:16px; width:100%; overflow:hidden; border-radius:6px; background:rgba(255,255,255,0.08);">'
            f'<div title="投資 {investment_pct:.1f}%" style="width:{investment_pct:.4f}%; background:{investment_color};"></div>'
            f'<div title="可投入 {cash_pct:.1f}%" style="width:{cash_pct:.4f}%; background:{cash_color};"></div>'
            f"{keep_bar_html}"
            f"</div>"
            f'<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px; margin-bottom:4px;">'
            f'<div class="asset-value-label"><span class="asset-price-main">${investment_value:,.0f}</span></div>'
            f'<div style="text-align:right;" class="asset-value-label"><span class="asset-price-main">${investable:,.0f}</span></div>'
            f"{keep_val_html}"
            f"</div>"
            f"</div>"
        )
        legend_items += (
            f'<div style="display:flex; align-items:center; gap:4px;">'
            f'<div style="width:10px; height:10px; border-radius:2px; background:{investment_color};"></div>'
            f'<span class="asset-price-main">{title} ${bank_total_full:,.0f}</span>'
            f"</div>"
        )

    if not bank_blocks:
        return

    keep_header = (
        '<div style="text-align:right;" class="asset-value-label">保留金</div>'
        if any_keep
        else "<div></div>"
    )
    header = (
        f'<div style="padding:0 0.5rem; margin-top:6px;">'
        f'<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px;">'
        f'<div class="asset-value-label">投資</div>'
        f'<div style="text-align:right;" class="asset-value-label">可投入</div>'
        f"{keep_header}"
        f"</div></div>"
    )
    legend = (
        f'<div style="display:flex; justify-content:center; gap:16px;'
        f' flex-wrap:wrap; margin-top:6px; padding:0 0.5rem;">'
        f"{legend_items}</div>"
    )

    st.markdown(header + bank_blocks + legend, unsafe_allow_html=True)


def render_dataframe_component(df):
    df_view = df.copy()
    numeric_cols = [
        "單位數",
        "平均成本",
        "股價",
        "漲跌",
        "市值",
        "損益",
        "報酬率",
        "佔比",
    ]
    for col in numeric_cols:
        if col in df_view.columns:
            df_view[col] = pd.to_numeric(df_view[col], errors="coerce").fillna(0.0)

    for col in ["代碼", "名稱", "市場"]:
        if col in df_view.columns:
            df_view[col] = df_view[col].astype(str)

    df_view["標的"] = df_view["代碼"]
    cols_display = [
        "市場",
        "標的",
        "股價",
        "漲跌",
        "損益",
        "報酬率",
        "單位數",
        "平均成本",
        "市值",
        "佔比",
    ]
    cols_to_use = [col for col in cols_display if col in df_view.columns]

    event = st.dataframe(
        df_view[cols_to_use]
        .style.format(
            {
                "單位數": "{:,.0f}",
                "平均成本": "{:,.2f}",
                "股價": "{:,.2f}",
                "漲跌": "{:+,.2f}",
                "市值": "${:,.0f}",
                "損益": "${:+,.0f}",
                "報酬率": "{:+.2f}%",
                "佔比": "{:.1f}%",
            },
            na_rep="0",
        )
        .map(
            lambda x: (
                "color: #ff4b4b"
                if (pd.notnull(x) and x > 0)
                else ("color: #00c853" if (pd.notnull(x) and x < 0) else "")
            ),
            subset=["損益", "報酬率", "漲跌"],
        ),
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
        hide_index=True,
        column_config={
            "標的": st.column_config.TextColumn(
                "標的", help="顯示代碼 (點選可看完整名稱與分析)"
            )
        },
    )

    if event and event.selection and event.selection.rows:
        idx = event.selection.rows[0]
        selected_row = df.iloc[idx]
        title = f"🔍 {selected_row['名稱']} ({selected_row['代碼']}) 進階分析"
        render_title_component(title)
        with st.container(border=True):
            with st.spinner("分析中..."):
                adv_results = dashboard_logic.run_advanced_analysis(
                    pd.DataFrame([selected_row])
                )
                if not adv_results.empty:
                    render_advanced_analysis_ui(adv_results.iloc[0])


def render_shareholding_component(df, summary=None):
    investment_df = df[~_cash_mask(df)]

    actionable_map = {
        item["ticker"]: item for item in (summary or {}).get("actionable", [])
    }
    hold_off_map = {
        item["ticker"]: item for item in (summary or {}).get("hold_off", [])
    }
    warning_map = {w["ticker"]: w for w in (summary or {}).get("warnings", [])}

    for idx, row in investment_df.iterrows():
        ticker = row["代碼"]
        with st.container(border=False):
            with st.container():
                c1, c2, c3, c4 = st.columns([0.65, 2.2, 1, 1])
                with c1:
                    st.markdown(
                        '<div class="asset-card-beacon" style="display:none;"></div>',
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "🔍",
                        key=f"btn_{ticker}_{idx}",
                        help="點擊執行進階量化分析",
                    ):
                        state_key = f"analyze_{ticker}"
                        st.session_state[state_key] = not st.session_state.get(
                            state_key, False
                        )
                        st.rerun()

                with c2:
                    update_time_str = (
                        f"⏳ {row.get('更新時間', '')} | "
                        if row.get("更新時間")
                        else ""
                    )
                    if ticker in warning_map:
                        indicator = '<span style="margin-left:5px;">🟠</span>'
                    elif ticker in actionable_map:
                        indicator = '<span style="margin-left:5px;">🟢</span>'
                    elif ticker in hold_off_map:
                        indicator = '<span style="margin-left:5px;">⚪</span>'
                    else:
                        indicator = ""
                    st.markdown(
                        f"""<div class='asset-info-container'>
                        <div class='asset-info-meta'>{update_time_str}{row["市場"]} | {ticker} ({row["佔比"]:.1f}%) </div>
                        <div class='asset-info-name'>{row["名稱"]}{indicator}</div>
                        </div>""",
                        unsafe_allow_html=True,
                    )

                with c3:
                    price, change = row["股價"], row["漲跌"]
                    change_val = (
                        float(change) if pd.notnull(change) and change != "-" else 0.0
                    )
                    st.markdown(
                        f"""<div class='asset-value-container'>
                        <div class='asset-value-label'>現價 / 漲跌</div>
                        {render_vertical_value_tag_component(price, change_val)}
                        </div>""",
                        unsafe_allow_html=True,
                    )

                with c4:
                    pl, roi = row["損益"], row["報酬率"]
                    st.markdown(
                        f"""<div class='asset-value-container'>
                        <div class='asset-value-label'>損益 / 報酬</div>
                        {render_vertical_value_tag_component(f"{pl:+,.0f}", roi)}
                        </div>""",
                        unsafe_allow_html=True,
                    )
            # st.divider()

            if st.session_state.get(f"analyze_{ticker}", False):
                render_cost_component(row)

                with st.spinner("正在進行深度數據穿透..."):
                    _cached = st.session_state.get("_adv_res_cache")
                    if _cached is not None and not _cached.empty:
                        adv_results = _cached[_cached[COL_TICKER] == ticker]
                    else:
                        if hasattr(dashboard_logic, "clear_ticker_cache"):
                            dashboard_logic.clear_ticker_cache(ticker)
                        adv_results = dashboard_logic.run_advanced_analysis(
                            pd.DataFrame([row])
                        )
                        st.session_state["_adv_res_cache"] = adv_results
                    if not adv_results.empty:
                        with st.container():
                            render_advanced_analysis_ui(
                                adv_results.iloc[0],
                                warning=warning_map.get(ticker),
                                actionable=actionable_map.get(ticker),
                                hold_off=hold_off_map.get(ticker),
                            )
