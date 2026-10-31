import type { MapResource } from '../stores/map'
import { useMapStore } from '../stores/map'
import { useMapEditorStore } from '../stores/mapEditor'
import { createLayerTransform, tileSpriteTransform } from '../utils/tileLayerTransform'

interface TilePainterOptions {
  getApp: () => any
  getPIXI: () => any
  // 由画布渲染核心提供
  renderTile: (layerId: number, x: number, y: number, tileId: number) => Promise<void>
  getTileSprite: (key: string) => any
  getTileTexture: (resource: MapResource, tileIndex: number) => Promise<any>
  onTilePainted: (x: number, y: number, tileId: number) => void
  onTileErased: (x: number, y: number) => void
  onRenderRequest: () => void
}

/**
 * 绘制图层瓦片操作：画笔/直线/矩形/橡皮/油漆桶/移动工具与半透明幽灵预览。
 */
export function useTilePainter(options: TilePainterOptions) {
  const mapStore = useMapStore()
  const mapEditorStore = useMapEditorStore()
  const { getApp, getPIXI } = options

  let lastPaintedKey = ''

  // 幽灵预览：用真实图块纹理铺在格子上（半透明），代替原来的绿色边框
  const PREVIEW_ALPHA = 0.5
  let previewContainer: any = null
  const previewSprites = new Map<string, any>()
  /** 当前预览内容：格子 → 要显示的图块（多图块图章会包含多种图块） */
  let previewTargets = new Map<string, { x: number; y: number; resource: MapResource; tileIndex: number }>()
  /** 已加载的图块纹理（按 资源id:图块序号 缓存，多图块图章共用） */
  const previewTextures = new Map<string, any>()
  const previewLoading = new Set<string>()

  // Move tool state
  let moveStartPos: { x: number; y: number } | null = null
  let moveTileId = 0
  let moveStartSprite: any = null
  let moveDragSprite: any = null

  // 直线/矩形工具：按住拖动的起点与当前终点（抬起时一次性落笔）
  let shapeStart: { x: number; y: number } | null = null
  let shapeEnd: { x: number; y: number } | null = null
  // 本次直线/矩形是否用右键拖出（擦除）
  let shapeErase = false
  // 本次直线/矩形使用的画笔（固定一块，拖动过程中不随随机画笔变化）
  let shapeBrush: { resourceIndex: number; tileIndex: number } | null = null

  // 编码 tileId: 使用Tiled标准，GID = firstgid + tileIndex
  // firstgid 由 tileSets 数组中的瓦片集确定
  function encodeTileId(_layerId: number, localRIdx: number, tileIndex: number): number {
    // 直接用素材自己的 firstgid，不再依赖图层顺序偏移
    const resource = mapStore.activeLayerResources[localRIdx]
    if (resource) return resource.firstgid + tileIndex
    return tileIndex + 1
  }

  async function updateTileAt(layerIndex: number, x: number, y: number) {
    const layer = mapStore.mapData.layers[layerIndex]
    if (!layer || layer.type !== 'drawing') return
    const tileId = layer.tiles[`${x},${y}`] ?? 0
    await options.renderTile(layer.id, x, y, tileId)
  }

  function previewKey(resourceId: string, tileIndex: number) {
    return `${resourceId}:${tileIndex}`
  }

  /** 删除缓存里的幽灵图块 */
  function clearPreviewSprites() {
    for (const sprite of previewSprites.values()) {
      sprite.parent?.removeChild(sprite)
      sprite.destroy()
    }
    previewSprites.clear()
  }

  /** 隐藏并清空幽灵预览 */
  function hidePreview() {
    previewTargets = new Map()
    if (previewContainer) previewContainer.visible = false
    clearPreviewSprites()
  }

  /** 为当前预览里还没缓存的图块加载纹理 */
  function ensurePreviewTextures() {
    for (const target of previewTargets.values()) {
      const key = previewKey(target.resource.id, target.tileIndex)
      if (previewTextures.has(key) || previewLoading.has(key)) continue
      previewLoading.add(key)
      options.getTileTexture(target.resource, target.tileIndex).then(tex => {
        previewLoading.delete(key)
        if (tex) previewTextures.set(key, tex)
        layoutPreview()
      }).catch(() => {
        previewLoading.delete(key)
      })
    }
  }

  /** 按当前预览内容摆放幽灵图块；纹理还没加载好的格子先不显示 */
  function layoutPreview() {
    const app = getApp()
    const PIXI = getPIXI()
    if (!app || !PIXI) return

    if (!previewContainer) {
      previewContainer = new PIXI.Container()
      app.stage.addChild(previewContainer)
    }
    if (previewTargets.size === 0) {
      previewContainer.visible = false
      clearPreviewSprites()
      return
    }

    const tileSize = mapStore.mapData.tileSize
    // 图块层的整层变换：预览跟着同样的缩放/旋转/位移，才能和实际落笔位置对齐
    const layer = mapStore.activeLayer
    const transform = createLayerTransform(
      mapStore.mapData.width,
      mapStore.mapData.height,
      tileSize,
      layer?.type === 'drawing' ? layer : null,
    )
    const wanted = new Set<string>()

    for (const [cellKey, target] of previewTargets) {
      const tex = previewTextures.get(previewKey(target.resource.id, target.tileIndex))
      if (!tex) continue
      wanted.add(cellKey)
      let sprite = previewSprites.get(cellKey)
      if (!sprite) {
        sprite = new PIXI.Sprite(tex)
        sprite.anchor.set(0.5)
        previewContainer.addChild(sprite)
        previewSprites.set(cellKey, sprite)
      } else if (sprite.texture !== tex) {
        sprite.texture = tex
      }
      sprite.alpha = PREVIEW_ALPHA
      // 与真实图块完全相同的摆放方式（锚点居中 + 整层缩放/旋转/镜像）
      const st = tileSpriteTransform(transform, target.x, target.y, tileSize, target.resource.tileWidth, target.resource.tileHeight)
      sprite.x = st.x
      sprite.y = st.y
      sprite.rotation = st.rotation
      sprite.width = target.resource.tileWidth * Math.abs(st.scaleX)
      sprite.height = target.resource.tileHeight * Math.abs(st.scaleY)
      if (st.scaleX < 0) sprite.scale.x = -Math.abs(sprite.scale.x)
      if (st.scaleY < 0) sprite.scale.y = -Math.abs(sprite.scale.y)
    }

    for (const [cellKey, sprite] of previewSprites) {
      if (wanted.has(cellKey)) continue
      sprite.parent?.removeChild(sprite)
      sprite.destroy()
      previewSprites.delete(cellKey)
    }
    previewContainer.visible = previewSprites.size > 0
  }

  /** 随机画笔是否真正生效（开关打开且池子里有图块；池子为空时回退到当前画笔） */
  function isRandomActive() {
    return mapStore.randomBrushEnabled && mapStore.randomBrushPool.length > 0
  }

  /** 多图块图章是否生效（随机画笔优先走随机逻辑） */
  function isStampActive() {
    return mapStore.tileBrushStamp.length > 1 && !isRandomActive()
  }

  /** 悬停预览用的画笔：随机画笔固定取池子第一块，避免鼠标移动时预览图块乱跳 */
  function previewBrush() {
    if (isRandomActive()) {
      const first = mapStore.randomBrushPool[0]
      const index = mapStore.activeLayerResources.findIndex(r => r.id === first.resourceId)
      if (index >= 0) return { resourceIndex: index, tileIndex: first.tileIndex }
    }
    const brush = mapStore.pickBrush()
    return brush.tileIndex >= 0 ? brush : null
  }

  /**
   * 把锚点格子展开成预览内容。
   * 多图块图章：按调色板里的相对位置整组显示；普通画笔：每个锚点都显示同一块。
   */
  function buildPreviewTargets(
    baseCells: { x: number; y: number }[],
    brush: { resourceIndex: number; tileIndex: number } | null,
    useStamp = true,
  ) {
    const targets = new Map<string, { x: number; y: number; resource: MapResource; tileIndex: number }>()

    if (useStamp && isStampActive()) {
      const resources = mapStore.activeLayerResources
      for (const cell of expandStamp(baseCells)) {
        const resource = resources[cell.resourceIndex]
        if (!resource) continue
        targets.set(`${cell.x},${cell.y}`, {
          x: cell.x,
          y: cell.y,
          resource,
          tileIndex: cell.tileIndex,
        })
      }
      return targets
    }

    if (!brush) return targets
    const resource = mapStore.activeLayerResources[brush.resourceIndex]
    if (!resource) return targets
    for (const base of baseCells) {
      targets.set(`${base.x},${base.y}`, { x: base.x, y: base.y, resource, tileIndex: brush.tileIndex })
    }
    return targets
  }

  function showPreview(targets: Map<string, { x: number; y: number; resource: MapResource; tileIndex: number }>) {
    previewTargets = targets
    ensurePreviewTextures()
    layoutPreview()
  }

  function updatePreview(pos: { x: number; y: number } | null) {
    // 橡皮不画幽灵预览
    if (!pos || mapEditorStore.currentTool === 'erase') {
      hidePreview()
      return
    }
    // 多图块图章：悬停就显示整组（油漆桶仍是单块填充，预览也用单块）
    if (isStampActive() && mapEditorStore.currentTool !== 'fill') {
      showPreview(buildPreviewTargets([pos], null))
      return
    }
    const brush = previewBrush()
    if (!brush) {
      hidePreview()
      return
    }
    showPreview(buildPreviewTargets([pos], brush, mapEditorStore.currentTool !== 'fill'))
  }

  /** 直线（Bresenham）：起点到终点的所有格子，含两端 */
  function lineCells(start: { x: number; y: number }, end: { x: number; y: number }) {
    const cells: { x: number; y: number }[] = []
    let x = start.x
    let y = start.y
    const dx = Math.abs(end.x - x)
    const dy = -Math.abs(end.y - y)
    const sx = x < end.x ? 1 : -1
    const sy = y < end.y ? 1 : -1
    let err = dx + dy
    while (true) {
      cells.push({ x, y })
      if (x === end.x && y === end.y) break
      const e2 = 2 * err
      if (e2 >= dy) { err += dy; x += sx }
      if (e2 <= dx) { err += dx; y += sy }
    }
    return cells
  }

  /** 矩形：起点与终点围出的整个矩形区域，含行列边界 */
  function rectCells(start: { x: number; y: number }, end: { x: number; y: number }) {
    const cells: { x: number; y: number }[] = []
    const x0 = Math.min(start.x, end.x)
    const x1 = Math.max(start.x, end.x)
    const y0 = Math.min(start.y, end.y)
    const y1 = Math.max(start.y, end.y)
    for (let y = y0; y <= y1; y++) {
      for (let x = x0; x <= x1; x++) cells.push({ x, y })
    }
    return cells
  }

  /** 当前直线/矩形工具对应的格子集合 */
  function shapeCells(start: { x: number; y: number }, end: { x: number; y: number }) {
    return mapEditorStore.currentTool === 'line' ? lineCells(start, end) : rectCells(start, end)
  }

  /** 多图块图章的图块（相对偏移 + 当前图层的资源下标）；不生效时返回 null */
  function stampEntries() {
    if (!isStampActive()) return null
    const result: { dx: number; dy: number; resourceIndex: number; tileIndex: number }[] = []
    for (const entry of mapStore.tileBrushStamp) {
      const resourceIndex = mapStore.activeLayerResources.findIndex(r => r.id === entry.resourceId)
      if (resourceIndex < 0) continue
      result.push({ dx: entry.dx, dy: entry.dy, resourceIndex, tileIndex: entry.tileIndex })
    }
    return result.length ? result : null
  }

  /**
   * 把锚点格子展开成图章落笔的格子：
   * - 单格（画笔/点击）：整组盖章，锚点格对选区左上角；
   * - 直线/矩形多格：按图案网格平铺（对齐起点格），避免整组在每一格叠加互相覆盖。
   */
  function expandStamp(baseCells: { x: number; y: number }[]) {
    const entries = stampEntries()
    if (!entries || baseCells.length === 0) return []

    if (baseCells.length <= 1) {
      const base = baseCells[0]
      return entries.map(e => ({
        x: base.x + e.dx,
        y: base.y + e.dy,
        resourceIndex: e.resourceIndex,
        tileIndex: e.tileIndex,
      }))
    }

    const width = Math.max(...entries.map(e => e.dx)) + 1
    const height = Math.max(...entries.map(e => e.dy)) + 1
    const lookup = new Map<string, { resourceIndex: number; tileIndex: number }>()
    for (const entry of entries) {
      lookup.set(`${entry.dx},${entry.dy}`, { resourceIndex: entry.resourceIndex, tileIndex: entry.tileIndex })
    }
    // 用形状左上角做图案锚点：反向拖拽也不会把图案镜像过来
    let minX = Infinity
    let minY = Infinity
    for (const base of baseCells) {
      if (base.x < minX) minX = base.x
      if (base.y < minY) minY = base.y
    }
    const anchor = { x: minX, y: minY }
    const cells: { x: number; y: number; resourceIndex: number; tileIndex: number }[] = []
    for (const base of baseCells) {
      const px = (((base.x - anchor.x) % width) + width) % width
      const py = (((base.y - anchor.y) % height) + height) % height
      const hit = lookup.get(`${px},${py}`)
      if (!hit) continue
      cells.push({ x: base.x, y: base.y, resourceIndex: hit.resourceIndex, tileIndex: hit.tileIndex })
    }
    return cells
  }

  /** 把展开后的图章格子写入图层 */
  function paintStampCells(layerId: number, cells: { x: number; y: number; resourceIndex: number; tileIndex: number }[]) {
    for (const cell of cells) {
      mapStore.setTile(cell.x, cell.y, encodeTileId(layerId, cell.resourceIndex, cell.tileIndex))
      updateTileAt(mapStore.activeLayerIndex, cell.x, cell.y)
    }
  }

  /** 在锚点格擦除整组图章的覆盖范围（图章不生效时只擦一格） */
  function eraseStampAt(base: { x: number; y: number }) {
    const stamp = mapStore.tileBrushStamp
    if (stamp.length > 1) {
      for (const entry of stamp) {
        const x = base.x + entry.dx
        const y = base.y + entry.dy
        mapStore.setTile(x, y, 0)
        updateTileAt(mapStore.activeLayerIndex, x, y)
      }
      return
    }
    mapStore.setTile(base.x, base.y, 0)
    updateTileAt(mapStore.activeLayerIndex, base.x, base.y)
  }

  /** 抬起时把整条直线 / 整个矩形一次性写进图层（同一次按压合并为一步历史） */
  function commitShapeStroke() {
    const start = shapeStart
    const end = shapeEnd
    const erase = shapeErase
    const brush = shapeBrush
    shapeStart = null
    shapeEnd = null
    shapeErase = false
    shapeBrush = null
    // 落笔后真实图块已经以正常不透明度出现，幽灵预览要收掉
    hidePreview()
    if (!start || !end) return
    const layer = mapStore.activeLayer
    if (!layer || layer.type !== 'drawing') return
    const cells = shapeCells(start, end)
    // 随机画笔：每一格各自随机（散布命中的格子跳过），而不是整条/整片都用同一块
    const random = !erase && isRandomActive()
    // 多图块图章：单格落笔整组盖章；直线/矩形按图案网格平铺，避免整组逐格叠加互相覆盖
    const stampCells = !erase && !random ? expandStamp(cells) : []
    if (!erase && !random && stampCells.length === 0 && (!brush || brush.tileIndex < 0)) return

    // 先按格子汇总（后写覆盖先写），避免重复渲染同一格
    const planned = new Map<string, { x: number; y: number; tileId: number }>()
    const plan = (x: number, y: number, tileId: number) => {
      planned.set(`${x},${y}`, { x, y, tileId })
    }
    if (erase) {
      // 擦除时按整组图章的覆盖范围清空（与当前是否随机无关）
      const stamp = mapStore.tileBrushStamp.length > 1 ? mapStore.tileBrushStamp : null
      for (const base of cells) {
        if (stamp) {
          for (const entry of stamp) plan(base.x + entry.dx, base.y + entry.dy, 0)
        } else {
          plan(base.x, base.y, 0)
        }
      }
    } else if (random) {
      for (const base of cells) {
        const picked = mapStore.pickBrush()
        // 散布把这一格留空：保持原样，不擦除
        if (picked.tileIndex < 0) continue
        plan(base.x, base.y, encodeTileId(layer.id, picked.resourceIndex, picked.tileIndex))
      }
    } else if (stampCells.length) {
      for (const cell of stampCells) {
        plan(cell.x, cell.y, encodeTileId(layer.id, cell.resourceIndex, cell.tileIndex))
      }
    } else {
      for (const base of cells) {
        plan(base.x, base.y, encodeTileId(layer.id, brush!.resourceIndex, brush!.tileIndex))
      }
    }
    for (const cell of planned.values()) {
      mapStore.setTile(cell.x, cell.y, cell.tileId)
      updateTileAt(mapStore.activeLayerIndex, cell.x, cell.y)
    }
  }

  // 移动工具的拖拽预览：与真实图块共用整层变换
  function placeDragSprite(pos: { x: number; y: number }) {
    if (!moveDragSprite) return
    const tileSize = mapStore.mapData.tileSize
    const layer = mapStore.activeLayer
    const transform = createLayerTransform(
      mapStore.mapData.width,
      mapStore.mapData.height,
      tileSize,
      layer?.type === 'drawing' ? layer : null,
    )
    const tex = moveDragSprite.texture
    const st = tileSpriteTransform(transform, pos.x, pos.y, tileSize, tex.width, tex.height)
    moveDragSprite.x = st.x
    moveDragSprite.y = st.y
    moveDragSprite.rotation = st.rotation
    moveDragSprite.width = tex.width * Math.abs(st.scaleX)
    moveDragSprite.height = tex.height * Math.abs(st.scaleY)
    if (st.scaleX < 0) moveDragSprite.scale.x = -Math.abs(moveDragSprite.scale.x)
    if (st.scaleY < 0) moveDragSprite.scale.y = -Math.abs(moveDragSprite.scale.y)
  }

  function resetPaintKey() {
    lastPaintedKey = ''
  }

  // 绘制工具按下：左键绘制，右键擦除；橡皮、油漆桶、移动工具同理
  function handlePaintPointerDown(e: PointerEvent, pos: { x: number; y: number }) {
    // 一次按下开始的改动全部合并成一步历史，抬起时统一收尾
    mapStore.beginTileStroke()
    // 绘制工具：左键绘制，右键擦除
    if (mapEditorStore.currentTool === 'draw' && mapStore.activeLayer && mapStore.activeLayer.type === 'drawing') {
      const layer = mapStore.activeLayer
      if (e.button === 0) {
        // 多图块图章：一次贴出整组；普通画笔：只贴当前一块
        const stampCells = expandStamp([pos])
        let tileId = 0
        if (stampCells.length) {
          paintStampCells(layer.id, stampCells)
          tileId = encodeTileId(layer.id, stampCells[0].resourceIndex, stampCells[0].tileIndex)
        } else {
          const brush = mapStore.pickBrush()
          if (brush.tileIndex < 0) return
          tileId = encodeTileId(layer.id, brush.resourceIndex, brush.tileIndex)
          mapStore.setTile(pos.x, pos.y, tileId)
          updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
        }
        lastPaintedKey = `${pos.x},${pos.y}`
        options.onTilePainted(pos.x, pos.y, tileId)
      } else if ((e.button as number) === 2) {
        eraseStampAt(pos)
        lastPaintedKey = `${pos.x},${pos.y}`
        options.onTileErased(pos.x, pos.y)
      }
    } else if (
      (mapEditorStore.currentTool === 'line' || mapEditorStore.currentTool === 'rect')
      && (e.button === 0 || (e.button as number) === 2)
      && mapStore.activeLayer && mapStore.activeLayer.type === 'drawing'
    ) {
      // 直线/矩形：先记起点，拖动时只做预览，抬起时才真正落笔（右键拖出 = 擦除）
      shapeErase = (e.button as number) === 2
      if (shapeErase) {
        shapeBrush = null
        hidePreview()
      } else if (isStampActive()) {
        // 多图块图章：不需要单块画笔，直接用整组预览
        shapeBrush = null
        showPreview(buildPreviewTargets([pos], null))
      } else {
        // 随机画笔按格子随机，这里只取一块用作拖动时的预览；不能因为散布随机到空白就整笔放弃
        const brush = previewBrush()
        if (!brush) return
        shapeBrush = brush
        showPreview(buildPreviewTargets([pos], brush))
      }
      shapeStart = pos
      shapeEnd = pos
    } else if (mapEditorStore.currentTool === 'erase') {
      eraseStampAt(pos)
      lastPaintedKey = `${pos.x},${pos.y}`
      options.onTileErased(pos.x, pos.y)
    } else if (mapEditorStore.currentTool === 'fill' && mapStore.activeLayer) {
      const brush = mapStore.pickBrush()
      if (brush.tileIndex < 0) return
      const tileId = encodeTileId(mapStore.activeLayer.id, brush.resourceIndex, brush.tileIndex)
      floodFill(pos.x, pos.y, tileId)
    } else if (mapEditorStore.currentTool === 'move') {
      const layer = mapStore.activeLayer
      if (layer && layer.type === 'drawing') {
        const tileId = layer.tiles[`${pos.x},${pos.y}`] ?? 0
        if (tileId !== 0) {
          moveStartPos = pos
          moveTileId = tileId
          const spriteKey = `${layer.id}:${pos.x},${pos.y}`
          moveStartSprite = options.getTileSprite(spriteKey) ?? null
          if (moveStartSprite) moveStartSprite.visible = false
          // 异步加载纹理创建拖拽 sprite
          const PIXI = getPIXI()
          const app = getApp()
          const tileSets = mapStore.mapData.tileSets
          let matchedTs: any = null
          for (let i = tileSets.length - 1; i >= 0; i--) {
            if (tileId >= tileSets[i].firstgid) { matchedTs = tileSets[i]; break }
          }
          const tIdx = matchedTs ? tileId - matchedTs.firstgid : 0
          const texRes = matchedTs
            ? mapStore.mapData.resources.find((r: MapResource) => r.firstgid === matchedTs.firstgid)
              ?? mapStore.mapData.resources.find((r: MapResource) => r.path === matchedTs.imagePath)
            : null
          if (texRes && PIXI && app) {
            options.getTileTexture(texRes, tIdx).then(texture => {
              if (!texture || !moveTileId) return
              moveDragSprite = new PIXI.Sprite(texture)
              moveDragSprite.anchor.set(0.5)
              placeDragSprite(pos)
              app.stage.addChild(moveDragSprite)
            }).catch(() => {})
          }
        }
      }
    }
  }

  // 绘制工具拖动：连续绘制 + 移动工具预览
  function handlePaintPointerMove(e: PointerEvent, pos: { x: number; y: number } | null) {
    // Move tool preview
    if (moveStartPos && moveTileId && moveDragSprite && pos) {
      placeDragSprite(pos)
    }

    // 直线/矩形：按住拖动时实时显示将要填充的格子
    if (mapEditorStore.currentTool === 'line' || mapEditorStore.currentTool === 'rect') {
      if (!shapeStart) {
        updatePreview(pos)
        return
      }
      if (e.buttons === 0) {
        // 某些输入设备/时序下 pointerup 会丢失，先出现 buttons=0 的移动事件：
        // 这里用最后有效位置直接提交，宁可提前收笔也不能让整条直线/矩形丢掉
        commitShapeStroke()
        updatePreview(pos)
        return
      }
      if (pos) {
        shapeEnd = pos
        if (shapeErase) {
          hidePreview()
        } else {
          showPreview(buildPreviewTargets(shapeCells(shapeStart, shapeEnd), shapeBrush))
        }
      }
      return
    }

    if (mapEditorStore.currentTool === 'draw' || mapEditorStore.currentTool === 'erase' || mapEditorStore.currentTool === 'fill') {
      updatePreview(pos)

      if (pos && (e.buttons === 1 || e.buttons === 2)) {
        const key = `${pos.x},${pos.y}`
        if (key !== lastPaintedKey) {
          // 绘制工具：左键绘制，右键擦除
          if (mapEditorStore.currentTool === 'draw' && mapStore.activeLayer && mapStore.activeLayer.type === 'drawing') {
            const layer = mapStore.activeLayer
            if (e.buttons === 2) {
              eraseStampAt(pos)
            } else {
              const stampCells = expandStamp([pos])
              if (stampCells.length) {
                paintStampCells(layer.id, stampCells)
                options.onTilePainted(
                  pos.x,
                  pos.y,
                  encodeTileId(layer.id, stampCells[0].resourceIndex, stampCells[0].tileIndex),
                )
              } else {
                const brush = mapStore.pickBrush()
                if (brush.tileIndex >= 0) {
                  const tileId = encodeTileId(layer.id, brush.resourceIndex, brush.tileIndex)
                  mapStore.setTile(pos.x, pos.y, tileId)
                  updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
                  options.onTilePainted(pos.x, pos.y, tileId)
                }
              }
            }
          } else if (mapEditorStore.currentTool === 'erase') {
            eraseStampAt(pos)
            options.onTileErased(pos.x, pos.y)
          }
          lastPaintedKey = key
        }
      }
    }
  }

  // 移动工具落子：把瓦片放到新位置
  function handlePointerUp(pos: { x: number; y: number } | null) {
    // 直线/矩形：抬起时一次性落笔（终点以抬起位置为准）
    if (shapeStart) {
      if (pos) shapeEnd = pos
      commitShapeStroke()
    }
    if (moveStartPos && moveTileId) {
      if (pos && (pos.x !== moveStartPos.x || pos.y !== moveStartPos.y)) {
        const layer = mapStore.activeLayer
        if (layer && layer.type === 'drawing') {
          mapStore.setTile(moveStartPos.x, moveStartPos.y, 0)
          mapStore.setTile(pos.x, pos.y, moveTileId)
          updateTileAt(mapStore.activeLayerIndex, moveStartPos.x, moveStartPos.y)
          updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
        }
      } else if (moveStartSprite) {
        // 未移动，恢复原始 sprite 可见
        moveStartSprite.visible = true
      }
      moveStartPos = null
      moveTileId = 0
      moveStartSprite = null
      if (moveDragSprite) {
        const app = getApp()
        app?.stage.removeChild(moveDragSprite)
        moveDragSprite.destroy()
        moveDragSprite = null
      }
    }
    // 抬起：把本次笔画里的所有格子改动合并成一步历史
    mapStore.endTileStroke()
  }

  function floodFill(startX: number, startY: number, fillTileId: number) {
    const layer = mapStore.activeLayer
    if (!layer || layer.type !== 'drawing') return

    const targetTileId = layer.tiles[`${startX},${startY}`] ?? 0
    if (targetTileId === fillTileId) return

    const { width, height } = mapStore.mapData
    const stack: [number, number][] = [[startX, startY]]
    const visited = new Set<string>()

    while (stack.length > 0) {
      const [x, y] = stack.pop()!
      const key = `${x},${y}`
      if (visited.has(key)) continue
      visited.add(key)

      if (x < 0 || x >= width || y < 0 || y >= height) continue

      const currentId = layer.tiles[key] ?? 0
      if (currentId !== targetTileId) continue

      mapStore.setTile(x, y, fillTileId)

      stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1])
    }

    options.onRenderRequest()
  }

  /** 是否还有未提交的直线/矩形笔划（全局 pointerup 兜底时判断用） */
  function hasActiveShapeStroke() {
    return shapeStart !== null
  }

  /** 取消未完成的直线/矩形笔划（切换工具、离开画布、切地图时调用） */
  function resetShapeStroke() {
    shapeStart = null
    shapeEnd = null
    shapeErase = false
    shapeBrush = null
  }

  // 切换地图时清理移动工具状态
  function resetMoveState() {
    moveStartPos = null
    moveTileId = 0
    resetShapeStroke()
    hidePreview()
    if (moveDragSprite) {
      const app = getApp()
      app?.stage.removeChild(moveDragSprite)
      moveDragSprite.destroy()
      moveDragSprite = null
    }
  }

  return {
    encodeTileId,
    updateTileAt,
    updatePreview,
    hidePreview,
    resetPaintKey,
    handlePaintPointerDown,
    handlePaintPointerMove,
    handlePointerUp,
    floodFill,
    resetMoveState,
    resetShapeStroke,
    hasActiveShapeStroke,
  }
}
