# -*- coding: utf-8 -*-
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import platform
from assets_config import ASSETS
from rich.console import Console

console = Console()


def set_chinese_font():
    """自動根據作業系統設定中文字體，避免圓餅圖出現亂碼"""
    system = platform.system()
    if system == "Darwin":  # Mac
        plt.rcParams["font.sans-serif"] = ["Arial Unicode MS"]
    elif system == "Windows":  # Windows
        plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei"]
    plt.rcParams["axes.unicode_minus"] = False


def get_exchange_rate():
    """獲取最新 JPY/TWD 匯率，失敗時使用安全預設值"""
    try:
        # 2026 年預期匯率可能波動，優先嘗試抓取即時數據
        rate = yf.Ticker("JPYTWD=X").fast_info["last_price"]
        if rate is None:
            raise ValueError
        return rate
    except Exception:
        print("⚠️ 提醒：無法取得即時匯率，將使用預設值 0.215")
        return 0.215


def get_trend_symbol(value, styled=True):
    symbol = "🔺" if value > 0 else "🔻"
    if styled:
        return f"\033[31m{symbol}\033[0m" if value > 0 else f"\033[32m{symbol}\033[0m"
    return symbol


def check_market_radar():
    """
    抓取先行指標：S&P 500 期貨 (ES=F) 與 日圓匯率 (JPY=X)
    以及核心部位 1655.T 對照
    """
    radar_tickers = {"ES=F": "美股期貨指標", "JPY=X": "美元/日圓匯率"}

    print("--- 🌍 全球市場即時雷達 ---")
    for ticker, name in radar_tickers.items():
        try:
            t = yf.Ticker(ticker)
            last_price = t.fast_info["last_price"]

            # 計算漲跌幅 (需抓取昨日收盤)
            hist = t.history(period="2d")
            if not hist.empty:
                prev_close = hist["Close"].iloc[0]
                change_pct = ((last_price - prev_close) / prev_close) * 100
                symbol = get_trend_symbol(change_pct)
                print(
                    f"{name} ({ticker}): {last_price:,.2f} | 今日漲跌: {symbol} {change_pct:.2f}%"
                )
        except Exception:
            print(f"⚠️ 無法取得 {name} ({ticker}) 數據")

    # 2. 抓取您的核心部位 1655.T 對照
    try:
        etf_1655 = yf.Ticker("1655.T").fast_info
        etf_price = etf_1655["last_price"]
        print(f"\n您的標的 (1655.JP): {etf_price:,.1f} JPY")
    except Exception:
        pass
    print("-" * 30)


def plot_asset_allocation(df, jpy_twd):
    """繪製資產分佈圓餅圖 (市場別 & 項目別)"""

    # 定義共用的 autopct 產生器
    def make_autopct(values):
        def my_autopct(pct):
            total = sum(values)
            val = int(round(pct * total / 100.0))
            # 若佔比小於 1% 則不顯示文字，避免重疊
            return f"{pct:.1f}%\n(${val:,})" if pct > 1 else ""

        return my_autopct

    # 建立 1x2 的子圖 (寬度設大一點以容納兩張圖)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # --- 左圖：市場分佈 ---
    market_dist = df.groupby("市場")["台幣市值"].sum()
    market_dist.plot(
        kind="pie",
        autopct=make_autopct(market_dist),
        startangle=140,
        shadow=True,
        ax=axes[0],
        ylabel="",
    )
    axes[0].set_title(f"資產分佈 - 市場別 (匯率: {jpy_twd:.4f})", fontsize=14)

    # --- 右圖：項目分佈 ---
    # 移除名稱中的 Emoji，避免 Matplotlib 字型警告
    clean_names = (
        df["名稱"]
        .astype(str)
        .str.replace("🏆 ", "", regex=False)
        .str.replace("🚩 ", "", regex=False)
    )
    item_dist = df.set_index(clean_names)["台幣市值"]
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
    plt.show()


def run_precision_dashboard():
    check_market_radar()
    set_chinese_font()
    jpy_twd = get_exchange_rate()
    results = []
    currency_symbols = {"JPY": "¥", "USD": "$"}
    # 這裡定義獲利與比例的門檻
    PROFIT_GOAL = 100  # 100% 翻倍勳章
    # WARNING_WEIGHT = 35  # 單一標的超過 35% 警示

    def calculate_metrics(
        asset, val_origin, cost_origin, rate, source, asset_type, price=None
    ):
        val_twd = val_origin * rate
        ccy = asset["ccy"]
        symbol = currency_symbols.get(ccy, "")
        origin_str = f"{symbol}{val_origin:,.0f}" if ccy != "TWD" else "--"

        cost_str = (
            f"{symbol}{cost_origin:,.0f}"
            if (ccy != "TWD" and cost_origin > 0)
            else "--"
        )
        cost_twd = cost_origin * rate
        pl_val = val_twd - cost_twd
        pl_pct = (pl_val / cost_twd * 100) if cost_twd != 0 else 0

        # --- 獲利勳章邏輯 ---
        name = asset["name"]
        if pl_pct >= PROFIT_GOAL:
            name = "🏆 " + name
        elif pl_pct >= 20:
            name = "🚩 " + name

        price_str = f"{price:,.2f}" if price is not None else "--"

        return {
            "市場": asset["market"],
            "類型": asset_type,
            "代碼": asset["id"],
            "名稱": name,
            "幣別": ccy,
            "成本": cost_str,
            "市值": origin_str,
            "台幣市值": round(val_twd),
            "台幣成本": round(cost_twd),
            "股價": price_str,
            "損益": round(pl_val),
            "報酬率": pl_pct,
            "來源": source,
        }

    # 1. 處理 基金 (手動輸入最新淨值)
    for fund in ASSETS["funds"].values():
        rate = jpy_twd if fund["ccy"] == "JPY" else 1

        # 計算總單位數與總成本 (支援多筆紀錄)
        investments = fund.get("investment", [])
        total_units = sum(i.get("units", 0) for i in investments)
        total_cost = sum(i.get("cost", 0) for i in investments)

        # 如果資產有提供 "value" 欄位，則優先使用該值，否則由單位和淨值計算
        val_origin = fund.get("value", fund["nav"] * total_units)
        results.append(
            calculate_metrics(fund, val_origin, total_cost, rate, "Manual", "基金")
        )

    # 2. 處理 ETF (自動抓取最新股價)
    for etf in ASSETS["etfs"].values():
        try:
            ticker = yf.Ticker(etf["id"])
            price = ticker.fast_info["last_price"]
            # 換算為台幣
            rate = jpy_twd if etf["ccy"] == "JPY" else 1

            # 計算總股數與總成本 (支援多筆紀錄)
            investments = etf.get("investment", [])
            total_shares = sum(i.get("shares", 0) for i in investments)
            total_cost = sum(i.get("cost", 0) for i in investments)

            val_origin = price * total_shares
            results.append(
                calculate_metrics(
                    etf, val_origin, total_cost, rate, "Yahoo", "ETF", price=price
                )
            )
        except Exception:
            print(f"❌ 無法抓取 ETF: {etf['id']}，請檢查網路或代碼。")

    # 3. 數據處理與視覺化
    df = pd.DataFrame(results)
    # 依照 幣別(升冪) 與 報酬率(降冪) 排序
    df.sort_values(by=["幣別", "報酬率"], ascending=[False, False], inplace=True)

    # 計算佔比
    total_value = df["台幣市值"].sum()
    df["佔比"] = (df["台幣市值"] / total_value * 100).map("{:.1f}%".format)

    # 檢查是否在 Jupyter 環境中
    is_jupyter = False
    try:
        from IPython.core.getipython import get_ipython

        shell = get_ipython().__class__.__name__
        if shell == "ZMQInteractiveShell":
            is_jupyter = True
    except Exception:
        pass

    # 4. 輸出報表
    print("\n" + "=" * 100)
    print(f"📅 報表產出時間: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 100)

    # 建立顯示用的 DataFrame (格式化數值)
    format_df = df[
        [
            "市場",
            "類型",
            "名稱",
            "代碼",
            "股價",
            "成本",
            "市值",
            "台幣成本",
            "台幣市值",
            "損益",
            "報酬率",
            "佔比",
            "來源",
        ]
    ].copy()
    format_df["台幣市值"] = format_df["台幣市值"].map(lambda x: f"${x:,.0f}")
    format_df["台幣成本"] = format_df["台幣成本"].map(lambda x: f"${x:,.0f}")

    # Jupyter 使用 CSS 上色，不需 ANSI 色碼；Console 需要 ANSI 色碼
    use_ansi = not is_jupyter
    format_df["損益"] = format_df["損益"].map(
        lambda x: f"{get_trend_symbol(x, styled=use_ansi)} ${x:+,.0f}"
    )
    format_df["報酬率"] = format_df["報酬率"].map(
        lambda x: f"{get_trend_symbol(x, styled=use_ansi)} {x:+.1f}%"
    )

    if is_jupyter:
        try:
            from IPython.display import display

            # 定義上色邏輯：紅漲 (red)、綠跌 (green)
            def color_pl(val):
                if isinstance(val, str):
                    if "+" in val:
                        return (
                            "color: #ff5252; font-weight: bold;"  # 亮紅色 (適合深色底)
                        )
                    if "-" in val:
                        return (
                            "color: #69f0ae; font-weight: bold;"  # 亮綠色 (適合深色底)
                        )
                return ""

            # 設定表格樣式：靠右對齊、文字顏色
            # 使用 Pandas Styler 進行美化 (Pandas 3.0+ 使用 map 取代 applymap)
            styled_df = (
                format_df.style.map(color_pl, subset=["損益", "報酬率"])
                .set_properties(
                    **{
                        "text-align": "right",
                        "font-family": "monospace",
                        "background-color": "#333333",
                        "color": "#ffffff",
                    }
                )
                .set_table_styles(
                    [
                        {
                            "selector": "th",
                            "props": [
                                ("text-align", "center"),
                                ("background-color", "#212121"),
                                ("color", "#ffffff"),
                            ],
                        },
                        {
                            "selector": "tr:hover",
                            "props": [("background-color", "#424242")],
                        },
                    ]
                )
            )
            display(styled_df)
        except Exception:
            pass
    else:
        # 終端機環境：維持純文字輸出
        # 啟用東亞寬度設定以修正中文字元對齊問題
        pd.set_option("display.unicode.east_asian_width", True)

        # 手動補空白以達成靠右對齊 (對齊個位數)
        for col in [
            "成本",
            "市值",
            "台幣市值",
            "台幣成本",
            "股價",
            "損益",
            "報酬率",
            "佔比",
        ]:
            max_len = format_df[col].astype(str).map(len).max()
            format_df[col] = format_df[col].astype(str).str.rjust(max_len)
        print(format_df.to_string(index=False, justify="right"))

    total_cost = df["台幣成本"].sum()
    total_pl = df["損益"].sum()
    total_roi = (total_pl / total_cost * 100) if total_cost != 0 else 0

    # 根據損益決定終端機文字顏色 (簡單版)
    pl_color = ""  # 若需要終端機顏色可在此擴充 ANSI code

    print(f"\n💰 總市值預估 (TWD): ${df['台幣市值'].sum():,}")
    print(f"💵 總投入成本 (TWD): ${total_cost:,.0f}")
    print(f"📈 帳面損益 (TWD):   {pl_color}${total_pl:+,.0f} ({total_roi:+.2f}%)")
    print("=" * 100)

    # 繪製圓餅圖 (僅在 Jupyter 顯示)
    if is_jupyter:
        plot_asset_allocation(df, jpy_twd)


if __name__ == "__main__":
    run_precision_dashboard()
