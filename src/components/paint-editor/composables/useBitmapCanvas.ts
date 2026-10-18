import { watch, nextTick, onBeforeUnmount, type Ref } from 'vue'
import { usePaintStore } from '../../../stores/paint'
import { floodFill } from '../tools/floodFill'
import { rgbaCss, hexToRgba } from '../utils/artboardExport'
import { contentBBox } from '../../../utils/bsfPacker'

/** 撤销栈上限：位图后备为 1:1 逻辑像素（640×480 ≈ 1.2MB/张），每帧独立计 */
const HISTORY_LIMIT = 25

const SHAPE_TOOLS = new Set(['line', 'rect', 'ellipse'])
const FREE_TOOLS = new Set(['brush', 'eraser'])

/**
 * 位图绘制引擎：管理画布 2D 上下文、笔画状态机、撤销/重做快照、工具光标、多帧像素。
 * paper 对象不在此文件（矢量引擎 Stage 2 接入 usePaperScope）。
 * paper/ctx/离屏画布等重对象全部闭包持有，不进入 Vue 响应式。
 *
 * 坐标约定：位图模式 canvas 后备缓冲 = 逻辑尺寸（1:1 像素网格，对齐 Scratch），
 * setTransform 为单位矩阵。若未来引入 HiDPI/超采样后备（属性=逻辑×缩放），
 * setTransform/pixelScale 机制已就绪：路径绘制走逻辑坐标，getImageData/
 * putImageData/洪水填充工作在后备像素坐标（种子点乘缩放系数）。
 *
 * 多帧约定：DOM canvas 是【活动帧】的唯一真源；非活动帧存在离屏画布数组 pixels[]，
 * 与 store.frames 下标对齐。切换帧时 flush（DOM→离屏）/ load（离屏→DOM）；
 * 撤销栈按帧 id 存放在 histMap，切换时随帧交换。
 */
export function useBitmapCanvas(canvasRef: Ref<HTMLCanvasElement | undefined>) {
  const store = usePaintStore()

  // ─── 多帧像素与历史（非响应式闭包）───
  /** pixels[i] = 第 i 帧离屏画布；null = 未初始化（空白帧） */
  let pixels: (HTMLCanvasElement | null)[] = [null]
  /**
   * 帧名（与 pixels 对齐）：载入既有角色帧时保留原名（.bsf clips 引用），
   * 新建帧为 null（保存回写时生成唯一新名）。
   */
  let frameNames: (string | null)[] = [null]
  let currentIdx = 0
  const histMap = new Map<string, { undo: ImageData[]; redo: ImageData[] }>()

  // ─── 撤销/重做（当前帧的栈；切帧时换入换出）───
  let undoStack: ImageData[] = []
  let redoStack: ImageData[] = []

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

  // ─── 多帧像素管理 ───

  function makeOffscreen(w: number, h: number): HTMLCanvasElement {
    const c = document.createElement('canvas')
    c.width = w
    c.height = h
    return c
  }

  /** 生成帧缩略图（高 44px 等比）写入 store 元数据，供帧列表展示 */
  function updateThumb(index: number, source: HTMLCanvasElement) {
    const meta = store.frames[index]
    if (!meta || source.height === 0) return
    const th = 44
    const tw = Math.max(1, Math.round((source.width / source.height) * th))
    const tc = makeOffscreen(tw, th)
    const tctx = tc.getContext('2d')!
    tctx.imageSmoothingEnabled = true
    tctx.drawImage(source, 0, 0, tw, th)
    meta.thumb = tc.toDataURL('image/png')
  }

  /** 活动帧（DOM canvas）→ 离屏存储 + 刷新缩略图 */
  function flushActiveToPixels() {
    const canvas = canvasRef.value
    if (!canvas || currentIdx < 0 || currentIdx >= pixels.length) return
    let off = pixels[currentIdx]
    if (!off) {
      off = makeOffscreen(canvas.width, canvas.height)
      pixels[currentIdx] = off
    }
    const octx = off.getContext('2d')!
    octx.setTransform(1, 0, 0, 1, 0, 0)
    octx.clearRect(0, 0, off.width, off.height)
    octx.drawImage(canvas, 0, 0)
    updateThumb(currentIdx, off)
  }

  /** 离屏存储 → 活动帧（DOM canvas）；像素复制走单位变换避免路径变换干扰 */
  function loadPixelsToActive(index: number) {
    const c = ctx2d()
    const canvas = canvasRef.value
    if (!c || !canvas) return
    c.setTransform(1, 0, 0, 1, 0, 0)
    c.clearRect(0, 0, canvas.width, canvas.height)
    const src = index >= 0 && index < pixels.length ? pixels[index] : null
    if (src) c.drawImage(src, 0, 0)
    applyBackingTransform()
  }

  /**
   * 帧同步：把 DOM canvas 切换到 store.activeFrameIndex 指向的帧。
   * flush 旧帧 → 交换撤销栈 → load 新帧。
   */
  function syncActiveFrame() {
    const target = store.activeFrameIndex
    if (target === currentIdx && currentIdx >= 0) return

    if (currentIdx >= 0 && currentIdx < pixels.length) flushActiveToPixels()

    // 旧帧历史入柜
    const oldMeta = currentIdx >= 0 ? store.frames[currentIdx] : undefined
    if (oldMeta) {
      histMap.set(oldMeta.id, { undo: undoStack, redo: redoStack })
    }

    currentIdx = target

    // 新帧历史出柜（未访问过的帧用全新栈）
    const newMeta = target >= 0 ? store.frames[target] : undefined
    if (newMeta) {
      const h = histMap.get(newMeta.id)
      undoStack = h?.undo ?? []
      redoStack = h?.redo ?? []
    } else {
      undoStack = []
      redoStack = []
    }
    loadPixelsToActive(target)
    syncHistoryFlags()
  }

  watch(() => store.activeFrameIndex, () => syncActiveFrame())

  /**
   * 新建/复制帧：复制=拷贝当前帧内容，新建=空白；自动切换到新帧。
   */
  function addFrame(duplicate: boolean) {
    const canvas = canvasRef.value
    if (!canvas) return
    flushActiveToPixels()

    const off = makeOffscreen(canvas.width, canvas.height)
    if (duplicate && currentIdx >= 0 && currentIdx < pixels.length && pixels[currentIdx]) {
      off.getContext('2d')!.drawImage(pixels[currentIdx]!, 0, 0)
    }
    pixels.push(off)
    frameNames.push(null)
    store.frames.push({ id: store.makeFrameId() })
    updateThumb(pixels.length - 1, off)

    // 切到新帧（watcher 负责 flush 旧帧并 load；重复 flush 幂等无害）
    store.activeFrameIndex = store.frames.length - 1
    markDirty()
  }

  /** 删除指定帧（至少保留 1 帧） */
  function removeFrame(index: number): boolean {
    if (store.frames.length <= 1 || index < 0 || index >= store.frames.length) return false
    flushActiveToPixels()

    histMap.delete(store.frames[index].id)
    pixels.splice(index, 1)
    frameNames.splice(index, 1)
    store.frames.splice(index, 1)

    let newIdx = store.activeFrameIndex
    if (index < newIdx) newIdx--
    else if (index === newIdx) newIdx = Math.min(newIdx, store.frames.length - 1)

    currentIdx = -1 // 失效，强制 sync 重载（删的是当前帧时新帧顶上同下标，watcher 不会触发）
    store.activeFrameIndex = newIdx
    syncActiveFrame()
    markDirty()
    return true
  }

  /**
   * 整体载入一组帧（编辑既有角色）：替换全部离屏像素与帧名，切到指定帧。
   * 载入帧为全画布尺寸；names[i] 为原帧名（新建帧传 null，保存时生成）。
   */
  function loadFrames(canvases: HTMLCanvasElement[], names: (string | null)[], activeIndex: number) {
    pixels = canvases.map(c => {
      const off = makeOffscreen(c.width, c.height)
      off.getContext('2d')!.drawImage(c, 0, 0)
      return off
    })
    frameNames = names.slice(0, canvases.length)
    while (frameNames.length < canvases.length) frameNames.push(null)

    histMap.clear()
    undoStack = []
    redoStack = []

    store.frames = canvases.map(() => ({ id: store.makeFrameId() }))
    const idx = Math.min(Math.max(0, activeIndex), Math.max(0, canvases.length - 1))
    currentIdx = -1
    store.activeFrameIndex = idx
    syncActiveFrame()

    pixels.forEach((pc, i) => {
      if (pc) updateThumb(i, pc)
    })
    syncHistoryFlags()
  }

  /** 帧名列表（与 getFrameCanvases 对齐；null = 新帧，回写时生成） */
  function getFrameNames(): (string | null)[] {
    return [...frameNames]
  }

  /** 供保存管线取全部帧像素（先 flush 活动帧；调用方只读不改） */
  function getFrameCanvases(): HTMLCanvasElement[] {
    flushActiveToPixels()
    const w = canvasRef.value?.width ?? store.artboardWidth
    const h = canvasRef.value?.height ?? store.artboardHeight
    return pixels.map(pc => pc ?? makeOffscreen(w, h))
  }

  /**
   * 一键裁切画板到内容：取【全部帧】非透明像素的联合包围盒，裁掉四周空白
   * （每帧内容整体平移，互不裁切丢失）。尺寸变更经模板重新绑定清空 canvas，
   * 裁出的像素在 nextTick（属性生效后）写回。
   * @returns false = 无可裁切（全部为空或已无空白）
   */
  function cropToContent(): boolean {
    if (store.mode !== 'bitmap') return false
    flushActiveToPixels()

    let minX = Infinity
    let minY = Infinity
    let maxX = -1
    let maxY = -1
    for (const pc of pixels) {
      if (!pc) continue
      const b = contentBBox(pc)
      if (!b) continue
      minX = Math.min(minX, b.x)
      minY = Math.min(minY, b.y)
      maxX = Math.max(maxX, b.x + b.w - 1)
      maxY = Math.max(maxY, b.y + b.h - 1)
    }
    if (maxX < 0) return false
    const w = maxX - minX + 1
    const h = maxY - minY + 1
    if (w === store.artboardWidth && h === store.artboardHeight && minX === 0 && minY === 0) return false

    // 每帧重建为新尺寸并整体平移
    pixels = pixels.map(pc => {
      if (!pc) return null
      const nc = makeOffscreen(w, h)
      nc.getContext('2d')!.drawImage(pc, -minX, -minY)
      return nc
    })

    histMap.clear()
    undoStack = []
    redoStack = []

    // 触发模板重新绑定尺寸（canvas 被清空），尺寸 watch 清历史并重设变换
    store.artboardWidth = w
    store.artboardHeight = h
    store.dirty = true
    currentIdx = -1
    nextTick(() => {
      syncActiveFrame()
      for (let i = 0; i < pixels.length; i++) {
        if (pixels[i]) updateThumb(i, pixels[i]!)
      }
      // 新画板居中复位，保证内容完整可见
      store.resetView()
    })
    return true
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
  // 同步清掉全部帧的历史快照（尺寸变化后快照与画布不匹配，跨帧同样失效）
  watch(() => [store.artboardWidth, store.artboardHeight], () => {
    applyBackingTransform()
    histMap.clear()
    undoStack = []
    redoStack = []
    syncHistoryFlags()
  }, { flush: 'post' })

  onBeforeUnmount(() => {
    detach()
    undoStack = []
    redoStack = []
    histMap.clear()
    pixels = []
  })

  return {
    undo,
    redo,
    clear,
    cropToContent,
    addFrame,
    removeFrame,
    loadFrames,
    getFrameCanvases,
    getFrameNames,
    getCanvas: () => canvasRef.value ?? null,
  }
}
