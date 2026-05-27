# -*- coding: utf-8 -*-
import math


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
    asset_type="個股",
    alpha_win_rate="0%",
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

    match (lt_context, st_momentum):
        case ("BULLISH", "STRONG"):
            tags.append("🔥極致強勢")
            advice_base = "標的處於長短線多頭共振，向上動能極強。"
        case ("BULLISH", "WEAK"):
            tags.append("🟢長線多頭")
            advice_base = "標的維持長線多頭格局，但短線出現技術性背離（跌破月線），正進行結構性回測。"
        case ("BEARISH", "STRONG"):
            tags.append("💧弱勢反彈")
            advice_base = "長線空頭趨勢未變，當前僅屬超跌後的短線乖離修正。"
        case ("BEARISH", "WEAK"):
            tags.append("🔵長線偏弱")
            advice_base = "長短線均受制於均線下行，技術面承壓，尚未見止跌訊號。"
        case _:
            tags.append("⚪中性整理")
            advice_base = "趨勢動能不明，建議於關鍵支撐位階觀察。"

    if rs_percentile >= 90:
        tags.append("🔥極致過熱")
    elif rs_percentile >= 75:
        tags.append("🚀動能強勢")
    elif rs_percentile <= 10:
        tags.append("💎黃金深水區")
    elif rs_percentile <= 30:
        tags.append("🔵價值佈局區")
    else:
        tags.append("⚪趨勢中軸")

    if rsi > 80:
        tags.append("🟢買超")
    elif rsi < 20:
        tags.append("🔴賣超")

    if price is not None and ma5 is not None and price < ma5:
        tags.append("🔴破線轉弱")
        bias_advice += "跌破五日線，技術回測中。"
    else:
        tags.append("🟢多頭支撐")
        bias_advice += "站穩五日線，續強中。"

    if bias is not None and not math.isnan(bias):
        if bias <= -7:
            tags.append("🟠極度價值區")
            bias_advice += f"標的位於月線下方 {bias:.1f}%，處於極度價值區。"
        elif -7 < bias <= -4:
            tags.append("💧跌深反彈區")
            bias_advice += f"標的位於月線下方 {bias:.1f}%，處於跌深反彈區。"
        elif bias >= 7:
            tags.append("🔴過熱區")
            bias_advice += f"標的位於月線上方 {bias:.1f}%，處於過熱區。"
        else:
            tags.append("🟢趨勢區" if bias >= 0 else "🟡價值區")

    is_fund_like = asset_type in ["ETF", "基金", "Fund", "個股 (ETF)"]

    if not is_fund_like:
        if eps is not None and not math.isnan(eps) and eps > 0:
            tags.append("📊盈利穩健")
            if pe_ratio is not None and not math.isnan(pe_ratio) and pe_ratio > 0:
                pe_desc = (
                    "低估值"
                    if pe_ratio < 15
                    else "合理估值"
                    if pe_ratio <= 30
                    else "高成長溢價"
                )
                fund_advice += f" 基本面 EPS 正向，反映出{pe_desc}。"

        if peg_ratio is not None and not math.isnan(peg_ratio) and peg_ratio > 0:
            if peg_ratio < 1.0:
                tags.append("💎估值極具吸引力 (PEG < 1)")
                fund_advice += " 成長估值具備極高吸引力 (PEG < 1)。"
            elif peg_ratio > 2.0:
                tags.append("⚠️成長溢價過高 (PEG > 2)")
                if lt_context == "BULLISH":
                    fund_advice += " 需注意成長性已透支估值 (PEG > 2)。"
    else:
        if sharpe > 1.2:
            tags.append("💎高效率資產")
            fund_advice += f" 具備高夏普值 ({sharpe:.1f})，資產配置效率極佳。"

        try:
            alpha_num = float(str(alpha_win_rate).replace("%", ""))
            if alpha_num > 60:
                tags.append("🛡️強勢管理")
                fund_advice += (
                    f" Alpha 勝率 ({alpha_num:.1f}%) 表現強勁，具備超額報酬能力。"
                )
        except Exception:
            pass

        if rs_percentile <= 20:
            tags.append("⚖️配置機會")
            fund_advice += "標的相對於基準處於深水區，為跨市場再平衡的潛在買點。"

    if (
        dividend_yield is not None
        and not math.isnan(dividend_yield)
        and dividend_yield > 0.035
    ):
        if rs_percentile < 20 or lt_context == "BEARISH":
            tags.append("🛡️息收護城河")
            fund_advice += (
                f"具備高股息殖利率 ({dividend_yield:.1%})，為下行提供防禦支撐。"
            )

    vp_advice = ""
    if price_change_pct > 1.5:
        if vol_ratio > 1.5:
            tags.append("🚀價量齊揚")
            vp_advice = "今日價量齊揚，主動性買盤積極介入。"
        elif vol_ratio < 0.75:
            tags.append("🔴量能不足")
            vp_advice = "⚠️偵測到價漲量縮現象（量價背離），目前反彈動能缺乏成交量支撐，反彈動能可能衰竭，請謹慎追高。"
    elif price_change_pct < -1.5:
        if vol_ratio > 2.0:
            tags.append("😱異常爆量")
            vp_advice = (
                "😱偵測到異常爆量 (2.0x+)，技術支撐可能失效，建議暫緩接單並觀察防守位。"
            )
        elif vol_ratio > 1.5:
            tags.append("🔻帶量下殺")
            vp_advice = "😱 帶量下殺，反映恐慌性賣壓持續湧現，建議優先觀察狙擊位。"
        elif vol_ratio < 0.8:
            tags.append("⚪量縮止跌")
            vp_advice = "量縮下跌，賣壓出現竭盡跡象，有利於短線止跌整理。"

    advice_base_display = f"\n{advice_base}" if advice_base else ""
    fund_display = f"\n{fund_advice}" if fund_advice else ""
    bias_advice_display = f"\n{bias_advice}" if bias_advice else ""
    vp_advice_display = f"\n{vp_advice}" if vp_advice else ""

    full_advice = (
        f"{advice_base_display}{fund_display}{bias_advice_display}{vp_advice_display}"
    )
    return full_advice, tags
