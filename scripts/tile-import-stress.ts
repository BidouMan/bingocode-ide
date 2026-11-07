/**
 * 图块 / 图块集上传导入回归 + 压力测试（纯 Node，无需启动 Tauri）
 *
 * 运行：pnpm exec tsx scripts/tile-import-stress.ts
 *
 * 被测对象：src/composables/useTileAssetImport.ts + src/utils/tileAssetFit.ts
 * 覆盖：
 *  - 第一次导入锁定格子 / 后续素材归一化 / 非整数倍逐块缩放
 *  - 未设定尺寸、非法尺寸、超大尺寸、超大画布、零尺寸、非正方形
 *  - 文件名 / 地图名的路径穿越
 *  - 并发导入、同名覆盖、refit 幂等性
 *  - 随机压力：任意尺寸序列 + 改格子 + 重新归一化后的不变量
 *
 * 说明：Image / canvas / Tauri invoke 全部 mock，因此这里验证的是「业务逻辑与
 * 尺寸换算是否正确、是否会产出危险数据」，真实像素效果仍需在应用里肉眼确认。
 */
import { createPinia, setActivePinia } from 'pinia'

// ===================== 浏览器 / Tauri 环境 mock =====================
const g = globalThis as any
g.window = globalThis

const memStore = new Map<string, string>()
g.localStorage = {
  getItem: (k: string) => memStore.get(k) ?? null,
  setItem: (k: string, v: string) => void memStore.set(k, v),
  removeItem: (k: string) => void memStore.delete(k),
  clear: () => memStore.clear(),
}

/** 模拟磁盘上的图片文件：路径 → 尺寸 */
const files = new Map<string, { w: number; h: number }>()
/** 记录复制到项目的文件（相对路径） */
const copies: string[] = []
/** 记录 write_binary 写入的文件（路径 + 内容载荷） */
const writes: { path: string; payload: string }[] = []
/** 每次 fitTileSheet 创建的 canvas（用于断言尺寸与逐块绘制次数） */
const canvases: FakeCanvas[] = []
/** data URL → 图片尺寸（read_image_as_data_url 时登记） */
const dataUrlSizes = new Map<string, { w: number; h: number }>()

function makeDataUrl(path: string) {
  return `data:image/png;base64,${Buffer.from(`IMG:${path}`).toString('base64')}`
}

class FakeImage {
  width = 0
  height = 0
  onload: (() => void) | null = null
  onerror: ((e?: any) => void) | null = null
  set src(v: string) {
    const info = dataUrlSizes.get(v)
    setTimeout(() => {
      if (!info) {
        this.onerror?.(new Error('图片加载失败'))
        return
      }
      this.width = info.w
      this.height = info.h
      this.onload?.()
    }, 0)
  }
}

class FakeCanvas {
  width = 0
  height = 0
  drawCalls: { args: number[] }[] = []
  private _ctx = {
    imageSmoothingEnabled: true,
    drawImage: (_img: any, ...args: number[]) => {
      this.drawCalls.push({ args })
    },
  }
  getContext(type: string) {
    return type === '2d' ? this._ctx : null
  }
  get smoothing() {
    return this._ctx.imageSmoothingEnabled
  }
  toDataURL() {
    const payload = `FIT:${this.width}x${this.height}`
    const url = `data:image/png;base64,${Buffer.from(payload).toString('base64')}`
    // 派生图回读时尺寸保持一致（refit 目前只读原图，这里只是兜底）
    dataUrlSizes.set(url, { w: this.width, h: this.height })
    return url
  }
}

g.Image = FakeImage
g.document = {
  createElement(tag: string) {
    if (tag !== 'canvas') throw new Error(`未 mock的 DOM 元素: ${tag}`)
    const c = new FakeCanvas()
    canvases.push(c)
    return c
  },
}

function resetMockFs() {
  files.clear()
  copies.length = 0
  writes.length = 0
  canvases.length = 0
  dataUrlSizes.clear()
}

function addFile(path: string, w: number, h: number) {
  files.set(path, { w, h })
}

g.__TAURI_INTERNALS__ = {
  invoke: async (cmd: string, args: any) => {
    switch (cmd) {
      case 'read_image_as_data_url': {
        const info = files.get(args.path)
        if (!info) throw new Error(`文件不存在: ${args.path}`)
        const url = makeDataUrl(args.path)
        dataUrlSizes.set(url, info)
        return url
      }
      case 'copy_file_to_project': {
        copies.push(args.relativePath)
        const info = files.get(args.src)
        if (info) files.set(`${args.projectRoot}/${args.relativePath}`, { ...info })
        return null
      }
      case 'write_binary': {
        // dataUrlToBytes 会把 'FIT:WxH' 的字符码传过来，直接还原
        const payload = String.fromCharCode(...(args.data as number[]).slice(0, 64))
        writes.push({ path: args.path, payload })
        return null
      }
      default:
        throw new Error(`未 mock 的 Tauri 命令: ${cmd}`)
    }
  },
  transformCallback: () => 0,
  convertFileSrc: (p: string) => p,
  metadata: { currentWindow: { label: 'main' }, currentWebview: { label: 'main' } },
}

let unhandled = 0
process.on('unhandledRejection', (e) => {
  unhandled++
  console.warn('[警告] 未处理的异步异常（测试继续）:', (e as any)?.message ?? e)
})

setActivePinia(createPinia())

const { useMapStore } = await import('../src/stores/map')
const { useProjectStore } = await import('../src/stores/project')
const { useTileAssetImport } = await import('../src/composables/useTileAssetImport')

const mapStore = useMapStore()
const projectStore = useProjectStore()
const { importTileImage, refitTilesetsToGrid } = useTileAssetImport()

const PROJECT_ROOT = '/tmp/bingo-tile-stress-project'
projectStore.setProject(PROJECT_ROOT, 'stress')

// ===================== 断言 / 结果收集 =====================
const results: { name: string; ok: boolean; detail: string }[] = []
const risks: { level: '高' | '中' | '低'; name: string; detail: string }[] = []

async function test(name: string, fn: () => Promise<void> | void) {
  try {
    await fn()
    results.push({ name, ok: true, detail: '通过' })
    console.log(`✅ ${name}`)
  } catch (e: any) {
    results.push({ name, ok: false, detail: e?.message ?? String(e) })
    console.error(`❌ ${name}\n   ${e?.message ?? e}`)
  }
}

function assert(cond: any, msg: string) {
  if (!cond) throw new Error(msg)
}

function risk(level: '高' | '中' | '低', name: string, detail: string) {
  risks.push({ level, name, detail })
  console.log(`   ⚠️ [${level}] ${name}：${detail}`)
}

// ===================== 地图 / 素材辅助 =====================
interface MapOpts {
  name?: string
  width?: number
  height?: number
  tileSize?: number
  explicit?: boolean
}

/** 每张测试地图用唯一名字（真实项目里地图名也唯一，避免文件名占位串到下一张图） */
let mapSeq = 1

/** 重置为一张空白图块地图（默认 40×30 格，格子 32） */
function resetMap(opts: MapOpts = {}) {
  resetMockFs()
  mapStore.newMap()
  const d = mapStore.mapData
  d.name = opts.name ?? `地图${mapSeq++}`
  d.width = opts.width ?? 40
  d.height = opts.height ?? 30
  d.tileSize = opts.tileSize ?? 32
  d.tileSizeExplicit = opts.explicit ?? false
  d.resources = []
  d.tileSets = []
  d.layers = []
  mapStore.addLayer('图块图层')
}

function adopt(res: any, name: string) {
  return mapStore.addResource({
    name,
    path: res.path,
    resourceType: 'tileset',
    tileWidth: res.tileWidth,
    tileHeight: res.tileHeight,
    collisionType: '图像',
    collisionEnabled: false,
    originPath: res.originPath,
    nativeTileSize: res.nativeTileSize,
    assetKind: res.assetKind,
  } as any)
}

/** 导入并像真实调用方一样把素材写进地图（真实调用方一定会传 fileName） */
async function importAndAdopt(src: string, opts: any = {}, name = '素材') {
  const res = await importTileImage(src, {
    ...opts,
    fileName: opts.fileName ?? src.split('/').pop(),
  })
  if (res) adopt(res, name)
  return res
}

function lastCanvas() {
  return canvases[canvases.length - 1]
}

function lastWrite() {
  return writes[writes.length - 1]
}

/** 核心不变量：素材的切片尺寸必须等于地图唯一格子 */
function assertGrid(res: any, label: string) {
  assert(res, `${label}: 导入返回 null`)
  assert(
    res.tileWidth === mapStore.mapData.tileSize,
    `${label}: 切片 ${res.tileWidth} ≠ 地图格子 ${mapStore.mapData.tileSize}`,
  )
  assert(res.tileHeight === res.tileWidth, `${label}: 切片非正方形 ${res.tileWidth}×${res.tileHeight}`)
  assert(
    res.path.startsWith('assets/maps/'),
    `${label}: 派生路径不在项目地图目录（${res.path}）`,
  )
  assert(!res.path.includes('..'), `${label}: 派生路径含 ..（${res.path}）`)
  assert(!res.originPath.includes('..'), `${label}: 原始路径含 ..（${res.originPath}）`)
}

// ===================== 固定回归用例 =====================
await test('1. 首次导入 16px 单图块：自动把地图格子锁成 16，像素坐标同步放大', async () => {
  resetMap({ tileSize: 32 })
  addFile('/lib/tile16.png', 16, 16)
  const res = await importAndAdopt('/lib/tile16.png', { kind: 'tile' }, '16砖块')

  assert(res, '首次导入应成功')
  assert(mapStore.mapData.tileSize === 16, `格子应锁为 16，实际 ${mapStore.mapData.tileSize}`)
  assert(mapStore.mapData.tileSizeExplicit === true, '首次导入后应锁定格子')
  assert(mapStore.mapData.width === 80, `地图宽应 40→80，实际 ${mapStore.mapData.width}`)
  assert(mapStore.mapData.height === 60, `地图高应 30→60，实际 ${mapStore.mapData.height}`)
  assertGrid(res, '首次导入')
  assert(res.path === res.originPath, '尺寸一致时不应生成派生图')
  assert(writes.length === 0, `不应写派生图（写了 ${writes.length} 次）`)
  assert(copies.length === 1 && copies[0] === `assets/maps/${mapStore.mapData.name}/images/tile16.png`, `复制路径不对：${copies}`)
})

await test('2. 锁定 16 后导入 24px 图集：逐块缩放，每块对齐且无累积漂移', async () => {
  resetMap({ tileSize: 16, explicit: true })
  addFile('/lib/s24.png', 48, 48) // 2×2 块，每块 24
  const res = await importAndAdopt('/lib/s24.png', { kind: 'tileset', tileSize: 24 }, '24图集')

  assertGrid(res, '24→16')
  assert(res.nativeTileSize === 24, `应记录原始尺寸 24，实际 ${res.nativeTileSize}`)
  assert(res.path.endsWith('s24@16.png'), `派生文件名应为 s24@16.png，实际 ${res.path}`)

  const canvas = lastCanvas()
  assert(canvas, '应创建缩放画布')
  assert(canvas.width === 32 && canvas.height === 32, `画布应 32×32，实际 ${canvas.width}×${canvas.height}`)
  assert(canvas.smoothing === false, '必须关闭平滑（最近邻）')
  assert(canvas.drawCalls.length === 4, `非整数倍应逐块绘制 4 次，实际 ${canvas.drawCalls.length}`)
  const expect = [
    [0, 0, 24, 24, 0, 0, 16, 16],
    [24, 0, 24, 24, 16, 0, 16, 16],
    [0, 24, 24, 24, 0, 16, 16, 16],
    [24, 24, 24, 24, 16, 16, 16, 16],
  ]
  canvas.drawCalls.forEach((c, i) => {
    assert(JSON.stringify(c.args) === JSON.stringify(expect[i]), `第 ${i} 块坐标错误：${c.args}`)
  })

  const write = lastWrite()
  assert(write, '应写入派生图')
  assert(write.path === `${PROJECT_ROOT}/assets/maps/${mapStore.mapData.name}/images/s24@16.png`, `派生图路径错误：${write.path}`)
  assert(write.payload === 'FIT:32x32', `派生图尺寸错误：${write.payload}`)
})

await test('3. 锁定 32 后导入 16px 单图块：整数倍整图放大（1 次 drawImage）', async () => {
  resetMap({ tileSize: 32 })
  addFile('/lib/a32.png', 64, 64)
  await importAndAdopt('/lib/a32.png', { kind: 'tileset', tileSize: 32 }, '32图集')

  addFile('/lib/tile16.png', 16, 16)
  const res = await importAndAdopt('/lib/tile16.png', { kind: 'tile' }, '16砖块')
  assertGrid(res, '16→32')
  const canvas = lastCanvas()
  assert(canvas.width === 32 && canvas.height === 32, `画布应 32×32，实际 ${canvas.width}×${canvas.height}`)
  assert(canvas.drawCalls.length === 1, `整数倍应整图一次绘制，实际 ${canvas.drawCalls.length}`)
  assert(mapStore.mapData.tileSize === 32, '已有素材后不应再改格子')
})

await test('4. 已画过图块的图层：导入新素材不再自动改格子', async () => {
  resetMap({ tileSize: 32 })
  const layer: any = mapStore.mapData.layers[0]
  layer.tiles = { '0,0': 1 }
  addFile('/lib/tile16.png', 16, 16)
  const res = await importAndAdopt('/lib/tile16.png', { kind: 'tile' }, '16砖块')
  assertGrid(res, '已画图块')
  assert(mapStore.mapData.tileSize === 32, `不应改格子，实际 ${mapStore.mapData.tileSize}`)
  assert(mapStore.mapData.tileSizeExplicit === false, '不应把格子标记为手动锁定')
  assert(res.nativeTileSize === 16, '应记录原始尺寸 16')
})

await test('5. 未设定尺寸的图集：按当前格子切原图（对齐但不缩放）', async () => {
  resetMap({ tileSize: 16, explicit: true })
  addFile('/lib/unknown.png', 64, 64)
  const res = await importAndAdopt('/lib/unknown.png', { kind: 'tileset' }, '未设定图集')
  assertGrid(res, '未知尺寸')
  assert(res!.path === res!.originPath, '未知尺寸不应生成派生图')
  assert(res!.nativeTileSize === undefined, '未设定尺寸时不应伪造 nativeTileSize')
  assert(canvases.length === 0, '未设定尺寸不应触发缩放')
  risk('低', '无元数据时无法推断图集的真实图块尺寸', '现在会输出明确告警（不再静默），但仍只能按当前格子切；建议在素材整理里给图集补齐尺寸')
})

await test('6. 非法 tileSize（NaN / 0 / 负数 / 字符串 / 小数）不崩溃且不污染地图', async () => {
  resetMap({ tileSize: 16, explicit: true })
  addFile('/lib/odd.png', 32, 32)
  for (const bad of [NaN, 0, -16, '16' as any, 0.4, 16.6]) {
    const res = await importAndAdopt('/lib/odd.png', { kind: 'tileset', tileSize: bad }, `坏值${String(bad)}`)
    assertGrid(res, `tileSize=${String(bad)}`)
    assert(res!.nativeTileSize === undefined, `tileSize=${String(bad)} 应视为未设定`)
    assert(res!.path === res!.originPath, `tileSize=${String(bad)} 不应生成派生图`)
  }
  assert(mapStore.mapData.tileSize === 16, '非法尺寸不应改地图格子')
  risk('低', '非标准 tileSize 被忽略', '索引里出现 16.6 / 20 这类非标准值时按「未设定」处理（按当前格子切），不会崩溃或污染地图')
})

await test('7. 极大 tileSize：被校验拦截，地图保持原状', async () => {
  resetMap({ tileSize: 32, width: 40, height: 30 })
  mapStore.updateTileSize(1_000_000, true)
  assert(mapStore.mapData.tileSize === 32, `应拒绝 1000000，实际 ${mapStore.mapData.tileSize}`)
  assert(mapStore.mapData.width === 40 && mapStore.mapData.height === 30, `地图不应被压缩，实际 ${mapStore.mapData.width}×${mapStore.mapData.height}`)
  assert(mapStore.mapData.tileSizeExplicit === false, '被拒绝的尺寸不应锁定格子')

  addFile('/lib/huge.png', 2048, 2048)
  const res = await importAndAdopt('/lib/huge.png', { kind: 'tileset', tileSize: 1_000_000 }, '巨图集')
  assert(res, '导入不应崩溃')
  assertGrid(res, '巨图集')
  assert(mapStore.mapData.tileSize === 32, '异常尺寸不应改格子')
  assert(mapStore.mapData.width === 40 && mapStore.mapData.height === 30, '地图宽高应保持原状')
})

await test('8. 超大画布：拒绝导入，不破坏对齐不变量', async () => {
  resetMap({ tileSize: 8 })
  addFile('/lib/tiny8.png', 8, 8)
  await importAndAdopt('/lib/tiny8.png', { kind: 'tile' }, '8砖块')

  // 12000×12000 / 12 = 1000×1000 块，目标 8000×8000 = 64M 像素 > 33.5M 上限
  addFile('/lib/large.png', 12000, 12000)
  const res = await importTileImage('/lib/large.png', { kind: 'tileset', tileSize: 12, fileName: 'large.png' })
  assert(res === null, '超限缩放应拒绝导入')
  assert(writes.length === 0, `不应写派生图，实际写了 ${writes.length} 次`)
  assert(mapStore.mapData.resources.length === 1, `只应保留第一个素材，实际 ${mapStore.mapData.resources.length}`)
  assert(mapStore.mapData.tileSize === 8, '地图格子不应改变')
})

await test('9. 零尺寸 / 非正方形单图块：拒绝导入，不再静默裁切', async () => {
  resetMap({ tileSize: 16, explicit: true })
  addFile('/lib/zero.png', 0, 0)
  const zero = await importTileImage('/lib/zero.png', { kind: 'tileset', tileSize: 16, fileName: 'zero.png' })
  assert(zero === null, '零尺寸图片应拒绝导入')
  assert(copies.length === 0, '零尺寸图片不应复制到项目')

  resetMap({ tileSize: 32, explicit: true })
  addFile('/lib/rect.png', 64, 32)
  const rect = await importTileImage('/lib/rect.png', { kind: 'tile', fileName: 'rect.png' })
  assert(rect === null, '非正方形单图块应拒绝导入')
  assert(copies.length === 0, '非正方形单图块不应复制到项目')
  assert(mapStore.mapData.resources.length === 0, '不应新增素材')
})

await test('10. 文件名路径穿越被剥离（/ 与 \\ 两种分隔符）', async () => {
  resetMap({ tileSize: 32 })
  addFile('/lib/a.png', 32, 32)
  const r1 = await importAndAdopt('/lib/a.png', { fileName: '../../../../evil.png' }, '穿越1')
  assertGrid(r1, '穿越1')
  assert(copies[0] === `assets/maps/${mapStore.mapData.name}/images/evil.png`, `文件名穿越未被剥离：${copies[0]}`)

  const r2 = await importAndAdopt('/lib/a.png', { fileName: '..\\..\\evil2.png' }, '穿越2')
  assertGrid(r2, '穿越2')
  assert(!copies[1].includes('..'), `反斜杠穿越未被剥离：${copies[1]}`)
})

await test('11. 地图名含 ../：拒绝导入，不会写到项目目录之外', async () => {
  resetMap({ tileSize: 32, explicit: true, name: '../../../../tmp/evil-map' })
  addFile('/lib/a.png', 32, 32)
  const res = await importTileImage('/lib/a.png', { fileName: 'a.png' })
  assert(res === null, '非法地图名应拒绝导入')
  assert(copies.length === 0, `不应产生任何复制路径，实际 ${copies[0]}`)
})

await test('12. 串行重复导入同名文件：自动 -2 后缀，不覆盖', async () => {
  resetMap({ tileSize: 32 })
  addFile('/lib/same.png', 32, 32)
  await importAndAdopt('/lib/same.png', { kind: 'tileset', tileSize: 32 }, '第一次')
  await importAndAdopt('/lib/same.png', { kind: 'tileset', tileSize: 32 }, '第二次')
  assert(copies.length === 2, `应复制两次，实际 ${copies.length}`)
  assert(copies[0] === `assets/maps/${mapStore.mapData.name}/images/same.png`, `第一次路径：${copies[0]}`)
  assert(copies[1] === `assets/maps/${mapStore.mapData.name}/images/same-2.png`, `第二次应加 -2，实际 ${copies[1]}`)
})

await test('13. 并发导入同名文件：各自占位不同文件名，不再互相覆盖', async () => {
  resetMap({ tileSize: 32 })
  addFile('/lib/dirA/same.png', 32, 32)
  addFile('/lib/dirB/same.png', 32, 32)
  const [ra, rb] = await Promise.all([
    importTileImage('/lib/dirA/same.png', { kind: 'tileset', tileSize: 32, fileName: 'same.png' }),
    importTileImage('/lib/dirB/same.png', { kind: 'tileset', tileSize: 32, fileName: 'same.png' }),
  ])
  assert(ra && rb, '并发导入不应失败')
  assert(copies.length === 2, `应复制两次，实际 ${copies.length}`)
  assert(copies[0] !== copies[1], `两个并发导入占用了同一路径：${copies[0]}`)
  assert(ra!.path !== rb!.path, `两个素材不应共用同一路径：${ra!.path}`)
})

await test('14. 并发「首次导入」：只有一个真正锁定格子，结果一致', async () => {
  resetMap({ tileSize: 32 })
  addFile('/lib/t16.png', 16, 16)
  addFile('/lib/s32.png', 64, 64)
  const [single, sheet] = await Promise.all([
    importTileImage('/lib/t16.png', { kind: 'tile', fileName: 't16.png' }),
    importTileImage('/lib/s32.png', { kind: 'tileset', tileSize: 32, fileName: 's32.png' }),
  ])
  assert(single && sheet, '并发首次导入不应失败')
  const grid = mapStore.mapData.tileSize
  assert(grid === 16 || grid === 32, `格子应被其中一个锁定，实际 ${grid}`)
  assert(single!.tileWidth === grid, `单图块切片 ${single!.tileWidth} ≠ 最终格子 ${grid}`)
  assert(sheet!.tileWidth === grid, `图集切片 ${sheet!.tileWidth} ≠ 最终格子 ${grid}`)
  assert(mapStore.mapData.tileSizeExplicit === true, '应锁定格子')
})

await test('15. refit 同尺寸重复调用：完全跳过，不重复读图 / 不重复写盘', async () => {
  resetMap({ tileSize: 16, explicit: true })
  addFile('/lib/n32.png', 64, 64)
  await importAndAdopt('/lib/n32.png', { kind: 'tileset', tileSize: 32 }, '32图集')
  // 导入时已经生成了目标格子的派生图，refit 不应再做任何处理
  const before = writes.length

  await refitTilesetsToGrid(16)
  assert(writes.length === before, `导入后已对齐，refit 不应再写盘，实际多写 ${writes.length - before} 次`)
  await refitTilesetsToGrid(16)
  assert(writes.length === before, `第二次同尺寸 refit 不应写盘，实际多写 ${writes.length - before} 次`)
  assert(mapStore.mapData.resources[0].tileWidth === 16, 'refit 后切片应等于目标格子')
})

await test('16. 改格子后 refit：所有素材都能重新归一化，切回原尺寸恢复原图', async () => {
  resetMap({ tileSize: 16, explicit: true })
  addFile('/lib/n32.png', 64, 64)
  await importAndAdopt('/lib/n32.png', { kind: 'tileset', tileSize: 32 }, '32图集')
  addFile('/lib/t16.png', 16, 16)
  await importAndAdopt('/lib/t16.png', { kind: 'tile' }, '16砖块')

  mapStore.updateTileSize(24, true)
  await refitTilesetsToGrid(24)
  for (const r of mapStore.mapData.resources) {
    assert(r.tileWidth === 24, `改 24 后 ${r.name} 切片 ${r.tileWidth}`)
  }
  const sheetWrite = writes.find(w => w.path.endsWith('n32@24.png'))
  assert(sheetWrite, '32→24 应写入 n32@24.png')
  assert(sheetWrite!.payload === 'FIT:48x48', `32→24 的 2×2 图集应生成 48×48，实际 ${sheetWrite!.payload}`)

  mapStore.updateTileSize(32, true)
  await refitTilesetsToGrid(32)
  const sheetRes = mapStore.mapData.resources.find(r => r.name === '32图集')!
  assert(sheetRes.path === sheetRes.originPath, '切回原始尺寸应恢复原图')
  assert(sheetRes.tileWidth === 32, `切回 32 后切片应 32，实际 ${sheetRes.tileWidth}`)

  // 再次 refit 同尺寸：路径应保持不变（重复写盘已在用例 15 记录为风险）
  const pathsBefore = mapStore.mapData.resources.map(r => r.path).join('|')
  await refitTilesetsToGrid(32)
  const pathsAfter = mapStore.mapData.resources.map(r => r.path).join('|')
  assert(pathsAfter === pathsBefore, `重复 refit 改变了素材路径：${pathsBefore} → ${pathsAfter}`)
})

await test('17. 旧素材没有原始尺寸：按新格子切原图并补登记', async () => {
  resetMap({ tileSize: 16 })
  const id = mapStore.addResource({
    name: '旧素材',
    path: 'assets/maps/地图1/images/old.png',
    resourceType: 'tileset',
    tileWidth: 32,
    tileHeight: 32,
    collisionType: '图像',
    collisionEnabled: false,
  } as any)
  addFile(`${PROJECT_ROOT}/assets/maps/地图1/images/old.png`, 128, 128)

  await refitTilesetsToGrid(16)
  const res = mapStore.mapData.resources.find(r => r.id === id)!
  assert(res.tileWidth === 16, `旧素材应改为 16，实际 ${res.tileWidth}`)
  assert(res.originPath === 'assets/maps/地图1/images/old.png', `应补登记 originPath，实际 ${res.originPath}`)
  assert(res.nativeTileSize === undefined, '旧素材不应伪造 nativeTileSize')

  const writeCount = writes.length
  await refitTilesetsToGrid(16)
  assert(writes.length === writeCount, '旧素材已对齐时不应重复处理')
})

await test('18. 读取图片失败：返回 null，不复制、不污染地图', async () => {
  resetMap({ tileSize: 32 })
  const res = await importTileImage('/lib/missing.png', { kind: 'tile' })
  assert(res === null, `读取失败应返回 null，实际 ${res}`)
  assert(copies.length === 0, '读取失败不应复制文件')
  assert(mapStore.mapData.resources.length === 0, '读取失败不应新增素材')
  assert(mapStore.mapData.tileSize === 32, '读取失败不应改格子')
})

await test('19. 非整数倍逐块绘制的规模：85×85 块 = 7225 次 drawImage（可接受）', async () => {
  resetMap({ tileSize: 16, explicit: true })
  addFile('/lib/big24.png', 2040, 2040)
  const t0 = performance.now()
  const res = await importAndAdopt('/lib/big24.png', { kind: 'tileset', tileSize: 24 }, '大图集')
  const ms = performance.now() - t0

  assertGrid(res, '大图集')
  const canvas = lastCanvas()
  assert(canvas.width === 1360 && canvas.height === 1360, `画布应 1360×1360，实际 ${canvas.width}×${canvas.height}`)
  assert(canvas.drawCalls.length === 85 * 85, `应绘制 7225 次，实际 ${canvas.drawCalls.length}`)
  console.log(`   ↳ 非整数倍 7225 块逐块缩放耗时（mock canvas）：${ms.toFixed(1)}ms`)
  risk('低', '超大非整数倍图集会退化为逐块绘制', `例如 2040×2040、24px 图集换算到 16px 需要 ${85 * 85} 次 drawImage；已加「块数 > 2000」告警，真机仍可能有明显卡顿`)
})

// ===================== 随机压力测试 =====================
function mulberry32(seed: number) {
  return function () {
    seed |= 0
    seed = (seed + 0x6D2B79F5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const COMMON_SIZES = [8, 16, 24, 32, 48, 64]

interface StressStats {
  seed: number
  imports: number
  firstLocks: number
  refits: number
  gridChanges: number
  maxDrawCalls: number
  ms: number
}

async function runStress(seed: number, steps: number): Promise<StressStats> {
  const rand = mulberry32(seed)
  const pick = <T,>(arr: T[]): T => arr[Math.floor(rand() * arr.length)]
  const stats: StressStats = {
    seed, imports: 0, firstLocks: 0, refits: 0, gridChanges: 0, maxDrawCalls: 0, ms: 0,
  }
  const t0 = performance.now()
  resetMap({ tileSize: pick(COMMON_SIZES) })
  // 首次导入可能把格子改成素材自己的尺寸，之后必须保持稳定
  let expectedGrid = mapStore.mapData.tileSize

  for (let i = 0; i < steps; i++) {
    const native = pick(COMMON_SIZES)
    // 图片大小：2~4 × native，保证是完整图块
    const factor = 2 + Math.floor(rand() * 3)
    const isTile = rand() < 0.35
    const path = `/lib/s${seed}-${i}.png`
    addFile(path, isTile ? native : native * factor, isTile ? native : native * factor)

    const before = mapStore.mapData.tileSize
    const res = await importTileImage(path, isTile
      ? { kind: 'tile', fileName: `s${seed}-${i}.png` }
      : { kind: 'tileset', tileSize: native, fileName: `s${seed}-${i}.png` })
    assert(res, `随机 ${seed}#${i}: 导入返回 null`)
    adopt(res, `素材${i}`)
    assertGrid(res, `随机 ${seed}#${i} (native=${native}, grid=${mapStore.mapData.tileSize})`)

    if (i === 0) {
      stats.firstLocks++
      expectedGrid = mapStore.mapData.tileSize
    } else {
      assert(
        mapStore.mapData.tileSize === expectedGrid,
        `随机 ${seed}#${i}: 首次锁定后格子不应再自动变化（${expectedGrid} → ${mapStore.mapData.tileSize}，本次 native=${native}，导入前=${before}）`,
      )
    }
    if (canvases.length > 0) stats.maxDrawCalls = Math.max(stats.maxDrawCalls, lastCanvas().drawCalls.length)
    stats.imports++

    // 每 12 次随机改一次格子，并全量重新归一化
    if (i > 0 && i % 12 === 0) {
      const next = pick(COMMON_SIZES)
      mapStore.updateTileSize(next, true)
      await refitTilesetsToGrid(next)
      expectedGrid = next
      stats.gridChanges++
      stats.refits++
      for (const r of mapStore.mapData.resources) {
        assert(r.tileWidth === next, `随机 ${seed}#${i}: refit 后 ${r.name} 切片 ${r.tileWidth} ≠ ${next}`)
        assert(r.tileHeight === next, `随机 ${seed}#${i}: refit 后 ${r.name} 高度 ${r.tileHeight} ≠ ${next}`)
      }
    }
  }

  // 收尾：再全量 refit 一次，确保最终状态一致
  const finalGrid = pick(COMMON_SIZES)
  mapStore.updateTileSize(finalGrid, true)
  await refitTilesetsToGrid(finalGrid)
  for (const r of mapStore.mapData.resources) {
    assert(r.tileWidth === finalGrid, `随机 ${seed} 收尾: ${r.name} 切片 ${r.tileWidth} ≠ ${finalGrid}`)
  }
  stats.ms = performance.now() - t0
  return stats
}

await test('20. 随机压力：4 个种子 × 80 次导入 + 周期性改格子', async () => {
  const seeds = [20261106, 20261107, 20261108, 20261109]
  const all: StressStats[] = []
  for (const seed of seeds) all.push(await runStress(seed, 80))

  for (const s of all) {
    console.log(
      `   ↳ seed ${s.seed}：导入 ${s.imports} 次，首次锁定 ${s.firstLocks} 次，`
      + `改格子 ${s.gridChanges} 次 / refit ${s.refits} 次，单次最大逐块绘制 ${s.maxDrawCalls} 次，耗时 ${s.ms.toFixed(0)}ms`,
    )
  }
  const sum = all.reduce((n, s) => n + s.imports, 0)
  assert(sum === seeds.length * 80, `随机导入次数异常：${sum}`)
  assert(all.every(s => s.firstLocks === 1), `每个种子应只锁定一次格子：${all.map(s => s.firstLocks)}`)
  assert(all.every(s => s.gridChanges === 6), `每个种子应改 6 次格子：${all.map(s => s.gridChanges)}`)
})

// ===================== 汇总 =====================
const failed = results.filter(r => !r.ok)
console.log('\n================ 测试结果 ================')
console.log(`用例：${results.length}，通过：${results.length - failed.length}，失败：${failed.length}`)
if (unhandled) console.log(`异步异常（不致命）：${unhandled} 条`)
if (failed.length) {
  for (const f of failed) console.log(`- ${f.name}: ${f.detail}`)
}

console.log('\n================ 发现的风险 ================')
if (risks.length === 0) console.log('无')
for (const r of risks) console.log(`[${r.level}] ${r.name}：${r.detail}`)

process.exitCode = failed.length ? 1 : 0
