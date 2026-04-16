# -*- coding: utf-8 -*-
import os
import sys

# 將專案根目錄加入搜尋路徑
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import argparse
import pandas as pd
from ui.dashboard_ui import show_jupyter
from apps import dashboard_cli

def get_env():
    # 檢查是否在 Jupyter Notebook
    try:
        from IPython.core.getipython import get_ipython
        if get_ipython().__class__.__name__ == "ZMQInteractiveShell":
            return "jupyter"
    except Exception:
        pass

    # 檢查是否由 Streamlit 啟動
    if "streamlit" in " ".join(sys.argv).lower():
        return "streamlit"

    return "console"

if __name__ == "__main__":
    env = get_env()

    if env == "streamlit":
        import runpy
        # 確保路徑正確，指向 apps/dashboard_st.py
        script_path = os.path.join(os.path.dirname(__file__), "dashboard_st.py")
        runpy.run_path(script_path, run_name="__main__")
        sys.exit()

    if env == "jupyter":
        from core import dashboard_logic
        print("--- Jupyter 模式啟動 ---")
        radar = dashboard_logic.get_market_radar_data()
        exchange_rates = dashboard_logic.exchange_rate(radar)
        df_res, _ = dashboard_logic.calculate_assets_data(exchange_rates)
        show_jupyter(df_res, radar, exchange_rates)

    if env == "console":
        # 調用 CLI 模式
        dashboard_cli.run_cli()
