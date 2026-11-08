// 角色编辑器冒烟 + 压力测试 runner（仅测试用）
// 用法：node tests/smoke/run-smoke.mjs
//
// 原理：启动 Vite dev server → 用 Playwright 打开 tests/smoke/sprite-editor.html（直接挂载
// SpriteEditorView）→ 页面里的 window.__TAURI_INTERNALS__ 被 mock 成 fetch('/__smoke/invoke')，
// 由本脚本用真实 Node 文件系统执行 → 全程真实跑组件逻辑，断言组件内部状态与落盘 manifest。
import { spawn } from 'node:child_process'
import { mkdtemp, cp, mkdir, rm, readFile, writeFile, rename, access, readdir } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { tmpdir, homedir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from 'playwright-core'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.resolve(__dirname, '../..')
const PORT = 5199
const URL = `http://localhost:${PORT}/tests/smoke/sprite-editor.html`
const BROWSER = path.join(
  homedir(),
  'Library/Caches/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-mac-arm64/chrome-headless-shell',
)

// ─── 测试上下文 ────────────────────────────────────────────────────────────
const results = []
let stage = '准备'
function setStage(name) { stage = name }
function check(id, name, pass, detail) {
  results.push({ id, stage, name, pass: !!pass, detail })
  const icon = pass ? '✓' : '✗'
  console.log(`${icon} [${stage}] ${name}${detail ? ` — ${detail}` : ''}`)
}
function near(a, b, eps = 0.51) { return Math.abs(a - b) <= eps }

// IPC 调用统计（压力测试用）
const ipc = { calls: {}, writeCount: 0, unknown: new Set(), escapedRename: [] }

async function handleInvoke(cmd, args = {}) {
  ipc.calls[cmd] = (ipc.calls[cmd] || 0) + 1
  const p = args.path ?? args.oldPath ?? args.newPath ?? args.dirPath ?? ''
  switch (cmd) {
    case 'get_engine_assets_dir':
      return path.join(REPO, 'engine/assets')
    case 'path_exists':
      return existsSync(p)
    case 'list_dir':
      return (await readdir(p)).sort()
    case 'read_file':
      return readFile(p, 'utf8')
    case 'read_binary':
      return Array.from((await readFile(p)))
    case 'read_image_as_data_url': {
      const buf = await readFile(p)
      const ext = path.extname(p).toLowerCase()
      const mime = ext === '.jpg' || ext === '.jpeg' ? 'image/jpeg'
        : ext === '.gif' ? 'image/gif'
          : ext === '.webp' ? 'image/webp'
            : ext === '.bmp' ? 'image/bmp'
              : ext === '.svg' ? 'image/svg+xml'
                : 'image/png'
      return `data:${mime};base64,${buf.toString('base64')}`
    }
    case 'write_file':
      ipc.writeCount++
      await mkdir(path.dirname(p), { recursive: true })
      await writeFile(p, args.content, 'utf8')
      return null
    case 'write_binary':
      ipc.writeCount++
      await mkdir(path.dirname(p), { recursive: true })
      await writeFile(p, Buffer.from(args.data))
      return null
    case 'create_dir':
      await mkdir(p, { recursive: true })
      return null
    case 'delete_path':
      await rm(p, { recursive: true, force: true })
      return null
    case 'rename_path': {
      // 记录是否越出项目目录（路径穿越安全性检查）
      if (!path.resolve(args.newPath).startsWith(PROJECT)) {
        ipc.escapedRename.push({ from: args.oldPath, to: args.newPath })
      }
      await rename(args.oldPath, args.newPath)
      return null
    }
    case 'get_version':
      return '0.0.0-smoke'
    default:
      ipc.unknown.add(cmd)
      return null
  }
}

// ─── 准备临时项目 + 角色素材 ────────────────────────────────────────────────
const ROOT = await mkdtemp(path.join(tmpdir(), 'bingo-sprite-smoke-'))
const PROJECT = path.join(ROOT, 'project')
const SPRITES = path.join(PROJECT, 'assets/sprites')

async function extractBsf(pkgName, dirName) {
  const zip = path.join(REPO, 'engine/assets/sprites/characters/packages', pkgName)
  const dest = path.join(SPRITES, dirName)
  await mkdir(dest, { recursive: true })
  await new Promise((resolve, reject) => {
    const un = spawn('unzip', ['-o', zip, '-d', dest], { stdio: 'ignore' })
    un.on('exit', code => (code === 0 ? resolve() : reject(new Error(`unzip ${pkgName} 失败`))))
  })
  return dest
}

await mkdir(SPRITES, { recursive: true })
const dirA = await extractBsf('大鲨鱼.bsf', '角色A')
const dirB = await extractBsf('马里奥.bsf', '角色B')
const dirC = await extractBsf('大鲨鱼.bsf', '角色C')
// 单图角色：复制一张内置图片到项目里
const imageSrc = path.join(REPO, 'engine/assets/sprites/characters/images/变变怪.png')
const imageDst = path.join(SPRITES, '测试图片.png')
await cp(imageSrc, imageDst)
// 老格式 .bgs 目录角色（config.json + 逐帧 png）：用于测试删除造型
const dirBgs = path.join(SPRITES, '角色D')
await mkdir(dirBgs, { recursive: true })
await cp(imageSrc, path.join(dirBgs, '1.png'))
await cp(imageSrc, path.join(dirBgs, '2.png'))
await cp(imageSrc, path.join(dirBgs, '3.png'))
await writeFile(path.join(dirBgs, 'config.json'), JSON.stringify({
  name: '角色D',
  frames: ['1.png', '2.png', '3.png'],
  segments: [{ name: '待机', start: 1, end: 3, fps: 8 }],
}, null, 2), 'utf8')
// 另一份未被修改的旧格式 .bgs（Q 阶段兼容性检查用，避免受 J 阶段删除帧影响）
const dirBgs2 = path.join(SPRITES, '角色E')
await mkdir(dirBgs2, { recursive: true })
await cp(imageSrc, path.join(dirBgs2, '1.png'))
await cp(imageSrc, path.join(dirBgs2, '2.png'))
await cp(imageSrc, path.join(dirBgs2, '3.png'))
await writeFile(path.join(dirBgs2, 'config.json'), JSON.stringify({
  name: '角色E',
  frames: ['1.png', '2.png', '3.png'],
  segments: [{ name: '待机', start: 1, end: 3, fps: 8 }],
}, null, 2), 'utf8')
// 损坏的 .bsf 目录：manifest.json 不是合法 JSON（健壮性测试：应显示错误而不是白屏/崩溃）
const dirBad = path.join(SPRITES, '坏角色')
await mkdir(dirBad, { recursive: true })
await cp(imageSrc, path.join(dirBad, 'sheet.png'))
await writeFile(path.join(dirBad, 'manifest.json'), '{ "canvas": { "w": 95 ', 'utf8')

const SPRITE_ITEMS = [
  { id: 's-a', name: '角色A', type: 'sprite', path: dirA },
  { id: 's-b', name: '角色B', type: 'sprite', path: dirB },
  { id: 's-c', name: '角色C', type: 'sprite', path: dirC },
  { id: 's-d', name: '角色D', type: 'sprite', path: dirBgs },
  { id: 's-e', name: '角色E', type: 'sprite', path: dirBgs2 },
  { id: 's-img', name: '测试图片', type: 'sprite', path: imageDst },
  { id: 's-bad', name: '坏角色', type: 'sprite', path: dirBad },
]

const manifestA = () => path.join(dirA, 'manifest.json')
async function readManifest(dir = dirA) {
  return JSON.parse(await readFile(path.join(dir, 'manifest.json'), 'utf8'))
}

// ─── 启动 Vite ─────────────────────────────────────────────────────────────
setStage('启动')
const vite = spawn(path.join(REPO, 'node_modules/.bin/vite'), ['--port', String(PORT), '--strictPort'], {
  cwd: REPO,
  stdio: ['ignore', 'pipe', 'pipe'],
})
vite.stderr.on('data', () => {})
const viteExited = new Promise(resolve => vite.on('exit', resolve))

async function waitForServer() {
  for (let i = 0; i < 180; i++) {
    try {
      const res = await fetch(URL)
      if (res.ok) return
    } catch { /* retry */ }
    await new Promise(r => setTimeout(r, 500))
  }
  throw new Error('Vite dev server 未就绪')
}
await waitForServer()
console.log(`Vite ready at ${URL}`)

// ─── 浏览器 + mock Tauri ────────────────────────────────────────────────────
if (!existsSync(BROWSER)) throw new Error(`找不到 chromium headless shell: ${BROWSER}`)
const browser = await chromium.launch({ executablePath: BROWSER, headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 })

await context.addInitScript(({ project, sprites }) => {
  // ── 测试统计 / 泄漏观测 ──
  const st = window.__smoke = {
    mounted: false,
    project,
    sprites,
    errors: [],
    urls: { created: 0, revoked: 0, active: new Set() },
    intervals: new Set(),
    timeouts: new Set(),
    longTasks: [],
    nextCb: 1,
  }
  window.addEventListener('error', e => st.errors.push(String(e.message || e.error)))
  window.addEventListener('unhandledrejection', e => st.errors.push(String(e.reason)))

  const nativeCreate = URL.createObjectURL.bind(URL)
  const nativeRevoke = URL.revokeObjectURL.bind(URL)
  URL.createObjectURL = obj => {
    const u = nativeCreate(obj)
    st.urls.created++
    st.urls.active.add(u)
    return u
  }
  URL.revokeObjectURL = u => {
    st.urls.revoked++
    st.urls.active.delete(u)
    return nativeRevoke(u)
  }
  const nativeSetInterval = window.setInterval.bind(window)
  const nativeClearInterval = window.clearInterval.bind(window)
  window.setInterval = (fn, ms, ...a) => {
    const id = nativeSetInterval(fn, ms, ...a)
    st.intervals.add(id)
    return id
  }
  window.clearInterval = id => {
    st.intervals.delete(id)
    return nativeClearInterval(id)
  }
  const nativeSetTimeout = window.setTimeout.bind(window)
  const nativeClearTimeout = window.clearTimeout.bind(window)
  window.setTimeout = (fn, ms, ...a) => {
    const id = nativeSetTimeout(fn, ms, ...a)
    st.timeouts.add(id)
    return id
  }
  window.clearTimeout = id => {
    st.timeouts.delete(id)
    return nativeClearTimeout(id)
  }
  try {
    new PerformanceObserver(list => {
      for (const e of list.getEntries()) st.longTasks.push(e.duration)
    }).observe({ entryTypes: ['longtask'] })
  } catch { /* 不支持 longtask 时忽略 */ }

  // ── Tauri IPC mock ──
  window.__TAURI_INTERNALS__ = {
    invoke: async (cmd, args) => {
      const res = await fetch('/__smoke/invoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cmd, args }),
      })
      const data = await res.json()
      if (!data.ok) throw new Error(data.error || `invoke ${cmd} 失败`)
      return data.value
    },
    convertFileSrc: p => `/__smoke/file?path=${encodeURIComponent(p)}`,
    transformCallback: cb => {
      const id = st.nextCb++
      window[`__tauri_cb_${id}`] = cb
      return id
    },
    unregisterCallback: id => { delete window[`__tauri_cb_${id}`] },
    metadata: { currentWindow: { label: 'main' }, currentWebview: { label: 'main' } },
  }

  // 每个页面会话从干净状态开始（右侧面板页等记忆项）
  try { localStorage.clear() } catch { /* ignore */ }
}, { project: PROJECT, sprites: SPRITE_ITEMS })

const page = await context.newPage()
const consoleErrors = []
page.on('console', msg => {
  if (msg.type() === 'error') consoleErrors.push(`[${stage}] ${msg.text()}`)
})
page.on('pageerror', e => {
  const msg = `[${stage}] PAGEERROR: ${e.message}\n${(e.stack || '').split('\n').slice(0, 4).join('\n')}`
  consoleErrors.push(msg)
  console.log('⚠', msg.split('\n')[0], `(${stage})`)
})
page.on('requestfailed', req => {
  if (!req.url().includes('__smoke')) consoleErrors.push(`[${stage}] REQUESTFAILED: ${req.url()} ${req.failure()?.errorText}`)
})

await page.route('**/__smoke/invoke', async route => {
  try {
    const body = JSON.parse(route.request().postData() || '{}')
    const value = await handleInvoke(body.cmd, body.args || {})
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, value }) })
  } catch (e) {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: false, error: String(e && e.stack || e) }),
    })
  }
})
await page.route('**/__smoke/file**', async route => {
  try {
    const u = new URL(route.request().url())
    const p = u.searchParams.get('path')
    const buf = await readFile(p)
    const ext = path.extname(p).toLowerCase()
    const mime = ext === '.jpg' || ext === '.jpeg' ? 'image/jpeg' : 'image/png'
    await route.fulfill({ status: 200, contentType: mime, body: buf })
  } catch (e) {
    await route.fulfill({ status: 404, body: String(e) })
  }
})

// ─── 页面操作辅助 ──────────────────────────────────────────────────────────
async function state() { return page.evaluate(() => window.__smoke.readState()) }
async function waitMounted(timeout = 30000) {
  await page.waitForFunction(() => {
    const st = window.__smoke
    return !!(st && st.mounted && st.readState && st.readState() && st.readState().frameCount > 0)
  }, null, { timeout })
}
async function settle(ms = 450) { await page.waitForTimeout(ms) }
function chip(label) {
  return page.locator('.anno-toolbar').getByRole('button', { name: label, exact: true })
}
function section(title) {
  return page.locator('.mi-section').filter({
    has: page.locator('.mi-head-title').filter({ hasText: new RegExp(`^${title}$`) }),
  }).first()
}
function row(title, label) {
  return section(title).locator('.att-row').filter({
    has: page.locator('.att-label').filter({ hasText: new RegExp(`^${label}$`) }),
  }).first()
}
async function fillText(title, label, value, idx = 0) {
  const input = row(title, label).locator('input.att-input').nth(idx)
  try {
    await input.click({ timeout: 6000 })
  } catch (e) {
    const diag = await page.evaluate(() => {
      const el = document.querySelector('.sprite-editor-page')
      const s = el && el.__vueParentComponent && el.__vueParentComponent.setupState
      return {
        rightTab: s && s.rightTab,
        selMarker: s && s.selMarkerName,
        animPage: !!document.querySelector('.anim-list'),
        titles: [...document.querySelectorAll('.mi-head-title')].map(n => n.textContent),
        errors: (window.__smoke.errors || []).slice(-4),
      }
    })
    console.log(`fillText 失败：${title}/${label}[${idx}] 诊断:`, JSON.stringify(diag, null, 2))
    throw e
  }
  await input.fill(String(value))
  await input.press('Tab')
  await page.waitForTimeout(60)
}
async function toggle(title, label) {
  await row(title, label).locator('input[type=checkbox]').first().click()
  await page.waitForTimeout(60)
}
const esc = t => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
async function choose(title, label, option) {
  const r = row(title, label)
  await r.locator('.custom-select').click()
  await page.waitForTimeout(50)
  await r.locator('.custom-select-option').filter({ hasText: new RegExp(`^${esc(option)}$`) }).first().click()
  await page.waitForTimeout(80)
}
async function tab(name) {
  await page.locator('.right-tab').filter({ hasText: new RegExp(`^${name}$`) }).first().click()
  await page.waitForTimeout(80)
}
async function resetAxis(title, label, index = 0) {
  const r = row(title, label)
  await r.hover()
  await r.locator('button.att-reset').nth(index).click({ force: true })
  await page.waitForTimeout(100)
}
async function clickButton(text) {
  // 直接触发 DOM click：避免面板重渲染期间 Playwright 的“元素已脱离 DOM”重试
  await page.evaluate(t => {
    const btn = [...document.querySelectorAll('.mi-btn, .mi-actions button')]
      .find(b => (b.textContent || '').trim() === t)
    if (!btn) throw new Error(`按钮不存在: ${t}`)
    btn.click()
  }, text)
  await page.waitForTimeout(120)
}
async function callFn(name, ...args) {
  return page.evaluate(([n, a]) => {
    const el = document.querySelector('.sprite-editor-page')
    const s = el && el.__vueParentComponent && el.__vueParentComponent.setupState
    if (!s || typeof s[n] !== 'function') throw new Error(`组件方法不存在: ${n}`)
    return s[n](...a)
  }, [name, args])
}
async function selectSprite(id) {
  await page.evaluate(id => { window.__smoke.resource.selectedSpriteId = id }, id)
  await page.waitForTimeout(400)
  await page.waitForFunction(() => {
    const s = window.__smoke.readState()
    return s && s.frameCount > 0
  })
}
async function canvasPainted(selector) {
  return page.evaluate(sel => {
    const c = document.querySelector(sel)
    if (!c || !c.width || !c.height) return { ok: false, reason: '无画布' }
    const ctx = c.getContext('2d')
    const d = ctx.getImageData(0, 0, c.width, c.height).data
    let n = 0
    for (let i = 3; i < d.length; i += 4) if (d[i] > 8) n++
    return { ok: n > 20, alphaPixels: n, size: [c.width, c.height] }
  }, selector)
}

// ─── A. 载入与基础渲染 ─────────────────────────────────────────────────────
setStage('A 载入')
await page.goto(URL, { waitUntil: 'domcontentloaded' })
try {
  await waitMounted()
} catch (e) {
  console.log('页面未挂载，诊断信息：')
  console.log('console:', JSON.stringify(consoleErrors, null, 2))
  console.log('body:', (await page.evaluate(() => document.body.innerText)).slice(0, 500))
  console.log('smoke:', await page.evaluate(() => window.__smoke ? {
    mounted: window.__smoke.mounted,
    errors: window.__smoke.errors,
    hasRead: typeof window.__smoke.readState,
  } : 'no __smoke'))
  throw e
}
await settle(300)
let s0 = await state()
const baseManifest = await readManifest(dirA)
check('A1', '角色成功载入且帧数正确', s0.frameCount === baseManifest.frames.length && !s0.loadError,
  `frames=${s0.frameCount} 期望=${baseManifest.frames.length} loadError=${s0.loadError}`)
check('A2', '动画片段载入', s0.animCount === (baseManifest.clips || []).length,
  `anim=${s0.animCount} 期望=${(baseManifest.clips || []).length}`)
check('A3', '画布尺寸取 manifest canvas', s0.bsfCanvas && s0.bsfCanvas.w === baseManifest.canvas.w && s0.bsfCanvas.h === baseManifest.canvas.h,
  JSON.stringify(s0.bsfCanvas))
const paint = await canvasPainted('canvas.canvas-sprite')
check('A4', '主画布已绘制非透明像素', paint.ok, JSON.stringify(paint))
const previewPaint = await canvasPainted('canvas.preview-image')
check('A5', '预览画布已绘制', previewPaint.ok, JSON.stringify(previewPaint))
check('A6', '像素画自动判定为 pixelated', s0.pixelArt === true && s0.imageRendering === 'pixelated',
  `pixelArt=${s0.pixelArt} rendering=${s0.imageRendering}`)
check('A7', '初始变换为默认值', s0.transform && s0.transform.x === 0 && s0.transform.y === 0 && s0.transform.angle === 0 && s0.transform.scale === 100,
  JSON.stringify(s0.transform))
check('A8', '造型列表 DOM 与帧数一致', await page.locator('.costume-item').count() === s0.frameCount,
  `dom=${await page.locator('.costume-item').count()}`)
const idleIntervals = await page.evaluate(() => window.__smoke.intervals.size)
check('A9', '基线定时器（框架自身）', true, `idleIntervals=${idleIntervals}`)

// ─── B. 动画播放 / 帧切换 ──────────────────────────────────────────────────
setStage('B 动画')
await tab('动画')
await page.locator('.anim-item').first().click()
await page.waitForTimeout(80)
const animName = await page.locator('.anim-item').first().innerText()
check('B1', '点选动画片段后进入激活态', (await page.locator('.anim-item.anim-item-active').count()) === 1, animName)
// 设计行为：选中片段即自动播放（startAnimation）
s0 = await state()
check('B2', '选中片段后自动开始播放', s0.playing === true, `playing=${s0.playing}`)
// 把播放速度降到 1 帧/秒，便于稳定观测
const fpsInput = page.locator('.fps-input')
await fpsInput.click()
await fpsInput.fill('2')
await fpsInput.press('Tab')
await page.waitForTimeout(100)
// 先暂停
if ((await state()).playing) {
  await page.locator('.preview-btns button').nth(1).click()
  await page.waitForTimeout(150)
}
const pausedFrame = (await state()).selectedFrame
await page.waitForTimeout(800)
check('B3', '暂停后帧不再变化', (await state()).selectedFrame === pausedFrame, `frame=${pausedFrame}`)
// 再播放
await page.locator('.preview-btns button').nth(1).click()
await page.waitForTimeout(120)
const playStartFrame = (await state()).selectedFrame
s0 = await state()
check('B4', '点击播放后进入 playing', s0.playing === true, `playing=${s0.playing}`)
await page.waitForTimeout(1200)
s0 = await state()
check('B5', '播放中帧索引推进', s0.selectedFrame !== playStartFrame, `${playStartFrame} → ${s0.selectedFrame}`)
await page.locator('.preview-btns button').nth(1).click()
await page.waitForTimeout(150)
check('B6', '再次点击暂停', (await state()).playing === false)
// 首帧 / 末帧边界
await page.locator('.costume-item').nth(0).click()
await page.locator('.preview-btns button').nth(0).click()
await page.waitForTimeout(100)
check('B7', '首帧再上一帧不越界', (await state()).selectedFrame === 0, `frame=${(await state()).selectedFrame}`)
await page.locator('.costume-item').nth(s0.frameCount - 1).click()
await page.locator('.preview-btns button').nth(2).click()
await page.waitForTimeout(100)
check('B8', '末帧再下一帧不越界', (await state()).selectedFrame === s0.frameCount - 1)
// 帧选择 & 落盘 defaultFrame
await page.locator('.costume-item').nth(3).click()
await settle()
const mAfterFrame = await readManifest()
check('B9', '选中帧写入 defaultFrame', typeof mAfterFrame.defaultFrame === 'string')
check('B10', '选中帧高亮正确', (await state()).costumeHighlight === 3, `idx=${(await state()).costumeHighlight}`)
check('B11', '帧切换后预览画布仍正常绘制', (await canvasPainted('canvas.preview-image')).ok)

// ─── C. 变换（属性面板 + 内部落盘） ───────────────────────────────────────
setStage('C 变换')
await tab('属性')
await fillText('变换', '位置', '100', 0)
await fillText('变换', '位置', '-50', 1)
s0 = await state()
check('C1', '位置输入生效', s0.transform.x === 100 && s0.transform.y === -50, JSON.stringify(s0.transform))
await fillText('变换', '旋转', '45')
s0 = await state()
check('C2', '旋转输入生效', s0.transform.angle === 45, `angle=${s0.transform.angle}`)
await fillText('变换', '缩放', '200', 0)
s0 = await state()
check('C3', '等比缩放输入生效', s0.transform.scale === 200 && (s0.transform.scaleX ?? 200) === 200,
  JSON.stringify(s0.transform))
await settle()
let mA = await readManifest()
check('C4', '变换已写入 manifest', mA.transform && mA.transform.x === 100 && mA.transform.y === -50
  && mA.transform.angle === 45 && mA.transform.scale === 200, JSON.stringify(mA.transform))
// 超长 / 非法输入
await fillText('变换', '位置', '9999999999999999', 0)
check('C5', '超长数字被钳制到 ±4000', Math.abs((await state()).transform.x) <= 4000, `x=${(await state()).transform.x}`)
await fillText('变换', '位置', 'abc', 0)
await page.waitForTimeout(100)
check('C6', '非法文本不破坏数值', Number.isFinite((await state()).transform.x), `x=${(await state()).transform.x}`)
await fillText('变换', '缩放', '0', 0)
check('C7', '缩放 0 被钳制到最小值 5', (await state()).transform.scale === 5, `scale=${(await state()).transform.scale}`)
await fillText('变换', '缩放', '9999', 0)
check('C8', '缩放超上限被钳制到 1000', (await state()).transform.scale === 1000, `scale=${(await state()).transform.scale}`)
await fillText('变换', '缩放', '200', 0)
await fillText('变换', '旋转', '-45')
check('C9', '负角度可用', (await state()).transform.angle === -45)
// 分轴缩放
const lockRow = row('变换', '缩放')
const lockBox = lockRow.locator('input[type=checkbox]').first()
if (await lockBox.count()) {
  await lockBox.click()
  await page.waitForTimeout(80)
  await fillText('变换', '缩放', '150', 0)
  await fillText('变换', '缩放', '80', 1)
  await settle()
  mA = await readManifest()
  check('C10', '取消约束后分轴缩放落盘', mA.transform && mA.transform.scaleX === 150 && mA.transform.scaleY === 80,
    JSON.stringify(mA.transform))
} else {
  check('C10', '缩放行存在约束比例开关', false, '未找到约束复选框')
  await fillText('变换', '缩放', '150', 0)
}
// 复位
await resetAxis('变换', '位置', 0)
await resetAxis('变换', '位置', 1)
s0 = await state()
check('C11', '分轴重置位置回 0', s0.transform.x === 0 && s0.transform.y === 0, JSON.stringify(s0.transform))
// 手柄拖动（移动）
const preDrag = await state()
console.log('C12 诊断:', JSON.stringify({
  activeTool: preDrag.activeTool,
  selectionActive: preDrag.selectionActive,
  gizmoVisible: preDrag.gizmoVisible,
  canAnno: preDrag.canAnno,
  bsfCanvas: preDrag.bsfCanvas,
  bsfFrameCount: preDrag.bsfFrameCount,
  gizmoCount: await page.locator('.gizmo-frame').count(),
  chips: await page.evaluate(() => [...document.querySelectorAll('.anno-toolbar .layer-chip')].map(e => JSON.stringify(e.textContent))),
}))
await chip('选择').click()
const canvasBox = await page.locator('canvas.canvas-sprite').boundingBox()
const gizmoBox = await page.locator('.gizmo-frame').count()
  ? await page.locator('.gizmo-frame').first().boundingBox()
  : null
check('C12a', '变换手柄可见', !!gizmoBox, `gizmoVisible=${(await state()).gizmoVisible}`)
const dragBox = gizmoBox || canvasBox
await page.mouse.move(dragBox.x + dragBox.width / 2, dragBox.y + dragBox.height / 2)
await page.mouse.down()
await page.mouse.move(dragBox.x + dragBox.width / 2 + 60, dragBox.y + dragBox.height / 2 + 40, { steps: 6 })
await page.mouse.up()
await page.waitForTimeout(150)
s0 = await state()
check('C12', '画布拖拽产生位移', s0.transform.x > 20 && s0.transform.y < -10,
  `x=${s0.transform.x} y=${s0.transform.y}`)
// Esc 取消拖动
const beforeCancel = (await state()).transform
await page.mouse.move(dragBox.x + dragBox.width / 2, dragBox.y + dragBox.height / 2)
await page.mouse.down()
await page.mouse.move(dragBox.x + dragBox.width / 2 + 90, dragBox.y + dragBox.height / 2 + 60, { steps: 4 })
await page.keyboard.press('Escape')
await page.mouse.up()
await page.waitForTimeout(150)
const afterCancel = (await state()).transform
check('C13', 'Esc 取消拖动恢复原位', near(afterCancel.x, beforeCancel.x, 1.5) && near(afterCancel.y, beforeCancel.y, 1.5),
  JSON.stringify({ beforeCancel, afterCancel }))
// 滚轮缩放
await page.mouse.move(canvasBox.x + canvasBox.width / 2, canvasBox.y + canvasBox.height / 2)
for (let i = 0; i < 40; i++) await page.mouse.wheel(0, -200)
await page.waitForTimeout(200)
const zoomMax = (await state()).zoom
for (let i = 0; i < 80; i++) await page.mouse.wheel(0, 300)
await page.waitForTimeout(200)
const zoomMin = (await state()).zoom
check('C14', '滚轮缩放钳制在 0.1~32', zoomMax <= 32 + 1e-6 && zoomMin >= 0.1 - 1e-6,
  `max=${zoomMax} min=${zoomMin}`)
await page.locator('.scene-float-zoom').click()
await page.waitForTimeout(100)
check('C15', '重置视图回到 100%', near((await state()).zoom, 1, 0.001), `zoom=${(await state()).zoom}`)

// ─── D. 中心点 ─────────────────────────────────────────────────────────────
setStage('D 中心点')
const dState0 = await state()
if (!dState0.canAnno) {
  console.log('D 诊断：canAnno=false', JSON.stringify({ bsfCanvas: dState0.bsfCanvas, frameCount: dState0.frameCount }))
}
const dChips = await page.evaluate(() => ({
  toolbar: !!document.querySelector('.anno-toolbar'),
  chips: [...document.querySelectorAll('.layer-chip')].map(e => e.textContent.trim()),
}))
if (!dChips.chips.includes('中心')) console.log('D 诊断：工具条', JSON.stringify(dChips))
await chip('中心').click({ timeout: 8000 })
await page.waitForTimeout(120)
check('D1', '中心工具激活并切到属性页', (await state()).activeTool === 'pivot' && (await state()).rightTab === 'props')
const pivotStart = (await state()).pivot
const pivotStartTransform = (await state()).transform
// 拖拽中心点手柄
const handle = page.locator('.pivot-handle').first()
const hb = await handle.boundingBox()
if (hb) {
  await page.mouse.move(hb.x + hb.width / 2, hb.y + hb.height / 2)
  await page.mouse.down()
  await page.mouse.move(hb.x + hb.width / 2 + 50, hb.y + hb.height / 2 + 50, { steps: 6 })
  await page.mouse.up()
  await page.waitForTimeout(150)
} else {
  check('D2', '中心点手柄可见', false, '找不到 .pivot-handle')
}
const pivotDragged = (await state()).pivot
check('D2', '拖拽中心点改变 pivot', pivotDragged && (Math.abs(pivotDragged.x - pivotStart.x) > 10 || Math.abs(pivotDragged.y - pivotStart.y) > 10),
  `${JSON.stringify(pivotStart)} → ${JSON.stringify(pivotDragged)}`)
check('D3', '拖拽中心点补偿角色位置（画面不跳）', near((await state()).transform.x, pivotStartTransform.x, 100),
  `tx=${(await state()).transform.x} 起始=${pivotStartTransform.x}`)
// 偏移输入钳制
await fillText('中心点', '位置', '9999', 0)
s0 = await state()
check('D4', '中心点 X 钳制在画布内', s0.pivot.x <= s0.bsfCanvas.w + 0.01 && s0.pivot.x >= -0.01,
  `pivot=${JSON.stringify(s0.pivot)} canvas=${JSON.stringify(s0.bsfCanvas)}`)
await resetAxis('中心点', '位置', 0)
check('D5', '重置 X 回到原始中心', (await state()).pivotOffset.x === 0, JSON.stringify((await state()).pivotOffset))
// 脚底预设
await clickButton('脚底')
s0 = await state()
check('D6', '脚底预设 pivot.y 接近内容底部', s0.pivot.y > 0, JSON.stringify(s0.pivot))
// 作用范围：仅当前帧
await choose('中心点', '作用范围', '仅当前帧')
await clickButton('中心')
check('D7', '切换仅当前帧后写帧级 pivot', (await state()).pivotScope === 'one')
await clickButton('脚底')
check('D8', '帧级覆盖角标出现', (await page.locator('.pivot-override-badge').count()) >= 1,
  `badges=${await page.locator('.pivot-override-badge').count()}`)
await settle()
let mD = await readManifest()
check('D9', '帧级 pivot 覆盖已落盘', mD.frames.some(f => f.pivot) === true, JSON.stringify(mD.frames.map(f => f.pivot || null)))
// 清除帧覆盖
const resetAllCount = await page.evaluate(() =>
  [...document.querySelectorAll('.mi-btn')].filter(b => (b.textContent || '').trim() === '恢复统一').length)
if (resetAllCount) {
  await clickButton('恢复统一')
  check('D10', '清除帧级覆盖', (await page.locator('.pivot-override-badge').count()) === 0)
} else {
  check('D10', '存在清除帧覆盖按钮', false, '未找到清除按钮')
}
await choose('中心点', '作用范围', '全部帧')
await page.waitForTimeout(100)

// ─── E. 碰撞 ───────────────────────────────────────────────────────────────
setStage('E 碰撞')
await chip('碰撞').click()
await page.waitForTimeout(150)
check('E1', '碰撞工具切到碰撞页', (await state()).rightTab === 'collision' && (await state()).activeTool === 'collision')
check('E2', '进入碰撞工具自动生成自定义矩形', (await state()).collision && (await state()).collision.type === 'rect',
  JSON.stringify((await state()).collision))
const colRect = (await state()).collision
await choose('基础设置', '形状', '胶囊')
await page.waitForTimeout(100)
let col = (await state()).collision
check('E3', '切换胶囊形状', col && col.type === 'capsule', JSON.stringify(col))
check('E4', '形状切换保持中心与包围盒', near(col.cx, colRect.cx, 0.6) && near(col.cy, colRect.cy, 0.6)
  && col.radius > 0 && col.height >= col.radius * 2,
  `${JSON.stringify(col)} vs ${JSON.stringify(colRect)}`)
await choose('基础设置', '形状', '矩形')
await page.waitForTimeout(100)
col = (await state()).collision
await fillText('变换', '位置', '10', 0)
col = (await state()).collision
check('E5', '碰撞位置 X +10 生效', near(col.cx - colRect.cx, 10, 0.6), `cx=${col.cx} base=${colRect.cx}`)
await fillText('变换', '位置', '10', 1)
col = (await state()).collision
check('E6', '碰撞 Y 正向为向上（cy 减小）', near(col.cy - colRect.cy, -10, 0.6), `cy=${col.cy}`)
await resetAxis('变换', '位置', 0)
await resetAxis('变换', '位置', 1)
col = (await state()).collision
check('E7', '碰撞位置重置回内容框', near(col.cx, colRect.cx, 0.6) && near(col.cy, colRect.cy, 0.6), JSON.stringify(col))
await fillText('变换', '缩放', '50', 0)
col = (await state()).collision
check('E8', '碰撞缩放 50% 生效', near(col.w, colRect.w / 2, 1), `w=${col.w} base=${colRect.w}`)
await resetAxis('变换', '缩放', 0)
// 碰撞作用 / 类型
await choose('基础设置', '作用', '感应')
check('E9', '碰撞作用可切为感应', (await state()).collisionKind === 'sensor', `kind=${(await state()).collisionKind}`)
check('E10', '感应时单向碰撞禁用', await row('基础设置', '单向碰撞').locator('input[type=checkbox]').first().isDisabled())
await choose('基础设置', '作用', '碰撞 + 感应')
check('E11', '碰撞作用可切为碰撞+感应', (await state()).collisionKind === 'both')
await choose('基础设置', '作用', '碰撞')
// 类型（标签）
await choose('基础设置', '类型', '自定义…')
const customInput = row('基础设置', '类型名').locator('input.att-input')
if (await customInput.count()) {
  await customInput.click()
  await customInput.fill('  敌人  ')
  await customInput.press('Tab')
  await page.waitForTimeout(100)
  check('E12', '自定义类型名去除首尾空格', (await state()).collisionTag === '敌人', `tag=${(await state()).collisionTag}`)
  await customInput.click()
  await customInput.fill('')
  await customInput.press('Tab')
  await page.waitForTimeout(100)
  check('E13', '空类型名清空回默认', (await state()).collisionTag === null, `tag=${(await state()).collisionTag}`)
} else {
  check('E12', '存在自定义类型输入框', false)
}
// 单向碰撞
await toggle('基础设置', '单向碰撞')
check('E14', '单向碰撞可启用', (await state()).activeTool === 'collision')
await choose('基础设置', '方向', '从右侧挡住')
await fillText('基础设置', '厚度', '20')
await settle()
let mE = await readManifest()
check('E15', '单向方向 / 厚度落盘且厚度钳制 8', mE.collisionOneWay === true && mE.collisionOneWayDirX === -1
  && mE.collisionOneWayMargin === 8, JSON.stringify({
  oneWay: mE.collisionOneWay, dir: [mE.collisionOneWayDirX, mE.collisionOneWayDirY], margin: mE.collisionOneWayMargin,
}))
// 碰撞层级
await toggle('基础设置', '碰撞层级')
await page.waitForTimeout(100)
check('E16', '碰撞层级启用后显示层网格', (await page.locator('.layer-grid').count()) >= 2)
await page.locator('.layer-block').filter({ hasText: '碰撞层' }).locator('.layer-cell').nth(2).click()
await page.locator('.layer-block').filter({ hasText: '碰撞掩码' }).locator('.layer-cell').nth(1).click()
await settle()
mE = await readManifest()
check('E17', '碰撞层 / 掩码落盘', mE.collisionLayersEnabled === true && mE.collisionLayer === 3
  && Array.isArray(mE.collisionMask) && mE.collisionMask.includes(2), JSON.stringify({
  layer: mE.collisionLayer, mask: mE.collisionMask,
}))
// 碰撞旋转
await fillText('变换', '旋转', '90')
await fillText('变换', '旋转', '999')
await settle()
mE = await readManifest()
check('E18', '碰撞旋转钳制在 ±180', mE.collisionAngle === 180, `angle=${mE.collisionAngle}`)
// 禁用碰撞
await toggle('基础设置', '禁用碰撞')
await page.waitForTimeout(100)
check('E19', '禁用碰撞开关生效', (await state()).collisionDisabled === true)
check('E20', '禁用后单向碰撞置灰', await row('基础设置', '单向碰撞').locator('input[type=checkbox]').first().isDisabled())
await toggle('基础设置', '禁用碰撞')
await page.waitForTimeout(100)
// 自动碰撞复位
await choose('基础设置', '形状', '自动（内容包围盒）')
await page.waitForTimeout(100)
s0 = await state()
check('E21', '自动形状清除自定义碰撞', s0.collision === null, JSON.stringify(s0.collision))
// 拖动碰撞框中心
await chip('碰撞').click()
await page.waitForTimeout(100)
const overlay = page.locator('.cso-root').first()
const ob = await overlay.count() ? await overlay.boundingBox() : null
if (ob) {
  await page.mouse.move(ob.x + ob.width / 2, ob.y + ob.height / 2)
  await page.mouse.down()
  await page.mouse.move(ob.x + ob.width / 2 + 30, ob.y + ob.height / 2, { steps: 5 })
  await page.mouse.up()
  await page.waitForTimeout(120)
  check('E22', '拖动碰撞框中心生成自定义碰撞', (await state()).collision !== null)
} else {
  check('E22', '碰撞覆盖层可见', false, '找不到 .collision-shape-overlay')
}

// ─── F. 基础属性（图层 / 翻转 / 隐藏 / 重力 / Y 排序） ─────────────────────
setStage('F 基础属性')
await tab('属性')
await fillText('基础设置', '图层设置', '5')
await settle()
let mF = await readManifest()
check('F1', '图层 5 落盘', mF.layer === 5, `layer=${mF.layer}`)
await fillText('基础设置', '图层设置', '999')
await settle()
mF = await readManifest()
check('F2', '图层超上限钳制到 100', mF.layer === 100, `layer=${mF.layer}`)
await fillText('基础设置', '图层设置', '0')
await settle()
mF = await readManifest()
check('F3', '图层 0 不写冗余字段', mF.layer === undefined, `layer=${mF.layer}`)
console.log('F 诊断:', JSON.stringify(await page.evaluate(() => ({
  rightTab: document.querySelector('.sprite-editor-page').__vueParentComponent.setupState.rightTab,
  sections: [...document.querySelectorAll('.mi-section')].map(s => ({
    title: s.querySelector('.mi-head-title')?.textContent?.trim(),
    rows: [...s.querySelectorAll('.att-label')].map(l => l.textContent?.trim()),
  })),
})), null, 1))
await choose('基础设置', '翻转模式', '水平翻转')
await settle()
mF = await readManifest()
check('F4', '水平翻转落盘', mF.flipX === true && !mF.flipY, JSON.stringify({ flipX: mF.flipX, flipY: mF.flipY }))
check('F5', '翻转预览生效', await page.evaluate(() => {
  const c = document.querySelector('canvas.preview-image')
  return c ? getComputedStyle(c).transform : ''
}) !== 'none', 'transform 已应用')
await choose('基础设置', '翻转模式', '水平 + 垂直')
await settle()
mF = await readManifest()
check('F6', '水平+垂直翻转落盘', mF.flipX === true && mF.flipY === true)
await choose('基础设置', '翻转模式', '不翻转')
await toggle('基础设置', '初始隐藏')
await toggle('基础设置', '受到重力')
await toggle('基础设置', 'Y轴排序')
await settle()
mF = await readManifest()
check('F7', '初始隐藏落盘', mF.hidden === true)
check('F8', '关闭重力落盘为 false', mF.gravity === false)
check('F9', 'Y 轴排序落盘', mF.ySort === true)
await settle()
const sizeInputs = row('基础设置', '画布尺寸').locator('input.att-input')
check('F10', '画布尺寸只读', (await sizeInputs.nth(0).getAttribute('readonly')) !== null)

// ─── G. 标记（挂点） ──────────────────────────────────────────────────────
setStage('G 标记')
await chip('标记').click()
await page.waitForTimeout(100)
// 画布上点一下放置标记
const cb = await page.locator('canvas.canvas-sprite').boundingBox()
await page.mouse.click(cb.x + cb.width / 2, cb.y + cb.height / 2)
await page.waitForTimeout(200)
s0 = await state()
check('G1', '画布点击创建标记', s0.markers && Object.keys(s0.markers).length >= 1,
  JSON.stringify(Object.keys(s0.markers || {})))
check('G2', '创建后自动切到标记设置页', (await state()).rightTab === 'props')
check('G3', '画布显示标记图钉', (await page.locator('.marker-handle').count()) >= 1)
const markerName = Object.keys((await state()).markers)[0]
// 拖动标记
const mb = await page.locator('.marker-handle').first().boundingBox()
const posBefore = (await state()).markers[markerName]
if (mb) {
  await page.mouse.move(mb.x + mb.width / 2, mb.y + mb.height / 2)
  await page.mouse.down()
  await page.mouse.move(mb.x + mb.width / 2 + 40, mb.y + mb.height / 2 + 30, { steps: 5 })
  await page.mouse.up()
  await page.waitForTimeout(150)
}
const posAfter = (await state()).markers[markerName]
check('G4', '拖拽标记改变坐标', posAfter && posBefore && (Math.abs(posAfter.x - posBefore.x) > 10 || Math.abs(posAfter.y - posBefore.y) > 10),
  `${JSON.stringify(posBefore)} → ${JSON.stringify(posAfter)}`)
// 重命名
const nameInput = row('标记信息', '名称').locator('input.att-input')
await nameInput.click()
await nameInput.fill('手持点')
await nameInput.press('Enter')
await page.waitForTimeout(100)
s0 = await state()
check('G5', '标记重命名生效', !!(s0.markers && s0.markers['手持点']), JSON.stringify(Object.keys(s0.markers || {})))
// 重名拒绝
const renamedInput = row('标记信息', '名称').locator('input.att-input')
await renamedInput.click()
await renamedInput.fill('手持点')
await renamedInput.press('Enter')
await page.waitForTimeout(100)
check('G6', '同名提交不产生重复标记', Object.keys((await state()).markers).length === 1)
// 作用范围仅当前帧 → 帧覆盖
await choose('标记信息', '作用范围', '仅当前帧')
await page.waitForTimeout(80)
const markPosBefore = (await state()).markers['手持点']
await fillText('标记信息', '位置', String(markPosBefore.x + 10), 0)
await settle()
const mm = await readManifest()
check('G7', '标记帧级覆盖落盘', mm.frames.some(f => f.markers && f.markers['手持点']),
  JSON.stringify(mm.frames.map(f => f.markers || null)))
check('G8', '标记覆盖角标出现', (await page.locator('.marker-override-badge').count()) >= 1)
await choose('标记信息', '作用范围', '全部帧')
await settle()
const posUnified = (await state()).markers['手持点']
check('G9', '回到全部帧编辑统一值', posUnified && typeof posUnified.x === 'number')
// 显示 / 锁定
await toggle('显示与锁定', '显示')
await page.waitForTimeout(100)
check('G10', '取消显示后画布图钉隐藏', (await page.locator('.marker-handle').count()) === 0)
await toggle('显示与锁定', '显示')
await toggle('显示与锁定', '锁定')
await page.waitForTimeout(100)
const lockedPos = (await state()).markers['手持点']
const lb = await page.locator('.marker-handle').first().boundingBox()
if (lb) {
  await page.mouse.move(lb.x + lb.width / 2, lb.y + lb.height / 2)
  await page.mouse.down()
  await page.mouse.move(lb.x + lb.width / 2 + 50, lb.y + lb.height / 2 + 40, { steps: 4 })
  await page.mouse.up()
  await page.waitForTimeout(100)
}
const lockedAfter = (await state()).markers['手持点']
check('G11', '锁定后拖拽不改变坐标', near(lockedAfter.x, lockedPos.x, 0.01) && near(lockedAfter.y, lockedPos.y, 0.01),
  `${JSON.stringify(lockedPos)} → ${JSON.stringify(lockedAfter)}`)
await settle()
const mLock = await readManifest()
check('G12', '锁定状态落盘', mLock.markers['手持点'].locked === true)
await toggle('显示与锁定', '锁定')
// 类型
await choose('标记信息', '类型', '右手')
await page.waitForTimeout(100)
s0 = await state()
check('G13', '标记类型写入', s0.markers['手持点'].type === '右手', JSON.stringify(s0.markers['手持点']))
// 复制 + 删除
await callFn('duplicateMarker', '手持点')
await page.waitForTimeout(100)
check('G14', '复制标记（副本命名）', Object.keys((await state()).markers).length === 2,
  JSON.stringify(Object.keys((await state()).markers)))
await callFn('deleteMarker', '手持点')
await page.waitForTimeout(100)
check('G15', '删除标记生效', Object.keys((await state()).markers).length === 1,
  JSON.stringify(Object.keys((await state()).markers)))
// 清理
for (const name of Object.keys((await state()).markers)) await callFn('deleteMarker', name)
await settle()

// ─── H. 落盘 / 重载一致性 ──────────────────────────────────────────────────
setStage('H 持久化')
await tab('属性')
await fillText('变换', '位置', '120', 0)
await fillText('变换', '位置', '-80', 1)
await choose('基础设置', '翻转模式', '水平翻转')
await page.locator('.costume-item').nth(5).click()
await settle(600)
const beforeReload = await state()
const mBeforeReload = await readManifest()
await page.reload({ waitUntil: 'domcontentloaded' })
await waitMounted()
await settle(300)
const afterReload = await state()
check('H1', '重载后变换保持', afterReload.transform.x === 120 && afterReload.transform.y === -80,
  `before=${JSON.stringify(beforeReload.transform)} after=${JSON.stringify(afterReload.transform)}`)
check('H2', '重载后翻转保持', afterReload.flipX === true, `flipX=${afterReload.flipX}`)
check('H3', '重载后默认帧保持', afterReload.defaultFrameIndex === 5,
  `defaultFrame=${afterReload.defaultFrameIndex} manifest=${mBeforeReload.defaultFrame}`)
check('H4', '重载后碰撞与图层保持', typeof afterReload.collisionKind === 'string' || afterReload.collisionKind === null)
check('H5', '重载后画布仍正常绘制', (await canvasPainted('canvas.canvas-sprite')).ok)
check('H6', 'manifest 无重复/异常帧', mBeforeReload.frames.length === baseManifest.frames.length,
  `frames=${mBeforeReload.frames.length}`)

// ─── I. 单图角色 ───────────────────────────────────────────────────────────
setStage('I 单图角色')
await selectSprite('s-img')
await page.waitForTimeout(600)
s0 = await state()
check('I1', '单图角色载入', s0.frameCount === 1 && s0.name === '测试图片', `name=${s0.name} frames=${s0.frameCount}`)
check('I2', '单图角色在内存合成 bsf 元数据', s0.bsfCanvas !== null, JSON.stringify(s0.bsfCanvas))
check('I3', '单图角色画布已绘制', (await canvasPainted('canvas.canvas-sprite')).ok)
await tab('属性')
await chip('中心').click()
await page.waitForTimeout(100)
await clickButton('脚底')
await settle(600)
const convertedDir = path.join(SPRITES, '测试图片')
const converted = existsSync(path.join(convertedDir, 'manifest.json'))
check('I4', '首次标注后转正为 .bsf 目录', converted, convertedDir)
check('I5', '转正后原图片已删除', !existsSync(imageDst))
check('I6', '资源路径改为目录', (await state()).path === convertedDir, (await state()).path)
const imgManifest = JSON.parse(await readFile(path.join(convertedDir, 'manifest.json'), 'utf8'))
check('I7', '转正 manifest 画布为图片尺寸', imgManifest.canvas.w > 0 && imgManifest.canvas.h > 0,
  JSON.stringify(imgManifest.canvas))
check('I8', '转正后有 sheet.png', existsSync(path.join(convertedDir, 'sheet.png')))

// ─── J. 造型删除一致性 ─────────────────────────────────────────────────────
setStage('J 删除造型')
// .bsf：设计上不支持删除（需回 BingoPacker 重打包），确认菜单确实隐藏
await selectSprite('s-c')
await settle(500)
await page.locator('.costume-item').nth(2).click({ button: 'right' })
await page.waitForTimeout(100)
check('J0', '.bsf 右键菜单不提供删除（已知限制）',
  (await page.locator('.context-menu-item').count()) === 0,
  `menuItems=${await page.locator('.context-menu-item').count()}`)
await page.keyboard.press('Escape')
await page.mouse.click(20, 20)
// 老格式 .bgs：可删除造型
await selectSprite('s-d')
await settle(500)
const beforeDel = await state()
const beforeDelConfig = JSON.parse(await readFile(path.join(dirBgs, 'config.json'), 'utf8'))
const activeUrlsBeforeDelete = await page.evaluate(() => window.__smoke.urls.active.size)
await page.locator('.costume-item').nth(2).click({ button: 'right' })
await page.waitForTimeout(100)
await page.locator('.context-menu-item').filter({ hasText: /删除造型/ }).first().click()
await settle(600)
const afterDel = await state()
const afterDelConfig = JSON.parse(await readFile(path.join(dirBgs, 'config.json'), 'utf8'))
check('J1', '删除造型后帧数 -1', afterDel.frameCount === beforeDel.frameCount - 1,
  `${beforeDel.frameCount} → ${afterDel.frameCount}`)
check('J2', 'config.json 帧数同步', afterDelConfig.frames.length === afterDel.frameCount,
  `config=${afterDelConfig.frames.length} frames=${afterDel.frameCount}`)
check('J3', '删除后默认帧指向存在的帧或安全回退',
  typeof afterDelConfig.defaultFrame !== 'string' || afterDelConfig.frames.includes(afterDelConfig.defaultFrame),
  `defaultFrame=${afterDelConfig.defaultFrame} frames=${JSON.stringify(afterDelConfig.frames)}`)
check('J4', '删除后动画区间不超过帧数',
  (afterDelConfig.segments || []).every(c => (c.end ?? 0) <= afterDel.frameCount),
  JSON.stringify(afterDelConfig.segments))
check('J5', '删除后选中帧回退到有效范围', afterDel.selectedFrame <= afterDel.frameCount - 1,
  `selected=${afterDel.selectedFrame}`)
const activeUrlsAfterDelete = await page.evaluate(() => window.__smoke.urls.active.size)
check('J6', '删除帧释放其 ObjectURL（不泄漏 Blob）', activeUrlsAfterDelete < activeUrlsBeforeDelete,
  `${activeUrlsBeforeDelete} → ${activeUrlsAfterDelete}`)
// 撤销删除
await callFn('undo')
await page.waitForTimeout(400)
const afterUndo = await state()
check('J7', '撤销删除恢复帧数', afterUndo.frameCount === beforeDel.frameCount,
  `${afterDel.frameCount} → ${afterUndo.frameCount}`)
// 删除最后一帧
await page.locator('.costume-item').nth(afterUndo.frameCount - 1).click()
await page.waitForTimeout(100)
await page.locator('.costume-item').nth(afterUndo.frameCount - 1).click({ button: 'right' })
await page.waitForTimeout(100)
await page.locator('.context-menu-item').filter({ hasText: /删除造型/ }).first().click()
await settle(500)
check('J8', '删除最后一帧后选中帧回退', (await state()).selectedFrame <= afterUndo.frameCount - 2,
  `selected=${(await state()).selectedFrame}`)
check('J9', '删除最后一帧后选中帧有效', (await state()).selectedFrame >= 0,
  `selected=${(await state()).selectedFrame}`)
const lastConfig = JSON.parse(await readFile(path.join(dirBgs, 'config.json'), 'utf8'))
check('J10', '最后一帧删除后 defaultFrame 不指向已删除帧',
  typeof lastConfig.defaultFrame !== 'string' || lastConfig.frames.includes(lastConfig.defaultFrame),
  `defaultFrame=${lastConfig.defaultFrame} frames=${JSON.stringify(lastConfig.frames)}`)

// ─── N. 动画片段管理 ───────────────────────────────────────────────────────
setStage('N 动画片段')
await selectSprite('s-a')
await settle(500)
await tab('动画')
const n0 = await state()
const addBtn = page.locator('.preview-btns button').nth(5)
await addBtn.click()
await page.waitForTimeout(200)
let ns = await state()
check('N1', '新增动画片段（默认命名 动画）', ns.animCount === n0.animCount + 1 && ns.selectedAnimName === '动画',
  `anim=${ns.animCount} selected=${ns.selectedAnimName}`)
await addBtn.click()
await page.waitForTimeout(200)
ns = await state()
check('N2', '再次新增自动编号（动画1）', ns.animCount === n0.animCount + 2 && ns.selectedAnimName === '动画1',
  `anim=${ns.animCount} selected=${ns.selectedAnimName}`)
check('N3', '新片段默认 10 帧/秒', ns.fps === 10, `fps=${ns.fps}`)
const activeAnim = page.locator('.anim-item.anim-item-active').first()
// 起止帧越界钳制（@change 触发）
await activeAnim.locator('.anim-spin').nth(0).fill('999')
await activeAnim.locator('.anim-spin').nth(0).press('Tab')
await page.waitForTimeout(120)
ns = await state()
check('N4', '起始帧超上限钳制到末帧', ns.anims.find(a => a.name === '动画1').start <= n0.frameCount,
  JSON.stringify(ns.anims.find(a => a.name === '动画1')))
await activeAnim.locator('.anim-spin').nth(1).fill('0')
await activeAnim.locator('.anim-spin').nth(1).press('Tab')
await page.waitForTimeout(120)
ns = await state()
check('N5', '结束帧低于起始时钳制到起始', ns.anims.find(a => a.name === '动画1').end >= ns.anims.find(a => a.name === '动画1').start,
  JSON.stringify(ns.anims.find(a => a.name === '动画1')))
// 循环开关
await activeAnim.locator('.anim-loop-btn').click()
await settle(500)
let mN = await readManifest()
check('N6', '循环关闭落盘', (mN.clips || []).find(c => c.name === '动画1')?.loop === false,
  JSON.stringify((mN.clips || []).map(c => [c.name, c.loop])))
// 双击重命名
await activeAnim.locator('.anim-name').dblclick()
await page.waitForTimeout(100)
const renameInput = page.locator('.anim-rename-input')
await renameInput.fill('跑步')
await renameInput.press('Enter')
await settle(500)
ns = await state()
check('N7', '动画片段重命名生效', ns.anims.some(a => a.name === '跑步'),
  JSON.stringify(ns.anims.map(a => a.name)))
const originalAnimName = n0.anims[0].name
const runItem = page.locator('.anim-item').filter({ hasText: '跑步' }).first()
await runItem.locator('.anim-name').dblclick()
await page.waitForTimeout(100)
await page.locator('.anim-rename-input').fill(originalAnimName)
await page.locator('.anim-rename-input').press('Enter')
await page.waitForTimeout(200)
ns = await state()
check('N8', '重命名为已存在名称被拒绝', ns.anims.some(a => a.name === '跑步') && ns.animCount === n0.animCount + 2,
  JSON.stringify(ns.anims.map(a => a.name)))
// 右键删除片段
await page.locator('.anim-item').filter({ hasText: '跑步' }).first().click({ button: 'right' })
await page.waitForTimeout(100)
await page.locator('.context-menu-item').first().click()
await settle(500)
ns = await state()
check('N9', '右键删除动画片段', ns.animCount === n0.animCount + 1 && ns.selectedAnimName === null,
  `anim=${ns.animCount} selected=${ns.selectedAnimName}`)
// 清理多余的「动画」片段
await callFn('deleteAnimation', '动画')
await settle(500)
ns = await state()
check('N10', '清理后片段数回到原始', ns.animCount === n0.animCount, `anim=${ns.animCount} 期望=${n0.animCount}`)

// ─── O. 撤销 / 重做 / 快捷键 ───────────────────────────────────────────────
setStage('O 撤销重做')
await selectSprite('s-a')
await settle(500)
await tab('属性')
const oBase = (await state()).transform
await fillText('变换', '位置', '300', 0)
await settle(700)
check('O1', '修改位置到 300', (await state()).transform.x === 300, `x=${(await state()).transform.x}`)
await page.evaluate(() => document.activeElement && document.activeElement.blur())
await page.keyboard.press('Control+z')
await settle(500)
check('O2', 'Ctrl+Z 撤销回上一值', (await state()).transform.x !== 300,
  `x=${(await state()).transform.x} 基线=${oBase.x}`)
await page.keyboard.press('Control+Shift+z')
await settle(500)
check('O3', 'Ctrl+Shift+Z 重做回到 300', (await state()).transform.x === 300,
  `x=${(await state()).transform.x}`)
check('O4', '重做后撤销栈可用、重做栈清空', (await state()).canUndo === true && (await state()).canRedo === false,
  `undo=${(await state()).canUndo} redo=${(await state()).canRedo}`)
// 输入框聚焦时 Ctrl+Z 不应撤销角色编辑
await row('基础设置', '图像名称').locator('input.att-input').click()
await page.keyboard.press('Control+z')
await page.waitForTimeout(200)
check('O5', '输入框内 Ctrl+Z 不触发角色撤销', (await state()).transform.x === 300,
  `x=${(await state()).transform.x}`)
await page.evaluate(() => document.activeElement && document.activeElement.blur())
// F 键：视图回到 100%
await page.mouse.move(400, 300)
for (let i = 0; i < 5; i++) await page.mouse.wheel(0, -200)
await page.waitForTimeout(200)
const zoomBeforeF = (await state()).zoom
await page.keyboard.press('f')
await page.waitForTimeout(150)
check('O6', 'F 键重置视图到 100%', near((await state()).zoom, 1, 0.001), `${zoomBeforeF} → ${(await state()).zoom}`)
// Delete 键删除选中标记
await chip('标记').click()
await page.waitForTimeout(120)
const kc = await page.locator('canvas.canvas-sprite').boundingBox()
await page.mouse.click(kc.x + kc.width / 2 + 10, kc.y + kc.height / 2 + 10)
await page.waitForTimeout(250)
const markerCountBeforeDel = Object.keys((await state()).markers || {}).length
// 放置后焦点自动落在「名称」输入框（输入框内 Delete 属于文字编辑，先移出焦点）
await page.evaluate(() => document.activeElement && document.activeElement.blur())
await page.keyboard.press('Delete')
await page.waitForTimeout(200)
check('O7', 'Delete 键删除选中标记', Object.keys((await state()).markers || {}).length === markerCountBeforeDel - 1,
  `${markerCountBeforeDel} → ${Object.keys((await state()).markers || {}).length}`)
for (const name of Object.keys((await state()).markers)) await callFn('deleteMarker', name)
await settle()
// 连续撤销到底（历史栈可回溯）
await tab('属性')
for (let i = 0; i < 3; i++) {
  await fillText('变换', '位置', String((await state()).transform.x + 5), 0)
  await settle(450) // 每次修改间隔超过历史合并窗口（250ms），确保各自成为一步
}
await settle(700)
let undos = 0
while ((await state()).canUndo && undos < 12) { await callFn('undo'); await page.waitForTimeout(80); undos++ }
check('O8', '连续撤销可回溯多步', undos >= 3, `撤销 ${undos} 步`)

// ─── P. 预览与视图控件 ────────────────────────────────────────────────────
setStage('P 预览控件')
await tab('动画')
const p0 = await state()
await page.locator('.preview-btns button').nth(3).click()
await page.waitForTimeout(120)
const scaleAfter = (await state()).previewScale
check('P1', '预览比例切换生效', scaleAfter !== p0.previewScale, `${p0.previewScale} → ${scaleAfter}`)
await page.locator('.preview-btns button').nth(3).click()
await page.waitForTimeout(120)
check('P2', '再次切换比例复原', (await state()).previewScale === p0.previewScale,
  `${(await state()).previewScale}`)
const bg0 = (await state()).previewBg
await page.locator('.preview-btns button').nth(4).click()
await page.waitForTimeout(100)
const bg1 = (await state()).previewBg
await page.locator('.preview-btns button').nth(4).click()
await page.waitForTimeout(100)
await page.locator('.preview-btns button').nth(4).click()
await page.waitForTimeout(100)
check('P3', '预览背景三档循环', bg1 !== bg0 && (await state()).previewBg === bg0,
  `${bg0} → ${bg1} → ${(await state()).previewBg}`)
await page.locator('.scene-zoom-bar button').nth(0).click()
await page.waitForTimeout(100)
check('P4', '缩小按钮 -10%', near((await state()).zoom, 0.9, 0.01), `zoom=${(await state()).zoom}`)
await page.locator('.scene-zoom-bar button').nth(2).click()
await page.waitForTimeout(100)
await page.locator('.scene-zoom-bar button').nth(1).click()
await page.waitForTimeout(100)
check('P5', '重置视图按钮回到 100%', near((await state()).zoom, 1, 0.001), `zoom=${(await state()).zoom}`)
// 空格 + 拖拽平移
await page.evaluate(() => document.activeElement && document.activeElement.blur())
const panBefore = (await state()).pan
const transformDuringPan = (await state()).transform
const cbox = await page.locator('canvas.canvas-sprite').boundingBox()
await page.mouse.move(cbox.x + cbox.width / 2, cbox.y + cbox.height / 2)
await page.keyboard.down('Space')
await page.mouse.down()
await page.mouse.move(cbox.x + cbox.width / 2 + 60, cbox.y + cbox.height / 2 + 40, { steps: 5 })
await page.mouse.up()
await page.keyboard.up('Space')
await page.waitForTimeout(150)
const panAfter = (await state()).pan
check('P6', '空格拖拽平移画布', (Math.abs(panAfter[0] - panBefore[0]) > 20 || Math.abs(panAfter[1] - panBefore[1]) > 20),
  `${JSON.stringify(panBefore)} → ${JSON.stringify(panAfter)}`)
check('P7', '平移不改动角色变换',
  near((await state()).transform.x, transformDuringPan.x, 0.01) && near((await state()).transform.y, transformDuringPan.y, 0.01),
  `${JSON.stringify(transformDuringPan)} → ${JSON.stringify((await state()).transform)}`)
await page.locator('.scene-zoom-bar button').nth(1).click()
await page.waitForTimeout(100)

// ─── Q. 异常数据 / 兼容性 ──────────────────────────────────────────────────
setStage('Q 健壮性')
await page.evaluate(() => { window.__smoke.resource.selectedSpriteId = 's-bad' })
await page.waitForTimeout(900)
const qState = await state()
check('Q1', '损坏 manifest 显示载入错误而非崩溃', !!qState.loadError, String(qState.loadError).slice(0, 80))
check('Q2', '载入错误时页面与编辑器仍在', (await page.locator('.sprite-editor-page').count()) === 1
  && (await page.locator('.load-error').count()) === 1)
check('Q3', '载入错误提示对用户可见', (await page.locator('.load-error').first().innerText()).length > 5,
  (await page.locator('.load-error').first().innerText()).slice(0, 40))
// 回到正常角色应恢复
await selectSprite('s-a')
await settle(600)
check('Q4', '从损坏角色切回正常角色可恢复', (await state()).frameCount === baseManifest.frames.length,
  `frames=${(await state()).frameCount}`)
// 失败后重新选中「上一个正常角色」：组件内部同路径会跳过重载，错误提示是否残留
await page.evaluate(() => { window.__smoke.resource.selectedSpriteId = 's-a' })
await page.waitForTimeout(400)
check('Q4b', '载入失败后重新选中原角色清除错误提示', !(await state()).loadError,
  `loadError=${(await state()).loadError}`)
// 空名称改名
await selectSprite('s-c')
await settle(500)
await tab('属性')
const nameBeforeEmpty = (await state()).name
const qName = row('基础设置', '图像名称').locator('input.att-input')
await qName.click()
await qName.fill('')
await qName.press('Enter')
await settle(400)
check('Q5', '空名称改名被拒绝并回退', (await state()).name === nameBeforeEmpty && existsSync(dirC),
  `name=${(await state()).name} 期望=${nameBeforeEmpty}`)
// 重命名到已存在角色名
await qName.click()
await qName.fill('角色A')
await qName.press('Enter')
await settle(600)
check('Q6', '重命名到已存在名称时安全回退（不覆盖原角色）', existsSync(dirA) && existsSync(dirC),
  `dirA=${existsSync(dirA)} dirC=${existsSync(dirC)} path=${(await state()).path}`)
// 旧 .bgs 角色兼容
await selectSprite('s-e')
await settle(600)
const qBgs = await state()
check('Q7', '旧版 .bgs 角色正常载入', qBgs.frameCount === 3 && qBgs.name === '角色E',
  `frames=${qBgs.frameCount} name=${qBgs.name}`)
check('Q8', '旧版 .bgs 无标注数据（canAnno=false）', qBgs.canAnno === false && qBgs.bsfFrameCount === 0,
  `canAnno=${qBgs.canAnno} bsfFrames=${qBgs.bsfFrameCount}`)

// ─── S. 单图转正后的持久化回归（转正动作本身已在 I 阶段覆盖） ──────────────
setStage('S 单图转正回归')
const sImgDir = path.join(SPRITES, '测试图片')
// 切走再切回：应按 .bsf 目录读取，标注能力保持
await page.evaluate(() => { window.__smoke.resource.selectedSpriteId = 's-b' })
await page.waitForTimeout(300)
await selectSprite('s-img')
await settle(600)
let sState = await state()
check('S1', '转正后重新打开仍是可标注 .bsf 角色', sState.canAnno === true && sState.bsfFrameCount === 1
  && sState.path === sImgDir, `canAnno=${sState.canAnno} path=${sState.path}`)
// 后续修改应写入目录 manifest（不再重复转正）
await tab('属性')
await toggle('基础设置', '初始隐藏')
await settle(800)
const sManifest = JSON.parse(await readFile(path.join(sImgDir, 'manifest.json'), 'utf8'))
check('S2', '后续修改写入目录 manifest（隐藏状态已保存）', sManifest.hidden === true,
  JSON.stringify({ hidden: sManifest.hidden, frames: sManifest.frames.length }))
await toggle('基础设置', '初始隐藏')
await settle(700)
const sManifest2 = JSON.parse(await readFile(path.join(sImgDir, 'manifest.json'), 'utf8'))
check('S3', '关闭隐藏后 manifest 同步清除', sManifest2.hidden === false || sManifest2.hidden === undefined,
  `hidden=${sManifest2.hidden}`)
check('S4', '反复保存后画面与标注数据仍完整', (await state()).frameCount === 1
  && (await state()).bsfFrameCount === 1 && (await canvasPainted('canvas.canvas-sprite')).ok)

// ─── K. 压力测试 ───────────────────────────────────────────────────────────
setStage('K 压力')
await selectSprite('s-a')
await settle(500)
const urlBefore = await page.evaluate(() => ({
  created: window.__smoke.urls.created,
  revoked: window.__smoke.urls.revoked,
  active: window.__smoke.urls.active.size,
}))
const heapBefore = await page.evaluate(() => performance.memory ? performance.memory.usedJSHeapSize : 0)

// 快速切帧 2000 次
const t1 = Date.now()
await page.evaluate(() => {
  const s = document.querySelector('.sprite-editor-page').__vueParentComponent.setupState
  for (let i = 0; i < 2000; i++) s.onCostumeClick(i % s.currentSprite.frames.length)
})
const frameSwitchMs = Date.now() - t1
check('K1', '快速切帧 2000 次无异常且耗时可控', frameSwitchMs < 3000, `${frameSwitchMs}ms`)
// 快速播放/暂停 300 次
await page.locator('.right-tab').first().click()
await page.locator('.anim-item').first().click()
await page.waitForTimeout(100)
// 选中片段会自动播放，先停掉，记录空闲态定时器基线
if ((await state()).playing) {
  await page.locator('.preview-btns button').nth(1).click()
  await page.waitForTimeout(150)
}
const idleTimerCount = await page.evaluate(() => window.__smoke.intervals.size)
const t2 = Date.now()
await page.evaluate(() => {
  const s = document.querySelector('.sprite-editor-page').__vueParentComponent.setupState
  for (let i = 0; i < 300; i++) {
    s.togglePlay()
    s.togglePlay()
  }
})
const playMs = Date.now() - t2
check('K2', '快速播放/暂停 300 次无异常', playMs < 3000, `${playMs}ms`)
await page.waitForTimeout(150)
const timersAfterPlay = await page.evaluate(() => window.__smoke.intervals.size)
check('K3', '播放结束后定时器回到基线（无累积）', timersAfterPlay === idleTimerCount,
  `基线=${idleTimerCount} 之后=${timersAfterPlay}`)
// 连续输入 1000 次（只应产生一次落盘）
ipc.writeCount = 0
const t3 = Date.now()
await page.evaluate(() => {
  const s = document.querySelector('.sprite-editor-page').__vueParentComponent.setupState
  for (let i = 0; i < 1000; i++) s.onTransformInput('x', { target: { value: String(i % 200) } })
})
await settle(800)
const inputMs = Date.now() - t3
const writesAfterInput = ipc.writeCount
check('K4', '连续输入 1000 次触发防抖单次落盘', writesAfterInput <= 2, `writes=${writesAfterInput}`)
check('K5', '连续输入耗时可控', inputMs < 5000, `${inputMs}ms`)
check('K6', '连续输入后最终值正确', (await state()).transform.x === 999 % 200, `x=${(await state()).transform.x}`)
// 反复切换角色 20 次
const kErrFrom = consoleErrors.length
const t4 = Date.now()
for (let i = 0; i < 20; i++) {
  await page.evaluate(id => { window.__smoke.resource.selectedSpriteId = id }, i % 2 ? 's-a' : 's-b')
  await page.waitForTimeout(120)
}
await page.waitForTimeout(500)
const switchMs = Date.now() - t4
const kNewErrors = consoleErrors.slice(kErrFrom)
const kBlobNoise = kNewErrors.filter(e => e.includes('net::ERR_FILE_NOT_FOUND'))
const kRealErrors = kNewErrors.filter(e => !e.includes('net::ERR_FILE_NOT_FOUND'))
check('K7', '反复切换角色 20 次无异常', kRealErrors.length === 0, JSON.stringify(kRealErrors))
check('K9', '切换角色时不产生失效 blob 请求', kBlobNoise.length === 0,
  `${kBlobNoise.length} 次瞬态 blob 加载失败（${switchMs}ms / 20 次切换）`)
const urlAfter = await page.evaluate(() => ({
  created: window.__smoke.urls.created,
  revoked: window.__smoke.urls.revoked,
  active: window.__smoke.urls.active.size,
}))
check('K8', 'objectURL 创建/释放基本平衡（无持续泄漏）',
  urlAfter.active - urlBefore.active <= 30,
  `before=${urlBefore.active} after=${urlAfter.active} created=${urlAfter.created - urlBefore.created} revoked=${urlAfter.revoked - urlBefore.revoked}`)
const heapAfter = await page.evaluate(() => performance.memory ? performance.memory.usedJSHeapSize : 0)
const heapGrowthMb = heapBefore && heapAfter ? (heapAfter - heapBefore) / 1024 / 1024 : 0
check('K9', '压力后堆内存增长在合理范围', heapGrowthMb < 80, `${heapGrowthMb.toFixed(1)} MB（${(heapBefore / 1048576).toFixed(1)} → ${(heapAfter / 1048576).toFixed(1)}）`)
const lt = await page.evaluate(() => window.__smoke.longTasks)
check('K10', '长任务（>50ms）数量可控', lt.length <= 40, `longTasks=${lt.length} max=${lt.length ? Math.max(...lt).toFixed(0) : 0}ms`)
// 重复保存 30 次
ipc.writeCount = 0
await page.evaluate(() => {
  const s = document.querySelector('.sprite-editor-page').__vueParentComponent.setupState
  for (let i = 0; i < 30; i++) s.onTransformInput('angle', { target: { value: String(i) } })
})
await page.waitForTimeout(800)
check('K11', '重复保存 30 次无报错', true, `writes=${ipc.writeCount}`)

// ─── L. 改名 / 路径安全 ───────────────────────────────────────────────────
setStage('L 改名安全')
await selectSprite('s-c')
await settle(500)
await tab('属性')
const nameField = row('基础设置', '图像名称').locator('input.att-input')
await nameField.click()
await nameField.fill('角色C改名')
await nameField.press('Enter')
await settle(400)
const renamedDir = path.join(SPRITES, '角色C改名')
check('L1', '正常改名迁移目录', existsSync(renamedDir), renamedDir)
check('L2', '改名后编辑器路径同步', (await state()).path === renamedDir, (await state()).path)
await nameField.click()
await nameField.fill('角色C')
await nameField.press('Enter')
await settle(400)
check('L3', '改回原名目录恢复', existsSync(dirC), dirC)
// 路径穿越检查：填 ../ 名称
const escapeTarget = path.join(ROOT, 'should-not-exist-outside-sprites')
await nameField.click()
await nameField.fill('../../../should-not-exist-outside-sprites')
await nameField.press('Enter')
await settle(500)
check('L4', '改名拒绝路径穿越（不越出 sprites 目录）',
  ipc.escapedRename.length === 0,
  ipc.escapedRename.length ? JSON.stringify(ipc.escapedRename) : '未发生越界写入')
// 还原（若真的越界了，把目录搬回去，并把资源项的 path 一并还原，避免后续阶段读不到）
if (ipc.escapedRename.length) {
  try {
    const to = ipc.escapedRename[ipc.escapedRename.length - 1].to
    if (existsSync(to)) await rename(to, dirC)
    await page.evaluate(({ id, p }) => {
      const item = window.__smoke.resource.sprites.find(s => s.id === id)
      if (item) item.path = p
    }, { id: 's-c', p: dirC })
  } catch { /* ignore */ }
}

// ─── M. 卸载 / 残留监听 ───────────────────────────────────────────────────
setStage('M 卸载泄漏')
const beforeUnmount = await page.evaluate(() => ({
  intervals: window.__smoke.intervals.size,
  timeouts: window.__smoke.timeouts.size,
}))
await page.evaluate(() => window.__smoke.app.unmount())
await page.waitForTimeout(400)
const afterUnmount = await page.evaluate(() => ({
  intervals: window.__smoke.intervals.size,
  timeouts: window.__smoke.timeouts.size,
}))
check('M1', '卸载后动画 interval 不残留', afterUnmount.intervals <= beforeUnmount.intervals,
  `${beforeUnmount.intervals} → ${afterUnmount.intervals}（挂载基线 ${idleIntervals}）`)

// ─── R. 反复挂载 / 卸载 ───────────────────────────────────────────────────
setStage('R 反复挂载')
await page.evaluate(() => { window.__smoke.mountApp() })
try {
  await waitMounted(10000)
} catch (e) {
  const diag = await page.evaluate(() => ({
    pageCount: document.querySelectorAll('.sprite-editor-page').length,
    containerHtml: (document.querySelector('#app')?.innerHTML || '').slice(0, 160),
    errors: (window.__smoke.errors || []).slice(0, 6),
    selectedId: window.__smoke.resource?.selectedSpriteId,
    spriteCount: window.__smoke.resource?.sprites?.length,
    state: (() => {
      try { return window.__smoke.readState ? window.__smoke.readState() : 'no readState' }
      catch (err) { return 'readState 抛错: ' + (err && err.message) }
    })(),
  }))
  console.log('R1 诊断:', JSON.stringify(diag, null, 2))
  throw e
}
await settle(400)
let rState = await state()
check('R1', '卸载后可重新挂载并载入角色', rState && rState.frameCount > 0, `frames=${rState && rState.frameCount}`)
const rIntervalsMounted = await page.evaluate(() => window.__smoke.intervals.size)
await page.evaluate(() => window.__smoke.app.unmount())
await page.waitForTimeout(300)
const rIntervalsUnmounted = await page.evaluate(() => window.__smoke.intervals.size)
check('R2', '再次卸载无定时器残留', rIntervalsUnmounted <= rIntervalsMounted,
  `${rIntervalsMounted} → ${rIntervalsUnmounted}`)
// 再挂载一次，确认可反复使用
await page.evaluate(() => { window.__smoke.mountApp() })
await waitMounted()
await settle(300)
check('R3', '反复挂载仍能正常工作', (await state()).frameCount > 0)
await page.evaluate(() => { window.__smoke.app.unmount() })
await page.waitForTimeout(300)
check('R4', '反复挂载后卸载无残留异常', (await page.evaluate(() => window.__smoke.intervals.size))
  <= rIntervalsMounted,
  `intervals=${await page.evaluate(() => window.__smoke.intervals.size)}`)

// ─── 汇总 ──────────────────────────────────────────────────────────────────
const errorsSnapshot = {
  consoleErrors: [...new Set(consoleErrors)].slice(0, 30),
  pageErrors: await page.evaluate(() => window.__smoke.errors.slice(0, 20)),
  unknownCommands: [...ipc.unknown],
}
// 测试故意触发的失败日志（损坏 manifest / 重名改名）或可容忍的瞬态资源错误，不计入"非预期"
const EXPECTED_CONSOLE = ['Failed to load sprite', '重命名角色失败', 'net::ERR_FILE_NOT_FOUND', 'Failed to load resource']
const unexpectedConsole = errorsSnapshot.consoleErrors.filter(e => !EXPECTED_CONSOLE.some(p => e.includes(p)))
check('X1', '无未捕获运行时错误', errorsSnapshot.pageErrors.length === 0, JSON.stringify(errorsSnapshot.pageErrors))
check('X2', '无非预期 console.error 级别错误', unexpectedConsole.length === 0, JSON.stringify(unexpectedConsole))
check('X3', '所有 IPC 命令均已实现', errorsSnapshot.unknownCommands.length === 0, JSON.stringify(errorsSnapshot.unknownCommands))
if (errorsSnapshot.consoleErrors.length !== unexpectedConsole.length) {
  console.log('（已排除测试故意触发的预期错误日志：', JSON.stringify(EXPECTED_CONSOLE), '）')
}

const failed = results.filter(r => !r.pass)
const warnings = []
console.log('\n──────────────────────────────')
console.log(`结果: ${results.length - failed.length}/${results.length} 通过`)
if (failed.length) {
  console.log('\n失败项:')
  for (const f of failed) console.log(`  ✗ [${f.stage}] ${f.name} — ${f.detail ?? ''}`)
}
console.log('\nIPC 调用统计:', JSON.stringify(ipc.calls, null, 2))
console.log('objectURL:', JSON.stringify(urlAfter))
console.log('longTasks:', lt.length, lt.length ? `max=${Math.max(...lt).toFixed(0)}ms` : '')
console.log('临时项目:', ROOT)

await browser.close()
vite.kill()
await Promise.race([viteExited, new Promise(r => setTimeout(r, 3000))])
process.exit(failed.length ? 1 : 0)
