// 共用 ECharts option builder：橫向長條圖 / 圓餅圖
// 給 AdvancedAnalysisPanel（單標的持股/產業）與 AllocationModal（X-Ray 全組合）共用

export function buildHorizontalBarOption(items, { getName, getValue, color = '#60a5fa' } = {}) {
  const sorted = [...items].sort((a, b) => getValue(a) - getValue(b)) // 遞增排序 → 最大值顯示在最上方
  const names  = sorted.map(getName)
  const values = sorted.map(i => +(getValue(i) * 100).toFixed(2))
  return {
    backgroundColor: 'transparent',
    grid: { left: 10, right: 50, top: 10, bottom: 10, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: '#1f2937', borderColor: '#374151',
      textStyle: { color: '#d1d5db', fontSize: 12 },
      formatter: (p) => `${p[0].name}<br/>${p[0].value}%`,
    },
    xAxis: {
      type: 'value',
      axisLabel: { color: '#6b7280', fontSize: 10, formatter: '{value}%' },
      splitLine: { lineStyle: { color: '#1f2937' } },
      axisLine: { lineStyle: { color: '#374151' } },
    },
    yAxis: {
      type: 'category',
      data: names,
      axisLabel: { color: '#9ca3af', fontSize: 11 },
      axisLine: { lineStyle: { color: '#374151' } },
      axisTick: { show: false },
    },
    series: [{
      type: 'bar',
      data: values,
      barMaxWidth: 16,
      itemStyle: { color, borderRadius: [0, 4, 4, 0] },
      label: { show: true, position: 'right', color: '#9ca3af', fontSize: 10, formatter: '{c}%' },
    }],
  }
}

const PIE_HEAD_HEIGHT = 200   // 圓餅本體固定高度
const PIE_LEGEND_ROW_HEIGHT = 22
const PIE_LEGEND_ITEMS_PER_ROW = 4 // 估算每列項目數

export function buildPieOption(items, { getName, getValue } = {}) {
  const data = items.map(i => ({ name: getName(i), value: +(getValue(i) * 100).toFixed(2) }))
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: '{b}: {d}%' },
    legend: {
      orient: 'horizontal',
      bottom: 0,
      left: 'center',
      textStyle: { color: '#9ca3af', fontSize: 11 },
      itemGap: 8,
    },
    series: [{
      type: 'pie',
      radius: ['38%', '65%'],
      center: ['50%', `${PIE_HEAD_HEIGHT / 2}px`],
      data,
      label: { show: false },
      emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.5)' } },
    }],
  }
}

// 圓餅圖 legend 改成自動換行往下排列（比照 AssetPieChart），容器高度需依項目數動態調整
export function pieChartHeight(count) {
  const rows = Math.ceil(count / PIE_LEGEND_ITEMS_PER_ROW)
  return PIE_HEAD_HEIGHT + rows * PIE_LEGEND_ROW_HEIGHT + 16
}

export function horizontalBarHeight(count, { rowHeight = 28, min = 160 } = {}) {
  return Math.max(min, count * rowHeight + 20)
}
