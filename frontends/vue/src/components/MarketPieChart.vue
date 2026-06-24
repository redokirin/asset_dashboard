<template>
  <div class="rounded-xl bg-gray-800 p-4">
    <div class="font-semibold text-sm mb-3">市場佔比</div>
    <div ref="chartEl" class="w-full" style="height: 280px" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  marketShare: { type: Object, required: true },
})

const chartEl = ref(null)
let chart = null

function buildOption(data) {
  const EXCLUDE = new Set(['現金', 'daily_pnl'])
  const items = Object.entries(data)
    .filter(([name, value]) => !EXCLUDE.has(name) && typeof value === 'object' && value !== null)
    .map(([name, value]) => ({ name, value: value['佔比'] ?? value['市值'] }))
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {d}%',
    },
    legend: {
      orient: 'horizontal',
      bottom: 0,
      left: 'center',
      textStyle: { color: '#9ca3af', fontSize: 12 },
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '42%'],
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
  chart.setOption(buildOption(props.marketShare))
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  chart?.dispose()
  window.removeEventListener('resize', () => chart?.resize())
})

watch(
  () => props.marketShare,
  (val) => chart?.setOption(buildOption(val)),
  { deep: true }
)
</script>
