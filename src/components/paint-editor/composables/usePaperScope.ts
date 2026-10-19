import { watch, onBeforeUnmount, type Ref } from 'vue'
import paper from 'paper'
import { usePaintStore } from '../../../stores/paint'
import { rgbaCss } from '../utils/artboardExport'

/** 矢量撤销栈上限（exportJSON 快照，与位图 25 步对齐） */
const HISTORY_LIMIT = 25

/**
 * 矢量绘制引擎（paper 接入）。
 *
 * 架构约束：
 * - PaperScope / paper.Item 等对象全部闭包持有，绝不进 Vue 深层响应式（proxy 会破坏 paper 内部）。
 * - **Scratch 同款渲染架构**：矢量 canvas 固定铺满舞台（不进 artboard 的 CSS transform 管道），
 *   缩放/平移走 paper view.matrix——每次变化按屏幕像素重新栅格化几何，背面固定 = 舞台×dpr（有界）。
 *   反面教训：画布被 CSS transform 拉伸会经合成器任意重采样，分数缩放/平移下不可恢复地发糊；
 *   加大背面只能缓解（仍经合成器）。固定背面 + 矩阵缩放开销极低，Scratch 在低配机器流畅即此方案。
 * - 不使用 paper 自带 Tool/DOM 事件：自绑 pointer 事件 + clientToArtboard（用位图画布 rect 实测
 *   除法，与位图引擎同一坐标源），逻辑坐标喂给 paper API；view.matrix 只影响渲染不影响工具坐标。
 * - 多帧：每帧 project.exportJSON() 快照存 frameJson[]，切换时导出旧帧/导入新帧；
 *   另存 frameRaster[]（project.draw 逻辑坐标直绘的栅格）供保存与缩略图合成（与 view 状态无关）。
 * - 选中高亮不走 paper.item.selected（会被渲染进 canvas、随保存烙印）——
 *   自绘 SVG 包围盒（store.vectorSelBox），与位图变换框同一 overlay 思路。
 */
export function usePaperScope(
  canvasRef: Ref<HTMLCanvasElement | undefined>,
  /** 位图画布：坐标换算基准（位于 artboard 内、随 CSS transform 变换，与位图引擎同源） */
  coordRef: Ref<HTMLCanvasElement | undefined>,
  /** 帧操作钩子（由 PaintArtboard 注入，保持两引擎帧数组对齐；缩略图合成也在画板层用双 canvas 完成） */
  hooks: {
    /** 帧切换完成（旧帧已导出）后刷新缩略图合成 */
    onFrameSwitched: (oldIndex: number, newIndex: number) => void
    /** 矢量内容变更后刷新当前帧缩略图 */
    onContentChanged: () => void
    /**
     * 位图代理（Scratch 同款：矢量场景底层 image 对象）的位图层真源接口。
     * 代理只存在于矢量模式；其变换在手势/翻转结束时经 transformFrame 烘回位图像素。
     */
    bitmapLayer: {
      /** 当前帧位图源（DOM canvas 显示真源） */
      getFrame: () => HTMLCanvasElement | null
      /** 把代理的累计仿射烘进位图像素（内部压位图撤销栈+重绘+缩略图） */
      transformFrame: (m: { a: number; b: number; c: number; d: number; tx: number; ty: number }) => void
      /** 清空当前帧位图像素（矢量模式 Delete 命中代理时，对齐 Scratch 删 image） */
      clearFrame: () => void
    }
  }
) {
  const store = usePaintStore()

  let scope: paper.PaperScope | null = null

  // ─── 多帧矢量状态（与 store.frames 下标对齐）───  /** 每帧 project JSON 快照；null = 该帧无矢量内容 */
  let frameJson: (string | null)[] = [null]
  /** 每帧矢量层位图快照（保存/缩略图合成用）；活动帧实时取 canvas */
  let frameRaster: (HTMLCanvasElement | null)[] = [null]
  let currentIdx = 0
  /** 每帧撤销栈（按帧 id 存放，切帧交换——与位图 histMap 同模式） */
  const histMap = new Map<string, { undo: string[]; redo: string[] }>()
  let undoStack: string[] = []
  let redoStack: string[] = []

  // ─── 交互状态（闭包）───
  type SelOp = 'none' | 'create' | 'move' | 'marquee' | 'scale' | 'rotate'
  let selOp: SelOp = 'none'
  /** 当前选中对象（顶层 item） */
  const selected = new Set<paper.Item>()
  let marqueeAnchor = { x: 0, y: 0 }
  /** move：按下点相对选区 union 中心的偏移；记录位移前快照供无操作回滚 */
  let opSnapshot: string | null = null
  let opMoved = false
  let lastPointer = { x: 0, y: 0 }

  /**
   * 选中变换框（选中会话内持久，对齐位图浮动选区模型）：
   * 定向矩形 {中心, 半宽高, 角度}——选中建立时由内容 AABB 重置（angle=0），
   * move 平移中心、rotate 只改角度、scale 改半尺寸+中心，撤销/清选/换选才丢弃。
   * 与 store.vectorSelBox 分工：本结构是几何真源，store 只存渲染所需投影
   * （corners/handles/rotate 柄）。
   */
  interface SelFrame {
    cx: number
    cy: number
    hw: number
    hh: number
    angle: number
  }
  let selFrame: SelFrame | null = null
  /** scale 手势起始态（down 捕获；move 每次从起始态绝对计算，防增量漂移） */
  let scaleStart: {
    f: SelFrame
    dir: { x: number; y: number }
    axes: { x: boolean; y: boolean }
    anchor: { x: number; y: number }
    p0Local: { x: number; y: number }
    /** 上一事件的累计比例（增量变换：W_n···W_1 ≡ 绝对量，A/θ 全程不变） */
    sx: number
    sy: number
  } | null = null
  /** rotate 手势起始态（绝对角度制：target 每次由起始角全量推导，Shift 吸附稳定） */
  let rotateStart: {
    angle0: number
    center: { x: number; y: number }
    a0: number
    /** 已施加到内容的角度增量（target − angle0） */
    applied: number
  } | null = null

  // 形状/画笔进行态
  let activePath: paper.Path | null = null
  let strokeStart: { x: number; y: number } | null = null

  /** 矢量剪贴板（选中项的 detached 克隆，画板会话内有效；不进 store） */
  let clipboardItems: paper.Item[] = []

  // ─── 位图代理（Scratch 同款 <image>：位图层在矢量场景中的可选中/可变换对象）───
  /** 场景底层的位图 Raster；null = 位图模式或未同步 */
  let bitmapRaster: paper.Raster | null = null
  /** 构造定位基线 matrix（position=(w/2,h/2) 会写进 matrix，烘入像素时须扣除） */
  let bitmapRasterBase: paper.Matrix | null = null

  function isBitmapRaster(item: paper.Item | null | undefined): boolean {
    return !!item && item === bitmapRaster
  }

  /**
   * 位图内容包围盒（非透明像素 bbox，画板逻辑坐标）：代理 Raster 是整帧画布，
   * 直接用其 bounds 选框会撑满画板——选框须贴合实际内容（空内容返回 null）。
   * 扫描 DOM canvas（显示真源，1 逻辑像素 = 1 物理像素），仅在选中建立/烘入后调用。
   */
  function bitmapContentBounds(): paper.Rectangle | null {
    const src = hooks.bitmapLayer.getFrame()
    if (!src || src.width === 0 || src.height === 0) return null
    const ctx = src.getContext('2d')
    if (!ctx) return null
    const w = src.width
    const h = src.height
    const data = ctx.getImageData(0, 0, w, h).data
    let minX = w
    let minY = h
    let maxX = -1
    let maxY = -1
    for (let y = 0; y < h; y++) {
      const row = y * w
      for (let x = 0; x < w; x++) {
        if (data[(row + x) * 4 + 3] > 8) {
          if (x < minX) minX = x
          if (x > maxX) maxX = x
          if (y < minY) minY = y
          if (y > maxY) maxY = y
        }
      }
    }
    if (maxX < 0) return null // 全透明
    const sx = src.width / store.artboardWidth || 1
    const sy = src.height / store.artboardHeight || 1
    return new scope!.Rectangle(
      minX / sx,
      minY / sy,
      (maxX - minX + 1) / sx,
      (maxY - minY + 1) / sy
    )
  }

  /** 摘除位图代理（对象丢弃，下次 sync 重建） */
  function removeBitmapRaster() {
    if (bitmapRaster) {
      bitmapRaster.remove()
      bitmapRaster = null
      bitmapRasterBase = null
      scope?.view.update() // 同步重绘（模式切换同帧交接，防一帧空窗/重影）
    }
  }

  /**
   * 同步位图代理：矢量模式下把当前帧位图作为底层 image 放进场景（重建式）。
   * - Raster 默认中心在原点（_getBounds setCenter(0,0)），position 定位到画板左上；
   * - imageSmoothing=false：位图观感恒定像素块（对齐位图层 canvas-pixelated）；
   * - insertChild(0) 恒压场景底层（矢量对象叠画其上，hitTest 顶层优先）。
   */
  function syncBitmapRaster() {
    if (!scope) return
    removeBitmapRaster()
    if (store.mode !== 'vector') return
    const src = hooks.bitmapLayer.getFrame()
    if (!src || src.width === 0 || src.height === 0) return
    const r = new scope.Raster(src)
    r.smoothing = 'off' // 最近邻渲染：位图观感恒定像素块（对齐位图层 canvas-pixelated）
    r.position = new scope.Point(src.width / 2, src.height / 2)
    scope.project.activeLayer?.insertChild(0, r)
    bitmapRaster = r
    bitmapRasterBase = r.matrix.clone()
    scope.view.update() // 同步重绘代理（模式切换同帧交接，位图 canvas 随后隐藏无空窗）
  }

  /** restoreFrom（undo/redo）后把代理插回场景：历史快照不含代理，保留对象与其变换 */
  function reattachBitmapRaster() {
    if (bitmapRaster && !bitmapRaster.parent && store.mode === 'vector') {
      activeLayer()?.insertChild(0, bitmapRaster)
    }
  }

  /**
   * 导出/绘制时临时摘除位图代理：它不是矢量真源，不进撤销快照/帧槽 JSON/缩略图/保存合成
   * （否则位图像素被 base64 进快照、保存时两层重复叠加）。嵌套调用幂等。
   */
  function withRasterDetached<T>(fn: () => T): T {
    const r = bitmapRaster
    const wasAttached = !!r && !!r.parent
    if (wasAttached) r!.remove()
    try {
      return fn()
    } finally {
      if (wasAttached && r && !r.parent) activeLayer()?.insertChild(0, r)
    }
  }

  /** 手势/翻转用快照（等价 exportJSON，自动排除代理） */
  function snapshotForGesture(): string {
    return withRasterDetached(() => scope!.project.exportJSON())
  }

  /**
   * 把位图代理的累计变换烘进位图像素并重建代理（Scratch：image 变换即落到 costume，
   * 切模式/切帧不会丢）。相对矩阵 = 当前 matrix × 基线逆（基线是构造定位，不在像素内容里；
   * 手势/翻转均为 prepend，m = W·base → rel = W ✓）。烘后保持代理选中态。
   */
  function bakeRasterIfTransformed() {
    const r = bitmapRaster
    if (!r || !bitmapRasterBase || !r.parent) return
    const rel = r.matrix.appended(bitmapRasterBase.inverted())
    if (rel.isIdentity()) return
    const v = rel.values
    hooks.bitmapLayer.transformFrame({ a: v[0], b: v[1], c: v[2], d: v[3], tx: v[4], ty: v[5] })
    const wasSelected = selected.has(r)
    selected.delete(r)
    syncBitmapRaster() // 从烘后像素重建（新基线），换对象
    if (wasSelected && bitmapRaster) {
      selected.add(bitmapRaster)
      resetSelFrame() // 框按烘后内容 bbox 重算（代理 bounds 是整帧，不可沿用旧框）
    }
    syncVectorSelBox()
    hooks.onContentChanged()
  }

  /** 屏幕坐标 → 画板逻辑坐标（用位图画布 rect 实测除法：其位于 artboard transform 内，恒准） */
  function clientToArtboard(e: { clientX: number; clientY: number }) {
    const el = coordRef.value ?? canvasRef.value!
    const rect = el.getBoundingClientRect()
    return {
      x: ((e.clientX - rect.left) / rect.width) * store.artboardWidth,
      y: ((e.clientY - rect.top) / rect.height) * store.artboardHeight,
    }
  }

  // ─── 历史（exportJSON 快照）───

  function syncHistoryFlags() {
    store.vectorCanUndo = undoStack.length > 0
    store.vectorCanRedo = redoStack.length > 0
  }

  /** 变更前压栈（exportJSON 快照，摘除位图代理）；redo 分支统一清空 */
  function pushHistory() {
    if (!scope) return
    undoStack.push(snapshotForGesture())
    if (undoStack.length > HISTORY_LIMIT) undoStack.shift()
    redoStack = []
    syncHistoryFlags()
  }

  /** 零操作回滚（down 压栈后未产生实际变化） */
  function popHistory() {
    undoStack.pop()
    syncHistoryFlags()
  }

  function restoreFrom(json: string) {
    if (!scope) return
    scope.project.clear() // 代理随之脱离（对象引用保留在 bitmapRaster）
    scope.project.importJSON(json) // 历史快照本身不含代理
    // clear 后无层，importJSON 重建；确保 activeLayer 指向可用层
    if (scope.project.layers.length === 0) {
      new scope.Layer()
    }
    scope.project.activeLayer?.activate()
    reattachBitmapRaster()
    scope.view.update()
    clearSelection()
    syncVectorContentFlag()
  }

  function undo() {
    if (undoStack.length === 0) return
    const cur = snapshotForGesture()
    const json = undoStack.pop()!
    redoStack.push(cur)
    restoreFrom(json)
    syncHistoryFlags()
    hooks.onContentChanged()
  }

  function redo() {
    if (redoStack.length === 0) return
    const cur = snapshotForGesture()
    const json = redoStack.pop()!
    undoStack.push(cur)
    restoreFrom(json)
    syncHistoryFlags()
    hooks.onContentChanged()
  }

  // ─── 选中管理 ───

  /** 定向框四角（局部 ±半尺寸 经 旋转+平移）：TL TR BR BL（与位图 floatCorners 同构） */
  function frameCorners(f: SelFrame): { x: number; y: number }[] {
    const c = Math.cos(f.angle)
    const s = Math.sin(f.angle)
    const locals: [number, number][] = [
      [-f.hw, -f.hh],
      [f.hw, -f.hh],
      [f.hw, f.hh],
      [-f.hw, f.hh],
    ]
    return locals.map(([lx, ly]) => ({
      x: f.cx + lx * c - ly * s,
      y: f.cy + lx * s + ly * c,
    }))
  }

  /** 由选中内容 AABB 重建变换框（新选中：轴对齐、angle=0）；半尺寸下限 0.5 保证手柄可命中。
   *  矢量用 strokeBounds（含描边外扩，笔画不露框）；位图代理用内容包围盒
   *  （代理是整帧画布，bounds 会撑满画板） */
  function resetSelFrame() {
    if (selected.size === 0) {
      selFrame = null
      return
    }
    let minX = Infinity
    let minY = Infinity
    let maxX = -Infinity
    let maxY = -Infinity
    let any = false
    for (const item of selected) {
      let b: paper.Rectangle
      if (isBitmapRaster(item)) {
        const cb = bitmapContentBounds()
        if (!cb) continue // 全透明内容不贡献框
        b = cb
      } else {
        b = item.strokeBounds
      }
      any = true
      minX = Math.min(minX, b.left)
      minY = Math.min(minY, b.top)
      maxX = Math.max(maxX, b.right)
      maxY = Math.max(maxY, b.bottom)
    }
    if (!any) {
      selFrame = null
      return
    }
    selFrame = {
      cx: (minX + maxX) / 2,
      cy: (minY + maxY) / 2,
      hw: Math.max((maxX - minX) / 2, 0.5),
      hh: Math.max((maxY - minY) / 2, 0.5),
      angle: 0,
    }
  }

  function syncVectorSelBox() {
    if (selected.size === 0) {
      selFrame = null
      store.vectorSelBox = null
      store.vectorSelectedCount = 0
      return
    }
    if (!selFrame) resetSelFrame()
    const f = selFrame!
    const cs = frameCorners(f)
    const topMid = { x: (cs[0].x + cs[1].x) / 2, y: (cs[0].y + cs[1].y) / 2 }
    const nx = topMid.x - f.cx
    const ny = topMid.y - f.cy
    const nl = Math.hypot(nx, ny) || 1
    // 旋转柄：顶边中点沿外法线，外偏移按 1/zoom 屏幕恒定约 14px（与位图一致）
    const rotOff = 14 / Math.max(0.1, store.zoom)
    store.vectorSelBox = {
      corners: cs,
      handles: [
        cs[0], cs[1], cs[2], cs[3],
        { x: (cs[0].x + cs[1].x) / 2, y: (cs[0].y + cs[1].y) / 2 },
        { x: (cs[1].x + cs[2].x) / 2, y: (cs[1].y + cs[2].y) / 2 },
        { x: (cs[2].x + cs[3].x) / 2, y: (cs[2].y + cs[3].y) / 2 },
        { x: (cs[3].x + cs[0].x) / 2, y: (cs[3].y + cs[0].y) / 2 },
      ],
      rotateTop: topMid,
      rotateAt: { x: topMid.x + (nx / nl) * rotOff, y: topMid.y + (ny / nl) * rotOff },
    }
    store.vectorSelectedCount = selected.size
  }

  function clearSelection() {
    selected.clear()
    syncVectorSelBox()
  }

  /** 沿 parent 上溯到活动层直接子级（Group 整体选中，对齐 Scratch 对象语义） */
  function topLevelOf(item: paper.Item): paper.Item {
    let cur = item
    while (cur.parent && cur.parent !== scope!.project.activeLayer) {
      cur = cur.parent
    }
    return cur
  }

  function setSelection(items: paper.Item[]) {
    clearSelection()
    for (const it of items) selected.add(it)
    syncVectorSelBox()
  }

  // ─── 内容标记（保存锁尺寸/裁切禁用）───

  function syncVectorContentFlag() {
    if (!scope) return
    // 位图代理不算矢量内容（否则矢量模式一开就永久禁裁切/保存重复叠加）
    const layer = scope.project.activeLayer
    const live = layer ? layer.children.some((c) => c !== bitmapRaster) : false
    store.vectorContent = live || frameJson.some((j) => j !== null)
  }

  function markDirty() {
    store.dirty = true
    syncVectorContentFlag()
    hooks.onContentChanged()
  }

  // ─── 栅格快照（保存/缩略图合成）───

  /** 有界像素比：背面上限约 8MP，防大舞台/大画板内存爆炸（常规机型 dpr 恒不触顶） */
  function clampedPixelRatio(area: number): number {
    const dpr = window.devicePixelRatio || 1
    return Math.max(1, Math.min(dpr, Math.sqrt(8e6 / Math.max(1, area))))
  }

  /**
   * 把当前 project 以逻辑坐标直绘到离屏画布（尺寸 = 逻辑 × rr）。
   * 不经 view（缩放/平移无关）——保存、缩略图、帧栅格缓存全部由此产出。
   * Project.draw 是 CanvasView.update 的渲染入口（paper 0.12.18 源码核实，d.ts 未收录）：
   * 先 ctx.save + 应用传入矩阵，children 在当前 ctx 基础 transform 下绘制——
   * 调用前置 ctx 基础为 scale(rr)，传 identity 矩阵即得 逻辑×rr 内容。
   */
  function drawProjectToRaster(): HTMLCanvasElement | null {
    if (!scope) return null
    const layer = scope.project.activeLayer
    const live = layer ? layer.children.some((c) => c !== bitmapRaster) : false
    if (!live) return null
    return withRasterDetached(() => {
      const w = store.artboardWidth
      const h = store.artboardHeight
      const rr = clampedPixelRatio(w * h)
      const c = document.createElement('canvas')
      c.width = Math.round(w * rr)
      c.height = Math.round(h * rr)
      const ctx = c.getContext('2d')!
      ctx.setTransform(rr, 0, 0, rr, 0, 0)
      const proj = scope!.project as unknown as {
        draw: (ctx: CanvasRenderingContext2D, m: paper.Matrix, pr: number) => void
      }
      proj.draw(ctx, new scope!.Matrix(), rr)
      return c
    })
  }

  /**
   * 取第 i 帧矢量层位图（保存/缩略图合成用）。
   * 活动帧即时直绘 project；非活动帧用切换时缓存的 raster。
   */
  function getFrameRaster(i: number): HTMLCanvasElement | null {
    if (i === currentIdx) return drawProjectToRaster()
    return frameRaster[i]
  }

  /** 任意帧存在矢量内容（供保存合成决定是否叠加） */
  function hasVectorContent(): boolean {
    return store.vectorContent
  }

  // ─── 帧同步（由 PaintArtboard 在帧操作前后显式调用 + activeFrameIndex watcher 兜底）───

  /** 导出活动帧到槽位（离开当前帧/保存前调用） */
  function exportActiveFrame() {
    if (!scope || currentIdx < 0 || currentIdx >= frameJson.length) return
    const layer = scope.project.activeLayer
    const live = layer ? layer.children.some((c) => c !== bitmapRaster) : false
    frameJson[currentIdx] = live ? snapshotForGesture() : null
    frameRaster[currentIdx] = live ? drawProjectToRaster() : null
  }

  /** 导入目标帧内容到 project（进入新帧后调用） */
  function importFrame(index: number) {
    if (!scope) return
    scope.project.clear()
    const json = frameJson[index]
    if (json) {
      scope.project.importJSON(json)
      if (scope.project.layers.length === 0) new scope.Layer()
      scope.project.activeLayer?.activate()
    }
    scope.view.update()
    currentIdx = index
    clearSelection()
    syncBitmapRaster() // 换帧重建位图代理（新帧位图；位图引擎 watcher 先行，DOM 已切好）
    // 撤销栈换柜
    const meta = store.frames[index]
    if (meta) {
      const h = histMap.get(meta.id)
      undoStack = h?.undo ?? []
      redoStack = h?.redo ?? []
    } else {
      undoStack = []
      redoStack = []
    }
    syncHistoryFlags()
    syncVectorContentFlag()
  }

  function syncActiveFrame() {
    const target = store.activeFrameIndex
    if (target === currentIdx && currentIdx >= 0) return
    const old = currentIdx
    exportActiveFrame()
    // 历史入柜
    const oldMeta = old >= 0 ? store.frames[old] : undefined
    if (oldMeta) histMap.set(oldMeta.id, { undo: undoStack, redo: redoStack })
    importFrame(target)
    hooks.onFrameSwitched(old, target)
  }

  watch(() => store.activeFrameIndex, () => syncActiveFrame())

  /** 帧数组增删同步（由 PaintArtboard 编排，须与位图像素数组保持下标对齐） */
  function onFrameAdded(duplicate: boolean, newIndex: number) {
    // 复制帧前先固化活动帧（用户可能刚画了矢量内容，槽位是旧快照）
    exportActiveFrame()
    const src = duplicate ? frameJson[currentIdx] : null
    const rasterSrc = duplicate ? frameRaster[currentIdx] : null
    frameJson.splice(newIndex, 0, src)
    frameRaster.splice(newIndex, 0, rasterSrc)
  }

  function onFrameRemoved(index: number) {
    frameJson.splice(index, 1)
    frameRaster.splice(index, 1)
    const meta = store.frames[index]
    if (meta) histMap.delete(meta.id)
    if (index === currentIdx) {
      currentIdx = -1 // 失效，强制 syncActiveFrame 重载
    } else if (index < currentIdx) {
      currentIdx--
    }
  }

  /** 整体载入（编辑既有角色）：既有帧均为纯位图，矢量槽全部清空 */
  function onLoadFrames(count: number) {
    frameJson = Array.from({ length: count }, () => null)
    frameRaster = Array.from({ length: count }, () => null)
    histMap.clear()
    undoStack = []
    redoStack = []
    currentIdx = -1
    if (scope) {
      scope.project.clear()
      if (scope.project.layers.length === 0) new scope.Layer()
      scope.project.activeLayer?.activate()
      scope.view.update()
    }
    syncHistoryFlags()
    syncVectorContentFlag()
    importFrame(store.activeFrameIndex)
  }

  /** 保存前固化活动帧槽位（export 不改 project；栅格直绘 project，与 view 状态无关） */
  function beforeExport() {
    exportActiveFrame()
    syncVectorContentFlag()
  }

  /**
   * 模式转换烘焙清空（vector→bitmap 编排在 PaintArtboard 调用）：
   * 全部帧矢量槽置空、清场景与两套撤销栈——转换单向不可逆（对齐 Scratch：
   * 旧素材保持位图、切回矢量不自动恢复）。槽位数组只清内容不改长度，
   * 持续与位图帧下标对齐；之后仍可在矢量模式追加新矢量内容（双层显示）。
   */
  function clearAllForBake() {
    if (!scope) return
    clearSelection()
    removeBitmapRaster() // 防御：正常由 mode watch 先行摘除
    scope.project.clear()
    if (scope.project.layers.length === 0) new scope.Layer()
    scope.project.activeLayer?.activate()
    scope.view.update()
    frameJson = frameJson.map(() => null)
    frameRaster = frameRaster.map(() => null)
    histMap.clear()
    undoStack = []
    redoStack = []
    syncHistoryFlags()
    syncVectorContentFlag()
  }

  // ─── 工具操作 ───

  function activeLayer(): paper.Layer | null {
    return scope?.project.activeLayer ?? null
  }

  function styleColor(): paper.Color {
    return new scope!.Color(rgbaCss(store.fillColor, store.opacity))
  }

  /** 形状的填充/描边开关语义（与位图 drawShapePreview 一致：两者全关回退填充保可见） */
  function shapeStyle(item: paper.Path, isLine: boolean) {
    const fillOn = !isLine && (store.fillEnabled || !store.strokeEnabled)
    const strokeOn = isLine || store.strokeEnabled
    if (fillOn) item.fillColor = styleColor()
    else item.fillColor = null as unknown as paper.Color
    if (strokeOn) {
      item.strokeColor = styleColor()
      item.strokeWidth = store.strokeWidth
      item.strokeJoin = 'round'
      item.strokeCap = 'round'
    } else {
      item.strokeColor = null as unknown as paper.Color
    }
  }

  /** Shift 约束：直线 45° 步进、矩形/椭圆正形（与位图引擎同规则） */
  function constrain(p: { x: number; y: number }, shift: boolean): { x: number; y: number } {
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
    const s = Math.max(Math.abs(dx), Math.abs(dy))
    return {
      x: strokeStart.x + (dx < 0 ? -s : s),
      y: strokeStart.y + (dy < 0 ? -s : s),
    }
  }

  function beginBrush(p: { x: number; y: number }) {
    pushHistory()
    const path = new scope!.Path()
    path.strokeColor = styleColor()
    path.strokeWidth = store.brushSize
    path.strokeCap = 'round'
    path.strokeJoin = 'round'
    path.fillColor = null as unknown as paper.Color
    path.add(new scope!.Point(p.x, p.y))
    activePath = path
    strokeStart = p
  }

  function continueBrush(p: { x: number; y: number }) {
    if (!activePath) return
    // 节流：位移过小不加点
    const last = activePath.lastSegment?.point
    if (last && Math.hypot(p.x - last.x, p.y - last.y) < 0.5) return
    activePath.add(new scope!.Point(p.x, p.y))
  }

  function endBrush() {
    if (!activePath) return
    if (activePath.segments.length === 1) {
      // 单击落点：加 0.01 偏移保证 round cap 渲染出圆点
      const pt = activePath.firstSegment!.point
      activePath.add(new scope!.Point(pt.x + 0.01, pt.y + 0.01))
    } else if (activePath.segments.length > 2) {
      activePath.smooth()
    }
    activePath = null
    strokeStart = null
    markDirty()
  }

  function beginShape(p: { x: number; y: number }, shift: boolean) {
    pushHistory()
    strokeStart = p
    const start = constrain(p, shift)
    if (store.activeTool === 'line') {
      const path = new scope!.Path([
        new scope!.Segment(new scope!.Point(start.x, start.y)),
        new scope!.Segment(new scope!.Point(start.x, start.y)),
      ])
      shapeStyle(path, true)
      activePath = path
    } else {
      rebuildShape(start, start)
    }
  }

  /** 矢量橡皮筋：每帧移除旧 preview 重建（教学场景规模下开销可忽略） */
  let shapePreview: paper.Path | null = null

  function rebuildShape(from: { x: number; y: number }, to: { x: number; y: number }) {
    shapePreview?.remove()
    const S = scope!
    let path: paper.Path
    if (store.activeTool === 'rect') {
      path = new S.Path.Rectangle(new S.Point(from.x, from.y), new S.Point(to.x, to.y))
    } else {
      path = new S.Path.Ellipse(new S.Rectangle(from.x, from.y, to.x - from.x, to.y - from.y))
    }
    shapeStyle(path, false)
    shapePreview = path
  }

  function continueShape(p: { x: number; y: number }, shift: boolean) {
    if (!strokeStart) return
    const end = constrain(p, shift)
    if (store.activeTool === 'line' && activePath) {
      activePath.lastSegment!.point = new scope!.Point(end.x, end.y)
    } else {
      rebuildShape(strokeStart, end)
    }
  }

  function endShape(p: { x: number; y: number }, shift: boolean) {
    const end = constrain(p, shift)
    const isClick =
      !strokeStart || (Math.abs(end.x - strokeStart.x) < 0.5 && Math.abs(end.y - strokeStart.y) < 0.5)
    if (store.activeTool === 'line') {
      if (isClick) {
        activePath?.remove()
        activePath = null
        popHistory()
      } else {
        activePath = null
        markDirty()
      }
    } else {
      // rebuildShape 已在 continue 中生成终态；零尺寸则丢弃
      if (isClick) {
        shapePreview?.remove()
        shapePreview = null
        popHistory()
      } else {
        shapePreview = null
        markDirty()
      }
    }
    strokeStart = null
  }

  function doFill(p: { x: number; y: number }) {
    if (!scope) return
    const hit = scope.project.hitTest(new scope.Point(p.x, p.y), {
      fill: true,
      stroke: true,
      tolerance: 2,
    })
    if (!hit) return
    // 位图代理不接受矢量填充（位图换色在位图模式用填充工具）
    if (isBitmapRaster(hit.item)) return
    pushHistory()
    const color = styleColor()
    if (hit.type === 'stroke') {
      hit.item.strokeColor = color
    } else {
      hit.item.fillColor = color
    }
    markDirty()
  }

  /** 橡皮手势状态：首次命中才压栈（未命中不产生空撤销步）；拖过整段只记一步、结束统一刷缩略图 */
  let erasePushed = false
  let eraseChanged = false

  function eraseAt(p: { x: number; y: number }) {
    if (!scope) return
    const r = Math.max(2, store.brushSize / 2)
    const hit = scope.project.hitTest(new scope.Point(p.x, p.y), {
      fill: true,
      stroke: true,
      segments: true,
      tolerance: r,
    })
    if (!hit) return
    // 矢量橡皮不擦位图层（位图橡皮在位图模式）
    if (isBitmapRaster(hit.item)) return
    if (!erasePushed) {
      pushHistory()
      erasePushed = true
    }
    const item = topLevelOf(hit.item)
    // 填充闭合路径：布尔差集局部擦除；开放笔画/组：整对象移除（保底，避免布尔把开放路径闭合化）
    if (item instanceof scope.Path && item.closed && item.hasFill()) {
      try {
        const circle = new scope.Path.Circle(new scope.Point(p.x, p.y), r)
        const result = item.subtract(circle)
        circle.remove()
        if (result && !result.isEmpty()) {
          result.insertBelow(item)
          item.remove()
        } else {
          item.remove()
        }
      } catch {
        item.remove()
      }
    } else {
      item.remove()
    }
    clearSelection()
    eraseChanged = true
  }

  // ─── select 工具（变换框手柄：移动/缩放/旋转，对齐位图浮动选区模型）───

  /** 共轭缩放线性部分：L = R(θ)·diag(sx,sy)·R(-θ)（对称矩阵） */
  function scaleLinear(theta: number, sx: number, sy: number) {
    const c = Math.cos(theta)
    const s = Math.sin(theta)
    return {
      a: sx * c * c + sy * s * s,
      b: (sx - sy) * s * c,
      d: sx * s * s + sy * c * c,
    }
  }

  /**
   * 世界坐标缩放矩阵：绕 anchor 把 θ 方向的局部轴缩放 (sx,sy)——
   * W = T(A)·R(θ)·S·R(-θ)·T(-A)。选中项恒为活动层直接子级（层矩阵恒等），
   * item.transform 是世界坐标 prepend（paper 源码 _matrix.prepend 核实），语义恒成立。
   */
  function worldScaleMatrix(
    anchor: { x: number; y: number },
    theta: number,
    sx: number,
    sy: number
  ): paper.Matrix {
    const L = scaleLinear(theta, sx, sy)
    const tx = anchor.x - (L.a * anchor.x + L.b * anchor.y)
    const ty = anchor.y - (L.b * anchor.x + L.d * anchor.y)
    return new scope!.Matrix(L.a, L.b, L.b, L.d, tx, ty)
  }

  /** 点在四边形内（射线法，与位图 inPolygon 同款） */
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
   * 缩放描边线宽：几何 transform 不改 strokeWidth（数值恒定），不同步则缩小后
   * 恒宽描边露出框外、放大后框相对内容偏大。非均匀缩放取面积均值 √|sx·sy|
   * （canvas strokeWidth 为标量，均匀缩放精确、非均匀 1px 级近似）。
   */
  function scaleStrokeWidths(item: paper.Item, f: number) {
    if (!(f > 0) || Math.abs(f - 1) < 1e-6) return
    if (item.children && item.children.length > 0) {
      for (const c of item.children) scaleStrokeWidths(c, f)
      return
    }
    if (item.strokeColor) {
      item.strokeWidth = Math.max(0.01, item.strokeWidth * f)
    }
  }

  type ScaleDef = {
    dir: { x: number; y: number }
    axes: { x: boolean; y: boolean }
  }

  /** 缩放手柄定义（TL TR BR BL T B L R，与位图 scaleHandleInfo 同表）：局部方向与启用轴 */
  function scaleHandleDefs(): Array<ScaleDef & { world: { x: number; y: number } }> {
    const f = selFrame
    if (!f) return []
    const cs = frameCorners(f)
    return [
      { world: cs[0], dir: { x: -1, y: -1 }, axes: { x: true, y: true } },
      { world: cs[1], dir: { x: 1, y: -1 }, axes: { x: true, y: true } },
      { world: cs[2], dir: { x: 1, y: 1 }, axes: { x: true, y: true } },
      { world: cs[3], dir: { x: -1, y: 1 }, axes: { x: true, y: true } },
      { world: { x: (cs[0].x + cs[1].x) / 2, y: (cs[0].y + cs[1].y) / 2 }, dir: { x: 0, y: -1 }, axes: { x: false, y: true } },
      { world: { x: (cs[2].x + cs[3].x) / 2, y: (cs[2].y + cs[3].y) / 2 }, dir: { x: 0, y: 1 }, axes: { x: false, y: true } },
      { world: { x: (cs[0].x + cs[3].x) / 2, y: (cs[0].y + cs[3].y) / 2 }, dir: { x: -1, y: 0 }, axes: { x: true, y: false } },
      { world: { x: (cs[1].x + cs[2].x) / 2, y: (cs[1].y + cs[2].y) / 2 }, dir: { x: 1, y: 0 }, axes: { x: true, y: false } },
    ]
  }

  /**
   * 变换框手柄命中（优先级与位图 hitTestFloat 一致）：
   * rotate > 缩放角/边手柄 > 框内(move) > outside。
   * 旋转柄命中宽容化：圆点命中区加大，且「顶边中点→圆点」的连线线段也可命中
   * （实际操作常按在连线上，仅圆点可中会表现为"旋转无效"——按下即落到 outside 清选区）。
   */
  function hitTestFrame(
    p: { x: number; y: number }
  ): { kind: 'rotate' } | { kind: 'scale'; def: ScaleDef & { world: { x: number; y: number } } } | { kind: 'move' } | { kind: 'outside' } {
    if (!selFrame) return { kind: 'outside' }
    const z = Math.max(0.1, store.zoom)
    const cs = frameCorners(selFrame)

    // 旋转柄：圆点 + 连接线段（点到线段距离）
    const topMid = { x: (cs[0].x + cs[1].x) / 2, y: (cs[0].y + cs[1].y) / 2 }
    const nxl = Math.hypot(topMid.x - selFrame.cx, topMid.y - selFrame.cy) || 1
    const rotOff = 14 / z
    const rot = {
      x: topMid.x + ((topMid.x - selFrame.cx) / nxl) * rotOff,
      y: topMid.y + ((topMid.y - selFrame.cy) / nxl) * rotOff,
    }
    if (Math.hypot(p.x - rot.x, p.y - rot.y) <= Math.max(12, 18 / z)) return { kind: 'rotate' }
    // 连线线段命中（topMid → rot）
    {
      const ax = rot.x - topMid.x
      const ay = rot.y - topMid.y
      const len2 = ax * ax + ay * ay
      const t = len2 > 0 ? Math.max(0, Math.min(1, ((p.x - topMid.x) * ax + (p.y - topMid.y) * ay) / len2)) : 0
      const dx = p.x - (topMid.x + ax * t)
      const dy = p.y - (topMid.y + ay * t)
      if (Math.hypot(dx, dy) <= Math.max(6, 10 / z)) return { kind: 'rotate' }
    }

    // 缩放手柄（角+边中点），命中区按屏幕恒定
    const hs = Math.max(4, 10 / z)
    for (const def of scaleHandleDefs()) {
      if (Math.abs(p.x - def.world.x) <= hs / 2 && Math.abs(p.y - def.world.y) <= hs / 2) {
        return { kind: 'scale', def }
      }
    }

    if (inPolygon(p, cs)) return { kind: 'move' }
    return { kind: 'outside' }
  }

  /** 开始移动手势（框内拖动 / 命中内容拖动共用）：压栈快照供零操作回滚 */
  function startMove(p: { x: number; y: number }) {
    selOp = 'move'
    opSnapshot = snapshotForGesture()
    opMoved = false
    lastPointer = p
  }

  function beginSelect(p: { x: number; y: number }, shift: boolean) {
    if (!scope) return

    // 变换框手柄优先（旋转 > 缩放 > 框内移动），随后才是内容命中与框选
    if (selected.size > 0 && selFrame) {
      const hit = hitTestFrame(p)
      if (hit.kind === 'rotate') {
        opSnapshot = snapshotForGesture()
        opMoved = false
        rotateStart = {
          angle0: selFrame.angle,
          center: { x: selFrame.cx, y: selFrame.cy },
          a0: Math.atan2(p.y - selFrame.cy, p.x - selFrame.cx),
          applied: 0,
        }
        selOp = 'rotate'
        return
      }
      if (hit.kind === 'scale') {
        opSnapshot = snapshotForGesture()
        opMoved = false
        const f: SelFrame = { ...selFrame }
        const c = Math.cos(f.angle)
        const s = Math.sin(f.angle)
        // 锚点 = 对侧边/角的局部坐标（与手柄方向相反）→ 世界坐标
        const aLocal = { x: -hit.def.dir.x * f.hw, y: -hit.def.dir.y * f.hh }
        const anchor = {
          x: f.cx + aLocal.x * c - aLocal.y * s,
          y: f.cy + aLocal.x * s + aLocal.y * c,
        }
        const dx = p.x - anchor.x
        const dy = p.y - anchor.y
        scaleStart = {
          f,
          dir: hit.def.dir,
          axes: hit.def.axes,
          anchor,
          p0Local: { x: dx * c + dy * s, y: -dx * s + dy * c },
          sx: 1,
          sy: 1,
        }
        selOp = 'scale'
        return
      }
      if (hit.kind === 'move') {
        startMove(p)
        return
      }
      // 框外：落到下方内容命中/框选（框选会 clearSelection 收起变换框）
    }

    const tol = 4 / Math.max(0.1, store.zoom)
    const rawHit = scope.project.hitTest(new scope.Point(p.x, p.y), {
      fill: true,
      stroke: true,
      segments: true,
      tolerance: tol,
    })
    // 位图代理命中按像素判定：paper 对 Raster 只查 bounds，透明区应视为未命中
    //（落到框选，不误选整帧 image；Scratch 同款——点在图像非透明像素上才选中）
    let hit: paper.HitResult | null = rawHit
    if (
      rawHit &&
      isBitmapRaster(rawHit.item) &&
      rawHit.type === 'pixel' &&
      rawHit.color &&
      rawHit.color.alpha < 0.15
    ) {
      hit = null
    }
    if (hit) {
      const top = topLevelOf(hit.item)
      if (shift) {
        if (selected.has(top)) selected.delete(top)
        else selected.add(top)
        // 多选成员变化：按新集合 AABB 重建变换框（角度归零，框始终贴住内容）
        if (selected.size > 0) resetSelFrame()
      } else if (!selected.has(top)) {
        setSelection([top])
      }
      syncVectorSelBox()
      if (selected.size > 0) startMove(p)
    } else {
      if (!shift) clearSelection()
      selOp = 'marquee'
      marqueeAnchor = p
      store.selection = { x: p.x, y: p.y, w: 0, h: 0 }
      store.floatActive = false // 蚂蚁线 div 走 selection 渲染
    }
  }

  function continueSelect(p: { x: number; y: number }, shift: boolean) {
    if (selOp === 'move') {
      const dx = p.x - lastPointer.x
      const dy = p.y - lastPointer.y
      if (dx !== 0 || dy !== 0) {
        for (const item of selected) item.translate(new scope!.Point(dx, dy))
        if (selFrame) {
          selFrame.cx += dx
          selFrame.cy += dy
        }
        lastPointer = p
        opMoved = true
        syncVectorSelBox()
      }
    } else if (selOp === 'rotate' && rotateStart && selFrame) {
      const rs = rotateStart
      const f = selFrame
      const aCur = Math.atan2(p.y - rs.center.y, p.x - rs.center.x)
      // 绝对角度制：目标角由起始角 + 归一化指针角差推导（绕回不跳变）
      let target = rs.angle0 + Math.atan2(Math.sin(aCur - rs.a0), Math.cos(aCur - rs.a0))
      if (shift) {
        const step = Math.PI / 12
        target = Math.round(target / step) * step
      }
      const appliedNow = target - rs.angle0
      const dApply = appliedNow - rs.applied
      if (dApply !== 0) {
        for (const item of selected) {
          // paper 的 Item.rotate 参数单位是「度」（Matrix.rotate 内部 ×π/180），而本模块
          // 手势数学全部用弧度——必须换算后传入，否则图像只转 1/57、边框（SVG 按弧度画）却在转
          item.rotate((dApply * 180) / Math.PI, new scope!.Point(rs.center.x, rs.center.y))
        }
        rs.applied = appliedNow
        f.angle = target
        syncVectorSelBox()
        opMoved = true
      }
    } else if (selOp === 'scale' && scaleStart && selFrame) {
      const ss = scaleStart
      const f = selFrame
      const f0 = ss.f
      const c = Math.cos(f0.angle)
      const s = Math.sin(f0.angle)
      const dx = p.x - ss.anchor.x
      const dy = p.y - ss.anchor.y
      const pLocal = { x: dx * c + dy * s, y: -dx * s + dy * c }
      const dL = { x: pLocal.x - ss.p0Local.x, y: pLocal.y - ss.p0Local.y }

      // 锚定缩放（对侧边固定不动，PS/Scratch 行为）：新半尺寸 = 起始半尺寸 + 指针局部位移·dir/2
      let newHalfX = ss.axes.x ? f0.hw + (dL.x * ss.dir.x) / 2 : f0.hw
      let newHalfY = ss.axes.y ? f0.hh + (dL.y * ss.dir.y) / 2 : f0.hh
      if (shift) {
        // Shift 等比：角手柄取变化大的轴为主、边手柄以该轴为主，两轴同比例
        const rX = (f0.hw + (dL.x * ss.dir.x) / 2) / f0.hw
        const rY = (f0.hh + (dL.y * ss.dir.y) / 2) / f0.hh
        const r =
          ss.axes.x && ss.axes.y
            ? Math.abs(rX) > Math.abs(rY)
              ? rX
              : rY
            : ss.axes.x
              ? rX
              : rY
        newHalfX = f0.hw * r
        newHalfY = f0.hh * r
      }
      // 穿过对侧边 → 半尺寸变负 = 该轴镜像翻转（对齐位图 signedScale）；
      // 仅钳制 |half| ≥ 0.5 防矩阵退化与除零（0 处取正方向起步）
      const clampHalf = (v: number) => (Math.abs(v) < 0.5 ? (v < 0 ? -0.5 : 0.5) : v)
      newHalfX = clampHalf(newHalfX)
      newHalfY = clampHalf(newHalfY)

      const sx = newHalfX / f0.hw
      const sy = newHalfY / f0.hh
      const incX = sx / ss.sx
      const incY = sy / ss.sy
      if (Math.abs(incX - 1) > 1e-10 || Math.abs(incY - 1) > 1e-10) {
        // 内容增量变换：共轭缩放连乘 ≡ 起始态绝对量（anchor/θ 全程不变）
        const W = worldScaleMatrix(ss.anchor, f0.angle, incX, incY)
        const sAvg = Math.sqrt(Math.abs(incX * incY))
        for (const item of selected) {
          item.transform(W)
          scaleStrokeWidths(item, sAvg) // 描边随缩放同步，否则缩小后恒宽描边露出框外
        }
        ss.sx = sx
        ss.sy = sy
      }

      // 框同步：绝对量从起始态推导（不依赖增量累计，无漂移）
      const L = scaleLinear(f0.angle, sx, sy)
      const vx = f0.cx - ss.anchor.x
      const vy = f0.cy - ss.anchor.y
      f.cx = ss.anchor.x + (L.a * vx + L.b * vy)
      f.cy = ss.anchor.y + (L.b * vx + L.d * vy)
      f.hw = newHalfX
      f.hh = newHalfY
      syncVectorSelBox()
      opMoved = true
    } else if (selOp === 'marquee') {
      store.selection = {
        x: Math.min(marqueeAnchor.x, p.x),
        y: Math.min(marqueeAnchor.y, p.y),
        w: Math.abs(p.x - marqueeAnchor.x),
        h: Math.abs(p.y - marqueeAnchor.y),
      }
    }
  }

  function endSelect() {
    if (selOp === 'move' || selOp === 'scale' || selOp === 'rotate') {
      if (opMoved && opSnapshot) {
        undoStack.push(opSnapshot)
        if (undoStack.length > HISTORY_LIMIT) undoStack.shift()
        redoStack = []
        syncHistoryFlags()
        markDirty()
        // 选中含位图代理时：变换即烘回位图像素（切模式不丢，对齐 Scratch image 落 costume）
        bakeRasterIfTransformed()
      }
      opSnapshot = null
      opMoved = false
      scaleStart = null
      rotateStart = null
    } else if (selOp === 'marquee') {
      const r = store.selection
      store.selection = null
      if (r && r.w >= 2 && r.h >= 2 && scope) {
        const rect = new scope.Rectangle(r.x, r.y, r.w, r.h)
        const layer = activeLayer()
        if (layer) {
          // 框选只圈矢量对象：位图代理是整帧，纳入会让每次框选都撑满全画板
          const hits = layer.children.filter((c) => c !== bitmapRaster && rect.intersects(c.strokeBounds))
          setSelection(hits)
        }
      }
    }
    selOp = 'none'
  }

  // ─── 对象操作（顶栏/快捷键路由进来）───

  function deleteSelection() {
    if (selected.size === 0 || !scope) return
    // 矢量对象删除；位图代理命中 = 清空位图层（对齐 Scratch 删 image 的破坏性语义）
    const hasRaster = Array.from(selected).some((it) => isBitmapRaster(it))
    const targets = Array.from(selected).filter((it) => !isBitmapRaster(it))
    if (targets.length > 0) pushHistory()
    for (const item of targets) item.remove()
    if (hasRaster) {
      hooks.bitmapLayer.clearFrame()
      removeBitmapRaster()
      hooks.onContentChanged()
    }
    clearSelection()
    if (targets.length > 0) markDirty()
  }

  function copySelection() {
    if (selected.size === 0) return
    // 克隆为 detached 副本入剪贴板（排除位图代理：位图层的复制走位图模式选区）
    const targets = Array.from(selected).filter((it) => !isBitmapRaster(it))
    if (targets.length === 0) return
    clipboardItems = targets.map((it) => it.clone({ insert: false }))
    store.hasVectorClipboard = true
  }

  function cutSelection() {
    if (selected.size === 0) return
    copySelection()
    deleteSelection()
  }

  function pasteClipboard() {
    if (clipboardItems.length === 0 || !scope || !activeLayer()) return
    pushHistory()
    const layer = activeLayer()!
    const pasted: paper.Item[] = []
    for (const proto of clipboardItems) {
      const c = proto.clone({ insert: false })
      layer.addChild(c)
      c.translate(new scope.Point(16, 16))
      pasted.push(c)
    }
    setSelection(pasted)
    markDirty()
  }

  function flipSelection(axis: 'h' | 'v') {
    if (!scope) return
    const layer = activeLayer()
    if (!layer) return
    // targets 含位图代理（选中态或无选区的整体翻转）：代理翻转后烘回像素
    const targets = selected.size > 0 ? Array.from(selected) : layer.children.slice()
    if (targets.length === 0) return
    pushHistory()
    // 无选区翻转整体（对齐位图「无选区翻转整帧」语义）：绕画板中心；有选区绕变换框中心
    let cx = store.artboardWidth / 2
    let cy = store.artboardHeight / 2
    if (selected.size > 0 && selFrame) {
      cx = selFrame.cx
      cy = selFrame.cy
    }
    const center = new scope.Point(cx, cy)
    for (const it of targets) {
      if (axis === 'h') it.scale(-1, 1, center)
      else it.scale(1, -1, center)
    }
    // 定向框随内容镜像：中心/半尺寸不变，角度取反（θ → −θ）
    if (selFrame) selFrame.angle = -selFrame.angle
    syncVectorSelBox()
    markDirty()
    bakeRasterIfTransformed() // 代理有翻转则烘入（无代理/恒等时幂等返回）
  }

  function groupSelection() {
    // 组合只组矢量对象（位图代理必须恒在场景底层，进组会破坏结构约定）
    const items = Array.from(selected).filter((it) => !isBitmapRaster(it))
    if (items.length < 2 || !scope || !activeLayer()) return
    pushHistory()
    const group = new scope.Group(items)
    setSelection([group])
    markDirty()
  }

  function ungroupSelection() {
    if (selected.size === 0 || !scope || !activeLayer()) return
    const groups = Array.from(selected).filter((it) => it instanceof scope!.Group)
    if (groups.length === 0) return
    pushHistory()
    const layer = activeLayer()!
    const released: paper.Item[] = []
    for (const g of groups) {
      const index = g.index
      const children = g.removeChildren()
      // 保持层级位置
      children.forEach((c: paper.Item, i: number) => layer.insertChild(index + i, c))
      released.push(...children)
      g.remove()
    }
    setSelection(released)
    markDirty()
  }

  /** 图层上/下移一层（moveAbove/moveBelow = insertAbove/insertBelow 别名） */
  function layerMove(dir: 'up' | 'down') {
    // 位图代理恒在底层，不参与图层调整
    const targets = Array.from(selected).filter((it) => !isBitmapRaster(it))
    if (targets.length === 0 || !scope || !activeLayer()) return
    pushHistory()
    for (const item of targets) {
      const sibs = item.parent!.children
      const i = item.index
      if (dir === 'up' && i < sibs.length - 1) {
        ;(item as unknown as { moveAbove: (o: paper.Item) => void }).moveAbove(sibs[i + 1])
      } else if (dir === 'down' && i > 0) {
        ;(item as unknown as { moveBelow: (o: paper.Item) => void }).moveBelow(sibs[i - 1])
      }
    }
    markDirty()
  }

  function clearLayer() {
    const layer = activeLayer()
    if (!layer) return
    // 清空矢量层（排除位图代理：位图层的清空走位图模式或 Delete 命中代理）
    const targets = layer.children.filter((c) => c !== bitmapRaster)
    if (targets.length === 0) return
    pushHistory()
    for (const c of targets.slice()) c.remove()
    clearSelection()
    syncVectorContentFlag()
    markDirty()
  }

  // ─── 指针事件（自绑，坐标与位图同源）───

  function onPointerDown(e: PointerEvent) {
    if (e.button !== 0 || store.mode !== 'vector' || !scope) return
    const p = clientToArtboard(e)
    canvasRef.value?.setPointerCapture(e.pointerId)
    const tool = store.activeTool

    if (tool === 'brush') {
      beginBrush(p)
    } else if (tool === 'line' || tool === 'rect' || tool === 'ellipse') {
      beginShape(p, e.shiftKey)
    } else if (tool === 'fill') {
      doFill(p)
    } else if (tool === 'eraser') {
      erasePushed = false
      eraseChanged = false
      eraseAt(p)
    } else if (tool === 'select') {
      beginSelect(p, e.shiftKey)
    }
    // reshape / text / eyedropper：占位（Stage 3/4）
  }

  function onPointerMove(e: PointerEvent) {
    if (!scope) return
    if (e.buttons !== 1) return
    const p = clientToArtboard(e)
    const tool = store.activeTool
    if (tool === 'brush') {
      continueBrush(p)
    } else if (tool === 'line' || tool === 'rect' || tool === 'ellipse') {
      continueShape(p, e.shiftKey)
    } else if (tool === 'eraser') {
      eraseAt(p)
    } else if (tool === 'select') {
      continueSelect(p, e.shiftKey)
    }
  }

  function onPointerUp(e: PointerEvent) {
    if (!scope) return
    const p = clientToArtboard(e)
    const tool = store.activeTool
    if (tool === 'brush') {
      endBrush()
    } else if (tool === 'line' || tool === 'rect' || tool === 'ellipse') {
      endShape(p, e.shiftKey)
    } else if (tool === 'select') {
      endSelect()
    } else if (tool === 'eraser') {
      // 手势结束：整段只压了一步栈；有实际擦除才刷脏标与缩略图
      if (eraseChanged) markDirty()
      erasePushed = false
      eraseChanged = false
    }
    selOp = 'none'
  }

  // ─── 光标 ───

  /** 双环圆圈光标（与位图引擎同款，深浅底都可见） */
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
    } else if (
      tool === 'line' ||
      tool === 'rect' ||
      tool === 'ellipse' ||
      tool === 'fill'
    ) {
      canvas.style.cursor = 'crosshair'
    } else {
      canvas.style.cursor = 'default'
    }
  }

  // ─── 生命周期 ───

  /**
   * 同步矢量视口（Scratch 同款架构核心）：
   * - viewSize = 舞台 CSS 尺寸（canvas 铺满舞台、其上无 transform 祖先，rect 即布局尺寸）；
   * - 背面 pr = dpr（面积有界），**与缩放无关**——缩放不改背面尺寸，固定开销；
   * - view.matrix 把 逻辑坐标 映射到舞台像素：S = zoom·P + t，
   *   t 由 舞台中心 + 平移 − 逻辑半宽×zoom 推出（与 artboard 的 flex 居中 + translate/scale 数学等价）；
   * - clip-path 把渲染裁剪到 artboard 视觉盒（否则矢量笔画会溢出画板画到舞台背景上）。
   *
   * paper CanvasView 渲染约定（paper 0.12.18 源码核实）：
   * - CanvasView.update → project.draw(ctx, view.matrix, _pixelRatio)：项目在 ctx 基础
   *   transform = scale(pr) 下绘制，传入的 view.matrix 叠加其上（缩放平移即由此生效）；
   * - 改 _pixelRatio 后必须重调 _setElementSize 重建背面（canvas.width 赋值清空画布），
   *   并归正 ctx 基础 transform 到 scale(pr)（pr===1 时 _setElementSize 跳过 ctx 块，
   *   旧 scale 会残留导致绘制错位），再强制 _needsUpdate + update 同步重绘。
   * 内部字段（版本锁定 0.12.18）走窄类型断言。
   */
  function syncVectorView() {
    if (!scope) return
    const canvas = canvasRef.value
    if (!canvas) return
    const aw = store.artboardWidth
    const ah = store.artboardHeight
    const stageRect = canvas.getBoundingClientRect()
    const sw = stageRect.width
    const sh = stageRect.height
    if (sw <= 0 || sh <= 0) return

    const view = scope.view
    const priv = view as unknown as {
      _pixelRatio: number
      _setElementSize: (w: number, h: number) => void
      _needsUpdate: boolean
    }
    const pr = clampedPixelRatio(sw * sh)

    // 先设 pr：viewSize setter 内部 _setElementSize 会用到
    priv._pixelRatio = pr
    view.viewSize = new scope.Size(sw, sh) // 舞台尺寸变化时更新视口
    priv._setElementSize(sw, sh) // 视口未变但 pr 变了时，仍需重建背面
    // 清掉 paper 写入的内联宽高，交还 CSS width:100%：否则盒子被旧值钉死，
    // 舞台变化后 ResizeObserver 永远不再触发（尺寸失同步死锁）
    canvas.style.width = ''
    canvas.style.height = ''
    const ctx = canvas.getContext('2d')
    if (ctx) ctx.setTransform(pr, 0, 0, pr, 0, 0) // 归正基础 transform（含 pr===1 残留修复）

    // 逻辑 → 舞台：与 artboard「flex 居中 + translate(pan) scale(zoom)（origin center）」等价
    const z = store.zoom
    const tx = sw / 2 + store.panX - (aw * z) / 2
    const ty = sh / 2 + store.panY - (ah * z) / 2
    view.matrix = new scope.Matrix(z, 0, 0, z, tx, ty)

    // 裁剪到 artboard 视觉盒（负偏移钳到 0：画板超出舞台部分本就不可见）
    const art = coordRef.value?.getBoundingClientRect()
    if (art) {
      const left = Math.max(0, art.left - stageRect.left)
      const top = Math.max(0, art.top - stageRect.top)
      const right = Math.max(0, stageRect.right - art.right)
      const bottom = Math.max(0, stageRect.bottom - art.bottom)
      canvas.style.clipPath = `inset(${top}px ${right}px ${bottom}px ${left}px)`
    }

    priv._needsUpdate = true
    view.update() // 背面可能被清空 + 矩阵已变，同步重绘一帧
  }

  /** 舞台尺寸观察（窗口变化）→ 重同步视口 */
  let resizeObserver: ResizeObserver | null = null

  function attach() {
    const canvas = canvasRef.value
    if (!canvas || scope) return
    // 独立 PaperScope 实例：与全局默认 scope 隔离，卸载时 remove() 彻底释放
    scope = new paper.PaperScope()
    scope.setup(canvas) // canvas 铺满舞台且其上无 transform → setup 读到的 rect 即舞台布局尺寸
    if (scope.project.layers.length === 0) new scope.Layer()
    scope.project.activeLayer?.activate()
    syncVectorView()

    canvas.addEventListener('pointerdown', onPointerDown)
    canvas.addEventListener('pointermove', onPointerMove)
    canvas.addEventListener('pointerup', onPointerUp)
    canvas.addEventListener('pointercancel', onPointerUp)
    resizeObserver = new ResizeObserver(() => syncVectorView())
    resizeObserver.observe(canvas)
    updateCursor()
    syncHistoryFlags()
    syncVectorContentFlag()
    syncBitmapRaster() // canvas 就绪后按当前模式补建位图代理（mode watch 只在切换时触发）
  }

  function detach() {
    const canvas = canvasRef.value
    if (canvas) {
      canvas.removeEventListener('pointerdown', onPointerDown)
      canvas.removeEventListener('pointermove', onPointerMove)
      canvas.removeEventListener('pointerup', onPointerUp)
      canvas.removeEventListener('pointercancel', onPointerUp)
      canvas.style.clipPath = ''
    }
    resizeObserver?.disconnect()
    resizeObserver = null
    if (scope) {
      // remove() 清除全部 project/view/tools 并注销 scope（d.ts 未收录，运行时存在）
      ;(scope as unknown as { remove: () => void }).remove()
      scope = null
    }
    selected.clear()
    selFrame = null
    scaleStart = null
    rotateStart = null
    bitmapRaster = null // scope.remove 已销毁场景对象，仅丢引用
    bitmapRasterBase = null
    clipboardItems = []
    frameJson = []
    frameRaster = []
    histMap.clear()
    undoStack = []
    redoStack = []
  }

  watch(canvasRef, (el, old) => {
    if (old) detach()
    if (el) attach()
  }, { immediate: true })

  // 缩放/平移/画板尺寸变化 → 重同步视口（矩阵 + 裁剪；背面固定不随缩放增长）
  watch(
    () => [store.zoom, store.panX, store.panY, store.artboardWidth, store.artboardHeight],
    () => syncVectorView(),
    { flush: 'post' }
  )

  // 缩放变化 → 重算变换框投影（旋转柄外偏移按 1/zoom 换算，屏幕尺寸须恒定）
  watch(
    () => store.zoom,
    () => syncVectorSelBox()
  )

  watch(
    () => [store.activeTool, store.brushSize, store.zoom],
    () => updateCursor()
  )

  // 模式切换：离开矢量收起选中并摘除代理（位图层回到位图模式编辑）；
  // 进入矢量时同步代理（此时位图引擎 mode watch/commit 已先行收口，DOM 即最终像素）
  watch(() => store.mode, (m) => {
    if (m !== 'vector') {
      clearSelection()
      removeBitmapRaster()
    } else {
      syncBitmapRaster()
      syncVectorContentFlag()
    }
  })

  onBeforeUnmount(() => {
    detach()
    store.vectorSelBox = null
    store.vectorSelectedCount = 0
    store.vectorCanUndo = false
    store.vectorCanRedo = false
    store.hasVectorClipboard = false
    store.vectorContent = false
  })

  return {
    undo,
    redo,
    clearLayer,
    deleteSelection,
    copySelection,
    cutSelection,
    pasteClipboard,
    flipSelection,
    groupSelection,
    ungroupSelection,
    layerMove,
    /** 收起选中（Esc 路由；清 selected 与变换框） */
    deselect: clearSelection,
    syncActiveFrame,
    onFrameAdded,
    onFrameRemoved,
    onLoadFrames,
    beforeExport,
    clearAllForBake,
    getFrameRaster,
    hasVectorContent,
    exportActiveFrame,
    /** 矢量剪贴板是否有内容（供顶栏粘贴按钮） */
    hasClipboard: () => clipboardItems.length > 0,
  }
}
