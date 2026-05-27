# -*- coding: utf-8 -*-
"""
risk.py - 風險指標計算模組

提供 MDD (最大回撤)、Current Drawdown、Pain Ratio 與 Comfort Score。
所有函式均以 O(n) 單次迴圈完成主要計算，支援 type hints。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# 資料結構
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class DrawdownResult:
    """回撤分析結果"""

    maxDrawdownPercent: float = 0.0  # 歷史最大回撤 (負值, e.g. -18.18)
    currentDrawdownPercent: float = 0.0  # 目前回撤，相對歷史高點 (負值)
    painRatio: float = 0.0  # 目前痛感 / 歷史最大痛感，0~1
    peakValue: float = 0.0  # MDD 期間的高點值
    troughValue: float = 0.0  # MDD 期間的低點值
    peakDate: str = ""  # MDD 高點日期
    troughDate: str = ""  # MDD 低點日期
    currentValue: float = 0.0  # 序列最新值
    comfortScore: str = "High"  # High / Medium / Low

    @property
    def max_drawdown_percent(self) -> float:
        return self.maxDrawdownPercent

    @property
    def current_drawdown_percent(self) -> float:
        return self.currentDrawdownPercent

    @property
    def pain_ratio(self) -> float:
        return self.painRatio

    @property
    def peak_value(self) -> float:
        return self.peakValue

    @property
    def trough_value(self) -> float:
        return self.troughValue

    @property
    def peak_date(self) -> str:
        return self.peakDate

    @property
    def trough_date(self) -> str:
        return self.troughDate

    @property
    def current_value(self) -> float:
        return self.currentValue

    @property
    def comfort_score(self) -> str:
        return self.comfortScore


# ──────────────────────────────────────────────────────────────────────────────
# 內部工具
# ──────────────────────────────────────────────────────────────────────────────


def _compute_comfort_score(max_drawdown_percent: float) -> str:
    """根據 maxDrawdownPercent 計算舒適度等級"""
    abs_mdd = abs(max_drawdown_percent)
    if abs_mdd < 10:
        return "High"
    elif abs_mdd < 20:
        return "Medium"
    else:
        return "Low"


# ──────────────────────────────────────────────────────────────────────────────
# 核心計算
# ──────────────────────────────────────────────────────────────────────────────


def calculate_drawdown(
    value_history: list[dict],
) -> Optional[DrawdownResult]:
    """
    核心回撤計算（O(n) 單次迴圈）。

    Args:
        value_history: 按時間升冪排列的歷史序列，格式如：
            [{"date": "2026-01-01", "value": 100.0}, ...]

    Returns:
        DrawdownResult，或在空資料 / 全部無效時回傳 None。
    """
    if not value_history:
        logger.debug("calculate_drawdown: 空資料，回傳 None")
        return None

    # 過濾 value <= 0 的異常資料
    valid_history = [
        item
        for item in value_history
        if isinstance(item.get("value"), (int, float)) and item["value"] > 0
    ]

    if not valid_history:
        logger.debug("calculate_drawdown: 無有效資料 (value <= 0)，回傳 None")
        return None

    # ── O(n) 單次迴圈計算 MDD ──────────────────────────────────────────────────
    first = valid_history[0]
    rolling_peak_value: float = first["value"]
    rolling_peak_date: str = first["date"]

    max_drawdown: float = 0.0  # 最大回撤 (負值)
    mdd_peak_value: float = first["value"]
    mdd_peak_date: str = first["date"]
    mdd_trough_value: float = first["value"]
    mdd_trough_date: str = first["date"]

    for item in valid_history:
        val: float = item["value"]
        date: str = item["date"]

        if val >= rolling_peak_value:
            # 創新高：更新 rolling peak
            rolling_peak_value = val
            rolling_peak_date = date
        else:
            # 回撤：檢查是否突破歷史最深回撤
            drawdown = (val - rolling_peak_value) / rolling_peak_value * 100
            if drawdown < max_drawdown:
                max_drawdown = drawdown
                mdd_peak_value = rolling_peak_value
                mdd_peak_date = rolling_peak_date
                mdd_trough_value = val
                mdd_trough_date = date

    # ── 目前值與 Current Drawdown ─────────────────────────────────────────────
    current_value: float = valid_history[-1]["value"]
    current_drawdown = (current_value - rolling_peak_value) / rolling_peak_value * 100

    # ── Pain Ratio：clamp 在 0~1 ──────────────────────────────────────────────
    if max_drawdown == 0.0:
        pain_ratio = 0.0
    else:
        pain_ratio = min(
            1.0, max(0.0, abs(current_drawdown) / abs(max_drawdown))
        )

    comfort_score = _compute_comfort_score(max_drawdown)

    return DrawdownResult(
        maxDrawdownPercent=round(max_drawdown, 4),
        currentDrawdownPercent=round(current_drawdown, 4),
        painRatio=round(pain_ratio, 4),
        peakValue=mdd_peak_value,
        troughValue=mdd_trough_value,
        peakDate=mdd_peak_date,
        troughDate=mdd_trough_date,
        currentValue=current_value,
        comfortScore=comfort_score,
    )


def calculateDrawdown(valueHistory: list[dict]) -> Optional[DrawdownResult]:
    """Compatibility wrapper for the legacy camelCase API."""
    return calculate_drawdown(valueHistory)


# ──────────────────────────────────────────────────────────────────────────────
# 公開介面（語義化包裝）
# ──────────────────────────────────────────────────────────────────────────────


def calculate_asset_drawdown(
    price_history: list[dict],
) -> Optional[DrawdownResult]:
    """
    計算單一資產的回撤指標。

    Args:
        price_history: [{"date": "YYYY-MM-DD", "value": float}, ...]

    Returns:
        DrawdownResult 或 None
    """
    return calculate_drawdown(price_history)


def calculateAssetDrawdown(priceHistory: list[dict]) -> Optional[DrawdownResult]:
    """Compatibility wrapper for the legacy camelCase API."""
    return calculate_asset_drawdown(priceHistory)


def calculate_portfolio_drawdown(
    portfolio_value_history: list[dict],
) -> Optional[DrawdownResult]:
    """
    計算投資組合整體的回撤指標。

    Args:
        portfolio_value_history: 組合總市值的時間序列
            [{"date": "YYYY-MM-DD", "value": float}, ...]

    Returns:
        DrawdownResult 或 None
    """
    return calculate_drawdown(portfolio_value_history)


def calculatePortfolioDrawdown(
    portfolioValueHistory: list[dict],
) -> Optional[DrawdownResult]:
    """Compatibility wrapper for the legacy camelCase API."""
    return calculate_portfolio_drawdown(portfolioValueHistory)


# ──────────────────────────────────────────────────────────────────────────────
# Report 輸出工具
# ──────────────────────────────────────────────────────────────────────────────


def format_drawdown_for_report(
    ticker: str,
    name: str,
    result: Optional[DrawdownResult],
) -> str:
    """
    格式化單一標的的回撤結果為 AI report markdown 片段。

    Args:
        ticker: 標的代碼，e.g. "1655.T"
        name:   標的名稱，e.g. "iShares S&P 500"
        result: DrawdownResult（None 時輸出資料不足提示）

    Returns:
        Markdown 字串
    """
    if result is None:
        return f"### [{ticker}] {name}\n- 資料不足，無法計算回撤指標\n"

    pain_pct = f"{result.painRatio * 100:.0f}%"
    return (
        f"### [{ticker}] {name}\n"
        f"- 最大回撤: {result.maxDrawdownPercent:.1f}%\n"
        f"- 目前回撤: {result.currentDrawdownPercent:.1f}%\n"
        f"- Pain Ratio: {pain_pct}\n"
        f"- 舒適度: {result.comfortScore}\n"
    )


def formatDrawdownForReport(
    ticker: str,
    name: str,
    result: Optional[DrawdownResult],
) -> str:
    """Compatibility wrapper for the legacy camelCase API."""
    return format_drawdown_for_report(ticker, name, result)
