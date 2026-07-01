# Asset Tracking — CLAUDE.md

個人全球資產追蹤系統，追蹤台股、日股、美股、基金、銀行帳戶的市值與損益。

---

## 目錄架構

```
asset_tracking/
├── api/                        # FastAPI 後端
│   └── main.py                 # 端點：見下方「FastAPI 端點」
│
├── apps/                       # 執行進入點
│   ├── dashboard_st.py         # Streamlit 主程式（仍可用，逐步退場）
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
│   ├── tags.py                 # 決策標籤常數（TAG_* + TAG_DISPLAY）
│   ├── analysis_quant.py       # 量化分析入口（re-export analysis/*）
│   ├── xray.py                 # ETF 持股穿透（analyze_portfolio_exposures、get_ticker_holdings）
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
│       ├── advanced_analysis.py# 量化分析頁（render_advanced_analysis_ui）
│       ├── allocation_analysis.py # 配置分析視圖
│       ├── charts.py           # Plotly 圓餅圖、K 線圖
│       ├── components.py       # 共用 HTML 元件（render_analysis_metrics_row）
│       └── filters.py          # 側邊欄過濾器
│
├── frontends/vue/              # Vue 3 前端（主力 UI，取代 Streamlit）
│   ├── src/
│   │   ├── api/portfolio.js    # axios 呼叫 FastAPI（全端點）
│   │   ├── views/Dashboard.vue # 主儀表板視圖
│   │   ├── components/
│   │   │   ├── SummaryCard.vue         # 總覽卡（市值/成本/損益/報酬）
│   │   │   ├── RiskScoreCard.vue       # 風險評分卡
│   │   │   ├── DailySummaryCard.vue    # 每日行動摘要（可折疊）
│   │   │   ├── AssetTable.vue          # 持倉明細表（展開含成本區塊 + AdvancedAnalysisPanel）
│   │   │   ├── AdvancedAnalysisPanel.vue # 四 tab 量化面板（Decision/Risk/Quant/FA）
│   │   │   ├── ChartModal.vue          # ECharts K 線圖 modal
│   │   │   ├── ExportPanel.vue         # AI 報告下載
│   │   │   ├── MarketPieChart.vue      # 市場配置圓餅圖
│   │   │   ├── AssetPieChart.vue       # 個股配置圓餅圖
│   │   │   └── LiquidityCard.vue       # 流動性分析
│   │   └── utils/colors.js     # 顏色工具
│   ├── vite.config.js
│   └── package.json
│
├── db/
│   ├── database.py             # SQLite CRUD（report_runs, order_bands, portfolio_snapshot, asset_snapshot）
│   └── portfolio.db            # SQLite 資料庫檔案（勿提交）
│
├── tests/                      # pytest 測試（對應 core/ 各模組）
├── scripts/                    # 維護腳本
│   ├── x-ray.py                # 持倉穿透 terminal（呼叫 core/xray.py）
│   ├── holdings.py             # 查詢單一 ETF 前十大持股 terminal
│   ├── update_ohlc_zones.py    # 更新 OHLC 區間資料
│   └── verify_order_bands.py   # 驗證掛單區間
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
    → adv_res（量化指標 DataFrame，tags 存 raw key）
    ↓
api/main.py                              ←→  frontends/vue/（主力 UI）
  /api/portfolio                              Dashboard.vue → SummaryCard, AssetTable
  /api/analysis/advanced  (tags→display)      → AdvancedAnalysisPanel（Decision/Risk/Quant/FA）
  /api/analysis/risk                          → RiskScoreCard
  /api/summary/daily                          → DailySummaryCard
  /api/ticker/{ticker}/historical             → ChartModal（ECharts K 線）
  /api/ticker/{ticker}/fundamental
  /api/export/ai[/{ticker}]                   → ExportPanel
  /api/xray                                   → ETF 持股穿透（依 region 彙總曝險）
  /api/holdings/{ticker}                      → 單一標的前十大持股

core/xray.py → analyze_portfolio_exposures() / get_ticker_holdings()
    ← yfinance funds_data.top_holdings（7 天 file cache：analyze/.xray_holdings_cache.json）
    → scripts/x-ray.py（terminal，on_ticker 進度 callback）
    → scripts/holdings.py（terminal，單一代碼查詢）

apps/dashboard_st.py  ←→  ui/streamlit/*（仍可執行，逐步退場）
```

---

## FastAPI 端點

| 端點 | 快取 | 說明 |
|------|------|------|
| `GET /health` | — | 健康檢查 |
| `GET /api/portfolio` | 600s | 持倉、市值、匯率 |
| `GET /api/analysis/advanced` | 3600s | 量化分析，`tags` 已轉為 display string |
| `GET /api/analysis/risk` | — | 整體風險係數 |
| `GET /api/summary/daily` | — | 每日行動摘要 |
| `GET /api/ticker/{ticker}/historical` | — | 歷史 OHLCV（period: 1mo/3mo/6mo/1y/2y） |
| `GET /api/ticker/{ticker}/fundamental` | — | 基本面資料 |
| `GET /api/export/ai` | — | 整份 AI 報告 |
| `GET /api/export/ai/{ticker}` | — | 單一標的 AI 報告 |
| `GET /api/xray` | 3600s | ETF 持股穿透；buckets 依 region 欄位彙總為「XX其他持股」 |
| `GET /api/holdings/{ticker}` | 1h (memory) | 單一標的前十大持股 |
| `POST /api/analysis/manual` | — | 自選代碼量化分析（傳入 `{"tickers": [...]}` ） |

快取實作：`lru_cache(maxsize=1)`，cache_key = `int(time.time() // TTL)`。  
`/api/holdings/{ticker}` 使用 `lru_cache(maxsize=64)` per ticker。  
`core/xray.py` 另有獨立 file-based cache（`analyze/.xray_holdings_cache.json`，TTL 7 天），terminal 與 API 共享同一份快取。

---

## 命名慣例

### Python

| 類型 | 慣例 | 範例 |
|------|------|------|
| 函式 / 變數 | `snake_case` | `calculate_assets_data`, `df_res` |
| DataFrame 欄位常數 | `COL_` 前綴，定義於 `core/columns.py` | `COL_MARKET_VALUE`, `COL_TICKER` |
| DataFrame 欄位值 | 中文字串（UI 契約，不改） | `"市值"`, `"損益"` |
| Tag 常數 | `TAG_` 前綴，定義於 `core/tags.py` | `TAG_ZONE_DAILY`, `TAG_VP_UP` |
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
- **進階分析欄位**（`run_advanced_analysis` 產出）：`annualizedVol`, `RSI`, `sharpeRatio`, `maxDrawdown`, `COL_TECH_DIAGNOSIS`, `entryZoneStatus`, `tags`
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

### X-Ray 持股穿透

```bash
# 整份持倉穿透（依 region 彙總曝險）
poetry run python scripts/x-ray.py

# 查詢單一 ETF/基金前十大持股
poetry run python scripts/holdings.py VOO
poetry run python scripts/holdings.py 1655.T
poetry run python scripts/holdings.py        # 互動輸入
```

---

## 關鍵設計規則

1. **`core/` 不依賴任何 UI 框架**：Streamlit、Rich、Vue 只在 `ui/` 和 `apps/` 使用。
2. **欄位名稱集中管理**：所有 DataFrame column key 必須在 `core/columns.py` 定義為 `COL_*` 常數，不得在各模組散落硬編碼中文字串。
3. **Tag 兩層分離**：`core/tags.py` 只存 raw ASCII key（`TAG_ZONE_DAILY = "zone_daily"`）。顯示字串（含 emoji）只在 `TAG_DISPLAY` dict 和 API response 轉換層出現。`adv_res["tags"]` 永遠是 raw key list；`entryZoneStatus` 欄位永遠是 display string（供 badge / substring match 使用）。
4. **快取注入模式**：`apps/dashboard_st.py` 透過 `dashboard_logic.FETCHERS` dict 注入帶 `@st.cache_data` 的 fetcher，讓 `core/` 保持無 Streamlit 依賴。
5. **FastAPI 序列化**：`NaN` / `inf` / `Timestamp` 一律在 `api/main.py` 的 `_safe()` 處理；`tags` raw key → display string 在 `/api/analysis/advanced` endpoint 轉換，Vue 端不需特殊處理。
6. **ECharts 初始化順序**：ChartModal 中必須先設 `loading = false`、`await nextTick()` 讓 `ref="chartEl"` 的 div 出現在 DOM，才能呼叫 `echarts.init()`。切換週期前 dispose 舊 chart 避免指向已移除的 DOM 節點。
7. **SQLite 資料**：`db/database.py` 儲存歷史快照（`portfolio_snapshot`、`asset_snapshot`）、掛單區間（`order_bands`）、市場事件（`market_events`）。

---

## Vue 元件職責

| 元件 | 資料來源 | 職責 |
|------|---------|------|
| `Dashboard.vue` | 所有 API | 編排、平行載入（`Promise.allSettled`）、傳 props |
| `SummaryCard.vue` | `/api/portfolio` summary | 總市值 / 成本 / 損益 / 報酬 |
| `RiskScoreCard.vue` | `/api/analysis/risk` | 風險分數、等級、三指標、alerts |
| `DailySummaryCard.vue` | `/api/summary/daily` | 可折疊；actionable / hold_off / warnings / region_gaps |
| `AssetTable.vue` | portfolio assets + advancedMap + dailySummary | 持倉列表；視圖切換（損益/成本）；展開含成本區塊 + AdvancedAnalysisPanel |
| `AdvancedAnalysisPanel.vue` | advancedMap 單列 + dailySummary signals | Decision / Risk / Quant / FA 四 tab，對應 Streamlit `render_advanced_analysis_ui()` |
| `ChartModal.vue` | `/api/ticker/{ticker}/historical` | ECharts K 線 + MA20/60 + 成交量；Teleport to body |
| `ExportPanel.vue` | `/api/export/ai` | 下載整份 `.md` 報告 |

---

## 架構演進方向

雙軌並行，Vue 為主力：
- **現況**：Vue 3 → FastAPI → `core/`（主力 UI，所有端點已接通）
- **Streamlit**：仍可執行（`apps/dashboard_st.py`），功能完整，但不再主動維護
- **已補 Vue 功能**：`ManualAnalysis.vue`（自選代碼量化分析，對應 `show_manual_analysis_page`）
- **待補 Vue 功能**：X-Ray 持股穿透視圖（`/api/xray`、`/api/holdings/{ticker}` 已備妥）、配置分析視圖
