<template>
    <div class="space-y-2">
        <!-- Tab bar -->
        <div class="flex gap-0.5 text-xs border-b border-gray-700/50">
            <button v-for="tab in TABS" :key="tab.key" :class="[
                'px-3 py-1.5 -mb-px rounded-t-lg transition-colors border-b-2',
                activeTab === tab.key
                    ? 'border-blue-500 text-white bg-gray-700/30'
                    : 'border-transparent text-gray-400 hover:text-white'
            ]" @click="activeTab = tab.key">{{ tab.label }}</button>
        </div>

        <!-- ── Decision ──────────────────────────────────── -->
        <div v-if="activeTab === 'decision'" class="space-y-2.5">

            <!-- Price zone bar（有三個邊界值才顯示） -->
            <template v-if="hasZoneBar">
                <div class="space-y-0.5">
                    <div class="relative h-4 text-[10px] text-gray-400">
                        <span class="absolute" :style="`left:25%;transform:translateX(-50%)`">{{ fmt2(r.dailyUpper)
                            }}</span>
                        <span class="absolute" :style="`left:50%;transform:translateX(-50%)`">{{
                            fmt2(r.boundaryDailyRetest) }}</span>
                        <span class="absolute" :style="`left:75%;transform:translateX(-50%)`">{{
                            fmt2(r.boundaryRetestSniper) }}</span>
                    </div>
                    <div class="flex rounded overflow-hidden" style="height:12px">
                        <div class="w-1/4 bg-red-500/80" title="追價警戒"></div>
                        <div class="w-1/4 bg-orange-500/80" title="日常波段"></div>
                        <div class="w-1/4 bg-green-500/80" title="技術回測"></div>
                        <div class="w-1/4 bg-green-300/60" title="狙擊位"></div>
                    </div>
                    <div class="relative h-5 text-xs text-white">
                        <span class="absolute whitespace-nowrap"
                            :style="`left:${pricePct}%;transform:translateX(-50%)`">▲ {{ r['股價'] }}</span>
                    </div>
                </div>
            </template>

            <!-- 無 zone bar → 掛單三格 -->
            <div v-else class="grid grid-cols-3 gap-2">
                <div class="rounded-lg bg-yellow-900/20 border border-yellow-700/30 px-3 py-2 text-center">
                    <div class="text-xs text-yellow-600">🟡 日常波段</div>
                    <div class="text-sm font-medium tabular-nums">{{ r['日常波段'] ?? '—' }}</div>
                </div>
                <div class="rounded-lg bg-green-900/20 border border-green-700/30 px-3 py-2 text-center">
                    <div class="text-xs text-green-600">🟢 技術回測</div>
                    <div class="text-sm font-medium tabular-nums">{{ r['技術回測'] ?? '—' }}</div>
                </div>
                <div class="rounded-lg bg-purple-900/20 border border-purple-700/30 px-3 py-2 text-center">
                    <div class="text-xs text-purple-400">⭐ 狙擊位</div>
                    <div class="text-sm font-medium tabular-nums">{{ r['狙擊位'] ?? '—' }}</div>
                </div>
            </div>

            <!-- Tags -->
            <div v-if="r.tags?.length" class="flex flex-wrap gap-1.5">
                <span v-for="tag in r.tags" :key="tag"
                    class="text-xs px-2 py-0.5 rounded-full bg-blue-900/40 border border-blue-700/40 text-blue-300">{{
                        tag }}</span>
            </div>

            <!-- 技術診斷 -->
            <div v-if="r['技術診斷']" class="text-xs text-gray-300 bg-gray-700/30 rounded-lg px-3 py-2 leading-relaxed">{{
                r['技術診斷'] }}
            </div>

            <!-- 可執行訊號 -->
            <div v-if="actionable" class="text-xs text-gray-400 flex flex-wrap gap-2">
                <span v-if="actionable.fib_price != null">
                    最近支撐 <span class="text-gray-200">{{ actionable.fib_price.toFixed(2) }}</span>
                </span>
                <span v-if="actionable.quality_note" class="text-yellow-300/80">{{ actionable.quality_note }}</span>
            </div>

            <!-- 觀望提示 -->
            <div v-if="holdOff" class="text-xs text-gray-400 bg-gray-700/30 rounded-lg px-3 py-2 leading-relaxed">
                ⚪ 觀望
                <template v-if="holdOff.zone_range">｜區間 {{ holdOff.zone_range }}</template>
                ｜{{ holdOff.quality_note || '量縮上漲，不追' }}
            </div>

            <!-- 警示 -->
            <div v-if="warning"
                class="text-xs text-yellow-300 bg-yellow-900/20 border border-yellow-700/30 rounded-lg px-3 py-2">
                ⚠️ {{ warning.advice }}
                <div v-if="warning.reasons?.length" class="text-yellow-400/70 mt-0.5">
                    {{ warning.reasons.join('｜') }}
                </div>
            </div>
        </div>

        <!-- ── Risk ──────────────────────────────────────── -->
        <div v-else-if="activeTab === 'risk'" class="space-y-2">
            <!-- Hero：持有力 + 年化波動 -->
            <div class="grid grid-cols-2 gap-2">
                <div class="rounded-lg bg-gray-700/40 px-3 py-2.5 text-center">
                    <div class="text-sm font-semibold" :class="holdClr">
                        {{ holdStr }}
                        <span class="tracking-wider">{{ stars }}</span>
                    </div>
                    <div class="text-xs text-gray-500 mt-0.5">🏆 持有力</div>
                </div>
                <div class="rounded-lg bg-gray-700/40 px-3 py-2.5 text-center">
                    <div class="text-sm font-semibold" :class="volClr">{{ volStr }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">年化波動率 · {{ r.volGrade ?? '—' }}</div>
                </div>
            </div>

            <div class="text-xs text-gray-500">⚠️ 風險指標</div>
            <!-- 舒適度 / MDD / 目前回撤 -->
            <div class="grid grid-cols-3 gap-2">
                <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
                    <div class="text-sm font-semibold" :class="comfortClr">{{ r.comfortScore ?? '—' }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">舒適度</div>
                </div>
                <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
                    <div class="text-sm font-semibold" :class="mddClr">{{ mddStr }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">MDD</div>
                </div>
                <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
                    <div class="text-sm font-semibold" :class="currClr">{{ currStr }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">目前回撤</div>
                </div>
            </div>

            <!-- Pain / Sharpe / Alpha -->
            <div class="grid grid-cols-3 gap-2">
                <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
                    <div class="text-sm font-semibold" :class="painClr">{{ painStr }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">Pain Ratio</div>
                </div>
                <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
                    <div class="text-sm font-semibold">{{ r['夏普值'] ?? '—' }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">Sharpe</div>
                </div>
                <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
                    <div class="text-sm font-semibold">{{ r['Alpha 勝率'] ?? '—' }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">Alpha 勝率</div>
                </div>
            </div>
        </div>

        <!-- ── Quant ─────────────────────────────────────── -->
        <div v-else-if="activeTab === 'quant'" class="space-y-2">
            <div class="text-xs text-gray-500">📋 基本面</div>
            <div class="grid grid-cols-4 gap-2">
                <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
                    <div class="text-sm font-semibold tabular-nums">{{ fmtEps }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">EPS</div>
                </div>
                <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
                    <div class="text-sm font-semibold" :class="peClr">{{ fmtPe }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">P/E</div>
                </div>
                <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
                    <div class="text-sm font-semibold" :class="yieldClr">{{ r['殖利率'] ?? '—' }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">殖利率</div>
                </div>
                <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
                    <div class="text-sm font-semibold tabular-nums">{{ r.PEG ?? '—' }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">PEG</div>
                </div>
            </div>
            <div class="text-xs text-gray-500">📊 量化分析</div>
            <div class="grid grid-cols-4 gap-2">
                <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
                    <div class="text-sm font-semibold">{{ r['RS 百分位'] ?? '—' }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">RS%</div>
                </div>
                <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
                    <div class="text-sm font-semibold" :class="rsiClr">{{ fmt1(r.RSI) }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">RSI</div>
                </div>
                <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
                    <div class="text-sm font-semibold" :class="biasClr">{{ r['乖離率 (Bias)'] ?? '—' }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">Bias%</div>
                </div>
                <div class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
                    <div class="text-sm font-semibold" :class="volRatioClr">{{ r['量比'] ?? '—' }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">量比</div>
                </div>
            </div>

            <div class="text-xs text-gray-500 mt-1">📈 均線參考</div>
            <div class="grid grid-cols-4 gap-2">
                <div v-for="ma in ['MA20', 'MA60', 'MA120', 'MA250']" :key="ma"
                    class="rounded-lg bg-gray-700/40 px-3 py-2 text-center">
                    <div class="text-sm font-semibold tabular-nums">{{ fmt2(r[ma]) }}</div>
                    <div class="text-xs text-gray-500 mt-0.5">{{ ma }}</div>
                </div>
            </div>
        </div>

        <!-- ── Holdings ────────────────────────────────────────── -->
        <div v-else-if="activeTab === 'holdings'" class="space-y-3">
            <div v-if="holdingsLoading" class="text-xs text-gray-500 text-center py-6">載入中…</div>
            <div v-else-if="holdingsError" class="text-xs text-red-400 text-center py-6">{{ holdingsError }}</div>
            <template v-else>
                <div>
                    <div class="text-xs text-gray-500 mb-1">📦 前十大持股</div>
                    <div v-if="holdingsList.length" ref="holdingsChartEl" class="w-full"
                        :style="`height: ${holdingsChartHeight}px`" />
                    <div v-else class="text-xs text-gray-500 py-3 text-center">個股或無持股穿透資料</div>
                </div>
                <div>
                    <div class="text-xs text-gray-500 mb-1">🏭 產業配置</div>
                    <div v-if="sectorList.length" ref="sectorChartEl" class="w-full"
                        :style="`height: ${sectorChartHeight}px`" />
                    <div v-else class="text-xs text-gray-500 py-3 text-center">無產業配置資料</div>
                </div>
            </template>
        </div>

        <!-- ── Details（交易紀錄） ─────────────────────────────── -->
        <div v-else-if="activeTab === 'details'" class="space-y-2">
            <div v-if="!transactions.length" class="text-xs text-gray-500 text-center py-6">無交易紀錄</div>
            <div v-else class="overflow-x-auto">
                <table class="w-full text-xs">
                    <thead>
                        <tr class="text-gray-500 border-b border-gray-700/50">
                            <th class="text-left py-1.5 pr-2">日期</th>
                            <th class="text-right py-1.5 pr-2">股數</th>
                            <th class="text-right py-1.5 pr-2">價格</th>
                            <th class="text-right py-1.5 pr-2">手續費</th>
                            <th class="text-right py-1.5 pr-2">總額</th>
                            <th class="text-right py-1.5">損益</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr v-for="(t, i) in transactions" :key="i" class="border-b border-gray-800">
                            <td class="py-1.5 pr-2 text-gray-300 whitespace-nowrap">{{ t.date }}</td>
                            <td class="py-1.5 pr-2 text-right tabular-nums">{{ fmtInt(t.shares) }}</td>
                            <td class="py-1.5 pr-2 text-right tabular-nums">{{ fmt2(t.price) }}</td>
                            <td class="py-1.5 pr-2 text-right tabular-nums text-gray-400">{{ fmtInt(t.fee) }}</td>
                            <td class="py-1.5 pr-2 text-right tabular-nums">{{ fmtInt(t.total) }}</td>
                            <td class="py-1.5 text-right tabular-nums" :class="plColor(t.pnl)">{{ fmtInt(t.pnl) }}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { fetchHoldings } from '../api/portfolio.js'
import { buildHorizontalBarOption, buildPieOption, horizontalBarHeight, pieChartHeight } from '../utils/chartOptions.js'
import { plColor } from '../utils/colors.js'

const props = defineProps({
    res: { type: Object, required: true },
    actionable: { type: Object, default: null },   // from dailySummary.actionable
    warning: { type: Object, default: null },   // from dailySummary.warnings
    holdOff: { type: Object, default: null },   // from dailySummary.hold_off
    transactions: { type: Array, default: () => [] },   // from transactionsMap[ticker]
})

const TABS = [
    { key: 'decision', label: '🎯 決策' },
    { key: 'risk', label: '⚠️ 風險' },
    { key: 'quant', label: '📊 量化' },
    { key: 'holdings', label: '🔬 成分' },
    { key: 'details', label: '📋 明細' },
]
const activeTab = ref('decision')

const r = computed(() => props.res)

// ── Price zone bar ────────────────────────────────────
const hasZoneBar = computed(() =>
    r.value.dailyUpper != null &&
    r.value.boundaryDailyRetest != null &&
    r.value.boundaryRetestSniper != null
)

const pricePct = computed(() => {
    if (!hasZoneBar.value) return 0
    const p = parseFloat(String(r.value['股價'] ?? 0).replace(',', ''))
    const up = r.value.dailyUpper
    const bdr = r.value.boundaryDailyRetest
    const brs = r.value.boundaryRetestSniper
    const zd = (up - bdr) || 1
    const zr = (bdr - brs) || 1

    if (p >= up) return Math.max(0, Math.min(25, ((up + zd - p) / zd) * 25))
    if (p >= bdr) return 50 - ((p - bdr) / zd) * 25
    if (p >= brs) return 75 - ((p - brs) / zr) * 25
    return Math.min(100, 75 + ((brs - p) / zr) * 25)
})

// ── Risk computed ─────────────────────────────────────
const holdAbility = computed(() => r.value.hold_abilityScore)
const holdPct = computed(() => typeof holdAbility.value === 'number' ? Math.round(holdAbility.value * 100) : 0)
const holdStr = computed(() => `${holdPct.value}%`)
const stars = computed(() => {
    const p = holdPct.value
    if (p >= 95) return '⭐⭐⭐⭐⭐'
    if (p >= 80) return '⭐⭐⭐⭐'
    if (p >= 65) return '⭐⭐⭐'
    if (p >= 50) return '⭐⭐'
    return '⭐'
})

const mddStr = computed(() => typeof r.value.maxDrawdownPct === 'number' ? `${r.value.maxDrawdownPct.toFixed(1)}%` : '—')
const currStr = computed(() => typeof r.value.currentDrawdownPct === 'number' ? `${r.value.currentDrawdownPct.toFixed(1)}%` : '—')
const painStr = computed(() => typeof r.value.painRatio === 'number' ? `${(r.value.painRatio * 100).toFixed(0)}%` : '—')
const volStr = computed(() => typeof r.value.annualizedVol === 'number' ? `${(r.value.annualizedVol * 100).toFixed(1)}%` : '—')

// ── Color helpers ─────────────────────────────────────
function ddClr(v) {
    if (typeof v !== 'number') return ''
    const a = Math.abs(v)
    return a < 5 ? 'text-green-400' : a < 15 ? 'text-orange-400' : 'text-red-400'
}

const holdClr = computed(() => {
    const v = holdAbility.value
    if (typeof v !== 'number') return 'text-gray-300'
    return v >= 0.70 ? 'text-green-400' : v >= 0.40 ? 'text-orange-400' : 'text-red-400'
})
const mddClr = computed(() => ddClr(r.value.maxDrawdownPct))
const currClr = computed(() => ddClr(r.value.currentDrawdownPct))
const painClr = computed(() => {
    const v = r.value.painRatio
    if (typeof v !== 'number') return ''
    return v < 0.20 ? 'text-green-400' : v < 0.50 ? 'text-orange-400' : 'text-red-400'
})
const volClr = computed(() => {
    return { '低波動': 'text-green-400', '中波動': 'text-orange-400', '高波動': 'text-red-400' }[r.value.volGrade] ?? ''
})
const comfortClr = computed(() => {
    return { 'High': 'text-green-400', 'Medium': 'text-orange-400', 'Low': 'text-red-400' }[r.value.comfortScore] ?? ''
})
const rsiClr = computed(() => {
    const v = r.value.RSI
    if (v == null) return ''
    return v >= 70 ? 'text-red-400' : v <= 30 ? 'text-green-400' : ''
})
const biasClr = computed(() => {
    const v = r.value['乖離率 (Bias)']
    if (v == null || v === '-') return ''
    const n = parseFloat(String(v).replace('%', '').replace(',', ''))
    if (isNaN(n)) return ''
    if (Math.abs(n) > 50) return 'text-red-400'
    if (n > 15) return 'text-orange-400'
    if (n < -10) return 'text-green-400'
    return ''
})
const volRatioClr = computed(() => {
    const v = r.value['量比']
    if (v == null || v === '-') return ''
    const n = parseFloat(String(v).replace(',', ''))
    return !isNaN(n) && n > 50 ? 'text-red-400' : ''
})

// ── FA computed ───────────────────────────────────────
const fmtEps = computed(() => {
    const v = r.value.EPS
    if (v == null) return '—'
    const n = parseFloat(v)
    return isNaN(n) ? '—' : n.toFixed(2)
})
const fmtPe = computed(() => {
    const v = r.value.PE
    if (v == null) return '—'
    const n = parseFloat(v)
    return isNaN(n) ? '—' : n.toFixed(1)
})
const peClr = computed(() => {
    const v = r.value.PE
    if (v == null) return ''
    const n = parseFloat(v)
    return !isNaN(n) && (n > 500 || n < 0) ? 'text-red-400' : ''
})
const yieldClr = computed(() => {
    const v = r.value['殖利率']
    if (v == null || v === '-') return ''
    const n = parseFloat(String(v).replace('%', ''))
    return !isNaN(n) && n > 20.0 ? 'text-red-400' : ''
})

// ── Holdings tab（持股穿透 + 產業配置） ─────────────────
const ticker = computed(() => r.value['代碼'])

const holdingsList = ref([])
const sectorList = ref([])
const holdingsLoading = ref(false)
const holdingsError = ref('')
let loadedTicker = null

const holdingsChartEl = ref(null)
const sectorChartEl = ref(null)
let holdingsChart = null
let sectorChart = null

const holdingsChartHeight = computed(() => horizontalBarHeight(holdingsList.value.length))
const sectorChartHeight = computed(() => pieChartHeight(sectorList.value.length))

function disposeHoldingsCharts() {
    holdingsChart?.dispose(); holdingsChart = null
    sectorChart?.dispose(); sectorChart = null
}

async function renderHoldingsCharts() {
    await nextTick()
    disposeHoldingsCharts()
    if (holdingsList.value.length && holdingsChartEl.value) {
        holdingsChart = echarts.init(holdingsChartEl.value, 'dark')
        holdingsChart.setOption(buildHorizontalBarOption(holdingsList.value, {
            getName: h => h.ticker || h.symbol,
            getValue: h => h.weight,
        }))
    }
    if (sectorList.value.length && sectorChartEl.value) {
        sectorChart = echarts.init(sectorChartEl.value, 'dark')
        sectorChart.setOption(buildPieOption(sectorList.value, {
            getName: s => s.name || s.sector,
            getValue: s => s.weight,
        }))
    }
}

async function loadHoldings() {
    const t = ticker.value
    if (!t) return
    holdingsLoading.value = true
    holdingsError.value = ''
    try {
        const res = await fetchHoldings(t)
        holdingsList.value = res.holdings ?? []
        sectorList.value = res.sector_allocation ?? []
        loadedTicker = t
    } catch (e) {
        holdingsError.value = `載入失敗：${e.message}`
    } finally {
        holdingsLoading.value = false
    }
    await renderHoldingsCharts()
}

function onHoldingsResize() {
    holdingsChart?.resize()
    sectorChart?.resize()
}

watch([activeTab, ticker], ([tab, tk]) => {
    if (tab !== 'holdings') {
        disposeHoldingsCharts()
        return
    }
    if (tk !== loadedTicker) {
        loadHoldings()
    } else {
        renderHoldingsCharts()
    }
})

onMounted(() => window.addEventListener('resize', onHoldingsResize))
onUnmounted(() => {
    window.removeEventListener('resize', onHoldingsResize)
    disposeHoldingsCharts()
})

// ── Formatters ────────────────────────────────────────
function fmt1(n) {
    if (n == null || n === '-' || n === '') return '—'
    const v = Number(n)
    return isNaN(v) ? String(n) : v.toFixed(1)
}
function fmt2(n) {
    if (n == null || n === '-' || n === '') return '—'
    const v = Number(n)
    return isNaN(v) ? String(n) : v.toFixed(2)
}
function fmtInt(n) {
    if (n == null || n === '-' || n === '') return '—'
    const v = Number(n)
    return isNaN(v) ? String(n) : Math.round(v).toLocaleString('zh-TW')
}
</script>
