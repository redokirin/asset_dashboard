<template>
    <div class="rounded-xl bg-gray-800 p-4 space-y-3">
        <div class="flex items-center justify-between">
            <span class="text-xs text-gray-400 uppercase tracking-wide">市場事件日曆</span>
            <div class="flex items-center gap-2">
                <button @click="prevMonth" class="text-gray-400 hover:text-white text-xs px-1.5">◀</button>
                <span class="text-sm font-medium tabular-nums">{{ monthLabel }}</span>
                <button @click="nextMonth" class="text-gray-400 hover:text-white text-xs px-1.5">▶</button>
            </div>
        </div>

        <div class="grid grid-cols-7 gap-1 text-center text-xs text-gray-500">
            <span v-for="w in WEEKDAYS" :key="w">{{ w }}</span>
        </div>

        <div v-if="loading" class="text-xs text-gray-500 text-center py-6">載入中…</div>
        <div v-else class="grid grid-cols-7 gap-1">
            <template v-for="(week, wi) in weeks" :key="wi">
                <button v-for="(cell, ci) in week" :key="ci" :disabled="!cell" @click="cell && openDay(cell.dateStr)"
                    :class="[
                        'aspect-square rounded-lg text-xs flex flex-col items-center justify-center gap-0.5 transition-colors',
                        !cell ? 'invisible' : 'hover:bg-gray-700',
                        cell && cell.dateStr === todayStr ? 'ring-1 ring-blue-500' : '',
                    ]">
                    <span v-if="cell" class="tabular-nums">{{ cell.date.getDate() }}</span>
                    <span v-if="cell && eventDates.has(cell.dateStr)" class="w-1 h-1 rounded-full bg-yellow-400" />
                </button>
            </template>
        </div>

        <MarketEventDayModal v-if="selectedDate" :date="selectedDate" @close="onModalClose" />
    </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { toDateStr, buildMonthGrid } from '../utils/date.js'
import { fetchMarketEvents } from '../api/portfolio.js'
import MarketEventDayModal from './MarketEventDayModal.vue'

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六']

const today = new Date()
const todayStr = toDateStr(today)
const currentMonth = ref(new Date(today.getFullYear(), today.getMonth(), 1))
const eventDates = ref(new Set())
const loading = ref(false)
const selectedDate = ref('')

const monthLabel = computed(() => `${currentMonth.value.getFullYear()}年${currentMonth.value.getMonth() + 1}月`)
const weeks = computed(() => buildMonthGrid(currentMonth.value.getFullYear(), currentMonth.value.getMonth()))

async function loadMonthEvents() {
    loading.value = true
    try {
        const year = currentMonth.value.getFullYear()
        const month = currentMonth.value.getMonth()
        const start = toDateStr(new Date(year, month, 1))
        const end = toDateStr(new Date(year, month + 1, 0))
        const events = await fetchMarketEvents(start, end)
        eventDates.value = new Set(events.map(e => e.event_date))
    } catch (e) {
        eventDates.value = new Set()
    } finally {
        loading.value = false
    }
}

function prevMonth() {
    currentMonth.value = new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth() - 1, 1)
}
function nextMonth() {
    currentMonth.value = new Date(currentMonth.value.getFullYear(), currentMonth.value.getMonth() + 1, 1)
}

function openDay(dateStr) {
    selectedDate.value = dateStr
}
function onModalClose() {
    selectedDate.value = ''
    loadMonthEvents() // 彈窗內可能新增/編輯過事件，關閉後刷新月曆標記
}

watch(currentMonth, loadMonthEvents)
onMounted(loadMonthEvents)
</script>
