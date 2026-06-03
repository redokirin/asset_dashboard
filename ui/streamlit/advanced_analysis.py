# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from core import dashboard_logic
from ui.streamlit.charts import render_price_chart
from ui.streamlit.components import render_analysis_metrics_row


def render_advanced_analysis_ui(res):
    """
    四層 Tab 決策 UI  ·  Decision → Risk → Quant → Fundamental
    Hero 區塊使用 st.metric() 大字顯示，其餘格子使用 render_analysis_metrics_row()。
    """

    def _anomaly_color(value, metric_type):
        if value is None or str(value).strip() in ["-", ""]:
            return ""
        try:
            val = float(str(value).replace("%", "").replace(",", ""))
        except ValueError:
            return ""
        if metric_type == "bias":
            if val > 15:
                return "#FF4500"
            if val < -10:
                return "#00FF00"
            if abs(val) > 50:
                return "#FF4B4B"
        if metric_type == "yield" and val > 20.0:
            return "#FF4B4B"
        if metric_type == "vol_ratio" and val > 50:
            return "#FF4B4B"
        if metric_type == "pe" and (val > 500 or val < 0):
            return "#FF4B4B"
        return ""

    def _dd_color(v):
        if not isinstance(v, float):
            return ""
        a = abs(v)
        if a < 5:
            return "#00C853"
        if a < 15:
            return "#FF9800"
        return "#FF4B4B"

    def _pain_color(v):
        if not isinstance(v, float):
            return ""
        if v < 0.20:
            return "#00C853"
        if v < 0.50:
            return "#FF9800"
        return "#FF4B4B"

    def _hold_color(v):
        if not isinstance(v, float):
            return ""
        if v >= 0.70:
            return "#00C853"
        if v >= 0.40:
            return "#FF9800"
        return "#FF4B4B"

    comfort_colors = {"High": "#00C853", "Medium": "#FF9800", "Low": "#FF4B4B"}

    def _stars(pct: int) -> str:
        if pct >= 95:
            return "⭐⭐⭐⭐⭐"
        if pct >= 80:
            return "⭐⭐⭐⭐"
        if pct >= 65:
            return "⭐⭐⭐"
        if pct >= 50:
            return "⭐⭐"
        return "⭐"

    hold_ability = res.get("hold_abilityScore")
    comfort = res.get("comfortScore") or "-"
    max_drawdown = res.get("maxDrawdownPct")
    current_drawdown = res.get("currentDrawdownPct")
    pain = res.get("painRatio")

    hold_pct = int(hold_ability * 100) if isinstance(hold_ability, float) else 0
    pain_str = f"{pain * 100:.0f}%" if isinstance(pain, float) else "-"
    mdd_str = f"{max_drawdown:.1f}%" if isinstance(max_drawdown, float) else "-"
    curr_str = (
        f"{current_drawdown:.1f}%" if isinstance(current_drawdown, float) else "-"
    )
    hold_str = f"{hold_pct}%"

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["🎯 Decision", "⚠️ Risk", "📊 Quant", "📋 FA", "📉 Charts"]
    )

    with tab1:
        hero_row = render_analysis_metrics_row(
            {
                "🏆 持有力": (
                    f"{hold_str}"
                    f"<span style='font-size:0.95rem;letter-spacing:1px;margin-left:6px;'>"
                    f"{_stars(hold_pct)}</span>",
                    _hold_color(hold_ability),
                ),
                "舒適度": (comfort, comfort_colors.get(comfort, "")),
            }
        )
        st.markdown(hero_row, unsafe_allow_html=True)

        price_dic = {
            "股價": res.get("股價", "-"),
            "日常": res.get("日常波段", "-"),
            "回測": res.get("技術回測", "-"),
            "狙擊": res.get("狙擊位", "-"),
        }
        st.markdown(
            render_analysis_metrics_row(price_dic, "🎯 建議掛單"),
            unsafe_allow_html=True,
        )

        tags = res.get("tags")
        if tags:
            tag_html = "".join([f'<span class="light_tags">{t}</span>' for t in tags])
            st.markdown(
                f"<div class='tag-report-row'>{tag_html}</div>",
                unsafe_allow_html=True,
            )
        diag = res.get("技術診斷")
        if diag:
            st.info(str(diag))

    with tab2:
        risk_row1 = render_analysis_metrics_row(
            {
                "MDD": (mdd_str, _dd_color(max_drawdown)),
                "目前回撤": (curr_str, _dd_color(current_drawdown)),
                "Pain Ratio": (pain_str, _pain_color(pain)),
                "舒適度": (comfort, comfort_colors.get(comfort, "")),
            },
            "⚠️ 風險指標",
        )
        risk_row2 = render_analysis_metrics_row(
            {
                "持有力": (hold_str, _hold_color(hold_ability)),
                "Sharpe": res.get("夏普值", "-"),
                "Alpha 勝率": res.get("Alpha 勝率", "-"),
                "月度 α": res.get("月度 Alpha", "-"),
            }
        )
        st.markdown(risk_row1 + risk_row2, unsafe_allow_html=True)

    with tab3:
        quant_row1 = render_analysis_metrics_row(
            {
                "RS%": res.get("RS 百分位", "-"),
                "RSI": f"{res.get('RSI', 0):.1f}",
                "Bias%": (
                    res.get("乖離率 (Bias)", "-"),
                    _anomaly_color(res.get("乖離率 (Bias)"), "bias"),
                ),
                "量比": (
                    res.get("量比", "-"),
                    _anomaly_color(res.get("量比"), "vol_ratio"),
                ),
            },
            "📊 量化分析",
        )
        ma_row = render_analysis_metrics_row(
            {
                "MA20": res.get("MA20", "-"),
                "MA60": res.get("MA60", "-"),
                "MA120": res.get("MA120", "-"),
                "MA250": res.get("MA250", "-"),
            },
            "📈 均線參考",
        )
        st.markdown(quant_row1 + ma_row, unsafe_allow_html=True)

    with tab4:
        pe_v = res.get("PE")
        eps_v = res.get("EPS")
        try:
            pe_str = f"{float(pe_v):.1f}" if pe_v is not None else "-"
        except TypeError, ValueError:
            pe_str = "-"
        try:
            eps_str = f"{float(eps_v):.2f}" if eps_v is not None else "-"
        except TypeError, ValueError:
            eps_str = "-"

        fund_row = render_analysis_metrics_row(
            {
                "EPS": eps_str,
                "P/E": (pe_str, _anomaly_color(pe_v, "pe")),
                "殖利率": (
                    res.get("殖利率", "-"),
                    _anomaly_color(res.get("殖利率"), "yield"),
                ),
                "PEG": res.get("PEG", "-"),
            },
            "📋 基本面",
        )
        st.markdown(fund_row, unsafe_allow_html=True)

    with tab5:
        render_price_chart(res["代碼"])


def show_manual_analysis_page():
    st.info("請在此輸入標的代碼，系統將執行深度量化診斷。")
    manual_codes = st.text_input(
        "🔍 代碼輸入", placeholder="例如: 2330.TW 6284.TWO VOO"
    )

    if manual_codes:
        codes = [c.strip().upper() for c in manual_codes.split() if c.strip()]
        if codes:
            manual_df = pd.DataFrame(
                [
                    {
                        "市場": "手動",
                        "類型": "個股",
                        "名稱": c,
                        "代碼": c,
                        "幣別": "TWD",
                        "單位數": 0,
                        "平均成本": 0.0,
                        "漲跌": "-",
                        "股價": 0.0,
                        "建議掛單": 0.0,
                        "成本": 0,
                        "市值": 0,
                        "損益": 0,
                        "報酬率": 0.0,
                        "佔比": 0.0,
                        "_get_value": True,
                    }
                    for c in codes
                ]
            )
            with st.spinner("分析中..."):
                if hasattr(dashboard_logic, "clear_ticker_cache"):
                    for code in codes:
                        dashboard_logic.clear_ticker_cache(code)
                adv_manual = dashboard_logic.run_advanced_analysis(manual_df)
                if not adv_manual.empty:
                    for _, res in adv_manual.iterrows():
                        with st.expander(
                            f"📈 {res['名稱']} ({res['代碼']}) 報告", expanded=True
                        ):
                            render_advanced_analysis_ui(res)
