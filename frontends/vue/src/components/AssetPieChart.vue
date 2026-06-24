<template>
  <div class="rounded-xl bg-gray-800 p-4">
    <div class="font-semibold text-sm mb-3">資產佔比</div>
    <div ref="chartEl" class="w-full" :style="`height: ${chartHeight}px`" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  assets: { type: Array, required: true },
})

const chartEl = ref(null)
let chart = null

const PIE_HEIGHT = 220  // 圓餅固定高度
const ROW_HEIGHT = 22   // 每列圖例高度
const ITEMS_PER_ROW = 4 // 估算每列項目數

const filteredItems = computed(() =>
  props.assets
    .filter(r => r['市場'] !== '現金' && r['enabled'] !== 0 && (r['市值'] ?? 0) > 0)
    .map(r => ({ name: r['名稱'] || r['代碼'], value: r['市值'] }))
    .sort((a, b) => b.value - a.value)
)

const chartHeight = computed(() => {
  const rows = Math.ceil(filteredItems.value.length / ITEMS_PER_ROW)
  return PIE_HEIGHT + rows * ROW_HEIGHT + 16
})

function buildOption(items) {
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: (p) => `${p.name}<br/>${p.percent}%`,
    },
    legend: {
      orient: 'horizontal',
      bottom: 0,
      left: 'center',
      textStyle: { color: '#9ca3af', fontSize: 11 },
      itemGap: 8,
    },
    series: [
      {
        type: 'pie',
        radius: ['38%', '65%'],
        center: ['50%', `${PIE_HEIGHT / 2}px`],
        data: items,
        label: { show: false },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' },
        },
      },
    ],
  }
}

onMounted(() => {
  chart = echarts.init(chartEl.value, 'dark')
  chart.setOption(buildOption(filteredItems.value))
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  chart?.dispose()
  window.removeEventListener('resize', () => chart?.resize())
})

watch(filteredItems, (items) => {
  if (!chart) return
  chart.setOption(buildOption(items), true)
  chart.resize()
}, { deep: true })
</script>
