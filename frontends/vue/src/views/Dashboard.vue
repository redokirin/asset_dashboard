<template>
    <div class="min-h-screen p-4 md:p-6 space-y-5">
        <div class="flex items-center justify-between">
            <h1 class="text-lg font-bold tracking-tight">資產追蹤看板</h1>
            <div class="flex items-center gap-3">
                <span v-if="updatedAt" class="text-xs text-gray-500">{{ updatedAt }}</span>
                <button @click="load" :disabled="loading"
                    class="text-xs px-3 py-1.5 rounded-lg bg-gray-700 hover:bg-gray-600 disabled:opacity-50 transition-colors">
                    {{ loading ? '載入中…' : '重新整理' }}
                </button>
            </div>
        </div>

        <div v-if="error" class="rounded-xl bg-red-900/40 border border-red-700 p-4 text-sm text-red-300">
            {{ error }}
        </div>

        <template v-if="summary">
            <!-- 頂部：摘要 + 風險評分 -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
                <div class="lg:col-span-3">
                    <SummaryCard :summary="summary" />
                </div>
            </div>
            <!-- 主體 -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
                <div class="lg:col-span-2 space-y-5">
                    <!-- 每日摘要（可折疊） -->
                    <DailySummaryCard v-if="dailySummary" :summary="dailySummary" />
                    <AssetTable v-if="assets.length" :assets="assets" :advancedMap="advancedMap"
                        :dailySummary="dailySummary"
                        @open-chart="({ ticker, name }) => { chartTicker = ticker; chartName = name }" />
                </div>
                <div class="space-y-5">
                    <div>
                        <RiskScoreCard v-if="risk" :risk="risk" />
                        <div v-else class="rounded-xl bg-gray-800 p-4 text-xs text-gray-500 animate-pulse">
                            風險評分載入中…
                        </div>
                    </div>
                    <LiquidityCard v-if="assets.length" :assets="assets" />
                    <MarketPieChart v-if="marketShare" :marketShare="marketShare" />
                    <AssetPieChart v-if="assets.length" :assets="assets" />
                    <ExportPanel />
                </div>
            </div>
        </template>

        <div v-else-if="loading" class="text-center py-20 text-gray-500">載入資料中…</div>
    </div>

    <!-- K線圖 Modal -->
    <ChartModal v-if="chartTicker" :ticker="chartTicker" :name="chartName" @close="chartTicker = ''" />
</template>

<script setup>
import { ref, onMounted } from 'vue'
import SummaryCard from '../components/SummaryCard.vue'
import RiskScoreCard from '../components/RiskScoreCard.vue'
import DailySummaryCard from '../components/DailySummaryCard.vue'
import AssetTable from '../components/AssetTable.vue'
import ChartModal from '../components/ChartModal.vue'
import MarketPieChart from '../components/MarketPieChart.vue'
import AssetPieChart from '../components/AssetPieChart.vue'
import LiquidityCard from '../components/LiquidityCard.vue'
import ExportPanel from '../components/ExportPanel.vue'
import { fetchPortfolio, fetchRisk, fetchDailySummary, fetchAdvanced } from '../api/portfolio.js'

const summary = ref(null)
const assets = ref([])
const marketShare = ref(null)
const risk = ref(null)
const dailySummary = ref(null)
const advancedMap = ref({})
const loading = ref(false)
const error = ref('')
const updatedAt = ref('')
const chartTicker = ref('')
const chartName = ref('')

async function load() {
    loading.value = true
    error.value = ''
    try {
        // portfolio 優先，畫面先出來
        const port = await fetchPortfolio()
        assets.value = port.assets ?? []
        marketShare.value = port.market_share ?? {}
        summary.value = port.summary
        updatedAt.value = new Date().toLocaleTimeString('zh-TW')

        // risk、daily summary、advanced 三個平行載入
        const [riskData, summaryData, advData] = await Promise.allSettled([
            fetchRisk(),
            fetchDailySummary(),
            fetchAdvanced(),
        ])
        if (riskData.status === 'fulfilled') risk.value = riskData.value
        if (summaryData.status === 'fulfilled') dailySummary.value = summaryData.value
        if (advData.status === 'fulfilled') {
            const map = {}
            for (const row of advData.value.assets ?? []) map[row['代碼']] = row
            advancedMap.value = map
        }
    } catch (e) {
        error.value = `無法連線 API：${e.message}`
    } finally {
        loading.value = false
    }
}

onMounted(load)
</script>
