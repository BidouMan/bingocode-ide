import { watch } from 'vue'
import { useMapStore, type ShapeLayer, type ShapeItem } from '../stores/map'
import { useMapEditorStore } from '../stores/mapEditor'
import { pointInPolygon } from '../utils/mapImageGeometry'
import { collectSnapLines, snapAxisValue, snapRectOffset, snapThreshold } from '../utils/smartSnap'

interface ShapeLayerEditorOptions {
  getApp: () => any
  getScale: () => number
  /** 屏幕坐标叠加层 canvas：位于矢量画布之上，避免碰撞线被图像/矢量内容遮住 */
  getOverlayCanvas: () => HTMLCanvasElement | null
  /** 每次重绘前把叠加层 canvas 对齐到 Pixi 画布（尺寸/位置/DPR），避免偏移和拉伸模糊 */
  syncOverlay?: () => void
}

interface Point { x: number; y: number }

/**
 * 形状层编辑：世界坐标判定形状，选择/整框拖动/顶点编辑/矩形/自定义钢笔。
 */
export function useShapeLayerEditor(options: ShapeLayerEditorOptions) {
  const mapStore = useMapStore()
  const mapEditorStore = useMapEditorStore()
  const { getApp, getScale, getOverlayCanvas, syncOverlay } = options

  // 锚点抓取的屏幕像素容差
  const VERTEX_HIT_PX = 12

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

  function activeLayer(): ShapeLayer | null {
    return mapStore.activeShapeLayer
  }

  function activePolygon(): ShapeItem | null {
    return mapStore.activeShape
  }

  function pointsOf(polygon: ShapeItem): Point[] {
    return polygon.points.map(p => ({ x: p[0], y: p[1] }))
  }

  /** 智能吸附：像素 / 网格 / 图像边缘与中心；关闭时返回原始坐标（完全自由） */
  function snapPoint(world: Point): Point {
    if (!mapEditorStore.smartSnap) return world
    const ts = Math.max(1, mapStore.mapData.tileSize)
    const mapW = mapStore.mapData.width * ts
    const mapH = mapStore.mapData.height * ts
    const lines = collectSnapLines(mapStore.mapData.layers, mapW, mapH)
    const threshold = snapThreshold(getScale())
    return {
      x: snapAxisValue(world.x, lines.xs, ts, threshold),
      y: snapAxisValue(world.y, lines.ys, ts, threshold),
    }
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
    // 智能吸附开启时生成点取整（像素吸附），关闭时保留自由小数坐标
    if (mapEditorStore.smartSnap) {
      return points.map(p => [Math.round(p[0]), Math.round(p[1])])
    }
    return points
  }

  function findNearestVertex(polygon: ShapeItem | null, world: Point, threshold: number): number {
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

  function findNearestEdge(polygon: ShapeItem | null, world: Point, threshold: number): number {
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

  /** 当前形状层中命中最上层形状 */
  function findPolygonAt(world: Point): ShapeItem | null {
    const layer = activeLayer()
    if (!layer || layer.locked) return null
    for (let i = layer.shapes.length - 1; i >= 0; i--) {
      const poly = layer.shapes[i]
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
    selected = false,
    label = '',
  ) {
    if (points.length < 2) return
    const scale = getScale()
    ctx.beginPath()
    ctx.moveTo(points[0].x, points[0].y)
    for (let i = 1; i < points.length; i++) ctx.lineTo(points[i].x, points[i].y)
    ctx.closePath()
    ctx.fillStyle = colorCss(color, fillAlpha)
    ctx.fill()
    ctx.strokeStyle = colorCss(color, selected ? 1 : 0.9)
    ctx.lineWidth = selected ? lineWidth * 1.8 : lineWidth
    ctx.stroke()

    // 标签可视化：有标签的形状在包围盒中心写名字，一眼看出感应区/触发区的用途
    const text = label.trim()
    if (text) {
      const xs = points.map(p => p.x)
      const ys = points.map(p => p.y)
      const minX = Math.min(...xs)
      const maxX = Math.max(...xs)
      const minY = Math.min(...ys)
      const maxY = Math.max(...ys)
      // 形状在屏幕上太小时不写字，避免糊成一团
      if ((maxX - minX) * scale >= 18 && (maxY - minY) * scale >= 12) {
        const shown = text.length > 16 ? `${text.slice(0, 16)}…` : text
        // 画布变换含 DPR × 缩放，字号除以缩放得到屏幕稳定的 11px
        ctx.font = `${11 / scale}px "PingFang SC", "Microsoft YaHei", sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.lineWidth = 3 / scale
        ctx.strokeStyle = 'rgba(10, 12, 16, 0.75)'
        ctx.strokeText(shown, (minX + maxX) / 2, (minY + maxY) / 2)
        ctx.fillStyle = colorCss(color, 0.95)
        ctx.fillText(shown, (minX + maxX) / 2, (minY + maxY) / 2)
      }
    }

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

  /** 形状颜色：按能力类型区分，禁用统一灰色 */
  function shapeColor(poly: ShapeItem): number {
    if (poly.disabled) return 0x888888
    if (poly.kind === 'sensor') return 0xe5c07b
    if (poly.kind === 'both') return 0x528bff
    return 0xff5050
  }

  function drawOverlay() {
    const app = getApp()
    // 重绘前先对齐叠加层：尺寸/位置必须与 Pixi 画布完全一致，否则会出现偏移和拉伸模糊
    syncOverlay?.()
    const canvas = getOverlayCanvas()
    if (!app || !canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const dpr = window.devicePixelRatio || 1
    const scale = getScale()
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    // 平移量取整到设备像素，避免整像素网格线落在半像素上发虚
    const offsetX = Math.round(dpr * (app.stage.x || 0))
    const offsetY = Math.round(dpr * (app.stage.y || 0))
    ctx.setTransform(dpr * scale, 0, 0, dpr * scale, offsetX, offsetY)

    const lineWidth = Math.max(1, Math.round(1.5 * dpr)) / (dpr * scale)
    const editingLayer = activeLayer()
    const activeId = mapEditorStore.activeShapeId
    const editing = editingLayer != null

    for (const layer of mapStore.mapData.layers) {
      if (layer.type !== 'shape' || !layer.visible) continue
      const isActiveLayer = layer === editingLayer
      for (const poly of layer.shapes) {
        if (poly.points.length < 3) continue
        const isActive = isActiveLayer && poly.id === activeId
        drawPolygon(
          ctx,
          pointsOf(poly),
          shapeColor(poly),
          isActive ? (poly.disabled ? 0.16 : 0.26) : isActiveLayer ? 0.16 : 0.1,
          lineWidth,
          // 选择/加锚点/删锚点都需要看到锚点，保证增删即时可见
          isActive && editing && ['select', 'addPoint', 'deletePoint'].includes(mapEditorStore.shapeTool),
          isActive,
          poly.tag || '',
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
      mapStore.addShape('polygon', draftPolygon.map(p => [p.x, p.y]))
      // 创建后立即切到鼠标工具，让新形状处于选中可编辑状态
      mapEditorStore.setShapeTool('select')
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
    mapStore.updateShapePoints(poly.id, next)
    drawOverlay()
  }

  function pointerDown(world: Point, button: number) {
    const layer = activeLayer()
    if (!layer || layer.locked) return
    const tool = mapEditorStore.shapeTool
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
        if (selected) mapEditorStore.setActiveShapeId(selected.id)
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
        mapStore.updateShapePoints(selected.id, next)
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
        if (selected) mapEditorStore.setActiveShapeId(selected.id)
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

    // ====== 鼠标选择 / 编辑 ======
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

    // 2) 点到形状 → 选中并整框拖动；点到空白 → 按当前形状标签直接新建
    const hit = findPolygonAt(world)
    if (hit) {
      if (!selected || hit.id !== selected.id) {
        mapEditorStore.setActiveShapeId(hit.id)
        selectedVertexIndex = -1
      }
      draggingPolygon = true
      dragStartPoints = hit.points.map(p => [p[0], p[1]])
      // 整框拖动按原始指针位移计算，再由矩形吸附对齐边缘/中心（避免起点吸附造成跳动）
      dragStartWorld = { x: world.x, y: world.y }
    } else {
      selectedVertexIndex = -1
      mapEditorStore.setActiveShapeId(null)
      // 空白处拖拽 = 按当前形状标签直接新建（无需再点形状按钮）
      const shape = mapEditorStore.shapeDrawTool
      if (shape !== 'polygon') {
        draftShape = shape
        rectStart = local
        rectCurrent = local
      }
    }
    drawOverlay()
  }

  function pointerMove(world: Point) {
    const tool = mapEditorStore.shapeTool
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
      let dx = world.x - dragStartWorld.x
      let dy = world.y - dragStartWorld.y
      // 智能吸附：让碰撞框的左/中/右、上/中/下 就近对齐候选线
      if (mapEditorStore.smartSnap) {
        const xs = dragStartPoints.map(p => p[0])
        const ys = dragStartPoints.map(p => p[1])
        const ts = Math.max(1, mapStore.mapData.tileSize)
        const lines = collectSnapLines(
          mapStore.mapData.layers,
          mapStore.mapData.width * ts,
          mapStore.mapData.height * ts,
        )
        const offset = snapRectOffset({
          left: Math.min(...xs) + dx,
          top: Math.min(...ys) + dy,
          right: Math.max(...xs) + dx,
          bottom: Math.max(...ys) + dy,
        }, lines, ts, snapThreshold(getScale()))
        dx += offset.dx
        dy += offset.dy
      }
      const next = dragStartPoints.map(p => [p[0] + dx, p[1] + dy])
      mapStore.updateShapePoints(poly.id, next)
      drawOverlay()
      return
    }

    if (draggingVertexIndex >= 0) {
      const next = poly.points.map(p => [p[0], p[1]])
      next[draggingVertexIndex] = [local.x, local.y]
      mapStore.updateShapePoints(poly.id, next)
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
        mapStore.addShape(shape, buildShapePoints(shape, x0, y0, x1, y1))
        // 创建后立即切到鼠标工具，让新形状处于选中可编辑状态
        mapEditorStore.setShapeTool('select')
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
    if (mapStore.activeMode !== 'shape') return false
    if (e.key === 'Escape') {
      if (draftActive || rectStart) cancelDraft()
      else if (mapEditorStore.shapeTool !== 'select') mapEditorStore.setShapeTool('select')
      else mapEditorStore.setActiveShapeId(null)
      drawOverlay()
      return true
    }
    if (e.key === 'Enter' && mapEditorStore.shapeTool === 'polygon' && draftActive) {
      e.preventDefault()
      closeDraftPolygon()
      return true
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && mapEditorStore.shapeTool === 'select') {
      e.preventDefault()
      if (selectedVertexIndex >= 0) deleteSelectedVertex()
      else if (activePolygon()) mapStore.removeShape(activePolygon()!.id)
      drawOverlay()
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
    mapEditorStore.setActiveShapeId(id)
    mapEditorStore.setShapeTool('select')
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

  watch(() => mapStore.shapeRevision, () => drawOverlay())
  watch(() => mapEditorStore.activeShapeId, () => drawOverlay())
  watch(() => mapEditorStore.shapeTool, () => drawOverlay())
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
