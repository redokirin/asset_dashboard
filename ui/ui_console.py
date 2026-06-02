# -*- coding: utf-8 -*-
import pandas as pd

try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    from rich.align import Align

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


CASH_MARKETS = {"cash", "現金"}


def _cash_mask(df):
    if "市場" not in df.columns:
        return pd.Series(False, index=df.index)
    market_names = df["市場"].astype(str).str.strip().str.lower()
    return market_names.isin(CASH_MARKETS)


def show_console_rich(
    df,
    radar_data,
    market_share_data,
    advanced_results=None,
    show_report=True,
    console=None,
    is_list_mode=False,
    show_detail=False,
):
    if not HAS_RICH:
        print(df.to_string())
        return
    cash_mask = _cash_mask(df)
    investment_df = df[~cash_mask]
    cash_df = df[cash_mask]

    console = console or Console()
    console.print("\n[bold cyan]--- 全球市場即時雷達 ---[/bold cyan]")
    radar_table = Table(box=box.SIMPLE_HEAD)
    radar_table.add_column("指標名稱")
    radar_table.add_column("數值", justify="right")
    radar_table.add_column("漲跌幅", justify="right")
    for item in radar_data:
        color = "red" if item["漲跌幅"] > 0 else "green"
        radar_table.add_row(
            item["名稱"],
            f"{item['數值']:,.2f}",
            f"[{color}]{item['漲跌幅']:+.2f}%[/{color}]",
        )
    console.print(radar_table)

    if show_report:
        console.print("[bold cyan]--- 市場分佈佔比 ---[/bold cyan]")
        market_share_table = Table(box=box.SIMPLE_HEAD, show_header=True)
        market_share_table.add_column("市場", style="cyan")
        market_share_table.add_column("總市值", justify="right")
        market_share_table.add_column("佔比", justify="right")
        investment_total = investment_df["市值"].sum()
        if investment_total:
            investment_market_sum = investment_df.groupby("市場")["市值"].sum()
            for market, market_value in investment_market_sum.items():
                market_share_table.add_row(
                    market,
                    f"${market_value:,.0f}",
                    f"{market_value / investment_total * 100:.1f}%",
                )
        console.print(market_share_table)

        total_value = df["市值"].sum()
        if total_value:
            console.print("[bold cyan]--- 資產水位 ---[/bold cyan]")
            liquidity_table = Table(box=box.SIMPLE_HEAD, show_header=True)
            liquidity_table.add_column("幣別", style="cyan")
            liquidity_table.add_column("投資資產", justify="right")
            liquidity_table.add_column("現金部位", justify="right")
            liquidity_table.add_column("投資佔比", justify="right")
            liquidity_table.add_column("現金佔比", justify="right")
            for ccy in sorted(df["幣別"].dropna().astype(str).unique()):
                ccy_df = df[df["幣別"].astype(str) == ccy]
                ccy_cash_mask = _cash_mask(ccy_df)
                ccy_total = ccy_df["市值"].sum()
                if ccy_total == 0:
                    continue
                investment_value = ccy_df[~ccy_cash_mask]["市值"].sum()
                cash_value = ccy_df[ccy_cash_mask]["市值"].sum()
                liquidity_table.add_row(
                    ccy,
                    f"${investment_value:,.0f}",
                    f"${cash_value:,.0f}",
                    f"{investment_value / ccy_total * 100:.1f}%",
                    f"{cash_value / ccy_total * 100:.1f}%",
                )
            console.print(liquidity_table)

        if show_detail and not cash_df.empty:
            console.print("[bold cyan]--- 現金帳戶明細 ---[/bold cyan]")
            cash_table = Table(box=box.SIMPLE_HEAD, show_header=True)
            cash_table.add_column("名稱", style="white")
            cash_table.add_column("幣別", style="yellow", justify="center")
            cash_table.add_column("餘額", justify="right")
            cash_table.add_column("市值", justify="right")
            cash_table.add_column("佔比", justify="right")
            for _, row in cash_df.sort_values("市值", ascending=False).iterrows():
                cash_table.add_row(
                    str(row["名稱"]),
                    str(row["幣別"]),
                    f"{row['單位數']:,.0f}",
                    f"${row['市值']:,.0f}",
                    f"{row['佔比']:.1f}%",
                )
            console.print(cash_table)

    if advanced_results is not None and not advanced_results.empty:
        console.print("\n[bold cyan]--- 進階量化分析 ---[/bold cyan]")
        for _, row in advanced_results.iterrows():
            ticker = str(row["代碼"])
            console.print(f"\n[bold yellow]== {ticker} ==[/bold yellow]")
            console.print(
                f"EPS:{row.get('EPS', 0):.2f} 本益比:{row.get('PE', 0):.1f} 殖利率:{row.get('殖利率', '-')} PEG:{row.get('PEG', '-')} 量比:{row.get('量比', '-')}"
            )

            # ── 風險指標 helper ────────────────────────────────────────────────
            _mdd = row.get("maxDrawdownPct")
            _curr_dd = row.get("currentDrawdownPct")
            _pain = row.get("painRatio")
            _comfort = row.get("comfortScore") or "-"
            _hold = row.get("hold_abilityScore")

            def _dd_color(v):
                """回撤深度語義色（Rich markup）"""
                if v is None or not isinstance(v, (int, float)):
                    return "white"
                a = abs(v)
                if a < 5:
                    return "green"
                if a < 15:
                    return "yellow"
                return "red"

            def _hold_color(v):
                """持有力語義色"""
                if v is None or not isinstance(v, (int, float)):
                    return "white"
                if v >= 0.70:
                    return "green"
                if v >= 0.40:
                    return "yellow"
                return "red"

            _comfort_color = {"High": "green", "Medium": "yellow", "Low": "red"}.get(
                _comfort, "white"
            )

            _mdd_str = f"{_mdd:.1f}%" if isinstance(_mdd, float) else "-"
            _curr_str = f"{_curr_dd:.1f}%" if isinstance(_curr_dd, float) else "-"
            _pain_str = f"{_pain * 100:.0f}%" if isinstance(_pain, float) else "-"
            _hold_str = f"{_hold * 100:.0f}%" if isinstance(_hold, float) else "-"

            if is_list_mode:
                val_alpha = (
                    str(row.get("月度 Alpha", "-"))
                    .replace("[red]", "")
                    .replace("[green]", "")
                    .replace("[/]", "")
                )
                metrics = [
                    f"  > 股價: {row.get('股價', '-')} | RS%: {row.get('RS 百分位', '-')} | RSI: {row.get('RSI', 0):.1f}",
                    f"  > Alpha勝率: {row.get('Alpha 勝率', '-')} | 月度Alpha: {val_alpha} | 夏普值: {row.get('夏普值', '-')}",
                    f"  > 建議位階: 波段 {row.get('日常波段', '-')} / 回測 {row.get('技術回測', '-')} / 狙擊 {row.get('狙擊位', '-')}",
                    (
                        f"  > 風險: MDD [{_dd_color(_mdd)}]{_mdd_str}[/] | "
                        f"目前回撤 [{_dd_color(_curr_dd)}]{_curr_str}[/] | "
                        f"Pain {_pain_str} | "
                        f"舒適度 [{_comfort_color}]{_comfort}[/] | "
                        f"持有力 [{_hold_color(_hold)}]{_hold_str}[/]"
                    ),
                ]
                for line in metrics:
                    console.print(line)
            else:
                mini_table = Table(box=box.SIMPLE, show_header=True)
                cols = [
                    "股價",
                    "日常波段",
                    "技術回測",
                    "狙擊目標",
                    "MA20",
                    "MA60",
                    "MA120",
                    "MA250",
                    "RS",
                    "RS%",
                    "RSI",
                    "α勝率",
                    "月度α",
                    "夏普值",
                    "乖離率",
                ]
                for col in cols:
                    mini_table.add_column(col, justify="right")
                mini_table.add_row(
                    str(row.get("股價", "-")),
                    str(row.get("日常波段", "-")),
                    str(row.get("技術回測", "-")),
                    str(row.get("狙擊位", "-")),
                    str(row.get("MA20", "-")),
                    str(row.get("MA60", "-")),
                    str(row.get("MA120", "-")),
                    str(row.get("MA250", "-")),
                    str(row.get("RS", "-")),
                    str(row.get("RS%", "-")),
                    f"{row.get('RSI', 0):.1f}",
                    str(row.get("Alpha 勝率", "-")),
                    str(row.get("月度 Alpha", "-")),
                    str(row.get("夏普值", "-")),
                    str(row.get("乖離率", "-")),
                )
                console.print(mini_table)

                # ── 風險指標小表 ───────────────────────────────────────────────
                risk_table = Table(box=box.SIMPLE, show_header=True)
                for col in ["MDD", "目前回撤", "Pain Ratio", "舒適度", "持有力"]:
                    risk_table.add_column(col, justify="right")
                risk_table.add_row(
                    f"[{_dd_color(_mdd)}]{_mdd_str}[/]",
                    f"[{_dd_color(_curr_dd)}]{_curr_str}[/]",
                    _pain_str,
                    f"[{_comfort_color}]{_comfort}[/]",
                    f"[{_hold_color(_hold)}]{_hold_str}[/]",
                )
                console.print(risk_table)

            console.print(
                f"{' '.join(row.get('tags', []))}\n{row.get('技術診斷', '-')}"
            )

    if show_report:
        console.print(
            f"\n[bold yellow]📅 報表時間: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}[/bold yellow]"
        )
        table = Table(box=box.SIMPLE)
        cols_config = [
            ("市場", "cyan", "left"),
            ("名稱", "white", "left"),
            ("代碼", "dim white", "left"),
            ("幣別", "yellow", "center"),
            ("單位數", "dim white", "right"),
            ("平均成本", "dim white", "right"),
            ("股價", "bold white", "right"),
            ("漲跌", "bold", "right"),
            # ("建議掛單", "magenta", "right"),
            ("成本", "dim white", "right"),
            ("市值", "bold white", "right"),
            ("損益", "bold", "right"),
            ("報酬率", "bold", "right"),
            ("佔比", "blue", "right"),
        ]

        if not show_detail:
            cols_to_keep = [
                "市場",
                "名稱",
                "幣別",
                "股價",
                "漲跌",
                "市值",
                "損益",
                "報酬率",
                "佔比",
            ]
            cols_config = [c for c in cols_config if c[0] in cols_to_keep]

        for c, s, j in cols_config:
            table.add_column(c, style=s, justify=j)
        for _, row in investment_df.iterrows():
            color = "red" if row["損益"] > 0 else "green"
            change_str = (
                f"[{'red' if row['漲跌'] > 0 else 'green'}]{row['漲跌']:+,.2f}[/]"
                if pd.notnull(row["漲跌"])
                else "-"
            )

            data_map = {
                "市場": str(row["市場"]),
                "名稱": str(row["名稱"]),
                "代碼": str(row["代碼"]),
                "幣別": str(row["幣別"]),
                "單位數": f"{row['單位數']:,.2f}",
                "平均成本": f"{row['平均成本']:,.2f}",
                "股價": f"{row['股價']:,.2f}",
                "漲跌": change_str,
                "成本": f"${row['成本']:,}",
                "市值": f"${row['市值']:,}",
                "損益": f"[{color}]{row['損益']:+,.0f}[/]",
                "報酬率": f"[{color}]{row['報酬率']:+.1f}%[/]",
                "佔比": f"{row['佔比']:.1f}%",
            }
            table.add_row(*[data_map[c[0]] for c in cols_config])
        console.print(table)
        console.print(
            f"\n💰 [bold]總市值: ${df['市值'].sum():,}[/] | 📈 [bold]總損益: {investment_df['損益'].sum():+,.0f}[/]"
        )
