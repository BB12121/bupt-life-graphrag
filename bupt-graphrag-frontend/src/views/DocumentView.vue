<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft, ArrowUpRight, Code2, FileText, LoaderCircle, ShieldCheck } from 'lucide-vue-next'
import { api } from '../api/client'
import type { DocumentDetail } from '../api/types'
import { renderMarkdown } from '../lib/markdown'
import { safeHttpUrl, shortCommit } from '../lib/presentation'
const route = useRoute(), detail = ref<DocumentDetail | null>(null), error = ref(''), loading = ref(true), view = ref('read')
const html = computed(() => detail.value ? renderMarkdown(detail.value.text, detail.value.document.source_url) : ''), lines = computed(() => detail.value?.text.split('\n') || [])
let sequence = 0
watch(() => [route.params.id, route.query.commit], async () => { const seq = ++sequence; loading.value = true; error.value = ''; try { const doc = await api.document(String(route.params.id), typeof route.query.commit === 'string' ? route.query.commit : undefined); if (seq === sequence) detail.value = doc } catch (e) { if (seq === sequence) error.value = e instanceof Error ? e.message : '原文读取失败' } finally { if (seq === sequence) loading.value = false } }, { immediate: true })
</script>
<template>
  <div class="page document-page"><RouterLink to="/documents" class="back-link"><ArrowLeft :size="16" />返回指南资料库</RouterLink><div v-if="loading" class="loading-block"><LoaderCircle class="spinning" :size="24" />正在读取原文…</div><div v-else-if="error" class="empty-state"><FileText :size="28" /><h2>这份原文暂时不可用</h2><p>{{ error }}</p></div><template v-else-if="detail"><div class="document-title-block"><h1>{{ detail.document.title.split('/').pop() }}</h1><p>{{ detail.document.title }}</p></div><div class="document-toolbar"><div class="segmented"><button :class="{ active: view === 'read' }" @click="view = 'read'"><FileText :size="14" />阅读视图</button><button :class="{ active: view === 'source' }" @click="view = 'source'"><Code2 :size="14" />原文行号</button></div><div class="document-toolbar-right"><span class="mono">{{ shortCommit(detail.document.source_commit) }}</span><a v-if="safeHttpUrl(detail.document.source_url)" :href="safeHttpUrl(detail.document.source_url)" class="button secondary small" target="_blank" rel="noopener noreferrer">打开来源<ArrowUpRight :size="14" /></a></div></div><article v-if="view === 'read'" class="markdown-content" v-html="html"></article><div v-else class="document-source source-lines"><div v-for="(line, i) in lines" :key="i" class="source-line"><span class="line-number">{{ i + 1 }}</span><code>{{ line || ' ' }}</code></div></div><div class="attribution-note"><ShieldCheck :size="14" /><p>固定版本资料，内容可能已有变化。</p></div></template></div>
</template>
