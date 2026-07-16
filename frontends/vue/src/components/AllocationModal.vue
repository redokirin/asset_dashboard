<template>
    <Teleport to="body">
        <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4" @click.self="$emit('close')">
            <div class="bg-gray-800 rounded-2xl w-full max-w-3xl shadow-2xl overflow-hidden flex flex-col"
                style="max-height: 88vh">

                <!-- Header -->
                <div class="flex items-center justify-between px-5 py-4 border-b border-gray-700 shrink-0">
                    <span class="font-bold">資產配置分析</span>
                    <button class="text-gray-400 hover:text-white text-lg leading-none px-1"
                        @click="$emit('close')">✕</button>
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

                    <!-- ── 流動性分析 ──────────────────────────── -->
                    <LiquidityCard v-if="activeTab === 'liquidity'" :assets="assets" />

                    <!-- ── 市場佔比 ──────────────────────────── -->
                    <MarketPieChart v-else-if="activeTab === 'market'" :marketShare="marketShare" />

                    <!-- ── 資產佔比 ──────────────────────────── -->
                    <AssetPieChart v-else-if="activeTab === 'asset'" :assets="assets" />

                    <!-- ── X-Ray 個股穿透 ────────────────────── -->
                    <XrayExposureCard v-else-if="activeTab === 'xray'" />

                    <!-- ── ETF 比較 ──────────────────────────── -->
                    <EtfCompareChart v-else-if="activeTab === 'compare'" />

                </div>
            </div>
        </div>
    </Teleport>
</template>

<script setup>
import { ref } from 'vue'
import LiquidityCard from './LiquidityCard.vue'
import MarketPieChart from './MarketPieChart.vue'
import AssetPieChart from './AssetPieChart.vue'
import XrayExposureCard from './XrayExposureCard.vue'
import EtfCompareChart from './EtfCompareChart.vue'

defineProps({
    marketShare: { type: Object, required: true },
    assets: { type: Array, required: true },
})
defineEmits(['close'])

const TABS = [
    { key: 'liquidity', label: '流動性' },
    { key: 'market', label: '市場' },
    { key: 'asset', label: '資產' },
    { key: 'xray', label: '穿透' },
    { key: 'compare', label: '比較' },
]
const activeTab = ref('liquidity')
</script>
