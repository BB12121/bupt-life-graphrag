import MarkdownIt from 'markdown-it'
import { safeHttpUrl } from './presentation'
const markdown = new MarkdownIt({ html: false, linkify: true, breaks: false })
const defaultLink = markdown.renderer.rules.link_open || ((tokens, index, options, _env, self) => self.renderToken(tokens, index, options))
markdown.renderer.rules.link_open = (tokens, index, options, env, self) => {
  const token = tokens[index], href = token.attrGet('href') || ''
  if (href.startsWith('#')) token.attrSet('href', href)
  else {
    let absolute: string | undefined
    try {
      const source = new URL(env.sourceUrl || 'https://github.com/byrdocs/bupt-survival-guide/')
      if (href.startsWith('/') && source.pathname.includes('/src/content/docs/')) {
        const parts = href.split('#'), path = parts[0] + (/\.mdx?$/.test(parts[0]) ? '' : '.md')
        const prefix = source.pathname.split('/src/content/docs/')[0]
        absolute = safeHttpUrl(new URL(prefix + '/src/content/docs' + path + (parts[1] ? '#' + parts[1] : ''), source.origin).href)
      } else absolute = safeHttpUrl(new URL(href, source).href)
    } catch {}
    token.attrSet('href', absolute || '#')
    token.attrSet('target', '_blank'); token.attrSet('rel', 'noopener noreferrer')
  }
  return defaultLink(tokens, index, options, env, self)
}
markdown.renderer.rules.image = (_tokens, _index) => '<span class="md-image-note">[原文图片 · 请前往来源查看，图片内容不作为问答依据]</span>'
const defaultHeading = markdown.renderer.rules.heading_open || ((tokens, index, options, _env, self) => self.renderToken(tokens, index, options))
markdown.renderer.rules.heading_open = (tokens, index, options, env, self) => {
  const title = (tokens[index + 1]?.children || []).filter(t => t.type === 'text' || t.type === 'code_inline').map(t => t.content).join('')
  const slug = title.toLowerCase().trim().replace(/[^\p{L}\p{N}_\s-]/gu, '').replace(/\s+/g, '-')
  const seen = env.headingIds || (env.headingIds = new Map<string, number>()), count = seen.get(slug) || 0
  seen.set(slug, count + 1); tokens[index].attrSet('id', slug + (count ? '-' + count : ''))
  return defaultHeading(tokens, index, options, env, self)
}
// Starlight aside labels; unknown types fall back to the raw type name.
const ASIDE_LABELS: Record<string, string> = { note: '注意', tip: '提示', caution: '警告', danger: '危险', curriculum: '课程' }
// Presentational tags are dropped while their text is kept; anything else (script, img, MDX) stays escaped.
const PLAIN_TAGS = /<\/?(?:details|summary|small|center|figure|figcaption|p|sup|sub|span|div|a|b|strong|i|em|u|font)(?:\s[^<>]*)?>/gi
// Footnote markers are restored after rendering, so a definition is never parsed as a link reference.
// Private-use code points: markdown-it rewrites NUL, but passes these through untouched.
const FN_OPEN = '', FN_CLOSE = ''

function preprocess(text: string, excerpt: boolean): string {
  let inAside = false
  const lines = text
    .replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/, '')
    .replace(/<!--[\s\S]*?-->/g, '')
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(PLAIN_TAGS, '')
    .split(/\r?\n/)
    .flatMap(line => {
      const open = line.match(/^\s*:::\s*([\w-]+)(?:\[([^\]]*)\])?.*$/)
      if (open) { inAside = true; const label = ASIDE_LABELS[open[1].toLowerCase()] || open[1]; return ['> **' + label + (open[2] ? ' · ' + open[2] : '') + '**', '>'] }
      // A closing fence may appear without its opening line when an excerpt starts mid-aside.
      if (/^\s*:::\s*$/.test(line)) { inAside = false; return [''] }
      line = line.replace(/^\[\^([\w-]+)\]:\s*/, '注' + FN_OPEN + '$1' + FN_CLOSE + '：').replace(/\[\^([\w-]+)\](?!:)/g, FN_OPEN + '$1' + FN_CLOSE)
      return [inAside ? '> ' + line : line]
    })
  let body = lines.join('\n')
  // In-page anchors cannot resolve inside an answer card; keep only the link text there.
  if (excerpt) body = body.replace(/\[([^\]]+)\]\(#[^)]*\)/g, '$1')
  return body
}

function restoreFootnotes(html: string): string {
  return html.replace(new RegExp(FN_OPEN + '([\\w-]+)' + FN_CLOSE, 'g'), '<sup class="md-footnote">$1</sup>').replace(/[]/g, '')
}

export function renderMarkdown(text: string, sourceUrl: string): string {
  return restoreFootnotes(markdown.render(preprocess(text, false), { sourceUrl }))
}

/** Renders a short guide quote (answer or evidence) with the same safety rules as the reading view. */
export function renderExcerpt(text: string, sourceUrl: string): string {
  return restoreFootnotes(markdown.render(preprocess(text, true), { sourceUrl, headingIds: new Map() }))
}

/** Backend text answers are "指南原文（heading）：\nquote"; split so the heading is not rendered as body. */
export type CitedSegment = { text: string } | { cite: number }

/** Split a model-written answer into plain text and [n] citations (n is 1-based into response.evidence). */
export function splitCitations(text: string): CitedSegment[] {
  const segments: CitedSegment[] = []
  let last = 0
  for (const match of text.matchAll(/\s*\[(\d+)\]/g)) {
    if (match.index! > last) segments.push({ text: text.slice(last, match.index) })
    segments.push({ cite: Number(match[1]) })
    last = match.index! + match[0].length
  }
  if (last < text.length) segments.push({ text: text.slice(last) })
  return segments
}

export function splitAnswer(text: string): { heading: string | null; body: string } {
  const match = text.match(/^指南原文（(.*?)）：\n([\s\S]*)$/)
  return match ? { heading: match[1], body: match[2] } : { heading: null, body: text }
}
