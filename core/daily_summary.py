# -*- coding: utf-8 -*-
from datetime import date, datetime

import pandas as pd

_CASH_MARKETS = {"bank", "cash", "現金"}

_SIGNAL_EMOJI = {
    "日常加碼": "🟡",
    "回測加碼": "🟢",
    "狙擊加碼": "⭐",
}

ACTIONABLE_SIGNALS = {"日常加碼", "回測加碼", "狙擊加碼"}


def _get_nearest_fib_support(zone_upper, zone_lower, current_price):
    if zone_upper is None or zone_lower is None or current_price is None:
        return None, None
    dist = zone_upper - zone_lower
    fib_levels = {
        "23.6%": zone_upper - dist * 0.236,
        "38.2%": zone_upper - dist * 0.382,
        "50.0%": zone_upper - dist * 0.500,
        "61.8%": zone_upper - dist * 0.618,
        "78.6%": zone_upper - dist * 0.786,
    }
    supports_below = {k: v for k, v in fib_levels.items() if v < current_price}
    if not supports_below:
        return None, None
    nearest_label = max(supports_below, key=lambda k: supports_below[k])
    return nearest_label, round(supports_below[nearest_label], 2)


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


def _classify_volume_quality(volume_ratio, tags):
    """
    Returns (quality_level, quality_note).
    Levels: caution / strong / weak / warning / normal
    """
    if volume_ratio is None or not isinstance(volume_ratio, (int, float)):
        return "normal", None
    if _contains_tag(tags, "帶量下殺") or _contains_tag(tags, "異常爆量"):
        return "caution", "⚠️ 異常量能，謹慎執行"
    if _contains_tag(tags, "價量齊揚") or volume_ratio >= 1.5:
        return "strong", "✅ 價量齊揚，動能確認"
    if _contains_tag(tags, "量能不足"):
        return "weak", "⚠️ 量偏低，建議小量"
    if volume_ratio >= 0.5:
        return "normal", None
    if volume_ratio >= 0.3:
        return "weak", "⚠️ 量偏低，建議小量"
    return "warning", "⚠️ 量縮，反彈動能待確認"


def _zone_close_position(current_price, zone_lower, zone_upper):
    """Returns 0.0–1.0 relative position within zone, or None if indeterminate."""
    if current_price is None or zone_lower is None or zone_upper is None:
        return None
    span = zone_upper - zone_lower
    if span <= 0:
        return None
    return min(1.0, max(0.0, (current_price - zone_lower) / span))


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
    inv_mask = ~df_res["市場"].fillna("").astype(str).str.strip().str.lower().isin(
        _CASH_MARKETS
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


def _build_prev_pain_map() -> dict[str, float]:
    """從 SQLite 快照取得「非今日最新一筆」的 pain_ratio，回傳 {ticker: value}。"""
    try:
        from db.database import get_latest_two_snapshots

        latest, previous = get_latest_two_snapshots()
        today_str = str(date.today())
        # 若最新快照就是今日，用 previous；否則最新快照即為昨日
        ref = previous if latest.get("date") == today_str else latest
        return {
            row["ticker"]: row["pain_ratio"]
            for row in ref.get("assets", [])
            if row.get("pain_ratio") is not None
        }
    except Exception:
        return {}


def generate_daily_summary(
    df_res,
    adv_res=None,
    region_targets=None,
    pain_threshold=0.30,
    drawdown_threshold=-3.0,
    risk_data=None,
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
        dict: text, actionable, warnings, region_gaps, timestamp
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    prev_pain_map = _build_prev_pain_map()

    inv_mask = ~df_res["市場"].fillna("").astype(str).str.strip().str.lower().isin(
        _CASH_MARKETS
    )
    work_df = df_res[inv_mask].copy()

    if adv_res is not None and not adv_res.empty and "代碼" in adv_res.columns:
        adv_cols = [
            c
            for c in [
                "代碼",
                "entryZoneStatus",
                "painRatio",
                "currentDrawdownPct",
                "tags",
                "dailyUpper",
                "boundaryDailyRetest",
                "boundaryRetestSniper",
                "_vol_ratio_raw",
            ]
            if c in adv_res.columns
        ]
        work_df = work_df.merge(adv_res[adv_cols], on="代碼", how="left")

    region_gaps = _calc_region_gaps(df_res, region_targets)
    actionable = []
    hold_off = []
    warnings = []

    for _, row in work_df.iterrows():
        ticker = str(row.get("代碼", ""))
        name = str(row.get("名稱", ticker))
        asset_type = str(row.get("類型", ""))

        if asset_type == "基金":
            continue

        entry_zone = row.get("entryZoneStatus", "")
        pain_ratio_val = row.get("painRatio", None)
        curr_dd = row.get("currentDrawdownPct", None)
        tags = row.get("tags", [])
        vol_ratio_raw = row.get("_vol_ratio_raw", None)
        try:
            vol_ratio_raw = float(vol_ratio_raw) if vol_ratio_raw is not None else None
        except (ValueError, TypeError):
            vol_ratio_raw = None

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
            du = row.get("dailyUpper")
            bdr = row.get("boundaryDailyRetest")
            brs = row.get("boundaryRetestSniper")
            raw_price = row.get("股價")
            current_price = None
            try:
                current_price = float(raw_price) if raw_price is not None else None
            except (ValueError, TypeError):
                pass

            if signal == "日常加碼" and du is not None and bdr is not None:
                zone_range = f"{bdr:.2f}~{du:.2f}"
                zone_lower, zone_upper = float(bdr), float(du)
            elif signal == "回測加碼" and bdr is not None and brs is not None:
                zone_range = f"{brs:.2f}~{bdr:.2f}"
                zone_lower, zone_upper = float(brs), float(bdr)
            elif signal == "狙擊加碼" and brs is not None:
                zone_range = f"< {brs:.2f}"
                zone_lower, zone_upper = None, None
            else:
                zone_range = None
                zone_lower, zone_upper = None, None

            fib_label, fib_price = _get_nearest_fib_support(
                zone_upper, zone_lower, current_price
            )

            quality_level, quality_note = _classify_volume_quality(vol_ratio_raw, tags)
            close_pos = _zone_close_position(current_price, zone_lower, zone_upper)

            # 日常區上半 + 量縮 → 降為觀望
            if (
                signal == "日常加碼"
                and quality_level == "warning"
                and close_pos is not None
                and close_pos > 0.5
            ):
                hold_off.append(
                    {
                        "ticker": ticker,
                        "name": name,
                        "signal": signal,
                        "zone_range": zone_range,
                        "quality_note": quality_note,
                        "close_pos": close_pos,
                    }
                )
            else:
                # 回測/狙擊 + 量縮 → 可執行但升級提示為拆小量
                if quality_level == "warning" and signal in ("回測加碼", "狙擊加碼"):
                    quality_note = (quality_note or "") + "，建議拆小量執行"

                actionable.append(
                    {
                        "ticker": ticker,
                        "name": name,
                        "signal": signal,
                        "emoji": _SIGNAL_EMOJI.get(signal, "🟡"),
                        "zone_range": zone_range,
                        "zone_upper": zone_upper,
                        "zone_lower": zone_lower,
                        "fib_label": fib_label,
                        "fib_price": fib_price,
                        "adv_price": raw_price,
                        "current_price": current_price,
                        "asset_type": asset_type,
                        "quality_note": quality_note,
                        "quality_level": quality_level,
                    }
                )

        if has_warning:
            reasons = []
            if is_high_pain:
                today_pct = int(float(pain_ratio_val) * 100)
                prev_pain = prev_pain_map.get(ticker)
                if prev_pain is not None:
                    prev_pct = int(float(prev_pain) * 100)
                    reasons.append(f"Pain Ratio {today_pct}%（昨日 {prev_pct}%）")
                else:
                    reasons.append(f"Pain Ratio {today_pct}%")
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

    warn_map = {w["ticker"]: w for w in warnings}
    rendered: set[str] = {item["ticker"] for item in hold_off}

    lines = [f"📋 今日行動摘要｜{now_str}", ""]

    if actionable:
        lines.append("【可執行】")
        for item in actionable:
            ticker = item["ticker"]
            rendered.add(ticker)
            zone_str = f"區間 {item['zone_range']}" if item["zone_range"] else ""
            if item.get("fib_price") is not None:
                fib_str = f"最近支撐 {item['fib_price']:.2f}"
            elif zone_str:
                cp = item.get("current_price")
                cp_display = f"{cp:.2f}" if cp is not None else "—"
                fib_str = f"現價({cp_display})近下緣，位置偏佳"
            else:
                fib_str = ""
            parts = [p for p in [item["signal"], zone_str, fib_str] if p]
            lines.append(f"● {ticker}｜{'｜'.join(parts)}")
            if item.get("quality_note"):
                lines.append(f"  {item['quality_note']}")
            if ticker in warn_map:
                w = warn_map[ticker]
                lines.append(f"  {'、'.join(w['reasons'])} ｜ {w['advice']}")
        lines.append("")

    if hold_off:
        lines.append("【觀望（量價異常）】")
        for item in hold_off:
            zone_str = f"區間 {item['zone_range']}" if item["zone_range"] else item["signal"]
            reason = item.get("quality_note") or "量縮上漲，不追"
            lines.append(f"● {item['ticker']}｜{zone_str}｜{reason}")
        lines.append("")

    warn_only = [w for w in warnings if w["ticker"] not in rendered]
    if warn_only:
        lines.append("【須注意】")
        for item in warn_only:
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

    risk_alerts = []
    if risk_data:
        try:
            from core.analysis.overall_risk import get_risk_alerts, get_risk_level
            from db.database import get_prev_risk_score
            prev_score = get_prev_risk_score()
            risk_alerts = get_risk_alerts(risk_data, prev_score)
            if risk_alerts:
                risk_score = risk_data["risk_score"]
                level_label, _ = get_risk_level(risk_score)
                lines.append("【整體風險】")
                lines.append(f"風險係數 {risk_score} / 100　{level_label}")
                for alert in risk_alerts:
                    lines.append(alert)
                lines.append("")
        except Exception:
            pass

    if not actionable and not hold_off and not warnings and not region_gaps and not risk_alerts:
        lines.append("✅ 今日無須特別行動，所有標的均正常")

    return {
        "text": "\n".join(lines),
        "actionable": actionable,
        "hold_off": hold_off,
        "warnings": warnings,
        "region_gaps": region_gaps,
        "risk_data": risk_data,
        "risk_alerts": risk_alerts,
        "timestamp": now_str,
    }
