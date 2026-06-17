<template>
  <div class="rounded-xl bg-gray-800 p-4">
    <div class="font-semibold text-sm mb-3">資產佔比</div>
    <div ref="chartEl" class="w-full" style="height: 280px" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  assets: { type: Array, required: true },
})

const chartEl = ref(null)
let chart = null

function buildOption(assets) {
  const items = assets
    .filter(r => r['市場'] !== '現金' && r['enabled'] !== 0 && (r['市值'] ?? 0) > 0)
    .map(r => ({ name: r['名稱'] || r['代碼'], value: r['市值'] }))
    .sort((a, b) => b.value - a.value)

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: (p) => `${p.name}<br/>${p.percent}%`,
    },
    legend: {
      orient: 'vertical',
      right: 10,
      top: 'middle',
      textStyle: { color: '#9ca3af', fontSize: 11 },
      type: 'scroll',
    },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['38%', '50%'],
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
  chart.setOption(buildOption(props.assets))
  window.addEventListener('resize', () => chart?.resize())
})

onUnmounted(() => {
  chart?.dispose()
  window.removeEventListener('resize', () => chart?.resize())
})

watch(
  () => props.assets,
  (val) => chart?.setOption(buildOption(val), true),
  { deep: true }
)
</script>
