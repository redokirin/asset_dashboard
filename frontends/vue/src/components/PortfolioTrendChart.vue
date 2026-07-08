<template>
  <div class="rounded-xl bg-gray-800 p-4">
    <div class="flex items-center justify-between mb-3">
      <div class="font-semibold text-sm">📈 資產趨勢</div>
      <div class="flex gap-1">
        <button v-for="r in RANGES" :key="r.key" :class="[
          'text-xs px-2 py-1 rounded-lg transition-colors',
          range === r.key ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-700'
        ]" @click="range = r.key">{{ r.label }}</button>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center text-xs text-gray-500" style="height: 340px">
      載入中…
    </div>
    <div v-else-if="error" class="flex items-center justify-center text-xs text-red-400" style="height: 340px">
      {{ error }}
    </div>
    <div v-else-if="!rows.length" class="flex items-center justify-center text-xs text-gray-500" style="height: 340px">
      尚無歷史快照資料
    </div>
    <div v-else ref="chartEl" class="w-full" style="height: 340px" />
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { fetchPortfolioHistory } from '../api/portfolio.js'

const RANGES = [
  { key: 90, label: '90天' },
  { key: 36500, label: '全部' },
]

const range = ref(90)
const loading = ref(false)
const error = ref('')
const rows = ref([])
const chartEl = ref(null)
let chart = null

// 每日損益變化 = 當日損益 - 前一日損益；第一筆沒有前一日資料，留空不畫
function calcDailyChange(data) {
  return data.map((d, i) => {
    if (i === 0 || d.total_gain == null || data[i - 1].total_gain == null) return null
    return +(d.total_gain - data[i - 1].total_gain).toFixed(2)
  })
}

function buildOption(data) {
  const dates = data.map(d => d.snapshot_date)
  const dailyChange = calcDailyChange(data)
  const upColor = '#ef4444'   // 紅漲（台股慣例）
  const downColor = '#22c55e' // 綠跌

  return {
    backgroundColor: 'transparent',
    animation: false,
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1f2937',
      borderColor: '#374151',
      textStyle: { color: '#d1d5db', fontSize: 12 },
      valueFormatter: (v) => (v == null ? '—' : v.toLocaleString('zh-TW', { maximumFractionDigits: 1 })),
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    legend: {
      data: ['總市值', '投入成本', '報酬率%', '每日損益變化'],
      top: 0,
      textStyle: { color: '#9ca3af', fontSize: 11 },
      itemWidth: 14, itemHeight: 2,
    },
    // 主圖（總市值/投入成本/報酬率%，佔 70%）+ 附圖（每日損益變化長條圖，佔 30%），x 軸對齊共用
    grid: [
      { left: 60, right: 50, top: 34, height: '48%' },
      { left: 60, right: 50, top: '68%', bottom: 30 },
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0,
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { show: false }, axisTick: { show: false },
        splitLine: { show: false } },
      { type: 'category', data: dates, gridIndex: 1,
        axisLine: { lineStyle: { color: '#374151' } },
        axisLabel: { color: '#6b7280', fontSize: 10 },
        splitLine: { show: false } },
    ],
    yAxis: [
      // 左軸下限動態抓資料最小值的 90%，避免總市值/投入成本波動被硬拉到含 0 的滿版壓縮
      { type: 'value', gridIndex: 0, position: 'left', name: 'TWD',
        min: (value) => Math.round(value.min * 0.9),
        nameTextStyle: { color: '#6b7280', fontSize: 10 },
        axisLabel: { color: '#6b7280', fontSize: 10, formatter: (v) => (v / 10000).toFixed(0) + '萬' },
        splitLine: { lineStyle: { color: '#1f2937' } },
        axisLine: { show: false } },
      { type: 'value', gridIndex: 0, position: 'right', name: '%',
        nameTextStyle: { color: '#6b7280', fontSize: 10 },
        axisLabel: { color: '#6b7280', fontSize: 10, formatter: '{value}%' },
        splitLine: { show: false },
        axisLine: { show: false } },
      // 附圖獨立 y 軸：scale:true 讓 echarts 依資料最大最小值自動 padding，不強制含 0
      { type: 'value', gridIndex: 1, scale: true, name: '損益變化',
        nameTextStyle: { color: '#6b7280', fontSize: 10 },
        axisLabel: { color: '#6b7280', fontSize: 10, formatter: (v) => (v / 10000).toFixed(1) + '萬' },
        splitLine: { lineStyle: { color: '#1f2937' } },
        axisLine: { show: false } },
    ],
    series: [
      { name: '總市值', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: data.map(d => d.total_value),
        smooth: true, symbol: 'none', lineStyle: { color: '#60a5fa', width: 2 } },
      { name: '投入成本', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: data.map(d => d.invest_value),
        smooth: true, symbol: 'none', lineStyle: { color: '#a78bfa', width: 1.5 } },
      { name: '報酬率%', type: 'line', xAxisIndex: 0, yAxisIndex: 1, data: data.map(d => d.total_gain_pct),
        smooth: true, symbol: 'none', lineStyle: { color: '#34d399', width: 1.5, type: 'dashed' } },
      { name: '每日損益變化', type: 'bar', xAxisIndex: 1, yAxisIndex: 2, data: dailyChange,
        itemStyle: { color: (p) => (p.value >= 0 ? upColor : downColor) } },
    ],
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await fetchPortfolioHistory(range.value)
  } catch (e) {
    error.value = `載入失敗：${e.message}`
  } finally {
    loading.value = false
  }

  if (chart) { chart.dispose(); chart = null }
  if (!rows.value.length) return

  await nextTick()
  if (!chartEl.value) return
  chart = echarts.init(chartEl.value, 'dark')
  chart.setOption(buildOption(rows.value))
}

function onResize() { chart?.resize() }

watch(range, load)
onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>
