<template>
    <div class="rounded-xl bg-gray-800 p-4 space-y-4">
        <div class="font-semibold text-sm">🔍 X-Ray 個股穿透</div>

        <!-- 地區篩選 -->
        <div class="flex flex-wrap gap-1.5">
            <button v-for="opt in regionOptions" :key="opt.code" type="button" @click="toggleRegion(opt.code)"
                class="text-xs px-2.5 py-1 rounded-full border transition-colors"
                :class="selectedRegions.includes(opt.code)
                    ? 'bg-blue-500/20 border-blue-400 text-blue-300'
                    : 'border-gray-600 text-gray-400 hover:border-gray-500'">
                {{ opt.label }}
            </button>
        </div>

        <div v-if="loading" class="text-xs text-gray-500 text-center py-10">穿透分析中，請稍候…</div>
        <div v-else-if="error" class="text-xs text-red-400 text-center py-10">{{ error }}</div>
        <template v-else-if="data">

            <!-- 摘要 -->
            <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400">
                <span>分析標的 <span class="text-gray-200">{{ data.assets_count }}</span> 檔</span>
                <span>已識別 <span class="text-green-400">{{ pct(data.identified_pct) }}</span></span>
                <span>未解析 <span class="text-orange-400">{{ pct(data.unidentified_pct) }}</span></span>
            </div>

            <!-- 個股曝險 -->
            <div>
                <div class="text-xs text-gray-500 mb-1">
                    📦 個股曝險 Top {{ exposuresTop.length }}
                    <span v-if="totalExposures > exposuresTop.length" class="text-gray-600">
                        （共 {{ totalExposures }} 檔已識別）
                    </span>
                </div>
                <div v-if="exposuresTop.length" ref="barEl" class="w-full" :style="`height: ${barHeight}px`" />
                <div v-else class="text-xs text-gray-500 py-3 text-center">無個股曝險資料</div>
            </div>

            <!-- 產業配置 -->
            <div>
                <div class="text-xs text-gray-500 mb-1">🏭 產業配置</div>
                <div v-if="sectorList.length" ref="sectorEl" class="w-full" :style="`height: ${sectorChartHeight}px`" />
                <div v-else class="text-xs text-gray-500 py-3 text-center">無產業配置資料</div>
            </div>

            <!-- 未解析桶 -->
            <div v-if="bucketsList.length">
                <div class="text-xs text-gray-500 mb-1">❔ 未解析（依地區彙總）</div>
                <div class="space-y-1">
                    <div v-for="b in bucketsList" :key="b.label"
                        class="flex justify-between text-xs bg-gray-700/30 rounded-lg px-3 py-1.5">
                        <span class="text-gray-300">{{ b.label }}</span>
                        <span class="text-gray-400 tabular-nums">{{ pct(b.weight) }}</span>
                    </div>
                </div>
            </div>
        </template>
    </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import { fetchXray } from '../api/portfolio.js'
import { buildHorizontalBarOption, buildPieOption, horizontalBarHeight, pieChartHeight } from '../utils/chartOptions.js'

const regionOptions = [
    { code: 'GB', label: '全球' },
    { code: 'US', label: '美股' },
    { code: 'JP', label: '日股' },
    { code: 'TW', label: '台股' },
]

const loading = ref(false)
const error = ref('')
const data = ref(null)
const selectedRegions = ref([])

const exposuresTop = computed(() => data.value?.exposures?.slice(0, 20) ?? [])
const totalExposures = computed(() => data.value?.exposures?.length ?? 0)
const sectorList = computed(() => data.value?.sector_exposures ?? [])
const bucketsList = computed(() => data.value?.buckets ?? [])
const barHeight = computed(() => horizontalBarHeight(exposuresTop.value.length))
const sectorChartHeight = computed(() => pieChartHeight(sectorList.value.length))

const barEl = ref(null)
const sectorEl = ref(null)
let barChart = null
let sectorChart = null

function disposeCharts() {
    barChart?.dispose(); barChart = null
    sectorChart?.dispose(); sectorChart = null
}

async function renderCharts() {
    await nextTick()
    disposeCharts()
    if (exposuresTop.value.length && barEl.value) {
        barChart = echarts.init(barEl.value, 'dark')
        barChart.setOption(buildHorizontalBarOption(exposuresTop.value, {
            getName: e => e.ticker || e.symbol,
            getValue: e => e.weight,
        }))
    }
    if (sectorList.value.length && sectorEl.value) {
        sectorChart = echarts.init(sectorEl.value, 'dark')
        sectorChart.setOption(buildPieOption(sectorList.value, {
            getName: s => s.name || s.sector,
            getValue: s => s.weight,
        }))
    }
}

async function load() {
    loading.value = true
    error.value = ''
    try {
        data.value = await fetchXray(selectedRegions.value)
    } catch (e) {
        error.value = `載入失敗：${e.message}`
    } finally {
        loading.value = false
    }
    await renderCharts()
}

function toggleRegion(code) {
    const idx = selectedRegions.value.indexOf(code)
    if (idx === -1) {
        selectedRegions.value.push(code)
    } else {
        selectedRegions.value.splice(idx, 1)
    }
    load()
}

function onResize() {
    barChart?.resize()
    sectorChart?.resize()
}

function pct(v) {
    return typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '—'
}

onMounted(() => {
    load()
    window.addEventListener('resize', onResize)
})
onUnmounted(() => {
    window.removeEventListener('resize', onResize)
    disposeCharts()
})
</script>
