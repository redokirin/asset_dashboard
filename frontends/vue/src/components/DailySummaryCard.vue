<template>
  <div class="rounded-xl bg-gray-800 p-4 space-y-3">
    <button
      class="w-full flex items-center justify-between"
      @click="open = !open"
    >
      <span class="text-xs text-gray-400 uppercase tracking-wide">今日行動摘要</span>
      <div class="flex items-center gap-2">
        <span v-if="badgeCount" class="text-xs bg-yellow-500/20 text-yellow-300 rounded-full px-2 py-0.5">
          {{ badgeCount }} 筆訊號
        </span>
        <span class="text-gray-500 text-xs">{{ open ? '▲' : '▼' }}</span>
      </div>
    </button>

    <div v-show="open" class="space-y-3">
      <!-- 可執行訊號 -->
      <div v-if="summary.actionable?.length">
        <div class="text-xs text-gray-500 mb-1">【可執行】</div>
        <div
          v-for="item in summary.actionable"
          :key="item.ticker"
          class="flex items-start gap-2 py-1.5 border-b border-gray-700/50 last:border-0"
        >
          <span class="text-base leading-none mt-0.5">{{ item.emoji }}</span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium">{{ item.ticker }}</span>
              <span class="text-xs text-gray-400">{{ item.name }}</span>
              <span class="text-xs text-gray-500">{{ item.signal }}</span>
            </div>
            <div v-if="item.zone_range" class="text-xs text-gray-400">
              區間 {{ item.zone_range }}
              <span v-if="item.fib_price" class="ml-1 text-gray-500">
                ｜支撐 {{ item.fib_label }} {{ item.fib_price }}
              </span>
            </div>
            <div v-if="item.quality_note" class="text-xs text-yellow-400/80">{{ item.quality_note }}</div>
          </div>
        </div>
      </div>

      <!-- 觀望 -->
      <div v-if="summary.hold_off?.length">
        <div class="text-xs text-gray-500 mb-1">【觀望（量價異常）】</div>
        <div
          v-for="item in summary.hold_off"
          :key="item.ticker"
          class="flex items-center gap-2 py-1 text-sm text-gray-400"
        >
          <span>⏸</span>
          <span class="font-medium text-gray-300">{{ item.ticker }}</span>
          <span class="text-xs">{{ item.quality_note || '量縮上漲，不追' }}</span>
        </div>
      </div>

      <!-- 警示 -->
      <div v-if="summary.warnings?.length">
        <div class="text-xs text-gray-500 mb-1">【須注意】</div>
        <div
          v-for="w in summary.warnings"
          :key="w.ticker"
          class="flex items-start gap-2 py-1 text-xs text-red-300/80"
        >
          <span>⚠️</span>
          <div>
            <span class="font-medium text-red-300">{{ w.ticker }}</span>
            {{ w.reasons?.join('、') }}｜{{ w.advice }}
          </div>
        </div>
      </div>

      <!-- 配置缺口 -->
      <div v-if="summary.region_gaps?.length">
        <div class="text-xs text-gray-500 mb-1">【配置缺口】</div>
        <div
          v-for="g in summary.region_gaps"
          :key="g.region"
          class="flex items-center justify-between text-xs py-0.5"
        >
          <span>{{ g.gap_pct < 0 ? '🔴' : '🟠' }} {{ g.region }}</span>
          <span class="text-gray-400">
            實際 {{ pct(g.current_pct) }} ／ 目標 {{ pct(g.target_pct) }}
            <span :class="g.gap_pct < 0 ? 'text-red-400' : 'text-orange-400'">
              {{ g.gap_pct > 0 ? '+' : '' }}{{ pct(g.gap_pct) }}
            </span>
          </span>
        </div>
      </div>

      <!-- 無訊號 -->
      <div
        v-if="!summary.actionable?.length && !summary.hold_off?.length && !summary.warnings?.length"
        class="text-xs text-gray-500"
      >
        ✅ 今日無須特別行動
      </div>

      <div class="text-xs text-gray-600 text-right">{{ summary.timestamp }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  summary: { type: Object, required: true },
})

const open = ref(true)

const badgeCount = computed(() => {
  return (props.summary.actionable?.length ?? 0) + (props.summary.warnings?.length ?? 0)
})

function pct(v) {
  if (v == null) return '—'
  return `${(v * 100).toFixed(1)}%`
}
</script>
