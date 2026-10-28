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
export function renderMarkdown(text: string, sourceUrl: string): string {
  return markdown.render(text.replace(/^---\r?\n[\s\S]*?\r?\n---(?:\r?\n|$)/, '').replace(/<!--[\s\S]*?-->/g, ''), { sourceUrl })
}
