import { watch, onBeforeUnmount, type Ref } from 'vue'
import { usePaintStore } from '../../../stores/paint'
import { floodFill } from '../tools/floodFill'
import { rgbaCss, hexToRgba } from '../utils/artboardExport'

/** 撤销栈上限：后备缓冲为物理像素（Retina 480×360@2x ≈ 2.7MB/张），25 张封顶约 70MB */
const HISTORY_LIMIT = 25

const SHAPE_TOOLS = new Set(['line', 'rect', 'ellipse'])
const FREE_TOOLS = new Set(['brush', 'eraser'])

/**
 * 位图绘制引擎：管理画布 2D 上下文、笔画状态机、撤销/重做快照、工具光标。
 * paper 对象不在此文件（矢量引擎 Stage 2 接入 usePaperScope）。
 * paper/ctx 等重对象全部闭包持有，不进入 Vue 响应式。
 *
 * 坐标约定：位图模式 canvas 后备缓冲 = 逻辑尺寸（1:1 像素网格，对齐 Scratch），
 * setTransform 为单位矩阵。若未来引入 HiDPI/超采样后备（属性=逻辑×缩放），
 * setTransform/pixelScale 机制已就绪：路径绘制走逻辑坐标，getImageData/
 * putImageData/洪水填充工作在后备像素坐标（种子点乘缩放系数）。
 */
export function useBitmapCanvas(canvasRef: Ref<HTMLCanvasElement | undefined>) {
  const store = usePaintStore()

  // ─── 撤销/重做（ImageData 快照，非响应式）───
  const undoStack: ImageData[] = []
  const redoStack: ImageData[] = []

  // ─── 进行中的笔画状态 ───
  let activeOp: 'none' | 'free' | 'shape' = 'none'
  let strokeStart: { x: number; y: number } | null = null
  let lastPoint: { x: number; y: number } | null = null
  /** 形状工具的基准快照（橡皮筋预览：每次 move 先回滚再重画） */
  let baseSnapshot: ImageData | null = null

  function ctx2d(): CanvasRenderingContext2D | null {
    // willReadFrequently：绘制引擎频繁 getImageData（笔画快照/填充），走软件渲染路径避免 GPU 回读卡顿
    return canvasRef.value?.getContext('2d', { willReadFrequently: true }) ?? null
  }

  /** 物理像素 / 逻辑像素 缩放系数（受 canvas 尺寸取整影响，按轴独立计算保证精确） */
  function pixelScale() {
    const canvas = canvasRef.value
    if (!canvas) return { sx: 1, sy: 1 }
    return {
      sx: canvas.width / store.artboardWidth,
      sy: canvas.height / store.artboardHeight,
    }
  }

  /** 把 ctx 变换设为逻辑坐标系（canvas 属性变化会重置 context 状态，尺寸变更后必须重调） */
  function applyBackingTransform() {
    const c = ctx2d()
    const canvas = canvasRef.value
    if (!c || !canvas) return
    const { sx, sy } = pixelScale()
    c.setTransform(sx, 0, 0, sy, 0, 0)
  }

  /** 屏幕坐标 → 画板逻辑坐标（getBoundingClientRect 已含 CSS transform 缩放/平移） */
  function clientToArtboard(e: { clientX: number; clientY: number }) {
    const canvas = canvasRef.value!
    const rect = canvas.getBoundingClientRect()
    return {
      x: ((e.clientX - rect.left) / rect.width) * store.artboardWidth,
      y: ((e.clientY - rect.top) / rect.height) * store.artboardHeight,
    }
  }

  function snapshot(): ImageData | null {
    const c = ctx2d()
    const canvas = canvasRef.value
    if (!c || !canvas) return null
    return c.getImageData(0, 0, canvas.width, canvas.height)
  }

  function syncHistoryFlags() {
    store.canUndo = undoStack.length > 0
    store.canRedo = redoStack.length > 0
  }

  /** 变更前压栈；redo 分支统一清空 */
  function pushHistory() {
    const snap = snapshot()
    if (!snap) return
    undoStack.push(snap)
    if (undoStack.length > HISTORY_LIMIT) undoStack.shift()
    redoStack.length = 0
    syncHistoryFlags()
  }

  function markDirty() {
    store.dirty = true
  }

  function undo() {
    const c = ctx2d()
    if (!c || undoStack.length === 0) return
    const current = snapshot()
    if (!current) return
    redoStack.push(current)
    if (redoStack.length > HISTORY_LIMIT) redoStack.shift()
    const prev = undoStack.pop()!
    c.putImageData(prev, 0, 0)
    syncHistoryFlags()
  }

  function redo() {
    const c = ctx2d()
    if (!c || redoStack.length === 0) return
    const current = snapshot()
    if (!current) return
    undoStack.push(current)
    if (undoStack.length > HISTORY_LIMIT) undoStack.shift()
    const next = redoStack.pop()!
    c.putImageData(next, 0, 0)
    syncHistoryFlags()
  }

  function clear() {
    const c = ctx2d()
    if (!c) return
    pushHistory()
    // 逻辑坐标系下清整板（transform 已缩放到物理像素）
    c.clearRect(0, 0, store.artboardWidth, store.artboardHeight)
    markDirty()
  }

  // ─── 自由笔画（画笔/橡皮）───

  function beginFreeStroke(point: { x: number; y: number }) {
    const c = ctx2d()
    if (!c) return
    pushHistory()
    activeOp = 'free'
    lastPoint = point

    c.save()
    if (store.activeTool === 'eraser') {
      c.globalCompositeOperation = 'destination-out'
      c.strokeStyle = 'rgba(0, 0, 0, 1)'
    } else {
      c.strokeStyle = rgbaCss(store.fillColor, store.opacity)
    }
    c.lineWidth = store.brushSize
    c.lineCap = 'round'
    c.lineJoin = 'round'
    // 单击无移动也要留下一个圆点
    c.beginPath()
    c.moveTo(point.x, point.y)
    c.lineTo(point.x + 0.01, point.y + 0.01)
    c.stroke()
  }

  function continueFreeStroke(point: { x: number; y: number }) {
    const c = ctx2d()
    if (!c || !lastPoint) return
    c.beginPath()
    c.moveTo(lastPoint.x, lastPoint.y)
    c.lineTo(point.x, point.y)
    c.stroke()
    lastPoint = point
  }

  function endFreeStroke() {
    ctx2d()?.restore()
    activeOp = 'none'
    lastPoint = null
    markDirty()
  }

  // ─── 形状笔画（直线/矩形/椭圆，橡皮筋预览）───

  /** Shift 约束：矩形/椭圆→正形，直线→45° 步进 */
  function constrainPoint(p: { x: number; y: number }, shift: boolean) {
    if (!shift || !strokeStart) return p
    const dx = p.x - strokeStart.x
    const dy = p.y - strokeStart.y
    if (store.activeTool === 'line') {
      const angle = Math.atan2(dy, dx)
      const step = Math.PI / 4
      const snapped = Math.round(angle / step) * step
      const len = Math.hypot(dx, dy)
      return {
        x: strokeStart.x + Math.cos(snapped) * len,
        y: strokeStart.y + Math.sin(snapped) * len,
      }
    }
    // rect / ellipse：等宽高
    const s = Math.max(Math.abs(dx), Math.abs(dy))
    return {
      x: strokeStart.x + (dx < 0 ? -s : s),
      y: strokeStart.y + (dy < 0 ? -s : s),
    }
  }

  function drawShapePreview(c: CanvasRenderingContext2D, start: { x: number; y: number }, end: { x: number; y: number }) {
    // 统一使用绘制色（fillColor）：直线/形状描边与填充同色，切换工具颜色不变
    // 填充/描边开关：两者都关时回退为填充（保证可见）；直线只有描边
    const fillOn = store.activeTool !== 'line' && (store.fillEnabled || !store.strokeEnabled)
    const strokeOn = store.activeTool === 'line' || store.strokeEnabled

    c.lineWidth = store.strokeWidth
    c.lineJoin = 'round'
    c.lineCap = 'round'
    c.beginPath()

    switch (store.activeTool) {
      case 'line':
        c.moveTo(start.x, start.y)
        c.lineTo(end.x, end.y)
        break
      case 'rect': {
        const x = Math.min(start.x, end.x)
        const y = Math.min(start.y, end.y)
        c.rect(x, y, Math.abs(end.x - start.x), Math.abs(end.y - start.y))
        break
      }
      case 'ellipse': {
        const cx = (start.x + end.x) / 2
        const cy = (start.y + end.y) / 2
        const rx = Math.abs(end.x - start.x) / 2
        const ry = Math.abs(end.y - start.y) / 2
        c.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2)
        break
      }
    }

    if (fillOn) {
      c.fillStyle = rgbaCss(store.fillColor, store.opacity)
      c.fill()
    }
    if (strokeOn) {
      c.strokeStyle = rgbaCss(store.fillColor, store.opacity)
      c.stroke()
    }
  }

  function beginShape(point: { x: number; y: number }) {
    const snap = snapshot()
    if (!snap) return
    pushHistory()
    activeOp = 'shape'
    strokeStart = point
    baseSnapshot = snap
  }

  function continueShape(point: { x: number; y: number }, shift: boolean) {
    const c = ctx2d()
    if (!c || !strokeStart || !baseSnapshot) return
    c.putImageData(baseSnapshot, 0, 0)
    drawShapePreview(c, strokeStart, constrainPoint(point, shift))
  }

  function endShape(point: { x: number; y: number }, shift: boolean) {
    const c = ctx2d()
    if (!c || !strokeStart || !baseSnapshot) {
      resetShapeState()
      return
    }
    const end = constrainPoint(point, shift)
    const isClick = Math.abs(end.x - strokeStart.x) < 0.5 && Math.abs(end.y - strokeStart.y) < 0.5
    c.putImageData(baseSnapshot, 0, 0)
    if (isClick) {
      // 零尺寸空点击：丢弃本次压栈，不产生可见变更
      undoStack.pop()
      syncHistoryFlags()
    } else {
      drawShapePreview(c, strokeStart, end)
      markDirty()
    }
    resetShapeState()
  }

  function resetShapeState() {
    activeOp = 'none'
    strokeStart = null
    baseSnapshot = null
  }

  // ─── 填充（洪水填充）───

  function doFill(point: { x: number; y: number }) {
    const c = ctx2d()
    const canvas = canvasRef.value
    if (!c || !canvas) return
    const img = c.getImageData(0, 0, canvas.width, canvas.height)
    const css = hexToRgba(store.fillColor, store.opacity)
    // floodFill 的 alpha 是 ImageData 通道值（0-255），而 hexToRgba 返回 CSS 约定（0-1）。
    // 不转换会把 alpha≈1 写进画布 → 填充区域近乎全透明，看起来像“被删除”
    const color = { r: css.r, g: css.g, b: css.b, a: Math.round(css.a * 255) }
    const { sx, sy } = pixelScale()
    const filled = floodFill(img, Math.floor(point.x * sx), Math.floor(point.y * sy), color)
    if (filled > 0) {
      pushHistory()
      c.putImageData(img, 0, 0)
      markDirty()
    }
  }

  // ─── 指针事件路由 ───

  function onPointerDown(e: PointerEvent) {
    if (e.button !== 0 || store.mode !== 'bitmap') return
    const canvas = canvasRef.value
    if (!canvas) return
    e.preventDefault()

    const point = clientToArtboard(e)
    if (FREE_TOOLS.has(store.activeTool)) {
      beginFreeStroke(point)
    } else if (SHAPE_TOOLS.has(store.activeTool)) {
      beginShape(point)
    } else if (store.activeTool === 'fill') {
      doFill(point)
    } else {
      // select / reshape / text / eyedropper：后续阶段实现
      return
    }
    canvas.setPointerCapture(e.pointerId)
  }

  function onPointerMove(e: PointerEvent) {
    if (activeOp === 'none') return
    const point = clientToArtboard(e)
    if (activeOp === 'free') {
      continueFreeStroke(point)
    } else {
      continueShape(point, e.shiftKey)
    }
  }

  function onPointerUp(e: PointerEvent) {
    if (activeOp === 'none') return
    const point = clientToArtboard(e)
    if (activeOp === 'free') {
      endFreeStroke()
    } else {
      endShape(point, e.shiftKey)
    }
  }

  // ─── 工具光标 ───

  /** 画笔/橡皮：双环保证深浅底都可见的圆圈光标，直径随缩放变化 */
  function makeCircleCursor(screenSize: number): string {
    const d = Math.max(4, Math.round(screenSize))
    const c = document.createElement('canvas')
    c.width = d
    c.height = d
    const cc = c.getContext('2d')!
    cc.beginPath()
    cc.arc(d / 2, d / 2, d / 2 - 1, 0, Math.PI * 2)
    cc.strokeStyle = 'rgba(255, 255, 255, 0.9)'
    cc.lineWidth = 1.5
    cc.stroke()
    cc.beginPath()
    cc.arc(d / 2, d / 2, d / 2 - 1, 0, Math.PI * 2)
    cc.strokeStyle = 'rgba(0, 0, 0, 0.8)'
    cc.lineWidth = 1
    cc.stroke()
    return `url(${c.toDataURL()}) ${d / 2} ${d / 2}, crosshair`
  }

  function updateCursor() {
    const canvas = canvasRef.value
    if (!canvas) return
    const tool = store.activeTool
    if (tool === 'brush' || tool === 'eraser') {
      canvas.style.cursor = makeCircleCursor(store.brushSize * store.zoom)
    } else if (tool === 'line' || tool === 'rect' || tool === 'ellipse' || tool === 'fill') {
      canvas.style.cursor = 'crosshair'
    } else {
      canvas.style.cursor = 'default'
    }
  }

  // ─── 生命周期 ───

  function attach() {
    const canvas = canvasRef.value
    if (!canvas) return
    applyBackingTransform()
    updateCursor()
    canvas.addEventListener('pointerdown', onPointerDown)
    canvas.addEventListener('pointermove', onPointerMove)
    canvas.addEventListener('pointerup', onPointerUp)
    canvas.addEventListener('pointercancel', onPointerUp)
  }

  function detach() {
    const canvas = canvasRef.value
    if (!canvas) return
    canvas.removeEventListener('pointerdown', onPointerDown)
    canvas.removeEventListener('pointermove', onPointerMove)
    canvas.removeEventListener('pointerup', onPointerUp)
    canvas.removeEventListener('pointercancel', onPointerUp)
  }

  // canvas 元素在模板中必然存在（棋盘格内），挂载后绑定
  watch(canvasRef, (el, old) => {
    if (old) detach()
    if (el) attach()
  }, { immediate: true })

  watch(() => [store.activeTool, store.brushSize, store.zoom], updateCursor, { immediate: true })

  // 画板尺寸变化：canvas 属性变更会清空内容并把 ctx 变换重置为单位矩阵。
  // flush: 'post' 保证此时模板上的新 width/height 属性已生效，再重设变换；
  // 同步清掉历史快照防止尺寸错乱的 putImageData
  watch(() => [store.artboardWidth, store.artboardHeight], () => {
    applyBackingTransform()
    undoStack.length = 0
    redoStack.length = 0
    syncHistoryFlags()
  }, { flush: 'post' })

  onBeforeUnmount(() => {
    detach()
    undoStack.length = 0
    redoStack.length = 0
  })

  return {
    undo,
    redo,
    clear,
    getCanvas: () => canvasRef.value ?? null,
  }
}
