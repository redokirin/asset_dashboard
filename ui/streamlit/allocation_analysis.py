# -*- coding: utf-8 -*-
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import dashboard_logic
from core.analysis.risk_balance import (
    build_comparison_df,
    build_region_df,
    calculate_risk_weighted_allocation,
    get_asset_region,
)
from core.columns import COL_MARKET, COL_MARKET_VALUE, COL_TICKER

_CASH_MARKETS = {"bank", "cash", "現金"}
_BANK_MARKETS = {"bank", "cash", "現金"}
_REGION_TARGETS = {"台股": 0.35, "日股": 0.30, "美股": 0.35}

_DIFF_LABELS = {
    "pos_large": "↑嚴重不足",
    "pos_mid": "↑不足",
    "pos_small": "≈ 合理",
    "neg_small": "≈ 合理",
    "neg_mid": "↓偏多",
    "neg_large": "↓嚴重超配",
}


def _diff_label(diff: float) -> str:
    if diff > 0.08:
        return _DIFF_LABELS["pos_large"]
    if diff > 0.03:
        return _DIFF_LABELS["pos_mid"]
    if diff > -0.03:
        return _DIFF_LABELS["neg_small"]
    if diff > -0.08:
        return _DIFF_LABELS["neg_mid"]
    return _DIFF_LABELS["neg_large"]


def _bar_chart(
    labels: list,
    series: dict[str, list],
    title: str,
    pct: bool = True,
) -> go.Figure:
    colors = {
        "理論(波動率)": "#60a5fa",
        "理論(綜合)": "#a78bfa",
        "理論(資金加權)": "#fb923c",
        "實際配置": "#34d399",
        "現有目標": "#f59e0b",
    }
    fig = go.Figure()
    for name, values in series.items():
        text_vals = [f"{v:.1%}" if pct else f"{v:.1f}" for v in values]
        fig.add_trace(
            go.Bar(
                name=name,
                x=labels,
                y=values,
                text=text_vals,
                textposition="outside",
                marker_color=colors.get(name, "#9ca3af"),
            )
        )
    fig.update_layout(
        title=title,
        barmode="group",
        yaxis_tickformat=".0%" if pct else "",
        height=360,
        margin=dict(t=40, b=20, l=20, r=20),
        legend=dict(orientation="h", y=-0.25),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#e5e7eb",
    )
    return fig


def _investment_df(df_res: pd.DataFrame) -> pd.DataFrame:
    if COL_MARKET not in df_res.columns:
        return df_res
    mask = df_res[COL_MARKET].astype(str).str.strip().str.lower().isin(_CASH_MARKETS)
    return df_res[~mask].copy()


def _bank_df(df_res: pd.DataFrame) -> pd.DataFrame:
    if COL_MARKET not in df_res.columns:
        return pd.DataFrame()
    mask = df_res[COL_MARKET].astype(str).str.strip().str.lower().isin(_BANK_MARKETS)
    return df_res[mask].copy()


def _merge_adv(inv_df: pd.DataFrame, adv_res: pd.DataFrame) -> pd.DataFrame:
    if adv_res is None or adv_res.empty or COL_TICKER not in adv_res.columns:
        return inv_df
    cols = adv_res.columns.difference(inv_df.columns.difference([COL_TICKER]))
    return pd.merge(inv_df, adv_res[cols], on=COL_TICKER, how="left")


def show_allocation_analysis(df_res: pd.DataFrame) -> None:
    st.subheader("📊 風險加權配置分析")
    st.caption("用年化波動率動態計算理論配置比例，並與實際配置對比。分析工具，不是操作指令。")

    inv_df = _investment_df(df_res)
    bank_df = _bank_df(df_res)
    if inv_df.empty:
        st.info("無投資標的資料。")
        return

    with st.spinner("抓取進階分析數據中…"):
        adv_res = dashboard_logic.run_advanced_analysis(inv_df)

    merged = _merge_adv(inv_df, adv_res)
    valid = merged[merged["annualizedVol"].notna()].copy()

    if valid.empty:
        st.warning("無法取得年化波動率，請確認標的資料已更新。")
        return

    has_acct = not bank_df.empty
    total_mv = valid[COL_MARKET_VALUE].sum()

    # ── 個別標的比較 ──────────────────────────────────────────────────────────
    comp_df = build_comparison_df(valid, bank_df=bank_df if has_acct else None)
    has_acct_col = "理論(資金加權)" in comp_df.columns

    st.markdown("### 【個別標的理論配置】")

    display = comp_df[["標的", "波動率"]].copy()
    display["理論(波動率)"] = comp_df["理論(波動率)"].map(lambda x: f"{x:.1%}")
    if has_acct_col:
        display["理論(資金加權)"] = comp_df["理論(資金加權)"].map(
            lambda x: f"{x:.1%}" if pd.notnull(x) else "-"
        )
    display["實際配置"] = comp_df["實際配置"].map(lambda x: f"{x:.1%}")
    display["差異(波動率)"] = comp_df["差異(波動率)"].map(
        lambda x: f"{x:+.1%} {_diff_label(x)}"
    )
    if has_acct_col:
        display["差異(資金加權)"] = comp_df["差異(資金加權)"].map(
            lambda x: f"{x:+.1%} {_diff_label(x)}" if pd.notnull(x) else "-"
        )

    gap_diff = (
        comp_df["差異(資金加權)"].fillna(comp_df["差異(波動率)"])
        if has_acct_col
        else comp_df["差異(波動率)"]
    )
    display["缺口"] = gap_diff.map(
        lambda x: f"{x * total_mv:+,.0f}" if pd.notnull(x) else "-"
    )
    st.dataframe(display, width='stretch', hide_index=True)

    ind_series = {
        "理論(波動率)": comp_df["理論(波動率)"].tolist(),
        "實際配置": comp_df["實際配置"].tolist(),
    }
    if has_acct_col:
        ind_series["理論(資金加權)"] = comp_df["理論(資金加權)"].fillna(0).tolist()

    ind_chart = _bar_chart(
        labels=comp_df["標的"].tolist(),
        series=ind_series,
        title="個別標的：理論 vs 實際配置",
    )
    st.plotly_chart(ind_chart, width='stretch')

    # ── 區域比較 ──────────────────────────────────────────────────────────────
    reg_df = build_region_df(
        valid,
        region_targets=_REGION_TARGETS,
        bank_df=bank_df if has_acct else None,
    )
    has_acct_reg = "理論(資金加權)" in reg_df.columns

    st.markdown("### 【區域配置對比】")

    reg_display = reg_df[["區域"]].copy()
    reg_display["理論(波動率)"] = reg_df["理論(波動率)"].map(lambda x: f"{x:.1%}")
    if has_acct_reg:
        reg_display["理論(資金加權)"] = reg_df["理論(資金加權)"].map(
            lambda x: f"{x:.1%}" if pd.notnull(x) else "-"
        )
    reg_display["實際配置"] = reg_df["實際配置"].map(lambda x: f"{x:.1%}")

    if has_acct_reg:
        reg_diff_raw = (reg_df["理論(資金加權)"] - reg_df["實際配置"]).fillna(
            reg_df["理論(波動率)"] - reg_df["實際配置"]
        )
        reg_display["差異(資金加權)"] = reg_diff_raw.map(
            lambda x: f"{x:+.1%} {_diff_label(x)}" if pd.notnull(x) else "-"
        )
    else:
        reg_diff_raw = reg_df["理論(波動率)"] - reg_df["實際配置"]
        reg_display["差異(波動率)"] = reg_diff_raw.map(
            lambda x: f"{x:+.1%} {_diff_label(x)}"
        )

    reg_display["缺口"] = reg_diff_raw.map(
        lambda x: f"{x * total_mv:+,.0f}" if pd.notnull(x) else "-"
    )
    st.dataframe(reg_display, width='stretch', hide_index=True)

    reg_series = {
        "理論(波動率)": reg_df["理論(波動率)"].tolist(),
        "實際配置": reg_df["實際配置"].tolist(),
    }
    if has_acct_reg:
        reg_series["理論(資金加權)"] = reg_df["理論(資金加權)"].fillna(0).tolist()

    reg_chart = _bar_chart(
        labels=reg_df["區域"].tolist(),
        series=reg_series,
        title="區域配置：理論 vs 實際",
    )
    st.plotly_chart(reg_chart, width='stretch')

    # ── 新標的模擬 ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 【新標的加入模擬】")
    sim_input = st.text_input(
        "輸入新標的代碼（多個標的用逗號分隔）",
        placeholder="例如: 0050.TW, AAPL, 7203.T",
        key="alloc_sim_ticker",
    )
    if sim_input:
        tickers = [t.strip().upper() for t in sim_input.split(",") if t.strip()]
        with st.spinner(f"分析 {', '.join(tickers)} 中…"):
            sim_rows = [
                {
                    COL_TICKER: t,
                    "市場": "手動",
                    "類型": "個股",
                    "名稱": t,
                    "幣別": "TWD",
                    "單位數": 0,
                    "平均成本": 0.0,
                    "股價": 0.0,
                    "成本": 0,
                    "市值": 0.0,
                    "損益": 0,
                    "報酬率": 0.0,
                    "佔比": 0.0,
                    "_get_value": True,
                }
                for t in tickers
            ]
            sim_adv = dashboard_logic.run_advanced_analysis(pd.DataFrame(sim_rows))

        if sim_adv.empty or "annualizedVol" not in sim_adv.columns:
            st.warning("無法取得波動率數據。")
        else:
            new_rows, failed = [], []
            for t in tickers:
                match = sim_adv[sim_adv[COL_TICKER] == t]
                if match.empty or pd.isna(match.iloc[0].get("annualizedVol")):
                    failed.append(t)
                    continue
                r = match.iloc[0]
                new_rows.append({
                    COL_TICKER: t,
                    COL_MARKET: get_asset_region(t),
                    COL_MARKET_VALUE: float(r.get("股價", 0) or 0),
                    "annualizedVol": r.get("annualizedVol"),
                    "maxDrawdownPct": r.get("maxDrawdownPct"),
                    "painRatio": r.get("painRatio"),
                })

            if failed:
                st.warning(f"以下標的無法取得波動率：{', '.join(failed)}")

            if new_rows:
                new_rows_df = pd.DataFrame(new_rows)
                combined_df = pd.concat([valid, new_rows_df], ignore_index=True)
                old_ind, old_reg = calculate_risk_weighted_allocation(valid)
                new_ind, new_reg = calculate_risk_weighted_allocation(combined_df)

                sim_table = [
                    {
                        "標的": r[COL_TICKER],
                        "區域": r[COL_MARKET],
                        "年化波動率": f"{r['annualizedVol']:.1%}",
                        "理論配置(加入後)": f"{new_ind.get(r[COL_TICKER], 0):.1%}",
                    }
                    for r in new_rows
                ]
                st.dataframe(pd.DataFrame(sim_table), hide_index=True, width="stretch")

                all_regions = sorted(set(list(old_reg) + list(new_reg)))
                reg_table = [
                    {
                        "區域": region,
                        "加入前": f"{old_reg.get(region, 0):.1%}",
                        "加入後": f"{new_reg.get(region, 0):.1%}",
                        "變化": (
                            lambda d: f"{d:+.1%} "
                            + ("⬆️" if d > 0.005 else ("⬇️" if d < -0.005 else "→"))
                        )(new_reg.get(region, 0) - old_reg.get(region, 0)),
                    }
                    for region in all_regions
                ]
                st.markdown("**區域配置變化：**")
                st.dataframe(pd.DataFrame(reg_table), hide_index=True, width="stretch")
