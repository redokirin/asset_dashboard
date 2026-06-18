<template>
  <div class="rounded-xl bg-gray-800 p-4 space-y-3">
    <div class="flex items-center justify-between">
      <span class="text-xs text-gray-400 uppercase tracking-wide">組合風險</span>
      <span class="text-xs" :class="levelColor">{{ risk.risk_level }}</span>
    </div>

    <div class="flex items-end gap-2">
      <span class="text-3xl font-bold" :class="levelColor">{{ risk.risk_score }}</span>
      <span class="text-sm text-gray-500 mb-1">/ 100</span>
    </div>

    <div class="w-full h-2 rounded-full bg-gray-700 overflow-hidden">
      <div
        class="h-full rounded-full transition-all duration-500"
        :class="barColor"
        :style="{ width: `${risk.risk_score}%` }"
      />
    </div>

    <div class="grid grid-cols-3 gap-2 pt-1">
      <div class="text-center">
        <div class="text-xs text-gray-500">投資比例</div>
        <div class="text-sm font-medium">{{ pct(risk.invested_ratio) }}</div>
      </div>
      <div class="text-center">
        <div class="text-xs text-gray-500">現金緩衝</div>
        <div class="text-sm font-medium">{{ pct(risk.cash_buffer_ratio) }}</div>
      </div>
      <div class="text-center">
        <div class="text-xs text-gray-500">高風險佔比</div>
        <div class="text-sm font-medium" :class="risk.high_risk_weight > 0.2 ? 'text-red-400' : ''">
          {{ pct(risk.high_risk_weight) }}
        </div>
      </div>
    </div>

    <div v-if="risk.alerts?.length" class="space-y-1 pt-1 border-t border-gray-700">
      <div
        v-for="(alert, i) in risk.alerts"
        :key="i"
        class="text-xs text-yellow-400"
      >
        {{ alert }}
      </div>
    </div>

    <div class="text-xs text-gray-500">{{ risk.risk_advice }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  risk: { type: Object, required: true },
})

const levelColor = computed(() => {
  const s = props.risk.risk_score ?? 0
  if (s < 20) return 'text-green-400'
  if (s < 35) return 'text-yellow-300'
  if (s < 50) return 'text-orange-400'
  if (s < 65) return 'text-red-400'
  return 'text-red-600'
})

const barColor = computed(() => {
  const s = props.risk.risk_score ?? 0
  if (s < 20) return 'bg-green-400'
  if (s < 35) return 'bg-yellow-300'
  if (s < 50) return 'bg-orange-400'
  if (s < 65) return 'bg-red-400'
  return 'bg-red-600'
})

function pct(v) {
  if (v == null) return '—'
  return `${(v * 100).toFixed(1)}%`
}
</script>
