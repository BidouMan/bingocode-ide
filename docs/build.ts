#!/usr/bin/env node
/**
 * BingoCodeIDE 帮助文档构建脚本
 * 将 content/ 下的 Markdown 文件转换为带侧边栏的静态 HTML 页面
 *
 * 设计目标：清晰的层级、克制的视觉、适合长时间阅读。
 */

import { readFileSync, writeFileSync, readdirSync, statSync, mkdirSync, existsSync } from 'fs'
import { execFileSync } from 'child_process'
import { join, relative, dirname } from 'path'
import { fileURLToPath } from 'url'
import { Marked } from 'marked'
import hljs from 'highlight.js'

// ─── 路径配置 ───

const __filename = fileURLToPath(import.meta.url)
const DOCS_ROOT = dirname(__filename)
const REPO_ROOT = dirname(DOCS_ROOT)
const CONTENT_DIR = join(DOCS_ROOT, 'content')
const TEMPLATE_DIR = join(DOCS_ROOT, 'templates')
const DIST_DIR = join(DOCS_ROOT, 'dist')
const STATIC_DIR = join(DOCS_ROOT, 'static')

const VERSION = JSON.parse(readFileSync(join(REPO_ROOT, 'package.json'), 'utf-8')).version
// 每次构建生成新戳，给首页截图加查询参数，避免浏览器缓存旧图
const BUILD_STAMP = Date.now().toString(36)

// ─── Markdown 解析器配置 ───

const marked = new Marked({
  gfm: true,
  // 单个回车即换行：中文写作习惯里，作者敲回车就是想要换行，
  // 不必再刻意行尾加两个空格。空行仍然是分段。
  breaks: true,
})

// 代码高亮
marked.use({
  renderer: {
    code({ text, lang }: { text: string; lang?: string }) {
      const language = lang && hljs.getLanguage(lang) ? lang : 'plaintext'
      const highlighted = hljs.highlight(text, { language }).value
      const langLabel = lang || 'text'
      return `<div class="code-block">
        <div class="code-header">
          <span class="code-lang">${langLabel}</span>
          <button class="copy-btn" type="button" data-copy>复制</button>
        </div>
        <pre><code class="hljs language-${language}">${highlighted}</code></pre>
      </div>`
    },
  },
})

// ─── 导航结构定义 ───

interface NavItem {
  title: string
  path: string
  children?: NavItem[]
}

const NAV_STRUCTURE: NavItem[] = [
  { title: '欢迎', path: 'index.md' },
  {
    title: '快速入门',
    path: 'getting-started/first-game.md',
    children: [
      { title: '第一个游戏', path: 'getting-started/first-game.md' },
      { title: '核心概念', path: 'getting-started/basic-concepts.md' },
      { title: '安装与环境配置', path: 'getting-started/install.md' },
    ],
  },
  {
    title: '编辑器指南',
    path: 'editor/sprite-editor.md',
    children: [
      { title: '角色编辑器', path: 'editor/sprite-editor.md' },
      { title: '地图编辑器', path: 'editor/map-editor.md' },
      { title: '资源管理面板', path: 'editor/resource-panel.md' },
    ],
  },
  {
    title: '教学案例',
    path: 'tutorials/platformer.md',
    children: [
      { title: '平台跳跃游戏', path: 'tutorials/platformer.md' },
      { title: '跳跃手感优化', path: 'tutorials/jump-feel.md' },
      { title: '射击游戏', path: 'tutorials/shooting.md' },
      { title: '益智游戏', path: 'tutorials/puzzle.md' },
    ],
  },
  {
    title: 'API 参考',
    path: 'api/sprite.md',
    children: [
      { title: '精灵 (Sprite)', path: 'api/sprite.md' },
      { title: '运动', path: 'api/movement.md' },
      { title: '外观', path: 'api/appearance.md' },
      { title: '侦测', path: 'api/detection.md' },
      { title: '事件', path: 'api/events.md' },
      { title: '控制', path: 'api/control.md' },
      { title: '时间', path: 'api/time.md' },
      { title: '声音', path: 'api/sound.md' },
      { title: '地图', path: 'api/map.md' },
      { title: '工具函数', path: 'api/tools.md' },
      { title: '功能总览', path: 'api/overview.md' },
    ],
  },
  {
    title: 'Python 基础',
    path: 'python/basics.md',
    children: [
      { title: '基础语法', path: 'python/basics.md' },
      { title: '常用模式', path: 'python/common-patterns.md' },
    ],
  },
  { title: '常见问题', path: 'faq.md' },
]

// ─── 侧边栏 HTML 生成 ───

function getPrefix(mdPath: string): string {
  const depth = mdPath.split('/').length - 1
  return depth > 0 ? '../'.repeat(depth) : './'
}

function generateSidebar(currentPath: string): string {
  const prefix = getPrefix(currentPath)

  const items = NAV_STRUCTURE.map((item) => {
    if (item.children) {
      const childrenHtml = item.children
        .map((child) => {
          const isActive = child.path === currentPath
          return `<a class="nav-item${isActive ? ' active' : ''}" href="${prefix}${child.path.replace('.md', '.html')}">${child.title}</a>`
        })
        .join('\n')

      const hasActiveChild = item.children.some((child) => child.path === currentPath)

      return `<div class="nav-group${hasActiveChild ? ' expanded' : ''}" data-group="${item.title}">
        <button class="nav-group-header" type="button">
          <span>${item.title}</span>
          <svg class="nav-arrow" width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
            <path d="M4 2L8 6L4 10" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>
          </svg>
        </button>
        <div class="nav-group-items">
          ${childrenHtml}
        </div>
      </div>`
    }

    const isActive = item.path === currentPath
    return `<a class="nav-item top-level${isActive ? ' active' : ''}" href="${prefix}${item.path.replace('.md', '.html')}">${item.title}</a>`
  })

  return `<div class="nav-brand">
      <img class="nav-brand-logo" src="${prefix}static/icons/app-logo.png" alt="BingoCodeIDE" />
      <div>
        <div class="nav-brand-text">BingoCode</div>
        <div class="nav-brand-tag">帮助文档</div>
      </div>
    </div>
    <div class="search-wrapper">
      <div class="search-box">
        <svg class="search-icon" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path d="M7 12A5 5 0 1 0 7 2a5 5 0 0 0 0 10zM14 14l-3.5-3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <input type="text" id="search-input" class="search-input" placeholder="搜索文档…" autocomplete="off" />
        <div id="search-results" class="search-results"></div>
      </div>
    </div>
    <div class="nav-section-title">文档</div>
    ${items.join('\n')}`
}

// ─── HTML 模板 ───

function getTemplate(): string {
  return readFileSync(join(TEMPLATE_DIR, 'page.html'), 'utf-8')
}

// ─── 截图占位符处理 ───
// 支持两种写法：
//   1. <!-- screenshot: editor/sprite-editor.png -->
//   2. <!-- screenshot: 路径 | 说明文字 -->
// 图片存在则直接显示；不存在时显示占位框，提示需要补哪张图。

function processScreenshots(html: string, prefix: string): string {
  return html.replace(/<!--\s*screenshot:\s*(.*?)\s*-->/g, (_match, raw: string) => {
    const [filePart, captionPart] = raw.split('|')
    const file = filePart.trim()
    const caption = (captionPart || '').trim()
    const safeFile = file.replace(/^\/+/, '')
    const imagePath = join(STATIC_DIR, 'screenshots', safeFile)
    const src = `${prefix}static/screenshots/${safeFile}`

    if (existsSync(imagePath)) {
      return `<figure class="screenshot-figure">
        <img src="${src}" alt="${caption}" loading="lazy" />
        ${caption ? `<figcaption class="screenshot-caption">${caption}</figcaption>` : ''}
      </figure>`
    }

    return `<div class="screenshot-placeholder">
      <svg class="shot-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">
        <rect x="3" y="4" width="18" height="16" rx="2"/>
        <circle cx="8.5" cy="9.5" r="1.5"/>
        <path d="m4 16 5-4 4 3 3-2 4 3"/>
      </svg>
      <div class="shot-title">待补充截图</div>
      <span class="shot-file">${safeFile}</span>
      <p class="shot-desc">${caption || '把截图放到 docs/static/screenshots/ 下的同名路径，重新构建后会自动替换此占位框。'}</p>
      <p class="shot-hint">截图尺寸不限，页面会自动缩放并裁掉透明边距。</p>
    </div>`
  })
}

// ─── 标题锚点与本页目录 ───

interface Heading {
  level: number
  id: string
  text: string
}

function slugify(text: string): string {
  return text
    .trim()
    .toLowerCase()
    .replace(/[\s\u3000]+/g, '-')
    .replace(/[^\p{L}\p{N}_-]/gu, '')
}

function addHeadingIds(html: string): { html: string; headings: Heading[] } {
  const headings: Heading[] = []
  const used = new Map<string, number>()

  const result = html.replace(/<h([234])>([\s\S]*?)<\/h\1>/g, (match, level: string, inner: string) => {
    const text = inner
      .replace(/<[^>]+>/g, '')
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&quot;/g, '"')
      .trim()

    let id = slugify(text) || `section-${headings.length + 1}`
    const count = used.get(id) || 0
    used.set(id, count + 1)
    if (count > 0) id = `${id}-${count + 1}`

    headings.push({ level: Number(level), id, text })
    return `<h${level} id="${id}">${inner}</h${level}>`
  })

  return { html: result, headings }
}

// ─── 处理内容中的链接 ───

// 源 Markdown 与产出的 HTML 相对目录深度一致，所以作者写的相对路径（同级 xx.md、
// 上级 ../api/xx.md、根目录 page.md）都可以原样沿用，只需把扩展名换成 .html。
// 不能再人为加 prefix，否则子目录页面里的同级链接会变成 ../xx.html 而失效。
function processLinks(html: string): string {
  return html.replace(/href="([^"#?]+\.md)([^"]*)"/g, (_match, path: string, rest: string) => {
    if (path.startsWith('http')) return `href="${path}${rest}"`
    return `href="${path.replace(/\.md$/, '.html')}${rest}"`
  })
}

// ─── 构建单个页面 ───

function buildPage(mdPath: string, template: string, searchIndex: string): void {
  const mdFullPath = join(CONTENT_DIR, mdPath)
  if (!existsSync(mdFullPath)) {
    console.warn(`⚠️  跳过不存在的文件: ${mdPath}`)
    return
  }

  const prefix = getPrefix(mdPath)
  const mdContent = readFileSync(mdFullPath, 'utf-8')

  // 首页由整段 HTML 组成：直接使用，避免 Markdown 解析打断卡片结构
  const isHome = mdPath === 'index.md'
  const rawHtml = isHome ? mdContent : (marked.parse(mdContent) as string)

  let content = processLinks(processScreenshots(rawHtml, prefix))

  // 首页不生成锚点，保持一个干净的开场
  if (!isHome) {
    content = addHeadingIds(content).html
  }

  const titleMatch =
    mdContent.match(/^#\s+(.+)/m) || mdContent.match(/<h1[^>]*>([\s\S]*?)<\/h1>/)
  const pageTitle = titleMatch
    ? titleMatch[1].replace(/<[^>]+>/g, '').trim()
    : '帮助文档'

  const fullHtml = template
    .replace(/\{\{PAGE_TITLE\}\}/g, pageTitle)
    .replace('{{SIDEBAR}}', generateSidebar(mdPath))
    .replace('{{CONTENT}}', content)
    .replace('{{HOME_CLASS}}', isHome ? ' is-home' : '')
    .replace('{{SEARCH_INDEX}}', searchIndex)
    .replace(/\{\{RELATIVE_PATH\}\}/g, prefix)
    .replace(/\{\{BUILD_STAMP\}\}/g, BUILD_STAMP)
    .replace(/\{\{VERSION\}\}/g, VERSION)

  const outPath = join(DIST_DIR, mdPath.replace('.md', '.html'))
  mkdirSync(dirname(outPath), { recursive: true })
  writeFileSync(outPath, fullHtml, 'utf-8')
  console.log(`✅ ${mdPath} → ${relative(DIST_DIR, outPath)}`)
}

// ─── 复制静态资源 ───

function copyDirRecursive(src: string, dest: string, skip?: Set<string>): void {
  if (!existsSync(src)) return
  for (const entry of readdirSync(src)) {
    if (skip && skip.has(entry)) continue
    const srcPath = join(src, entry)
    const destPath = join(dest, entry)
    if (statSync(srcPath).isDirectory()) {
      mkdirSync(destPath, { recursive: true })
      copyDirRecursive(srcPath, destPath)
    } else {
      writeFileSync(destPath, readFileSync(srcPath))
    }
  }
}

function copyStatic(): void {
  const distStatic = join(DIST_DIR, 'static')
  mkdirSync(distStatic, { recursive: true })

  // screenshots 单独处理：顺手裁掉 macOS 窗口截图自带的透明外框
  copyDirRecursive(STATIC_DIR, distStatic, new Set(['screenshots']))
  copyScreenshots()
  console.log('📁 静态资源已复制')
}

// 找到能 import PIL 的 Python；找不到就退回原样复制
function findPythonWithPillow(): string | null {
  const candidates = [
    join(REPO_ROOT, 'engine/venv/bin/python'),
    join(REPO_ROOT, 'engine/venv/bin/python3'),
    join(REPO_ROOT, 'engine/venv/Scripts/python.exe'),
    'python3',
    'python',
  ]
  for (const python of candidates) {
    try {
      execFileSync(python, ['-c', 'import PIL'], { stdio: 'ignore' })
      return python
    } catch {
      // 试下一个
    }
  }
  return null
}

function copyScreenshots(): void {
  const src = join(STATIC_DIR, 'screenshots')
  const dest = join(DIST_DIR, 'static/screenshots')
  mkdirSync(dest, { recursive: true })
  if (!existsSync(src)) return

  const python = findPythonWithPillow()
  if (!python) {
    console.warn('⚠️  未找到带 Pillow 的 Python，截图按原样复制（透明外框不会被裁掉）')
    copyDirRecursive(src, dest)
    return
  }

  execFileSync(python, [join(DOCS_ROOT, 'trim-screenshots.py'), src, dest], { stdio: 'inherit' })
}

// ─── 收集所有 Markdown 文件 ───

function collectMarkdownFiles(dir: string, prefix: string = ''): string[] {
  const files: string[] = []
  if (!existsSync(dir)) return files

  for (const entry of readdirSync(dir)) {
    const fullPath = join(dir, entry)
    const relPath = prefix ? `${prefix}/${entry}` : entry
    if (statSync(fullPath).isDirectory()) {
      files.push(...collectMarkdownFiles(fullPath, relPath))
    } else if (entry.endsWith('.md')) {
      files.push(relPath)
    }
  }
  return files
}

// ─── 构建搜索索引 ───

function buildSearchIndex(mdFiles: string[]): string {
  const index = mdFiles.map((mdPath) => {
    const mdFullPath = join(CONTENT_DIR, mdPath)
    const content = readFileSync(mdFullPath, 'utf-8')

    const titleMatch =
      content.match(/^#\s+(.+)/m) || content.match(/<h1[^>]*>([\s\S]*?)<\/h1>/)
    const title = titleMatch
      ? titleMatch[1].replace(/<[^>]+>/g, '').trim()
      : mdPath.replace('.md', '')

    const cleanContent = content
      .replace(/```[\s\S]*?```/g, '')
      .replace(/<!--[\s\S]*?-->/g, '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/#{1,6}\s+/g, '')
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
      .replace(/[*_`]/g, '')
      .replace(/\s+/g, ' ')
      .trim()
      .substring(0, 600)

    return {
      title,
      content: cleanContent,
      path: './' + mdPath.replace('.md', '.html'),
    }
  })

  return JSON.stringify(index)
}

// ─── 主函数 ───

function main() {
  console.log('🔨 开始构建 BingoCode 帮助文档…\n')

  mkdirSync(DIST_DIR, { recursive: true })

  const template = getTemplate()
  console.log('📄 模板已加载')

  const mdFiles = collectMarkdownFiles(CONTENT_DIR)
  console.log(`📚 找到 ${mdFiles.length} 个文档文件`)

  const searchIndex = buildSearchIndex(mdFiles)
  console.log('🔍 搜索索引已构建')

  for (const mdFile of mdFiles) {
    buildPage(mdFile, template, searchIndex)
  }

  copyStatic()

  console.log('\n✨ 构建完成！输出目录: docs/dist/')
  console.log('💡 在浏览器中打开 docs/dist/index.html 预览')
}

main()
