# -*- coding: utf-8 -*-
import os

import streamlit as st


def load_css():
    """載入外部 CSS 檔案樣式"""
    css_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "style.css")
    if os.path.exists(css_file):
        with open(css_file, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def get_color_class(val):
    """獲取數值文字顏色 (紅漲綠跌)"""
    if val > 0:
        return "text-red"
    if val < 0:
        return "text-green"
    return ""


def get_tag_class(val):
    """獲取漲跌標籤背景色 (紅漲綠跌)"""
    if isinstance(val, str):
        if "+" in val:
            return "bg-red-tag"
        if "-" in val:
            if val.strip() == "-":
                return "bg-grey-tag"
            return "bg-green-tag"
        return "bg-grey-tag"

    if val > 0:
        return "bg-red-tag"
    if val < 0:
        return "bg-green-tag"
    return "bg-grey-tag"


def render_title_component(title):
    st.markdown(f"<div class='section-title'>{title}</div>", unsafe_allow_html=True)


def render_horizontal_value_tag_component(value, tag):
    """橫向組件 -> 依照使用者要求改為 垂直排列 (Value above Tag)"""
    class_name_tag = get_tag_class(tag)

    if isinstance(value, str):
        display_val = value
    else:
        display_val = f"{value:+,.0f}" if value != 0 else f"{value:,.0f}"

    display_tag = f"{tag:+,.2f}%" if isinstance(tag, (int, float)) else str(tag)

    return f"""<div class='asset-value-container' style='align-items: center;'>
                <div class='asset-metric-value'>{display_val}</div>
                <div class='asset-change-tag {class_name_tag}' style='font-size: 0.75rem; margin-top: 2px;'>{display_tag}</div>
                </div>"""


def render_vertical_value_tag_component(value, tag):
    """縱向組件 -> 依照使用者要求改為 水平排列 (Value next to Tag)"""
    class_name_tag = get_tag_class(tag)

    if isinstance(value, str):
        display_val = value
    else:
        display_val = f"{value:,.2f}"

    display_tag = f"{tag:+,.2f}%" if isinstance(tag, (int, float)) else str(tag)

    return f"""<div class='asset-value-row'>
                <span class='asset-price-main'>{display_val}</span>
                <span class='asset-change-tag {class_name_tag}'>{display_tag}</span>
                </div>"""


def render_analysis_metrics_row(metrics_dict, title=None):
    """根據傳入的 dictionary 迴圈產生 analysis-metric-box DIV tag"""
    title_html = f'<div class="analysis-report-title">{title}</div>' if title else ""
    items_html = ""
    for label, value in metrics_dict.items():
        color_style = ""
        if isinstance(value, tuple) and len(value) == 2:
            display_val, color = value
            if color:
                color_style = f" style='color: {color};'"
        else:
            display_val = value

        items_html += (
            f'<div class="analysis-metric-box">'
            f'<div class="analysis-metric-value"{color_style}>{display_val}</div>'
            f'<div class="analysis-metric-label">{label}</div>'
            f"</div>"
        )
    return f'{title_html}<div class="analysis-metrics-flex">{items_html}</div>'


def render_tracking_metrics_row(items, title=None):
    """根據傳入的 list 迴圈產生 analysis-metric-box DIV tag"""
    title_html = f'<div class="analysis-report-title">{title}</div>' if title else ""
    items_html = ""

    for item in items:
        label = item.get("名稱", "")
        val = item.get("數值", 0)
        delta = item.get("漲跌幅", 0)
        items_html += (
            f'<div class="analysis-metric-box">'
            f"{render_horizontal_value_tag_component(val, delta)}"
            f'<div class="analysis-metric-label">{label}</div>'
            f"</div>"
        )
    return f'{title_html}<div class="analysis-metrics-flex">{items_html}</div>'


def render_cost_component(row):
    cost_dic = {
        "單位數": row["單位數"],
        "平均成本": f"${row['平均成本']:,.2f}",
        "成本": f"${row['成本']:,}",
        "市值": f"${row['市值']:,}",
    }

    cost_row = render_analysis_metrics_row(cost_dic)

    st.markdown(
        f"""<div class="analysis-report-row">
                    <div class="analysis-report-col">
                    {cost_row}
                    </div>
                    </div>""",
        unsafe_allow_html=True,
    )


def render_inline_metric(label, value, delta):
    with st.container(border=True, gap="xxsmall"):
        st.markdown(
            f"""<div class='inline-metric-container'>
                <div class='inline-metric-label'>{label}</div>
                {render_horizontal_value_tag_component(value, delta)}
            </div>""",
            unsafe_allow_html=True,
        )


def render_vertical_component(indices):
    for item in indices:
        render_inline_metric(
            item["名稱"], f"{item['數值']:,.2f}", f"{item['漲跌幅']:+.2f}%"
        )


def render_horizontal_component(major_rates):
    n_rate_cols = min(len(major_rates), 2) if major_rates else 1
    rate_cols = st.columns(n_rate_cols)
    for i, item in enumerate(major_rates):
        with rate_cols[i % n_rate_cols]:
            render_inline_metric(
                item["名稱"], f"{item['數值']:,.2f}", f"{item['漲跌幅']:+.2f}%"
            )
