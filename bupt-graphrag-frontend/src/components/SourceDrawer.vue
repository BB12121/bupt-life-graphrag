<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ArrowUpRight, BookOpen, Copy, FileText, LoaderCircle } from 'lucide-vue-next'
import { api } from '../api/client'
import type { DocumentDetail, Evidence } from '../api/types'
import { evidenceTitle, safeHttpUrl, shortCommit } from '../lib/presentation'
import { useWorkspace } from '../stores/workspace'
import ModalShell from './ModalShell.vue'
const props = defineProps<{ evidence: Evidence }>(), emit = defineEmits<{ close: [] }>(), store = useWorkspace()
const detail = ref<DocumentDetail | null>(null), error = ref(''), loading = ref(false), linesElement = ref<HTMLElement | null>(null)
const lines = computed(() => detail.value?.text.split('\n') || [])
let sequence = 0
watch(() => props.evidence, async evidence => {
  const id = ++sequence; loading.value = true; error.value = ''; detail.value = null
  try { const response = await api.document(evidence.doc_id, evidence.source_commit); if (id === sequence) detail.value = response }
  catch (e) { if (id === sequence) error.value = e instanceof Error ? e.message : '原文加载失败' }
  finally { if (id === sequence) { loading.value = false; await nextTick(); const line = linesElement.value?.querySelector('.highlighted'); if (line instanceof HTMLElement && linesElement.value) linesElement.value.scrollTop = Math.max(0, linesElement.value.scrollTop + line.getBoundingClientRect().top - linesElement.value.getBoundingClientRect().top - 72) } }
}, { immediate: true })
async function copy() { try { await navigator.clipboard.writeText(props.evidence.quote + '\n' + props.evidence.source_url); store.notify('引文和固定版本来源已复制') } catch { store.notify('当前浏览器不允许自动复制，请选择原文手动复制。') } }
</script>
<template>
  <ModalShell title="原文" drawer @close="emit('close')"><div class="source-document-title"><FileText :size="20" /><div><h3>{{ evidenceTitle(evidence) }}</h3><p>{{ evidence.heading }}</p></div></div><div class="source-meta"><span class="mono">{{ shortCommit(evidence.source_commit) }}</span><span>第 {{ evidence.line_start }}–{{ evidence.line_end }} 行</span><span class="pill subtle">固定版本</span></div><blockquote class="source-quote">{{ evidence.quote }}</blockquote><div class="source-actions"><button class="button secondary small" @click="copy"><Copy :size="14" />复制引用</button><a v-if="safeHttpUrl(evidence.source_url)" :href="safeHttpUrl(evidence.source_url)" class="button secondary small" target="_blank" rel="noopener noreferrer">GitHub 原文<ArrowUpRight :size="14" /></a></div><div class="section-line"><span><BookOpen :size="14" />原始 Markdown 上下文</span><span class="mono">{{ shortCommit(evidence.source_commit) }}</span></div><div v-if="loading" class="loading-block"><LoaderCircle class="spinning" :size="22" />正在读取固定版本原文…</div><div v-else-if="error" class="notice warning"><p>{{ error }}。上方仍保留回答返回的原始引文，可使用固定版本链接继续核查。</p></div><div v-else ref="linesElement" class="source-lines"><div v-for="(line, i) in lines" :key="i" :class="['source-line', { highlighted: i + 1 >= evidence.line_start && i + 1 <= evidence.line_end }]"><span class="line-number">{{ i + 1 }}</span><code>{{ line || ' ' }}</code></div></div><p class="helper">行号以所示版本为准。</p></ModalShell>
</template>
