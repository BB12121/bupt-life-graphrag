<script setup lang="ts">
import { computed, ref } from 'vue'
import { ChevronRight, LoaderCircle, Search } from 'lucide-vue-next'
import { useWorkspace } from '../stores/workspace'
import { shortCommit } from '../lib/presentation'
const store = useWorkspace(), query = ref(''), group = ref('全部资料')
const groupName = (path: string) => { const relative = path.replace('src/content/docs/', ''); return relative.includes('/') ? relative.split('/')[0] : '通用指南' }
const groups = computed(() => ['全部资料', ...new Set(store.documents.map(d => groupName(d.source_path)))])
const filtered = computed(() => store.documents.filter(d => (group.value === '全部资料' || groupName(d.source_path) === group.value) && (d.title + d.source_path).toLowerCase().includes(query.value.trim().toLowerCase())))
</script>
<template>
  <div class="page documents-page"><div class="page-heading"><h1>生活指南</h1><p>{{ store.statusLoading ? '正在读取资料…' : store.documents.length + ' 篇指南' }}<span v-if="store.status?.source_commit"> · {{ shortCommit(store.status.source_commit) }}</span></p></div>
    <div class="library-controls"><div class="search-field"><Search :size="18" /><input v-model="query" placeholder="搜索标题或目录" aria-label="搜索资料标题" /></div><span class="helper">{{ filtered.length }} 篇</span></div>
    <div class="category-tabs" aria-label="按原文目录分组"><button v-for="item in groups" :key="item" :class="{ active: group === item }" @click="group = item">{{ item }}</button></div>
    <p class="directory-note">分组仅按原文目录，不代表内容适用范围。</p>
    <div v-if="store.statusLoading" class="loading-block" role="status"><LoaderCircle class="spinning" :size="24" />正在读取指南…</div>
    <div v-else-if="store.startupError" class="empty-state"><h3>资料暂时无法读取</h3><p>{{ store.startupError }}</p><button class="button secondary" @click="store.initialize()">重试</button></div>
    <div v-else-if="filtered.length" class="document-grid"><RouterLink v-for="doc in filtered" :key="doc.id" :to="'/documents/' + doc.id" class="document-card"><span class="document-category">{{ groupName(doc.source_path) }}</span><h3>{{ doc.title.split('/').pop() }}</h3><div class="document-card-bottom"><span>阅读<ChevronRight :size="15" /></span></div></RouterLink></div>
    <div v-else class="empty-state"><Search :size="28" /><h3>没有匹配的资料</h3><p>试试其他关键词。</p><button class="button secondary" @click="query = ''; group = '全部资料'">清除筛选</button></div>
    <p class="attribution-note">资料来自 byrdocs/bupt-survival-guide · CC BY-NC-SA 4.0</p>
  </div>
</template>
