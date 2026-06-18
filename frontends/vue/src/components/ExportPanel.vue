<template>
  <div class="rounded-xl bg-gray-800 p-4 space-y-3">
    <span class="text-xs text-gray-400 uppercase tracking-wide">AI 報告匯出</span>

    <!-- 整份報告 -->
    <button
      :disabled="fullLoading"
      class="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-blue-700 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm font-medium"
      @click="exportFull"
    >
      <span v-if="fullLoading">產生中…</span>
      <span v-else>📥 下載整份診斷報告</span>
    </button>

    <!-- 狀態訊息 -->
    <div v-if="msg" :class="['text-xs text-center', msgError ? 'text-red-400' : 'text-green-400']">
      {{ msg }}
    </div>

    <div class="text-xs text-gray-600 leading-relaxed">
      整份報告包含組合摘要、各標的量化診斷、風險係數與配置建議，可直接貼入 Claude / Gemini 取得 AI 分析。
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { fetchExportAi } from '../api/portfolio.js'

const fullLoading = ref(false)
const msg         = ref('')
const msgError    = ref(false)

function showMsg(text, isError = false) {
  msg.value      = text
  msgError.value = isError
  setTimeout(() => { msg.value = '' }, 3000)
}

async function exportFull() {
  fullLoading.value = true
  try {
    const { report } = await fetchExportAi()
    const date = new Date().toISOString().slice(0, 10)
    downloadMd(report, `ai_report_${date}.md`)
    showMsg('✅ 報告已下載')
  } catch (e) {
    showMsg(`❌ 匯出失敗：${e.message}`, true)
  } finally {
    fullLoading.value = false
  }
}

function downloadMd(content, filename) {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
</script>
