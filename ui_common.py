# -*- coding: utf-8 -*-
import pandas as pd
import matplotlib.pyplot as plt
import platform

def set_chinese_font():
    system = platform.system()
    if system == "Darwin":
        plt.rcParams["font.sans-serif"] = ["Arial Unicode MS"]
    elif system == "Windows":
        plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei"]
    plt.rcParams["axes.unicode_minus"] = False

def plot_asset_allocation(df, exchange_rates):
    def make_autopct(values):
        def my_autopct(pct):
            total = sum(values)
            val = int(round(pct * total / 100.0))
            return f"{pct:.1f}%\n(${val:,})" if pct > 1 else ""
        return my_autopct

    set_chinese_font()
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    market_dist = df.groupby("市場")["市值"].sum()
    market_dist.plot(
        kind="pie",
        autopct=make_autopct(market_dist),
        startangle=140,
        shadow=True,
        ax=axes[0],
        ylabel="",
    )
    rates_str = ", ".join(
        [f"{k}/TWD: {v:.4f}" for k, v in exchange_rates.items() if k != "TWD"]
    )
    axes[0].set_title(f"資產分佈 - 市場別 ({rates_str})", fontsize=14)
    clean_names = df["名稱"].astype(str).str.replace(r"[🏆🚩]", "", regex=True)
    item_dist = df.set_index(clean_names)["市值"]
    item_dist.plot(
        kind="pie",
        autopct=make_autopct(item_dist),
        startangle=140,
        shadow=True,
        ax=axes[1],
        ylabel="",
    )
    axes[1].set_title("資產分佈 - 項目別", fontsize=14)
    plt.tight_layout()
    return fig
