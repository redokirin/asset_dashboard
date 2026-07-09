<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
      @click.self="$emit('close')"
    >
      <div class="bg-gray-800 rounded-2xl w-full max-w-3xl shadow-2xl overflow-hidden flex flex-col" style="max-height: 88vh">

        <!-- Header -->
        <div class="flex items-center justify-between px-5 py-4 border-b border-gray-700 shrink-0">
          <span class="font-bold">資產配置分析</span>
          <button class="text-gray-400 hover:text-white text-lg leading-none px-1" @click="$emit('close')">✕</button>
        </div>

        <!-- Tab bar -->
        <div class="flex gap-0.5 text-xs border-b border-gray-700/50 px-3 pt-2 shrink-0">
          <button v-for="tab in TABS" :key="tab.key" :class="[
            'px-3 py-1.5 -mb-px rounded-t-lg transition-colors border-b-2',
            activeTab === tab.key
              ? 'border-blue-500 text-white bg-gray-700/30'
              : 'border-transparent text-gray-400 hover:text-white'
          ]" @click="activeTab = tab.key">{{ tab.label }}</button>
        </div>

        <!-- Content -->
        <div class="p-4 overflow-y-auto">

          <!-- ── 市場佔比 ──────────────────────────── -->
          <MarketPieChart v-if="activeTab === 'market'" :marketShare="marketShare" />

          <!-- ── 資產佔比 ──────────────────────────── -->
          <AssetPieChart v-else-if="activeTab === 'asset'" :assets="assets" />

          <!-- ── X-Ray 個股穿透 ────────────────────── -->
          <div v-else-if="activeTab === 'xray'" class="space-y-4">
            <div v-if="xrayLoading" class="text-xs text-gray-500 text-center py-10">穿透分析中，請稍候…</div>
            <div v-else-if="xrayError" class="text-xs text-red-400 text-center py-10">{{ xrayError }}</div>
            <template v-else-if="xrayData">

              <!-- 摘要 -->
              <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400">
                <span>分析標的 <span class="text-gray-200">{{ xrayData.assets_count }}</span> 檔</span>
                <span>已識別 <span class="text-green-400">{{ pct(xrayData.identified_pct) }}</span></span>
                <span>未解析 <span class="text-orange-400">{{ pct(xrayData.unidentified_pct) }}</span></span>
              </div>

              <!-- 個股曝險 -->
              <div>
                <div class="text-xs text-gray-500 mb-1">
                  📦 個股曝險 Top {{ exposuresTop.length }}
                  <span v-if="totalExposures > exposuresTop.length" class="text-gray-600">
                    （共 {{ totalExposures }} 檔已識別）
                  </span>
                </div>
                <div v-if="exposuresTop.length" ref="xrayBarEl" class="w-full"
                  :style="`height: ${xrayBarHeight}px`" />
                <div v-else class="text-xs text-gray-500 py-3 text-center">無個股曝險資料</div>
              </div>

              <!-- 產業配置 -->
              <div>
                <div class="text-xs text-gray-500 mb-1">🏭 產業配置</div>
                <div v-if="sectorList.length" ref="xraySectorEl" class="w-full"
                  :style="`height: ${sectorChartHeight}px`" />
                <div v-else class="text-xs text-gray-500 py-3 text-center">無產業配置資料</div>
              </div>

              <!-- 未解析桶 -->
              <div v-if="bucketsList.length">
                <div class="text-xs text-gray-500 mb-1">❔ 未解析（依地區彙總）</div>
                <div class="space-y-1">
                  <div v-for="b in bucketsList" :key="b.label"
                    class="flex justify-between text-xs bg-gray-700/30 rounded-lg px-3 py-1.5">
                    <span class="text-gray-300">{{ b.label }}</span>
                    <span class="text-gray-400 tabular-nums">{{ pct(b.weight) }}</span>
                  </div>
                </div>
              </div>
            </template>
          </div>

          <!-- ── ETF 比較 ──────────────────────────── -->
          <div v-else-if="activeTab === 'compare'" class="space-y-2">
            <div class="flex items-center justify-between">
              <div class="text-xs text-gray-500">累積漲跌幅比較（以各標的自己第一筆資料為基準 0%）</div>
              <div class="flex gap-1">
                <button v-for="p in COMPARE_PERIODS" :key="p.key" :class="[
                  'text-xs px-2 py-1 rounded-lg transition-colors',
                  comparePeriod === p.key ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-700'
                ]" @click="comparePeriod = p.key">{{ p.label }}</button>
              </div>
            </div>
            <div v-if="compareLoading" class="text-xs text-gray-500 text-center py-10">載入中…</div>
            <div v-else-if="compareError" class="text-xs text-red-400 text-center py-10">{{ compareError }}</div>
            <div v-else ref="compareChartEl" class="w-full" style="height: 320px" />
          </div>

        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import MarketPieChart from './MarketPieChart.vue'
import AssetPieChart from './AssetPieChart.vue'
import { fetchXray, fetchHistorical } from '../api/portfolio.js'
import { buildHorizontalBarOption, buildPieOption, horizontalBarHeight, pieChartHeight } from '../utils/chartOptions.js'

defineProps({
  marketShare: { type: Object, required: true },
  assets: { type: Array, required: true },
})
defineEmits(['close'])

const TABS = [
  { key: 'market', label: '市場佔比' },
  { key: 'asset', label: '資產佔比' },
  { key: 'xray', label: 'X-Ray 個股穿透' },
  { key: 'compare', label: 'ETF 比較' },
]
const activeTab = ref('market')

function pct(v) {
  return typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '—'
}

// ── X-Ray ───────────────────────────────────────────────
const xrayLoading = ref(false)
const xrayError = ref('')
const xrayData = ref(null)
let xrayLoaded = false

const exposuresTop = computed(() => xrayData.value?.exposures?.slice(0, 20) ?? [])
const totalExposures = computed(() => xrayData.value?.exposures?.length ?? 0)
const sectorList = computed(() => xrayData.value?.sector_exposures ?? [])
const bucketsList = computed(() => xrayData.value?.buckets ?? [])
const xrayBarHeight = computed(() => horizontalBarHeight(exposuresTop.value.length))
const sectorChartHeight = computed(() => pieChartHeight(sectorList.value.length))

const xrayBarEl = ref(null)
const xraySectorEl = ref(null)
let xrayBarChart = null
let xraySectorChart = null

function disposeXrayCharts() {
  xrayBarChart?.dispose(); xrayBarChart = null
  xraySectorChart?.dispose(); xraySectorChart = null
}

async function renderXrayCharts() {
  await nextTick()
  disposeXrayCharts()
  if (exposuresTop.value.length && xrayBarEl.value) {
    xrayBarChart = echarts.init(xrayBarEl.value, 'dark')
    xrayBarChart.setOption(buildHorizontalBarOption(exposuresTop.value, {
      getName: e => e.ticker || e.symbol,
      getValue: e => e.weight,
    }))
  }
  if (sectorList.value.length && xraySectorEl.value) {
    xraySectorChart = echarts.init(xraySectorEl.value, 'dark')
    xraySectorChart.setOption(buildPieOption(sectorList.value, {
      getName: s => s.name || s.sector,
      getValue: s => s.weight,
    }))
  }
}

async function loadXray() {
  xrayLoading.value = true
  xrayError.value = ''
  try {
    xrayData.value = await fetchXray()
    xrayLoaded = true
  } catch (e) {
    xrayError.value = `載入失敗：${e.message}`
  } finally {
    xrayLoading.value = false
  }
  await renderXrayCharts()
}

// ── ETF 比較 ────────────────────────────────────────────
const COMPARE_TICKERS = ['0050.TW', '00981A.TW', '00985A.TW', '0052.TW', '^TWII']
const COMPARE_COLORS = ['#60a5fa', '#f59e0b', '#a78bfa', '#f472b6', '#9ca3af']
// 對齊後端 /api/ticker/{ticker}/historical 允許的 period 值，最大只開到 1y
const COMPARE_PERIODS = [
  { key: '1mo', label: '1月' },
  { key: '3mo', label: '3月' },
  { key: '6mo', label: '6月' },
  { key: '1y', label: '1年' },
]

const comparePeriod = ref('1y')
const compareLoading = ref(false)
const compareError = ref('')
const compareDates = ref([])
const compareSeries = ref([]) // [{ ticker, data: [...] }]
let compareLoadedPeriod = null

const compareChartEl = ref(null)
let compareChart = null

function disposeCompareChart() {
  compareChart?.dispose(); compareChart = null
}

function buildCompareOption() {
  return {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f2937', borderColor: '#374151',
      textStyle: { color: '#d1d5db', fontSize: 12 },
      valueFormatter: (v) => (v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`),
    },
    legend: {
      data: compareSeries.value.map(s => s.ticker),
      top: 0,
      textStyle: { color: '#9ca3af', fontSize: 11 },
      itemWidth: 14, itemHeight: 2,
    },
    grid: { left: 50, right: 20, top: 34, bottom: 30 },
    xAxis: {
      type: 'category',
      data: compareDates.value,
      axisLine: { lineStyle: { color: '#374151' } },
      axisLabel: { color: '#6b7280', fontSize: 10 },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#6b7280', fontSize: 10, formatter: '{value}%' },
      splitLine: { lineStyle: { color: '#1f2937' } },
      axisLine: { show: false },
    },
    series: compareSeries.value.map((s, i) => ({
      name: s.ticker,
      type: 'line',
      data: s.data,
      smooth: true,
      symbol: 'none',
      lineStyle: {
        color: COMPARE_COLORS[i % COMPARE_COLORS.length],
        width: s.ticker === '^TWII' ? 2 : 1.5,
        type: s.ticker === '^TWII' ? 'dashed' : 'solid',
      },
    })),
  }
}

async function renderCompareChart() {
  await nextTick()
  disposeCompareChart()
  if (!compareSeries.value.length || !compareChartEl.value) return
  compareChart = echarts.init(compareChartEl.value, 'dark')
  compareChart.setOption(buildCompareOption())
}

async function loadCompare() {
  compareLoading.value = true
  compareError.value = ''
  try {
    const results = await Promise.allSettled(
      COMPARE_TICKERS.map(t => fetchHistorical(t, comparePeriod.value))
    )
    const fetched = []
    results.forEach((r, i) => {
      if (r.status === 'fulfilled' && r.value?.data?.length) {
        fetched.push({ ticker: COMPARE_TICKERS[i], points: r.value.data })
      }
    })
    if (!fetched.length) {
      compareError.value = '無法取得歷史資料'
      return
    }

    // 不同標的上市時間不同（如新發行 ETF 沒有完整一年資料），用日期聯集當共用 x 軸，缺資料補 null
    const dateSet = new Set()
    fetched.forEach(s => s.points.forEach(p => dateSet.add(p.date)))
    const dates = [...dateSet].sort()

    // 每檔各自用自己最早一筆收盤價當基準（rebase 成 0%），才能在同一張圖比較漲跌幅
    compareSeries.value = fetched.map(s => {
      const closeByDate = new Map(s.points.map(p => [p.date, p.close]))
      const base = s.points[0]?.close
      return {
        ticker: s.ticker,
        data: dates.map(d => {
          const c = closeByDate.get(d)
          if (c == null || base == null) return null
          return +(((c / base) - 1) * 100).toFixed(2)
        }),
      }
    })
    compareDates.value = dates
    compareLoadedPeriod = comparePeriod.value
  } catch (e) {
    compareError.value = `載入失敗：${e.message}`
  } finally {
    compareLoading.value = false
  }
  await renderCompareChart()
}

function onResize() {
  xrayBarChart?.resize()
  xraySectorChart?.resize()
  compareChart?.resize()
}

watch(activeTab, (tab) => {
  if (tab !== 'xray') disposeXrayCharts()
  if (tab !== 'compare') disposeCompareChart()

  if (tab === 'xray') {
    if (!xrayLoaded) loadXray()
    else renderXrayCharts()
  } else if (tab === 'compare') {
    if (compareLoadedPeriod !== comparePeriod.value) loadCompare()
    else renderCompareChart()
  }
})

watch(comparePeriod, () => {
  if (activeTab.value === 'compare') loadCompare()
})

window.addEventListener('resize', onResize)
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  disposeXrayCharts()
  disposeCompareChart()
})
</script>
