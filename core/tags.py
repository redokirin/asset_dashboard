# -*- coding: utf-8 -*-
"""Semantic tag constants and display map for diagnostic tags.

Tags are stored and compared as short ASCII keys (e.g. TAG_VP_UP = "vp_up").
Display strings (with emojis) live only in TAG_DISPLAY and are applied at
render time via TAG_DISPLAY.get(tag, tag).
"""

# Volume / price quality
TAG_VP_UP        = "vp_up"        # 🚀 價量齊揚
TAG_VOL_WEAK     = "vol_weak"     # 🔴 量能不足
TAG_VOL_SPIKE    = "vol_spike"    # 😱 異常爆量
TAG_VOL_CRASH    = "vol_crash"    # 🔻 帶量下殺
TAG_VOL_DRY_STOP = "vol_dry_stop" # ⚪ 量縮止跌

# Risk
TAG_STRESS_FAIL = "stress_fail"   # ⚠️ 壓力測試不足

# Trend (long × short)
TAG_EXTREME_STRONG = "extreme_strong" # 🔥 極致強勢
TAG_LONG_BULL      = "long_bull"      # 🟢 長線多頭
TAG_WEAK_BOUNCE    = "weak_bounce"    # 💧 弱勢反彈
TAG_LONG_BEAR      = "long_bear"      # 🔵 長線偏弱
TAG_NEUTRAL        = "neutral"        # ⚪ 中性整理

# RS percentile
TAG_RS_EXTREME    = "rs_extreme"    # 🔥 極致過熱
TAG_RS_STRONG     = "rs_strong"     # 🚀 動能強勢
TAG_RS_DEEP_VALUE = "rs_deep_value" # 💎 黃金深水區
TAG_RS_VALUE_ZONE = "rs_value_zone" # 🔵 價值佈局區
TAG_RS_MIDLINE    = "rs_midline"    # ⚪ 趨勢中軸

# RSI
TAG_RSI_OVERBOUGHT = "rsi_overbought" # 🟢 買超
TAG_RSI_OVERSOLD   = "rsi_oversold"   # 🔴 賣超

# MA / 5-day line
TAG_MA_BREAK_WEAK    = "ma_break_weak"    # 🔴 破線轉弱
TAG_MA_BULL_SUPPORT  = "ma_bull_support"  # 🟢 多頭支撐

# Bias (deviation from MA20)
TAG_BIAS_EXTREME_VALUE = "bias_extreme_value" # 🟠 極度價值區
TAG_BIAS_DEEP_DROP     = "bias_deep_drop"     # 💧 跌深反彈區
TAG_BIAS_OVERHEATED    = "bias_overheated"    # 🔴 過熱區
TAG_BIAS_TREND         = "bias_trend"         # 🟢 趨勢區
TAG_BIAS_VALUE         = "bias_value"         # 🟡 價值區

# Fundamental — individual stocks only
TAG_PROFIT_STABLE   = "profit_stable"    # 📊 盈利穩健
TAG_PEG_ATTRACTIVE  = "peg_attractive"   # 💎 估值極具吸引力 (PEG < 1)
TAG_PEG_PREMIUM     = "peg_premium"      # ⚠️ 成長溢價過高 (PEG > 2)
TAG_PB_BELOW_NAV    = "pb_below_nav"     # 💎 股價低於淨值 (PB < 1)
TAG_PB_FAIR         = "pb_fair"          # 📘 合理淨值區間 (PB 1-3)
TAG_PB_PREMIUM      = "pb_premium"       # ⚠️ 淨值溢價偏高 (PB > 3)
TAG_PB_EXTREME      = "pb_extreme"       # 🔴 淨值嚴重溢價 (PB > 6)

# Fundamental — ETF / fund only
TAG_HIGH_EFFICIENCY    = "high_efficiency"    # 💎 高效率資產
TAG_STRONG_MGMT        = "strong_mgmt"        # 🛡️ 強勢管理
TAG_ALLOC_OPPORTUNITY  = "alloc_opportunity"  # ⚖️ 配置機會
TAG_DIVIDEND_MOAT      = "dividend_moat"      # 🛡️ 息收護城河

TAG_DISPLAY: dict[str, str] = {
    TAG_VP_UP:             "🚀 價量齊揚",
    TAG_VOL_WEAK:          "🔴 量能不足",
    TAG_VOL_SPIKE:         "😱 異常爆量",
    TAG_VOL_CRASH:         "🔻 帶量下殺",
    TAG_VOL_DRY_STOP:      "⚪ 量縮止跌",
    TAG_STRESS_FAIL:       "⚠️ 壓力測試不足",
    TAG_EXTREME_STRONG:    "🔥 極致強勢",
    TAG_LONG_BULL:         "🟢 長線多頭",
    TAG_WEAK_BOUNCE:       "💧 弱勢反彈",
    TAG_LONG_BEAR:         "🔵 長線偏弱",
    TAG_NEUTRAL:           "⚪ 中性整理",
    TAG_RS_EXTREME:        "🔥 極致過熱",
    TAG_RS_STRONG:         "🚀 動能強勢",
    TAG_RS_DEEP_VALUE:     "💎 黃金深水區",
    TAG_RS_VALUE_ZONE:     "🔵 價值佈局區",
    TAG_RS_MIDLINE:        "⚪ 趨勢中軸",
    TAG_RSI_OVERBOUGHT:    "🟢 買超",
    TAG_RSI_OVERSOLD:      "🔴 賣超",
    TAG_MA_BREAK_WEAK:     "🔴 破線轉弱",
    TAG_MA_BULL_SUPPORT:   "🟢 多頭支撐",
    TAG_BIAS_EXTREME_VALUE:"🟠 極度價值區",
    TAG_BIAS_DEEP_DROP:    "💧 跌深反彈區",
    TAG_BIAS_OVERHEATED:   "🔴 過熱區",
    TAG_BIAS_TREND:        "🟢 趨勢區",
    TAG_BIAS_VALUE:        "🟡 價值區",
    TAG_PROFIT_STABLE:     "📊 盈利穩健",
    TAG_PEG_ATTRACTIVE:    "💎 估值極具吸引力 (PEG < 1)",
    TAG_PEG_PREMIUM:       "⚠️ 成長溢價過高 (PEG > 2)",
    TAG_PB_BELOW_NAV:      "💎 股價低於淨值 (PB < 1)",
    TAG_PB_FAIR:           "📘 合理淨值區間 (PB 1-3)",
    TAG_PB_PREMIUM:        "⚠️ 淨值溢價偏高 (PB > 3)",
    TAG_PB_EXTREME:        "🔴 淨值嚴重溢價 (PB > 6)",
    TAG_HIGH_EFFICIENCY:   "💎 高效率資產",
    TAG_STRONG_MGMT:       "🛡️ 強勢管理",
    TAG_ALLOC_OPPORTUNITY: "⚖️ 配置機會",
    TAG_DIVIDEND_MOAT:     "🛡️ 息收護城河",
}
