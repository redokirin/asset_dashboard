# Asset Tracking — CLAUDE.md

個人全球資產追蹤系統，追蹤台股、日股、美股、基金、銀行帳戶的市值與損益。

---

## 目錄架構

```
asset_tracking/
├── api/                        # FastAPI 後端
│   └── main.py                 # 端點：/health, /api/portfolio
│
├── apps/                       # 執行進入點
│   ├── dashboard_st.py         # Streamlit 主程式（目前主要 UI）
│   ├── dashboard_cli.py        # CLI 模式
│   └── dashboard.py            # 通用啟動包裝
│
├── core/                       # 純業務邏輯（無 UI 依賴）
│   ├── columns.py              # 所有 DataFrame 欄位名稱常數（COL_*）
│   ├── data_loader.py          # Google Sheets 讀取、config 載入
│   ├── fetchers.py             # 相容性 facade，re-export data_sources/*
│   ├── calculators.py          # 資產計算主邏輯（calculate_assets_data）
│   ├── dashboard_logic.py      # Facade 模組，整合各子模組供外部呼叫
│   ├── daily_summary.py        # 每日摘要與操作建議（generate_daily_summary）
│   ├── exporters.py            # AI 報告匯出（export_for_ai）
│   ├── buy_levels.py           # 買點計算（get_buy_levels）
│   ├── risk.py                 # 回撤計算（calculate_drawdown）
│   ├── tags.py                 # 決策標籤
│   ├── analysis_quant.py       # 量化分析入口（re-export analysis/*）
│   ├── analysis/               # 量化分析子模組
│   │   ├── advanced.py         # run_advanced_analysis() — 主量化管線
│   │   ├── benchmark.py        # get_smart_benchmark() — 基準選擇
│   │   ├── diagnosis.py        # generate_advanced_diagnosis() — 文字診斷
│   │   ├── overall_risk.py     # calculate_overall_risk_score() — 組合風險
│   │   ├── risk_balance.py     # calculate_risk_weighted_allocation() — 風險加權配置
│   │   └── technical.py        # 技術指標（MA、RSI、Sharpe、MDD）
│   └── data_sources/           # 外部資料來源
│       ├── yahoo.py            # yfinance 下載（FETCHERS dict、fetch_historical_data）
│       ├── market_radar.py     # 大盤雷達（get_market_radar_data）
│       ├── cache.py            # requests_cache 安裝
│       └── patches.py          # yfinance 相容性修補
│
├── ui/                         # UI 層（依賴 core，不被 core 依賴）
│   ├── dashboard_ui.py         # Streamlit UI 總進入點（show_streamlit）
│   ├── ui_streamlit.py         # Streamlit render 主流程
│   ├── ui_common.py            # 共用格式化工具
│   ├── ui_console.py           # CLI 輸出格式化
│   ├── ui_jupyter.py           # Jupyter 輸出格式化
│   ├── style.css               # Streamlit 自訂樣式
│   └── streamlit/              # Streamlit 元件模組
│       ├── portfolio.py        # 持股表格、市場卡片、報告元件
│       ├── advanced_analysis.py# 量化分析頁（手動分析 tab）
│       ├── allocation_analysis.py # 配置分析視圖
│       ├── charts.py           # Plotly 圓餅圖、K 線圖
│       ├── components.py       # 共用 HTML 元件
│       └── filters.py          # 側邊欄過濾器
│
├── frontends/vue/              # Vue 3 前端（開發中，目標取代 Streamlit）
│   ├── src/
│   │   ├── api/portfolio.js    # axios 呼叫 FastAPI
│   │   ├── views/Dashboard.vue # 主儀表板視圖
│   │   ├── components/         # AssetTable, SummaryCard, PieChart...
│   │   └── utils/colors.js     # 顏色工具
│   ├── vite.config.js
│   └── package.json
│
├── db/
│   ├── database.py             # SQLite CRUD（report_runs, order_bands, portfolio_snapshot）
│   └── portfolio.db            # SQLite 資料庫檔案（勿提交）
│
├── tests/                      # pytest 測試（對應 core/ 各模組）
├── scripts/                    # 一次性資料庫種子與維護腳本
├── analyze/                    # 匯出的 AI 報告（勿提交重要決策內容）
├── refactor/                   # 重構規劃文件（參考用）
├── docs/                       # 投資策略文件
│   ├── strategy_rules.md
│   ├── investment_profile.md
│   └── decision_tags.yaml
├── assets_config.toml          # 本地設定（覆蓋 GSheets，勿提交）
├── credentials.json            # Google Service Account（勿提交）
├── pyproject.toml              # Poetry 依賴管理
└── requirements.txt            # pip 相容格式
```

---

## 資料流

```
Google Sheets（etfs / stocks / funds / Bank 工作表）
    ↓  data_loader.get_config_from_gsheets()
    ↓
data_sources/market_radar.py → get_market_radar_data()   ← Yahoo Finance
    ↓  calculators.exchange_rate(radar) → {JPY, USD, TWD}
    ↓
calculators.calculate_assets_data(exchange_rates)
    → df_res（DataFrame）+ market_share（dict）
    ↓
analysis/advanced.run_advanced_analysis(df_res)
    → adv_res（量化指標 DataFrame）
    ↓
api/main.py /api/portfolio  ←→  frontends/vue（目標架構）
apps/dashboard_st.py        ←→  ui/streamlit/*（現況）
```

---

## 命名慣例

### Python

| 類型 | 慣例 | 範例 |
|------|------|------|
| 函式 / 變數 | `snake_case` | `calculate_assets_data`, `df_res` |
| DataFrame 欄位常數 | `COL_` 前綴，定義於 `core/columns.py` | `COL_MARKET_VALUE`, `COL_TICKER` |
| DataFrame 欄位值 | 中文字串（UI 契約，不改） | `"市值"`, `"損益"` |
| 私有輔助函式 | 底線前綴 | `_safe(v)`, `_load_data()` |
| 測試檔案 | `test_` 前綴對應模組名 | `test_calculators.py` |

### Vue / JS

| 類型 | 慣例 | 範例 |
|------|------|------|
| 元件檔案 | `PascalCase.vue` | `AssetTable.vue` |
| JS 工具 | `camelCase.js` | `colors.js` |
| API 模組 | 依資源命名 | `api/portfolio.js` |

### DataFrame 欄位分類

- **基礎欄位**（`calculate_assets_data` 產出）：`COL_MARKET`, `COL_NAME`, `COL_TICKER`, `COL_PRICE`, `COL_MARKET_VALUE`, `COL_COST`, `COL_PROFIT_LOSS`, `COL_RETURN_PCT`, `COL_WEIGHT`
- **進階分析欄位**（`run_advanced_analysis` 產出）：`annualizedVol`, `RSI`, `sharpeRatio`, `maxDrawdown`, `COL_TECH_DIAGNOSIS`
- **私有欄位**：底線前綴，如 `COL_GET_VALUE = "_get_value"`（不顯示於 UI）

---

## 常用指令

### Python 環境

```bash
# 安裝依賴（Poetry）
poetry install

# 啟動 Streamlit UI
poetry run streamlit run apps/dashboard_st.py

# 啟動 FastAPI（開發模式，port 8000）
poetry run uvicorn api.main:app --reload --port 8000

# 執行測試
poetry run pytest tests/ -v

# 執行單一測試模組
poetry run pytest tests/test_calculators.py -v
```

### Vue 前端

```bash
cd frontends/vue

# 安裝依賴
npm install

# 開發模式（port 5173，proxy → FastAPI 8000）
npm run dev

# 打包
npm run build
```

### 資料庫維護腳本

```bash
# 更新 OHLC 區間資料
poetry run python scripts/update_ohlc_zones.py

# 驗證掛單區間
poetry run python scripts/verify_order_bands.py
```

---

## 關鍵設計規則

1. **`core/` 不依賴任何 UI 框架**：Streamlit、Rich、Vue 只在 `ui/` 和 `apps/` 使用。
2. **欄位名稱集中管理**：所有 DataFrame column key 必須在 `core/columns.py` 定義為 `COL_*` 常數，不得在各模組散落硬編碼中文字串。
3. **快取注入模式**：`apps/dashboard_st.py` 透過 `dashboard_logic.FETCHERS` dict 注入帶 `@st.cache_data` 的 fetcher，讓 `core/` 保持無 Streamlit 依賴。
4. **FastAPI 序列化**：`NaN` / `inf` / `Timestamp` 一律在 `api/main.py` 的 `_safe()` 處理後才輸出 JSON，Vue 端不需要做特殊處理。
5. **SQLite 資料**：`db/database.py` 儲存歷史快照（`portfolio_snapshot`）、掛單區間（`order_bands`）、市場事件（`market_events`）。

---

## 架構演進方向

目前雙軌並行：
- **現況**：Streamlit 直接 import `core/` 模組執行
- **目標**：Vue 3 前端 → FastAPI → `core/`（Streamlit 逐步退場）

FastAPI 現有端點：`GET /health`、`GET /api/portfolio`
待補端點（遷移 Vue 需要）：`/api/analysis/advanced`、`/api/summary/daily`、`/api/ticker/{ticker}/historical`、`/api/export/ai`
