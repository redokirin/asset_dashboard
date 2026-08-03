<template>
    <div class="rounded-xl bg-gray-800 p-4 space-y-3">
        <button class="w-full flex items-center justify-between" @click="open = !open">
            <span class="text-xs text-gray-400 uppercase tracking-wide">今日行動摘要</span>
            <div class="flex items-center gap-2">
                <span v-if="badgeCount" class="text-xs bg-yellow-500/20 text-yellow-300 rounded-full px-2 py-0.5">
                    {{ badgeCount }} 筆訊號
                </span>
                <span class="text-gray-500 text-xs">{{ open ? '▲' : '▼' }}</span>
            </div>
        </button>

        <div v-show="open" class="space-y-3">
            <!-- 可執行訊號／觀望／警示：依 ticker 合併顯示 -->
            <div v-if="merged.length">
                <div v-for="item in merged" :key="item.ticker"
                    class="flex items-start gap-2 py-1.5 border-b border-gray-700/50 last:border-0">
                    <span class="text-base leading-none mt-0.5">
                        {{ item.actionable ? item.actionable.emoji : (item.holdOff ? '⏸' : '⚠️') }}
                    </span>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2">
                            <span class="text-sm font-medium">{{ item.ticker }}</span>
                            <span class="text-xs text-gray-400">{{ item.name }}</span>
                            <span v-if="item.actionable" class="text-xs text-gray-500">{{ item.actionable.signal
                            }}</span>
                            <span v-else-if="item.holdOff" class="text-xs text-gray-500">觀望</span>
                        </div>
                        <div v-if="item.actionable?.zone_range" class="text-xs text-gray-400">
                            區間 {{ item.actionable.zone_range }}
                            <span v-if="item.actionable.fib_price" class="ml-1 text-gray-500">
                                ｜支撐 {{ item.actionable.fib_label }} {{ item.actionable.fib_price }}
                            </span>
                        </div>
                        <div v-if="item.actionable?.quality_note" class="text-xs text-yellow-400/80">
                            {{ item.actionable.quality_note }}
                        </div>
                        <div v-if="item.holdOff" class="text-xs text-gray-400">
                            {{ item.holdOff.quality_note || '量縮上漲，不追' }}
                        </div>
                        <div v-if="item.warning" class="text-xs text-red-300/80">
                            ⚠️ {{ item.warning.reasons?.join('、') }}｜{{ item.warning.advice }}
                        </div>
                    </div>
                </div>
            </div>

            <!-- 配置缺口 -->
            <div v-if="summary.region_gaps?.length">
                <div class="text-xs text-gray-500 mb-1">【配置缺口】</div>
                <div v-for="g in summary.region_gaps" :key="g.region"
                    class="flex items-center justify-between text-xs py-0.5">
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
            <div v-if="!merged.length" class="text-xs text-gray-500">
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

// 依 ticker 合併可執行訊號／觀望／警示；一檔標的可能同時有訊號 + 警示（例如可執行但 Pain Ratio 偏高）
const merged = computed(() => {
    const map = new Map()
    const entry = (ticker, name) => {
        if (!map.has(ticker)) map.set(ticker, { ticker, name, actionable: null, holdOff: null, warning: null })
        return map.get(ticker)
    }
    for (const item of props.summary.actionable ?? []) {
        entry(item.ticker, item.name).actionable = item
    }
    for (const item of props.summary.hold_off ?? []) {
        entry(item.ticker, item.name).holdOff = item
    }
    for (const item of props.summary.warnings ?? []) {
        entry(item.ticker, item.name).warning = item
    }
    return Array.from(map.values())
})

function pct(v) {
    if (v == null) return '—'
    return `${(v * 100).toFixed(1)}%`
}
</script>
