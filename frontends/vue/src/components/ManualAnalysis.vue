<template>
  <div class="space-y-5">
    <!-- 輸入區 -->
    <div class="rounded-xl bg-gray-800 border border-gray-700/50 p-4 space-y-3">
      <div class="text-sm font-semibold">自選代碼量化分析</div>
      <p class="text-xs text-gray-400">輸入 Yahoo Finance 代碼（空格分隔），例：2330.TW 6284.TWO VOO</p>
      <div class="flex gap-2">
        <input
          v-model="inputText"
          type="text"
          placeholder="2330.TW 6284.TWO VOO"
          class="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 transition-colors"
          @keydown.enter="runAnalysis"
        />
        <button
          @click="runAnalysis"
          :disabled="loading || !inputText.trim()"
          class="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-sm font-medium transition-colors shrink-0"
        >
          {{ loading ? '分析中…' : '分析' }}
        </button>
      </div>
      <div v-if="error" class="text-xs text-red-400">{{ error }}</div>
    </div>

    <!-- 分析進度 -->
    <div v-if="loading" class="text-center py-10 text-gray-400 text-sm animate-pulse">
      正在抓取資料並執行量化分析，請稍候…
    </div>

    <!-- 結果列表 -->
    <div v-if="!loading && results.length" class="space-y-4">
      <div
        v-for="res in results"
        :key="res['代碼']"
        class="rounded-xl bg-gray-800 border border-gray-700/50 overflow-hidden"
      >
        <!-- 標的 Header -->
        <div class="px-4 py-3 flex items-center justify-between border-b border-gray-700/40">
          <div class="flex items-center gap-2.5">
            <button
              class="font-mono text-blue-400 hover:underline text-sm font-semibold transition-colors"
              @click="openChart(res)"
            >{{ res['代碼'] }}</button>
            <span class="text-sm text-gray-300">{{ res['名稱'] !== res['代碼'] ? res['名稱'] : '' }}</span>
            <span v-if="res.entryZoneStatus && res.entryZoneStatus !== '-'" class="text-xs">
              {{ res.entryZoneStatus }}
            </span>
          </div>
          <div class="flex items-center gap-2 text-sm">
            <span v-if="res['股價']" class="font-medium tabular-nums">{{ fmtPrice(res['股價']) }}</span>
            <button
              class="flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg bg-gray-700 hover:bg-gray-600 disabled:opacity-50 transition-colors text-gray-300"
              :disabled="copyState[res['代碼']] === 'loading'"
              @click="copyReport(res)"
            >
              <span v-if="copyState[res['代碼']] === 'loading'">產生中…</span>
              <span v-else-if="copyState[res['代碼']] === 'done'" class="text-green-400">✅ 已複製</span>
              <span v-else-if="copyState[res['代碼']] === 'error'" class="text-red-400">❌ 失敗</span>
              <span v-else>📋 複製 AI 報告</span>
            </button>
          </div>
        </div>

        <!-- 四 tab 量化面板 -->
        <div class="px-4 py-3">
          <AdvancedAnalysisPanel :res="res" />
        </div>
      </div>
    </div>

    <!-- 查無結果提示 -->
    <div v-if="!loading && queried && !results.length" class="text-center py-10 text-gray-500 text-sm">
      查無分析結果，請確認代碼格式（例：2330.TW / 6284.TWO / VOO）
    </div>

    <!-- K 線圖 Modal -->
    <ChartModal
      v-if="chartTicker"
      :ticker="chartTicker"
      :name="chartName"
      @close="chartTicker = ''"
    />
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import AdvancedAnalysisPanel from './AdvancedAnalysisPanel.vue'
import ChartModal from './ChartModal.vue'
import { fetchManualAnalysis } from '../api/portfolio.js'

const inputText = ref('')
const loading = ref(false)
const error = ref('')
const results = ref([])
const queried = ref(false)
const chartTicker = ref('')
const chartName = ref('')
const copyState = reactive({})

async function runAnalysis() {
  const tickers = inputText.value.trim().toUpperCase().split(/\s+/).filter(Boolean)
  if (!tickers.length) return

  loading.value = true
  error.value = ''
  results.value = []
  queried.value = false

  try {
    const data = await fetchManualAnalysis(tickers)
    results.value = data.assets ?? []
    queried.value = true
  } catch (e) {
    error.value = `分析失敗：${e.response?.data?.detail ?? e.message}`
  } finally {
    loading.value = false
  }
}

function openChart(res) {
  chartTicker.value = res['代碼']
  chartName.value = res['名稱'] || res['代碼']
}

async function copyReport(res) {
  const ticker = res['代碼']
  copyState[ticker] = 'loading'
  try {
    const report = res._report
    if (!report) throw new Error('無報告內容')
    await navigator.clipboard.writeText(report)
    copyState[ticker] = 'done'
    setTimeout(() => { delete copyState[ticker] }, 2000)
  } catch {
    copyState[ticker] = 'error'
    setTimeout(() => { delete copyState[ticker] }, 2000)
  }
}

const priceFmt = new Intl.NumberFormat('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fmtPrice = (n) => n == null ? '—' : priceFmt.format(n)
</script>
