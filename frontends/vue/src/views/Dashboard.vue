<template>
  <div class="min-h-screen p-4 md:p-6 space-y-5">
    <div class="flex items-center justify-between">
      <h1 class="text-lg font-bold tracking-tight">資產追蹤看板</h1>
      <div class="flex items-center gap-3">
        <span v-if="updatedAt" class="text-xs text-gray-500">{{ updatedAt }}</span>
        <button
          @click="load"
          :disabled="loading"
          class="text-xs px-3 py-1.5 rounded-lg bg-gray-700 hover:bg-gray-600 disabled:opacity-50 transition-colors"
        >
          {{ loading ? '載入中…' : '重新整理' }}
        </button>
      </div>
    </div>

    <div v-if="error" class="rounded-xl bg-red-900/40 border border-red-700 p-4 text-sm text-red-300">
      {{ error }}
    </div>

    <template v-if="summary">
      <SummaryCard :summary="summary" />

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div class="lg:col-span-2 space-y-5">
          <AssetTable v-if="assets.length" :assets="assets" />
          <LiquidityCard v-if="assets.length" :assets="assets" />
        </div>
        <div class="space-y-5">
          <MarketPieChart v-if="marketShare" :marketShare="marketShare" />
          <AssetPieChart v-if="assets.length" :assets="assets" />
        </div>
      </div>
    </template>

    <div v-else-if="loading" class="text-center py-20 text-gray-500">載入資料中…</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import SummaryCard from '../components/SummaryCard.vue'
import AssetTable from '../components/AssetTable.vue'
import MarketPieChart from '../components/MarketPieChart.vue'
import AssetPieChart from '../components/AssetPieChart.vue'
import LiquidityCard from '../components/LiquidityCard.vue'
import { fetchPortfolio } from '../api/portfolio.js'

const summary = ref(null)
const assets = ref([])
const marketShare = ref(null)
const loading = ref(false)
const error = ref('')
const updatedAt = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const port = await fetchPortfolio()
    assets.value = port.assets ?? []
    marketShare.value = port.market_share ?? {}
    summary.value = port.summary
    updatedAt.value = new Date().toLocaleTimeString('zh-TW')
  } catch (e) {
    error.value = `無法連線 API：${e.message}`
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
