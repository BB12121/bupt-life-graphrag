import snapshot from './guide.json'
import { ApiError } from '../api/client'
import type { Campus, DocumentDetail, Entity, Evidence, GraphPath, KnowledgeStatus, QARequest, QAResponse, SyncResult } from '../api/types'
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))
export const sourceCommit = snapshot.commit
const guide = snapshot.documents as (DocumentDetail & { group: string })[]
let lastChecked: string | null = null
const entity = (id: string, type: Entity['type'], name: string, campus: Entity['campus'] = 'shared', aliases: string[] = [], url: string | null = null): Entity => ({ id, type, name, aliases, campus, url })
const hall = entity('place-shahe-yannan-hall', 'Place', '雁南一站式多功能厅', 'shahe', ['雁南多功能厅'])
const reservation = entity('service-shahe-hall-booking', 'Service', '多功能厅预约', 'shahe')
const platform = entity('platform-service-bupt', 'Platform', '网上服务大厅', 'shared', [], 'https://service.bupt.edu.cn/')
const student = entity('service-student-id', 'Service', '学生证补办申请', 'unknown')
const visitor = entity('service-visitor', 'Service', '校外人员入校申请', 'unknown')
const bike = entity('service-bike', 'Service', '电动车校内牌照申请', 'unknown')
const portal = entity('platform-information', 'Platform', '信息服务门户', 'shared', [], 'http://my.bupt.edu.cn/')
const network = entity('condition-campus-network', 'Condition', '校园网环境')
const shaheActivity = entity('place-shahe-activity', 'Place', '沙河校区学生活动中心', 'shahe', ['学活'])
const haidianActivity = entity('place-haidian-activity', 'Place', '海淀校区学生活动中心', 'haidian', ['学活'])
export const demoEntityList: Entity[] = [hall, reservation, platform, student, visitor, bike, portal, network, shaheActivity, haidianActivity]
export function makeEvidence(id: string, title: string, heading: string, start: number, end: number): Evidence {
  const doc = guide.find(x => x.document.title === title)
  if (!doc) throw new Error('示例文档不存在：' + title)
  return { id, doc_id: doc.document.id, source_commit: sourceCommit, source_path: doc.document.source_path, heading, line_start: start, line_end: end, quote: doc.text.split('\n').slice(start - 1, end).join('\n'), source_url: doc.document.source_url + '#L' + start + '-L' + end }
}
const hallEvidence = makeEvidence('ev-hall', '沙河校区/日常活动', '一站式多功能厅', 41, 43)
const servicesEvidence = makeEvidence('ev-services', '学习生活/常用网站', '网上服务大厅', 112, 120)
const networkEvidence = makeEvidence('ev-network', '学习生活/常用网站', '信息服务门户', 92, 96)
const activityEvidence = makeEvidence('ev-activity', '行话辞典', '简称 · 学活', 58, 58)
function baseResponse(): QAResponse { return { status: 'answered', reason: null, knowledge_revision: 1, source_commit: sourceCommit, answers: [], paths: [], evidence: [], warnings: [], clarifications: [] } }
function sharedPath(service: Entity, id: string, branch = 0): GraphPath { return { id, branch_id: branch, nodes: [hall, reservation, platform, service], edges: [{ subject_id: hall.id, relation: 'PROVIDES', object_id: reservation.id, evidence_ids: [hallEvidence.id] }, { subject_id: reservation.id, relation: 'USES_PLATFORM', object_id: platform.id, evidence_ids: [hallEvidence.id] }, { subject_id: service.id, relation: 'USES_PLATFORM', object_id: platform.id, evidence_ids: [servicesEvidence.id] }] } }
export function buildDemoResponse(input: QARequest): QAResponse {
  const r = baseResponse(), q = input.question.trim()
  if (!q) throw new ApiError('invalid_question', '请输入非空问题。', 422)
  if (input.entity_bindings['学活'] && ![shaheActivity.id, haidianActivity.id].includes(input.entity_bindings['学活'])) throw new ApiError('invalid_entity_binding', '所选实体不在演示候选范围内。', 422)
  if (/冲突状态演示/.test(q)) return { ...r, status: 'partial', reason: 'conflicting_evidence', warnings: ['这是一条界面状态测试样例，不表示真实指南中已发现冲突。示例不编造冲突事实。'] }
  if (/现在|实时|今天.*营业|目前.*开放/.test(q)) return { ...r, status: 'abstained', reason: 'realtime_unavailable', warnings: ['当前回答依据固定指南快照，不提供实时状态确认。'] }
  if (/学活/.test(q)) {
    const binding = input.entity_bindings['学活']
    if (!binding) return { ...r, status: 'needs_clarification', reason: 'ambiguous_entity', clarifications: [{ field: 'entity_bindings', mention: '学活', options: [shaheActivity, haidianActivity].filter(e => !input.campus || e.campus === input.campus).map(e => ({ value: e.id, label: e.name })) }] }
    const choice = demoEntityList.find(e => e.id === binding)!
    if (input.campus && input.campus !== choice.campus) return { ...r, status: 'needs_clarification', reason: 'campus_required', clarifications: [{ field: 'campus', mention: '', options: [{ value: choice.campus, label: choice.name.replace('学生活动中心', '') }] }] }
    return { ...r, answers: [{ text: '“学活”是“学生活动中心”的简称。指南注明海淀和沙河校区各有一栋；你选择的是' + choice.name + '。这条原文未提供更具体的楼内位置。', entity_ids: [choice.id], path_ids: [], evidence_ids: [activityEvidence.id] }], evidence: [activityEvidence] }
  }
  if (/校园卡|一卡通/.test(q)) {
    if (!input.campus) return { ...r, status: 'needs_clarification', reason: 'campus_required', clarifications: [{ field: 'campus', mention: '', options: [{ value: 'shahe', label: '沙河校区' }, { value: 'haidian', label: '海淀校区' }] }] }
    const isShahe = input.campus === 'shahe', ev = makeEvidence('ev-card', isShahe ? '沙河校区/生活服务' : '海淀校区/生活服务', isShahe ? '校园一卡通补办' : '补办校园卡', isShahe ? 67 : 90, isShahe ? 69 : 92)
    return { ...r, answers: [{ text: isShahe ? '沙河校区可在学生活动中心一楼综合服务大厅的自动补办机器上办理，需携带身份证或输入身份证号。指南记载卡费为 20 元，综合服务大厅从东侧入口进入。' : '海淀校区可前往综合服务大厅（学苑风味餐厅南侧）使用自助补卡机。需刷身份证或输入身份证号；指南记载费用 20 元，从校园卡余额扣除，新卡当场出卡。', entity_ids: [], path_ids: [], evidence_ids: [ev.id] }], evidence: [ev], warnings: ['费用、办理时间等可能变化，请以对应服务的实际通知为准。'] }
  }
  if (/信息.*门户/.test(q)) {
    const path: GraphPath = { id: 'path-network', branch_id: 0, nodes: [portal, network], edges: [{ subject_id: portal.id, relation: 'REQUIRES', object_id: network.id, evidence_ids: [networkEvidence.id] }] }
    r.answers = [{ text: '需要。指南在“信息服务门户”条目明确注明“此网站需要校园网环境”。该门户用于查看校内通知和新闻，并提供各类校内资源的跳转入口。', entity_ids: [portal.id, network.id], path_ids: [path.id], evidence_ids: [networkEvidence.id] }]; r.paths = [path]; r.evidence = [networkEvidence]
  } else if (/多功能厅|预约平台/.test(q)) {
    if (input.campus === 'haidian') return { ...r, status: 'needs_clarification', reason: 'campus_required', clarifications: [{ field: 'campus', mention: '', options: [{ value: 'shahe', label: '沙河校区（此示例的多功能厅）' }] }] }
    if (/还能|手续|部分结果|交集/.test(q)) {
      r.paths = [sharedPath(student, 'path-student'), sharedPath(visitor, 'path-visitor'), sharedPath(bike, 'path-bike')]
      r.answers = [{ text: '可以。雁南一站式多功能厅通过「网上服务大厅」预约；同一平台还可以申请补办学生证、预约校外人员入校、办理电动车校内牌照等手续。这些服务共用平台，并不表示都在多功能厅现场办理。', entity_ids: [hall.id, reservation.id, platform.id, student.id, visitor.id, bike.id], path_ids: r.paths.map(p => p.id), evidence_ids: [hallEvidence.id, servicesEvidence.id] }]; r.evidence = [hallEvidence, servicesEvidence]
      if (/交集/.test(q)) {
        const full = sharedPath(student, 'path-intersection-a', 0), second: GraphPath = { id: 'path-intersection-b', branch_id: 1, nodes: [platform, student], edges: [{ subject_id: student.id, relation: 'USES_PLATFORM', object_id: platform.id, evidence_ids: [servicesEvidence.id] }] }
        r.paths = [full, second]; r.answers = [{ text: '学生证补办申请满足这两个条件：它与多功能厅预约使用同一平台，也是在网上服务大厅办理的事项。下面分别展示两条查询分支的支持。', entity_ids: [student.id], path_ids: r.paths.map(p => p.id), evidence_ids: [hallEvidence.id, servicesEvidence.id] }]
      }
      if (/部分结果/.test(q)) { r.status = 'partial'; r.reason = 'search_truncated'; r.paths = [r.paths[0]]; r.answers = [{ text: '已确认一项共用平台的手续：学生证补办申请。此次是截断状态演示，结果不代表完整清单。', entity_ids: [student.id], path_ids: [r.paths[0].id], evidence_ids: [hallEvidence.id, servicesEvidence.id] }]; r.warnings = ['这是人工设置的检索截断样例，用于验证 partial 的界面提示，不是实际搜索性能结果。'] }
    } else {
      const path: GraphPath = { id: 'path-booking', branch_id: 0, nodes: [hall, reservation, platform], edges: [{ subject_id: hall.id, relation: 'PROVIDES', object_id: reservation.id, evidence_ids: [hallEvidence.id] }, { subject_id: reservation.id, relation: 'USES_PLATFORM', object_id: platform.id, evidence_ids: [hallEvidence.id] }] }
      r.paths = [path]; r.evidence = [hallEvidence]; r.answers = [{ text: '沙河雁南一站式多功能厅需要通过「网上服务大厅」预约。指南同一段也提到雁北设有一站式多功能厅；这条路径展示的是雁南的预约服务。', entity_ids: path.nodes.map(n => n.id), path_ids: [path.id], evidence_ids: [hallEvidence.id] }]
    }
  } else if (/网上服务大厅.*校园网/.test(q)) return { ...r, status: 'abstained', reason: 'no_evidence', warnings: ['示例所用的“网上服务大厅”原文没有直接说明校园网要求，不能把其他平台的条件套用过来。'] }
  else return { ...r, status: 'abstained', reason: 'unsupported_query', warnings: ['演示模式只内置人工核对的有限示例，不执行自由检索。连接真实后端后可查询更多问题。'] }
  if (input.mode === 'vector') { r.paths = []; r.answers = r.answers.map(a => ({ ...a, path_ids: [] })); r.warnings.push('这是人工核对的 vector 展示样例，不执行向量模型；只保留文本依据。') }
  return r
}
export async function demoStatus(): Promise<KnowledgeStatus> { await delay(100); return { repository: snapshot.repository, source_commit: sourceCommit, knowledge_revision: 1, document_count: guide.length, last_synced_at: lastChecked } }
export async function demoDocuments() { await delay(80); return guide.map(x => x.document) }
export async function demoDocument(id: string, commit?: string): Promise<DocumentDetail> { await delay(150); if (commit && commit !== sourceCommit) throw new ApiError('revision_not_found', '演示未保存这个版本的原文。', 404); const doc = guide.find(x => x.document.id === id); if (!doc) throw new ApiError('document_not_found', '没有找到这篇指南。', 404); return { document: doc.document, text: doc.text } }
export async function demoEntities(q: string, campus: Campus) { await delay(100); return demoEntityList.filter(e => (!campus || e.campus === campus || e.campus === 'shared') && [e.name, ...e.aliases].some(n => n.includes(q))) }
export async function demoQA(input: QARequest) { await delay(650); return structuredClone(buildDemoResponse(input)) }
export async function demoSync(ref: string): Promise<SyncResult> { await delay(1300); if (ref !== 'main' && ref !== sourceCommit) throw new ApiError('demo_revision_unavailable', '演示只内置一个固定快照；如需同步其他版本，请连接真实后端。', 404); lastChecked = new Date().toISOString(); return { source_commit: sourceCommit, knowledge_revision: 1, added: 0, updated: 0, deleted: 0, pending_count: 0, changed: false } }
