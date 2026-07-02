<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4"
      @click.self="$emit('close')"
    >
      <div class="bg-gray-800 rounded-2xl w-full max-w-3xl shadow-2xl overflow-hidden flex flex-col" style="max-height: 88vh">

        <!-- Header -->
        <div class="flex items-center justify-between px-5 py-4 border-b border-gray-700 shrink-0">
          <span class="font-bold">資產配置分析</span>
          <button class="text-gray-400 hover:text-white text-lg leading-none px-1" @click="$emit('close')">✕</button>
        </div>

        <!-- Tab bar -->
        <div class="flex gap-0.5 text-xs border-b border-gray-700/50 px-3 pt-2 shrink-0">
          <button v-for="tab in TABS" :key="tab.key" :class="[
            'px-3 py-1.5 -mb-px rounded-t-lg transition-colors border-b-2',
            activeTab === tab.key
              ? 'border-blue-500 text-white bg-gray-700/30'
              : 'border-transparent text-gray-400 hover:text-white'
          ]" @click="activeTab = tab.key">{{ tab.label }}</button>
        </div>

        <!-- Content -->
        <div class="p-4 overflow-y-auto">

          <!-- ── 市場佔比 ──────────────────────────── -->
          <MarketPieChart v-if="activeTab === 'market'" :marketShare="marketShare" />

          <!-- ── 資產佔比 ──────────────────────────── -->
          <AssetPieChart v-else-if="activeTab === 'asset'" :assets="assets" />

          <!-- ── X-Ray 個股穿透 ────────────────────── -->
          <div v-else-if="activeTab === 'xray'" class="space-y-4">
            <div v-if="xrayLoading" class="text-xs text-gray-500 text-center py-10">穿透分析中，請稍候…</div>
            <div v-else-if="xrayError" class="text-xs text-red-400 text-center py-10">{{ xrayError }}</div>
            <template v-else-if="xrayData">

              <!-- 摘要 -->
              <div class="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-400">
                <span>分析標的 <span class="text-gray-200">{{ xrayData.assets_count }}</span> 檔</span>
                <span>已識別 <span class="text-green-400">{{ pct(xrayData.identified_pct) }}</span></span>
                <span>未解析 <span class="text-orange-400">{{ pct(xrayData.unidentified_pct) }}</span></span>
              </div>

              <!-- 個股曝險 -->
              <div>
                <div class="text-xs text-gray-500 mb-1">
                  📦 個股曝險 Top {{ exposuresTop.length }}
                  <span v-if="totalExposures > exposuresTop.length" class="text-gray-600">
                    （共 {{ totalExposures }} 檔已識別）
                  </span>
                </div>
                <div v-if="exposuresTop.length" ref="xrayBarEl" class="w-full"
                  :style="`height: ${xrayBarHeight}px`" />
                <div v-else class="text-xs text-gray-500 py-3 text-center">無個股曝險資料</div>
              </div>

              <!-- 產業配置 -->
              <div>
                <div class="text-xs text-gray-500 mb-1">🏭 產業配置</div>
                <div v-if="sectorList.length" ref="xraySectorEl" class="w-full"
                  :style="`height: ${sectorChartHeight}px`" />
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

        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import MarketPieChart from './MarketPieChart.vue'
import AssetPieChart from './AssetPieChart.vue'
import { fetchXray } from '../api/portfolio.js'
import { buildHorizontalBarOption, buildPieOption, horizontalBarHeight, pieChartHeight } from '../utils/chartOptions.js'

defineProps({
  marketShare: { type: Object, required: true },
  assets: { type: Array, required: true },
})
defineEmits(['close'])

const TABS = [
  { key: 'market', label: '市場佔比' },
  { key: 'asset', label: '資產佔比' },
  { key: 'xray', label: 'X-Ray 個股穿透' },
]
const activeTab = ref('market')

function pct(v) {
  return typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '—'
}

// ── X-Ray ───────────────────────────────────────────────
const xrayLoading = ref(false)
const xrayError = ref('')
const xrayData = ref(null)
let xrayLoaded = false

const exposuresTop = computed(() => xrayData.value?.exposures?.slice(0, 20) ?? [])
const totalExposures = computed(() => xrayData.value?.exposures?.length ?? 0)
const sectorList = computed(() => xrayData.value?.sector_exposures ?? [])
const bucketsList = computed(() => xrayData.value?.buckets ?? [])
const xrayBarHeight = computed(() => horizontalBarHeight(exposuresTop.value.length))
const sectorChartHeight = computed(() => pieChartHeight(sectorList.value.length))

const xrayBarEl = ref(null)
const xraySectorEl = ref(null)
let xrayBarChart = null
let xraySectorChart = null

function disposeXrayCharts() {
  xrayBarChart?.dispose(); xrayBarChart = null
  xraySectorChart?.dispose(); xraySectorChart = null
}

async function renderXrayCharts() {
  await nextTick()
  disposeXrayCharts()
  if (exposuresTop.value.length && xrayBarEl.value) {
    xrayBarChart = echarts.init(xrayBarEl.value, 'dark')
    xrayBarChart.setOption(buildHorizontalBarOption(exposuresTop.value, {
      getName: e => e.name || e.symbol,
      getValue: e => e.weight,
    }))
  }
  if (sectorList.value.length && xraySectorEl.value) {
    xraySectorChart = echarts.init(xraySectorEl.value, 'dark')
    xraySectorChart.setOption(buildPieOption(sectorList.value, {
      getName: s => s.sector,
      getValue: s => s.weight,
    }))
  }
}

async function loadXray() {
  xrayLoading.value = true
  xrayError.value = ''
  try {
    xrayData.value = await fetchXray()
    xrayLoaded = true
  } catch (e) {
    xrayError.value = `載入失敗：${e.message}`
  } finally {
    xrayLoading.value = false
  }
  await renderXrayCharts()
}

function onXrayResize() {
  xrayBarChart?.resize()
  xraySectorChart?.resize()
}

watch(activeTab, (tab) => {
  if (tab !== 'xray') {
    disposeXrayCharts()
    return
  }
  if (!xrayLoaded) loadXray()
  else renderXrayCharts()
})

window.addEventListener('resize', onXrayResize)
onUnmounted(() => {
  window.removeEventListener('resize', onXrayResize)
  disposeXrayCharts()
})
</script>
