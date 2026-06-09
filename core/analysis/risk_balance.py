# -*- coding: utf-8 -*-
import pandas as pd

from core.columns import COL_CURRENCY, COL_MARKET, COL_MARKET_VALUE, COL_TICKER

# 獨立帳戶基金（TISA）：不計入帳戶可投入金額，直接用實際市值代入
INDEPENDENT_FUNDS = frozenset({"0P00006AKV.TW", "0P00009PAQ.TW"})

_REGION_FROM_MARKET = {"美股", "日股", "台股", "全球"}


def get_asset_region(
    ticker: str,
    market: str | None = None,
    region: str | None = None,
) -> str:
    """
    判斷標的所屬區域（供風險加權配置分析使用）。
    優先序：region 欄位 > ticker 尾綴 > market 欄位 > "全球"
    """
    if region and str(region).strip() in _REGION_FROM_MARKET:
        return str(region).strip()
    t = ticker.upper()
    if t.endswith(".T"):
        return "日股"
    if t.endswith(".TW") or t.endswith(".TWO") or t.startswith("0P000"):
        return "台股"
    if market and str(market).strip() in _REGION_FROM_MARKET:
        return str(market).strip()
    return "全球"


def _vol_raw_weights(df: pd.DataFrame) -> dict:
    """計算以 1/annualizedVol 為基礎的原始權重。"""
    raw = {}
    for _, row in df.iterrows():
        vol = row.get("annualizedVol")
        try:
            vol = float(vol)
        except (TypeError, ValueError):
            continue
        if vol > 0:
            raw[row[COL_TICKER]] = 1.0 / vol
    return raw


def _composite_raw_weights(df: pd.DataFrame) -> dict:
    """計算以綜合風險分數 (0.5*vol + 0.3*mdd + 0.2*pain) 為基礎的原始權重。"""
    raw = {}
    for _, row in df.iterrows():
        try:
            vol = float(row.get("annualizedVol") or 0)
            mdd = abs(float(row.get("maxDrawdownPct") or 0))
            pain = float(row.get("painRatio") or 0)
        except (TypeError, ValueError):
            continue
        composite = 0.5 * vol + 0.3 * mdd + 0.2 * pain
        if composite > 0:
            raw[row[COL_TICKER]] = 1.0 / composite
    return raw


def _normalize(raw: dict) -> dict:
    total = sum(raw.values())
    if total == 0:
        return {}
    return {t: w / total for t, w in raw.items()}


def _region_weights(individual: dict, df: pd.DataFrame) -> dict:
    region_w: dict[str, float] = {}
    for _, row in df.iterrows():
        ticker = row[COL_TICKER]
        if ticker not in individual:
            continue
        region = get_asset_region(ticker, row.get(COL_MARKET), row.get("region"))
        region_w[region] = region_w.get(region, 0.0) + individual[ticker]
    return region_w


def calculate_risk_weighted_allocation(df: pd.DataFrame) -> tuple[dict, dict]:
    """
    純波動率版：用 1/annualizedVol 計算理論配置。
    Returns (individual_weights, region_weights) — 值均為 0~1 的比例。
    """
    raw = _vol_raw_weights(df)
    individual = _normalize(raw)
    return individual, _region_weights(individual, df)


def calculate_composite_weights(df: pd.DataFrame) -> tuple[dict, dict]:
    """
    綜合風險版：用 1/(0.5*vol + 0.3*mdd + 0.2*pain) 計算理論配置。
    Returns (individual_weights, region_weights)。
    """
    raw = _composite_raw_weights(df)
    individual = _normalize(raw)
    return individual, _region_weights(individual, df)


def build_comparison_df(
    df: pd.DataFrame,
    bank_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    建立個別標的的比較 DataFrame。
    bank_df 傳入時額外計算「理論(資金加權)」欄位。
    """
    total_val = df[COL_MARKET_VALUE].sum()
    vol_ind, _ = calculate_risk_weighted_allocation(df)
    comp_ind, _ = calculate_composite_weights(df)

    has_acct = bank_df is not None and not bank_df.empty
    acct_ind, _ = (
        calculate_account_weighted_allocation(df, bank_df) if has_acct else ({}, {})
    )

    rows = []
    for _, row in df.iterrows():
        ticker = row[COL_TICKER]
        vol = row.get("annualizedVol")
        try:
            vol_pct = f"{float(vol):.1%}"
        except (TypeError, ValueError):
            vol_pct = "-"

        actual = (float(row[COL_MARKET_VALUE]) / total_val) if total_val else 0
        theo_vol = vol_ind.get(ticker, 0)
        theo_comp = comp_ind.get(ticker, 0)
        theo_acct = acct_ind.get(ticker) if acct_ind else None

        entry = {
            "標的": ticker,
            "波動率": vol_pct,
            "理論(波動率)": theo_vol,
            "理論(綜合)": theo_comp,
            "實際配置": actual,
            "差異(波動率)": theo_vol - actual,
            "差異(綜合)": theo_comp - actual,
        }
        if acct_ind:
            entry["理論(資金加權)"] = theo_acct if theo_acct is not None else 0.0
            entry["差異(資金加權)"] = (theo_acct - actual) if theo_acct is not None else None

        rows.append(entry)

    return pd.DataFrame(rows)


def build_region_df(
    df: pd.DataFrame,
    region_targets: dict | None = None,
    bank_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    建立區域配置比較 DataFrame。
    bank_df 傳入時額外計算「理論(資金加權)」欄位。
    region_targets 格式：{"台股": 0.35, "日股": 0.30, "美股": 0.35}
    """
    total_val = df[COL_MARKET_VALUE].sum()
    _, vol_reg = calculate_risk_weighted_allocation(df)
    _, comp_reg = calculate_composite_weights(df)

    has_acct = bank_df is not None and not bank_df.empty
    _, acct_reg = (
        calculate_account_weighted_allocation(df, bank_df) if has_acct else ({}, {})
    )

    actual_by_region: dict[str, float] = {}
    for _, row in df.iterrows():
        region = get_asset_region(row[COL_TICKER], row.get(COL_MARKET), row.get("region"))
        actual_by_region[region] = (
            actual_by_region.get(region, 0.0)
            + float(row[COL_MARKET_VALUE]) / total_val
        )

    all_regions = sorted(set(list(vol_reg) + list(actual_by_region)))
    rows = []
    for region in all_regions:
        entry = {
            "區域": region,
            "理論(波動率)": vol_reg.get(region, 0),
            "理論(綜合)": comp_reg.get(region, 0),
            "實際配置": actual_by_region.get(region, 0),
            "現有目標": (region_targets or {}).get(region),
        }
        if acct_reg:
            entry["理論(資金加權)"] = acct_reg.get(region, 0)
        rows.append(entry)
    return pd.DataFrame(rows)


def _account_from_ticker(ticker: str) -> str:
    """依 ticker 尾綴判斷帳戶類型（台幣 / 日幣）。"""
    return "日幣" if ticker.upper().endswith(".T") else "台幣"


def calculate_account_weighted_allocation(
    inv_df: pd.DataFrame,
    bank_df: pd.DataFrame,
) -> tuple[dict, dict]:
    """
    帳戶資金限制版：依台幣/日幣可投入金額加權後正規化。
    台幣帳戶只買非 .T 標的；日幣帳戶只買 .T 標的。
    獨立帳戶基金（TISA）直接用實際市值代入。
    Returns (individual_weights, region_weights)，無銀行資料時回傳 ({}, {})。
    """
    # Step 1: 各帳戶可投入金額 (TWD)
    investable: dict[str, float] = {"台幣": 0.0, "日幣": 0.0}
    for _, row in bank_df.iterrows():
        ccy = str(row.get(COL_CURRENCY, "TWD")).upper()
        mv = float(row.get(COL_MARKET_VALUE, 0) or 0)
        keep = float(row.get("keepTwd", 0) or 0)
        inv_amt = max(0.0, mv - keep)
        if ccy == "JPY":
            investable["日幣"] += inv_amt
        else:
            investable["台幣"] += inv_amt

    if sum(investable.values()) == 0:
        return {}, {}

    # Step 2: 分離獨立帳戶基金
    is_fund_mask = inv_df[COL_TICKER].isin(INDEPENDENT_FUNDS)
    regular_df = inv_df[~is_fund_mask]
    funds_df = inv_df[is_fund_mask]

    # Step 3: 各帳戶內 1/vol 加權 × 帳戶預算
    raw_allocation: dict[str, float] = {}
    for account, budget in investable.items():
        if budget <= 0:
            continue
        group = regular_df[
            regular_df[COL_TICKER].apply(_account_from_ticker) == account
        ]
        acct_raw: dict[str, float] = {}
        for _, row in group.iterrows():
            try:
                vol = float(row.get("annualizedVol") or 0)
            except (TypeError, ValueError):
                continue
            if vol > 0:
                acct_raw[row[COL_TICKER]] = 1.0 / vol
        total_w = sum(acct_raw.values())
        if total_w > 0:
            for ticker, w in acct_raw.items():
                raw_allocation[ticker] = (w / total_w) * budget

    # Step 4: 獨立帳戶基金以實際市值代入
    for _, row in funds_df.iterrows():
        raw_allocation[row[COL_TICKER]] = float(row.get(COL_MARKET_VALUE, 0) or 0)

    # Step 5: 正規化
    total = sum(raw_allocation.values())
    if total == 0:
        return {}, {}
    individual = {t: v / total for t, v in raw_allocation.items()}
    return individual, _region_weights(individual, inv_df)


def evaluate_new_asset(new_row: dict, df_existing: pd.DataFrame) -> dict:
    """
    模擬新標的加入後的配置變化。
    new_row 需含 COL_TICKER, annualizedVol, maxDrawdownPct, painRatio, COL_MARKET_VALUE。
    """
    old_ind, old_reg = calculate_risk_weighted_allocation(df_existing)
    new_df = pd.concat(
        [df_existing, pd.DataFrame([new_row])], ignore_index=True
    )
    new_ind, new_reg = calculate_risk_weighted_allocation(new_df)

    ticker = new_row[COL_TICKER]
    all_regions = sorted(set(list(old_reg) + list(new_reg)))
    region_changes = {
        r: {"before": old_reg.get(r, 0), "after": new_reg.get(r, 0)}
        for r in all_regions
    }
    return {
        "ticker": ticker,
        "theoretical_weight": new_ind.get(ticker, 0),
        "region_changes": region_changes,
    }
