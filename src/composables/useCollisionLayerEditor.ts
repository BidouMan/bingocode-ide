import { watch } from 'vue'
import { useMapStore, type CollisionLayer, type CollisionPolygon } from '../stores/map'
import { useMapEditorStore } from '../stores/mapEditor'
import { pointInPolygon } from '../utils/mapImageGeometry'

interface CollisionLayerEditorOptions {
  getApp: () => any
  getScale: () => number
  /** 屏幕坐标叠加层 canvas：位于矢量画布之上，避免碰撞线被图像/矢量内容遮住 */
  getOverlayCanvas: () => HTMLCanvasElement | null
}

interface Point { x: number; y: number }

/**
 * 碰撞层编辑：世界坐标多碰撞体，选择/整框拖动/顶点编辑/矩形/自定义钢笔。
 */
export function useCollisionLayerEditor(options: CollisionLayerEditorOptions) {
  const mapStore = useMapStore()
  const mapEditorStore = useMapEditorStore()
  const { getApp, getScale, getOverlayCanvas } = options

  // 锚点抓取 / 边插点的屏幕像素容差
  const VERTEX_HIT_PX = 12
  const EDGE_HIT_PX = 5

  let rectStart: Point | null = null
  let rectCurrent: Point | null = null
  // 拖拽创建形状：矩形 / 圆形 / 胶囊
  let draftShape: 'rect' | 'circle' | 'capsule' | null = null
  let draftPolygon: Point[] = []
  let draftActive = false
  let draftPreview: Point | null = null
  let draggingVertexIndex = -1
  let selectedVertexIndex = -1
  // 整框拖动
  let draggingPolygon = false
  let dragStartPoints: number[][] = []
  let dragStartWorld: Point | null = null
  let lastPolygonClickAt = 0

  function activeLayer(): CollisionLayer | null {
    return mapStore.activeCollisionLayer
  }

  function activePolygon(): CollisionPolygon | null {
    return mapStore.activeCollisionPolygon
  }

  function pointsOf(polygon: CollisionPolygon): Point[] {
    return polygon.points.map(p => ({ x: p[0], y: p[1] }))
  }

  function snapPoint(world: Point): Point {
    if (mapEditorStore.snapToGrid) {
      const ts = Math.max(1, mapStore.mapData.tileSize)
      return { x: Math.round(world.x / ts) * ts, y: Math.round(world.y / ts) * ts }
    }
    // 默认像素吸附：对齐到整数地图像素
    return { x: Math.round(world.x), y: Math.round(world.y) }
  }

  function pointToSegmentDistance(p: Point, a: Point, b: Point): number {
    const dx = b.x - a.x
    const dy = b.y - a.y
    const lenSq = dx * dx + dy * dy
    if (lenSq === 0) return Math.hypot(p.x - a.x, p.y - a.y)
    const t = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / lenSq))
    return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy))
  }

  /** 点到线段最近点（用于"添加点"工具把新锚点落在边上） */
  function projectOnSegment(p: Point, a: Point, b: Point): Point {
    const dx = b.x - a.x
    const dy = b.y - a.y
    const lenSq = dx * dx + dy * dy
    if (lenSq === 0) return { x: a.x, y: a.y }
    const t = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / lenSq))
    return { x: a.x + t * dx, y: a.y + t * dy }
  }

  function rectPoints(x0: number, y0: number, x1: number, y1: number): number[][] {
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
  }

  /** 圆/椭圆：16 段近似，避免锚点过多 */
  function circlePoints(x0: number, y0: number, x1: number, y1: number): number[][] {
    const cx = (x0 + x1) / 2
    const cy = (y0 + y1) / 2
    const rx = (x1 - x0) / 2
    const ry = (y1 - y0) / 2
    const segments = 16
    const pts: number[][] = []
    for (let i = 0; i < segments; i++) {
      const a = (i / segments) * Math.PI * 2
      pts.push([cx + Math.cos(a) * rx, cy + Math.sin(a) * ry])
    }
    return pts
  }

  /** 胶囊：两端半圆 + 直边，按拖拽框自动判断横/竖 */
  function capsulePoints(x0: number, y0: number, x1: number, y1: number): number[][] {
    const w = x1 - x0
    const h = y1 - y0
    const seg = 8
    const pts: number[][] = []
    if (w >= h) {
      const r = h / 2
      const cy = (y0 + y1) / 2
      const left = x0 + r
      const right = x1 - r
      for (let i = 0; i <= seg; i++) {
        const a = -Math.PI / 2 + (i / seg) * Math.PI
        pts.push([right + Math.cos(a) * r, cy + Math.sin(a) * r])
      }
      for (let i = 0; i <= seg; i++) {
        const a = Math.PI / 2 + (i / seg) * Math.PI
        pts.push([left + Math.cos(a) * r, cy + Math.sin(a) * r])
      }
    } else {
      const r = w / 2
      const cx = (x0 + x1) / 2
      const top = y0 + r
      const bottom = y1 - r
      for (let i = 0; i <= seg; i++) {
        const a = (i / seg) * Math.PI
        pts.push([cx + Math.cos(a) * r, bottom + Math.sin(a) * r])
      }
      for (let i = 0; i <= seg; i++) {
        const a = Math.PI + (i / seg) * Math.PI
        pts.push([cx + Math.cos(a) * r, top + Math.sin(a) * r])
      }
    }
    return pts
  }

  function buildShapePoints(shape: 'rect' | 'circle' | 'capsule', x0: number, y0: number, x1: number, y1: number): number[][] {
    let points: number[][]
    if (shape === 'circle') points = circlePoints(x0, y0, x1, y1)
    else if (shape === 'capsule') points = capsulePoints(x0, y0, x1, y1)
    else points = rectPoints(x0, y0, x1, y1)
    // 像素吸附模式：生成点也取整，避免出现小数锚点
    if (!mapEditorStore.snapToGrid) {
      return points.map(p => [Math.round(p[0]), Math.round(p[1])])
    }
    return points
  }

  function findNearestVertex(polygon: CollisionPolygon | null, world: Point, threshold: number): number {
    if (!polygon) return -1
    const pts = pointsOf(polygon)
    let best = -1
    let bestDist = threshold
    pts.forEach((p, i) => {
      const d = Math.hypot(p.x - world.x, p.y - world.y)
      if (d < bestDist) {
        bestDist = d
        best = i
      }
    })
    return best
  }

  function findNearestEdge(polygon: CollisionPolygon | null, world: Point, threshold: number): number {
    if (!polygon) return -1
    const pts = pointsOf(polygon)
    if (pts.length < 2) return -1
    let best = -1
    let bestDist = threshold
    for (let i = 0; i < pts.length; i++) {
      const d = pointToSegmentDistance(world, pts[i], pts[(i + 1) % pts.length])
      if (d < bestDist) {
        bestDist = d
        best = i
      }
    }
    return best
  }

  /** 当前碰撞层中命中最上层碰撞体 */
  function findPolygonAt(world: Point): CollisionPolygon | null {
    const layer = activeLayer()
    if (!layer || layer.locked) return null
    for (let i = layer.polygons.length - 1; i >= 0; i--) {
      const poly = layer.polygons[i]
      if (poly.points.length < 3) continue
      if (pointInPolygon(world, pointsOf(poly))) return poly
    }
    return null
  }

  // ====== 绘制 ======

  function colorCss(color: number, alpha: number): string {
    return `rgba(${(color >> 16) & 0xff}, ${(color >> 8) & 0xff}, ${color & 0xff}, ${alpha})`
  }

  function drawPolygon(
    ctx: CanvasRenderingContext2D,
    points: Point[],
    color: number,
    fillAlpha: number,
    lineWidth: number,
    withHandles: boolean,
  ) {
    if (points.length < 2) return
    const scale = getScale()
    ctx.beginPath()
    ctx.moveTo(points[0].x, points[0].y)
    for (let i = 1; i < points.length; i++) ctx.lineTo(points[i].x, points[i].y)
    ctx.closePath()
    ctx.fillStyle = colorCss(color, fillAlpha)
    ctx.fill()
    ctx.strokeStyle = colorCss(color, 0.9)
    ctx.lineWidth = lineWidth
    ctx.stroke()

    if (!withHandles) return
    const radius = 4 / scale
    points.forEach((p, i) => {
      if (i === selectedVertexIndex) {
        ctx.beginPath()
        ctx.arc(p.x, p.y, radius * 1.6, 0, Math.PI * 2)
        ctx.fillStyle = colorCss(0x528bff, 0.9)
        ctx.fill()
      }
      ctx.beginPath()
      ctx.arc(p.x, p.y, radius, 0, Math.PI * 2)
      ctx.fillStyle = i === 0 ? colorCss(0x5BFB84, 1) : '#ffffff'
      ctx.fill()
      ctx.strokeStyle = colorCss(0xff5050, 1)
      ctx.lineWidth = 1 / scale
      ctx.stroke()
    })
  }

  function drawOverlay() {
    const app = getApp()
    const canvas = getOverlayCanvas()
    if (!app || !canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const scale = getScale()
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.setTransform(dpr * scale, 0, 0, dpr * scale, dpr * (app.stage.x || 0), dpr * (app.stage.y || 0))

    const lineWidth = 1.5 / scale
    const editingLayer = activeLayer()
    const activeId = mapEditorStore.activeCollisionPolygonId
    const editing = editingLayer != null

    for (const layer of mapStore.mapData.layers) {
      if (layer.type !== 'collision' || !layer.visible) continue
      const isActiveLayer = layer === editingLayer
      for (const poly of layer.polygons) {
        if (poly.points.length < 3) continue
        const isActive = isActiveLayer && poly.id === activeId
        drawPolygon(
          ctx,
          pointsOf(poly),
          poly.disabled ? 0x888888 : 0xff5050,
          isActive ? (poly.disabled ? 0.16 : 0.26) : isActiveLayer ? 0.16 : 0.1,
          lineWidth,
          // 选择/加锚点/删锚点都需要看到锚点，保证增删即时可见
          isActive && editing && ['select', 'addPoint', 'deletePoint'].includes(mapEditorStore.collisionLayerTool),
        )
      }
    }

    const current = activeLayer()
    if (!current) return

    // 矩形/圆形/胶囊拖拽预览
    if (rectStart && rectCurrent) {
      const x0 = Math.min(rectStart.x, rectCurrent.x)
      const x1 = Math.max(rectStart.x, rectCurrent.x)
      const y0 = Math.min(rectStart.y, rectCurrent.y)
      const y1 = Math.max(rectStart.y, rectCurrent.y)
      const preview = (draftShape ?? 'rect') === 'rect'
        ? [{ x: x0, y: y0 }, { x: x1, y: y0 }, { x: x1, y: y1 }, { x: x0, y: y1 }]
        : buildShapePoints(draftShape ?? 'rect', x0, y0, x1, y1).map(p => ({ x: p[0], y: p[1] }))
      drawPolygon(ctx, preview, 0x5BFB84, 0.15, lineWidth, false)
    }

    // 钢笔草稿
    if (draftActive && draftPolygon.length > 0) {
      ctx.beginPath()
      ctx.moveTo(draftPolygon[0].x, draftPolygon[0].y)
      for (let i = 1; i < draftPolygon.length; i++) ctx.lineTo(draftPolygon[i].x, draftPolygon[i].y)
      if (draftPreview) ctx.lineTo(draftPreview.x, draftPreview.y)
      ctx.strokeStyle = colorCss(0x5BFB84, 0.9)
      ctx.lineWidth = lineWidth
      ctx.stroke()

      const radius = 4 / scale
      for (const p of draftPolygon) {
        ctx.beginPath()
        ctx.arc(p.x, p.y, radius, 0, Math.PI * 2)
        ctx.fillStyle = '#ffffff'
        ctx.fill()
        ctx.strokeStyle = colorCss(0xff5050, 1)
        ctx.lineWidth = 1 / scale
        ctx.stroke()
      }
    }
  }

  // ====== 交互 ======

  function cancelDraft() {
    rectStart = null
    rectCurrent = null
    draftShape = null
    draftActive = false
    draftPolygon = []
    draftPreview = null
    draggingVertexIndex = -1
    resetPolygonDrag()
    drawOverlay()
  }

  function resetPolygonDrag() {
    draggingPolygon = false
    dragStartPoints = []
    dragStartWorld = null
  }

  function closeDraftPolygon() {
    if (draftPolygon.length >= 3) {
      mapStore.addCollisionPolygon('polygon', draftPolygon.map(p => [p.x, p.y]))
      // 创建完成切回选择移动（形状按钮仍常亮，创建后可立即选中/移动）
      mapEditorStore.setCollisionLayerTool('select')
    }
    draftActive = false
    draftPolygon = []
    draftPreview = null
    drawOverlay()
  }

  function deleteSelectedVertex() {
    const poly = activePolygon()
    if (!poly || poly.points.length <= 3 || selectedVertexIndex < 0) return
    const next = poly.points.map(p => [p[0], p[1]])
    next.splice(selectedVertexIndex, 1)
    selectedVertexIndex = -1
    mapStore.updateCollisionPolygonPoints(poly.id, next)
    drawOverlay()
  }

  function pointerDown(world: Point, button: number) {
    const layer = activeLayer()
    if (!layer || layer.locked) return
    const tool = mapEditorStore.collisionLayerTool
    const local = snapPoint(world)

    if (tool === 'rect' || tool === 'circle' || tool === 'capsule') {
      if (button !== 0) return
      draftShape = tool
      rectStart = local
      rectCurrent = local
      drawOverlay()
      return
    }

    if (tool === 'polygon') {
      if (button === 2) {
        // 右键撤销上一点
        if (draftActive && draftPolygon.length > 0) {
          draftPolygon.pop()
          if (draftPolygon.length === 0) draftActive = false
        }
        drawOverlay()
        return
      }
      if (button !== 0) return
      if (draftActive && draftPolygon.length >= 3) {
        // 点首点闭合
        if (Math.hypot(draftPolygon[0].x - world.x, draftPolygon[0].y - world.y) < 10 / getScale()) {
          closeDraftPolygon()
          return
        }
        // 双击闭合
        const now = Date.now()
        const last = draftPolygon[draftPolygon.length - 1]
        if (now - lastPolygonClickAt < 350 &&
            Math.hypot(last.x - world.x, last.y - world.y) < 10 / getScale()) {
          closeDraftPolygon()
          return
        }
      }
      if (!draftActive) {
        draftActive = true
        draftPolygon = []
      }
      const prev = draftPolygon[draftPolygon.length - 1]
      if (!prev || Math.hypot(prev.x - local.x, prev.y - local.y) > 1e-5) {
        draftPolygon.push(local)
      }
      lastPolygonClickAt = Date.now()
      drawOverlay()
      return
    }

    // ====== 锚点增删工具 ======
    if (tool === 'addPoint') {
      if (button !== 0) return
      // 未选中碰撞体时，按点击位置自动选中，避免"点了没反应"
      let selected = activePolygon()
      if (!selected) {
        selected = findPolygonAt(world)
        if (selected) mapEditorStore.setActiveCollisionPolygonId(selected.id)
      }
      if (!selected) return
      const pts = pointsOf(selected)
      const edge = findNearestEdge(selected, world, VERTEX_HIT_PX / getScale())
      if (edge >= 0) {
        // 新锚点落在最近的边上（保持形状不变形）
        const proj = projectOnSegment(world, pts[edge], pts[(edge + 1) % pts.length])
        const snapped = snapPoint(proj)
        const next = selected.points.map(p => [p[0], p[1]])
        next.splice(edge + 1, 0, [snapped.x, snapped.y])
        mapStore.updateCollisionPolygonPoints(selected.id, next)
        selectedVertexIndex = edge + 1
      }
      drawOverlay()
      return
    }

    if (tool === 'deletePoint') {
      if (button !== 0) return
      let selected = activePolygon()
      if (!selected) {
        selected = findPolygonAt(world)
        if (selected) mapEditorStore.setActiveCollisionPolygonId(selected.id)
      }
      if (!selected) return
      const idx = findNearestVertex(selected, world, VERTEX_HIT_PX / getScale())
      if (idx >= 0) {
        selectedVertexIndex = idx
        deleteSelectedVertex()
      }
      drawOverlay()
      return
    }

    // ====== 选择 / 编辑 ======
    resetPolygonDrag()
    draggingVertexIndex = -1

    if (button === 2) {
      // 右键删除锚点
      const idx = findNearestVertex(activePolygon(), world, VERTEX_HIT_PX / getScale())
      if (idx >= 0) {
        selectedVertexIndex = idx
        deleteSelectedVertex()
      }
      drawOverlay()
      return
    }
    if (button !== 0) return

    const selected = activePolygon()
    // 1) 锚点优先
    const vertexIdx = findNearestVertex(selected, world, VERTEX_HIT_PX / getScale())
    if (vertexIdx >= 0 && selected) {
      draggingVertexIndex = vertexIdx
      selectedVertexIndex = vertexIdx
      drawOverlay()
      return
    }

    // 2) 靠近边 → 插入锚点并拖动（只作用于当前碰撞体）
    const edgeIdx = findNearestEdge(selected, world, EDGE_HIT_PX / getScale())
    if (edgeIdx >= 0 && selected) {
      const next = selected.points.map(p => [p[0], p[1]])
      next.splice(edgeIdx + 1, 0, [local.x, local.y])
      mapStore.updateCollisionPolygonPoints(selected.id, next)
      draggingVertexIndex = edgeIdx + 1
      selectedVertexIndex = edgeIdx + 1
      drawOverlay()
      return
    }

    // 3) 框内 → 整框拖动；点击其他碰撞体 → 先选中再拖动
    const hit = findPolygonAt(world)
    if (hit) {
      if (!selected || hit.id !== selected.id) {
        mapEditorStore.setActiveCollisionPolygonId(hit.id)
        selectedVertexIndex = -1
      }
      draggingPolygon = true
      dragStartPoints = hit.points.map(p => [p[0], p[1]])
      dragStartWorld = snapPoint(world)
    } else {
      selectedVertexIndex = -1
      mapEditorStore.setActiveCollisionPolygonId(null)
      // 空白处拖拽 = 按当前记忆的形状直接新建（无需再点形状按钮）
      const shape = mapEditorStore.collisionShapeTool
      if (shape !== 'polygon') {
        draftShape = shape
        rectStart = local
        rectCurrent = local
      }
    }
    drawOverlay()
  }

  function pointerMove(world: Point) {
    const tool = mapEditorStore.collisionLayerTool
    const local = snapPoint(world)

    if (rectStart && draftShape) {
      rectCurrent = local
      drawOverlay()
      return
    }
    if (tool === 'polygon' && draftActive) {
      draftPreview = local
      drawOverlay()
      return
    }
    if (tool !== 'select') return

    const poly = activePolygon()
    if (!poly) return

    if (draggingPolygon && dragStartWorld) {
      const current = snapPoint(world)
      const dx = current.x - dragStartWorld.x
      const dy = current.y - dragStartWorld.y
      const next = dragStartPoints.map(p => [p[0] + dx, p[1] + dy])
      mapStore.updateCollisionPolygonPoints(poly.id, next)
      drawOverlay()
      return
    }

    if (draggingVertexIndex >= 0) {
      const next = poly.points.map(p => [p[0], p[1]])
      next[draggingVertexIndex] = [local.x, local.y]
      mapStore.updateCollisionPolygonPoints(poly.id, next)
      drawOverlay()
    }
  }

  function pointerUp(): boolean {
    if (rectStart && rectCurrent && draftShape) {
      const shape = draftShape
      const x0 = Math.min(rectStart.x, rectCurrent.x)
      const x1 = Math.max(rectStart.x, rectCurrent.x)
      const y0 = Math.min(rectStart.y, rectCurrent.y)
      const y1 = Math.max(rectStart.y, rectCurrent.y)
      rectStart = null
      rectCurrent = null
      draftShape = null
      if (x1 - x0 >= 2 && y1 - y0 >= 2) {
        mapStore.addCollisionPolygon(shape, buildShapePoints(shape, x0, y0, x1, y1))
        // 创建完成切回选择移动（形状按钮仍常亮，创建后可立即选中/移动）
        mapEditorStore.setCollisionLayerTool('select')
      }
      drawOverlay()
      return true
    }
    if (draggingVertexIndex >= 0) {
      draggingVertexIndex = -1
      drawOverlay()
      return true
    }
    if (draggingPolygon) {
      resetPolygonDrag()
      drawOverlay()
      return true
    }
    return false
  }

  function handleKeyDown(e: KeyboardEvent): boolean {
    if (mapStore.activeMode !== 'collision') return false
    if (e.key === 'Escape') {
      if (draftActive || rectStart) cancelDraft()
      else if (mapEditorStore.collisionLayerTool !== 'select') mapEditorStore.setCollisionLayerTool('select')
      else mapEditorStore.setActiveCollisionPolygonId(null)
      drawOverlay()
      return true
    }
    if (e.key === 'Enter' && mapEditorStore.collisionLayerTool === 'polygon' && draftActive) {
      e.preventDefault()
      closeDraftPolygon()
      return true
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && mapEditorStore.collisionLayerTool === 'select') {
      e.preventDefault()
      if (selectedVertexIndex >= 0) deleteSelectedVertex()
      else if (activePolygon()) mapStore.removeCollisionPolygon(activePolygon()!.id)
      return true
    }
    return false
  }

  function resetOnLeave() {
    if (draggingVertexIndex >= 0 || draggingPolygon) return
    if (rectStart) {
      rectStart = null
      rectCurrent = null
      draftShape = null
    }
    draftPreview = null
    drawOverlay()
  }

  function hoverKindAt(world: Point): 'vertex' | 'inside' | 'none' {
    const poly = activePolygon()
    if (poly && findNearestVertex(poly, world, VERTEX_HIT_PX / getScale()) >= 0) return 'vertex'
    return findPolygonAt(world) ? 'inside' : 'none'
  }

  function selectPolygon(id: string) {
    mapEditorStore.setActiveCollisionPolygonId(id)
    mapEditorStore.setCollisionLayerTool('select')
    selectedVertexIndex = -1
    drawOverlay()
  }

  function dispose() {
    const canvas = getOverlayCanvas()
    const ctx = canvas?.getContext('2d')
    if (canvas && ctx) {
      ctx.setTransform(1, 0, 0, 1, 0, 0)
      ctx.clearRect(0, 0, canvas.width, canvas.height)
    }
  }

  watch(() => mapStore.collisionRevision, () => drawOverlay())
  watch(() => mapEditorStore.activeCollisionPolygonId, () => drawOverlay())
  watch(() => mapEditorStore.collisionLayerTool, () => drawOverlay())
  watch(() => mapStore.mapLoadCount, () => drawOverlay())

  return {
    drawOverlay,
    pointerDown,
    pointerMove,
    pointerUp,
    handleKeyDown,
    resetOnLeave,
    cancelDraft,
    hoverKindAt,
    selectPolygon,
    dispose,
    // 供画布判断是否有进行中的拖拽
    isDragging: () => draggingVertexIndex >= 0 || draggingPolygon || !!rectStart,
  }
}
