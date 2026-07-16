<template>
    <div class="space-y-3">
        <div v-if="loading" class="text-xs text-gray-500 text-center py-6">載入中…</div>
        <div v-else-if="error" class="text-xs text-red-400 text-center py-6">{{ error }}</div>
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
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { fetchHoldings } from '../api/portfolio.js'
import { buildHorizontalBarOption, buildPieOption, horizontalBarHeight, pieChartHeight } from '../utils/chartOptions.js'

const props = defineProps({
    ticker: { type: String, default: '' },
})

const holdingsList = ref([])
const sectorList = ref([])
const loading = ref(false)
const error = ref('')
let loadedTicker = null

const holdingsChartEl = ref(null)
const sectorChartEl = ref(null)
let holdingsChart = null
let sectorChart = null

const holdingsChartHeight = computed(() => horizontalBarHeight(holdingsList.value.length))
const sectorChartHeight = computed(() => pieChartHeight(sectorList.value.length))

function disposeCharts() {
    holdingsChart?.dispose(); holdingsChart = null
    sectorChart?.dispose(); sectorChart = null
}

async function renderCharts() {
    await nextTick()
    disposeCharts()
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

async function load() {
    const t = props.ticker
    if (!t) return
    loading.value = true
    error.value = ''
    try {
        const res = await fetchHoldings(t)
        holdingsList.value = res.holdings ?? []
        sectorList.value = res.sector_allocation ?? []
        loadedTicker = t
    } catch (e) {
        error.value = `載入失敗：${e.message}`
    } finally {
        loading.value = false
    }
    await renderCharts()
}

function onResize() {
    holdingsChart?.resize()
    sectorChart?.resize()
}

watch(() => props.ticker, (t) => {
    if (t !== loadedTicker) load()
})

onMounted(() => {
    load()
    window.addEventListener('resize', onResize)
})
onUnmounted(() => {
    window.removeEventListener('resize', onResize)
    disposeCharts()
})
</script>
