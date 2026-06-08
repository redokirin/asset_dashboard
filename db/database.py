# -*- coding: utf-8 -*-
import json
import logging
import sqlite3
from datetime import date
from pathlib import Path

import pandas as pd

_DB_PATH = Path(__file__).parent / "portfolio.db"

_CASH_MARKETS = {"bank", "cash", "現金"}

_DDL = """
CREATE TABLE IF NOT EXISTS report_runs (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    report_date       DATE    NOT NULL UNIQUE,
    parameter_version TEXT,
    market_event_tag  TEXT,
    market_event_note TEXT,
    is_pressure_test  INTEGER DEFAULT 0,
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date       TEXT NOT NULL,
    event_tag        TEXT NOT NULL,
    event_name       TEXT,
    event_note       TEXT,
    is_pressure_test INTEGER DEFAULT 0,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_bands (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    report_run_id          INTEGER NOT NULL,
    report_date            DATE    NOT NULL,
    ticker                 TEXT    NOT NULL,
    daily_upper            REAL,
    boundary_daily_retest  REAL,
    boundary_retest_sniper REAL,
    close_price            REAL,
    close_zone             TEXT,
    close_position         REAL,
    open_price             REAL,
    high_price             REAL,
    low_price              REAL,
    open_zone              TEXT,
    high_zone              TEXT,
    low_zone               TEXT,
    open_position          REAL,
    high_position          REAL,
    low_position           REAL,
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(report_run_id, ticker)
);

CREATE TABLE IF NOT EXISTS portfolio_snapshot (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date   DATE    NOT NULL UNIQUE,
    total_value     REAL,
    total_gain      REAL,
    total_gain_pct  REAL,
    invest_value    REAL,
    cash_total      REAL,
    us_ratio        REAL,
    jp_ratio        REAL,
    tw_ratio        REAL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS asset_snapshot (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date   DATE    NOT NULL,
    ticker          TEXT    NOT NULL,
    name            TEXT,
    market          TEXT,
    price           REAL,
    daily_change    REAL,
    return_pct      REAL,
    weight          REAL,
    signal          TEXT,
    pain_ratio      REAL,
    drawdown        REAL,
    rs_percentile   REAL,
    alpha_win_rate  REAL,
    sharpe          REAL,
    annualized_vol  REAL,
    rsi             REAL,
    volume_ratio    REAL,
    tags            TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(snapshot_date, ticker)
);

CREATE TABLE IF NOT EXISTS cash_snapshot (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date DATE    NOT NULL,
    account_id    TEXT    NOT NULL,
    name          TEXT,
    balance       REAL,
    investable    REAL,
    reserve       REAL,
    currency      TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(snapshot_date, account_id)
);
"""


def _get_connection():
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _migrate(conn):
    """Idempotent schema migrations — safe to run multiple times."""
    existing = {r[1] for r in conn.execute("PRAGMA table_info(report_runs)").fetchall()}
    for col, col_def in [
        ("parameter_version", "TEXT"),
        ("market_event_tag",  "TEXT"),
        ("market_event_note", "TEXT"),
        ("is_pressure_test",  "INTEGER DEFAULT 0"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE report_runs ADD COLUMN {col} {col_def}")

    ob_cols = {r[1] for r in conn.execute("PRAGMA table_info(order_bands)").fetchall()}
    for col, col_def in [
        ("planned_order_price", "REAL"),
        ("actual_filled",       "INTEGER DEFAULT 0"),
        ("execution_status",    "TEXT"),
        ("execution_note",      "TEXT"),
    ]:
        if col not in ob_cols:
            conn.execute(f"ALTER TABLE order_bands ADD COLUMN {col} {col_def}")


def init_db():
    with _get_connection() as conn:
        conn.executescript(_DDL)
        _migrate(conn)


def _safe_float(val):
    if val is None:
        return None
    try:
        s = str(val).replace("%", "").replace(",", "").strip()
        if s in ("-", "", "nan", "None"):
            return None
        return float(s)
    except (ValueError, TypeError):
        return None


def _extract_signal(entry_zone_status):
    for sig in ("日常加碼", "回測加碼", "狙擊加碼", "追價警戒"):
        if sig in str(entry_zone_status):
            return sig
    return None


def _market_ratios(investment_df):
    total = float(investment_df["市值"].sum())
    if total == 0:
        return 0.0, 0.0, 0.0
    by_market = investment_df.groupby("市場")["市值"].sum() / total
    us = float(by_market.get("美股", 0.0))
    jp = float(by_market.get("日股", 0.0))
    tw = float(by_market.get("台股", 0.0))
    return us, jp, tw


def save_snapshot(df_res, adv_res=None, snapshot_date: date = None):
    """
    將投資組合快照存入 SQLite。
    寫入失敗時只記錄警告，不中斷主程式。
    同日重複執行時覆蓋（UPSERT）。
    """
    try:
        init_db()
        today = snapshot_date or date.today()

        bank_mask = (
            df_res["市場"].fillna("").astype(str).str.strip().str.lower().isin(_CASH_MARKETS)
        )
        bank_df = df_res[bank_mask].copy()
        inv_df = df_res[~bank_mask].copy()

        # ── portfolio_snapshot ──────────────────────────────────────────────
        total_val = float(df_res["市值"].sum())
        invest_val = float(inv_df["市值"].sum())
        cash_total = float(bank_df["市值"].sum())
        total_gain = float(inv_df["損益"].sum()) if "損益" in inv_df.columns else 0.0
        invested_capital = float(inv_df["成本"].sum()) if "成本" in inv_df.columns else 0.0
        total_gain_pct = (total_gain / invested_capital * 100) if invested_capital else 0.0
        us_r, jp_r, tw_r = _market_ratios(inv_df)

        with _get_connection() as conn:
            conn.execute(
                """
                INSERT INTO portfolio_snapshot
                    (snapshot_date, total_value, total_gain, total_gain_pct,
                     invest_value, cash_total, us_ratio, jp_ratio, tw_ratio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_date) DO UPDATE SET
                    total_value    = excluded.total_value,
                    total_gain     = excluded.total_gain,
                    total_gain_pct = excluded.total_gain_pct,
                    invest_value   = excluded.invest_value,
                    cash_total     = excluded.cash_total,
                    us_ratio       = excluded.us_ratio,
                    jp_ratio       = excluded.jp_ratio,
                    tw_ratio       = excluded.tw_ratio
                """,
                (str(today), total_val, total_gain, total_gain_pct,
                 invest_val, cash_total, us_r, jp_r, tw_r),
            )

            # ── asset_snapshot ───────────────────────────────────────────────
            work_df = inv_df.copy()
            if adv_res is not None and not adv_res.empty and "代碼" in adv_res.columns:
                adv_cols = [c for c in [
                    "代碼", "entryZoneStatus", "painRatio", "currentDrawdownPct",
                    "RS 百分位", "Alpha 勝率", "夏普值", "annualizedVol", "RSI",
                    "_vol_ratio_raw", "量比", "tags",
                ] if c in adv_res.columns]
                work_df = work_df.merge(adv_res[adv_cols], on="代碼", how="left")

            asset_rows = []
            for _, row in work_df.iterrows():
                vol_ratio = row.get("_vol_ratio_raw") or _safe_float(row.get("量比"))
                tags_val = row.get("tags", [])
                tags_json = json.dumps(tags_val, ensure_ascii=False) if isinstance(tags_val, list) else None

                asset_rows.append((
                    str(today),
                    str(row.get("代碼", "")),
                    str(row.get("名稱", "")),
                    str(row.get("市場", "")),
                    _safe_float(row.get("股價")),
                    _safe_float(row.get("漲跌")),
                    _safe_float(row.get("報酬率")),
                    _safe_float(row.get("佔比")),
                    _extract_signal(row.get("entryZoneStatus", "")),
                    _safe_float(row.get("painRatio")),
                    _safe_float(row.get("currentDrawdownPct")),
                    _safe_float(row.get("RS 百分位")),
                    _safe_float(row.get("Alpha 勝率")),
                    _safe_float(row.get("夏普值")),
                    _safe_float(row.get("annualizedVol")),
                    _safe_float(row.get("RSI")),
                    _safe_float(vol_ratio),
                    tags_json,
                ))

            conn.executemany(
                """
                INSERT INTO asset_snapshot
                    (snapshot_date, ticker, name, market, price, daily_change,
                     return_pct, weight, signal, pain_ratio, drawdown,
                     rs_percentile, alpha_win_rate, sharpe, annualized_vol,
                     rsi, volume_ratio, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_date, ticker) DO UPDATE SET
                    name           = excluded.name,
                    market         = excluded.market,
                    price          = excluded.price,
                    daily_change   = excluded.daily_change,
                    return_pct     = excluded.return_pct,
                    weight         = excluded.weight,
                    signal         = excluded.signal,
                    pain_ratio     = excluded.pain_ratio,
                    drawdown       = excluded.drawdown,
                    rs_percentile  = excluded.rs_percentile,
                    alpha_win_rate = excluded.alpha_win_rate,
                    sharpe         = excluded.sharpe,
                    annualized_vol = excluded.annualized_vol,
                    rsi            = excluded.rsi,
                    volume_ratio   = excluded.volume_ratio,
                    tags           = excluded.tags
                """,
                asset_rows,
            )

            # ── cash_snapshot ────────────────────────────────────────────────
            cash_rows = []
            for _, row in bank_df.iterrows():
                account_id = str(row.get("代碼", "")).strip()
                if not account_id:
                    continue
                balance = float(row.get("市值", 0) or 0)
                reserve = float(row.get("keepTwd", 0) or 0)
                investable = balance - reserve
                cash_rows.append((
                    str(today),
                    account_id,
                    str(row.get("名稱", account_id)),
                    balance,
                    investable,
                    reserve,
                    str(row.get("幣別", "")),
                ))

            conn.executemany(
                """
                INSERT INTO cash_snapshot
                    (snapshot_date, account_id, name, balance, investable, reserve, currency)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_date, account_id) DO UPDATE SET
                    name       = excluded.name,
                    balance    = excluded.balance,
                    investable = excluded.investable,
                    reserve    = excluded.reserve,
                    currency   = excluded.currency
                """,
                cash_rows,
            )

        count = len(asset_rows)
        logging.info(f"[db] 快照已儲存：{today}，{count} 筆標的")
        return count

    except Exception as exc:
        logging.warning(f"[db] 快照寫入失敗（主程式不受影響）：{exc}")
        return 0


def get_snapshot(target_date: date) -> dict:
    """讀取指定日期的快照，回傳 portfolio / assets / cash 三個列表。"""
    try:
        init_db()
        with _get_connection() as conn:
            port = conn.execute(
                "SELECT * FROM portfolio_snapshot WHERE snapshot_date = ?",
                (str(target_date),),
            ).fetchone()
            assets = conn.execute(
                "SELECT * FROM asset_snapshot WHERE snapshot_date = ? ORDER BY weight DESC",
                (str(target_date),),
            ).fetchall()
            cash = conn.execute(
                "SELECT * FROM cash_snapshot WHERE snapshot_date = ?",
                (str(target_date),),
            ).fetchall()
        return {
            "date": str(target_date),
            "portfolio": dict(port) if port else {},
            "assets": [dict(r) for r in assets],
            "cash": [dict(r) for r in cash],
        }
    except Exception as exc:
        logging.warning(f"[db] 快照讀取失敗：{exc}")
        return {}


def get_latest_two_snapshots() -> tuple[dict, dict]:
    """
    回傳最新兩天的快照 (latest, previous)。
    供 daily_summary diff 使用（如 Pain Ratio 昨日比較）。
    """
    try:
        init_db()
        with _get_connection() as conn:
            dates = conn.execute(
                "SELECT DISTINCT snapshot_date FROM asset_snapshot ORDER BY snapshot_date DESC LIMIT 2"
            ).fetchall()
        if not dates:
            return {}, {}
        latest = get_snapshot(dates[0]["snapshot_date"])
        previous = get_snapshot(dates[1]["snapshot_date"]) if len(dates) >= 2 else {}
        return latest, previous
    except Exception as exc:
        logging.warning(f"[db] 讀取最新快照失敗：{exc}")
        return {}, {}


# ── Order Bands ──────────────────────────────────────────────────────────────


def get_zone_and_position(price, daily_upper, boundary_daily_retest, boundary_retest_sniper):
    """
    返回 (zone, position)。
    zone: "chase" | "daily" | "pullback" | "sniper"
    position:
      daily/pullback → 0.0 (區間下緣) ~ 1.0 (區間上緣)
      chase          → None（無上限，位置無意義）
      sniper         → 0（統一記為 0，表示已低於狙擊線）
    """
    if price is None or daily_upper is None or boundary_daily_retest is None or boundary_retest_sniper is None:
        return None, None
    if price > daily_upper:
        return "chase", None
    if price > boundary_daily_retest:
        denom = daily_upper - boundary_daily_retest
        pos = (price - boundary_daily_retest) / denom if denom else None
        return "daily", round(pos, 4) if pos is not None else None
    if price > boundary_retest_sniper:
        denom = boundary_daily_retest - boundary_retest_sniper
        pos = (price - boundary_retest_sniper) / denom if denom else None
        return "pullback", round(pos, 4) if pos is not None else None
    return "sniper", 0


def create_report_run(report_date: date = None) -> int:
    """同一天只保留一筆 report_run。當天已有記錄直接回傳其 id，否則新增。"""
    init_db()
    today = report_date or date.today()
    with _get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM report_runs WHERE report_date = ? ORDER BY id DESC LIMIT 1",
            (str(today),),
        ).fetchone()
        if existing:
            return existing["id"]
        cur = conn.execute(
            "INSERT INTO report_runs (report_date) VALUES (?)", (str(today),)
        )
        return cur.lastrowid


def save_order_bands(report_run_id: int, adv_res, snapshot_date: date = None) -> int:
    """
    盤中執行：寫入各標的 close_price/close_zone/close_position。
    open/high/low 欄位留 NULL，待收盤後由 update_ohlc_zones() 補齊。
    """
    try:
        init_db()
        if adv_res is None or adv_res.empty:
            return 0
        today = snapshot_date or date.today()

        rows = []
        for _, row in adv_res.iterrows():
            ticker = str(row.get("代碼", ""))
            if not ticker:
                continue
            if ticker.upper().startswith("0P"):
                logging.debug(f"[db] save_order_bands: 跳過基金標的 {ticker}（yfinance 無 OHLC）")
                continue
            du = row.get("dailyUpper")
            bdr = row.get("boundaryDailyRetest")
            brs = row.get("boundaryRetestSniper")
            close_price = _safe_float(row.get("股價"))
            close_zone, close_pos = get_zone_and_position(close_price, du, bdr, brs)
            rows.append((
                report_run_id, str(today), ticker,
                du, bdr, brs,
                close_price, close_zone, close_pos,
            ))

        with _get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO order_bands
                    (report_run_id, report_date, ticker,
                     daily_upper, boundary_daily_retest, boundary_retest_sniper,
                     close_price, close_zone, close_position)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(report_run_id, ticker) DO UPDATE SET
                    daily_upper            = excluded.daily_upper,
                    boundary_daily_retest  = excluded.boundary_daily_retest,
                    boundary_retest_sniper = excluded.boundary_retest_sniper,
                    close_price            = excluded.close_price,
                    close_zone             = excluded.close_zone,
                    close_position         = excluded.close_position
                """,
                rows,
            )
        logging.info(
            f"[db] order_bands 已寫入：run_id={report_run_id}, {len(rows)} 筆。"
            "OHLC data unavailable at analysis time, only close zone recorded."
            " Run update_ohlc_zones() after market close to fill open/high/low."
        )
        return len(rows)
    except Exception as exc:
        logging.warning(f"[db] order_bands 寫入失敗：{exc}")
        return 0


def update_ohlc_zones(report_date: str) -> list[dict]:
    """
    收盤後補齊當日所有標的的 open/high/low 區間位置。
    回傳當日完整的區間落點表（含 close）。
    """
    from core.data_sources.yahoo import fetch_ohlc

    try:
        init_db()
        with _get_connection() as conn:
            band_rows = conn.execute(
                """
                SELECT ob.id, ob.ticker,
                       ob.daily_upper, ob.boundary_daily_retest, ob.boundary_retest_sniper,
                       ob.planned_order_price, ob.actual_filled
                FROM order_bands ob
                WHERE ob.report_date = ?
                """,
                (report_date,),
            ).fetchall()

        if not band_rows:
            logging.info(f"[db] update_ohlc_zones: {report_date} 無 order_bands 資料")
            return []

        with _get_connection() as conn:
            for row in band_rows:
                if row["ticker"].upper().startswith("0P"):
                    continue
                ohlc = fetch_ohlc(row["ticker"], report_date)
                if not ohlc:
                    logging.warning(f"[db] update_ohlc_zones: {row['ticker']} OHLC 取得失敗，跳過")
                    continue
                du = row["daily_upper"]
                bdr = row["boundary_daily_retest"]
                brs = row["boundary_retest_sniper"]
                open_zone, open_pos = get_zone_and_position(ohlc["open"], du, bdr, brs)
                high_zone, high_pos = get_zone_and_position(ohlc["high"], du, bdr, brs)
                low_zone, low_pos = get_zone_and_position(ohlc["low"], du, bdr, brs)
                conn.execute(
                    """
                    UPDATE order_bands SET
                        open_price = ?, open_zone = ?, open_position = ?,
                        high_price = ?, high_zone = ?, high_position = ?,
                        low_price  = ?, low_zone  = ?, low_position  = ?
                    WHERE id = ?
                    """,
                    (
                        ohlc["open"], open_zone, open_pos,
                        ohlc["high"], high_zone, high_pos,
                        ohlc["low"], low_zone, low_pos,
                        row["id"],
                    ),
                )
                if row["planned_order_price"] is not None:
                    missed = detect_missed_execution(
                        ticker=row["ticker"],
                        low_price=ohlc["low"],
                        planned_order_price=row["planned_order_price"],
                        actual_filled=bool(row["actual_filled"]),
                        close_price=ohlc["close"],
                    )
                    if missed:
                        conn.execute(
                            "UPDATE order_bands SET execution_status=?, execution_note=? WHERE id=?",
                            (missed["status"], missed["note"], row["id"]),
                        )

        with _get_connection() as conn:
            final = conn.execute(
                """
                SELECT ticker, open_zone, low_zone, close_zone,
                       open_position, low_position, close_position
                FROM order_bands
                WHERE report_date = ?
                ORDER BY ticker
                """,
                (report_date,),
            ).fetchall()

        return [dict(r) for r in final]
    except Exception as exc:
        logging.warning(f"[db] update_ohlc_zones 失敗：{exc}")
        return []


# ── Execution Status ──────────────────────────────────────────────────────────


def detect_missed_execution(ticker, low_price, planned_order_price, actual_filled, close_price):
    """
    三條件同時成立時標記 manual_override_missed_fill：
    1. low_price <= planned_order_price （價格曾到達掛單位置）
    2. actual_filled == False
    3. close_price > planned_order_price （收盤已反彈超過掛單價）
    """
    if (low_price is not None and
            low_price <= planned_order_price and
            not actual_filled and
            close_price is not None and
            close_price > planned_order_price):
        return {
            "status": "manual_override_missed_fill",
            "note": (
                f"系統價位曾觸發（最低 {low_price}，掛單 {planned_order_price}），"
                "但因人工觀望或資料延遲未成交，"
                "收盤已反彈。"
                "屬執行層問題，不代表掛單參數錯誤。"
            ),
        }
    return None


def update_execution_status(
    report_date: str,
    ticker: str,
    planned_order_price: float,
    actual_filled: bool = False,
) -> dict:
    """手動補錄或更新執行狀態。需在 update_ohlc_zones() 之後呼叫（low_price 需已填入）。"""
    init_db()
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT id, low_price, close_price FROM order_bands WHERE report_date=? AND ticker=?",
            (report_date, ticker),
        ).fetchone()
        if not row:
            logging.warning(f"[db] update_execution_status: {ticker} {report_date} 無記錄")
            return {}

        result = detect_missed_execution(
            ticker=ticker,
            low_price=row["low_price"],
            planned_order_price=planned_order_price,
            actual_filled=actual_filled,
            close_price=row["close_price"],
        )
        status = result["status"] if result else "no_trigger"
        note = result["note"] if result else None

        conn.execute(
            """UPDATE order_bands SET
                planned_order_price = ?,
                actual_filled = ?,
                execution_status = ?,
                execution_note = ?
               WHERE id = ?""",
            (planned_order_price, int(actual_filled), status, note, row["id"]),
        )
    return {"ticker": ticker, "status": status, "note": note}


# ── Market Events ─────────────────────────────────────────────────────────────


def add_market_event(
    event_date: str,
    event_tag: str,
    event_name: str = None,
    event_note: str = None,
    is_pressure_test: int = 0,
) -> int:
    """新增一筆 market_events 記錄，回傳 id。"""
    from datetime import datetime
    init_db()
    with _get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO market_events
                (event_date, event_tag, event_name, event_note, is_pressure_test, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_date, event_tag, event_name, event_note, is_pressure_test,
             datetime.now().isoformat()),
        )
        return cur.lastrowid


def update_report_run_event(
    report_date: str,
    market_event_tag: str = None,
    market_event_note: str = None,
    is_pressure_test: int = None,
    parameter_version: str = None,
) -> bool:
    """更新指定日期最新 report_run 的事件欄位。"""
    init_db()
    updates, values = [], []
    if market_event_tag is not None:
        updates.append("market_event_tag = ?");  values.append(market_event_tag)
    if market_event_note is not None:
        updates.append("market_event_note = ?"); values.append(market_event_note)
    if is_pressure_test is not None:
        updates.append("is_pressure_test = ?");  values.append(is_pressure_test)
    if parameter_version is not None:
        updates.append("parameter_version = ?"); values.append(parameter_version)
    if not updates:
        return False
    with _get_connection() as conn:
        run = conn.execute(
            "SELECT id FROM report_runs WHERE report_date = ? ORDER BY id DESC LIMIT 1",
            (report_date,),
        ).fetchone()
        if not run:
            logging.warning(f"[db] update_report_run_event: {report_date} 無 report_run")
            return False
        values.append(run["id"])
        conn.execute(f"UPDATE report_runs SET {', '.join(updates)} WHERE id = ?", values)
    return True
