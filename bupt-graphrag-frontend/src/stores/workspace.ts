import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '../api/client'
import type { Campus, Evidence, GuideDocument, KnowledgeStatus, QARequest, SyncResult, Turn } from '../api/types'
import { validateQA } from '../lib/presentation'
export const useWorkspace = defineStore('workspace', () => {
  const status = ref<KnowledgeStatus | null>(null), documents = ref<GuideDocument[]>([]), statusLoading = ref(true), startupError = ref(''), campus = ref<Campus>(null)
  const turns = ref<Turn[]>([]), currentTurnId = ref<string | null>(null), syncing = ref(false), labRunning = ref(false), syncResult = ref<SyncResult | null>(null), drawerEvidence = ref<Evidence | null>(null)
  const toast = ref(''), currentTurn = computed(() => turns.value.find(t => t.id === currentTurnId.value) || null), qaPending = computed(() => turns.value.some(t => t.pending))
  let toastTimer: ReturnType<typeof setTimeout>
  function notify(message: string) { toast.value = message; clearTimeout(toastTimer); toastTimer = setTimeout(() => { toast.value = '' }, 3500) }
  async function initialize() {
    statusLoading.value = true; startupError.value = ''
    try { const result = await Promise.all([api.status(), api.documents()]); status.value = result[0]; documents.value = result[1] }
    catch (e) { startupError.value = e instanceof Error ? e.message : '资料状态读取失败' }
    finally { statusLoading.value = false }
  }
  async function ask(input: QARequest) {
    if (syncing.value || qaPending.value || labRunning.value) { notify('当前任务仍在处理中，请稍候。'); return }
    const id = crypto.randomUUID(), turn: Turn = { id, request: { ...input, entity_bindings: { ...input.entity_bindings } }, response: null, pending: true, elapsedMs: 0, error: null }
    turns.value.unshift(turn); turns.value = turns.value.slice(0, 15); currentTurnId.value = id
    const started = performance.now()
    try {
      const response = await api.qa(input), problems = validateQA(response)
      if (problems.length) throw new Error('支持材料数据不完整：' + problems.join('；'))
      const saved = turns.value.find(t => t.id === id); if (saved) saved.response = response
    } catch (e) { const saved = turns.value.find(t => t.id === id); if (saved) saved.error = e instanceof Error ? e.message : '问题处理失败' }
    finally { const saved = turns.value.find(t => t.id === id); if (saved) { saved.pending = false; saved.elapsedMs = performance.now() - started } }
  }
  async function sync(ref: string, adminKey?: string) {
    if (qaPending.value || syncing.value || labRunning.value) throw new Error('请等待当前任务完成后再同步。')
    syncing.value = true; syncResult.value = null
    try { syncResult.value = await api.sync(ref, adminKey); await initialize(); return syncResult.value }
    finally { syncing.value = false }
  }
  function resetConversation() { if (qaPending.value) { notify('请等待当前问题完成。'); return } currentTurnId.value = null }
  return { status, documents, statusLoading, startupError, campus, turns, currentTurnId, currentTurn, qaPending, syncing, labRunning, syncResult, drawerEvidence, toast, initialize, ask, sync, notify, resetConversation }
})
