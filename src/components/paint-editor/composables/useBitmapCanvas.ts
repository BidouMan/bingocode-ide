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

  // ─── 位图选区（select 工具：框选 → 自动浮动 + 变换框移动/旋转/缩放）───
  /** 浮动选区原始像素（未变换）；显示 = 以 floatXf 变换绘制 */
  let floatCanvas: HTMLCanvasElement | null = null
  /** 浮动选区变换：中心（画布逻辑坐标）+ 缩放 + 旋转角 */
  let floatXf = { cx: 0, cy: 0, sx: 1, sy: 1, angle: 0 }
  /** 剪贴板单槽（画板会话内有效，可跨帧粘贴） */
  let clipboardCanvas: HTMLCanvasElement | null = null
  let clipboardOrigin = { x: 0, y: 0 }
  let selOp: 'none' | 'create' | 'move' | 'scale' | 'rotate' = 'none'
  let selAnchor = { x: 0, y: 0 }
  /** move：按下点相对浮动中心的偏移 */
  let floatGrab = { x: 0, y: 0 }
  /** scale：down 时锚点世界坐标 / 初始指针局部坐标 / 手柄方向 / 启用轴 / 原始半尺寸 */
  let scaleAnchorW = { x: 0, y: 0 }
  let scaleP0Local = { x: 0, y: 0 }
  let scaleDir = { x: 1, y: 1 }
  let scaleAxes = { x: true, y: true }
  let scaleOrigHalf = { x: 0, y: 0 }
  /** op 开始时的浮动变换快照（up 时比较判断是否产生实际变化） */
  let opStartXf: { cx: number; cy: number; sx: number; sy: number; angle: number } | null = null

  /**
   * 整帧仿射变换烘入（矢量模式下位图代理 Raster 手势/翻转结束时调用）：
   * 按画板逻辑坐标的 paper 仿射矩阵重采样当前帧像素并替换；
   * 变换前压一步撤销（快照 = 变换前像素），随后重绘 DOM 与缩略图。
   */
  function transformWholeFrame(m: {
    a: number
    b: number
    c: number
    d: number
    tx: number
    ty: number
  }) {
    flushActiveToPixels() // 确保 pixels 与 DOM 一致（flush 顺带收口浮动选区）
    const base = pixels[currentIdx]
    if (!base) return
    pushHistory()
    const { sx, sy } = pixelScale()
    const out = makeOffscreen(base.width, base.height)
    const octx = out.getContext('2d')!
    // 物理坐标变换 = 缩放 S ∘ 逻辑仿射 M：setTransform 参数 (sx·a, sy·b, sx·c, sy·d, sx·tx, sy·ty)
    octx.setTransform(sx * m.a, sy * m.b, sx * m.c, sy * m.d, sx * m.tx, sy * m.ty)
    octx.drawImage(base, 0, 0)
    pixels[currentIdx] = out
    const c = ctx2d()
    const canvas = canvasRef.value
    if (c && canvas) {
      c.setTransform(1, 0, 0, 1, 0, 0)
      c.clearRect(0, 0, canvas.width, canvas.height)
      c.drawImage(out, 0, 0)
      applyBackingTransform()
    }
    updateThumb(currentIdx, out)
    markDirty()
  }

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
    // 快照即显示真源：丢弃浮动/选区保持一致（浮动像素已含在快照里）
    floatCanvas = null
    setFloatActive(false)
    setSelection(null)
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
    floatCanvas = null
    setFloatActive(false)
    setSelection(null)
    syncHistoryFlags()
  }

  function clear() {
    const c = ctx2d()
    if (!c) return
    bakeFloatIfAny()
    pushHistory()
    // 逻辑坐标系下清整板（transform 已缩放到物理像素）
    c.clearRect(0, 0, store.artboardWidth, store.artboardHeight)
    markDirty()
  }

  // ─── 自由笔画（画笔/橡皮）───

  function beginFreeStroke(point: { x: number; y: number }) {
    const c = ctx2d()
    if (!c) return
    bakeFloatIfAny()
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
    bakeFloatIfAny()
    const base = snapshot()
    if (!base) return
    pushHistory()
    activeOp = 'shape'
    strokeStart = point
    baseSnapshot = base
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
    octx.drawImage(canvas, 0, 0) // DOM 含浮动合成 → flush 即烘焙
    updateThumb(currentIdx, off)
    // flush 会把浮动选区烘焙进离屏：随后清掉浮动与选区（换帧/保存/裁切统一语义）
    floatCanvas = null
    setFloatActive(false)
    setSelection(null)
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

    // 整体替换：丢弃旧浮动/选区（剪贴板保留，可跨帧粘贴）
    floatCanvas = null
    setFloatActive(false)
    setSelection(null)

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

  /**
   * 模式转换烘焙回写（vector→bitmap 单向烘焙，PaintArtboard 编排调用）：
   * 用「位图⊕矢量合成后」的画布整体替换全部帧像素——与 loadFrames 不同，
   * 保留帧 meta/帧名（不重建 store.frames，矢量 histMap 与帧 id 的关联不失效）；
   * 清空全部撤销栈（烘焙不可逆，对齐 Scratch 转换语义），重绘 DOM 与逐帧缩略图。
   */
  function replacePixelsForBake(canvases: HTMLCanvasElement[]) {
    pixels = canvases.map((c) => {
      const off = makeOffscreen(c.width, c.height)
      off.getContext('2d')!.drawImage(c, 0, 0)
      return off
    })
    // 浮动选区/框选跨模式无意义（切模式瞬间必为空，防御性清理）
    floatCanvas = null
    setFloatActive(false)
    setSelection(null)
    histMap.clear()
    undoStack = []
    redoStack = []
    syncHistoryFlags()
    if (currentIdx >= 0 && currentIdx < pixels.length) rerenderComposite()
    pixels.forEach((pc, i) => {
      if (pc) updateThumb(i, pc)
    })
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
    bakeFloatIfAny()
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

  // ─── 位图选区操作（浮动选区 = 中心/缩放/旋转变换模型）───

  function cloneCanvas(src: HTMLCanvasElement): HTMLCanvasElement {
    const c = makeOffscreen(src.width, src.height)
    c.getContext('2d')!.drawImage(src, 0, 0)
    return c
  }

  function setSelection(r: { x: number; y: number; w: number; h: number } | null) {
    store.selection = r
  }

  function setFloatActive(b: boolean) {
    store.floatActive = b
    if (!b) store.transformBox = null
  }

  /**
   * 同步变换框几何到 store（SVG overlay 渲染用）。
   * 关键约束：变换框 UI 只存在于 SVG 层，绝不画进真源画布——
   * 否则烘焙/保存会把框线像素烙进图像（历史 bug）。
   */
  function syncTransformBox() {
    if (!floatCanvas || !store.floatActive) {
      store.transformBox = null
      return
    }
    const cs = floatCorners()
    if (cs.length !== 4) {
      store.transformBox = null
      return
    }
    const topMid = { x: (cs[0].x + cs[1].x) / 2, y: (cs[0].y + cs[1].y) / 2 }
    let nx = topMid.x - floatXf.cx
    let ny = topMid.y - floatXf.cy
    const nl = Math.hypot(nx, ny) || 1
    nx /= nl
    ny /= nl
    // 旋转柄：顶边中点沿外法线，外偏移按 1/zoom 屏幕恒定约 14px
    const rotOff = 14 / Math.max(0.1, store.zoom)
    store.transformBox = {
      corners: cs,
      handles: [
        cs[0], cs[1], cs[2], cs[3],
        { x: (cs[0].x + cs[1].x) / 2, y: (cs[0].y + cs[1].y) / 2 },
        { x: (cs[1].x + cs[2].x) / 2, y: (cs[1].y + cs[2].y) / 2 },
        { x: (cs[2].x + cs[3].x) / 2, y: (cs[2].y + cs[3].y) / 2 },
        { x: (cs[3].x + cs[0].x) / 2, y: (cs[3].y + cs[0].y) / 2 },
      ],
      rotateTop: topMid,
      rotateAt: { x: topMid.x + nx * rotOff, y: topMid.y + ny * rotOff },
    }
  }

  /** 两点 → 归一化并夹取到画板内的整数矩形 */
  function normRect(ax: number, ay: number, bx: number, by: number) {
    const x0 = Math.min(ax, bx)
    const y0 = Math.min(ay, by)
    const x1 = Math.max(ax, bx)
    const y1 = Math.max(ay, by)
    const W = store.artboardWidth
    const H = store.artboardHeight
    const x = Math.max(0, Math.min(W, Math.floor(x0)))
    const y = Math.max(0, Math.min(H, Math.floor(y0)))
    const w = Math.max(0, Math.min(W, Math.ceil(x1)) - x)
    const h = Math.max(0, Math.min(H, Math.ceil(y1)) - y)
    return { x, y, w, h }
  }

  /** 浮动选区四个世界角点（局部 ±半尺寸 经 旋转+平移）：TL TR BR BL */
  function floatCorners(): { x: number; y: number }[] {
    if (!floatCanvas) return []
    const hw = (floatCanvas.width * floatXf.sx) / 2
    const hh = (floatCanvas.height * floatXf.sy) / 2
    const cos = Math.cos(floatXf.angle)
    const sin = Math.sin(floatXf.angle)
    const locals = [
      { x: -hw, y: -hh },
      { x: hw, y: -hh },
      { x: hw, y: hh },
      { x: -hw, y: hh },
    ]
    return locals.map(l => ({
      x: floatXf.cx + l.x * cos - l.y * sin,
      y: floatXf.cy + l.x * sin + l.y * cos,
    }))
  }

  /** 浮动选区 AABB（复制/删除/蚂蚁线按钮用） */
  function floatAabb(): { x: number; y: number; w: number; h: number } | null {
    const cs = floatCorners()
    if (cs.length === 0) return null
    const xs = cs.map(c => c.x)
    const ys = cs.map(c => c.y)
    const x = Math.round(Math.min(...xs))
    const y = Math.round(Math.min(...ys))
    return {
      x,
      y,
      w: Math.round(Math.max(...xs)) - x,
      h: Math.round(Math.max(...ys)) - y,
    }
  }

  /** 点在四边形内（射线法） */
  function inPolygon(p: { x: number; y: number }, poly: { x: number; y: number }[]): boolean {
    let inside = false
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const a = poly[i]
      const b = poly[j]
      if ((a.y > p.y) !== (b.y > p.y) &&
          p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x) {
        inside = !inside
      }
    }
    return inside
  }

  /**
   * DOM canvas 是显示真源（committed + 浮动合成）。
   * commit：把 DOM 整体烘焙为新的 committed 离屏并清掉浮动（视觉不变），
   * 并立即重绘——否则变换框/手柄会残留在画布上（点空白、粘贴替换等场景）。
   */
  function commitFloatNow() {
    const canvas = canvasRef.value
    if (!canvas) return
    pixels[currentIdx] = cloneCanvas(canvas)
    floatCanvas = null
    setFloatActive(false)
    rerenderComposite()
  }

  /** 仅在存在浮动时烘焙（绘制类工具下笔前调用，避免浮动像素漏进笔画层） */
  function bakeFloatIfAny() {
    if (floatCanvas) commitFloatNow()
  }

  /** 以当前变换绘制浮动选区到指定 ctx（逻辑坐标系） */
  function renderFloat(c: CanvasRenderingContext2D) {
    if (!floatCanvas) return
    c.save()
    c.translate(floatXf.cx, floatXf.cy)
    c.rotate(floatXf.angle)
    c.scale(floatXf.sx, floatXf.sy)
    c.drawImage(floatCanvas, -floatCanvas.width / 2, -floatCanvas.height / 2)
    c.restore()
  }

  /** 手柄命中检测：rotate > 缩放角/边 > 框内(move) > outside */
  function hitTestFloat(p: { x: number; y: number }): 'rotate' | 'scale' | 'move' | 'outside' {
    if (!floatCanvas) return 'outside'
    const z = Math.max(0.1, store.zoom)
    const cs = floatCorners()
    if (cs.length !== 4) return 'outside'

    // 旋转柄
    const topMid = { x: (cs[0].x + cs[1].x) / 2, y: (cs[0].y + cs[1].y) / 2 }
    let nx = topMid.x - floatXf.cx
    let ny = topMid.y - floatXf.cy
    const nl = Math.hypot(nx, ny) || 1
    nx /= nl
    ny /= nl
    const rot = { x: topMid.x + nx * (14 / z), y: topMid.y + ny * (14 / z) }
    if (Math.hypot(p.x - rot.x, p.y - rot.y) <= Math.max(6, 8 / z)) return 'rotate'

    // 缩放手柄（角+边中点），命中区放大一倍
    const hs = Math.max(4, 10 / z)
    const handlePts = [
      cs[0], cs[1], cs[2], cs[3],
      { x: (cs[0].x + cs[1].x) / 2, y: (cs[0].y + cs[1].y) / 2 },
      { x: (cs[1].x + cs[2].x) / 2, y: (cs[1].y + cs[2].y) / 2 },
      { x: (cs[2].x + cs[3].x) / 2, y: (cs[2].y + cs[3].y) / 2 },
      { x: (cs[3].x + cs[0].x) / 2, y: (cs[3].y + cs[0].y) / 2 },
    ]
    for (const hp of handlePts) {
      if (Math.abs(p.x - hp.x) <= hs / 2 && Math.abs(p.y - hp.y) <= hs / 2) return 'scale'
    }

    if (inPolygon(p, cs)) return 'move'
    return 'outside'
  }

  /** scale down 配置表：局部手柄方向（TL TR BR BL T B L R 顺序） */
  function scaleHandleInfo(p: { x: number; y: number }) {
    if (!floatCanvas) return null
    const z = Math.max(0.1, store.zoom)
    const hs = Math.max(4, 10 / z)
    const cs = floatCorners()
    // 半尺寸取绝对值：翻转（负缩放）状态下手柄/锚点定义仍按视觉尺寸
    const hw = Math.abs((floatCanvas.width * floatXf.sx) / 2)
    const hh = Math.abs((floatCanvas.height * floatXf.sy) / 2)
    // [局部手柄位置, 方向, 启用轴, 局部锚点]
    const defs: Array<{
      world: { x: number; y: number }
      dir: { x: number; y: number }
      axes: { x: boolean; y: boolean }
      aLocal: { x: number; y: number }
    }> = [
      { world: cs[0], dir: { x: -1, y: -1 }, axes: { x: true, y: true }, aLocal: { x: hw, y: hh } },
      { world: cs[1], dir: { x: 1, y: -1 }, axes: { x: true, y: true }, aLocal: { x: -hw, y: hh } },
      { world: cs[2], dir: { x: 1, y: 1 }, axes: { x: true, y: true }, aLocal: { x: -hw, y: -hh } },
      { world: cs[3], dir: { x: -1, y: 1 }, axes: { x: true, y: true }, aLocal: { x: hw, y: -hh } },
      { world: { x: (cs[0].x + cs[1].x) / 2, y: (cs[0].y + cs[1].y) / 2 }, dir: { x: 0, y: -1 }, axes: { x: false, y: true }, aLocal: { x: 0, y: hh } },
      { world: { x: (cs[2].x + cs[3].x) / 2, y: (cs[2].y + cs[3].y) / 2 }, dir: { x: 0, y: 1 }, axes: { x: false, y: true }, aLocal: { x: 0, y: -hh } },
      { world: { x: (cs[0].x + cs[3].x) / 2, y: (cs[0].y + cs[3].y) / 2 }, dir: { x: -1, y: 0 }, axes: { x: true, y: false }, aLocal: { x: hw, y: 0 } },
      { world: { x: (cs[1].x + cs[2].x) / 2, y: (cs[1].y + cs[2].y) / 2 }, dir: { x: 1, y: 0 }, axes: { x: true, y: false }, aLocal: { x: -hw, y: 0 } },
    ]
    // 边手柄 L/R 与角共用世界点，命中时优先按更小手柄判定——按 defs 顺序首个命中即可（角优先）
    for (const d of defs) {
      if (Math.abs(p.x - d.world.x) <= hs / 2 && Math.abs(p.y - d.world.y) <= hs / 2) return d
    }
    return null
  }

  /** 重绘显示：committed 离屏 + 浮动合成；变换框几何同步给 SVG overlay（不碰画布像素） */
  function rerenderComposite() {
    const c = ctx2d()
    const canvas = canvasRef.value
    if (!c || !canvas) return
    c.setTransform(1, 0, 0, 1, 0, 0)
    c.clearRect(0, 0, canvas.width, canvas.height)
    const base = currentIdx >= 0 && currentIdx < pixels.length ? pixels[currentIdx] : null
    if (base) c.drawImage(base, 0, 0)
    renderFloat(c)
    applyBackingTransform()
    syncTransformBox()
  }

  /** 选区像素切除为浮动选区并立即进入变换框状态（PS cut 语义 + Scratch 即时变换框） */
  function cutSelectionToFloat() {
    const canvas = canvasRef.value
    const r = store.selection
    if (!canvas || !r || r.w <= 0 || r.h <= 0) return
    const snap = cloneCanvas(canvas)
    const fc = makeOffscreen(r.w, r.h)
    fc.getContext('2d')!.drawImage(snap, r.x, r.y, r.w, r.h, 0, 0, r.w, r.h)
    snap.getContext('2d')!.clearRect(r.x, r.y, r.w, r.h)
    pixels[currentIdx] = snap
    floatCanvas = fc
    floatXf = { cx: r.x + r.w / 2, cy: r.y + r.h / 2, sx: 1, sy: 1, angle: 0 }
    setFloatActive(true)
    const aabb = floatAabb()
    if (aabb) setSelection(aabb)
    rerenderComposite()
  }

  function startSelectionOp(point: { x: number; y: number }) {
    // 有浮动选区：手柄命中优先
    if (floatCanvas && store.floatActive) {
      const hit = hitTestFloat(point)
      opStartXf = { ...floatXf }
      if (hit === 'rotate') {
        selOp = 'rotate'
        return
      }
      if (hit === 'scale') {
        const info = scaleHandleInfo(point)
        if (info && floatCanvas) {
          selOp = 'scale'
          scaleDir = info.dir
          scaleAxes = info.axes
          // 半尺寸取绝对值（翻转态下再次缩放时比例计算稳定）
          scaleOrigHalf = {
            x: Math.abs((floatCanvas.width * floatXf.sx) / 2),
            y: Math.abs((floatCanvas.height * floatXf.sy) / 2),
          }
          // 锚点世界坐标 + 初始指针局部坐标（相对锚点、去旋转）
          const cos = Math.cos(floatXf.angle)
          const sin = Math.sin(floatXf.angle)
          scaleAnchorW = {
            x: floatXf.cx + info.aLocal.x * cos - info.aLocal.y * sin,
            y: floatXf.cy + info.aLocal.x * sin + info.aLocal.y * cos,
          }
          const dx = point.x - scaleAnchorW.x
          const dy = point.y - scaleAnchorW.y
          scaleP0Local = { x: dx * cos + dy * sin, y: -dx * sin + dy * cos }
        }
        return
      }
      if (hit === 'move') {
        selOp = 'move'
        floatGrab = { x: point.x - floatXf.cx, y: point.y - floatXf.cy }
        return
      }
      // 框外：烘焙浮动 → 开始新框选
      pushHistory()
      commitFloatNow()
      setSelection(null)
      selOp = 'create'
      selAnchor = point
      return
    }

    // 无浮动：开始新框选
    setSelection(null)
    selOp = 'create'
    selAnchor = point
  }

  function continueSelectionOp(point: { x: number; y: number }, shift: boolean) {
    if (selOp === 'create') {
      setSelection(normRect(selAnchor.x, selAnchor.y, point.x, point.y))
      return
    }
    if (!floatCanvas || !opStartXf) return

    if (selOp === 'move') {
      floatXf.cx = point.x - floatGrab.x
      floatXf.cy = point.y - floatGrab.y
      rerenderComposite()
      return
    }

    if (selOp === 'rotate') {
      let angle = Math.atan2(point.y - floatXf.cy, point.x - floatXf.cx) + Math.PI / 2
      // Shift 吸附 15°
      if (shift) {
        const step = Math.PI / 12
        angle = Math.round(angle / step) * step
      }
      floatXf.angle = angle
      rerenderComposite()
      return
    }

    if (selOp === 'scale') {
      const cos = Math.cos(opStartXf.angle)
      const sin = Math.sin(opStartXf.angle)
      const dx = point.x - scaleAnchorW.x
      const dy = point.y - scaleAnchorW.y
      const p1Local = { x: dx * cos + dy * sin, y: -dx * sin + dy * cos }
      const dL = { x: p1Local.x - scaleP0Local.x, y: p1Local.y - scaleP0Local.y }

      // 锚定缩放（PS/Scratch 行为）：对侧边固定不动——
      // 中心移动 Δ/2，半尺寸增加 Δ·dir/2（此前半尺寸误用整段 Δ，导致对边与手柄错位漂移）
      const ratioX = (scaleOrigHalf.x + (dL.x * scaleDir.x) / 2) / scaleOrigHalf.x
      const ratioY = (scaleOrigHalf.y + (dL.y * scaleDir.y) / 2) / scaleOrigHalf.y
      const signedScale = (absBase: number, ratio: number) => {
        const raw = absBase * ratio
        return (raw < 0 ? -1 : 1) * Math.max(0.02, Math.abs(raw))
      }

      if (shift) {
        // Shift 等比缩放：角手柄取变化大的轴为主，边手柄以该轴为主，两轴同比例；
        // 中心 = 锚点 + down 时中心相对向量 × 比例（锚点固定，任意旋转角下都成立）
        const r = scaleAxes.x && scaleAxes.y
          ? (Math.abs(ratioX) > Math.abs(ratioY) ? ratioX : ratioY)
          : (scaleAxes.x ? ratioX : ratioY)
        floatXf.sx = signedScale(Math.abs(opStartXf.sx), r)
        floatXf.sy = signedScale(Math.abs(opStartXf.sy), r)
        const relX = opStartXf.cx - scaleAnchorW.x
        const relY = opStartXf.cy - scaleAnchorW.y
        floatXf.cx = scaleAnchorW.x + relX * r
        floatXf.cy = scaleAnchorW.y + relY * r
      } else {
        if (scaleAxes.x) {
          floatXf.sx = signedScale(Math.abs(opStartXf.sx), ratioX)
        }
        if (scaleAxes.y) {
          floatXf.sy = signedScale(Math.abs(opStartXf.sy), ratioY)
        }
        // 中心随锚点对称移动：Δ/2（局部）→ 世界
        const cdx = scaleAxes.x ? dL.x / 2 : 0
        const cdy = scaleAxes.y ? dL.y / 2 : 0
        floatXf.cx = opStartXf.cx + cdx * cos - cdy * sin
        floatXf.cy = opStartXf.cy + cdx * sin + cdy * cos
      }
      rerenderComposite()
    }
  }

  function endSelectionOp(point: { x: number; y: number }) {
    if (selOp === 'create') {
      const r = normRect(selAnchor.x, selAnchor.y, point.x, point.y)
      if (r.w < 2 || r.h < 2) {
        // 点击空白：取消选区
        setSelection(null)
      } else {
        // 框选完成 → 立即切成浮动选区并进入变换框状态（对齐 Scratch：建选即可动/转/缩）
        setSelection(r)
        cutSelectionToFloat()
      }
    } else if (selOp === 'move' || selOp === 'scale' || selOp === 'rotate') {
      // 变换结束：同步 AABB 给按钮/蚂蚁线；有实际变化则标记脏
      const aabb = floatAabb()
      if (aabb) setSelection(aabb)
      if (opStartXf && (
        Math.abs(opStartXf.cx - floatXf.cx) > 0.01 ||
        Math.abs(opStartXf.cy - floatXf.cy) > 0.01 ||
        Math.abs(opStartXf.sx - floatXf.sx) > 0.0001 ||
        Math.abs(opStartXf.sy - floatXf.sy) > 0.0001 ||
        Math.abs(opStartXf.angle - floatXf.angle) > 0.0001
      )) {
        markDirty()
      }
      opStartXf = null
    }
    selOp = 'none'
  }

  /** 复制选区到剪贴板（含浮动合成） */
  function copySelection() {
    const r = store.selection
    const canvas = canvasRef.value
    if (!canvas || !r || r.w <= 0 || r.h <= 0) return
    const cb = makeOffscreen(r.w, r.h)
    cb.getContext('2d')!.drawImage(canvas, r.x, r.y, r.w, r.h, 0, 0, r.w, r.h)
    clipboardCanvas = cb
    clipboardOrigin = { x: r.x, y: r.y }
    store.hasClipboard = true
  }

  /** 粘贴剪贴板为新浮动选区（带 16px 位移便于辨识；越界时反向/回退） */
  function pasteClipboard() {
    if (!clipboardCanvas || !canvasRef.value) return
    pushHistory()
    commitFloatNow()
    floatCanvas = cloneCanvas(clipboardCanvas)

    // 位移策略：优先 (+16,+16)，越界换 (−16,−16)，再越界回原位
    const off = 16
    const W = store.artboardWidth
    const H = store.artboardHeight
    let ox = clipboardOrigin.x + off
    let oy = clipboardOrigin.y + off
    if (ox + floatCanvas.width > W) ox = clipboardOrigin.x - off
    if (oy + floatCanvas.height > H) oy = clipboardOrigin.y - off
    ox = Math.max(-floatCanvas.width + 1, Math.min(W - 1, ox))
    oy = Math.max(-floatCanvas.height + 1, Math.min(H - 1, oy))

    floatXf = {
      cx: ox + floatCanvas.width / 2,
      cy: oy + floatCanvas.height / 2,
      sx: 1,
      sy: 1,
      angle: 0,
    }
    setFloatActive(true)
    const aabb = floatAabb()
    if (aabb) setSelection(aabb)
    rerenderComposite()
    markDirty()
  }

  /** 删除选区内容（有浮动先烘焙再清）；保留蚂蚁线 */
  function deleteSelection() {
    const r = store.selection
    if (!r || r.w <= 0 || r.h <= 0) return
    pushHistory()
    commitFloatNow()
    pixels[currentIdx]?.getContext('2d')!.clearRect(r.x, r.y, r.w, r.h)
    rerenderComposite()
    markDirty()
  }

  /** 镜像翻转：有选区翻转选区内容，无选区翻转整帧 */
  function flipSelection(dir: 'h' | 'v') {
    const canvas = canvasRef.value
    if (!canvas) return
    pushHistory()
    commitFloatNow()
    const base = pixels[currentIdx]
    if (!base) return
    const r = store.selection ?? { x: 0, y: 0, w: base.width, h: base.height }
    if (r.w <= 0 || r.h <= 0) return
    const region = makeOffscreen(r.w, r.h)
    region.getContext('2d')!.drawImage(base, r.x, r.y, r.w, r.h, 0, 0, r.w, r.h)
    const bctx = base.getContext('2d')!
    bctx.clearRect(r.x, r.y, r.w, r.h)
    bctx.save()
    if (dir === 'h') {
      bctx.translate(r.x + r.w, r.y)
      bctx.scale(-1, 1)
    } else {
      bctx.translate(r.x, r.y + r.h)
      bctx.scale(1, -1)
    }
    bctx.drawImage(region, 0, 0)
    bctx.restore()
    rerenderComposite()
    markDirty()
  }

  /** Esc / 离开选择工具：烘焙浮动并收起选区 */
  function commitAndDeselect() {
    if (floatCanvas) {
      pushHistory()
      commitFloatNow()
    }
    setSelection(null)
  }

  // ─── 指针事件路由 ───

  function onPointerDown(e: PointerEvent) {
    if (e.button !== 0 || store.mode !== 'bitmap') return
    const canvas = canvasRef.value
    if (!canvas) return
    e.preventDefault()

    const point = clientToArtboard(e)
    if (store.activeTool === 'select') {
      startSelectionOp(point)
    } else if (FREE_TOOLS.has(store.activeTool)) {
      beginFreeStroke(point)
    } else if (SHAPE_TOOLS.has(store.activeTool)) {
      beginShape(point)
    } else if (store.activeTool === 'fill') {
      doFill(point)
    } else {
      // reshape / text / eyedropper：后续阶段实现
      return
    }
    canvas.setPointerCapture(e.pointerId)
  }

  function onPointerMove(e: PointerEvent) {
    if (selOp !== 'none') {
      continueSelectionOp(clientToArtboard(e), e.shiftKey)
      return
    }
    if (activeOp === 'none') return
    const point = clientToArtboard(e)
    if (activeOp === 'free') {
      continueFreeStroke(point)
    } else {
      continueShape(point, e.shiftKey)
    }
  }

  function onPointerUp(e: PointerEvent) {
    if (selOp !== 'none') {
      endSelectionOp(clientToArtboard(e))
      return
    }
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

  watch(() => [store.activeTool, store.brushSize, store.zoom], () => {
    updateCursor()
    // 缩放变化 → 变换框手柄按 1/zoom 反比重绘（保持屏幕恒定大小）
    if (store.floatActive && floatCanvas) rerenderComposite()
  }, { immediate: true })

  // 离开选择工具：烘焙浮动并收起选区（位图绘制不按选区约束，蚂蚁线留着无意义）
  watch(() => store.activeTool, (tool, oldTool) => {
    if (oldTool === 'select' && tool !== 'select') {
      commitAndDeselect()
    }
  })

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
    replacePixelsForBake,
    transformWholeFrame,
    getFrameCanvases,
    getFrameNames,
    copySelection,
    pasteClipboard,
    deleteSelection,
    flipSelection,
    commitAndDeselect,
    getCanvas: () => canvasRef.value ?? null,
  }
}
