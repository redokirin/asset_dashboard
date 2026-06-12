# -*- coding: utf-8 -*-
import math

from core.tags import (
    TAG_ALLOC_OPPORTUNITY,
    TAG_BIAS_DEEP_DROP,
    TAG_BIAS_EXTREME_VALUE,
    TAG_BIAS_OVERHEATED,
    TAG_BIAS_TREND,
    TAG_BIAS_VALUE,
    TAG_DIVIDEND_MOAT,
    TAG_EXTREME_STRONG,
    TAG_HIGH_EFFICIENCY,
    TAG_LONG_BEAR,
    TAG_LONG_BULL,
    TAG_MA_BREAK_WEAK,
    TAG_MA_BULL_SUPPORT,
    TAG_NEUTRAL,
    TAG_PB_BELOW_NAV,
    TAG_PB_EXTREME,
    TAG_PB_FAIR,
    TAG_PB_PREMIUM,
    TAG_PEG_ATTRACTIVE,
    TAG_PEG_PREMIUM,
    TAG_PROFIT_STABLE,
    TAG_RS_DEEP_VALUE,
    TAG_RS_EXTREME,
    TAG_RS_MIDLINE,
    TAG_RS_STRONG,
    TAG_RS_VALUE_ZONE,
    TAG_RSI_OVERBOUGHT,
    TAG_RSI_OVERSOLD,
    TAG_STRONG_MGMT,
    TAG_VOL_CRASH,
    TAG_VOL_DRY_STOP,
    TAG_VOL_SPIKE,
    TAG_VOL_WEAK,
    TAG_VP_UP,
    TAG_WEAK_BOUNCE,
)


def generate_advanced_diagnosis(
    bias,
    sharpe,
    rs_percentile,
    ticker,
    price_change_pct=0,
    vol_ratio=1.0,
    rsi=0,
    price=None,
    ma5=None,
    ma20=None,
    ma250=None,
    eps=None,
    pe_ratio=None,
    dividend_yield=None,
    peg_ratio=None,
    pb_ratio=None,
    asset_type="個股",
    alpha_win_rate="0%",
    history_years=None,
    entry_zone_status=None,
):
    """綜合量化診斷邏輯 (整合基本面、技術位、RS、RSI 與量價關係)"""
    tags = []
    fund_advice = ""
    bias_advice = ""

    if ma250 is None or math.isnan(ma250):
        lt_context, lt_desc = "LONG_UNKNOWN", "長線趨勢數據不足"
    elif price is not None and price > ma250:
        lt_context, lt_desc = "BULLISH", "長線多頭格局"
    else:
        lt_context, lt_desc = "BEARISH", "長線空頭排列"

    st_momentum = "MOM_UNKNOWN"
    if price is not None and ma20 is not None and not math.isnan(ma20):
        st_momentum = "STRONG" if price > ma20 else "WEAK"

    if entry_zone_status and entry_zone_status != "-":
        tags.append(entry_zone_status)

    match (lt_context, st_momentum):
        case ("BULLISH", "STRONG"):
            tags.append(TAG_EXTREME_STRONG)
            advice_base = "標的處於長短線多頭共振，向上動能極強。"
        case ("BULLISH", "WEAK"):
            tags.append(TAG_LONG_BULL)
            advice_base = "標的維持長線多頭格局，但短線出現技術性背離（跌破月線），正進行結構性回測。"
        case ("BEARISH", "STRONG"):
            tags.append(TAG_WEAK_BOUNCE)
            advice_base = "長線空頭趨勢未變，當前僅屬超跌後的短線乖離修正。"
        case ("BEARISH", "WEAK"):
            tags.append(TAG_LONG_BEAR)
            advice_base = "長短線均受制於均線下行，技術面承壓，尚未見止跌訊號。"
        case _:
            tags.append(TAG_NEUTRAL)
            advice_base = "趨勢動能不明，建議於關鍵支撐位階觀察。"

    if rs_percentile >= 90:
        tags.append(TAG_RS_EXTREME)
    elif rs_percentile >= 75:
        tags.append(TAG_RS_STRONG)
    elif rs_percentile <= 10:
        tags.append(TAG_RS_DEEP_VALUE)
    elif rs_percentile <= 30:
        tags.append(TAG_RS_VALUE_ZONE)
    else:
        tags.append(TAG_RS_MIDLINE)

    if rsi > 80:
        tags.append(TAG_RSI_OVERBOUGHT)
    elif rsi < 20:
        tags.append(TAG_RSI_OVERSOLD)

    if price is not None and ma5 is not None and price < ma5:
        tags.append(TAG_MA_BREAK_WEAK)
        bias_advice += "跌破五日線，技術回測中。"
    else:
        tags.append(TAG_MA_BULL_SUPPORT)
        bias_advice += "站穩五日線，續強中。"

    if bias is not None and not math.isnan(bias):
        if bias <= -7:
            tags.append(TAG_BIAS_EXTREME_VALUE)
            bias_advice += f"標的位於月線下方 {bias:.1f}%，處於極度價值區。"
        elif -7 < bias <= -4:
            tags.append(TAG_BIAS_DEEP_DROP)
            bias_advice += f"標的位於月線下方 {bias:.1f}%，處於跌深反彈區。"
        elif bias >= 7:
            tags.append(TAG_BIAS_OVERHEATED)
            bias_advice += f"標的位於月線上方 {bias:.1f}%，處於過熱區。"
        else:
            tags.append(TAG_BIAS_TREND if bias >= 0 else TAG_BIAS_VALUE)

    is_fund_like = asset_type in ["ETF", "基金", "Fund", "個股 (ETF)"]

    if not is_fund_like:
        if eps is not None and not math.isnan(eps) and eps > 0:
            tags.append(TAG_PROFIT_STABLE)
            if pe_ratio is not None and not math.isnan(pe_ratio) and pe_ratio > 0:
                pe_desc = (
                    "低估值"
                    if pe_ratio < 15
                    else "合理估值"
                    if pe_ratio <= 30
                    else "高成長溢價"
                )
                fund_advice += f"基本面 EPS 正向，反映出{pe_desc}。"

        if peg_ratio is not None and not math.isnan(peg_ratio) and peg_ratio > 0:
            if peg_ratio < 1.0:
                tags.append(TAG_PEG_ATTRACTIVE)
                fund_advice += "成長估值具備極高吸引力 (PEG < 1)。"
            elif peg_ratio > 2.0:
                tags.append(TAG_PEG_PREMIUM)
                if lt_context == "BULLISH":
                    fund_advice += "需注意成長性已透支估值 (PEG > 2)。"

        if pb_ratio is not None and not math.isnan(pb_ratio) and pb_ratio > 0:
            if pb_ratio < 1.0:
                tags.append(TAG_PB_BELOW_NAV)
                fund_advice += (
                    f"股價淨值比 {pb_ratio:.2f}，低於帳面價值，具備安全邊際。"
                )
            elif pb_ratio <= 3.0:
                tags.append(TAG_PB_FAIR)
            elif pb_ratio <= 6.0:
                tags.append(TAG_PB_PREMIUM)
                fund_advice += (
                    f"股價淨值比 {pb_ratio:.2f}，估值溢價明顯，需關注成長性是否支撐。"
                )
            else:
                tags.append(TAG_PB_EXTREME)
                fund_advice += (
                    f"股價淨值比 {pb_ratio:.2f}，淨值溢價極高，估值泡沫風險上升。"
                )
    else:
        if sharpe > 1.2:
            tags.append(TAG_HIGH_EFFICIENCY)
            fund_advice += f"具備高夏普值 ({sharpe:.1f})，資產配置效率極佳。"

        try:
            alpha_num = float(str(alpha_win_rate).replace("%", ""))
            if alpha_num > 60:
                tags.append(TAG_STRONG_MGMT)
                fund_advice += (
                    f"Alpha 勝率 ({alpha_num:.1f}%) 表現強勁，具備超額報酬能力。"
                )
        except Exception:
            pass

        if rs_percentile <= 20:
            tags.append(TAG_ALLOC_OPPORTUNITY)
            fund_advice += "標的相對於基準處於深水區，為跨市場再平衡的潛在買點。"

    if (
        dividend_yield is not None
        and not math.isnan(dividend_yield)
        and dividend_yield > 0.035
    ):
        if rs_percentile < 20 or lt_context == "BEARISH":
            tags.append(TAG_DIVIDEND_MOAT)
            fund_advice += (
                f"具備高股息殖利率 ({dividend_yield:.1%})，為下行提供防禦支撐。"
            )

    vp_advice = ""
    if price_change_pct > 1.5:
        if vol_ratio > 1.5:
            tags.append(TAG_VP_UP)
            vp_advice = "今日價量齊揚，主動性買盤積極介入。"
        elif vol_ratio < 0.75:
            tags.append(TAG_VOL_WEAK)
            vp_advice = "⚠️偵測到價漲量縮現象（量價背離），目前反彈動能缺乏成交量支撐，反彈動能可能衰竭，請謹慎追高。"
    elif price_change_pct < -1.5:
        if vol_ratio > 2.0:
            tags.append(TAG_VOL_SPIKE)
            vp_advice = (
                "😱偵測到異常爆量 (2.0x+)，技術支撐可能失效，建議暫緩接單並觀察防守位。"
            )
        elif vol_ratio > 1.5:
            tags.append(TAG_VOL_CRASH)
            vp_advice = "😱 帶量下殺，反映恐慌性賣壓持續湧現。"
        elif vol_ratio < 0.8:
            tags.append(TAG_VOL_DRY_STOP)
            vp_advice = "量縮下跌，賣壓出現竭盡跡象，有利於短線止跌整理。"

    # 先不加入持有力的壓力測試
    # stress_advice = ""
    # if history_years is not None and history_years < 2:
    #     history_months = max(1, round(history_years * 12))
    #     tags.append("⚠️壓力測試不足")
    #     if history_years < 1:
    #         stress_advice = f"⚠️ 本標的歷史僅 {history_months} 個月，從未經歷完整市場壓力測試，MDD 不具參考性，持有力評分偏高存在高估風險。"
    #     else:
    #         stress_advice = f"⚠️ 本標的歷史不足 2 年（{history_months} 個月），壓力測試樣本有限，MDD 與舒適度參考性有限。"

    advice_base_display = f"\n{advice_base}" if advice_base else ""
    fund_display = f"\n{fund_advice}" if fund_advice else ""
    bias_advice_display = f"\n{bias_advice}" if bias_advice else ""
    vp_advice_display = f"\n{vp_advice}" if vp_advice else ""

    full_advice = (
        f"{advice_base_display}{fund_display}{bias_advice_display}{vp_advice_display}"
    )
    return full_advice, tags
