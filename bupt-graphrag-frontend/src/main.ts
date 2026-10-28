import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './styles.css'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', component: () => import('./views/AskView.vue'), meta: { title: '问答' } },
    { path: '/documents', component: () => import('./views/DocumentsView.vue'), meta: { title: '生活指南' } },
    { path: '/documents/:id', component: () => import('./views/DocumentView.vue'), meta: { title: '原文阅读' } },
    { path: '/knowledge', component: () => import('./views/KnowledgeView.vue'), meta: { title: '知识库' } },
    { path: '/lab', component: () => import('./views/LabView.vue'), meta: { title: '检索对比' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})
router.afterEach(to => { document.title = String(to.meta.title || '北邮生活指南') + ' · 北邮生活指南' })
createApp(App).use(createPinia()).use(router).mount('#app')
