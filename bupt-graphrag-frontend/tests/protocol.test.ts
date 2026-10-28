import { describe, expect, it } from 'vitest'
import { buildDemoResponse, makeEvidence, sourceCommit } from '../src/data/demo'
import snapshot from '../src/data/guide.json'
import type { QARequest } from '../src/api/types'
import { edgeDirection, safeHttpUrl, validateQA } from '../src/lib/presentation'
import { renderMarkdown } from '../src/lib/markdown'
const request = (question: string, extra: Partial<QARequest> = {}): QARequest => ({ question, campus: 'shahe', mode: 'hybrid', entity_bindings: {}, ...extra })
describe('固定版本原文与证据', () => {
  it('纳入 39 篇业务正文，均使用完整且相同的固定提交', () => { expect(snapshot.documents).toHaveLength(39); expect(sourceCommit).toMatch(/^[a-f0-9]{40}$/); expect(snapshot.documents.every(x => x.document.source_commit === sourceCommit)).toBe(true) })
  it('所有示例引文都能在未经清洗的相应行范围逐字找到', () => {
    for (const question of ['多功能厅预约平台还能办理哪些手续？', '信息服务门户需要校园网吗？', '多功能厅怎么预约？', '补办校园一卡通', '多功能厅交集', '多功能厅部分结果']) {
      const r = buildDemoResponse(request(question)); expect(validateQA(r)).toEqual([])
      for (const e of r.evidence) { const doc = snapshot.documents.find(x => x.document.id === e.doc_id)!; expect(e.quote).toBe(doc.text.split('\n').slice(e.line_start - 1, e.line_end).join('\n')); expect(e.quote.length).toBeGreaterThan(0); expect(e.source_url).toContain(sourceCommit); expect(e.source_url).toContain('#L' + e.line_start + '-L' + e.line_end) }
    }
  })
})
describe('路径与业务状态', () => {
  it('三跳保留反向遍历时的事实方向', () => { const r = buildDemoResponse(request('多功能厅预约平台还能办理哪些手续？')); expect(r.paths).toHaveLength(3); expect(r.paths[0].edges).toHaveLength(3); expect(edgeDirection(r.paths[0], 2)).toBe('reverse'); expect(r.paths[0].edges[2].subject_id).toBe(r.paths[0].nodes[3].id) })
  it('交集同时返回两个完整分支', () => { const r = buildDemoResponse(request('多功能厅交集')); expect(r.paths.map(p => p.branch_id)).toEqual([0, 1]); expect(r.answers[0].path_ids).toHaveLength(2); expect(validateQA(r)).toEqual([]) })
  it('vector 不返回图路径，但保留真实原文证据', () => { const r = buildDemoResponse(request('多功能厅预约平台还能办理哪些手续？', { mode: 'vector' })); expect(r.paths).toEqual([]); expect(r.answers[0].path_ids).toEqual([]); expect(r.evidence.length).toBeGreaterThan(0) })
  it('不把其他平台的校园网要求套到网上服务大厅', () => { const r = buildDemoResponse(request('网上服务大厅需要校园网吗？')); expect(r.status).toBe('abstained'); expect(r.reason).toBe('no_evidence') })
  it('歧义绑定使用原 mention，确认后能继续回答', () => { const r = buildDemoResponse(request('学活是什么？', { campus: null })); expect(r.status).toBe('needs_clarification'); expect(r.clarifications[0].mention).toBe('学活'); const selected = r.clarifications[0].options[0].value; const result = buildDemoResponse(request('学活是什么？', { campus: null, entity_bindings: { 学活: selected } })); expect(result.status).toBe('answered'); expect(result.paths).toEqual([]); expect(validateQA(result)).toEqual([]) })
  it('校区未指定时要求澄清，不混淆两校区补卡流程', () => { const r = buildDemoResponse(request('校园卡补办', { campus: null })); expect(r.reason).toBe('campus_required'); const a = buildDemoResponse(request('校园卡补办')), b = buildDemoResponse(request('校园卡补办', { campus: 'haidian' })); expect(a.evidence[0].source_path).not.toBe(b.evidence[0].source_path); expect(a.answers[0].text).toContain('或') })
  it('实时请求拒答；未知问题不伪装成自由模型问答', () => { expect(buildDemoResponse(request('现在多功能厅开放吗？')).reason).toBe('realtime_unavailable'); expect(buildDemoResponse(request('不存在的自由提问样例')).reason).toBe('unsupported_query') })
  it('partial 可以没有答案，且保留限制说明', () => { const r = buildDemoResponse(request('冲突状态演示')); expect(r.status).toBe('partial'); expect(r.answers).toEqual([]); expect(r.warnings[0]).toContain('不表示真实指南'); expect(validateQA(r)).toEqual([]) })
  it('缺失来源会被标为支持材料不完整', () => { const r = buildDemoResponse(request('多功能厅怎么预约？')); r.evidence = []; expect(validateQA(r).length).toBeGreaterThan(0) })
})
describe('安全显示', () => {
  it('拒绝可执行 URL，允许 http/https', () => { expect(safeHttpUrl('javascript:alert(1)')).toBeUndefined(); expect(safeHttpUrl('data:text/html,test')).toBeUndefined(); expect(safeHttpUrl('https://example.com/')).toBe('https://example.com/') })
  it('不执行 Markdown 内的 HTML/MDX、脚本或图片', () => { const html = renderMarkdown('<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n<Component />\n\n![图片](https://example.com/tracker.png)', 'https://github.com/byrdocs/bupt-survival-guide/'); expect(html).not.toContain('<script>'); expect(html).not.toContain('<img '); expect(html).toContain('&lt;script&gt;'); expect(html).toContain('原文图片') })
  it('去除 frontmatter 仅用于阅读视图，不改动原始正文', () => { const body = '---\ntitle: 示例\n---\n\n正文'; expect(renderMarkdown(body, 'https://example.com/')).not.toContain('title:'); expect(body).toContain('title: 示例') })
  it('仓库内部文档链接保持固定提交，不错误跳到 GitHub 根目录', () => { const html = renderMarkdown('[校园网](/学习生活/校园网#网关账号)', 'https://github.com/byrdocs/bupt-survival-guide/blob/' + sourceCommit + '/src/content/docs/test.md'); expect(html).toContain('/blob/' + sourceCommit + '/src/content/docs/'); expect(html).toContain('.md#'); expect(html).toContain('noopener noreferrer') })
})
