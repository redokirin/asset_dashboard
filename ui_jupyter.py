# -*- coding: utf-8 -*-
import pandas as pd
from ui_common import set_chinese_font


def show_jupyter(df, radar_data, exchange_rates):
    from IPython.display import display

    set_chinese_font()
    print("--- 🌍 全球市場雷達 ---")
    display(pd.DataFrame(radar_data).style.hide(axis="index"))
    print("\n--- 📋 資產明細 ---")
    display(
        df.style.format(
            {
                "單位數": "{:,.2f}",
                "平均成本": "{:,.2f}",
                "股價": "{:,.2f}",
                "市值": "${:,.0f}",
                "損益": "${:+,.0f}",
                "報酬率": "{:+.2f}%",
                "佔比": "{:.1f}%",
            }
        ).map(
            lambda x: "color: red" if x > 0 else "color: green",
            subset=["損益", "報酬率"],
        )
    )
