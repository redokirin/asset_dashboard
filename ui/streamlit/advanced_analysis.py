# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from core import dashboard_logic
from core.exporters import export_single_target_for_ai
from ui.streamlit.charts import render_price_chart
from ui.streamlit.components import render_analysis_metrics_row


def _fmt_reason(r: str) -> str:
    import re

    m = re.match(r"Pain Ratio (\d+)%（昨日 (\d+)%）", r)
    return f"Pain Ratio {m.group(2)}% > {m.group(1)}%" if m else r


def render_advanced_analysis_ui(res, warning=None, actionable=None, hold_off=None):
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
    ann_vol = res.get("annualizedVol")
    vol_grade = res.get("volGrade") or "-"

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
        _daily_upper = res.get("dailyUpper")
        _zone_status = res.get("entryZoneStatus") or "-"
        _price_now = res.get("股價", "-")
        _daily_bid = res.get("日常波段", "-")
        _retest_bid = res.get("技術回測", "-")
        _sniper_bid = res.get("狙擊位", "-")
        _bdr = res.get("boundaryDailyRetest")
        _brs = res.get("boundaryRetestSniper")

        if _daily_upper is not None and _bdr is not None and _brs is not None:
            # Price zone bar — 4 equal 25% segments, price marker proportional within zone
            try:
                _p = float(str(_price_now).replace(",", ""))
                _zd = _daily_upper - _bdr or 1.0
                _zr = _bdr - _brs or 1.0
                if _p >= _daily_upper:
                    _price_pct = max(
                        0.0, min(25.0, ((_daily_upper + _zd - _p) / _zd) * 25)
                    )
                elif _p >= _bdr:
                    _price_pct = 50.0 - ((_p - _bdr) / _zd) * 25
                elif _p >= _brs:
                    _price_pct = 75.0 - ((_p - _brs) / _zr) * 25
                else:
                    _price_pct = min(100.0, 75.0 + ((_brs - _p) / _zr) * 25)
            except ValueError, TypeError, ZeroDivisionError:
                _price_pct = 12.5

            st.markdown(
                f"""<div style="margin:4px 0 2px 0;">
                  <div style="position:relative; height:18px; font-size:0.9rem; color:#aaa;">
                    <span style="position:absolute;left:25%;transform:translateX(-50%);">{_daily_upper:.2f}</span>
                    <span style="position:absolute;left:50%;transform:translateX(-50%);">{_bdr:.2f}</span>
                    <span style="position:absolute;left:75%;transform:translateX(-50%);">{_brs:.2f}</span>
                  </div>
                  <div style="display:flex;height:14px;border-radius:6px;overflow:hidden;">
                    <div style="width:25%;background:#ef4444;" title="追價警戒 > {_daily_upper:.2f}"></div>
                    <div style="width:25%;background:#f97316;" title="日常 {_bdr:.2f}~{_daily_upper:.2f}"></div>
                    <div style="width:25%;background:#22c55e;" title="回測 {_brs:.2f}~{_bdr:.2f}"></div>
                    <div style="width:25%;background:#86efac;" title="狙擊 < {_brs:.2f}"></div>
                  </div>
                  <div style="position:relative;height:20px;margin-top:1px;">
                    <span style="position:absolute;left:{_price_pct:.1f}%;transform:translateX(-50%);font-size:1rem;color:#fff;white-space:nowrap;">▲ {_price_now}</span>
                  </div>
                </div>""",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                render_analysis_metrics_row(
                    {"日常": _daily_bid, "回測": _retest_bid, "狙擊": _sniper_bid},
                    "🎯 建議掛單",
                ),
                unsafe_allow_html=True,
            )

        if actionable:
            _parts = []
            if actionable.get("fib_price") is not None:
                _parts.append(f"最近支撐 {actionable['fib_price']:.2f}")
            if actionable.get("quality_note"):
                _parts.append(actionable["quality_note"])
            if _parts:
                st.caption("｜".join(_parts))

        tags = res.get("tags")
        if tags:
            from core.tags import TAG_DISPLAY
            tag_html = "".join([f'<span class="light_tags">{TAG_DISPLAY.get(t, t)}</span>' for t in tags])
            st.markdown(
                f"<div class='tag-report-row'>{tag_html}</div>",
                unsafe_allow_html=True,
            )
        diag = res.get("技術診斷")
        if diag:
            st.info(str(diag))
        if hold_off:
            reason = hold_off.get("quality_note") or "量縮上漲，不追"
            zone_str = f"區間 {hold_off['zone_range']}" if hold_off.get("zone_range") else ""
            body = "｜".join(p for p in [zone_str, reason] if p)
            st.info(f"⚪ 觀望\n\n{body}")
        if warning:
            reasons = "｜".join(_fmt_reason(r) for r in warning["reasons"])
            st.warning(f"{warning['advice']}\n\n{reasons}")

    with tab2:

        def _vol_color(grade):
            return {"低波動": "#00C853", "中波動": "#FF9800", "高波動": "#FF4B4B"}.get(
                grade, ""
            )

        vol_str = f"{ann_vol:.1%}" if isinstance(ann_vol, float) else "-"
        hero_row = render_analysis_metrics_row(
            {
                "🏆 持有力": (
                    f"{hold_str}"
                    f"<span style='font-size:0.95rem;letter-spacing:1px;margin-left:6px;'>"
                    f"{_stars(hold_pct)}</span>",
                    _hold_color(hold_ability),
                ),
                "年化波動率": (vol_str, _vol_color(vol_grade)),
            }
        )
        st.markdown(hero_row, unsafe_allow_html=True)
        risk_row1 = render_analysis_metrics_row(
            {
                "舒適度": (comfort, comfort_colors.get(comfort, "")),
                "MDD": (mdd_str, _dd_color(max_drawdown)),
                "目前回撤": (curr_str, _dd_color(current_drawdown)),
            },
            "⚠️ 風險指標",
        )
        risk_row2 = render_analysis_metrics_row(
            {
                "Pain Ratio": (pain_str, _pain_color(pain)),
                "Sharpe": res.get("夏普值", "-"),
                "Alpha 勝率": res.get("Alpha 勝率", "-"),
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
                            ticker = res["代碼"]
                            date_str = pd.Timestamp.now().strftime("%Y%m%d")
                            st.download_button(
                                label="📥 導出 AI 報告",
                                data=export_single_target_for_ai(res).encode("utf-8"),
                                file_name=f"ai_report_{ticker}_{date_str}.md",
                                mime="text/markdown",
                                key=f"dl_{ticker}",
                            )
