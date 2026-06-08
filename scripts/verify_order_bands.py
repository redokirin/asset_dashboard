# -*- coding: utf-8 -*-
"""
快速驗證 order_bands / report_runs 是否正確寫入。

用法：
  .venv/Scripts/python.exe scripts/verify_order_bands.py          # 查詢現有資料
  .venv/Scripts/python.exe scripts/verify_order_bands.py --mock   # 用假資料跑一次完整流程
  .venv/Scripts/python.exe scripts/verify_order_bands.py --date 2026-06-08
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import _DB_PATH as DB_PATH


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _table_exists(conn, name):
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


# ── 1. Schema ─────────────────────────────────────────────────────────────────


def check_schema():
    print("=== 1. Schema 確認 ===")
    with _conn() as conn:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
        ]
        print(f"現有資料表：{tables}")
        for t in ("report_runs", "order_bands", "market_events"):
            if t in tables:
                cols = [
                    r[1] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()
                ]
                print(f"  {t}: {cols}")
            else:
                print(f"  ⚠️  {t} 不存在")
    print()


# ── 2. report_runs ────────────────────────────────────────────────────────────


def show_report_runs():
    print("=== 2. 最近 report_runs ===")
    print(f"  DB: {DB_PATH.resolve()}")
    with _conn() as conn:
        if not _table_exists(conn, "report_runs"):
            print("  （report_runs 不存在）")
            print()
            return
        runs = conn.execute(
            "SELECT * FROM report_runs ORDER BY id DESC LIMIT 5"
        ).fetchall()
    if not runs:
        print("  （尚無資料）")
        print()
        return
    for r in runs:
        pt = r["is_pressure_test"] if r["is_pressure_test"] is not None else 0
        tag = r["market_event_tag"] or "-"
        ver = r["parameter_version"] or "-"
        pt_flag = " [壓力測試]" if pt else ""
        print(
            f"  id={r['id']}  {r['report_date']}  ver={ver}  tag={tag}{pt_flag}"
            f"  created={r['created_at']}"
        )
    print()


# ── 3. classify_market_event ──────────────────────────────────────────────────


def classify_market_event(rows):
    """
    根據 close_zone 分布推斷當日市場事件類型。
    回傳 (event_tag, description)。
    """
    zones = [r["close_zone"] for r in rows if r.get("close_zone")]
    if not zones:
        return None, "zone 資料不足，無法分類"

    total = len(zones)
    counts = {}
    for z in zones:
        counts[z] = counts.get(z, 0) + 1

    sniper_n = counts.get("sniper", 0) + counts.get("snipe", 0)
    pullback_n = counts.get("pullback", 0)
    daily_n = counts.get("daily", 0)
    chase_n = counts.get("chase", 0)

    detail = "  ".join(f"{k}×{v}" for k, v in sorted(counts.items()))

    if sniper_n / total >= 0.5:
        return "sniper_event", f"本日分類：sniper_event — 極端錯殺事件。（{detail}）"
    if pullback_n / total >= 0.4 and sniper_n >= 1:
        return (
            "stress_pullback",
            f"本日分類：stress_pullback — 壓力回測，需觀察 3-5 日修復。（{detail}）",
        )
    if daily_n / total >= 0.5 and sniper_n == 0:
        return (
            "orderly_pullback",
            f"本日分類：orderly_pullback — 有序回測，不是狙擊盤。（{detail}）",
        )
    if chase_n / total >= 0.5:
        return (
            "chase_event",
            f"本日分類：chase_event — 多數標的位於追價警戒區。（{detail}）",
        )

    majority = max(counts, key=counts.get)
    return (
        majority,
        f"本日多數標的位於 {majority} 區（{counts[majority]}/{total}）。（{detail}）",
    )


# ── 4. order_bands ────────────────────────────────────────────────────────────


def show_order_bands(report_date=None):
    label = report_date or "最新一次 report_run"
    print(f"=== 3. order_bands（{label}）===")
    with _conn() as conn:
        if not _table_exists(conn, "order_bands"):
            print("  （order_bands 不存在）")
            print()
            return

        if report_date:
            rows = conn.execute(
                """
                SELECT ticker, close_zone, close_position,
                       open_zone, open_position, high_zone, high_position,
                       low_zone, low_position
                FROM order_bands WHERE report_date = ? ORDER BY ticker
                """,
                (report_date,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT ticker, close_zone, close_position,
                       open_zone, open_position, high_zone, high_position,
                       low_zone, low_position
                FROM order_bands
                WHERE report_date = (SELECT MAX(report_date) FROM order_bands)
                ORDER BY ticker
                """
            ).fetchall()

    rows = [dict(r) for r in rows]

    if not rows:
        print("  （尚無資料）")
        print()
        return

    def fp(v):
        return f"{v:.4f}" if v is not None else "  -  "

    header = (
        f"{'ticker':<14}"
        f" {'close_z':<10} {'c_pos':<7}"
        f" {'open_z':<10} {'o_pos':<7}"
        f" {'high_z':<10} {'h_pos':<7}"
        f" {'low_z':<10} {'l_pos':<7}"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['ticker']:<14}"
            f" {(r['close_zone'] or 'NULL'):<10} {fp(r['close_position']):<7}"
            f" {(r['open_zone'] or 'NULL'):<10} {fp(r['open_position']):<7}"
            f" {(r['high_zone'] or 'NULL'):<10} {fp(r['high_position']):<7}"
            f" {(r['low_zone'] or 'NULL'):<10} {fp(r['low_position']):<7}"
        )

    tag, desc = classify_market_event(rows)
    print()
    print(f"  自動分類 → {desc}")
    print()


# ── 5. market_events ─────────────────────────────────────────────────────────


def show_market_events():
    print("=== 4. market_events ===")
    with _conn() as conn:
        if not _table_exists(conn, "market_events"):
            print("  （market_events 不存在）")
            print()
            return
        rows = conn.execute(
            "SELECT * FROM market_events ORDER BY event_date DESC LIMIT 10"
        ).fetchall()
    if not rows:
        print("  （尚無資料）")
        print()
        return
    for r in rows:
        pt = " [壓力測試]" if r["is_pressure_test"] else ""
        print(f"  [{r['event_date']}] {r['event_tag']}{pt}  {r['event_name'] or ''}")
        if r["event_note"]:
            for line in r["event_note"].strip().splitlines():
                print(f"      {line}")
    print()


# ── Mock 流程 ─────────────────────────────────────────────────────────────────


def run_mock():
    import pandas as pd
    from db.database import (
        create_report_run,
        get_zone_and_position,
        init_db,
        save_order_bands,
    )

    print("=== Mock 流程：寫入假資料 ===")
    init_db()

    # daily_upper=160, bdr=145, brs=130
    cases = [
        ("MOCK_A", "150.00", "daily", (150 - 145) / (160 - 145)),  # daily
        ("MOCK_B", "142.00", "pullback", (142 - 130) / (145 - 130)),  # pullback
        ("MOCK_C", "128.00", "sniper", 0),  # sniper → 0
        ("MOCK_D", "165.00", "chase", None),  # chase → None
    ]
    mock_adv = pd.DataFrame(
        [
            {
                "代碼": t,
                "股價": p,
                "dailyUpper": 160.0,
                "boundaryDailyRetest": 145.0,
                "boundaryRetestSniper": 130.0,
            }
            for t, p, _, _ in cases
        ]
    )

    run_id = create_report_run()
    count = save_order_bands(run_id, mock_adv)
    print(f"  create_report_run → run_id={run_id}")
    print(f"  save_order_bands  → {count} 筆")
    print()

    all_pass = True
    print("  驗證 get_zone_and_position：")
    for ticker, price, exp_zone, exp_pos in cases:
        zone, pos = get_zone_and_position(float(price), 160.0, 145.0, 130.0)
        ok_zone = zone == exp_zone
        if exp_pos is None:
            ok_pos = pos is None
        else:
            ok_pos = pos is not None and abs(pos - round(exp_pos, 4)) < 1e-6
        ok = ok_zone and ok_pos
        mark = "OK" if ok else "FAIL"
        print(
            f"  [{mark}] {ticker}: zone={zone}  position={pos}  (expected zone={exp_zone} pos={exp_pos})"
        )
        if not ok:
            all_pass = False

    print()
    print("  " + ("全部通過" if all_pass else "有異常，請檢查邏輯"))
    print()


# ── main ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="寫入假資料並驗證")
    parser.add_argument("--date", default=None, help="指定查詢日期，格式 YYYY-MM-DD")
    args = parser.parse_args()

    check_schema()
    if args.mock:
        run_mock()
    show_report_runs()
    show_order_bands(args.date)
    show_market_events()


if __name__ == "__main__":
    main()
