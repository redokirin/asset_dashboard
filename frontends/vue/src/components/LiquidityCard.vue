<template>
    <div class="rounded-xl bg-gray-800 p-4 space-y-3">
        <div class="font-semibold text-sm">流動性分析</div>

        <div v-if="!groups.length" class="text-xs text-gray-500">無資料</div>

        <template v-else>
            <!-- header row -->
            <div class="grid gap-2 px-1 text-xs text-gray-400" style="grid-template-columns:1fr 1fr 1fr;">
                <span>投資</span>
                <span class="text-right">可投入</span>
                <span v-if="anyKeep" class="text-right">保留金</span>
                <span v-else />
            </div>

            <!-- bank groups -->
            <div v-for="g in groups" :key="g.key" class="space-y-1">
                <!-- stacked bar -->
                <div class="flex h-4 w-full overflow-hidden rounded-md" style="background:rgba(255,255,255,0.08)">
                    <div :title="`投資 ${g.investmentPct.toFixed(1)}%`"
                        :style="{ width: g.investmentPct + '%', background: g.investColor }" />
                    <div :title="`可投入 ${g.cashPct.toFixed(1)}%`"
                        :style="{ width: g.cashPct + '%', background: g.cashColor }" />
                    <div v-if="g.keepTwd > 0" :title="`保留金 ${g.keepPct.toFixed(1)}%`"
                        :style="{ width: g.keepPct + '%', background: '#36494f' }" />
                </div>

                <!-- value row -->
                <div class="grid gap-2 px-1 text-xs tabular-nums" style="grid-template-columns:1fr 1fr 1fr;">
                    <span class="font-medium">${{ fmt(g.investmentValue) }}</span>
                    <span class="text-right">${{ fmt(g.investable) }}</span>
                    <span v-if="anyKeep" class="text-right text-gray-400">
                        {{ g.keepTwd > 0 ? '$' + fmt(g.keepTwd) : '' }}
                    </span>
                    <span v-else />
                </div>
            </div>

            <!-- legend -->
            <div class="flex flex-wrap gap-3 pt-1">
                <div v-for="g in groups" :key="'leg-' + g.key" class="flex items-center gap-1.5 text-xs">
                    <div class="w-2.5 h-2.5 rounded-sm shrink-0" :style="{ background: g.investColor }" />
                    <span class="text-gray-300">{{ g.title }}</span>
                    <span class="text-gray-500">${{ fmt(g.total) }}</span>
                </div>
            </div>
        </template>
    </div>
</template>

<script setup>
import { computed } from 'vue'

const CASH_MARKETS = new Set(['bank', 'cash', '現金'])
const PALETTES = [
    ['#2563eb', '#93c5fd'],
    ['#059669', '#86efac'],
    ['#7c3aed', '#c4b5fd'],
    ['#0f766e', '#99f6e4'],
]

const props = defineProps({
    assets: { type: Array, required: true },
})

const isCash = (r) => CASH_MARKETS.has((r['市場'] ?? '').toString().trim().toLowerCase())

const groups = computed(() => {
    const cashAssets = props.assets.filter(isCash)
    const investments = props.assets.filter(r => !isCash(r) && r['enabled'] !== 0)

    const bankRows = Object.fromEntries(
        cashAssets
            .filter(r => r['代碼'])
            .map(r => [r['代碼'].toString().trim(), r])
    )

    const settlementOf = (r) => (r['Settlement'] ?? '').toString().trim()
    const settlementKeys = [...new Set(investments.map(settlementOf))]

    const groupKeys = [...Object.keys(bankRows)]
    for (const k of settlementKeys) {
        if (!groupKeys.includes(k)) groupKeys.push(k)
    }

    const result = []
    groupKeys.forEach((key, idx) => {
        const bankRow = bankRows[key] ?? null
        const title = bankRow ? (bankRow['名稱'] || key) : (key || '未指定交割銀行')
        const matchedInv = key
            ? investments.filter(r => settlementOf(r) === key)
            : investments.filter(r => settlementOf(r) === '')
        const matchedCash = key
            ? cashAssets.filter(r => (r['代碼'] ?? '').toString().trim() === key)
            : []

        const investmentValue = matchedInv.reduce((s, r) => s + (r['市值'] ?? 0), 0)
        const cashValue = matchedCash.reduce((s, r) => s + (r['市值'] ?? 0), 0)
        if (investmentValue + cashValue === 0) return

        const keepTwd = bankRow ? (bankRow['keepTwd'] ?? 0) : 0
        const investable = cashValue - keepTwd
        const total = investmentValue + investable + keepTwd

        const investmentPct = total ? investmentValue / total * 100 : 0
        const cashPct = total ? investable / total * 100 : 0
        const keepPct = total ? keepTwd / total * 100 : 0

        const [investColor, cashColor] = PALETTES[idx % PALETTES.length]
        result.push({ key, title, investmentValue, investable, keepTwd, total, investmentPct, cashPct, keepPct, investColor, cashColor })
    })
    return result
})

const anyKeep = computed(() => groups.value.some(g => g.keepTwd > 0))

const fmt = new Intl.NumberFormat('zh-TW', { maximumFractionDigits: 0 }).format.bind(
    new Intl.NumberFormat('zh-TW', { maximumFractionDigits: 0 })
)
</script>
