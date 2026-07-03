# -*- coding: utf-8 -*-
"""
清除 ticker_cache（core/xray.py 單標的 holdings/sector 週度快照），
供資料格式異動後想強制重新抓取時使用。SQLite 快取跨週才會自動失效，重啟後端不會清掉。

用法：
  .venv/Scripts/python.exe scripts/clear_ticker_cache.py                  # 清全部
  .venv/Scripts/python.exe scripts/clear_ticker_cache.py 2330.TW          # 只清單一標的（全部 kind）
  .venv/Scripts/python.exe scripts/clear_ticker_cache.py --kind sector    # 只清某種 kind（全部標的）
  .venv/Scripts/python.exe scripts/clear_ticker_cache.py 2330.TW --kind sector
"""
import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.database import _get_connection, init_db


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker", nargs="?", help="只清除單一標的（不分大小寫）")
    parser.add_argument("--kind", choices=["holdings", "sector"], help="只清除某種 kind")
    args = parser.parse_args()

    init_db()
    where, params = [], []
    if args.ticker:
        where.append("ticker = ?")
        params.append(args.ticker.upper())
    if args.kind:
        where.append("kind = ?")
        params.append(args.kind)

    sql = "DELETE FROM ticker_cache"
    if where:
        sql += " WHERE " + " AND ".join(where)

    with _get_connection() as conn:
        cur = conn.execute(sql, params)
        print(f"已清除 {cur.rowcount} 筆快取")


if __name__ == "__main__":
    main()
