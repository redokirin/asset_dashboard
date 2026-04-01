# -*- coding: utf-8 -*-
import sys
import argparse
import pandas as pd
from dashboard_ui import show_jupyter
import dashboard_cli


def get_env():
    # 檢查是否在 Jupyter Notebook
    try:
        from IPython.core.getipython import get_ipython

        if get_ipython().__class__.__name__ == "ZMQInteractiveShell":
            return "jupyter"
    except Exception:
        pass

    # 檢查是否由 Streamlit 啟動 (雖然建議改用 streamlit run dashboard_st.py)
    if "streamlit" in " ".join(sys.argv).lower():
        return "streamlit"

    return "console"


if __name__ == "__main__":
    env = get_env()

    if env == "streamlit":
        import runpy

        runpy.run_path("dashboard_st.py", run_name="__main__")
        sys.exit()

    if env == "jupyter":
        import dashboard_logic

        print("--- Jupyter 模式啟動 ---")
        radar = dashboard_logic.get_market_radar_data()
        exchange_rates = dashboard_logic.exchange_rate(radar)
        df_res, _ = dashboard_logic.calculate_assets_data(exchange_rates)
        show_jupyter(df_res, radar, exchange_rates)
    else:
        # 調用 CLI 模式
        dashboard_cli.run_cli()
