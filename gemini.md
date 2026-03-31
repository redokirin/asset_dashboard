# 專案規範：asset_tracking

## 1. 專案概述
這是一個個人財務與資產追蹤儀表板。主要功能為讀取特定格式的財務數據，並彙整台股、美股、日股與加密貨幣等多幣別（TWD, JPY, USD）資產，進行績效計算與視覺化呈現。

## 2. 開發環境與依賴管理
- 核心語言：Python 3.12+
- 套件管理工具：**嚴格使用 Poetry**。
  - 絕對禁止建議 `pip install`，新增套件請一律給出 `poetry add <package>` 的指令。
  - 虛擬環境配置於專案根目錄下的 `.venv` (`virtualenvs.in-project = true`)。

## 3. 核心技術棧
- 數據獲取：`yfinance`
- 數據處理：`pandas`
- UI 呈現：
  - 終端機/Console：`rich`
  - 網頁版儀表板：`streamlit`

## 4. 程式碼撰寫規範
- **現代語法**：請優先使用 Python 3.10+ 的現代語法（例如：使用 `match-case` 進行條件分派，取代過長的 `if-elif-else` 鏈）。
- **中斷執行**：若需強制結束程式，請一律使用 `sys.exit()`，禁止使用 `os._exit()` 或 `quit()`。
- **環境變數**：敏感資訊（如 API Keys、憑證路徑）必須透過 `python-dotenv` 從 `.env` 檔案讀取，絕對禁止在程式碼中 hard-code。
- **效能優化**：呼叫 `yfinance` 等外部 API 時，必須實作或遵循既有的 SQLite 快取機制（如 `requests-cache` 或原生 sqlite3），避免頻繁請求導致 IP 遭封鎖。

## 5. UI 與排版特殊規則 (嚴格遵守)
- **終端機 Emoji 寬度對齊**：為了避免 `rich` 表格錯位，燈號請一律使用標準「2 字元寬度」的圓圈 Emoji。
  - ✅ 允許使用：🟠 (極度價值), 💧(跌深反彈), 🟡 (價值), 🟢 (趨勢), 🔴 (過熱), 🔥 (過熱), ⚪ (正常), 🔵 (深水)
  - ❌ **絕對禁止**：警告符號 `⚠️` (U+26A0)，會導致表格直線位移。
  - 預設空號請使用「兩個半形空白 (`"  "`)」以補足寬度。
- **財務色彩邏輯**：在終端機輸出時，若有自訂顏色需求，增長/獲利使用紅色（`[red]` 或 🔴/🔺），下跌/虧損使用綠色（`[green]` 或 🟢/▼）。

## 6. 部署與容器化規範
- 目標環境：Synology NAS (透過 Container Manager / Docker Compose)。
- Dockerfile 基礎映像檔請使用輕量級的 `python:3.12-slim`。
- Streamlit 啟動指令必須包含 `--server.address=0.0.0.0` 以確保可從外部網路存取。