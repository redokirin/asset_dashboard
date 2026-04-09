# -*- coding: utf-8 -*-
"""
UI 組件導出層
本檔案將不同環境的 UI 邏輯分發至獨立模組，以提高維護性。
"""

# 匯入共用邏輯與繪圖
from ui_common import set_chinese_font, plot_asset_allocation

# 匯入 Streamlit 特定組件
from ui_streamlit import (
    load_css,
    render_advanced_analysis_ui,
    show_manual_analysis_page,
    render_title_component,
    render_profit_and_loss_component,
    render_vertical_component,
    render_horizontal_component,
    render_dataframe_component,
    render_shareholding_component,
    render_plotly_pie_charts,
    render_inline_metric,
    show_streamlit
)

# 匯入 Console (Rich) 特定組件
from ui_console import show_console_rich

# 匯入 Jupyter 特定組件
from ui_jupyter import show_jupyter
