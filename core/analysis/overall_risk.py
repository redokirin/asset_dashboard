# -*- coding: utf-8 -*-
"""整體風險係數計算模組。"""
from __future__ import annotations

import pandas as pd

_CASH_MARKETS = {"bank", "cash", "現金"}
_HIGH_PAIN_THRESHOLD = 0.70


def _is_stress_insufficient(tags) -> bool:
    if not isinstance(tags, list):
        return False
    return any("壓力測試不足" in str(t) for t in tags)


def _asset_risk_score(
    ann_vol: float | None,
    curr_dd_pct: float | None,
    pain_ratio: float | None,
    hold_ability: float | None,
    stress_insufficient: bool = False,
) -> float:
    """
    計算單一標的風險分數（0~1）。
    ann_vol: 年化波動率（decimal，e.g. 0.25）
    curr_dd_pct: 目前回撤（百分比單位，e.g. -5.2）
    pain_ratio: 0~1 decimal
    hold_ability: 持有力分數 0~1 decimal
    """
    vol_norm = min(1.0, (ann_vol or 0.0) / 0.60)
    drawdown_norm = min(1.0, abs(curr_dd_pct or 0.0) / 30.0)
    pain_norm = min(1.0, pain_ratio or 0.0)
    hold_penalty = 1.0 - min(1.0, hold_ability or 0.0)

    score = (
        0.40 * vol_norm
        + 0.25 * drawdown_norm
        + 0.25 * pain_norm
        + 0.10 * hold_penalty
    )

    if stress_insufficient:
        score = min(1.0, score * 1.2)

    return round(score, 4)


def calculate_overall_risk_score(
    adv_res: pd.DataFrame,
    df_res: pd.DataFrame,
) -> dict:
    """
    計算整體風險係數（0~100）與各項分解數據。

    Returns:
        {
            risk_score: float,          # 0~100
            portfolio_risk: float,      # 持倉加權風險（0~1）
            invested_ratio: float,      # 投資資產 / 總資產
            cash_buffer_ratio: float,   # 可投入現金 / 總資產
            high_risk_weight: float,    # Pain Ratio > 70% 標的佔比
            asset_breakdown: list[dict],
        }
    """
    if adv_res is None or adv_res.empty or df_res is None or df_res.empty:
        return {}

    cash_mask = (
        df_res["市場"].fillna("").astype(str).str.strip().str.lower().isin(_CASH_MARKETS)
    )
    inv_df = df_res[~cash_mask].copy()
    bank_df = df_res[cash_mask].copy()

    adv_cols = [c for c in [
        "代碼", "annualizedVol", "currentDrawdownPct", "painRatio",
        "hold_abilityScore", "tags",
    ] if c in adv_res.columns]
    work = inv_df.merge(adv_res[adv_cols], on="代碼", how="left")

    invested_value = float(work["市值"].sum())
    total_cash = float(bank_df["市值"].sum())
    total_assets = invested_value + total_cash

    investable_cash = sum(
        float(row.get("市值", 0) or 0) - float(row.get("keepTwd", 0) or 0)
        for _, row in bank_df.iterrows()
    )

    if invested_value == 0 or total_assets == 0:
        return {}

    asset_breakdown = []
    portfolio_risk = 0.0

    for _, row in work.iterrows():
        mv = float(row.get("市值", 0) or 0)
        if mv <= 0:
            continue
        weight = mv / invested_value
        score = _asset_risk_score(
            ann_vol=row.get("annualizedVol"),
            curr_dd_pct=row.get("currentDrawdownPct"),
            pain_ratio=row.get("painRatio"),
            hold_ability=row.get("hold_abilityScore"),
            stress_insufficient=_is_stress_insufficient(row.get("tags")),
        )
        contribution = weight * score
        portfolio_risk += contribution
        asset_breakdown.append({
            "ticker": str(row.get("代碼", "")),
            "name": str(row.get("名稱", "")),
            "weight": round(weight, 4),
            "risk_score": score,
            "weighted_contribution": round(contribution, 4),
            "pain_ratio": row.get("painRatio"),
        })

    invested_ratio = invested_value / total_assets
    cash_buffer_ratio = max(0.0, investable_cash / total_assets)
    overall_risk = portfolio_risk * invested_ratio
    risk_score = round(overall_risk * 100, 1)

    high_risk_weight = sum(
        a["weight"]
        for a in asset_breakdown
        if a.get("pain_ratio") is not None
        and float(a["pain_ratio"] or 0) > _HIGH_PAIN_THRESHOLD
    ) * invested_ratio

    return {
        "risk_score": risk_score,
        "portfolio_risk": round(portfolio_risk, 4),
        "invested_ratio": round(invested_ratio, 4),
        "cash_buffer_ratio": round(cash_buffer_ratio, 4),
        "high_risk_weight": round(high_risk_weight, 4),
        "asset_breakdown": sorted(
            asset_breakdown, key=lambda x: x["weighted_contribution"], reverse=True
        ),
    }


def get_risk_level(score: float) -> tuple[str, str]:
    """回傳 (等級標籤, 建議文字)。"""
    if score < 20:
        return "🟢 保守", "現金充裕，可積極在回測區加碼"
    elif score < 35:
        return "🟡 中低", "正常水位，依掛單系統執行"
    elif score < 50:
        return "🟠 中等", "持倉適中，放慢加碼速度"
    elif score < 65:
        return "🔴 中高", "持倉偏重，優先補強弱勢標的"
    else:
        return "⛔ 高風險", "暫停加碼，考慮部分獲利了結"


def build_risk_report_section(risk_data: dict) -> str:
    """回傳診斷報告的整體風險係數 Markdown 區塊。"""
    if not risk_data:
        return ""

    score = risk_data["risk_score"]
    level_label, level_advice = get_risk_level(score)
    port_pct = risk_data["portfolio_risk"] * 100
    cash_pct = risk_data["cash_buffer_ratio"] * 100
    inv_pct = risk_data["invested_ratio"] * 100
    high_pct = risk_data["high_risk_weight"] * 100

    lines = [
        "## 整體風險係數\n",
        f"**風險分數：{score} / 100　{level_label}**\n",
        "| 維度 | 數值 | 說明 |",
        "|------|------|------|",
        f"| 投資部位風險 | {port_pct:.1f}% | 持倉標的加權風險 |",
        f"| 現金緩衝比例 | {cash_pct:.1f}% | 可投入現金 / 總資產 |",
        f"| 實際投資比例 | {inv_pct:.1f}% | 投資資產 / 總資產 |",
        f"| 高風險標的佔比 | {high_pct:.1f}% | Pain Ratio > 70% 的標的 |",
    ]

    breakdown = risk_data.get("asset_breakdown", [])
    if breakdown:
        lines += [
            "\n### 標的風險分解\n",
            "| 標的 | 市值佔比 | 風險分數 | 加權貢獻 |",
            "|------|---------|---------|---------|",
        ]
        for a in breakdown:
            lines.append(
                f"| {a['ticker']} | {a['weight']:.1%} | {a['risk_score']:.2f} | {a['weighted_contribution']:.3f} |"
            )

    lines += [
        "\n### 風險建議",
        level_advice,
    ]

    return "\n".join(lines)


def get_risk_alerts(
    risk_data: dict,
    prev_risk_score: float | None = None,
) -> list[str]:
    """回傳整合進行動摘要的風險警示列表。"""
    if not risk_data:
        return []

    alerts = []
    score = risk_data["risk_score"]

    if score >= 65:
        alerts.append("⛔ 整體風險係數偏高，建議暫停加碼")

    if prev_risk_score is not None and (score - prev_risk_score) > 10:
        alerts.append(
            f"⚠️ 風險係數單日上升 {score - prev_risk_score:.1f}，市場壓力增加"
        )

    high_risk_weight = risk_data.get("high_risk_weight", 0)
    if high_risk_weight > 0.20:
        alerts.append(
            f"⚠️ 高風險標的佔投資資產 {high_risk_weight:.1%}，建議控制比例"
        )

    return alerts
