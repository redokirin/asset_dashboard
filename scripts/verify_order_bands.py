# -*- coding: utf-8 -*-
"""
快速驗證 order_bands / report_runs 是否正確寫入。

用法：
  .venv/Scripts/python.exe scripts/verify_order_bands.py          # 查詢現有資料
  .venv/Scripts/python.exe scripts/verify_order_bands.py --mock   # 用假資料跑一次完整流程
"""
import os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DB_PATH = Path(__file__).parent.parent / "db" / "portfolio.db"


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── 1. 驗證 schema ────────────────────────────────────────────────────────────

def check_schema():
    print("=== 1. Schema 確認 ===")
    with _conn() as conn:
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()]
        print(f"現有資料表：{tables}")
        for t in ("report_runs", "order_bands"):
            if t in tables:
                cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()]
                print(f"  {t}: {cols}")
            else:
                print(f"  ⚠️  {t} 不存在（需先執行一次「分析報告」或 --mock）")
    print()


# ── 2. 查詢現有資料 ───────────────────────────────────────────────────────────

def show_existing():
    print("=== 2. 現有 report_runs ===")
    with _conn() as conn:
        runs = conn.execute(
            "SELECT * FROM report_runs ORDER BY id DESC LIMIT 5"
        ).fetchall() if _table_exists(conn, "report_runs") else []
    if runs:
        for r in runs:
            print(f"  id={r['id']}  date={r['report_date']}  created={r['created_at']}")
    else:
        print("  （尚無資料）")
    print()

    print("=== 3. 最新一次 report_run 的 order_bands ===")
    with _conn() as conn:
        if not _table_exists(conn, "order_bands"):
            print("  （order_bands 資料表不存在）")
            return
        rows = conn.execute("""
            SELECT ticker, close_zone, close_position,
                   open_zone, open_position, low_zone, low_position
            FROM order_bands
            WHERE report_run_id = (SELECT MAX(id) FROM report_runs)
            ORDER BY ticker
        """).fetchall()
    if rows:
        fmt = "{:<10} {:<10} {:<8} {:<10} {:<8} {:<10} {:<8}"
        print(fmt.format("ticker", "close_zone", "close_p", "open_zone", "open_p", "low_zone", "low_p"))
        print("-" * 70)
        for r in rows:
            def fmt_pos(v):
                return f"{v:.4f}" if v is not None else "None"
            print(fmt.format(
                r["ticker"],
                r["close_zone"] or "NULL",
                fmt_pos(r["close_position"]),
                r["open_zone"] or "NULL",
                fmt_pos(r["open_position"]),
                r["low_zone"] or "NULL",
                fmt_pos(r["low_position"]),
            ))
    else:
        print("  （尚無資料）")
    print()


def _table_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


# ── 4. Mock 流程（不需要開 Streamlit）────────────────────────────────────────

def run_mock():
    import pandas as pd
    from db.database import create_report_run, save_order_bands, init_db

    print("=== Mock 流程：寫入假資料 ===")
    init_db()

    mock_adv = pd.DataFrame([
        {
            "代碼": "MOCK_A",
            "股價": "150.00",
            "dailyUpper": 160.0,
            "boundaryDailyRetest": 145.0,
            "boundaryRetestSniper": 130.0,
        },
        {
            "代碼": "MOCK_B",
            "股價": "142.00",   # 日常區
            "dailyUpper": 160.0,
            "boundaryDailyRetest": 145.0,
            "boundaryRetestSniper": 130.0,
        },
        {
            "代碼": "MOCK_C",
            "股價": "128.00",   # 狙擊區
            "dailyUpper": 160.0,
            "boundaryDailyRetest": 145.0,
            "boundaryRetestSniper": 130.0,
        },
        {
            "代碼": "MOCK_D",
            "股價": "165.00",   # 追價警戒
            "dailyUpper": 160.0,
            "boundaryDailyRetest": 145.0,
            "boundaryRetestSniper": 130.0,
        },
    ])

    run_id = create_report_run()
    count = save_order_bands(run_id, mock_adv)
    print(f"  create_report_run → run_id={run_id}")
    print(f"  save_order_bands  → {count} 筆寫入")

    # 預期結果（daily_upper=160, bdr=145, brs=130）
    expected = [
        ("MOCK_A", "daily",    (150 - 145) / (160 - 145)),  # 145 < 150 <= 160
        ("MOCK_B", "pullback", (142 - 130) / (145 - 130)),  # 130 < 142 <= 145
        ("MOCK_C", "snipe",    None),                        # 128 <= 130
        ("MOCK_D", "chase",    None),                        # 165 > 160
    ]
    # 實際結果
    from db.database import get_zone_and_position
    print()
    print("  驗證 get_zone_and_position：")
    all_pass = True
    for ticker, exp_zone, exp_pos in expected:
        row = mock_adv[mock_adv["代碼"] == ticker].iloc[0]
        zone, pos = get_zone_and_position(
            float(row["股價"]), row["dailyUpper"],
            row["boundaryDailyRetest"], row["boundaryRetestSniper"]
        )
        ok = zone == exp_zone
        marker = "✅" if ok else "❌"
        print(f"  {marker} {ticker}: zone={zone}  position={pos}")
        if not ok:
            all_pass = False

    print()
    if all_pass:
        print("  ✅ 全部通過")
    else:
        print("  ❌ 有異常，請檢查 get_zone_and_position 邏輯")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock", action="store_true", help="寫入假資料並驗證")
    args = parser.parse_args()

    check_schema()
    if args.mock:
        run_mock()
        print()
    show_existing()


if __name__ == "__main__":
    main()
