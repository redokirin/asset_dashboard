# -*- coding: utf-8 -*-
import pandas as pd

def export_for_ai(df):
    """導出 AI 分析文本"""
    report = ["--- AI 分析專用數據摘要 ---"]
    for _, row in df.iterrows():
        # 使用列表方式呈現，確保數據完整不截斷
        pl_pct = f"{row['報酬率']:.2f}%" if pd.notnull(row["報酬率"]) else "0%"
        change = f"{row['漲跌']:+.2f}" if pd.notnull(row["漲跌"]) else "0"
        line = (
            f"- {row['代碼']}: 股價 {row['股價']} ({change}), "
            f"平均成本 {row['平均成本']}, 單位數 {row['單位數']}, "
            f"報酬率 {pl_pct}, 建議掛單 {row['建議掛單']}"
        )
        report.append(line)
    report.append("-" * 30)
    return "\n".join(report)
