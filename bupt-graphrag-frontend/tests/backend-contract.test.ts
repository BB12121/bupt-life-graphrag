import { describe, expect, it } from 'vitest'
import answered from '../../docs/examples/answered.json'
import partial from '../../docs/examples/partial.json'
import abstained from '../../docs/examples/abstained.json'
import clarification from '../../docs/examples/needs_clarification.json'
import type { QAResponse } from '../src/api/types'
import { edgeDirection, validateQA } from '../src/lib/presentation'

describe('后端实际导出的响应与前端协议兼容', () => {
  for (const response of [answered, partial, abstained, clarification]) {
    it(`接受 ${response.status} 并校验引用完整性`, () => {
      expect(validateQA(response as QAResponse)).toEqual([])
    })
  }
  it('实际跨文档三跳末边按逆向显示', () => {
    const response = answered as QAResponse
    const path = response.paths.find(p => p.nodes.at(-1)?.name === '学生证补办申请')!
    expect(edgeDirection(path, 2)).toBe('reverse')
    expect(new Set(response.evidence.map(e => e.source_path)).size).toBe(2)
  })
})
