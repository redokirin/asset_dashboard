# -*- coding: utf-8 -*-
"""
檢查指定代碼有沒有被 get_assets() 正確讀進來（跳過 API 層的所有快取，直接讀 Google Sheets）。

用法：
  .venv/Scripts/python.exe scripts/inspect_asset_row.py 1321.T
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_loader import get_assets


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "1321.T"
    assets = get_assets()

    print(f"檢查代碼：{target}\n")
    for cat in ["etfs", "stocks", "funds", "banks"]:
        cat_dict = assets.get(cat, {})
        print(f"[{cat}]  共 {len(cat_dict)} 筆")
        if target in cat_dict:
            print(f"  找到！內容：")
            for k, v in cat_dict[target].items():
                print(f"    {k}: {v!r}")
        else:
            # 順便看看有沒有相近但對不上的 key（大小寫、多餘空白等）
            close = [k for k in cat_dict if target.strip().upper() == str(k).strip().upper()]
            if close:
                print(f"  沒有精確符合，但找到大小寫不同的 key：{close}")
            else:
                print(f"  沒找到")
        print()


if __name__ == "__main__":
    main()
