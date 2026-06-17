<template>
  <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
    <div v-for="item in cards" :key="item.label" class="rounded-xl bg-gray-800 p-4">
      <div class="text-xs text-gray-400 mb-1">{{ item.label }}</div>
      <div :class="['text-xl font-bold tabular-nums', item.colorClass]">{{ item.value }}</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { plColor } from '../utils/colors.js'

const props = defineProps({
  summary: { type: Object, required: true },
})

const fmt = (n) =>
  new Intl.NumberFormat('zh-TW', { maximumFractionDigits: 0 }).format(n ?? 0)

const cards = computed(() => {
  const s = props.summary
  const pl = s.total_pl_twd ?? 0
  const retPct = s.return_pct ?? 0

  return [
    { label: '總市值 (TWD)', value: `$${fmt(s.total_value_twd)}`, colorClass: 'text-white' },
    { label: '總成本 (TWD)', value: `$${fmt(s.total_cost_twd)}`, colorClass: 'text-gray-300' },
    { label: '總損益 (TWD)', value: `${pl >= 0 ? '+' : ''}$${fmt(pl)}`, colorClass: plColor(pl) },
    { label: '報酬率', value: `${retPct >= 0 ? '+' : ''}${retPct}%`, colorClass: plColor(retPct) },
  ]
})
</script>
