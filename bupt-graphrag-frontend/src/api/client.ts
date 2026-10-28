import type { Campus, DocumentDetail, Entity, GuideDocument, KnowledgeStatus, QARequest, QAResponse, SyncResult } from './types'
// Live is the default. Demo must be explicitly selected at build/dev startup.
export const isDemo = import.meta.env.VITE_API_MODE === 'demo'
const base = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '')
export class ApiError extends Error { constructor(public code: string, message: string, public status = 0) { super(message); this.name = 'ApiError' } }
async function request<T>(path: string, method = 'GET', body?: unknown, adminKey?: string): Promise<T> {
  const controller = new AbortController(), timeout = setTimeout(() => controller.abort(), 180_000)
  try {
    const headers: Record<string, string> = { Accept: 'application/json' }
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    if (adminKey) headers['X-Admin-Key'] = adminKey
    const res = await fetch(base + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal })
    const data = await res.json().catch(() => null)
    if (!res.ok) throw new ApiError(data?.error?.code || 'http_' + res.status, data?.error?.message || '请求未完成，请稍后手动重试。', res.status)
    if (data === null) throw new ApiError('invalid_response', '服务未返回有效的 JSON 数据。', res.status)
    return data as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof Error && error.name === 'AbortError') throw new ApiError('timeout', '等待超时；服务端任务可能仍在运行，请勿重复提交。')
    throw new ApiError('network_error', '无法连接服务。请检查后端地址与网络连接，再手动重试。')
  } finally { clearTimeout(timeout) }
}
const demo = () => import('../data/demo')
export const api = {
  status: async (): Promise<KnowledgeStatus> => isDemo ? (await demo()).demoStatus() : request('/knowledge/status'),
  documents: async (): Promise<GuideDocument[]> => isDemo ? (await demo()).demoDocuments() : (await request<{items: GuideDocument[]}>('/documents')).items,
  document: async (id: string, commit?: string): Promise<DocumentDetail> => isDemo ? (await demo()).demoDocument(id, commit) : request('/documents/' + encodeURIComponent(id) + (commit ? '?source_commit=' + encodeURIComponent(commit) : '')),
  entities: async (q = '', campus: Campus = null): Promise<Entity[]> => { const params = new URLSearchParams(); if (q) params.set('q', q); if (campus) params.set('campus', campus); return isDemo ? (await demo()).demoEntities(q, campus) : (await request<{items: Entity[]}>('/entities?' + params.toString())).items },
  qa: async (input: QARequest): Promise<QAResponse> => isDemo ? (await demo()).demoQA(input) : request('/qa', 'POST', input),
  sync: async (ref: string, adminKey?: string): Promise<SyncResult> => isDemo ? (await demo()).demoSync(ref) : request('/knowledge/sync', 'POST', { ref }, adminKey),
}
