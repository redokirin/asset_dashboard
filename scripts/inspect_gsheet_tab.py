# -*- coding: utf-8 -*-
"""
探查 Google Sheets 分頁的欄位結構（不寫入任何 core/ 邏輯，純檢視用）。

用法：
  .venv/Scripts/python.exe scripts/inspect_gsheet_tab.py JPY TWD
  .venv/Scripts/python.exe scripts/inspect_gsheet_tab.py          # 預設檢查 JPY, TWD
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

import gspread
from google.oauth2.service_account import Credentials

from core.data_loader import CREDENTIALS_PATH, SPREADSHEET_ID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def main():
    tabs = sys.argv[1:] or ["JPY", "TWD"]

    if not CREDENTIALS_PATH.exists():
        print(f"找不到本地憑證檔：{CREDENTIALS_PATH}")
        return

    creds = Credentials.from_service_account_file(str(CREDENTIALS_PATH), scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SPREADSHEET_ID)

    print("試算表現有分頁：", [ws.title for ws in sh.worksheets()])
    print()

    for tab in tabs:
        print("=" * 70)
        print(f"  分頁：{tab}")
        print("=" * 70)
        try:
            ws = sh.worksheet(tab)
        except gspread.exceptions.WorksheetNotFound:
            print(f"  找不到分頁 {tab}\n")
            continue

        values = ws.get_all_values()
        if not values:
            print("  （空白分頁）\n")
            continue

        header = values[0]
        print("  欄位標頭：", header)
        print(f"  總列數（含標頭）：{len(values)}")
        print("  前 5 筆資料：")
        for row in values[1:6]:
            print("   ", row)
        print()


if __name__ == "__main__":
    main()
