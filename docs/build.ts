#!/usr/bin/env node
/**
 * BingoCodeIDE 帮助文档构建脚本
 * 将 content/ 下的 Markdown 文件转换为带侧边栏的静态 HTML 页面
 */

import { readFileSync, writeFileSync, readdirSync, statSync, mkdirSync, existsSync } from 'fs'
import { join, relative, dirname, basename } from 'path'
import { fileURLToPath } from 'url'
import { Marked } from 'marked'
import hljs from 'highlight.js'

// ─── 路径配置 ───

const __filename = fileURLToPath(import.meta.url)
const DOCS_ROOT = dirname(__filename)
const CONTENT_DIR = join(DOCS_ROOT, 'content')
const TEMPLATE_DIR = join(DOCS_ROOT, 'templates')
const DIST_DIR = join(DOCS_ROOT, 'dist')
const STATIC_DIR = join(DOCS_ROOT, 'static')

// ─── Markdown 解析器配置 ───

const marked = new Marked({
  gfm: true,
  breaks: false,
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
          <button class="copy-btn" onclick="copyCode(this)">复制</button>
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
    path: 'getting-started/install.md',
    children: [
      { title: '安装与环境配置', path: 'getting-started/install.md' },
      { title: '第一个游戏', path: 'getting-started/first-game.md' },
      { title: '核心概念', path: 'getting-started/basic-concepts.md' },
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
      { title: '控制', path: 'api/control.md' },
      { title: '声音', path: 'api/sound.md' },
      { title: '地图', path: 'api/map.md' },
      { title: '工具函数', path: 'api/tools.md' },
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

function generateSidebar(currentPath: string): string {
  // 计算当前页面的深度，确定需要多少 ../ 回到根目录
  const depth = currentPath.split('/').length - 1
  const prefix = depth > 0 ? '../'.repeat(depth) : './'

  const items = NAV_STRUCTURE.map((item) => {
    if (item.children) {
      const childrenHtml = item.children
        .map((child) => {
          const isActive = child.path === currentPath
          return `<a class="nav-item${isActive ? ' active' : ''}" href="${prefix}${child.path.replace('.md', '.html')}">${child.title}</a>`
        })
        .join('\n')

      // 判断当前分组是否包含活动页面
      const hasActiveChild = item.children.some((c) => c.path === currentPath)

      return `<div class="nav-group${hasActiveChild ? ' expanded' : ''}">
        <button class="nav-group-header" onclick="toggleNavGroup(this)">
          <span>${item.title}</span>
          <svg class="nav-arrow" width="12" height="12" viewBox="0 0 12 12">
            <path d="M4 2L8 6L4 10" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round"/>
          </svg>
        </button>
        <div class="nav-group-items">
          ${childrenHtml}
        </div>
      </div>`
    } else {
      const isActive = item.path === currentPath
      return `<a class="nav-item top-level${isActive ? ' active' : ''}" href="${prefix}${item.path.replace('.md', '.html')}">${item.title}</a>`
    }
  })

  return `<div class="nav-brand">
      <img class="nav-brand-logo" src="${prefix}static/icons/app-logo.png" alt="BingoCodeIDE" />
      <div>
        <div class="nav-brand-text">BingoCodeIDE</div>
        <div class="nav-brand-tag">帮助文档</div>
      </div>
    </div>
    <div class="search-wrapper">
      <div class="search-box">
        <svg class="search-icon" viewBox="0 0 16 16" fill="none">
          <path d="M7 12A5 5 0 1 0 7 2a5 5 0 0 0 0 10zM14 14l-3.5-3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <input type="text" id="search-input" class="search-input" placeholder="搜索文档..." />
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

function processScreenshots(html: string, mdPath: string): string {
  // 处理 <!-- screenshot: ... --> 注释
  return html.replace(
    /<!--\s*screenshot:\s*(.*?)\s*-->\s*<!--\s*alt:\s*(.*?)\s*-->\s*<!--\s*description:\s*(.*?)\s*-->/g,
    (_, src, alt, desc) => {
      const imgSrc = `static/screenshots/${src}`
      return `<div class="screenshot-placeholder">
        <img src="${imgSrc}" alt="${alt}" loading="lazy" />
        <p class="screenshot-desc">${desc}</p>
      </div>`
    }
  )
}

// ─── 处理内容中的链接 ───

function processLinks(html: string, mdPath: string): string {
  // 计算当前页面的深度
  const depth = mdPath.split('/').length - 1
  const prefix = depth > 0 ? '../'.repeat(depth) : './'

  // 修复相对链接 - 匹配 href="xxx.md" 格式
  return html.replace(/href="([^"]*\.md)"/g, (match, path) => {
    // 跳过已经处理过的链接
    if (path.startsWith('./') || path.startsWith('../') || path.startsWith('http')) {
      return match
    }
    return `href="${prefix}${path}"`
  })
}

// ─── 构建单个页面 ───

function buildPage(mdPath: string, template: string, searchIndex: string): void {
  const mdFullPath = join(CONTENT_DIR, mdPath)
  if (!existsSync(mdFullPath)) {
    console.warn(`⚠️  跳过不存在的文件: ${mdPath}`)
    return
  }

  const mdContent = readFileSync(mdFullPath, 'utf-8')
  const htmlContent = marked.parse(mdContent) as string
  const processedContent = processLinks(processScreenshots(htmlContent, mdPath), mdPath)

  // 提取标题
  const titleMatch = mdContent.match(/^#\s+(.+)/m)
  const pageTitle = titleMatch ? titleMatch[1] : 'BingoCodeIDE 帮助文档'

  // 生成侧边栏
  const sidebar = generateSidebar(mdPath)

  // 组装完整 HTML
  const fullHtml = template
    .replace('{{PAGE_TITLE}}', pageTitle)
    .replace('{{SIDEBAR}}', sidebar)
    .replace('{{CONTENT}}', processedContent)
    .replace('{{SEARCH_INDEX}}', searchIndex)
    .replace(
      '{{RELATIVE_PATH}}',
      mdPath.split('/').length > 1 ? '../'.repeat(mdPath.split('/').length - 1) : ''
    )

  // 输出文件
  const outPath = join(DIST_DIR, mdPath.replace('.md', '.html'))
  const outDir = dirname(outPath)
  mkdirSync(outDir, { recursive: true })
  writeFileSync(outPath, fullHtml, 'utf-8')
  console.log(`✅ ${mdPath} → ${relative(DIST_DIR, outPath)}`)
}

// ─── 复制静态资源 ───

function copyStatic(): void {
  const distStatic = join(DIST_DIR, 'static')
  mkdirSync(distStatic, { recursive: true })

  function copyDir(src: string, dest: string) {
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

  copyDir(STATIC_DIR, distStatic)
  console.log('📁 静态资源已复制')
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
  const index = mdFiles.map(mdPath => {
    const mdFullPath = join(CONTENT_DIR, mdPath)
    const content = readFileSync(mdFullPath, 'utf-8')
    
    // 提取标题
    const titleMatch = content.match(/^#\s+(.+)/m)
    const title = titleMatch ? titleMatch[1] : mdPath.replace('.md', '')
    
    // 清理内容用于搜索（移除代码块、特殊字符）
    const cleanContent = content
      .replace(/```[\s\S]*?```/g, '') // 移除代码块
      .replace(/#{1,6}\s+/g, '') // 移除标题标记
      .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // 链接转文本
      .replace(/[*_`]/g, '') // 移除格式符号
      .replace(/\n+/g, ' ') // 换行转空格
      .trim()
      .substring(0, 500) // 限制长度

    const htmlPath = './' + mdPath.replace('.md', '.html')
    
    return { title, content: cleanContent, path: htmlPath }
  })

  return JSON.stringify(index)
}

// ─── 主函数 ───

function main() {
  console.log('🔨 开始构建 BingoCodeIDE 帮助文档...\n')

  // 确保输出目录存在
  mkdirSync(DIST_DIR, { recursive: true })

  // 加载模板
  const template = getTemplate()
  console.log('📄 模板已加载')

  // 收集所有 Markdown 文件
  const mdFiles = collectMarkdownFiles(CONTENT_DIR)
  console.log(`📚 找到 ${mdFiles.length} 个文档文件`)

  // 构建搜索索引
  const searchIndex = buildSearchIndex(mdFiles)
  console.log('🔍 搜索索引已构建')

  // 构建每个页面
  for (const mdFile of mdFiles) {
    buildPage(mdFile, template, searchIndex)
  }

  // 复制静态资源
  copyStatic()

  console.log('\n✨ 构建完成！输出目录: docs/dist/')
  console.log('💡 在浏览器中打开 docs/dist/index.html 预览')
}

main()
