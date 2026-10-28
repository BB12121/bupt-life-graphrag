import type { Edge, Evidence, GraphPath, QAResponse, Turn } from '../api/types'

export const campusLabel = (campus: string | null) => ({ shahe: '沙河校区', haidian: '海淀校区', shared: '全校适用', unknown: '范围待确认' }[campus || ''] || '暂不指定')
export const entityTypeLabel = (type: string) => ({ Campus: '校区', Place: '地点', Service: '服务', Platform: '平台', Condition: '条件' }[type] || type)
export const relationLabel = (relation: string) => ({ LOCATED_IN: '位于', PROVIDES: '提供服务', USES_PLATFORM: '使用平台', REQUIRES: '需要条件' }[relation] || relation)
export const shortCommit = (sha: string | null | undefined) => sha ? sha.slice(0, 8) : '尚未导入'
export function safeHttpUrl(value: string | null | undefined): string | undefined {
  if (!value) return undefined
  try { const u = new URL(value); return ['http:', 'https:'].includes(u.protocol) ? u.href : undefined } catch { return undefined }
}
export function edgeDirection(path: GraphPath, index: number): 'forward' | 'reverse' | 'invalid' {
  const edge = path.edges[index], a = path.nodes[index], b = path.nodes[index + 1]
  if (!edge || !a || !b) return 'invalid'
  if (edge.subject_id === a.id && edge.object_id === b.id) return 'forward'
  if (edge.subject_id === b.id && edge.object_id === a.id) return 'reverse'
  return 'invalid'
}
export function validateQA(response: QAResponse): string[] {
  const problems: string[] = []
  if (!response || !['answered', 'partial', 'abstained', 'needs_clarification'].includes(response.status)) return ['无法识别回答状态']
  if (![response.answers, response.paths, response.evidence, response.warnings, response.clarifications].every(Array.isArray)) return ['接口数组字段不完整']
  const evidences = new Set(response.evidence.map(e => e.id)), paths = new Set(response.paths.map(p => p.id))
  for (const answer of response.answers) {
    if (answer.path_ids.some(id => !paths.has(id)) || answer.evidence_ids.some(id => !evidences.has(id))) problems.push('结论的支持材料引用不完整')
  }
  for (const path of response.paths) {
    if (!path.nodes.length || path.edges.length !== path.nodes.length - 1) problems.push('路径节点与边数量不匹配')
    path.edges.forEach((edge: Edge, i: number) => {
      if (edgeDirection(path, i) === 'invalid') problems.push('路径关系方向与节点不匹配')
      if (!edge.evidence_ids.length || edge.evidence_ids.some(id => !evidences.has(id))) problems.push('路径缺少有效的原文引用')
    })
  }
  response.evidence.forEach(e => { if (!Number.isInteger(e.line_start) || e.line_start < 1 || e.line_end < e.line_start || e.source_commit !== response.source_commit) problems.push('证据版本或原文行范围不一致') })
  return [...new Set(problems)]
}
export function evidenceTitle(evidence: Evidence): string { return evidence.source_path.replace('src/content/docs/', '').replace(/\.mdx?$/, '') }
export function formatTime(iso: string | null): string { return iso ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso)) : '尚无记录' }
export function exportTurn(turn: Turn): void {
  if (!turn.response) return
  const r = turn.response
  const text = ['# 北邮生活指南 · 回答快照', '', '问题：' + turn.request.question, '校区：' + campusLabel(turn.request.campus), '模式：' + turn.request.mode, '状态：' + r.status, '知识版本：' + r.knowledge_revision, '来源提交：' + r.source_commit, '', ...r.answers.flatMap(a => [a.text, '']), ...r.warnings.map(w => '提醒：' + w), '', '## 原文依据', ...r.evidence.flatMap((e, i) => ['', String(i + 1) + '. ' + evidenceTitle(e) + ' L' + e.line_start + '–' + e.line_end, e.quote, e.source_url]), '', '本回答依据指南快照，不能确认实时状态。'].join('\n')
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown;charset=utf-8' })), a = document.createElement('a')
  a.href = url; a.download = '北邮生活指南-回答-' + shortCommit(r.source_commit) + '.md'; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}
