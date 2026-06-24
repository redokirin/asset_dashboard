<template>
  <div class="space-y-2">
    <div class="flex items-center justify-between px-1">
      <span class="font-semibold text-sm">持倉明細</span>
      <div class="flex items-center gap-2 text-xs text-gray-400">
        <!-- 視圖切換 tag -->
        <div class="flex gap-1 pr-2 border-r border-gray-700/60">
          <button
            v-for="view in VIEW_OPTS"
            :key="view.key"
            :class="['px-2 py-0.5 rounded transition-colors', viewMode === view.key ? 'bg-blue-600/50 text-blue-300' : 'hover:text-white']"
            @click="viewMode = view.key"
          >{{ view.label }}</button>
        </div>
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
      class="rounded-xl bg-gray-800 border border-gray-700/50 overflow-hidden"
    >
      <!-- 主列（點擊展開） -->
      <div
        class="px-4 py-3 cursor-pointer hover:bg-gray-750 transition-colors"
        @click="toggleExpand(row['代碼'])"
      >
        <div class="flex flex-wrap sm:flex-nowrap sm:items-center items-start gap-x-3 gap-y-1.5">
          <!-- 左：meta + 名稱（手機佔滿整行，桌機 flex-1） -->
          <div class="w-full sm:flex-1 sm:w-auto min-w-0">
            <div class="text-xs text-gray-400 leading-tight">
              {{ row['市場'] }} |
              <button
                class="font-mono hover:text-blue-400 hover:underline transition-colors"
                @click.stop="emit('open-chart', { ticker: row['代碼'], name: row['名稱'] })"
              >{{ row['代碼'] }}</button>
              <span class="ml-1">({{ fmtPct1(row['佔比']) }}%)</span>
              <span v-if="row['更新時間']" class="ml-2">⏳ {{ row['更新時間'] }}</span>
            </div>
            <div class="flex items-center gap-2 mt-0.5">
              <span class="font-semibold text-sm truncate">{{ row['名稱'] }}</span>
              <span
                v-if="adv(row)?.entryZoneStatus && adv(row).entryZoneStatus !== '-'"
                class="text-xs shrink-0"
              >{{ adv(row).entryZoneStatus }}</span>
            </div>
          </div>

          <!-- 中右 + 箭頭：手機靠右下，桌機接在名稱後 -->
          <div class="flex items-center gap-3 ml-auto sm:ml-0 shrink-0">
            <!-- 中：現價 / 漲跌 -->
            <div class="text-right">
              <div class="text-xs text-gray-400">現價 / 漲跌</div>
              <div class="flex items-center gap-1.5 justify-end mt-0.5">
                <span class="text-sm font-medium tabular-nums">{{ fmtPrice(row['股價']) }}</span>
                <span :class="['text-xs px-1.5 py-0.5 rounded tabular-nums', tagClass(row['漲跌'])]">
                  {{ fmtChange(row['漲跌']) }}
                </span>
              </div>
            </div>

            <!-- 右：損益/報酬 或 成本/均價（依視圖切換） -->
            <div class="text-right">
              <template v-if="viewMode === 'pl'">
                <div class="text-xs text-gray-400">損益 / 報酬</div>
                <div class="flex items-center gap-1.5 justify-end mt-0.5">
                  <span class="text-sm font-medium tabular-nums">{{ fmtPl(row['損益']) }}</span>
                  <span :class="['text-xs px-1.5 py-0.5 rounded tabular-nums', tagClass(row['報酬率'])]">
                    {{ fmtRoi(row['報酬率']) }}
                  </span>
                </div>
              </template>
              <template v-else>
                <div class="text-xs text-gray-400">成本 / 均價</div>
                <div class="flex items-center gap-1.5 justify-end mt-0.5">
                  <span class="text-sm font-medium tabular-nums">{{ fmtCost(row['成本']) }}</span>
                  <span class="text-xs px-1.5 py-0.5 rounded tabular-nums bg-gray-700 text-gray-300">
                    {{ fmtPrice(row['平均成本']) }}
                  </span>
                </div>
              </template>
            </div>

            <!-- 展開箭頭 -->
            <div class="flex items-center text-gray-600">
              <span class="text-xs">{{ expanded.has(row['代碼']) ? '▲' : '▼' }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 展開面板 -->
      <div
        v-if="expanded.has(row['代碼'])"
        class="border-t border-gray-700/50 bg-gray-850"
      >
        <!-- 成本區塊（永遠顯示） -->
        <div class="px-4 py-3 grid grid-cols-4 gap-2 border-b border-gray-700/40">
          <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
            <div class="text-sm font-medium tabular-nums">{{ fmtUnits(row['單位數']) }}</div>
            <div class="text-xs text-gray-500 mt-0.5">持股數</div>
          </div>
          <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
            <div class="text-sm font-medium tabular-nums">{{ fmtCost(row['成本']) }}</div>
            <div class="text-xs text-gray-500 mt-0.5">成本</div>
          </div>
          <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
            <div class="text-sm font-medium tabular-nums">{{ fmtPrice(row['平均成本']) }}</div>
            <div class="text-xs text-gray-500 mt-0.5">均價</div>
          </div>
          <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
            <div class="text-sm font-medium tabular-nums">{{ fmtCost(row['市值']) }}</div>
            <div class="text-xs text-gray-500 mt-0.5">市值</div>
          </div>
        </div>

        <!-- 四 tab 量化面板 -->
        <div v-if="adv(row)" class="px-4 py-3">
          <AdvancedAnalysisPanel
            :res="adv(row)"
            :actionable="signalFor(row['代碼']).actionable"
            :warning="signalFor(row['代碼']).warning"
            :holdOff="signalFor(row['代碼']).holdOff"
          />
        </div>
        <div v-else class="px-4 pb-3 text-xs text-gray-500">
          量化資料載入中或不適用此標的
        </div>

        <!-- AI 報告複製按鈕 -->
        <div v-if="adv(row)" class="px-4 pb-3 flex justify-end">
          <button
            class="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg bg-gray-700 hover:bg-gray-600 disabled:opacity-50 transition-colors text-gray-300"
            :disabled="copyingMap[row['代碼']] === 'loading'"
            @click.stop="copyTickerReport(row['代碼'])"
          >
            <span v-if="copyingMap[row['代碼']] === 'loading'">產生中…</span>
            <span v-else-if="copyingMap[row['代碼']] === 'done'" class="text-green-400">✅ 已複製</span>
            <span v-else-if="copyingMap[row['代碼']] === 'error'" class="text-red-400">❌ 失敗</span>
            <span v-else>📋 複製 AI 報告</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import AdvancedAnalysisPanel from './AdvancedAnalysisPanel.vue'
import { fetchExportAiTicker } from '../api/portfolio.js'

const emit = defineEmits(['open-chart'])

const CASH_MARKETS = new Set(['bank', 'cash', '現金'])
const VIEW_OPTS = [
  { key: 'pl',   label: '損益' },
  { key: 'cost', label: '成本' },
]
const SORT_OPTS = [
  { key: '市值', label: '市值' },
  { key: '報酬率', label: '報酬率' },
  { key: '損益', label: '損益' },
]

const props = defineProps({
  assets:       { type: Array,  required: true },
  advancedMap:  { type: Object, default: () => ({}) },
  dailySummary: { type: Object, default: null },
})

const viewMode   = ref('pl')
const sortKey    = ref('市值')
const sortAsc    = ref(false)
const expanded   = ref(new Set())
const copyingMap = ref({})

function toggleSort(key) {
  if (sortKey.value === key) sortAsc.value = !sortAsc.value
  else { sortKey.value = key; sortAsc.value = false }
}

function toggleExpand(ticker) {
  const s = new Set(expanded.value)
  s.has(ticker) ? s.delete(ticker) : s.add(ticker)
  expanded.value = s
}

function adv(row) {
  return props.advancedMap[row['代碼']] ?? null
}

function signalFor(ticker) {
  const ds = props.dailySummary
  if (!ds) return { actionable: null, warning: null, holdOff: null }
  return {
    actionable: ds.actionable?.find(a => a.ticker === ticker) ?? null,
    warning:    ds.warnings?.find(w => w.ticker === ticker) ?? null,
    holdOff:    ds.hold_off?.find(h => h.ticker === ticker) ?? null,
  }
}

async function copyTickerReport(ticker) {
  copyingMap.value = { ...copyingMap.value, [ticker]: 'loading' }
  try {
    const { report } = await fetchExportAiTicker(ticker)
    await navigator.clipboard.writeText(report)
    copyingMap.value = { ...copyingMap.value, [ticker]: 'done' }
    setTimeout(() => { copyingMap.value = { ...copyingMap.value, [ticker]: 'idle' } }, 2000)
  } catch {
    copyingMap.value = { ...copyingMap.value, [ticker]: 'error' }
    setTimeout(() => { copyingMap.value = { ...copyingMap.value, [ticker]: 'idle' } }, 2000)
  }
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

function tagClass(n) {
  if (n == null || n === '-') return 'bg-gray-700 text-gray-300'
  const v = typeof n === 'string' ? parseFloat(n) : n
  if (v > 0) return 'bg-red-900/60 text-red-300'
  if (v < 0) return 'bg-green-900/60 text-green-300'
  return 'bg-gray-700 text-gray-300'
}

const intFmt   = new Intl.NumberFormat('zh-TW', { maximumFractionDigits: 0 })
const priceFmt = new Intl.NumberFormat('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fmtUnits  = (n) => n == null ? '—' : new Intl.NumberFormat('zh-TW', { maximumFractionDigits: 4 }).format(n)
const fmtPrice  = (n) => n == null ? '—' : priceFmt.format(n)
const fmtCost   = (n) => n == null ? '—' : intFmt.format(n)
const fmtChange = (n) => {
  if (n == null || n === '-') return '—'
  const v = typeof n === 'string' ? parseFloat(n) : n
  return isNaN(v) ? String(n) : `${v >= 0 ? '+' : ''}${v.toFixed(2)}`
}
const fmtPl   = (n) => n == null ? '—' : `${n >= 0 ? '+' : ''}${intFmt.format(n)}`
const fmtRoi  = (n) => n == null ? '—' : `${n >= 0 ? '+' : ''}${Number(n).toFixed(2)}%`
const fmtPct1 = (n) => n == null ? '0.0' : Number(n).toFixed(1)
</script>
