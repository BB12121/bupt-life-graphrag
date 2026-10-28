<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ArrowUp, ArrowUpRight, ChevronDown, ChevronRight, History, MapPin, Plus } from 'lucide-vue-next'
import { useWorkspace } from '../stores/workspace'
import { campusLabel } from '../lib/presentation'
import type { Campus } from '../api/types'
import { isDemo } from '../api/client'
import AnswerPanel from '../components/AnswerPanel.vue'
import ModalShell from '../components/ModalShell.vue'
const store = useWorkspace(), question = ref(''), campusMenu = ref(false), showHistory = ref(false)
const canSubmit = computed(() => question.value.trim() && !store.qaPending && !store.syncing && !store.labRunning && !store.statusLoading)
const examples = [
  { label: '多功能厅怎么预约？', question: '沙河雁南一站式多功能厅怎么预约？', campus: 'shahe' as Campus },
  { label: '校园一卡通怎么补办？', question: '校园一卡通怎么补办？', campus: null as Campus },
  { label: '预约平台还能办理什么？', question: '沙河雁南一站式多功能厅的预约平台还能办理哪些手续？', campus: 'shahe' as Campus },
]
async function submit() { if (!canSubmit.value) return; campusMenu.value = false; await store.ask({ question: question.value.trim(), campus: store.campus, mode: 'hybrid', entity_bindings: {} }) }
function runExample(example: typeof examples[number]) { question.value = example.question; store.campus = example.campus; submit() }
function keyboard(e: KeyboardEvent) { if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && !e.isComposing) { e.preventDefault(); submit() } }
async function newQuestion() { store.resetConversation(); if (!store.qaPending) { question.value = ''; await nextTick(); document.getElementById('question')?.focus() } }
watch(() => store.currentTurnId, async () => { await nextTick(); document.getElementById('answer-result')?.scrollIntoView({ behavior: 'smooth', block: 'start' }) })
</script>
<template>
  <div :class="['page', 'ask-page', { 'has-result': store.currentTurn }]">
    <div v-if="!store.currentTurn" class="ask-heading"><h1>你想了解什么？</h1><p>校园服务、办事流程和生活信息。</p></div>
    <div v-else class="query-heading"><h1>查询结果</h1><div class="question-utilities"><button class="button secondary small" @click="showHistory = true"><History :size="15" />记录</button><button class="button secondary small" :disabled="store.qaPending" @click="newQuestion"><Plus :size="15" />新问题</button></div></div>
    <div class="question-area">
      <form class="question-box" @submit.prevent="submit">
        <label class="sr-only" for="question">你的校园生活问题</label><textarea id="question" v-model="question" :disabled="store.syncing" placeholder="例如：校园一卡通怎么补办？" rows="2" maxlength="2000" @keydown="keyboard"></textarea>
        <div class="question-box-bottom"><div class="campus-select"><button type="button" class="campus-trigger" :aria-expanded="campusMenu" @click="campusMenu = !campusMenu"><MapPin :size="15" />{{ campusLabel(store.campus) }}<ChevronDown :size="12" /></button><div v-if="campusMenu" class="campus-menu"><button v-for="option in [{ value: null, label: '暂不指定' }, { value: 'shahe', label: '沙河校区' }, { value: 'haidian', label: '海淀校区' }]" :key="String(option.value)" type="button" :class="{ active: store.campus === option.value }" @click="store.campus = option.value as Campus; campusMenu = false">{{ option.label }}</button></div></div><button class="send-button" type="submit" :disabled="!canSubmit" aria-label="提交问题" title="提交问题（⌘ / Ctrl + Enter）"><ArrowUp :size="21" /></button></div>
      </form>
      <p class="input-note">{{ isDemo ? '演示版，仅支持内置示例。' : '回答依据指南，可查看原文。' }}</p>
    </div>
    <template v-if="!store.currentTurn"><div class="suggestions"><span>试试这些问题</span><div class="example-list"><button v-for="example in examples" :key="example.label" :disabled="store.qaPending || store.syncing || store.labRunning || store.statusLoading" @click="runExample(example)">{{ example.label }}<ArrowUpRight :size="14" /></button></div></div><RouterLink to="/documents" class="browse-link">浏览指南<ChevronRight :size="16" /></RouterLink></template>
    <AnswerPanel v-else :key="store.currentTurn.id" :turn="store.currentTurn" />
  </div>
  <ModalShell v-if="showHistory" title="问题记录" @close="showHistory = false"><div class="history-list"><button v-for="turn in store.turns" :key="turn.id" :class="{ active: store.currentTurnId === turn.id }" @click="store.currentTurnId = turn.id; question = turn.request.question; store.campus = turn.request.campus; showHistory = false"><History :size="16" /><span>{{ turn.request.question }}</span><ChevronRight :size="16" /></button></div><p class="helper">记录保留至刷新页面，最多 15 条。</p></ModalShell>
</template>
