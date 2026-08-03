<template>
    <div class="rounded-xl bg-gray-800 p-4 space-y-2">
        <div class="flex items-center justify-between">
            <div class="font-semibold text-sm">📊 ETF 比較</div>
            <div class="flex gap-1">
                <button v-for="p in PERIODS" :key="p.key" :class="[
                    'text-xs px-2 py-1 rounded-lg transition-colors',
                    period === p.key ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-700'
                ]" @click="period = p.key">{{ p.label }}</button>
            </div>
        </div>
        <div class="text-xs text-gray-500">累積漲跌幅比較（以各標的自己第一筆資料為基準 0%）</div>

        <div v-if="loading" class="text-xs text-gray-500 text-center py-10">載入中…</div>
        <div v-else-if="error" class="text-xs text-red-400 text-center py-10">{{ error }}</div>
        <div v-else ref="chartEl" class="w-full" style="height: 320px" />
    </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { fetchHistorical } from '../api/portfolio.js'

const TICKERS = ['0050.TW', '00981A.TW', '00985A.TW', '0052.TW', '^TWII', '00878.TW']
const COLORS = ['#60a5fa', '#f59e0b', '#a78bfa', '#f472b6', '#9ca3af', '#02C874']
// 對齊後端 /api/ticker/{ticker}/historical 允許的 period 值，最大只開到 1y
const PERIODS = [
    { key: '1mo', label: '1月' },
    { key: '3mo', label: '3月' },
    { key: '6mo', label: '6月' },
    { key: '1y', label: '1年' },
]

const period = ref('1mo')
const loading = ref(false)
const error = ref('')
const dates = ref([])
const series = ref([]) // [{ ticker, data: [...] }]

const chartEl = ref(null)
let chart = null

function disposeChart() { chart?.dispose(); chart = null }

function buildOption() {
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
            data: series.value.map(s => s.ticker),
            top: 0,
            textStyle: { color: '#9ca3af', fontSize: 11 },
            itemWidth: 14, itemHeight: 2,
        },
        grid: { left: 50, right: 20, top: 34, bottom: 30 },
        xAxis: {
            type: 'category',
            data: dates.value,
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
        series: series.value.map((s, i) => ({
            name: s.ticker,
            type: 'line',
            data: s.data,
            smooth: true,
            symbol: 'none',
            lineStyle: {
                color: COLORS[i % COLORS.length],
                width: s.ticker === '^TWII' ? 2 : 1.5,
                type: s.ticker === '^TWII' ? 'dashed' : 'solid',
            },
        })),
    }
}

async function renderChart() {
    await nextTick()
    disposeChart()
    if (!series.value.length || !chartEl.value) return
    chart = echarts.init(chartEl.value, 'dark')
    chart.setOption(buildOption())
}

async function load() {
    loading.value = true
    error.value = ''
    try {
        const results = await Promise.allSettled(
            TICKERS.map(t => fetchHistorical(t, period.value))
        )
        const fetched = []
        results.forEach((r, i) => {
            if (r.status === 'fulfilled' && r.value?.data?.length) {
                fetched.push({ ticker: TICKERS[i], points: r.value.data })
            }
        })
        if (!fetched.length) {
            error.value = '無法取得歷史資料'
            return
        }

        // 不同標的上市時間不同（如新發行 ETF 沒有完整一年資料），用日期聯集當共用 x 軸，缺資料補 null
        const dateSet = new Set()
        fetched.forEach(s => s.points.forEach(p => dateSet.add(p.date)))
        const allDates = [...dateSet].sort()

        // 每檔各自用自己最早一筆收盤價當基準（rebase 成 0%），才能在同一張圖比較漲跌幅
        series.value = fetched.map(s => {
            const closeByDate = new Map(s.points.map(p => [p.date, p.close]))
            const base = s.points[0]?.close
            return {
                ticker: s.ticker,
                data: allDates.map(d => {
                    const c = closeByDate.get(d)
                    if (c == null || base == null) return null
                    return +(((c / base) - 1) * 100).toFixed(2)
                }),
            }
        })
        dates.value = allDates
    } catch (e) {
        error.value = `載入失敗：${e.message}`
    } finally {
        loading.value = false
    }
    await renderChart()
}

function onResize() { chart?.resize() }

watch(period, load)
onMounted(() => {
    load()
    window.addEventListener('resize', onResize)
})
onUnmounted(() => {
    window.removeEventListener('resize', onResize)
    disposeChart()
})
</script>
