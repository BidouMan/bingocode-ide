#!/usr/bin/env node
/**
 * BingoCode 开发者手册构建脚本
 *
 * 独立于客户端打包：输出到 manual/dist，可本地打开、局域网或服务器部署。
 * 用法：
 *   pnpm manual:build   构建静态站点
 *   pnpm manual:serve   构建后启动本地服务器（0.0.0.0，可供局域网访问）
 */

import {
  readFileSync,
  writeFileSync,
  readdirSync,
  statSync,
  mkdirSync,
  existsSync,
  rmSync,
} from 'fs'
import { join, dirname, relative } from 'path'
import { fileURLToPath } from 'url'
import { createServer } from 'http'
import { networkInterfaces } from 'os'
import { Marked } from 'marked'
import hljs from 'highlight.js'

const __filename = fileURLToPath(import.meta.url)
const MANUAL_ROOT = dirname(__filename)
const REPO_ROOT = dirname(MANUAL_ROOT)
const CONTENT_DIR = join(MANUAL_ROOT, 'content')
const TEMPLATE_DIR = join(MANUAL_ROOT, 'templates')
const STATIC_DIR = join(MANUAL_ROOT, 'static')
const DIST_DIR = join(MANUAL_ROOT, 'dist')
const ASSETS_DIR = join(DIST_DIR, 'assets')

const VERSION = JSON.parse(readFileSync(join(REPO_ROOT, 'package.json'), 'utf-8')).version
const BUILD_DATE = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
}).format(new Date())

// ─── 导航结构 ───

interface NavItem {
  title: string
  path: string
  status?: 'ready' | 'soon'
  short?: string
}

interface NavGroup {
  title: string
  icon: 'start' | 'editor' | 'api'
  items: NavItem[]
}

const NAV: NavGroup[] = [
  {
    title: '开始',
    icon: 'start',
    items: [
      { title: '手册首页', path: 'index.md', short: '总览' },
      { title: '快速入门', path: 'guide/getting-started.md', short: '15 分钟' },
    ],
  },
  {
    title: '编辑器',
    icon: 'editor',
    items: [
      { title: '角色编辑器', path: 'editor/sprite-editor.md', short: '绘制与标注' },
      { title: '地图编辑器', path: 'editor/map-editor.md', status: 'soon' },
      { title: '资源管理', path: 'editor/resource-panel.md', status: 'soon' },
    ],
  },
  {
    title: 'API 参考',
    icon: 'api',
    items: [
      { title: '精灵 Sprite', path: 'api/sprite.md', short: '角色对象' },
      { title: '运动', path: 'api/movement.md', short: '移动与跳跃' },
      { title: '外观', path: 'api/appearance.md', status: 'soon' },
      { title: '侦测', path: 'api/detection.md', status: 'soon' },
      { title: '事件', path: 'api/events.md', status: 'soon' },
      { title: '控制', path: 'api/control.md', status: 'soon' },
      { title: '时间', path: 'api/time.md', status: 'soon' },
      { title: '声音', path: 'api/sound.md', status: 'soon' },
      { title: '地图', path: 'api/map.md', status: 'soon' },
      { title: '运算与工具', path: 'api/tools.md', status: 'soon' },
    ],
  },
]

const READY_ITEMS: NavItem[] = NAV.flatMap((group) =>
  group.items.filter((item) => item.status !== 'soon')
)

function findGroup(path: string): NavGroup | undefined {
  return NAV.find((group) => group.items.some((item) => item.path === path))
}

function findNavItem(path: string): NavItem | undefined {
  return READY_ITEMS.find((item) => item.path === path)
}

// ─── 图标 ───

function groupIcon(name: NavGroup['icon']): string {
  const paths: Record<NavGroup['icon'], string> = {
    start: '<path d="M8 4.8v14.4L18.5 12 8 4.8Z" />',
    editor: '<path d="M4.5 19.5 8 18.8 18.3 8.5a2.1 2.1 0 0 0-3-3L5.1 15.8l-.6 3.7Z" /><path d="m13.8 6.9 3 3" />',
    api: '<path d="M8.5 4 4 12l4.5 8M15.5 4 20 12l-4.5 8" />',
  }
  return `<svg class="group-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name]}</svg>`
}

function themeIcon(): string {
  return `<svg class="theme-icon theme-icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg><svg class="theme-icon theme-icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20.5 14.2A8.5 8.5 0 0 1 9.8 3.5a8.5 8.5 0 1 0 10.7 10.7Z"/></svg>`
}

function searchIcon(): string {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4 4"/></svg>`
}

function menuIcon(): string {
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16"/></svg>`
}

function chevronIcon(): string {
  return `<svg class="chevron" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m4 2 4 4-4 4"/></svg>`
}

// ─── Markdown ───

const marked = new Marked({
  gfm: true,
  breaks: false,
})

marked.use({
  renderer: {
    code({ text, lang }: { text: string; lang?: string }) {
      const requested = (lang || '').trim().toLowerCase()
      const language = requested && hljs.getLanguage(requested) ? requested : 'plaintext'
      const highlighted = hljs.highlight(text, { language }).value
      const label = requested || 'text'
      return `<div class="code-block">
  <div class="code-head">
    <span class="code-lang">${escapeHtml(label)}</span>
    <button class="copy-code" type="button" data-copy aria-label="复制代码">复制</button>
  </div>
  <pre><code class="hljs language-${language}">${highlighted}</code></pre>
</div>`
    },
  },
})

interface Heading {
  level: number
  id: string
  text: string
}

interface FrontMatter {
  [key: string]: string | boolean
}

function parseFrontMatter(source: string): { data: FrontMatter; body: string } {
  const match = source.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?/)
  if (!match) return { data: {}, body: source }

  const data: FrontMatter = {}
  for (const line of match[1].split(/\r?\n/)) {
    const index = line.indexOf(':')
    if (index < 0) continue
    const key = line.slice(0, index).trim()
    let value = line.slice(index + 1).trim()
    if (value === 'true') data[key] = true
    else if (value === 'false') data[key] = false
    else {
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1)
      }
      data[key] = value
    }
  }
  return { data, body: source.slice(match[0].length) }
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function stripTags(html: string): string {
  return html
    .replace(/<[^>]*>/g, '')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&amp;/g, '&')
    .replace(/\s+/g, ' ')
    .trim()
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[`*_~"'“”‘’（）()【】\[\]{}<>《》]/g, '')
    .replace(/[\s/\\|:：,，。.!！?？、]+/g, '-')
    .replace(/[^\p{L}\p{N}\-_.]/gu, '')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')
}

function addHeadingIds(html: string): { html: string; headings: Heading[] } {
  const used = new Map<string, number>()
  const headings: Heading[] = []

  const output = html.replace(
    /<h([23])([^>]*)>([\s\S]*?)<\/h\1>/g,
    (_match, rawLevel: string, attrs: string, inner: string) => {
      if (/\bid=/.test(attrs)) return `<h${rawLevel}${attrs}>${inner}</h${rawLevel}>`
      const level = Number(rawLevel)
      const text = stripTags(inner)
      let base = slugify(text) || `section-${headings.length + 1}`
      const count = used.get(base) || 0
      used.set(base, count + 1)
      if (count > 0) base = `${base}-${count + 1}`

      headings.push({ level, id: base, text })
      return `<h${level}${attrs} id="${base}"><a class="heading-anchor" href="#${base}" aria-label="复制本节链接">#</a>${inner}</h${level}>`
    }
  )

  return { html: output, headings }
}

function processLinks(html: string, prefix: string): string {
  return html.replace(/href="([^"]+?\.md)"/g, (match, path: string) => {
    if (path.startsWith('http') || path.startsWith('#') || path.startsWith('/')) return match
    if (path.startsWith('./') || path.startsWith('../')) return match
    return `href="${prefix}${path.replace(/\.md$/, '.html')}"`
  })
}

function renderScreenshots(html: string, prefix: string): string {
  let figureIndex = 0
  return html.replace(
    /<figure class="shot" data-file="([^"]+)"(?: data-caption="([^"]*)")?(?: data-desc="([^"]*)")?><\/figure>/g,
    (_match, file: string, caption: string, description: string) => {
      figureIndex += 1
      const safeFile = file.replace(/[^a-zA-Z0-9._/-]/g, '')
      const imagePath = join(STATIC_DIR, 'screenshots', safeFile)
      const exists = existsSync(imagePath)
      const alt = caption || description || '文档截图'
      const number = `图 ${figureIndex}`
      const desc = description || '建议使用 16:9 截图，保持界面清晰。'

      if (exists) {
        return `<figure class="shot">
  <button class="shot-open" type="button" data-lightbox="${prefix}assets/screenshots/${safeFile}" aria-label="放大查看${escapeHtml(alt)}">
    <img src="${prefix}assets/screenshots/${safeFile}" alt="${escapeHtml(alt)}" loading="lazy" />
  </button>
  <figcaption><span class="shot-num">${number}</span>${escapeHtml(caption || description || '')}</figcaption>
</figure>`
      }

      return `<figure class="shot shot-pending">
  <div class="shot-placeholder">
    <div class="shot-placeholder-icon">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <rect x="3" y="4" width="18" height="16" rx="2.5"/><circle cx="8.5" cy="9" r="1.5"/><path d="m3 16 5-4 4 3 3-2 6 5"/>
      </svg>
    </div>
    <div class="shot-placeholder-copy">
      <strong>待补截图</strong>
      <code>${escapeHtml(safeFile)}</code>
      <span>${escapeHtml(desc)}</span>
    </div>
    <span class="shot-placeholder-size">16:9</span>
  </div>
  <figcaption><span class="shot-num">${number}</span>${escapeHtml(caption || alt)}</figcaption>
</figure>`
    }
  )
}

function renderApiIndex(html: string, headings: Heading[]): string {
  if (!html.includes('<!-- api-index -->')) return html

  const entries = headings.filter((heading) => heading.level === 3)
  if (!entries.length) return html.replace('<!-- api-index -->', '')

  const links = entries
    .map(
      (heading) => `<a class="api-index-item" href="#${heading.id}">
  <span class="api-index-name">${escapeHtml(heading.text.split('—')[0].trim())}</span>
  <span class="api-index-title">${escapeHtml(heading.text.split('—').slice(1).join('—').trim())}</span>
</a>`
    )
    .join('\n')

  return html.replace(
    '<!-- api-index -->',
    `<nav class="api-index" aria-label="本页 API 索引">
  <div class="api-index-head">
    <span>本页函数索引</span>
    <span class="api-index-count">${entries.length} 项</span>
  </div>
  <div class="api-index-grid">${links}</div>
</nav>`
  )
}

// ─── 页面模板片段 ───

function generateSidebar(currentPath: string): string {
  const groups = NAV.map((group) => {
    const hasActive = group.items.some((item) => item.path === currentPath && !item.status)
    const items = group.items
      .map((item) => {
        const active = item.path === currentPath
        const prefix = currentPath.split('/').length - 1 > 0 ? '../'.repeat(currentPath.split('/').length - 1) : './'
        const href = `${prefix}${item.path.replace(/\.md$/, '.html')}`

        if (item.status === 'soon' || !findNavItem(item.path)) {
          return `<span class="nav-item disabled" aria-disabled="true">
  <span class="nav-item-title">${escapeHtml(item.title)}</span>
  <span class="nav-soon">待编写</span>
</span>`
        }

        return `<a class="nav-item${active ? ' active' : ''}" href="${href}"${active ? ' aria-current="page"' : ''}>
  <span class="nav-item-title">${escapeHtml(item.title)}</span>
  ${item.short ? `<span class="nav-short">${escapeHtml(item.short)}</span>` : ''}
</a>`
      })
      .join('\n')

    return `<section class="nav-group${hasActive ? ' expanded' : ''}">
  <button class="nav-group-title" type="button" aria-expanded="${hasActive ? 'true' : 'false'}">
    ${groupIcon(group.icon)}
    <span>${escapeHtml(group.title)}</span>
    ${chevronIcon()}
  </button>
  <div class="nav-group-items">
    ${items}
  </div>
</section>`
  }).join('\n')

  const homeHref = currentPath.includes('/')
    ? `${'../'.repeat(currentPath.split('/').length - 1)}index.html`
    : './index.html'

  return `<div class="sidebar-inner">
  <a class="brand" href="${homeHref}" aria-label="BingoCode 开发者手册首页">
    <span class="brand-mark">B</span>
    <span class="brand-copy">
      <strong>BingoCode</strong>
      <span>开发者手册</span>
    </span>
  </a>

  <button class="search-trigger" type="button" data-search-open>
    ${searchIcon()}
    <span>搜索函数、属性、教程</span>
    <kbd>⌘ K</kbd>
  </button>

  <nav class="sidebar-nav" aria-label="文档导航">
    ${groups}
  </nav>

  <div class="sidebar-footer">
    <div class="sidebar-version">
      <span class="status-dot"></span>
      <span>v${VERSION}</span>
      <span class="dot-sep">·</span>
      <span>本地手册</span>
    </div>
    <p>离线可读，也可部署到局域网或服务器。</p>
  </div>
</div>`
}

function generateBreadcrumbs(path: string, title: string): string {
  if (path === 'index.md') {
    return '<span class="crumb-current">手册首页</span>'
  }

  const group = findGroup(path)
  const depth = path.split('/').length - 1
  const prefix = depth > 0 ? '../'.repeat(depth) : './'
  return `<a href="${prefix}index.html">手册</a>
<span class="crumb-sep">/</span>
<span>${escapeHtml(group?.title || '文档')}</span>
<span class="crumb-sep">/</span>
<span class="crumb-current">${escapeHtml(title)}</span>`
}

function generateToc(headings: Heading[], enabled: boolean): string {
  if (!enabled) return ''
  const items = headings.filter((heading) => heading.level === 2 || heading.level === 3)
  if (!items.length) return ''

  const links = items
    .map(
      (heading) => `<a class="toc-link level-${heading.level}" href="#${heading.id}">${escapeHtml(heading.text)}</a>`
    )
    .join('\n')

  return `<div class="toc-inner">
  <div class="toc-title">本页目录</div>
  <nav class="toc-nav" aria-label="本页目录">
    ${links}
  </nav>
  <div class="toc-note">
    <strong>需要完整示例？</strong>
    <p>每页底部都附有可直接运行的完整代码，复制到客户端即可试玩。</p>
  </div>
</div>`
}

function generatePrevNext(path: string): string {
  const index = READY_ITEMS.findIndex((item) => item.path === path)
  const prev = index > 0 ? READY_ITEMS[index - 1] : null
  const next = index >= 0 && index < READY_ITEMS.length - 1 ? READY_ITEMS[index + 1] : null
  if (!prev && !next) return ''

  const depth = path.split('/').length - 1
  const prefix = depth > 0 ? '../'.repeat(depth) : './'

  const card = (item: NavItem, direction: 'prev' | 'next') => {
    const arrow = direction === 'prev' ? '←' : '→'
    return `<a class="page-nav-card ${direction}" href="${prefix}${item.path.replace(/\.md$/, '.html')}">
  <span class="page-nav-label">${direction === 'prev' ? `${arrow} 上一篇` : `下一篇 ${arrow}`}</span>
  <span class="page-nav-title">${escapeHtml(item.title)}</span>
</a>`
  }

  return `<nav class="page-nav" aria-label="上下页">
  ${prev ? card(prev, 'prev') : '<span></span>'}
  ${next ? card(next, 'next') : '<span></span>'}
</nav>`
}

// ─── 搜索索引 ───

interface SearchPage {
  title: string
  group: string
  path: string
  description: string
  headings: { id: string; title: string }[]
  text: string
}

function buildSearchIndex(pages: SearchPage[]): string {
  return `window.__BINGO_DOCS__ = ${JSON.stringify(
    {
      version: VERSION,
      pages,
    },
    null,
    2
  )};\n`
}

// ─── 页面构建 ───

function buildPage(item: NavItem, template: string): SearchPage {
  const mdPath = join(CONTENT_DIR, item.path)
  if (!existsSync(mdPath)) {
    throw new Error(`缺少内容文件：${item.path}`)
  }

  const source = readFileSync(mdPath, 'utf-8')
  const { data, body } = parseFrontMatter(source)
  const title = String(data.title || item.title)
  const description = String(data.description || '')
  const layout = String(data.layout || 'doc')
  const tocEnabled = data.toc !== false
  const group = findGroup(item.path)

  const depth = item.path.split('/').length - 1
  const prefix = depth > 0 ? '../'.repeat(depth) : './'

  // 允许内容中直接使用 {{PREFIX}} 拼接静态资源或页面链接
  const preparedBody = body.replace(/\{\{PREFIX\}\}/g, prefix)

  // 首页由整段 HTML 组成，直接使用，避免 Markdown 解析打断代码卡和卡片结构
  let html = layout === 'home' ? preparedBody : (marked.parse(preparedBody) as string)
  html = processLinks(html, prefix)

  const withIds = layout === 'home' ? { html, headings: [] as Heading[] } : addHeadingIds(html)
  let content = withIds.html
  content = renderApiIndex(content, withIds.headings)
  content = renderScreenshots(content, prefix)

  const sidebar = generateSidebar(item.path)
  const toc = generateToc(withIds.headings, tocEnabled && layout !== 'home')
  const breadcrumbs = generateBreadcrumbs(item.path, title)
  const pageNav = generatePrevNext(item.path)

  const pageHead =
    layout === 'home'
      ? ''
      : `<header class="page-head">
  <div class="page-kicker">${escapeHtml(group?.title || '文档')}</div>
  <h1>${escapeHtml(title)}</h1>
  ${description ? `<p class="page-lead">${escapeHtml(description)}</p>` : ''}
</header>`

  const fullHtml = template
    .replaceAll('{{PAGE_TITLE}}', escapeHtml(title))
    .replaceAll('{{PAGE_DESC}}', escapeHtml(description))
    .replaceAll('{{PAGE_PATH}}', item.path)
    .replaceAll('{{PREFIX}}', prefix)
    .replaceAll('{{LAYOUT}}', layout)
    .replaceAll('{{SIDEBAR}}', sidebar)
    .replaceAll('{{BREADCRUMBS}}', breadcrumbs)
    .replaceAll('{{PAGE_HEAD}}', pageHead)
    .replaceAll('{{CONTENT}}', content)
    .replaceAll('{{TOC}}', toc)
    .replaceAll('{{PAGE_NAV}}', pageNav)
    .replaceAll('{{VERSION}}', VERSION)
    .replaceAll('{{BUILD_DATE}}', BUILD_DATE)
    .replaceAll('{{THEME_ICON}}', themeIcon())
    .replaceAll('{{MENU_ICON}}', menuIcon())
    .replaceAll('{{SEARCH_ICON}}', searchIcon())

  const outputPath = join(DIST_DIR, item.path.replace(/\.md$/, '.html'))
  mkdirSync(dirname(outputPath), { recursive: true })
  writeFileSync(outputPath, fullHtml, 'utf-8')

  const plainSource = layout === 'home' ? preparedBody : (marked.parse(preparedBody) as string)
  const plainText = stripTags(plainSource)
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 4000)

  return {
    title,
    group: group?.title || '文档',
    path: item.path.replace(/\.md$/, '.html'),
    description,
    headings: withIds.headings
      .filter((heading) => heading.level === 2 || heading.level === 3)
      .map((heading) => ({ id: heading.id, title: heading.text })),
    text: plainText,
  }
}

function copyDir(src: string, dest: string): void {
  if (!existsSync(src)) return
  for (const entry of readdirSync(src)) {
    const srcPath = join(src, entry)
    const destPath = join(dest, entry)
    if (statSync(srcPath).isDirectory()) {
      mkdirSync(destPath, { recursive: true })
      copyDir(srcPath, destPath)
    } else {
      writeFileSync(destPath, readFileSync(srcPath))
    }
  }
}

function build(): void {
  if (existsSync(DIST_DIR)) rmSync(DIST_DIR, { recursive: true, force: true })
  mkdirSync(ASSETS_DIR, { recursive: true })

  const template = readFileSync(join(TEMPLATE_DIR, 'page.html'), 'utf-8')
  const searchPages: SearchPage[] = []

  for (const item of READY_ITEMS) {
    searchPages.push(buildPage(item, template))
    console.log(`  构建 ${item.path.replace(/\.md$/, '.html')}`)
  }

  copyDir(STATIC_DIR, ASSETS_DIR)
  writeFileSync(join(ASSETS_DIR, 'search-index.js'), buildSearchIndex(searchPages), 'utf-8')

  console.log(`\n完成：${relative(REPO_ROOT, DIST_DIR)}`)
  console.log(`页面：${READY_ITEMS.length} 个`)
}

// ─── 本地 / 局域网预览 ───

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.svg': 'image/svg+xml',
  '.gif': 'image/gif',
  '.woff2': 'font/woff2',
}

function serve(port: number): void {
  const server = createServer((req, res) => {
    let urlPath = decodeURIComponent((req.url || '/').split('?')[0])
    if (urlPath === '/') urlPath = '/index.html'

    const filePath = join(DIST_DIR, urlPath)
    if (!filePath.startsWith(DIST_DIR)) {
      res.writeHead(403)
      res.end('Forbidden')
      return
    }

    if (!existsSync(filePath) || statSync(filePath).isDirectory()) {
      res.writeHead(404, { 'Content-Type': 'text/html; charset=utf-8' })
      res.end('<h1>404</h1><p>页面不存在。</p>')
      return
    }

    const ext = filePath.slice(filePath.lastIndexOf('.'))
    res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' })
    res.end(readFileSync(filePath))
  })

  server.listen(port, '0.0.0.0', () => {
    const addresses = Object.values(networkInterfaces())
      .flat()
      .filter((info) => info && info.family === 'IPv4' && !info.internal)
      .map((info) => info!.address)

    console.log(`\n本地预览：http://localhost:${port}`)
    for (const address of addresses) {
      console.log(`局域网访问：http://${address}:${port}`)
    }
    console.log('按 Ctrl+C 停止服务')
  })
}

build()

if (process.argv.includes('--serve')) {
  serve(Number(process.env.PORT || 4321))
}
