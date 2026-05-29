import { Marked } from 'marked'
import { markedHighlight } from 'marked-highlight'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'

// ---- marked v12: 通过 marked-highlight 扩展集成代码高亮 ----
const marked = new Marked(
  markedHighlight({
    langPrefix: 'hljs language-',
    highlight(code: string, lang: string): string {
      if (lang && hljs.getLanguage(lang)) {
        return hljs.highlight(code, { language: lang }).value
      }
      return hljs.highlightAuto(code).value
    },
  }),
)

marked.setOptions({
  gfm: true,
  breaks: false,
})

// ---- XSS 防护：移除脚本标签（marked 默认转义 HTML，此为额外防线） ----
function stripScripts(html: string): string {
  return html.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
}

/**
 * 将 Markdown 文本渲染为安全的 HTML
 * @param raw 原始 Markdown 文本
 * @returns 可安全用于 v-html 的 HTML 字符串
 */
export function renderMarkdown(raw: string): string {
  // 1. 先转义内联 HTML（防止 XSS）
  // 2. 渲染 Markdown
  // 3. 移除任何 <script> 标签
  const html = marked.parse(raw, { async: false }) as string
  return stripScripts(html)
}

/**
 * 渲染内联 Markdown（无块级元素包装）
 */
export function renderInline(raw: string): string {
  const html = marked.parseInline(raw, { async: false }) as string
  return stripScripts(html)
}
