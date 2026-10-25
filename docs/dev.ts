#!/usr/bin/env node
/**
 * 帮助文档本地开发服务器
 * 监听 content/ static/ templates/ 变化 → 自动重建 → 浏览器自动刷新
 *
 * 用法：pnpm docs:dev
 */

import { createServer } from 'node:http'
import { readFile } from 'node:fs/promises'
import { watch } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { dirname, join, resolve, extname, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const DOCS_ROOT = dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = dirname(DOCS_ROOT)
const DIST_DIR = join(DOCS_ROOT, 'dist')
const WATCH_DIRS = ['content', 'static', 'templates'].map((dir) => join(DOCS_ROOT, dir))
const PORT = Number(process.env.DOCS_PORT || 4322)

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.md': 'text/plain; charset=utf-8',
}

/** 构建版本号，页面轮询它来判断是否需要刷新 */
let stamp = ''

function build() {
  execFileSync(join(REPO_ROOT, 'node_modules', '.bin', 'tsx'), ['docs/build.ts'], {
    cwd: REPO_ROOT,
    stdio: 'inherit',
  })
  stamp = Date.now().toString(36)
}

function scheduleBuild() {
  let timer: NodeJS.Timeout | null = null
  return () => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      try {
        build()
        console.log(`[docs] 已更新 ${new Date().toLocaleTimeString()}`)
      } catch (error) {
        console.error('[docs] 构建失败：', error)
      }
    }, 120)
  }
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url || '/', 'http://localhost')

  if (url.pathname === '/__dev') {
    res.writeHead(200, { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' })
    res.end(stamp)
    return
  }

  let pathname = decodeURIComponent(url.pathname)
  if (pathname.endsWith('/')) pathname += 'index.html'

  const filePath = resolve(DIST_DIR, '.' + pathname)
  if (filePath !== DIST_DIR && !filePath.startsWith(DIST_DIR + sep)) {
    res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' })
    res.end('Forbidden')
    return
  }

  try {
    const data = await readFile(filePath)
    res.writeHead(200, {
      'Content-Type': MIME[extname(filePath).toLowerCase()] || 'application/octet-stream',
      'Cache-Control': 'no-store',
    })
    res.end(data)
  } catch {
    res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' })
    res.end('Not found')
  }
})

build()

server.on('error', (error: NodeJS.ErrnoException) => {
  if (error.code === 'EADDRINUSE') {
    console.error(`端口 ${PORT} 已被占用，先关掉旧的预览服务，或用 DOCS_PORT=4323 pnpm docs:dev`)
    process.exit(1)
  }
  throw error
})

server.listen(PORT, () => {
  const reload = scheduleBuild()
  for (const dir of WATCH_DIRS) watch(dir, { recursive: true }, reload)
  console.log(`[docs] 已启动 http://localhost:${PORT} （修改内容或替换截图后自动刷新）`)
})
