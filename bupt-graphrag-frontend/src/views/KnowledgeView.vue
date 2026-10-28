<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { ArrowUpRight, CheckCircle2, Clock3, Database, FileText, GitCommitHorizontal, Info, Layers, LoaderCircle, RefreshCw, ShieldCheck } from 'lucide-vue-next'
import { useWorkspace } from '../stores/workspace'
import { formatTime, shortCommit } from '../lib/presentation'
import { isDemo } from '../api/client'
const store = useWorkspace(), sourceRef = ref('main'), error = ref(''), started = ref(0), elapsed = ref(0)
const adminKey = ref('')
let timer: ReturnType<typeof setInterval>
onUnmounted(() => clearInterval(timer))
async function synchronize() { if (store.syncing || store.qaPending || store.labRunning) return; error.value = ''; started.value = Date.now(); elapsed.value = 0; timer = setInterval(() => { elapsed.value = Math.floor((Date.now() - started.value) / 1000) }, 1000); try { await store.sync(sourceRef.value.trim(), adminKey.value); store.notify('快照检查完成，资料状态已刷新') } catch (e) { error.value = e instanceof Error ? e.message : '同步失败'; await store.initialize() } finally { clearInterval(timer); adminKey.value = '' } }
const validRef = computed(() => sourceRef.value.trim() === 'main' || /^[a-f0-9]{40}$/i.test(sourceRef.value.trim()))
</script>
<template>
  <div class="page knowledge-page"><div class="page-heading"><h1>知识库</h1><p>查看资料版本，检查更新。</p></div>
    <div v-if="isDemo" class="notice info"><Info :size="17" /><p>演示版只检查内置资料，不联网更新。</p></div>
    <div class="status-metrics"><article><span>指南</span><strong>{{ store.status?.document_count ?? '—' }}<small>篇</small></strong></article><article><span>知识版本</span><strong>{{ store.status?.knowledge_revision ?? '—' }}</strong></article></div>
    <section class="settings-card"><div class="card-heading"><h2>资料来源</h2><span class="pill">{{ store.status?.source_commit ? '已载入' : '尚未导入' }}</span></div><dl class="source-details"><div><dt>仓库</dt><dd><a href="https://github.com/byrdocs/bupt-survival-guide" target="_blank" rel="noopener noreferrer">{{ store.status?.repository || 'byrdocs/bupt-survival-guide' }}<ArrowUpRight :size="13" /></a></dd></div><div><dt>提交版本</dt><dd class="mono wrap-anywhere">{{ store.status?.source_commit || '尚未导入' }}</dd></div><div><dt>{{ isDemo ? '上次演示检查' : '上次同步' }}</dt><dd>{{ formatTime(store.status?.last_synced_at || null) }}</dd></div></dl></section>
    <section class="settings-card sync-card"><div class="card-heading"><h2>检查更新</h2></div><p>{{ isDemo ? '检查当前内置快照。' : '从指南仓库检查新版本，成功后更新知识库。' }}</p><form class="sync-form" @submit.prevent="synchronize"><details class="advanced-options"><summary>指定版本</summary><label for="source-ref">分支或完整提交</label><input id="source-ref" v-model="sourceRef" :disabled="store.syncing" placeholder="main 或 40 位 commit SHA" /><span v-if="!validRef" class="field-error">请输入 main 或完整的 40 位十六进制 SHA。</span></details><button class="button primary" :disabled="!validRef || store.syncing || store.qaPending || store.labRunning"><component :is="store.syncing ? LoaderCircle : RefreshCw" :class="{ spinning: store.syncing }" :size="16" />{{ store.syncing ? '检查中…' : '检查更新' }}</button></form>
    <details v-if="!isDemo" class="advanced-options"><summary>同步管理密钥（可选）</summary><label for="admin-key">后端启用同步保护时填写</label><input id="admin-key" v-model="adminKey" type="password" autocomplete="off" :disabled="store.syncing" placeholder="未启用保护可留空" /><p class="helper">仅用于本次同步，不保存到浏览器。</p></details>
    <div v-if="store.syncing" class="sync-pending" role="status"><LoaderCircle class="spinning" :size="18" /><span>已等待 {{ elapsed }} 秒</span><p>请等待完成，勿重复提交。</p></div><div v-if="error" class="notice warning" role="alert"><Info :size="17" /><p>{{ error }}</p></div>
    <div v-if="store.syncResult && !store.syncing" class="sync-result"><div><CheckCircle2 :size="18" /><strong>{{ store.syncResult.changed ? '已更新至新版本' : '没有新版本' }}</strong><span>版本 {{ store.syncResult.knowledge_revision }}</span></div><div class="change-counts"><span>新增 {{ store.syncResult.added }}</span><span>修改 {{ store.syncResult.updated }}</span><span>删除 {{ store.syncResult.deleted }}</span><span>待审核 {{ store.syncResult.pending_count }}</span></div></div></section>
  </div>
</template>
