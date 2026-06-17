<template>
  <div class="space-y-2">
    <div class="flex items-center justify-between px-1">
      <span class="font-semibold text-sm">持倉明細</span>
      <div class="flex items-center gap-2 text-xs text-gray-400">
        <span>排序：</span>
        <button
          v-for="opt in SORT_OPTS"
          :key="opt.key"
          :class="['px-2 py-0.5 rounded', sortKey === opt.key ? 'bg-gray-600 text-white' : 'hover:text-white']"
          @click="toggleSort(opt.key)"
        >
          {{ opt.label }}{{ sortKey === opt.key ? (sortAsc ? ' ▲' : ' ▼') : '' }}
        </button>
        <span class="ml-1 text-gray-500">{{ sorted.length }} 筆</span>
      </div>
    </div>

    <div
      v-for="row in sorted"
      :key="row['代碼']"
      class="rounded-xl bg-gray-800 border border-gray-700/50 px-4 py-3 grid gap-x-3"
      style="grid-template-columns: 1fr auto auto"
    >
      <!-- 左：meta + 名稱 -->
      <div class="min-w-0">
        <div class="text-xs text-gray-400 leading-tight">
          {{ row['市場'] }} | {{ row['代碼'] }}
          <span class="ml-1">({{ fmtPct1(row['佔比']) }}%)</span>
          <span v-if="row['更新時間']" class="ml-2">⏳ {{ row['更新時間'] }}</span>
        </div>
        <div class="font-semibold text-sm mt-0.5 truncate">{{ row['名稱'] }}</div>
      </div>

      <!-- 中：現價 / 漲跌 -->
      <div class="text-right shrink-0">
        <div class="text-xs text-gray-400">現價 / 漲跌</div>
        <div class="flex items-center gap-1.5 justify-end mt-0.5">
          <span class="text-sm font-medium tabular-nums">{{ fmtPrice(row['股價']) }}</span>
          <span :class="['text-xs px-1.5 py-0.5 rounded tabular-nums', tagClass(row['漲跌'])]">
            {{ fmtChange(row['漲跌']) }}
          </span>
        </div>
      </div>

      <!-- 右：損益 / 報酬 -->
      <div class="text-right shrink-0">
        <div class="text-xs text-gray-400">損益 / 報酬</div>
        <div class="flex items-center gap-1.5 justify-end mt-0.5">
          <span class="text-sm font-medium tabular-nums">{{ fmtPl(row['損益']) }}</span>
          <span :class="['text-xs px-1.5 py-0.5 rounded tabular-nums', tagClass(row['報酬率'])]">
            {{ fmtRoi(row['報酬率']) }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const CASH_MARKETS = new Set(['bank', 'cash', '現金'])
const SORT_OPTS = [
  { key: '市值', label: '市值' },
  { key: '報酬率', label: '報酬率' },
  { key: '損益', label: '損益' },
]

const props = defineProps({
  assets: { type: Array, required: true },
})

const sortKey = ref('市值')
const sortAsc = ref(false)

function toggleSort(key) {
  if (sortKey.value === key) sortAsc.value = !sortAsc.value
  else { sortKey.value = key; sortAsc.value = false }
}

const sorted = computed(() => {
  const arr = props.assets.filter(r =>
    !CASH_MARKETS.has((r['市場'] ?? '').toLowerCase()) && r['enabled'] !== 0
  )
  arr.sort((a, b) => {
    const av = a[sortKey.value] ?? 0
    const bv = b[sortKey.value] ?? 0
    return sortAsc.value ? av - bv : bv - av
  })
  return arr
})

// 紅漲綠跌（台股慣例）
function tagClass(n) {
  if (n == null || n === '-') return 'bg-gray-700 text-gray-300'
  const v = typeof n === 'string' ? parseFloat(n) : n
  if (v > 0) return 'bg-red-900/60 text-red-300'
  if (v < 0) return 'bg-green-900/60 text-green-300'
  return 'bg-gray-700 text-gray-300'
}

const intFmt = new Intl.NumberFormat('zh-TW', { maximumFractionDigits: 0 })
const fmtPrice  = (n) => n == null ? '—' : new Intl.NumberFormat('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n)
const fmtChange = (n) => {
  if (n == null || n === '-') return '—'
  const v = typeof n === 'string' ? parseFloat(n) : n
  return isNaN(v) ? String(n) : `${v >= 0 ? '+' : ''}${v.toFixed(2)}`
}
const fmtPl     = (n) => n == null ? '—' : `${n >= 0 ? '+' : ''}${intFmt.format(n)}`
const fmtRoi    = (n) => n == null ? '—' : `${n >= 0 ? '+' : ''}${Number(n).toFixed(2)}%`
const fmtPct1   = (n) => n == null ? '0.0' : Number(n).toFixed(1)
</script>
