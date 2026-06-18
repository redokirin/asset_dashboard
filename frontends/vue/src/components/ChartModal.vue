<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
      @click.self="$emit('close')"
    >
      <div class="bg-gray-800 rounded-2xl w-full max-w-3xl shadow-2xl overflow-hidden">

        <!-- Header -->
        <div class="flex items-center justify-between px-5 py-4 border-b border-gray-700">
          <div>
            <span class="font-bold">{{ ticker }}</span>
            <span class="ml-2 text-sm text-gray-400">{{ name }}</span>
          </div>
          <div class="flex items-center gap-3">
            <!-- 週期選擇 -->
            <div class="flex gap-1">
              <button
                v-for="p in PERIODS"
                :key="p"
                :class="[
                  'text-xs px-2.5 py-1 rounded-lg transition-colors',
                  period === p ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-700'
                ]"
                @click="period = p"
              >{{ p }}</button>
            </div>
            <button
              class="text-gray-400 hover:text-white text-lg leading-none px-1"
              @click="$emit('close')"
            >✕</button>
          </div>
        </div>

        <!-- Chart area -->
        <div class="p-4">
          <div v-if="loading" class="flex items-center justify-center" style="height: 380px">
            <span class="text-gray-500 text-sm">載入中…</span>
          </div>
          <div v-else-if="error" class="flex items-center justify-center" style="height: 380px">
            <span class="text-red-400 text-sm">{{ error }}</span>
          </div>
          <div v-else ref="chartEl" style="height: 380px; width: 100%" />
        </div>

        <!-- 統計列 -->
        <div v-if="stats" class="grid grid-cols-4 gap-px bg-gray-700 border-t border-gray-700">
          <div v-for="s in stats" :key="s.label" class="bg-gray-800 px-4 py-2.5 text-center">
            <div class="text-xs text-gray-500">{{ s.label }}</div>
            <div class="text-sm font-medium mt-0.5" :class="s.color ?? ''">{{ s.value }}</div>
          </div>
        </div>

      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, onUnmounted, computed, nextTick } from 'vue'
import * as echarts from 'echarts'
import { fetchHistorical } from '../api/portfolio.js'

const props = defineProps({
  ticker: { type: String, required: true },
  name:   { type: String, default: '' },
})
defineEmits(['close'])

const PERIODS = ['1mo', '3mo', '6mo', '1y', '2y']

const period  = ref('6mo')
const loading = ref(false)
const error   = ref('')
const rawData = ref([])
const chartEl = ref(null)
let chart = null

// --- 移動平均 ---
function calcMA(data, n) {
  return data.map((_, i) => {
    if (i < n - 1) return null
    const avg = data.slice(i - n + 1, i + 1).reduce((s, d) => s + d.close, 0) / n
    return +avg.toFixed(4)
  })
}

// --- ECharts option ---
function buildOption(data) {
  const dates   = data.map(d => d.date)
  const candles = data.map(d => [d.open, d.close, d.low, d.high])
  const volumes = data.map(d => d.volume ?? 0)
  const ma20    = calcMA(data, 20)
  const ma60    = calcMA(data, 60)

  const upColor   = '#ef4444'   // 紅漲（台股慣例）
  const downColor = '#22c55e'   // 綠跌

  return {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#d1d5db', fontSize: 12 },
      formatter(params) {
        const c = params.find(p => p.seriesType === 'candlestick')
        if (!c) return ''
        const [o, cl, l, h] = c.value
        const vol = volumes[c.dataIndex]
        const pct = o > 0 ? (((cl - o) / o) * 100).toFixed(2) : '—'
        const clr = cl >= o ? upColor : downColor
        return `
          <div style="font-size:11px">
            <b>${c.axisValue}</b><br/>
            開 ${o.toFixed(2)}　高 ${h.toFixed(2)}<br/>
            低 ${l.toFixed(2)}　收 <span style="color:${clr}">${cl.toFixed(2)}</span>
            (${pct >= 0 ? '+' : ''}${pct}%)<br/>
            量 ${vol.toLocaleString()}
          </div>`
      },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], bottom: 8, height: 20,
        borderColor: '#374151', textStyle: { color: '#6b7280' },
        handleStyle: { color: '#4b5563' } },
    ],
    grid: [
      { left: 60, right: 16, top: 12, bottom: 72 },
      { left: 60, right: 16, top: '76%', bottom: 40 },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0,
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#6b7280', fontSize: 10 },
        splitLine: { show: false }, axisTick: { show: false } },
      { type: 'category', data: dates, gridIndex: 1,
        axisLabel: { show: false }, axisTick: { show: false },
        axisLine: { lineStyle: { color: '#374151' } }, splitLine: { show: false } },
    ],
    yAxis: [
      { scale: true, gridIndex: 0, splitNumber: 4,
        axisLabel: { color: '#6b7280', fontSize: 10 },
        splitLine: { lineStyle: { color: '#1f2937' } },
        axisLine: { lineStyle: { color: '#374151' } } },
      { scale: true, gridIndex: 1, splitNumber: 2,
        axisLabel: { show: false }, splitLine: { show: false },
        axisLine: { lineStyle: { color: '#374151' } } },
    ],
    series: [
      { name: 'K線', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
        data: candles,
        itemStyle: {
          color: upColor, color0: downColor,
          borderColor: upColor, borderColor0: downColor,
        } },
      { name: 'MA20', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: ma20, smooth: true, symbol: 'none',
        lineStyle: { color: '#fbbf24', width: 1.5 },
        tooltip: { valueFormatter: v => v?.toFixed(2) ?? '—' } },
      { name: 'MA60', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
        data: ma60, smooth: true, symbol: 'none',
        lineStyle: { color: '#60a5fa', width: 1.5 },
        tooltip: { valueFormatter: v => v?.toFixed(2) ?? '—' } },
      { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: volumes,
        itemStyle: {
          color: (params) => {
            const d = data[params.dataIndex]
            return d.close >= d.open ? upColor + '99' : downColor + '99'
          },
        } },
    ],
    legend: {
      data: ['MA20', 'MA60'],
      top: 0, right: 16,
      textStyle: { color: '#9ca3af', fontSize: 11 },
      itemWidth: 16, itemHeight: 2,
    },
  }
}

// --- 統計摘要 ---
const stats = computed(() => {
  if (!rawData.value.length) return null
  const data = rawData.value
  const last  = data[data.length - 1]
  const first = data[0]
  const highs = data.map(d => d.high)
  const lows  = data.map(d => d.low)
  const periodHigh = Math.max(...highs)
  const periodLow  = Math.min(...lows)
  const chg = first.close > 0 ? ((last.close - first.close) / first.close * 100).toFixed(2) : null

  return [
    { label: '最新收盤', value: last.close.toFixed(2) },
    { label: '期間漲跌', value: chg != null ? `${chg >= 0 ? '+' : ''}${chg}%` : '—',
      color: chg != null ? (chg >= 0 ? 'text-red-400' : 'text-green-400') : '' },
    { label: '期間高點', value: periodHigh.toFixed(2) },
    { label: '期間低點', value: periodLow.toFixed(2) },
  ]
})

// --- 資料載入 ---
async function loadChart() {
  // 每次重新載入前先清掉舊 chart，避免指向已移除的 DOM 節點
  if (chart) {
    chart.dispose()
    chart = null
    window.removeEventListener('resize', onResize)
  }

  loading.value = true
  error.value   = ''
  rawData.value = []
  try {
    const res = await fetchHistorical(props.ticker, period.value)
    rawData.value = res.data ?? []
    if (!rawData.value.length) { error.value = '無歷史資料'; return }

    // 先關掉 loading，讓 v-else 的 chartEl div 出現在 DOM 後再 init
    loading.value = false
    await nextTick()

    if (!chartEl.value) { error.value = '圖表容器未就緒'; return }

    chart = echarts.init(chartEl.value, 'dark')
    window.addEventListener('resize', onResize)
    chart.setOption(buildOption(rawData.value), true)
  } catch (e) {
    error.value = `載入失敗：${e.message}`
  } finally {
    loading.value = false
  }
}

function onResize() { chart?.resize() }

watch(() => props.ticker, loadChart, { immediate: true })
watch(period, loadChart)

onUnmounted(() => {
  chart?.dispose()
  chart = null
  window.removeEventListener('resize', onResize)
})
</script>
