/**
 * 地图编辑器回归 + 压力测试（纯 Node 环境，无需启动 Tauri）
 *
 * 运行：pnpm exec tsx scripts/map-editor-stress.ts
 *
 * 覆盖三次改动中可离线验证的核心逻辑：
 *  1. 缩略图/画布读图失败不再写缓存（组件逻辑，这里只覆盖数据层：路径失效不污染地图数据）
 *  2. 删除正在打开的地图后编辑器复位、删除地图后禁止自动保存复活（store 层复位 + 序列化往返）
 *  3. 图片素材不再占用图块 GID 空间、旧存档里被误建的图片图块集在读取时被清理
 */
import { createPinia, setActivePinia } from 'pinia'

// ---- 先造一个最小的浏览器 / Tauri 环境，再动态导入业务模块 ----
const g = globalThis as any
g.window = globalThis
const memStore = new Map<string, string>()
g.localStorage = {
  getItem: (k: string) => memStore.get(k) ?? null,
  setItem: (k: string, v: string) => void memStore.set(k, v),
  removeItem: (k: string) => void memStore.delete(k),
  clear: () => memStore.clear(),
}
g.__TAURI_INTERNALS__ = {
  invoke: async () => null,
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
const { serializeMap, deserializeMap } = await import('../src/utils/mapSerializer')
const { tileBaseGid, withTileFlip } = await import('../src/utils/tileGid')

const mapStore = useMapStore()

// ===================== 断言工具 =====================
const results: { name: string; ok: boolean; detail: string }[] = []
function test(name: string, fn: () => void) {
  try {
    fn()
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

// ===================== 不变量 =====================
/** 与 MapCanvas.renderTile 一致：GID → 图块素材（必须排除图片素材） */
function resolveByGid(map: any, gid: number): any {
  const base = tileBaseGid(gid)
  let matched: any = null
  for (let i = map.tileSets.length - 1; i >= 0; i--) {
    if (base < map.tileSets[i].firstgid) continue
    matched = map.tileSets[i]
    break
  }
  if (!matched) return null
  return map.resources.find((r: any) => r.resourceType !== 'image' && r.id === matched.id)
    ?? map.resources.find((r: any) => r.resourceType !== 'image' && r.firstgid === matched.firstgid)
    ?? map.resources.find((r: any) => r.resourceType !== 'image' && r.path === matched.imagePath)
    ?? null
}

function assertInvariants(map: any, label: string) {
  const imageResources = map.resources.filter((r: any) => r.resourceType === 'image')
  // 1. 图片素材不能有对应的图块集（否则会抢走同 firstgid 的图块渲染）
  const badSets = map.tileSets.filter((ts: any) =>
    imageResources.some((r: any) => (ts.id && r.id === ts.id) || (r.path === ts.imagePath && r.name === ts.name)),
  )
  assert(badSets.length === 0, `${label}: 图片素材被当成图块集（${badSets.map((t: any) => t.name).join(',')}）`)

  // 2. 图块素材的 firstgid 必须唯一
  const tileResources = map.resources.filter((r: any) => r.resourceType !== 'image')
  const gids = tileResources.map((r: any) => r.firstgid)
  assert(new Set(gids).size === gids.length, `${label}: 图块素材 firstgid 重复（${gids.join(',')}）`)

  // 3. 每个图块素材都要有对应图块集
  for (const r of tileResources) {
    assert(map.tileSets.some((ts: any) => ts.id === r.id), `${label}: 图块素材 ${r.name} 缺少图块集`)
  }

  // 4. 图块图层的 groupId 必须有效
  for (const l of map.layers) {
    if (l.type !== 'drawing' || !l.groupId) continue
    assert(
      (map.tilesetGroups ?? []).some((gp: any) => gp.id === l.groupId),
      `${label}: 图层 ${l.name} 的图块集分组不存在`,
    )
  }

  // 5. 已画图块必须都能解析到对应的图块素材：删除 / 清空素材时所有图层都要被清理，
  //    不允许留下渲染不出来的孤儿 GID（GID 空间重新分配后会被错误素材接住）
  for (const l of map.layers) {
    if (l.type !== 'drawing') continue
    for (const [key, gid] of Object.entries(l.tiles ?? {})) {
      if (!gid) continue
      const base = tileBaseGid(gid as number)
      const covering = map.tileSets.filter((ts: any) => base >= ts.firstgid).pop()
      assert(covering, `${label}: 图块 ${key}=${gid} 是孤儿（没有任何图块集覆盖）`)
      const res = resolveByGid(map, gid as number)
      assert(res !== null, `${label}: 图块 ${key}=${gid} 有图块集覆盖却解析不到素材`)
      assert(res!.resourceType !== 'image', `${label}: 图块 ${key}=${gid} 解析到了图片素材 ${res!.name}`)
      assert(res!.id === covering.id || res!.path === covering.imagePath, `${label}: 图块 ${key}=${gid} 解析到了错误的素材 ${res!.name}`)
    }
  }

  // 6. 素材 id 必须唯一（图层、调色板、图块集都靠 id 引用）
  const ids = map.resources.map((r: any) => r.id)
  assert(new Set(ids).size === ids.length, `${label}: 素材 id 重复（${ids.join(',')}）`)

  // 7. 图块集必须按 firstgid 升序：渲染时取「最后一个 firstgid <= GID」的图块集，
  //    顺序错乱会把图块解析到错误的图块集上
  for (let i = 1; i < map.tileSets.length; i++) {
    assert(
      map.tileSets[i].firstgid > map.tileSets[i - 1].firstgid,
      `${label}: 图块集 firstgid 未升序（${map.tileSets.map((ts: any) => ts.firstgid).join(',')}）`,
    )
  }

  // 8. 每个图块集都必须能反查到对应的图块素材（渲染时 GID → 图块集 → 素材）
  for (const ts of map.tileSets) {
    const res = map.resources.find((r: any) => r.resourceType !== 'image' && r.id === ts.id)
      ?? map.resources.find((r: any) => r.resourceType !== 'image' && r.firstgid === ts.firstgid)
      ?? map.resources.find((r: any) => r.resourceType !== 'image' && r.path === ts.imagePath)
    assert(res, `${label}: 图块集 ${ts.name} 找不到对应的图块素材`)
  }

  // 9. 调色板条目必须指向现存的图块素材（否则点上去画不出来）
  for (const e of map.tilePalette ?? []) {
    assert(
      map.resources.some((r: any) => r.resourceType !== 'image' && r.id === e.resourceId),
      `${label}: 调色板引用了不存在的素材 ${e.resourceId}`,
    )
  }
}

/** 加一张图片素材（模拟「绘制背景」） */
function addImageResource(name: string, path: string) {
  mapStore.addResource({
    name,
    path,
    resourceType: 'image',
    tileWidth: 640,
    tileHeight: 480,
    collisionType: '图像',
    collisionEnabled: false,
  } as any)
}

/** 加一个图块素材并返回它（自动进入当前图块图层的分组） */
function addTileResource(name: string, path: string) {
  const id = mapStore.addResource({
    name,
    path,
    resourceType: 'tileset',
    tileWidth: 16,
    tileHeight: 16,
    collisionType: '图像',
    collisionEnabled: false,
  } as any)
  const res = mapStore.mapData.resources.find(r => r.id === id)!
  return res
}

function roundTrip(label: string) {
  const save = serializeMap(mapStore.mapData)
  const loaded = deserializeMap(save as any)
  mapStore.loadMap(loaded as any)
  assertInvariants(mapStore.mapData, label)
  return save
}

// ===================== 固定回归用例 =====================
mapStore.newMap()

test('A. 图片素材不再创建图块集，也不占用图块 GID 空间', () => {
  mapStore.newMap()
  const before = mapStore.mapData.tileSets.length
  addImageResource('绘制背景', 'assets/maps/地图1/images/绘制背景.png')
  assert(mapStore.mapData.resources.length === 1, '图片素材应写入 resources')
  assert(mapStore.mapData.tileSets.length === before, '图片素材不应该创建图块集')
  assertInvariants(mapStore.mapData, 'A')
})

test('B. 图片素材与图块素材 firstgid 不再碰撞', () => {
  mapStore.newMap()
  addImageResource('绘制背景', 'assets/maps/地图1/images/绘制背景.png')
  mapStore.addLayer('图块图层')
  const t1 = addTileResource('金属砖块_1', 'assets/maps/地图1/images/砖1.png')
  const t2 = addTileResource('金属砖块_2', 'assets/maps/地图1/images/砖2.png')
  assert(t1.firstgid !== t2.firstgid, `两次图块素材 firstgid 应不同（${t1.firstgid}/${t2.firstgid}）`)
  const image = mapStore.mapData.resources.find(r => r.resourceType === 'image')!
  // 关键：GID 解析必须命中图块素材而不是图片素材
  const res = resolveByGid(mapStore.mapData, t2.firstgid)
  assert(res && res.id === t2.id, `GID=${t2.firstgid} 应解析到 ${t2.name}，实际 ${res?.name}`)
  assertInvariants(mapStore.mapData, 'B')
})

test('C. 复现报告 bug：删图块图层 → 重建 → 上传 → 能画且能渲染', () => {
  mapStore.newMap()
  // 先有绘制背景（图片素材）
  addImageResource('绘制背景', 'assets/maps/地图1/images/绘制背景.png')
  mapStore.addLayer('图块图层')
  const r1 = addTileResource('砖块', 'assets/maps/地图1/images/砖1.png')
  const gid1 = r1.firstgid
  mapStore.setTile(1, 1, gid1)
  assert(resolveByGid(mapStore.mapData, gid1)?.id === r1.id, '首次绘制应能解析到砖块')

  // 删除这个唯一的图块图层（触发清理分支）
  mapStore.setActiveLayer(mapStore.mapData.layers.findIndex(l => l.type === 'drawing'))
  mapStore.removeLayer(mapStore.activeLayerIndex)
  assert(mapStore.mapData.tileSets.length === 0, '删除最后一个图块图层应清空图块集')
  assert(
    mapStore.mapData.resources.filter(r => r.resourceType !== 'image').length === 0,
    '删除最后一个图块图层应清空图块素材',
  )

  // 重建图块图层并重新上传
  mapStore.addLayer('图块图层')
  const r2 = addTileResource('砖块', 'assets/maps/地图1/images/砖3.png')
  mapStore.setTile(2, 2, r2.firstgid)
  const resolved = resolveByGid(mapStore.mapData, r2.firstgid)
  assert(resolved?.id === r2.id, `重建后 GID=${r2.firstgid} 应解析到新砖块，实际 ${resolved?.name}`)
  assert(resolved?.resourceType !== 'image', '重建后不能解析到图片素材')
  assertInvariants(mapStore.mapData, 'C')
})

test('D. clearResources 不会误删图块集（原 firstgid 混用 bug）', () => {
  mapStore.newMap()
  addImageResource('绘制背景', 'assets/maps/地图1/images/绘制背景.png')
  mapStore.addLayer('图块图层')
  const groupA = mapStore.addTilesetGroupToActiveLayer()!
  const rA = addTileResource('砖块A', 'assets/maps/地图1/images/砖A.png')
  mapStore.setTile(0, 0, rA.firstgid)

  mapStore.addLayer('图块图层')
  const groupB = mapStore.addTilesetGroupToActiveLayer()!
  const rB = addTileResource('砖块B', 'assets/maps/地图1/images/砖B.png')

  // 选中 A 图层后清空它所在分组的素材
  const idxA = mapStore.mapData.layers.findIndex(l => l.type === 'drawing' && (l as any).groupId === groupA)
  mapStore.setActiveLayer(idxA)
  mapStore.clearResources()

  assert(
    mapStore.mapData.tileSets.some(ts => ts.id === rB.id),
    '清空 A 组素材时误删了 B 组的图块集',
  )
  assert(
    mapStore.mapData.resources.some(r => r.id === rB.id),
    '清空 A 组素材时误删了 B 组的素材',
  )
  assertInvariants(mapStore.mapData, 'D')
})

test('E. 旧存档（图片素材被误建成图块集）读取时自愈', () => {
  mapStore.newMap()
  addImageResource('绘制背景', 'assets/maps/地图1/images/绘制背景.png')
  mapStore.addLayer('图块图层')
  const tileRes = addTileResource('金属砖块_2', 'assets/maps/地图1/images/砖2.png')
  mapStore.setTile(3, 3, tileRes.firstgid)
  const save: any = serializeMap(mapStore.mapData)

  // 人为造出「旧版本会写出来的坏数据」：图片素材也有图块集，且 firstgid 与图块素材相同
  const imageRes: any = save.resources.find((r: any) => r.resourceType === 'image')
  imageRes.firstgid = tileRes.firstgid
  save.tilesets.push({
    id: imageRes.id ?? '',
    name: imageRes.name,
    image: imageRes.path,
    tileWidth: 640,
    tileHeight: 480,
    firstgid: tileRes.firstgid,
    collisionType: '图像',
    collisionEnabled: false,
    tiles: [],
  })

  const loaded = deserializeMap(save)
  mapStore.loadMap(loaded as any)
  const bad = mapStore.mapData.tileSets.filter(ts =>
    mapStore.mapData.resources.some(r => r.resourceType === 'image' && ((ts.id && r.id === ts.id) || (r.path === ts.imagePath && r.name === ts.name))),
  )
  assert(bad.length === 0, `读取旧存档后仍有图片图块集：${bad.map(t => t.name).join(',')}`)
  const res = resolveByGid(mapStore.mapData, tileRes.firstgid)
  assert(res?.id === tileRes.id, `旧存档读取后 GID=${tileRes.firstgid} 应解析到 ${tileRes.name}，实际 ${res?.name}`)
  assertInvariants(mapStore.mapData, 'E')
})

test('F. 序列化往返不丢图层/图块、不产生图片图块集', () => {
  mapStore.newMap()
  addImageResource('绘制背景', 'assets/maps/地图1/images/绘制背景.png')
  mapStore.addLayer('图块图层')
  const r1 = addTileResource('砖块', 'assets/maps/地图1/images/砖1.png')
  mapStore.setTile(0, 0, r1.firstgid)
  mapStore.setTile(3, 2, r1.firstgid)
  mapStore.addLayer('图块图层')
  const r2 = addTileResource('砖块2', 'assets/maps/地图1/images/砖2.png')
  mapStore.setTile(5, 5, r2.firstgid)

  const layersBefore = mapStore.mapData.layers.length
  const tilesBefore = mapStore.mapData.layers.reduce(
    (n, l: any) => n + Object.keys(l.tiles ?? {}).length,
    0,
  )
  roundTrip('F')
  assert(mapStore.mapData.layers.length === layersBefore, '往返后图层数量变化')
  const tilesAfter = mapStore.mapData.layers.reduce(
    (n, l: any) => n + Object.keys(l.tiles ?? {}).length,
    0,
  )
  assert(tilesAfter === tilesBefore, `往返后图块数量变化（${tilesBefore} → ${tilesAfter}）`)
})

test('G. 删除/重置地图状态（newMap）后不残留旧图层与旧图块', () => {
  mapStore.newMap()
  mapStore.addLayer('图块图层')
  addTileResource('砖块', 'assets/maps/地图1/images/砖1.png')
  mapStore.newMap()
  assert(mapStore.mapData.layers.length === 0, 'newMap 后不应残留图层')
  assert(mapStore.mapData.tileSets.length === 0, 'newMap 后不应残留图块集')
  assert(mapStore.mapData.resources.length === 0, 'newMap 后不应残留素材')
  assert(mapStore.currentMapPath === '', 'newMap 后 currentMapPath 应为空（防止自动保存写回已删除地图）')
})

test('I. 反证：旧渲染逻辑确实会命中图片素材（证明上面的用例不是空跑）', () => {
  const map: any = {
    resources: [
      { id: 'img', name: '绘制背景', path: 'a.png', resourceType: 'image', firstgid: 10001 },
      { id: 'tile', name: '砖', path: 'b.png', resourceType: 'tileset', firstgid: 10001 },
    ],
    tileSets: [
      { id: 'tile', name: '砖', imagePath: 'b.png', firstgid: 10001 },
      { id: 'img', name: '绘制背景', imagePath: 'a.png', firstgid: 10001 },
    ],
    layers: [],
  }
  // 旧写法（MapCanvas 修复前）：只按 firstgid 找第一个 → 命中图片素材，图块画上去看不见
  const old = map.resources.find((r: any) => r.firstgid === 10001)
  assert(old?.resourceType === 'image', '反证失败：旧逻辑本应命中图片素材')
  // 修复后的写法 → 命中图块素材
  const now = resolveByGid(map, 10001)
  assert(now?.id === 'tile', `修复后应命中图块素材，实际 ${now?.name}`)
})

test('J. 清空图块素材会清掉所有共用该分组图层上的图块（不留孤儿 GID 被新素材接住）', () => {
  mapStore.newMap()
  mapStore.addLayer('图块图层 A')
  const r1 = addTileResource('砖块', 'assets/maps/地图1/images/砖1.png')
  // 上传素材后 A 层才确定分组（空地图上传时自动建第一个图块集分组）
  const groupA = mapStore.activeTileGroupId
  mapStore.setTile(1, 1, r1.firstgid)

  // 新图块图层默认归入第一个图块集分组，两个绘制层共用同一组素材
  mapStore.addLayer('图块图层 B')
  assert(mapStore.activeTileGroupId === groupA, '两个图块图层应默认共用同一图块集分组')
  mapStore.setTile(2, 2, r1.firstgid)

  // 在 B 层点「清空图块」
  const bulkBefore = mapStore.tileBulkRevision
  mapStore.clearResources()
  // 跨图层清理必须发出批量刷新信号，否则其它图层的缩略图会停在旧内容
  assert(mapStore.tileBulkRevision > bulkBefore, '跨图层清理后没有发出批量刷新信号（缩略图不会更新）')
  for (const l of mapStore.mapData.layers as any[]) {
    if (l.type !== 'drawing') continue
    assert(Object.keys(l.tiles).length === 0, `${l.name} 仍残留图块（孤儿 GID）`)
  }
  assert(mapStore.mapData.tileSets.length === 0, '清空后不应残留图块集')

  // 重新上传素材：GID 空间从头开始，旧图块绝不能被新素材「复活」
  mapStore.setActiveLayer(mapStore.mapData.layers.findIndex(l => l.type === 'drawing'))
  const r2 = addTileResource('新砖块', 'assets/maps/地图1/images/新砖块.png')
  assert(r2.firstgid === 1, `清空后 GID 空间应从 1 重新开始（实际 ${r2.firstgid}）`)
  for (const l of mapStore.mapData.layers as any[]) {
    if (l.type !== 'drawing') continue
    for (const [key, gid] of Object.entries(l.tiles ?? {})) {
      assert(tileBaseGid(gid as number) !== r2.firstgid, `${l.name} 的 ${key} 旧图块被新素材接住了`)
    }
  }
  assertInvariants(mapStore.mapData, 'J')
})

test('K. 清空一个分组不会动到其它分组的图块与素材', () => {
  mapStore.newMap()
  addImageResource('绘制背景', 'assets/maps/地图1/images/背景.png')
  // A 组两个图层共用
  mapStore.addLayer('A1')
  const gA = mapStore.addTilesetGroupToActiveLayer()!
  const rA = addTileResource('砖A', 'assets/maps/地图1/images/a.png')
  mapStore.setTile(0, 0, rA.firstgid)
  mapStore.addLayer('A2')
  mapStore.useTilesetGroupForActiveLayer(gA)
  mapStore.setTile(1, 0, rA.firstgid)
  // B 组独立
  mapStore.addLayer('B1')
  const gB = mapStore.addTilesetGroupToActiveLayer()!
  const rB = addTileResource('砖B', 'assets/maps/地图1/images/b.png')
  mapStore.setTile(0, 1, rB.firstgid)

  // 在 A1 层清空 A 组
  const a1 = mapStore.mapData.layers.findIndex(l => l.name === 'A1')
  mapStore.setActiveLayer(a1)
  mapStore.clearResources()

  // A 组两个图层都清干净（共用同一组的图层必须一起清，不能留孤儿）
  for (const l of mapStore.mapData.layers as any[]) {
    if (l.type === 'drawing' && l.groupId === gA) {
      assert(Object.keys(l.tiles).length === 0, `${l.name} 仍残留 A 组图块`)
    }
  }
  assert(!mapStore.mapData.resources.some(r => r.id === rA.id), 'A 组素材应被清空')
  // B 组完全不受影响
  const b1: any = mapStore.mapData.layers.find(l => l.name === 'B1')
  assert(b1.tiles['0,1'] === rB.firstgid, 'B 组图块被误清')
  assert(resolveByGid(mapStore.mapData, rB.firstgid)?.id === rB.id, 'B 组图块解析错误')
  assert(mapStore.mapData.tileSets.some(ts => ts.id === rB.id), 'B 组图块集被误删')
  assert((mapStore.mapData.tilesetGroups ?? []).some(g => g.id === gB), 'B 组分组被误删')
  assertInvariants(mapStore.mapData, 'K')
})

test('L. 复制图块集分组：副本 GID 唯一、解析正确、原组不受影响', () => {
  mapStore.newMap()
  mapStore.addLayer('图层')
  const gA = mapStore.addTilesetGroupToActiveLayer()!
  const rA = addTileResource('砖A', 'assets/maps/地图1/images/a.png')
  mapStore.setTile(0, 0, rA.firstgid)

  const gCopy = mapStore.duplicateTilesetGroup(gA)!
  assert(!!gCopy && gCopy !== gA, '复制分组应返回新 id')
  const copyRes = mapStore.mapData.resources.filter(r => r.groupId === gCopy)
  assert(copyRes.length === 1, `副本分组应有 1 个素材（实际 ${copyRes.length}）`)
  assert(copyRes[0].firstgid !== rA.firstgid, '副本素材应分配新的 firstgid')
  assert(resolveByGid(mapStore.mapData, copyRes[0].firstgid)?.id === copyRes[0].id, '副本 GID 解析错误')
  assert(resolveByGid(mapStore.mapData, rA.firstgid)?.id === rA.id, '原组 GID 解析错误')
  const layer: any = mapStore.mapData.layers[0]
  assert(layer.tiles['0,0'] === rA.firstgid, '复制分组不应改动已画图块')
  assertInvariants(mapStore.mapData, 'L')
})

test('M. 删除中间分组：该组图块清干净、图层回落，其它分组不受影响', () => {
  mapStore.newMap()
  mapStore.addLayer('A')
  const gA = mapStore.addTilesetGroupToActiveLayer()!
  const rA = addTileResource('砖A', 'assets/maps/地图1/images/a.png')
  mapStore.setTile(0, 0, rA.firstgid)
  mapStore.addLayer('B')
  const gB = mapStore.addTilesetGroupToActiveLayer()!
  const rB = addTileResource('砖B', 'assets/maps/地图1/images/b.png')
  mapStore.setTile(0, 1, rB.firstgid)
  mapStore.addLayer('C')
  const gC = mapStore.addTilesetGroupToActiveLayer()!
  const rC = addTileResource('砖C', 'assets/maps/地图1/images/c.png')
  mapStore.setTile(0, 2, rC.firstgid)

  assert(mapStore.deleteTilesetGroup(gB) === true, '删除中间分组应成功')
  const bLayer: any = mapStore.mapData.layers.find(l => l.name === 'B')
  assert(Object.keys(bLayer.tiles).length === 0, '被删分组的图层仍有图块')
  assert(bLayer.groupId !== gB, '被删分组的图层应回落到其它分组')
  const aLayer: any = mapStore.mapData.layers.find(l => l.name === 'A')
  const cLayer: any = mapStore.mapData.layers.find(l => l.name === 'C')
  assert(aLayer.tiles['0,0'] === rA.firstgid, 'A 组图块被误删')
  assert(cLayer.tiles['0,2'] === rC.firstgid, 'C 组图块被误删')
  assert(mapStore.mapData.tileSets.some(ts => ts.id === rA.id), 'A 组图块集被误删')
  assert(mapStore.mapData.tileSets.some(ts => ts.id === rC.id), 'C 组图块集被误删')
  assertInvariants(mapStore.mapData, 'M')
})

test('N. 清空素材时，其它图层上的翻转图块也能被清掉（不因 GID 高位漏删）', () => {
  mapStore.newMap()
  mapStore.addLayer('图层A')
  const r = addTileResource('砖', 'assets/maps/地图1/images/n1.png')
  const flipped = withTileFlip(r.firstgid, true, false)
  mapStore.setTile(0, 0, flipped)
  mapStore.addLayer('图层B')
  mapStore.setTile(1, 1, flipped)
  mapStore.clearResources()
  const a: any = mapStore.mapData.layers.find(l => l.name === '图层A')
  assert(Object.keys(a.tiles).length === 0, '非当前图层的翻转图块没被清掉（高位导致漏删）')
  assertInvariants(mapStore.mapData, 'N')
})

test('O. 改格子尺寸后已画图块仍能正确解析（GID 不丢失）', () => {
  mapStore.newMap()
  mapStore.addLayer('图层')
  const r = addTileResource('砖', 'assets/maps/地图1/images/o1.png')
  mapStore.setTile(3, 3, r.firstgid)
  mapStore.updateTileSize(32)
  const layer: any = mapStore.mapData.layers[0]
  assert(Object.values(layer.tiles).some(v => tileBaseGid(v as number) === r.firstgid), '改尺寸后图块丢失')
  assert(resolveByGid(mapStore.mapData, r.firstgid)?.id === r.id, '改尺寸后 GID 解析错误')
  assertInvariants(mapStore.mapData, 'O')
})

test('P. 图块集分组的禁用 / 锁定不改动图块数据', () => {
  mapStore.newMap()
  mapStore.addLayer('图层')
  const g = mapStore.addTilesetGroupToActiveLayer()!
  const r = addTileResource('砖', 'assets/maps/地图1/images/p1.png')
  mapStore.setTile(0, 0, r.firstgid)
  mapStore.setTilesetGroupFlags(g, { disabled: true })
  mapStore.setTilesetGroupFlags(g, { locked: true })
  const group = (mapStore.mapData.tilesetGroups ?? []).find(x => x.id === g)!
  assert(group.disabled === true && group.locked === true, '分组状态未写入')
  const layer: any = mapStore.mapData.layers[0]
  assert(layer.tiles['0,0'] === r.firstgid, '改分组状态不应动图块')
  assert(resolveByGid(mapStore.mapData, r.firstgid)?.id === r.id, '改分组状态后解析错误')
  mapStore.setTilesetGroupFlags(g, { disabled: false, locked: false })
  assertInvariants(mapStore.mapData, 'P')
})

test('Q. 序列化往返后多分组 / 翻转图块 / 分组状态都保留', () => {
  mapStore.newMap()
  mapStore.addLayer('A')
  const gA = mapStore.addTilesetGroupToActiveLayer()!
  const rA = addTileResource('砖A', 'assets/maps/地图1/images/a.png')
  const flipped = withTileFlip(rA.firstgid, false, true)
  mapStore.setTile(0, 0, flipped)
  mapStore.setTilesetGroupFlags(gA, { disabled: true })
  mapStore.addLayer('B')
  const gB = mapStore.addTilesetGroupToActiveLayer()!
  const rB = addTileResource('砖B', 'assets/maps/地图1/images/b.png')
  mapStore.setTile(0, 1, rB.firstgid)

  const groupsBefore = mapStore.mapData.tilesetGroups?.length ?? 0
  roundTrip('Q')
  assert((mapStore.mapData.tilesetGroups ?? []).length === groupsBefore, '往返后分组数量变化')
  const a: any = mapStore.mapData.layers.find(l => l.name === 'A')
  assert(a.tiles['0,0'] === flipped, `往返后翻转标记丢失（${a.tiles['0,0']} ≠ ${flipped}）`)
  const gA2 = (mapStore.mapData.tilesetGroups ?? []).find(x => x.id === gA)!
  assert(gA2?.disabled === true, '往返后分组禁用状态丢失')
  assert(resolveByGid(mapStore.mapData, rB.firstgid)?.id === rB.id, '往返后 GID 解析错误')
})

test('R. 复制图块集后，原图块集的素材仍然完整可见', () => {
  mapStore.newMap()
  mapStore.addLayer('图层')
  const gA = mapStore.addTilesetGroupToActiveLayer()!
  const r1 = addTileResource('砖1', 'assets/maps/地图1/images/r1.png')
  const r2 = addTileResource('砖2', 'assets/maps/地图1/images/r2.png')
  mapStore.setTile(0, 0, r1.firstgid)
  mapStore.setTile(1, 1, r2.firstgid)

  const gCopy = mapStore.duplicateTilesetGroup(gA)!
  // 用户在列表里点回原来的图块集（左侧资源列表跟着切回该集合）
  mapStore.useTilesetGroupForActiveLayer(gA)

  const visible = mapStore.activeLayerResources
  assert(visible.length === 2, `原图块集应仍有 2 个素材，实际 ${visible.length} 个`)
  assert(
    visible.map(r => r.id).sort().join() === [r1.id, r2.id].sort().join(),
    `原图块集素材内容不对：${visible.map(r => r.name).join(',')}`,
  )
  // 界面上每一行的素材归属（PropertyPanel 的图块集列表用这个口径）
  const ownedA = mapStore.mapData.resources.filter(r => r.resourceType !== 'image' && r.groupId === gA)
  assert(ownedA.length === 2, `原图块集行内素材数不对（${ownedA.length}）`)

  const layer: any = mapStore.mapData.layers[0]
  assert(layer.tiles['0,0'] === r1.firstgid && layer.tiles['1,1'] === r2.firstgid, '复制后原图层图块被改动')
  assertInvariants(mapStore.mapData, 'R')
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

interface StressStats {
  seed: number
  paint: number
  flips: number
  roundTrips: number
  removedLayers: number
  cleared: number
  removedRes: number
  dupGroups: number
  delGroups: number
  tileSizes: number
  maxLayers: number
  maxGroups: number
}

/** 从当前状态里随机抽一个「绘制图层」下标；没有就新建一个 */
function ensureDrawingLayer() {
  const idx = mapStore.mapData.layers.findIndex(l => l.type === 'drawing')
  if (idx >= 0) {
    mapStore.setActiveLayer(idx)
    return idx
  }
  mapStore.addLayer('图块图层')
  return mapStore.mapData.layers.length - 1
}

function runStress(seed: number, steps: number): StressStats {
  const rand = mulberry32(seed)
  const pick = <T,>(arr: T[]): T => arr[Math.floor(rand() * arr.length)]
  const stats: StressStats = {
    seed, paint: 0, flips: 0, roundTrips: 0, removedLayers: 0, cleared: 0, removedRes: 0,
    dupGroups: 0, delGroups: 0, tileSizes: 0, maxLayers: 0, maxGroups: 0,
  }
  let seq = 0
  mapStore.newMap()
  const OPS = [
    'layer', 'layer',
    'image',
    'tile', 'tile',
    'paint', 'paint', 'paint', 'paint', 'paint',
    'flipPaint', 'flipPaint',
    'removeLayer',
    'clear', 'clear',
    'removeRes', 'removeRes',
    'move', 'rename',
    'roundtrip',
    'dupGroup',
    'delGroup',
    'newGroup',
    'groupFlags',
    'tileSize',
  ]

  for (let step = 0; step < steps; step++) {
    seq++
    const layers = mapStore.mapData.layers
    stats.maxLayers = Math.max(stats.maxLayers, layers.length)
    stats.maxGroups = Math.max(stats.maxGroups, (mapStore.mapData.tilesetGroups ?? []).length)
    const op = pick(OPS)

    if (op === 'layer') {
      if (layers.length < 8) mapStore.addLayer(rand() < 0.5 ? '图块图层' : `图层${seq}`)
    } else if (op === 'image') {
      addImageResource(`背景${seq}`, `assets/maps/地图1/images/img${seq}.png`)
    } else if (op === 'tile') {
      ensureDrawingLayer()
      // 每 3 次新素材换一个分组，制造「多分组 + 分组共用」的交叉场景
      if (seq % 3 === 0) mapStore.addTilesetGroupToActiveLayer()
      addTileResource(`砖${seq}`, `assets/maps/地图1/images/tile${seq}.png`)
    } else if (op === 'paint' || op === 'flipPaint') {
      const sets = mapStore.mapData.tileSets
      if (sets.length > 0) {
        const targets = mapStore.mapData.layers
          .map((l, i) => (l.type === 'drawing' ? i : -1))
          .filter(i => i >= 0)
        if (targets.length === 0) mapStore.addLayer('图块图层')
        const drawingIdx = targets.length > 0 ? pick(targets) : mapStore.mapData.layers.length - 1
        mapStore.setActiveLayer(drawingIdx)
        const ts = pick(sets)
        // 画的是该图块集的第一个图块；flipPaint 额外加上翻转高位
        const gid = op === 'flipPaint'
          ? withTileFlip(ts.firstgid, rand() < 0.5, rand() < 0.5)
          : ts.firstgid
        const x = Math.floor(rand() * Math.min(20, mapStore.mapData.width))
        const y = Math.floor(rand() * Math.min(20, mapStore.mapData.height))
        mapStore.setTile(x, y, gid)
        stats.paint++
        if (op === 'flipPaint') stats.flips++
      }
    } else if (op === 'removeLayer' && layers.length > 1) {
      mapStore.removeLayer(Math.floor(rand() * layers.length))
      stats.removedLayers++
    } else if (op === 'clear') {
      const d = mapStore.mapData.layers.findIndex(l => l.type === 'drawing')
      if (d >= 0) {
        mapStore.setActiveLayer(d)
        mapStore.clearResources()
        stats.cleared++
      }
    } else if (op === 'removeRes') {
      const d = mapStore.mapData.layers.findIndex(l => l.type === 'drawing')
      if (d >= 0) {
        mapStore.setActiveLayer(d)
        const visible = mapStore.activeLayerResources
        if (visible.length > 0) {
          mapStore.removeResource(Math.floor(rand() * visible.length))
          stats.removedRes++
        }
      }
    } else if (op === 'move' && layers.length > 1) {
      mapStore.moveLayerUp(Math.floor(rand() * layers.length))
      mapStore.moveLayerDown(Math.floor(rand() * layers.length))
    } else if (op === 'rename' && layers.length > 0) {
      mapStore.renameLayer(Math.floor(rand() * layers.length), `改名${seq}`)
    } else if (op === 'roundtrip') {
      roundTrip(`S${seed}-step${step}`)
      stats.roundTrips++
    } else if (op === 'dupGroup') {
      const groups = mapStore.mapData.tilesetGroups ?? []
      if (groups.length > 0 && groups.length < 6) {
        const id = pick(groups).id
        const created = mapStore.duplicateTilesetGroup(id)
        if (created) stats.dupGroups++
      }
    } else if (op === 'delGroup') {
      const groups = mapStore.mapData.tilesetGroups ?? []
      const removable = groups.filter(g => !g.locked)
      if (groups.length > 1 && removable.length > 0) {
        if (mapStore.deleteTilesetGroup(pick(removable).id)) stats.delGroups++
      }
    } else if (op === 'newGroup') {
      const groups = mapStore.mapData.tilesetGroups ?? []
      if (groups.length < 6) {
        ensureDrawingLayer()
        mapStore.addTilesetGroupToActiveLayer()
      }
    } else if (op === 'groupFlags') {
      const groups = mapStore.mapData.tilesetGroups ?? []
      if (groups.length > 0) {
        const target = pick(groups)
        mapStore.setTilesetGroupFlags(target.id, {
          disabled: rand() < 0.5,
          locked: rand() < 0.3,
        })
      }
    } else if (op === 'tileSize') {
      const current = mapStore.mapData.tileSize
      const next = pick([8, 16, 32].filter(s => s !== current))
      mapStore.updateTileSize(next)
      stats.tileSizes++
    }

    assertInvariants(mapStore.mapData, `seed${seed}-step${step}(${op})`)
  }
  // 收尾再读档一次，确保最终状态也能正常存取
  roundTrip(`S${seed}-final`)
  return stats
}

test('H. 随机操作压力测试（3 个种子 × 1500 步）', () => {
  const seeds = [20261106, 20261107, 20261108]
  const steps = 1500
  const all = seeds.map(s => runStress(s, steps))
  const sum = (k: keyof StressStats) => all.reduce((n, s) => n + (s[k] as number), 0)

  for (const s of all) {
    console.log(
      `   ↳ seed ${s.seed}：绘制 ${s.paint}（翻转 ${s.flips}）次，清空 ${s.cleared} 次，删素材 ${s.removedRes} 次，`
      + `删图层 ${s.removedLayers} 次，复制分组 ${s.dupGroups} 次，删分组 ${s.delGroups} 次，改尺寸 ${s.tileSizes} 次，`
      + `读档往返 ${s.roundTrips} 次，图层峰值 ${s.maxLayers}，分组峰值 ${s.maxGroups}`,
    )
  }

  // 覆盖率断言：避免随机序列“空跑通过”
  assert(sum('paint') >= 300, `绘制次数过少（${sum('paint')}），未覆盖绘制路径`)
  assert(sum('flips') >= 100, `翻转图块次数过少（${sum('flips')}）`)
  assert(sum('roundTrips') >= 60, `读档往返次数过少（${sum('roundTrips')}）`)
  assert(sum('cleared') >= 100, `清空素材次数过少（${sum('cleared')}）`)
  assert(sum('removedRes') >= 60, `删除单个素材次数过少（${sum('removedRes')}）`)
  assert(sum('dupGroups') >= 20, `复制分组次数过少（${sum('dupGroups')}）`)
  assert(sum('delGroups') >= 10, `删除分组次数过少（${sum('delGroups')}）`)
  assert(sum('tileSizes') >= 60, `改格子尺寸次数过少（${sum('tileSizes')}）`)
  assert(Math.max(...all.map(s => s.maxLayers)) >= 3, '图层数量过少，未覆盖多图层场景')
  assert(Math.max(...all.map(s => s.maxGroups)) >= 2, '分组数量过少，未覆盖多分组场景')
})

// ===================== 汇总 =====================
const failed = results.filter(r => !r.ok)
console.log('\n================ 测试结果 ================')
console.log(`用例：${results.length}，通过：${results.length - failed.length}，失败：${failed.length}`)
if (unhandled) console.log(`异步异常（不致命）：${unhandled} 条`)
if (failed.length) {
  for (const f of failed) console.log(`- ${f.name}: ${f.detail}`)
  process.exitCode = 1
} else {
  console.log('全部通过')
}
