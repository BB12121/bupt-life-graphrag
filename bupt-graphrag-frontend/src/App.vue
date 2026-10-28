<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowUpRight, BookOpen, Check, Menu, Search, X } from 'lucide-vue-next'
import { useWorkspace } from './stores/workspace'
import { isDemo } from './api/client'
import ModalShell from './components/ModalShell.vue'
import SourceDrawer from './components/SourceDrawer.vue'
const store = useWorkspace(), route = useRoute(), router = useRouter()
const mobileNav = ref(false), showHelp = ref(false), showSearch = ref(false), search = ref('')
const searchResults = computed(() => store.documents.filter(d => d.title.toLowerCase().includes(search.value.toLowerCase())).slice(0, 8))
const nav = [{ path: '/', name: '问答' }, { path: '/documents', name: '指南' }, { path: '/knowledge', name: '知识库' }, { path: '/lab', name: '检索对比' }]
const active = (path: string) => path === '/' ? route.path === '/' : route.path.startsWith(path)
function keyHandler(e: KeyboardEvent) {
  if (e.key === 'Escape') mobileNav.value = false
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); showSearch.value = !showSearch.value }
}
function go(path: string) { router.push(path); mobileNav.value = false }
onMounted(() => { store.initialize(); window.addEventListener('keydown', keyHandler) })
onUnmounted(() => window.removeEventListener('keydown', keyHandler))
</script>
<template>
  <a href="#main-content" class="skip-link">跳转到主要内容</a>
  <div class="app-layout">
    <header class="site-header">
      <div class="header-inner">
        <RouterLink to="/" class="brand" @click="mobileNav = false">北邮生活指南</RouterLink>
        <nav :class="['site-nav', { 'is-open': mobileNav }]" aria-label="主导航">
          <button v-for="item in nav" :key="item.path" :class="{ active: active(item.path) }" :aria-current="active(item.path) ? 'page' : undefined" @click="go(item.path)">{{ item.name }}</button>
        </nav>
        <div class="header-actions">
          <span v-if="isDemo" class="mode-badge">演示版</span>
          <button class="icon-button" aria-label="搜索指南，快捷键 Command 或 Control K" @click="showSearch = true"><Search :size="19" /></button>
          <button class="icon-button mobile-menu" :aria-expanded="mobileNav" :aria-label="mobileNav ? '关闭导航' : '打开导航'" @click="mobileNav = !mobileNav"><X v-if="mobileNav" :size="22" /><Menu v-else :size="22" /></button>
        </div>
      </div>
    </header>
    <main id="main-content">
      <div v-if="store.startupError" class="global-error" role="alert"><span>{{ store.startupError }}</span><button class="text-button" @click="store.initialize()">重试</button></div>
      <RouterView />
    </main>
    <footer class="page-footer"><span>指南内容不代表实时状态</span><div><a href="https://github.com/byrdocs/bupt-survival-guide" target="_blank" rel="noopener noreferrer">资料来源<ArrowUpRight :size="12" /></a><button @click="showHelp = true">关于</button></div></footer>
  </div>
  <div v-if="store.toast" class="toast" role="status"><Check :size="16" />{{ store.toast }}</div>
  <SourceDrawer v-if="store.drawerEvidence" :evidence="store.drawerEvidence" @close="store.drawerEvidence = null" />
  <ModalShell v-if="showSearch" title="搜索指南" @close="showSearch = false">
    <div class="dialog-search"><Search :size="19" /><input v-model="search" autofocus placeholder="搜索文档标题" aria-label="搜索文档标题" /></div>
    <div class="command-results"><button v-for="doc in searchResults" :key="doc.id" @click="go('/documents/' + doc.id); showSearch = false"><BookOpen :size="17" /><span>{{ doc.title }}</span><ArrowUpRight :size="15" /></button><div v-if="!searchResults.length" class="empty-small">没有匹配的文档</div></div>
  </ModalShell>
  <ModalShell v-if="showHelp" title="关于北邮生活指南" @close="showHelp = false">
    <div class="about-copy"><p>查询校园服务、办事流程和生活信息。回答可查看关系路径与原文。</p><p v-if="isDemo">当前为演示版，内置 39 篇固定版本指南和有限问答示例，未运行检索或模型推理。</p><p v-else>当前使用后端 API，回答以返回的原文和版本为准。</p><p>资料来自 byrdocs/bupt-survival-guide，遵循 CC BY-NC-SA 4.0。</p></div>
  </ModalShell>
</template>
