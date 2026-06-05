# -*- coding: utf-8 -*-
from datetime import datetime

import pandas as pd

_CASH_MARKETS = {"bank", "cash", "現金"}

_SIGNAL_EMOJI = {
    "日常加碼": "🟡",
    "回測加碼": "🟢",
    "狙擊加碼": "⭐",
}

ACTIONABLE_SIGNALS = {"日常加碼", "回測加碼", "狙擊加碼"}


def _extract_signal(entry_zone_status):
    if not isinstance(entry_zone_status, str):
        return None
    for sig in ACTIONABLE_SIGNALS:
        if sig in entry_zone_status:
            return sig
    return None


def _contains_tag(tags, keyword):
    if not isinstance(tags, list):
        return False
    return any(keyword in str(t) for t in tags)


def _account_label(row):
    settlement = str(row.get("Settlement", "")).strip()
    if settlement:
        return f"{settlement} 帳戶"
    ccy = str(row.get("幣別", "")).strip().upper()
    if ccy == "JPY":
        return "JPY 帳戶"
    if ccy == "USD":
        return "USD 帳戶"
    return "TWD 帳戶"


def _calc_region_gaps(df_res, region_targets):
    if not region_targets:
        return []
    inv_mask = (
        ~df_res["市場"].fillna("").astype(str).str.strip().str.lower().isin(_CASH_MARKETS)
    )
    inv_df = df_res[inv_mask]
    total_val = float(inv_df["市值"].sum())
    if total_val == 0:
        return []

    actual = inv_df.groupby("市場")["市值"].sum() / total_val
    gaps = []
    for region, target in region_targets.items():
        current = float(actual.get(region, 0.0))
        gap = current - target
        if abs(gap) > 0.05:
            gaps.append(
                {
                    "region": region,
                    "current_pct": current,
                    "target_pct": target,
                    "gap_pct": gap,
                }
            )
    return sorted(gaps, key=lambda x: x["gap_pct"])


def generate_daily_summary(
    df_res,
    adv_res=None,
    region_targets=None,
    pain_threshold=0.30,
    drawdown_threshold=-3.0,
):
    """
    從投資組合數據萃取每日行動摘要。

    Args:
        df_res: 投資組合 DataFrame
        adv_res: 進階分析 DataFrame（含 entryZoneStatus、painRatio、tags 等）
        region_targets: 各市場目標配置比例，如 {"日股": 0.30, "台股": 0.40}
        pain_threshold: Pain Ratio 警示門檻（預設 0.30）
        drawdown_threshold: 回撤門檻（百分比單位，預設 -3.0 即 -3%）

    Returns:
        dict: text, actionable, warnings, region_gaps, scheduled, timestamp
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    inv_mask = (
        ~df_res["市場"].fillna("").astype(str).str.strip().str.lower().isin(_CASH_MARKETS)
    )
    work_df = df_res[inv_mask].copy()

    if adv_res is not None and not adv_res.empty and "代碼" in adv_res.columns:
        adv_cols = [c for c in ["代碼", "entryZoneStatus", "painRatio", "currentDrawdownPct", "tags"] if c in adv_res.columns]
        work_df = work_df.merge(adv_res[adv_cols], on="代碼", how="left")

    region_gaps = _calc_region_gaps(df_res, region_targets)
    region_gap_map = {g["region"]: g for g in region_gaps}

    actionable = []
    warnings = []

    for _, row in work_df.iterrows():
        ticker = str(row.get("代碼", ""))
        name = str(row.get("名稱", ticker))
        market = str(row.get("市場", ""))
        asset_type = str(row.get("類型", ""))

        if asset_type == "基金":
            continue

        account = _account_label(row)

        entry_zone = row.get("entryZoneStatus", "")
        pain_ratio_val = row.get("painRatio", None)
        curr_dd = row.get("currentDrawdownPct", None)
        tags = row.get("tags", [])

        signal = _extract_signal(entry_zone)

        is_high_pain = (
            pain_ratio_val is not None
            and pd.notnull(pain_ratio_val)
            and float(pain_ratio_val) > pain_threshold
        )
        is_volume_crash = _contains_tag(tags, "帶量下殺")
        is_stress_fail = (
            _contains_tag(tags, "壓力測試不足")
            and curr_dd is not None
            and pd.notnull(curr_dd)
            and float(curr_dd) < drawdown_threshold
        )
        has_warning = is_high_pain or is_volume_crash or is_stress_fail

        if signal:
            gap_note = ""
            if market in region_gap_map:
                g = region_gap_map[market]
                gap_note = f"{market}缺口 {g['gap_pct'] * 100:+.1f}%"
            note_parts = [account]
            if gap_note:
                note_parts.append(gap_note)
            actionable.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "signal": signal,
                    "emoji": _SIGNAL_EMOJI.get(signal, "🟡"),
                    "note": "｜".join(note_parts),
                    "asset_type": asset_type,
                }
            )

        if has_warning:
            reasons = []
            if is_high_pain:
                reasons.append(f"Pain Ratio {int(float(pain_ratio_val) * 100)}%")
            if is_volume_crash:
                reasons.append("帶量下殺")
            if is_stress_fail:
                reasons.append(f"壓力測試不足（回撤 {float(curr_dd):.1f}%）")
            advice = "暫緩加碼" if is_high_pain else "注意風險"
            warnings.append(
                {
                    "ticker": ticker,
                    "name": name,
                    "reasons": reasons,
                    "advice": advice,
                }
            )

    lines = [f"📋 今日行動摘要｜{now_str}", ""]

    if actionable:
        lines.append("【可執行】")
        for item in actionable:
            lines.append(
                f"{item['emoji']} {item['ticker']}｜{item['signal']}｜{item['note']}"
            )
        lines.append("")

    if warnings:
        lines.append("【須注意】")
        for item in warnings:
            reason_str = "、".join(item["reasons"])
            lines.append(f"⚠️ {item['ticker']}｜{reason_str}｜{item['advice']}")
        lines.append("")

    if region_gaps:
        lines.append("【配置缺口】")
        for g in region_gaps:
            emoji = "🔴" if g["gap_pct"] < 0 else "🟠"
            lines.append(
                f"{emoji} {g['region']} {g['current_pct'] * 100:.1f}%"
                f"｜目標 {g['target_pct'] * 100:.0f}%"
                f"｜缺口 {g['gap_pct'] * 100:+.1f}%"
            )
        lines.append("")

    if not actionable and not warnings and not region_gaps:
        lines.append("✅ 今日無須特別行動，所有標的均正常")

    return {
        "text": "\n".join(lines),
        "actionable": actionable,
        "warnings": warnings,
        "region_gaps": region_gaps,
        "timestamp": now_str,
    }
