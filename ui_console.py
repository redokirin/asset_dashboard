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


def show_console_rich(
    df,
    radar_data,
    market_share_data,
    advanced_results=None,
    show_report=True,
    console=None,
    is_list_mode=False,
):
    if not HAS_RICH:
        print(df.to_string())
        return
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
        for market, data in market_share_data.items():
            market_share_table.add_row(
                market, f"${data['市值']:,.0f}", f"{data['佔比']:.1f}%"
            )
        console.print(market_share_table)

    if advanced_results is not None and not advanced_results.empty:
        console.print("\n[bold cyan]--- 進階量化分析 ---[/bold cyan]")
        for _, row in advanced_results.iterrows():
            ticker = str(row["代碼"])
            console.print(f"\n[bold yellow]== {ticker} ==[/bold yellow]")
            console.print(
                f"EPS:{row.get('EPS', 0):.2f} 本益比:{row.get('PE', 0):.1f} 成交量比率:{row.get('量比', '-')}"
            )
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
                ]
                for line in metrics:
                    console.print(line)
            else:
                mini_table = Table(box=box.SIMPLE, show_header=True)
                cols = [
                    "股價",
                    "RS",
                    "RS%",
                    "RSI",
                    "α勝率",
                    "月度α",
                    "夏普值",
                    "乖離率",
                    "MA20",
                    "MA60",
                    "MA120",
                    "MA250",
                    "日常波段",
                    "技術回測",
                    "狙擊目標",
                ]
                for col in cols:
                    mini_table.add_column(col, justify="right")
                mini_table.add_row(
                    str(row.get("股價", "-")),
                    str(row.get("RS", "-")),
                    str(row.get("RS%", "-")),
                    f"{row.get('RSI', 0):.1f}",
                    str(row.get("Alpha 勝率", "-")),
                    str(row.get("月度 Alpha", "-")),
                    str(row.get("夏普值", "-")),
                    str(row.get("乖離率", "-")),
                    str(row.get("MA20", "-")),
                    str(row.get("MA60", "-")),
                    str(row.get("MA120", "-")),
                    str(row.get("MA250", "-")),
                    str(row.get("日常波段", "-")),
                    str(row.get("技術回測", "-")),
                    str(row.get("狙擊位", "-")),
                )
                console.print(mini_table)
            console.print(
                f"{' '.join(row.get('tags', []))}\n{row.get('技術診斷', '-')}"
            )
            console.print("\n" + "=" * 73)

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
        for c, s, j in cols_config:
            table.add_column(c, style=s, justify=j)
        for _, row in df.iterrows():
            color = "red" if row["損益"] > 0 else "green"
            change_str = (
                f"[{'red' if row['漲跌'] > 0 else 'green'}]{row['漲跌']:+,.2f}[/]"
                if pd.notnull(row["漲跌"])
                else "-"
            )
            table.add_row(
                str(row["市場"]),
                str(row["名稱"]),
                str(row["代碼"]),
                str(row["幣別"]),
                f"{row['單位數']:,.2f}",
                f"{row['平均成本']:,.2f}",
                f"{row['股價']:,.2f}",
                change_str,
                # f"{row['建議掛單']:,.2f}" if row["建議掛單"] > 0 else "-",
                f"${row['成本']:,}",
                f"${row['市值']:,}",
                f"[{color}]{row['損益']:+,.0f}[/]",
                f"[{color}]{row['報酬率']:+.1f}%[/]",
                f"{row['佔比']:.1f}%",
            )
        console.print(table)
        console.print(
            f"\n💰 [bold]總市值: ${df['市值'].sum():,}[/] | 📈 [bold]總損益: {df['損益'].sum():+,.0f}[/]"
        )
