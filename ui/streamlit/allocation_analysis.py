# -*- coding: utf-8 -*-
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core import dashboard_logic
from core.analysis.risk_balance import (
    build_comparison_df,
    build_region_df,
    evaluate_new_asset,
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

    # ── 個別標的比較 ──────────────────────────────────────────────────────────
    comp_df = build_comparison_df(valid, bank_df=bank_df if has_acct else None)
    has_acct_col = "理論(資金加權)" in comp_df.columns

    st.markdown("### 【個別標的理論配置】")

    display = comp_df.copy()
    for col in ["理論(波動率)", "理論(綜合)", "實際配置"]:
        display[col] = comp_df[col].map(lambda x: f"{x:.1%}")
    display["差異(波動率)"] = comp_df["差異(波動率)"].map(
        lambda x: f"{x:+.1%} {_diff_label(x)}"
    )
    display["差異(綜合)"] = comp_df["差異(綜合)"].map(
        lambda x: f"{x:+.1%} {_diff_label(x)}"
    )
    if has_acct_col:
        display["理論(資金加權)"] = comp_df["理論(資金加權)"].map(
            lambda x: f"{x:.1%}" if pd.notnull(x) else "-"
        )
        display["差異(資金加權)"] = comp_df["差異(資金加權)"].map(
            lambda x: f"{x:+.1%} {_diff_label(x)}" if pd.notnull(x) else "-"
        )
    st.dataframe(display, width='stretch', hide_index=True)

    ind_series = {
        "理論(波動率)": comp_df["理論(波動率)"].tolist(),
        "理論(綜合)": comp_df["理論(綜合)"].tolist(),
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

    reg_display = reg_df.copy()
    for col in ["理論(波動率)", "理論(綜合)", "實際配置"]:
        reg_display[col] = reg_df[col].map(lambda x: f"{x:.1%}")
    reg_display["現有目標"] = reg_df["現有目標"].map(
        lambda x: f"{x:.1%}" if pd.notnull(x) else "—"
    )
    if has_acct_reg:
        reg_display["理論(資金加權)"] = reg_df["理論(資金加權)"].map(
            lambda x: f"{x:.1%}" if pd.notnull(x) else "-"
        )
    st.dataframe(reg_display, width='stretch', hide_index=True)

    reg_series = {
        "理論(波動率)": reg_df["理論(波動率)"].tolist(),
        "理論(綜合)": reg_df["理論(綜合)"].tolist(),
        "實際配置": reg_df["實際配置"].tolist(),
    }
    if has_acct_reg:
        reg_series["理論(資金加權)"] = reg_df["理論(資金加權)"].fillna(0).tolist()
    if reg_df["現有目標"].notna().any():
        reg_series["現有目標"] = reg_df["現有目標"].fillna(0).tolist()

    reg_chart = _bar_chart(
        labels=reg_df["區域"].tolist(),
        series=reg_series,
        title="區域配置：理論 vs 實際 vs 目標",
    )
    st.plotly_chart(reg_chart, width='stretch')

    # ── 新標的模擬 ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 【新標的加入模擬】")
    sim_ticker = st.text_input(
        "輸入新標的代碼（模擬加入後的配置變化）",
        placeholder="例如: 0050.TW",
        key="alloc_sim_ticker",
    )
    if sim_ticker:
        sim_ticker = sim_ticker.strip().upper()
        with st.spinner(f"分析 {sim_ticker} 中…"):
            sim_df = pd.DataFrame(
                [
                    {
                        COL_TICKER: sim_ticker,
                        "市場": "手動",
                        "類型": "個股",
                        "名稱": sim_ticker,
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
                ]
            )
            sim_adv = dashboard_logic.run_advanced_analysis(sim_df)

        if sim_adv.empty or "annualizedVol" not in sim_adv.columns:
            st.warning(f"無法取得 {sim_ticker} 的波動率數據。")
        else:
            sim_row_adv = sim_adv.iloc[0]
            new_row = {
                COL_TICKER: sim_ticker,
                COL_MARKET: get_asset_region(sim_ticker),
                COL_MARKET_VALUE: float(sim_row_adv.get("股價", 0) or 0),
                "annualizedVol": sim_row_adv.get("annualizedVol"),
                "maxDrawdownPct": sim_row_adv.get("maxDrawdownPct"),
                "painRatio": sim_row_adv.get("painRatio"),
            }
            result = evaluate_new_asset(new_row, valid)
            st.markdown(f"**{sim_ticker} 加入後的理論配置: {result['theoretical_weight']:.1%}**")
            st.markdown("**區域配置變化：**")
            for region, chg in result["region_changes"].items():
                delta = chg["after"] - chg["before"]
                arrow = "⬆️" if delta > 0.005 else ("⬇️" if delta < -0.005 else "→")
                st.markdown(
                    f"- **{region}**: {chg['before']:.1%} → {chg['after']:.1%} ({delta:+.1%}) {arrow}"
                )
