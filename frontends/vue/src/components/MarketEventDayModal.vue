<template>
    <Teleport to="body">
        <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4" @click.self="$emit('close')">
            <div class="bg-gray-800 rounded-2xl w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col"
                style="max-height: 88vh">

                <!-- Header -->
                <div class="flex items-center justify-between px-5 py-4 border-b border-gray-700 shrink-0">
                    <span class="font-bold">{{ date }}</span>
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
                <div class="p-4 overflow-y-auto space-y-3">

                    <!-- ── 市場事件 ──────────────────────────── -->
                    <div v-if="activeTab === 'events'" class="space-y-3">
                        <div v-if="eventsLoading" class="text-xs text-gray-500 text-center py-6">載入中…</div>
                        <div v-else-if="eventsError" class="text-xs text-red-400 text-center py-6">{{ eventsError }}</div>
                        <template v-else>
                            <div v-if="!events.length" class="text-xs text-gray-500 text-center py-4">當日無事件記錄</div>

                            <div v-for="ev in events" :key="ev.id"
                                class="rounded-lg bg-gray-700/40 p-3 space-y-2">
                                <template v-if="editingId === ev.id">
                                    <input v-model="editForm.event_tag" placeholder="event_tag"
                                        class="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-500" />
                                    <input v-model="editForm.event_name" placeholder="事件名稱"
                                        class="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-500" />
                                    <textarea v-model="editForm.event_note" placeholder="備註" rows="4"
                                        class="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-500" />
                                    <label class="flex items-center gap-2 text-xs text-gray-400">
                                        <input type="checkbox" v-model="editForm.is_pressure_test" />
                                        壓力測試事件
                                    </label>
                                    <div class="flex gap-2">
                                        <button @click="saveEdit(ev)" :disabled="savingEdit"
                                            class="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-xs font-medium transition-colors">
                                            {{ savingEdit ? '儲存中…' : '儲存' }}
                                        </button>
                                        <button @click="editingId = null"
                                            class="px-3 py-1.5 rounded-lg bg-gray-600 hover:bg-gray-500 text-xs transition-colors">
                                            取消
                                        </button>
                                    </div>
                                </template>
                                <template v-else>
                                    <div class="flex items-start justify-between gap-2">
                                        <div class="flex items-center gap-2 flex-wrap">
                                            <span class="text-sm font-medium">{{ ev.event_name || ev.event_tag }}</span>
                                            <span v-if="ev.is_pressure_test"
                                                class="text-xs px-2 py-0.5 rounded-full bg-yellow-900/30 border border-yellow-700/40 text-yellow-300">
                                                壓力測試
                                            </span>
                                        </div>
                                        <button @click="startEdit(ev)"
                                            class="text-xs text-gray-400 hover:text-white shrink-0">編輯</button>
                                    </div>
                                    <div class="text-xs text-gray-500">{{ ev.event_tag }}</div>
                                    <div v-if="ev.event_note" class="text-xs text-gray-300 whitespace-pre-wrap leading-relaxed">
                                        {{ ev.event_note }}
                                    </div>
                                </template>
                            </div>

                            <!-- 新增事件 -->
                            <div v-if="showAddForm" class="rounded-lg bg-gray-700/40 p-3 space-y-2">
                                <div class="text-xs text-gray-400">新增事件</div>
                                <input v-model="newForm.event_tag" placeholder="event_tag（必填）"
                                    class="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-500" />
                                <input v-model="newForm.event_name" placeholder="事件名稱"
                                    class="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-500" />
                                <textarea v-model="newForm.event_note" placeholder="備註" rows="4"
                                    class="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-blue-500" />
                                <label class="flex items-center gap-2 text-xs text-gray-400">
                                    <input type="checkbox" v-model="newForm.is_pressure_test" />
                                    壓力測試事件
                                </label>
                                <div class="flex gap-2">
                                    <button @click="saveNew" :disabled="savingNew || !newForm.event_tag.trim()"
                                        class="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-xs font-medium transition-colors">
                                        {{ savingNew ? '儲存中…' : '儲存' }}
                                    </button>
                                    <button @click="showAddForm = false"
                                        class="px-3 py-1.5 rounded-lg bg-gray-600 hover:bg-gray-500 text-xs transition-colors">
                                        取消
                                    </button>
                                </div>
                            </div>
                            <button v-else @click="showAddForm = true"
                                class="w-full text-xs px-3 py-2 rounded-lg bg-gray-700 hover:bg-gray-600 text-gray-300 transition-colors">
                                ＋ 新增事件
                            </button>
                        </template>
                    </div>

                    <!-- ── AI 報告 ──────────────────────────── -->
                    <div v-else-if="activeTab === 'reports'" class="space-y-3">
                        <div v-if="reportsLoading" class="text-xs text-gray-500 text-center py-6">載入中…</div>
                        <div v-else-if="reportsError" class="text-xs text-red-400 text-center py-6">{{ reportsError }}</div>
                        <template v-else>
                            <div v-if="!reports.length" class="text-xs text-gray-500 text-center py-4">當日無報告</div>
                            <div v-else class="flex flex-wrap gap-1.5">
                                <button v-for="f in reports" :key="f" @click="selectReport(f)" :class="[
                                    'text-xs px-2 py-1 rounded-lg transition-colors',
                                    selectedFile === f ? 'bg-blue-600 text-white' : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                                ]">{{ f }}</button>
                            </div>

                            <div v-if="contentLoading" class="text-xs text-gray-500 text-center py-6">載入報告中…</div>
                            <pre v-else-if="reportContent"
                                class="text-xs text-gray-300 whitespace-pre-wrap leading-relaxed bg-gray-900/40 rounded-lg p-3 overflow-x-auto"
                            >{{ reportContent }}</pre>
                        </template>
                    </div>

                </div>
            </div>
        </div>
    </Teleport>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue'
import {
    fetchMarketEvents, createMarketEvent, updateMarketEvent,
    fetchDayReports, fetchReportContent,
} from '../api/portfolio.js'

const props = defineProps({
    date: { type: String, required: true },
})
defineEmits(['close'])

const TABS = [
    { key: 'events', label: '市場事件' },
    { key: 'reports', label: 'AI 報告' },
]
const activeTab = ref('events')

// ── 市場事件 ────────────────────────────────────────────
const events = ref([])
const eventsLoading = ref(false)
const eventsError = ref('')

const editingId = ref(null)
const editForm = reactive({ event_tag: '', event_name: '', event_note: '', is_pressure_test: false })
const savingEdit = ref(false)

const showAddForm = ref(false)
const newForm = reactive({ event_tag: '', event_name: '', event_note: '', is_pressure_test: false })
const savingNew = ref(false)

async function loadEvents() {
    eventsLoading.value = true
    eventsError.value = ''
    try {
        events.value = await fetchMarketEvents(props.date, props.date)
    } catch (e) {
        eventsError.value = `載入失敗：${e.message}`
    } finally {
        eventsLoading.value = false
    }
}

function startEdit(ev) {
    editingId.value = ev.id
    editForm.event_tag = ev.event_tag
    editForm.event_name = ev.event_name || ''
    editForm.event_note = ev.event_note || ''
    editForm.is_pressure_test = !!ev.is_pressure_test
}

async function saveEdit(ev) {
    savingEdit.value = true
    try {
        await updateMarketEvent(ev.id, {
            event_tag: editForm.event_tag,
            event_name: editForm.event_name,
            event_note: editForm.event_note,
            is_pressure_test: editForm.is_pressure_test ? 1 : 0,
        })
        editingId.value = null
        await loadEvents()
    } catch (e) {
        eventsError.value = `儲存失敗：${e.message}`
    } finally {
        savingEdit.value = false
    }
}

async function saveNew() {
    if (!newForm.event_tag.trim()) return
    savingNew.value = true
    try {
        await createMarketEvent({
            event_date: props.date,
            event_tag: newForm.event_tag.trim(),
            event_name: newForm.event_name,
            event_note: newForm.event_note,
            is_pressure_test: newForm.is_pressure_test ? 1 : 0,
        })
        newForm.event_tag = ''
        newForm.event_name = ''
        newForm.event_note = ''
        newForm.is_pressure_test = false
        showAddForm.value = false
        await loadEvents()
    } catch (e) {
        eventsError.value = `新增失敗：${e.message}`
    } finally {
        savingNew.value = false
    }
}

// ── AI 報告 ─────────────────────────────────────────────
const reports = ref([])
const reportsLoading = ref(false)
const reportsError = ref('')
let reportsLoaded = false

const selectedFile = ref('')
const reportContent = ref('')
const contentLoading = ref(false)

async function loadReports() {
    reportsLoading.value = true
    reportsError.value = ''
    try {
        const res = await fetchDayReports(props.date)
        reports.value = res.files ?? []
        reportsLoaded = true
    } catch (e) {
        reportsError.value = `載入失敗：${e.message}`
    } finally {
        reportsLoading.value = false
    }
}

async function selectReport(filename) {
    selectedFile.value = filename
    contentLoading.value = true
    reportContent.value = ''
    try {
        const res = await fetchReportContent(props.date, filename)
        reportContent.value = res.content ?? ''
    } catch (e) {
        reportContent.value = `載入失敗：${e.message}`
    } finally {
        contentLoading.value = false
    }
}

watch(activeTab, (tab) => {
    if (tab === 'reports' && !reportsLoaded) loadReports()
})

onMounted(loadEvents)
</script>
