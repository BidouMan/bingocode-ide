import { watch, onBeforeUnmount, type Ref } from 'vue'
import paper from 'paper'
import { usePaintStore } from '../../../stores/paint'
import { rgbaCss } from '../utils/artboardExport'
import { snapRectOffset, type SnapLines } from '../../../utils/smartSnap'
import {
  ensurePaintFont,
  PAINT_FONT_FAMILY,
  PAINT_TEXT_SIZE,
  PAINT_TEXT_LEADING_RATIO,
} from '../utils/paintFont'

/** 矢量撤销栈上限（exportJSON 快照，与位图 25 步对齐） */
const HISTORY_LIMIT = 25

/**
 * 图形（形状）工具集合：创建完成后自动选中新图形并显示变换框，
 * 但**不切换工具**——保持当前工具即可直接操作选框（与位图模式统一）。
 */
const SHAPE_TOOLS = new Set(['line', 'rect', 'ellipse', 'pen'])
const isShapeTool = (tool: string) => SHAPE_TOOLS.has(tool)

/**
 * 可选视口适配器：让矢量引擎脱离角色绘制页的固定居中画板，
 * 挂到任意画布（如地图画布）上。逻辑坐标始终为“绘制画布像素”。
 */
export interface PaperViewportAdapter {
  /** 屏幕坐标 → 逻辑坐标（null 表示无法换算） */
  clientToArtboard: (e: { clientX: number; clientY: number }) => { x: number; y: number } | null
  /** 逻辑坐标 → 画布像素的仿射矩阵（paper.Matrix 的 a~ty） */
  getViewMatrix: (sw: number, sh: number) => {
    a: number
    b: number
    c: number
    d: number
    tx: number
    ty: number
  }
  /** 画布裁剪路径（CSS clip-path），返回 undefined 表示不裁剪 */
  getClipPath: (sw: number, sh: number) => string | undefined
}

export interface PaperScopeOptions {
  /** 自定义视口；不传时保持角色绘制页原有算法 */
  viewport?: PaperViewportAdapter
  /** 单帧模式：跳过角色帧切换/导入导出逻辑（地图图片图层用） */
  singleFrame?: boolean
  /** 是否创建位图代理 Raster；地图侧传 false，避免与 Pixi 底图重影 */
  proxy?: boolean
  /**
   * 智能吸附（画布像素坐标）：返回候选线/网格/阈值；
   * 返回 null 表示当前不吸附（例如吸附开关关闭或图层旋转）。
   */
  smartSnap?: () => { lines: SnapLines; grid: number; threshold: number } | null
}

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
  },
  options: PaperScopeOptions = {}
) {
  const store = usePaintStore()

  /**
   * 本引擎是否在前台可见。
   *
   * 角色绘制页（PaintArtboard）与地图编辑器（MapCanvas）各跑一套本引擎，
   * 页面用 v-show 常驻挂载（切换只用 display:none 隐藏），且共用同一个 paintStore。
   * 隐藏的一方 canvas rect 恒为 0：它不得再改写共享的选中投影（vectorSelBox /
   * vectorSelectedCount / reshape 锚点），否则会把另一方正在编辑的选框清掉
   * （地图编辑器滚轮缩放后选框整体消失即此原因）。
   */
  function isViewVisible(): boolean {
    const el = canvasRef.value
    if (!el || !el.isConnected) return false
    const r = el.getBoundingClientRect()
    return r.width > 0 && r.height > 0
  }

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
    if (options.proxy === false) return
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
    restoreFillPreview() // 悬停预览不得进任何快照（撤销栈/帧槽/导出共用此入口）
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
    if (options.viewport) {
      const mapped = options.viewport.clientToArtboard(e)
      if (mapped) return mapped
    }
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
    penDiscard() // 场景即将重建，进行中的钢笔路径随 project 一起销毁
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
    // 隐藏中的引擎不改写共享选中投影（另一编辑器正持有同一个 store）
    if (!isViewVisible()) return
    // 「取消组合」可用性：选中项里真有 Group 才可点（普通 Path/文字点了也是空操作）
    store.vectorCanUngroup =
      !!scope && Array.from(selected).some((it) => it instanceof scope!.Group)
    // 塑形工具：锚点显示取代变换框（框隐藏，计数照常同步）
    if (store.activeTool === 'reshape') {
      selFrame = null
      store.vectorSelBox = null
      store.vectorSelectedCount = selected.size
      syncStrokeWidthFromSelection() // 选中变化 → 线宽滑条跟随对象实际描边宽
      return
    }
    if (selected.size === 0) {
      selFrame = null
      store.vectorSelBox = null
      store.vectorSelectedCount = 0
      syncStrokeWidthFromSelection() // 清选复位 selectionHasStroke
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
    syncStrokeWidthFromSelection() // 选中变化 → 线宽滑条跟随对象实际描边宽
  }

  function clearSelection() {
    selected.clear()
    reshapeSel.clear() // 锚点选择随对象选择一并清空
    store.reshapePts = null
    store.reshapeOutline = null
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
    syncReshapePts() // 塑形工具下刷新锚点显示（非塑形幂等清空）
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

  /**
   * 以缩略图尺寸把当前 project 直绘到目标画布（不按全分辨率栅格化）。
   * target 画布尺寸即目标像素；返回是否确实存在矢量内容（无内容时不绘制）。
   * 绘制结束后目标画布可再叠加底图，用于合成图层缩略图。
   */
  function drawProjectToThumbnail(target: HTMLCanvasElement): boolean {
    if (!scope) return false
    const layer = scope.project.activeLayer
    const live = layer ? layer.children.some((c) => c !== bitmapRaster) : false
    if (!live) return false
    return withRasterDetached(() => {
      const w = store.artboardWidth
      const h = store.artboardHeight
      if (!w || !h || !target.width || !target.height) return false
      const scale = Math.min(target.width / w, target.height / h)
      const ctx = target.getContext('2d')
      if (!ctx) return false
      ctx.setTransform(scale, 0, 0, scale, 0, 0)
      const proj = scope!.project as unknown as {
        draw: (ctx: CanvasRenderingContext2D, m: paper.Matrix, pr: number) => void
      }
      proj.draw(ctx, new scope!.Matrix(), scale)
      return true
    })
  }

  /** 任意帧存在矢量内容（供保存合成决定是否叠加） */
  function hasVectorContent(): boolean {
    return store.vectorContent
  }

  // ─── 帧同步（由 PaintArtboard 在帧操作前后显式调用 + activeFrameIndex watcher 兜底）───

  /** 导出活动帧到槽位（离开当前帧/保存前调用） */
  function exportActiveFrame() {
    if (!scope || currentIdx < 0 || currentIdx >= frameJson.length) return
    penCancel() // 保存/切帧前不保留进行中的半成品形状
    const layer = scope.project.activeLayer
    const live = layer ? layer.children.some((c) => c !== bitmapRaster) : false
    frameJson[currentIdx] = live ? snapshotForGesture() : null
    frameRaster[currentIdx] = live ? drawProjectToRaster() : null
  }

  /** 导入目标帧内容到 project（进入新帧后调用） */
  function importFrame(index: number) {
    if (!scope) return
    restoreFillPreview() // 换帧清场景前收口悬停态（防引用悬空到已销毁对象）
    penDiscard() // 进行中的钢笔路径不跨帧保留（引用随 project.clear 失效）
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

  if (!options.singleFrame) {
    watch(() => store.activeFrameIndex, () => {
      forceEndTextEdit() // 切帧前收口编辑（编辑态引用不能跨帧）
      syncActiveFrame()
    })
  }

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

  /**
   * 移动帧槽：矢量快照与栅格缓存同步换位。
   * 当前场景内容属于活动帧，只把 currentIdx 同步到新下标，不重新导入场景。
   */
  function moveFrame(from: number, to: number) {
    const count = frameJson.length
    if (from === to || from < 0 || to < 0 || from >= count || to >= count) return
    exportActiveFrame()

    const moveItem = <T,>(arr: T[]) => {
      const [item] = arr.splice(from, 1)
      arr.splice(to, 0, item)
    }
    moveItem(frameJson)
    moveItem(frameRaster)

    const follow = (i: number) => {
      if (i === from) return to
      if (from < to && i > from && i <= to) return i - 1
      if (from > to && i >= to && i < from) return i + 1
      return i
    }
    if (currentIdx >= 0) currentIdx = follow(currentIdx)
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
      penDiscard()
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
    restoreFillPreview()
    penDiscard() // 烘焙前丢弃进行中的钢笔路径（引用随 project.clear 失效）
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
      if (isLine) {
        // 直线=纯描边对象：本体色=绘制色、本体粗细=lineWidth（独立于描边机制，默认 8）
        item.strokeColor = styleColor()
        item.strokeWidth = Math.max(1, store.lineWidth)
      } else {
        // 形状描边：色=描边通道色（UI 色块所见即所画），宽=描边粗细（0=未设→默认 4）
        item.strokeColor = styleStrokeColor()
        item.strokeWidth = store.strokeWidth > 0 ? store.strokeWidth : 4
      }
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

  // ─── 画笔（Scratch segment-brush 同款：带宽度的填充胶囊段逐段 unite）───
  // 笔画本体是填充轮廓而非"中心线+描边"——这是擦除断口形态的根源：
  // stroke 中心线被切开后 round cap 从断口两侧各伸 strokeWidth/2 会把缺口盖住
  //（40px 粗笔画切 12px 口只剩细缝）；填充轮廓走布尔差集，断口=橡皮圆弧切面，
  // 与矩形/圆形擦除观感完全统一。每段 unite 前 flatten 规避 paper 曲线 union
  // 丢块缺陷（paper #1321，Scratch 同款规避手段）。
  /** 进行中的笔画 blob（unite 会替换对象，动态追踪引用） */
  let blobPath: paper.PathItem | null = null
  /** 上一采样点 */
  let blobLast: { x: number; y: number } | null = null
  /** 落笔点（收笔开环 simplify 会扭曲首端——重并落笔原始圆修复，Scratch 同款） */
  let brushStartPt: { x: number; y: number } | null = null

  /** 单个胶囊段：a→b 两端直线 + 两端半圆弧（paper arcTo 原语），flatten+填充后返回 */
  function makeCapsule(
    a: { x: number; y: number },
    b: { x: number; y: number }
  ): paper.Path | null {
    const r = Math.max(1, store.brushSize / 2)
    const dx = b.x - a.x
    const dy = b.y - a.y
    const dd = Math.hypot(dx, dy)
    if (dd < 1e-6) return null
    const ux = dx / dd
    const uy = dy / dd
    const nx = -uy * r
    const ny = ux * r
    const cap = new scope!.Path()
    cap.add(new scope!.Point(a.x + nx, a.y + ny))
    cap.add(new scope!.Point(b.x + nx, b.y + ny))
    cap.arcTo(new scope!.Point(b.x + ux * r, b.y + uy * r), new scope!.Point(b.x - nx, b.y - ny))
    cap.add(new scope!.Point(a.x - nx, a.y - ny))
    cap.arcTo(new scope!.Point(a.x - ux * r, a.y - uy * r), new scope!.Point(a.x + nx, a.y + ny))
    cap.closed = true
    // 帽弧离散精度：弦高 = r/50（R=8→9 点、R=30→13 点半圆，圆润收尾）。
    // 原 min(5, brush/5) 在粗笔刷下半圆只剩 2~3 条弦 → 收笔呈三角尖
    cap.flatten(Math.max(0.2, r / 50))
    cap.fillColor = styleColor()
    cap.strokeColor = null
    return cap
  }

  function beginBrush(p: { x: number; y: number }) {
    pushHistory()
    const dot = new scope!.Path.Circle(
      new scope!.Point(p.x, p.y),
      Math.max(1, store.brushSize / 2)
    )
    dot.fillColor = styleColor()
    dot.strokeColor = null
    blobPath = dot
    blobLast = p
    brushStartPt = { x: p.x, y: p.y }
  }

  function continueBrush(p: { x: number; y: number }) {
    if (!blobPath || !blobLast) return
    const r = Math.max(1, store.brushSize / 2)
    const dx = p.x - blobLast.x
    const dy = p.y - blobLast.y
    const dist = Math.hypot(dx, dy)
    if (dist < 1) return // 过密节流（Scratch minDistance 同意）
    // 细分步长 = 1.5r：相邻胶囊轴向距 1.5r < 2r（帽必相交、侧边重叠 0.5r 无洞），
    // unite 次数比步长 r 少 1/3（对冲高精度帽带来的单次 unite 成本）
    const n = Math.min(Math.ceil(dist / (r * 1.5)), 64)
    let current: paper.PathItem = blobPath
    let from = blobLast
    for (let i = 1; i <= n; i++) {
      const to = { x: blobLast.x + (dx * i) / n, y: blobLast.y + (dy * i) / n }
      const cap = makeCapsule(from, to)
      if (cap) {
        const merged: paper.PathItem | null = current.unite(cap)
        if (merged) {
          cap.remove()
          current.remove()
          current = merged
        } else {
          cap.remove() // union 极端失败：丢这一小段，保留整笔
        }
      }
      from = to
    }
    blobPath = current
    blobLast = p
  }

  function endBrush() {
    if (!blobPath || !scope) return
    const S = scope
    const r = Math.max(1, store.brushSize / 2)
    const capAt = (c: { x: number; y: number }) => {
      const cap = new S.Path.Circle(new S.Point(c.x, c.y), r)
      cap.fillColor = styleColor()
      cap.strokeColor = null
      return cap
    }
    // ── Scratch 收笔三步（SegmentBrushHelper.onSegmentMouseUp 同款）──
    // simplify(2)：删除内部冗余点、把 flatten 密点重拟合为平滑曲线——
    // 实测 222→24 点（-89%），形状偏移 0.69%（<1%，肉眼无感）；
    // 点数大减 = 后续擦除布尔/渲染/撤销快照全链路提速
    if (blobPath instanceof S.Path && blobPath.segments.length > 4) {
      blobPath.closed = false
      blobPath.simplify(2)
      blobPath.closed = true
      // 开环闭合会扭曲首端（Scratch 注释同款）→ 重并落笔原始圆修复
      if (brushStartPt) {
        const cap = capAt(brushStartPt)
        const m = blobPath.unite(cap)
        cap.remove()
        if (m) {
          blobPath.remove()
          blobPath = m
        }
      }
    }
    // 尾端对称：补并尾部原始圆（起笔为纯贝塞尔圆，收笔保持同级圆润）
    if (blobLast) {
      const cap = capAt(blobLast)
      const m = blobPath.unite(cap)
      cap.remove()
      if (m) {
        blobPath.remove()
        blobPath = m
      }
    }
    blobPath = null
    blobLast = null
    brushStartPt = null
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
        const created = activePath
        activePath = null
        markDirty()
        finishShapeSelect(created)
      }
    } else {
      // rebuildShape 已在 continue 中生成终态；零尺寸则丢弃
      if (isClick) {
        shapePreview?.remove()
        shapePreview = null
        popHistory()
      } else {
        const created = shapePreview
        shapePreview = null
        markDirty()
        finishShapeSelect(created)
      }
    }
    strokeStart = null
  }

  /**
   * 图形创建完成 → 激活编辑选框（与位图模式统一）：
   * 选中新图形并显示变换框，但**不切换工具**——当前形状工具下就能直接拖动/缩放/旋转，
   * 点击选框外或换工具才收起选框（收尾逻辑见 beginFrameGesture）。
   */
  function finishShapeSelect(created: paper.Item | null) {
    if (!created) return
    setSelection([created])
  }

  // ─── 自定义形状（钢笔）：逐点落锚，点回首锚/双击/回车闭合 ───
  /**
   * 进行中的钢笔路径：只存已落锚点，场景内不描边不填充（不可见）。
   * 预览线/锚点/收尾高亮全部由 SVG overlay 按固定配色绘制（store.penState）——
   * 既不跟随颜色面板取色，也绝不会被快照/导出/缩略图带走。
   */
  let penPath: paper.Path | null = null
  /** 橡皮筋末端（光标位置，画板逻辑坐标） */
  let penCursor: { x: number; y: number } | null = null

  /** 首锚收尾命中半径（屏幕 10px 恒定 → 逻辑坐标） */
  function penCloseRadius(): number {
    return 10 / Math.max(0.1, store.zoom)
  }

  /** 已落锚点数 */
  function penAnchorCount(): number {
    return penPath ? penPath.segments.length : 0
  }

  /** 同步 overlay 预览状态（落点/移动/收尾都要刷新） */
  function syncPenState() {
    if (!penPath) {
      store.penState = null
      return
    }
    const anchors = penPath.segments.map((s) => ({ x: s.point.x, y: s.point.y }))
    const first = anchors[0]
    const closing =
      anchors.length >= 3 &&
      !!penCursor &&
      Math.hypot(penCursor.x - first.x, penCursor.y - first.y) <= penCloseRadius()
    store.penState = { anchors, cursor: penCursor, closing }
  }

  /** 丢弃进行中的路径（场景即将整体重建：撤销/切帧/载入/烘焙，不回滚撤销栈） */
  function penDiscard() {
    penPath = null
    penCursor = null
    store.penState = null
  }

  function penBegin(p: { x: number; y: number }) {
    pushHistory()
    penCursor = p
    penPath = new scope!.Path([new scope!.Segment(new scope!.Point(p.x, p.y))])
    penPath.fillColor = null as unknown as paper.Color
    penPath.strokeColor = null as unknown as paper.Color
    syncPenState()
  }

  /** 落一个锚点；双击=收尾，点回首锚=闭合 */
  function penPress(p: { x: number; y: number }, detail: number) {
    if (!penPath) {
      penBegin(p)
      return
    }
    penCursor = p
    if (detail >= 2) {
      // 双击：先落点（不足 3 点时补成有效锚点），再尝试闭合
      if (penAnchorCount() < 3) {
        penPath.add(new scope!.Segment(new scope!.Point(p.x, p.y)))
        syncPenState()
      }
      penFinish()
      return
    }
    const first = penPath.firstSegment!.point
    if (penAnchorCount() >= 3 && Math.hypot(p.x - first.x, p.y - first.y) <= penCloseRadius()) {
      penFinish()
      return
    }
    penPath.add(new scope!.Segment(new scope!.Point(p.x, p.y)))
    syncPenState()
  }

  /** 鼠标移动：橡皮筋末端跟随光标（不按键也跟随） */
  function penMove(p: { x: number; y: number }) {
    penCursor = p
    if (penPath) syncPenState()
  }

  /** 收尾：至少 3 个锚点才成形；闭合后选中新图形（不切工具，与直线/矩形/圆形一致） */
  function penFinish(): boolean {
    if (!penPath || penAnchorCount() < 3) return false
    const path = penPath
    penPath = null
    penCursor = null
    path.closed = true
    shapeStyle(path, false)
    markDirty()
    store.penState = null
    setSelection([path])
    // 不切换工具：保持当前钢笔工具，选框可直接操作（与直线/矩形/圆形一致）
    scope?.view.update()
    return true
  }

  /**
   * 取消进行中的钢笔路径。
   * rollbackHistory=false 用于场景即将整体替换（撤销/切帧/烘焙/卸载）的场合，只丢引用不动撤销栈。
   */
  function penCancel(rollbackHistory = true): boolean {
    const had = !!penPath
    penPath?.remove()
    penPath = null
    penCursor = null
    store.penState = null
    if (had && rollbackHistory) popHistory()
    if (had) scope?.view.update()
    return had
  }

  // ─── 填充（Scratch fill-tool 同款：命中换色 + 悬停预览 + 洞覆盖）───
  // 行为规格来自 scratch-paint src/helper/tools/fill-tool.js（develop）：
  // - 点击形状换色：fill 命中→填充色、stroke 命中→描边色；仅 Path/CompoundPath/PointText
  //   可填充——位图代理与空区域穿透（矢量模式无洪水填充，点空=无操作，与 Scratch 一致）
  // - 闭合/近闭合（首尾距<8）路径即使无填充也接受内部填充（Scratch hitUnfilledPaths 语义；
  //   stock paper 的 fill 命中要求 hasFill → 盲区扫描补齐）
  // - 复合路径整体换色；洞（反向子路径）克隆覆盖片填充，提交时父无描边且同色则并入父
  //   （Scratch addedFillItem + reduce 同款）
  // - 悬停即预览换色、按下压撤销栈、松手提交（Scratch updateFillPreview/onMouseUp 模型）

  type FillTarget =
    | { kind: 'style'; item: paper.Item; prop: 'fillColor' | 'strokeColor' }
    | { kind: 'hole'; hole: paper.Path; parent: paper.CompoundPath }

  /** 未提交的悬停预览：还原前不得进快照/导出/剪贴板（snapshotForGesture 统一还原） */
  type FillPreview =
    | { kind: 'style'; item: paper.Item; prop: 'fillColor' | 'strokeColor'; orig: paper.Color | null }
    | { kind: 'cover'; cover: paper.Path; hole: paper.Path; parent: paper.CompoundPath }

  let fillPreview: FillPreview | null = null
  let fillDown = false
  /** 本段手势已压撤销栈（压栈时机=目标首次出现：按下即命中或拖动中途碰到，二者只压一次） */
  let fillPushed = false
  /** 按下目标与当前色相同（零变更手势 → 松手回滚空撤销步） */
  let fillNoop = false

  /** 还原未提交的悬停预览（任何快照/切工具/离场前的统一收口） */
  function restoreFillPreview() {
    if (!fillPreview) return
    if (fillPreview.kind === 'style') {
      if (fillPreview.prop === 'fillColor') fillPreview.item.fillColor = fillPreview.orig
      else fillPreview.item.strokeColor = fillPreview.orig
    } else {
      fillPreview.cover.remove()
    }
    fillPreview = null
  }

  function hasVisibleStroke(item: paper.Item): boolean {
    const s = item.strokeColor
    return !!s && s.alpha > 0.004 && item.strokeWidth > 0
  }

  /**
   * 复合路径描边邻近（stock paper 复合只回 fill 命中、子级经验性不产 stroke 命中 →
   * 按几何距离补齐；Scratch 描边点击换描边色。getNearestLocation 走项目坐标全链路
   *（含父级变换，Node 实测）；loc.distance 即查询点到最近点距离）
   */
  function compoundStrokeNear(
    cp: paper.CompoundPath,
    p: { x: number; y: number },
    tol: number
  ): boolean {
    if (!hasVisibleStroke(cp)) return false
    const pt = new scope!.Point(p.x, p.y)
    const lim = cp.strokeWidth / 2 + tol
    for (const child of cp.children) {
      const loc = (child as paper.Path).getNearestLocation(pt)
      if (loc && loc.distance <= lim) return true
    }
    return false
  }

  /** Scratch helper/math.js expandBy 同款：逐段径向外扩，面积变小则回退（防自交） */
  function expandPathBy(path: paper.Path, amount: number) {
    const center = path.position
    let pathArea = path.area
    for (const seg of path.segments) {
      const delta = seg.point.subtract(center).normalize().multiply(amount)
      seg.point = seg.point.add(delta)
      if (path.area < pathArea) seg.point = seg.point.subtract(delta.multiply(2))
      pathArea = path.area
    }
  }

  /**
   * 解析填充目标 = stock hitTest + 盲区扫描，按同一 DFS 序裁决 z 层。
   * stock paper 打不中而 Scratch 可填的盲区：①无填充闭合/近闭合路径内部 ②复合的洞
   * ③复合描边。raw 与扫描各取最顶目标，序表先访问（z 更顶）者胜；同项偏 raw
   *（点在线上优先描边，与 stock Path._hitTestSelf 一致）。
   */
  function fillTargetAt(p: { x: number; y: number }): FillTarget | null {
    if (!scope) return null
    const S = scope
    const pt = new S.Point(p.x, p.y)
    const tol = 2 / Math.max(0.1, store.zoom)
    const layer = activeLayer()
    if (!layer) return null

    const order: paper.Item[] = []
    let blind: { target: FillTarget; idx: number } | null = null

    // 迭代 DFS（显式栈，hitTest 同序：自顶向下；组下钻、复合按单元）。
    // 不用闭包赋值：TS 对闭包内赋值的变量在闭包外读会按初始化值收窄成 never
    const stack: paper.Item[] = []
    for (let i = 0; i < layer.children.length; i++) stack.push(layer.children[i])
    while (stack.length > 0) {
      const it = stack.pop()! // 尾 = 最后压入 = 当前层最顶
      if (it === bitmapRaster) continue // 位图代理穿透（与 match 排除一致，序表不收）
      if (it instanceof S.Group) {
        for (let i = 0; i < it.children.length; i++) stack.push(it.children[i])
        continue // 组内容先于其下兄弟被访问 → z 序与 hitTest 一致
      }
      if (it instanceof S.CompoundPath) {
        order.push(it)
        if (!blind) {
          const idx = order.length - 1
          const hole = it.children.find(
            (c) => (c as paper.Path).area < 0 && c.contains(pt)
          ) as paper.Path | undefined
          if (compoundStrokeNear(it, p, tol)) {
            blind = { target: { kind: 'style', item: it, prop: 'strokeColor' }, idx }
          } else if (hole) {
            blind = { target: { kind: 'hole', hole, parent: it }, idx }
          } else if (!hasVisibleFill(it) && it.contains(pt)) {
            blind = { target: { kind: 'style', item: it, prop: 'fillColor' }, idx }
          }
        }
        continue // 复合 = 命中单元，不下钻（stock 同：子级只测描边且经验性不命中）
      }
      order.push(it)
      if (!blind && it instanceof S.Path && !hasVisibleFill(it)) {
        const almost =
          it.segments.length > 2 &&
          it.lastSegment!.point.getDistance(it.firstSegment!.point) < 8
        if ((it.closed || almost) && it.contains(pt)) {
          blind = { target: { kind: 'style', item: it, prop: 'fillColor' }, idx: order.length - 1 }
        }
      }
    }

    // stock hitTest（Scratch match：只认 Path/CompoundPath/PointText → 代理等穿透）
    const raw = S.project.hitTest(pt, {
      fill: true,
      stroke: true,
      segments: false,
      curves: false,
      tolerance: tol,
      match: (hr: paper.HitResult) =>
        hr.item instanceof S.Path ||
        hr.item instanceof S.CompoundPath ||
        hr.item instanceof S.PointText,
    })

    let target: FillTarget | null = null
    if (raw) {
      // 复合子级命中提升为整体（Scratch _getFillItem 同款）
      let item = raw.item
      while (item.parent instanceof S.CompoundPath) item = item.parent
      const rawIdx = order.indexOf(item)
      if (blind && blind.idx < rawIdx) target = blind.target // 盲区目标更顶 → 胜
      else target = { kind: 'style', item, prop: raw.type === 'stroke' ? 'strokeColor' : 'fillColor' }
    } else if (blind) {
      target = blind.target
    }
    if (!target) return null

    // 复合整体 fill 命中 + 点在描边邻域 → 改判描边（Scratch 描边点击换描边色）
    if (
      target.kind === 'style' &&
      target.item instanceof S.CompoundPath &&
      target.prop === 'fillColor' &&
      compoundStrokeNear(target.item, p, tol)
    ) {
      target = { kind: 'style', item: target.item, prop: 'strokeColor' }
    }
    return target
  }

  /** 应用填充预览（写色/创建洞覆盖片），记录还原所需原始态；顺带判定零变更手势 */
  function applyFillTarget(t: FillTarget) {
    if (!scope) return
    const color = styleColor()
    if (t.kind === 'hole') {
      // 克隆洞子路径（几何在复合坐标系）→ 转正向 + 微扩 0.1 压缝 → 提到复合上方
      const cover = t.hole.clone()
      cover.clockwise = true
      expandPathBy(cover, 0.1)
      // 子级移出复合后缺父级变换 → prepend 父全局矩阵（transform = 世界系 prepend）
      const g = (t.parent as unknown as { getGlobalMatrix: () => paper.Matrix }).getGlobalMatrix()
      cover.insertAbove(t.parent)
      cover.transform(g)
      cover.fillColor = color
      cover.strokeColor = null
      fillPreview = { kind: 'cover', cover, hole: t.hole, parent: t.parent }
      fillNoop = false // 新建对象恒为变更
    } else {
      const orig = t.prop === 'fillColor' ? t.item.fillColor : t.item.strokeColor
      if (t.prop === 'fillColor') t.item.fillColor = color
      else t.item.strokeColor = color
      fillPreview = { kind: 'style', item: t.item, prop: t.prop, orig }
      fillNoop = !!orig && orig.toCSS(false) === color.toCSS(false)
    }
  }

  function sameFillTarget(prev: FillPreview, t: FillTarget): boolean {
    if (t.kind === 'hole') return prev.kind === 'cover' && prev.parent === t.parent && prev.hole === t.hole
    if (prev.kind === 'cover') return prev.cover === t.item // 覆盖片在场时再命中的就是它自己
    return prev.item === t.item && prev.prop === t.prop
  }

  /** 同目标刷色（拾色器改色后继续移动即反映新色） */
  function recolorFillPreview() {
    if (!fillPreview) return
    const color = styleColor()
    if (fillPreview.kind === 'cover') fillPreview.cover.fillColor = color
    else if (fillPreview.prop === 'fillColor') fillPreview.item.fillColor = color
    else fillPreview.item.strokeColor = color
  }

  /** 悬停/拖动跟随：换目标先还原再应用；同目标只刷色（Scratch updateFillPreview 模型） */
  function fillMove(p: { x: number; y: number }) {
    if (fillDown && !fillPushed) {
      // 手势起于空白、拖动才碰到目标：延迟压栈再应用（等效 fillPress 后半段）——
      // Scratch mouseup 对当前预览无条件提交，此路径保证其可正确进撤销栈
      restoreFillPreview() // 幂等清场（press-on-empty 已清；防覆盖片被当目标重套）
      const t = fillTargetAt(p)
      if (!t) return
      pushHistory()
      applyFillTarget(t)
      fillPushed = true
      return
    }
    const t = fillTargetAt(p)
    if (!t) {
      restoreFillPreview()
      return
    }
    if (fillPreview && sameFillTarget(fillPreview, t)) {
      recolorFillPreview()
      return
    }
    restoreFillPreview()
    applyFillTarget(t) // 重算 fillNoop（拖动换目标以新目标判定）
  }

  function fillPress(p: { x: number; y: number }) {
    restoreFillPreview() // 干净场景解析（悬停出的覆盖片先摘，否则命中的就是片而非洞）
    fillDown = true // 点空白也开手势（目标可能中途出现，见 fillMove 延迟压栈）
    const t = fillTargetAt(p)
    if (!t) return
    pushHistory() // 内含快照前预览还原兜底；快照 = 原始色
    applyFillTarget(t)
    fillPushed = true
  }

  /** 洞覆盖片提交合并（Scratch handleMouseUp 同款）：父无描边且填充同色 → 洞消融进父 */
  function commitCoverMerge(pv: Extract<FillPreview, { kind: 'cover' }>) {
    const { cover, hole, parent } = pv
    const noStroke = !parent.strokeColor || parent.strokeColor.alpha === 0 || parent.strokeWidth === 0
    const css = cover.fillColor ? cover.fillColor.toCSS(false) : ''
    if (noStroke && css && parent.fillColor && parent.fillColor.toCSS(false) === css) {
      cover.remove()
      hole.remove()
      // 单子路径 reduce 成 Path；≥2 子返回自身（Node 实测幂等），重设填充无害
      const merged = (parent as unknown as { reduce: () => paper.Item }).reduce()
      merged.fillColor = cover.fillColor
    }
  }

  function fillRelease() {
    if (!fillDown) return
    fillDown = false
    if (!fillPushed) return // 整段手势从未命中目标 → 无压栈无变更
    fillPushed = false
    if (!fillPreview) {
      popHistory() // 拖离目标已还原 → 无变更，回滚空步
      return
    }
    if (fillNoop) {
      fillPreview = null // 预览色 == 原色，直接收态（无需还原）
      popHistory()
      return
    }
    if (fillPreview.kind === 'cover') commitCoverMerge(fillPreview)
    fillPreview = null // 提交：保留写入的预览色
    markDirty()
  }

  // ─── 塑形（Scratch reshape-tool 同款：4 级命中分派 + 锚点/手柄/曲线操作）───
  // 行为规格来自 scratch-paint src/helper/selection-tools/{reshape,point,handle}-tool.js
  // 与 containers/mode-tools.jsx（develop）：
  // - 命中优先级：选中锚点 → 选中锚点的手柄（项未全选时显示）→ 选中项的曲线
  //  → 任意可编辑路径填充/描边/曲线（位图代理穿透——塑形不作用于位图）
  // - 点曲线插入锚点（divideAt+smooth，立即可拖）；双击锚点删除（松手执行、拖动取消）
  // - 拖锚点=全部选中锚点同拖（Shift=45° 吸附）；拖柄=共线联动（已断开或 Alt=独立）
  // - 点空白框选锚点（框内锚点连同其对象一起选中）；点击已选中锚点松手反选（只留它）
  // - 顶栏「曲线/折线」按钮作用于选中锚点（mode-tools 同款算法，HANDLE_RATIO=0.39026…）

  const HANDLE_RATIO = 0.3902628565
  /** 双击判定窗口（Scratch DOUBLE_CLICK_MILLIS） */
  const RESHAPE_DBL_MS = 250
  /** 锚点/手柄命中半径（Scratch HANDLE_RADIUS 5.25 + PADDING 1，屏幕像素恒定） */
  const RESHAPE_TOL = 6.25

  /** 塑形选中的锚点 */
  let reshapeSel = new Set<paper.Segment>()
  let reshapeOp: 'none' | 'point' | 'handle' | 'move' | 'box' = 'none'
  let reshapeLast: { x: number; y: number } | null = null
  let reshapeDownPt: { x: number; y: number } | null = null
  /** 拖动起点各选中锚点的全局位置（Shift 45° 吸附基准 + 位移换算 local） */
  let reshapeOrigPts = new Map<paper.Segment, paper.Point>()
  let reshapeHandleHit: 'handle-in' | 'handle-out' | null = null
  let reshapeHandleSeg: paper.Segment | null = null
  /** 双击删点/取消选中挂起（拖动即取消，松手执行） */
  let reshapePendingDelete: paper.Segment | null = null
  let reshapePendingDesel: paper.Segment | null = null
  let reshapeInvertDesel = false
  let reshapeClickTime = 0
  let reshapeClickSeg: paper.Segment | null = null
  /** 手势快照（同 select opSnapshot：移动了才入栈） */
  let reshapeSnapshot: string | null = null
  let reshapeMoved = false
  let reshapeBoxAnchor: { x: number; y: number } | null = null
  /** 框选加选标志（按下时的 Shift，松手时决定是否清空旧选择） */
  let reshapeBoxAdditive = false

  /** 可锚点编辑的选中项（Path/CompoundPath；组与位图代理不参与塑形） */
  function reshapeItems(): paper.Item[] {
    if (!scope) return []
    const S = scope
    const out: paper.Item[] = []
    for (const it of selected) {
      if (it === bitmapRaster) continue
      if (it instanceof S.Path || it instanceof S.CompoundPath) out.push(it)
    }
    return out
  }

  /** 把选中项的全部锚点同步到 store（SVG overlay 渲染 + 顶栏曲线/折线按钮可用性） */
  function syncReshapePts() {
    const base = () => {
      store.reshapePts = null
      store.reshapeOutline = null
      store.reshapeHasUncurved = false
      store.reshapeHasPointed = false
      store.vectorSelectedCount = selected.size
    }
    if (store.activeTool !== 'reshape' || store.mode !== 'vector') {
      base()
      return
    }
    const items = reshapeItems()
    if (items.length === 0) {
      base()
      return
    }
    const pts: NonNullable<typeof store.reshapePts> = []
    const outlines: string[] = []
    let hasUncurved = false
    let hasPointed = false
    for (const item of items) {
      // 轮廓 path data（项目坐标）：运行时 getPathData(matrix) d.ts 未收录 → 窄 cast
      outlines.push(
        (item as unknown as { getPathData: (m: paper.Matrix) => string }).getPathData(
          item.globalMatrix
        )
      )
      // segments 是 PathItem 运行时聚合（d.ts 仅 Path 收录）——CompoundPath 同样可用
      const segs = (item as paper.Path).segments
      // 项内锚点全选 = Scratch fullySelected → 手柄隐藏
      const allSel = segs.length > 0 && segs.every((s) => reshapeSel.has(s))
      for (const seg of segs) {
        const path = seg.path
        const c = path.localToGlobal(seg.point)
        // 手柄只对选中锚点下发（Scratch：segment.selected 才画柄），项内全选时隐藏
        const sel = reshapeSel.has(seg)
        const showHandles = sel && !allSel
        const hi =
          showHandles && seg.handleIn.length > 0
            ? path.localToGlobal(seg.point.add(seg.handleIn))
            : null
        const ho =
          showHandles && seg.handleOut.length > 0
            ? path.localToGlobal(seg.point.add(seg.handleOut))
            : null
        pts.push({
          x: c.x,
          y: c.y,
          handleIn: hi ? { x: hi.x, y: hi.y } : null,
          handleOut: ho ? { x: ho.x, y: ho.y } : null,
          selected: sel,
        })
        if (sel) {
          // 曲线化判定（mode-tools _getSelectedUncurvedPoints 同款）
          const prev = seg.previous
          const next = seg.next
          const isCurved =
            (!prev || seg.handleIn.length > 0) &&
            (!next || seg.handleOut.length > 0) &&
            (prev && next ? seg.handleOut.isCollinear(seg.handleIn) : true)
          if (!isCurved) hasUncurved = true
          if (seg.handleIn.length > 0 || seg.handleOut.length > 0) hasPointed = true
        }
      }
    }
    store.reshapePts = pts
    store.reshapeOutline = outlines
    store.reshapeHasUncurved = hasUncurved
    store.reshapeHasPointed = hasPointed
    store.vectorSelectedCount = selected.size
  }

  function clearReshapeOverlay() {
    reshapeSel.clear()
    reshapeOp = 'none'
    reshapePendingDelete = null
    reshapePendingDesel = null
    reshapeHandleSeg = null
    reshapeHandleHit = null
    reshapeSnapshot = null
    reshapeMoved = false
    reshapeLast = null
    reshapeDownPt = null
    reshapeBoxAnchor = null
    reshapeOrigPts.clear()
    store.reshapePts = null
    store.reshapeOutline = null
    store.reshapeHasUncurved = false
    store.reshapeHasPointed = false
  }

  /** 4 级命中分派（reshape-tool.getHitResult 同构；hitTestAll 返回序=自顶向下，取首即最顶） */
  function reshapeTopHit(p: { x: number; y: number }): paper.HitResult | null {
    if (!scope) return null
    const S = scope
    const pt = new S.Point(p.x, p.y)
    const tol = RESHAPE_TOL / Math.max(0.1, store.zoom)
    const items = reshapeItems()
    if (items.length > 0) {
      const itemSet = new Set(items)
      // 1) 选中对象的任意锚点——match 按对象级（Scratch hitResult.item.selected 同款）。
      // 曾误写成锚点级（reshapeSel.has）：点未选中锚点第 1 级落空 → 落到第 3 级曲线
      // 命中 → 走 divideAt 加点分支 → 拖出新点而原点残留
      let hits = S.project.hitTestAll(pt, {
        segments: true,
        tolerance: tol,
        match: (hr: paper.HitResult) =>
          hr.type === 'segment' && !!hr.segment && itemSet.has(hr.item),
      })
      if (hits.length) return hits[0]
      // 2) 选中锚点的手柄（所属项未全选才可见可命中）
      hits = S.project.hitTestAll(pt, {
        handles: true,
        tolerance: tol,
        match: (hr: paper.HitResult) => {
          if (!hr.segment || !reshapeSel.has(hr.segment)) return false
          const segs = (hr.item as paper.Path).segments
          return !segs.every((s) => reshapeSel.has(s))
        },
      })
      if (hits.length) return hits[0]
      // 3) 选中项的曲线
      hits = S.project.hitTestAll(pt, {
        segments: false,
        curves: true,
        stroke: false,
        fill: false,
        tolerance: tol,
        match: (hr: paper.HitResult) => hr.type === 'curve' && itemSet.has(hr.item),
      })
      if (hits.length) return hits[0]
    }
    // 4) 任意可编辑路径的填充/描边/曲线（位图代理 match 排除 → 穿透）
    const hits4 = S.project.hitTestAll(pt, {
      fill: true,
      stroke: true,
      curves: true,
      tolerance: tol,
      match: (hr: paper.HitResult) =>
        hr.item !== bitmapRaster &&
        (hr.item instanceof S.Path || hr.item instanceof S.CompoundPath),
    })
    return hits4.length ? hits4[0] : null
  }

  /** Scratch math.js snapDeltaToAngle 同款：向量夹角吸附到 angle 步进（长度不变） */
  function snapDeltaToAngle(d: paper.Point, angle: number): paper.Point {
    const len = d.length
    if (len < 1e-9) return d
    const a = Math.round(Math.atan2(d.y, d.x) / angle) * angle
    return new scope!.Point(Math.cos(a) * len, Math.sin(a) * len)
  }

  /** point-tool.removePoint 同款：删段 + 邻接两段手柄长度按曲线长×HANDLE_RATIO 重调 */
  function reshapeRemovePoint(seg: paper.Segment) {
    const path = seg.path
    if (!path || path.segments.length <= 2) return // 至少保留两点防退化
    const index = seg.index
    path.removeSegment(index)
    const beforeSegment = path.segments[index - 1]
    const afterSegment = path.segments[index]
    const curveLength = beforeSegment && beforeSegment.curve ? beforeSegment.curve.length : null
    const zero = new scope!.Point(0, 0)
    if (beforeSegment && beforeSegment.handleOut.length > 0) {
      if (afterSegment && curveLength !== null) {
        beforeSegment.handleOut = beforeSegment.handleOut.multiply(
          (curveLength * HANDLE_RATIO) / beforeSegment.handleOut.length
        )
      } else {
        beforeSegment.handleOut = zero
      }
    }
    if (afterSegment && afterSegment.handleIn.length > 0) {
      if (beforeSegment && curveLength !== null) {
        afterSegment.handleIn = afterSegment.handleIn.multiply(
          (curveLength * HANDLE_RATIO) / afterSegment.handleIn.length
        )
      } else {
        afterSegment.handleIn = zero
      }
    }
  }

  /** 选中锚点转全局起始位置（拖动位移换算与 45° 吸附共用基准） */
  function captureReshapeOrigs() {
    reshapeOrigPts.clear()
    for (const s of reshapeSel) {
      reshapeOrigPts.set(s, s.path.localToGlobal(s.point))
    }
  }

  function beginReshape(p: { x: number; y: number }, shift: boolean, time: number) {
    if (!scope) return
    const hit = reshapeTopHit(p)
    // 双击窗口（Scratch：只看时间间隔）
    const dbl = !!reshapeClickSeg && time - reshapeClickTime < RESHAPE_DBL_MS
    reshapeClickTime = time
    reshapeClickSeg =
      hit && hit.segment && (hit.type === 'segment' || hit.type === 'handle-in' || hit.type === 'handle-out')
        ? hit.segment
        : null

    if (!hit) {
      // 空白 → 锚点框选（选择结果在 endReshape 落定）
      reshapeOp = 'box'
      reshapeBoxAnchor = p
      reshapeBoxAdditive = shift
      store.selection = { x: p.x, y: p.y, w: 0, h: 0 }
      store.floatActive = false
      return
    }

    const item = hit.item
    // FILL/Move：未选中项的任何命中、已选中项的填充/描边、双击非锚点
    if (
      !selected.has(item) ||
      hit.type === 'fill' ||
      hit.type === 'stroke' ||
      (hit.type !== 'segment' && dbl)
    ) {
      reshapeOp = 'move'
      if (!selected.has(item)) {
        if (!shift) {
          clearSelection()
        }
        selected.add(item)
      }
      syncVectorSelBox()
      syncReshapePts()
      reshapeSnapshot = snapshotForGesture()
      reshapeMoved = false
      reshapeLast = p
      reshapeDownPt = p
      return
    }

    if (hit.type === 'segment') {
      const seg = hit.segment!
      reshapeOp = 'point'
      if (dbl) reshapePendingDelete = seg
      if (reshapeSel.has(seg)) {
        // 已选中：Shift=松手取消选中；无 Shift=松手反选（只留它，point-tool 同款）
        reshapePendingDesel = seg
        reshapeInvertDesel = !shift
      } else {
        if (!shift) reshapeSel.clear()
        reshapeSel.add(seg)
      }
      syncReshapePts()
      reshapeSnapshot = snapshotForGesture()
      reshapeMoved = false
      reshapeLast = p
      reshapeDownPt = p
      captureReshapeOrigs()
      return
    }

    if (hit.type === 'curve') {
      // 曲线上插入锚点并立即进入拖动（point-tool.addPoint 同款；
      // stock paper 加点原语是 Curve.divideAt → 右段的 segment1 即新锚点）
      const nc = hit.location.curve.divideAt(hit.location)
      const ns = nc ? nc.segment1 : null
      if (ns) {
        if (!ns.hasHandles()) ns.smooth()
        reshapeOp = 'point'
        if (!shift) reshapeSel.clear()
        reshapeSel.add(ns)
        syncReshapePts()
        reshapeSnapshot = snapshotForGesture()
        reshapeMoved = false
        reshapeLast = p
        reshapeDownPt = p
        captureReshapeOrigs()
      }
      return
    }

    if (hit.type === 'handle-in' || hit.type === 'handle-out') {
      reshapeOp = 'handle'
      reshapeHandleHit = hit.type
      reshapeHandleSeg = hit.segment!
      reshapeSnapshot = snapshotForGesture()
      reshapeMoved = false
      reshapeLast = p
      return
    }
  }

  function continueReshape(p: { x: number; y: number }, shift: boolean, alt: boolean) {
    if (!scope || !reshapeLast) return
    const S = scope
    if (reshapeOp === 'box' && reshapeBoxAnchor) {
      const a = reshapeBoxAnchor
      store.selection = {
        x: Math.min(a.x, p.x),
        y: Math.min(a.y, p.y),
        w: Math.abs(p.x - a.x),
        h: Math.abs(p.y - a.y),
      }
      return
    }
    const dx = p.x - reshapeLast.x
    const dy = p.y - reshapeLast.y
    if (dx === 0 && dy === 0) return

    if (reshapeOp === 'point') {
      // 拖动取消挂起的删除/反选（point-tool：click 语义被 drag 覆盖）
      reshapePendingDelete = null
      reshapePendingDesel = null
      reshapeInvertDesel = false
      const snapBase = reshapeDownPt ?? p
      for (const [seg, origG] of reshapeOrigPts) {
        const path = seg.path
        const ng = shift
          ? origG.add(snapDeltaToAngle(new S.Point(p.x - snapBase.x, p.y - snapBase.y), Math.PI / 4))
          : new S.Point(origG.x + (p.x - snapBase.x), origG.y + (p.y - snapBase.y))
        seg.point = path.globalToLocal(ng)
      }
      reshapeMoved = true
      reshapeLast = p
      syncReshapePts()
      return
    }

    if (reshapeOp === 'handle' && reshapeHandleSeg && reshapeHandleHit) {
      const seg = reshapeHandleSeg
      const path = seg.path
      const isOut = reshapeHandleHit === 'handle-out'
      const g0 = isOut
        ? path.localToGlobal(seg.point.add(seg.handleOut))
        : path.localToGlobal(seg.point.add(seg.handleIn))
      const localH = path
        .globalToLocal(new S.Point(g0.x + dx, g0.y + dy))
        .subtract(seg.point)
      // 共线联动（handle-tool：两柄共线且非 Alt → 对侧柄保持共线反向、长度不变）
      const colinear = seg.handleIn.length > 0 && seg.handleOut.isCollinear(seg.handleIn)
      const mirror = !alt && colinear
      if (isOut) {
        seg.handleOut = localH
        if (mirror) seg.handleIn = seg.handleOut.multiply(-seg.handleIn.length / seg.handleOut.length)
      } else {
        seg.handleIn = localH
        if (mirror) seg.handleOut = seg.handleIn.multiply(-seg.handleOut.length / seg.handleIn.length)
      }
      reshapeMoved = true
      reshapeLast = p
      syncReshapePts()
      return
    }

    if (reshapeOp === 'move') {
      const t = new S.Point(dx, dy)
      for (const it of reshapeItems()) it.translate(t)
      reshapeMoved = true
      reshapeLast = p
      syncReshapePts()
    }
  }

  function endReshape() {
    if (!scope) return
    const S = scope
    if (reshapeOp === 'box') {
      const r = store.selection
      store.selection = null
      if (r && r.w >= 2 && r.h >= 2) {
        // 框选：框内锚点连同其对象一起选中（Shift=加选）
        const rect = new S.Rectangle(r.x, r.y, r.w, r.h)
        if (!reshapeBoxAdditive) {
          selected.clear()
          reshapeSel.clear()
        }
        const layer = activeLayer()
        if (layer) {
          for (const it of layer.children) {
            if (it === bitmapRaster) continue
            if (!(it instanceof S.Path || it instanceof S.CompoundPath)) continue
            let hitAny = false
            for (const seg of (it as paper.Path).segments) {
              const c = it.localToGlobal(seg.point)
              if (rect.contains(new S.Point(c.x, c.y))) {
                reshapeSel.add(seg)
                hitAny = true
              }
            }
            if (hitAny) selected.add(it)
          }
        }
        syncVectorSelBox()
        syncReshapePts()
      } else if (!reshapeBoxAdditive) {
        // 点击空白无框 → 取消全部选择
        clearSelection()
      }
    } else if (
      (reshapeOp === 'move' || reshapeOp === 'point' || reshapeOp === 'handle') &&
      reshapeMoved &&
      reshapeSnapshot
    ) {
      undoStack.push(reshapeSnapshot)
      if (undoStack.length > HISTORY_LIMIT) undoStack.shift()
      redoStack = []
      syncHistoryFlags()
      markDirty()
    } else if (reshapeOp === 'point' && !reshapeMoved) {
      // 未拖动 → 执行挂起的删除/反选（click 语义）
      if (reshapePendingDelete && reshapePendingDelete.path && reshapePendingDelete.path.parent) {
        if (reshapeSnapshot) {
          undoStack.push(reshapeSnapshot)
          if (undoStack.length > HISTORY_LIMIT) undoStack.shift()
          redoStack = []
          syncHistoryFlags()
        }
        const del = reshapePendingDelete
        reshapeRemovePoint(del)
        reshapeSel.delete(del)
        markDirty()
        syncReshapePts()
      } else if (reshapePendingDesel) {
        if (reshapeInvertDesel) {
          const keep = reshapePendingDesel
          reshapeSel.clear()
          reshapeSel.add(keep)
        } else {
          reshapeSel.delete(reshapePendingDesel)
        }
        syncReshapePts()
      }
    }
    reshapeOp = 'none'
    reshapeLast = null
    reshapeDownPt = null
    reshapeSnapshot = null
    reshapeMoved = false
    reshapePendingDelete = null
    reshapePendingDesel = null
    reshapeInvertDesel = false
    reshapeOrigPts.clear()
    reshapeHandleSeg = null
    reshapeHandleHit = null
    reshapeBoxAnchor = null
    reshapeBoxAdditive = false
  }

  /**
   * 顶栏「曲线」：把选中锚点曲线化（mode-tools.handleCurvePoints 同款算法）。
   * 无柄双邻点：柄平行于前邻→后邻连线；端点：凸侧法线与回看方向的平均；
   * 第二柄 = 第一柄镜像（共线等长）——此即「曲线点」定义。
   */
  function curveSelectedPoints() {
    if (!scope || reshapeSel.size === 0) return false
    pushHistory()
    let changed = false
    for (const seg of reshapeSel) {
      const prev = seg.previous
      const next = seg.next
      if (!prev && !next) continue // 单点路径无可 curve
      const isCurved =
        (!prev || seg.handleIn.length > 0) &&
        (!next || seg.handleOut.length > 0) &&
        (prev && next ? seg.handleOut.isCollinear(seg.handleIn) : true)
      if (isCurved) continue
      const noHandles = seg.handleIn.length === 0 && seg.handleOut.length === 0
      if (prev && next && noHandles) {
        seg.handleIn = prev.point
          .subtract(next.point)
          .normalize()
          .multiply(prev.curve.length * HANDLE_RATIO)
      } else if (prev && !next && seg.handleIn.length === 0) {
        const convexity = prev.curve.getCurvatureAtTime(0.5) < 0 ? -1 : 1
        seg.handleIn = prev.curve
          .getNormalAtTime(1)
          .multiply(convexity)
          .add(prev.point.subtract(seg.point).normalize())
          .normalize()
          .multiply(prev.curve.length * HANDLE_RATIO)
      } else if (next && !prev && seg.handleOut.length === 0) {
        const convexity = seg.curve.getCurvatureAtTime(0.5) < 0 ? -1 : 1
        seg.handleOut = seg.curve
          .getNormalAtTime(0)
          .multiply(convexity)
          .add(next.point.subtract(seg.point).normalize())
          .normalize()
          .multiply(seg.curve.length * HANDLE_RATIO)
      }
      if (seg.handleIn.length > 0 && next) seg.handleOut = seg.handleIn.multiply(-1)
      else if (seg.handleOut.length > 0 && prev) seg.handleIn = seg.handleOut.multiply(-1)
      changed = true
    }
    if (changed) {
      markDirty()
      syncReshapePts()
    } else {
      popHistory()
    }
    return changed
  }

  /** 顶栏「折线」：选中锚点清空两柄变尖角（mode-tools.handlePointPoints 同款） */
  function pointSelectedPoints() {
    if (reshapeSel.size === 0) return false
    pushHistory()
    const zero = scope ? new scope.Point(0, 0) : null
    let changed = false
    for (const seg of reshapeSel) {
      if (seg.handleIn.length > 0 || seg.handleOut.length > 0) {
        seg.handleIn = zero!
        seg.handleOut = zero!
        changed = true
      }
    }
    if (changed) {
      markDirty()
      syncReshapePts()
    } else {
      popHistory()
    }
    return changed
  }

  /** 方向键微移（reshape-tool.handleKeyDown 同款：优先移锚点，无锚点选中则移整项） */
  function reshapeNudge(key: string, repeat: boolean): boolean {
    if (!scope || store.activeTool !== 'reshape' || store.mode !== 'vector') return false
    const S = scope
    const d = 1 / Math.max(0.1, store.zoom)
    let dx = 0
    let dy = 0
    if (key === 'ArrowUp') dy = -d
    else if (key === 'ArrowDown') dy = d
    else if (key === 'ArrowLeft') dx = -d
    else if (key === 'ArrowRight') dx = d
    else return false
    const t = new S.Point(dx, dy)
    if (reshapeSel.size > 0) {
      if (!repeat) pushHistory() // 按住 repeat 合并为一步
      for (const seg of reshapeSel) {
        seg.point = seg.path.globalToLocal(seg.path.localToGlobal(seg.point).add(t))
      }
      markDirty()
      syncReshapePts()
      return true
    }
    const items = reshapeItems()
    if (items.length > 0) {
      if (!repeat) pushHistory()
      for (const it of items) it.translate(t)
      markDirty()
      syncReshapePts()
      return true
    }
    return false
  }

  /** Delete/Backspace：删除选中锚点（有锚点选中时优先于对象删除） */
  function reshapeDeletePoints(): boolean {
    if (store.activeTool !== 'reshape' || store.mode !== 'vector' || reshapeSel.size === 0) {
      return false
    }
    pushHistory()
    for (const seg of Array.from(reshapeSel)) {
      reshapeRemovePoint(seg)
      reshapeSel.delete(seg)
    }
    markDirty()
    syncReshapePts()
    return true
  }

  /** Escape：先清锚点选择，再清对象选择（返回是否已处理） */
  function reshapeEscape(): boolean {
    if (store.activeTool !== 'reshape' || store.mode !== 'vector') return false
    if (reshapeSel.size > 0) {
      reshapeSel.clear()
      syncReshapePts()
      return true
    }
    if (selected.size > 0) {
      clearSelection()
      return true
    }
    return false
  }

  // ─── 选中改色（调色板直改图形）───
  // 有选中矢量对象时，右侧调色即时应用到对象：填充通道改填充（有可见填充改填充、
  // 仅描边改描边）；描边由面板勾选区管理（仅矩形/椭圆预设与选中图形编辑时显示；
  // 画笔/橡皮/直线不显示——直线本体粗细走独立 lineWidth）。线宽滑条直改描边宽度，
  // 0=移除描边。撤销按编辑手势合并（colorEditing：一次拖动一步）。

  /** 递归收集可着色目标（Path/CompoundPath/PointText；组下钻、位图代理排除） */
  function tintTargets(): paper.Item[] {
    if (!scope) return []
    const S = scope
    const out: paper.Item[] = []
    const walk = (it: paper.Item) => {
      if (it === bitmapRaster) return
      if (it instanceof S.CompoundPath) {
        out.push(it)
        return
      }
      if (it instanceof S.PointText) {
        out.push(it)
        return
      }
      if (it instanceof S.Group) {
        for (const c of it.children) walk(c)
        return
      }
      if (it instanceof S.Path) out.push(it)
    }
    for (const it of selected) walk(it)
    return out
  }

  /** 描边通道绘制色（strokeColor + 不透明度） */
  function styleStrokeColor(): paper.Color {
    return new scope!.Color(rgbaCss(store.strokeColor, store.opacity))
  }

  function tintSelection(targets: paper.Item[]) {
    const color = styleColor()
    for (const it of targets) {
      if (it instanceof scope!.PointText) {
        it.fillColor = color // 文字只有填充色
        continue
      }
      if (hasVisibleFill(it)) it.fillColor = color
      else if (hasVisibleStroke(it)) it.strokeColor = color
      else it.fillColor = color // 双无的隐形形状 → 填充使其可见
    }
  }

  function tintStrokeSelection(targets: paper.Item[]) {
    const color = styleStrokeColor()
    for (const it of targets) {
      const p = it as paper.Path
      const had = hasVisibleStroke(p)
      it.strokeColor = color
      // 从未有描边的对象：宽度归 0（改色只定色相，线宽滑条显示 0，拖宽才出现描边）
      if (!had) p.strokeWidth = 0
    }
  }

  /** 本次改色手势是否已压撤销栈 / 是否产生可见变更（收口时统一刷缩略图） */
  let tintPushed = false
  let tintTouched = false

  /** 改色/线宽统一收口：首变压栈（同手势合并），拖动中只置脏标、结束统一刷缩略图 */
  function tintApply(apply: () => void) {
    if (!tintPushed) {
      pushHistory() // 手势首次：快照 = 改动前
      tintPushed = true
    }
    apply()
    if (store.colorEditing) {
      tintTouched = true
      store.dirty = true // 拖动中画布由 paper 实时重绘；缩略图收口统一刷
    } else {
      tintPushed = false // 非手势单次改动：一步一清
      markDirty()
    }
  }

  watch(
    () => [store.fillColor, store.opacity],
    () => {
      if (store.mode !== 'vector') return
      // 编辑中文字：即时跟随填充色（不压撤销栈，结束编辑时统一快照）
      if (textMode === 'edit' && textBox) {
        textBox.fillColor = styleColor()
        syncTextEditOverlay()
        return
      }
      const targets = tintTargets()
      if (targets.length === 0) return
      tintApply(() => tintSelection(targets))
    }
  )

  watch(
    () => [store.strokeColor, store.opacity],
    () => {
      if (store.mode !== 'vector') return
      if (!store.selectionHasStroke) return
      const targets = tintTargets()
      if (targets.length === 0) return
      tintApply(() => tintStrokeSelection(targets))
    }
  )

  // 勾选「描边」（store.strokeEnabled=勾选态，strokeToggleTick=强制信号——预设残留时
  // 新旧值相同 watch 不触发）。有选中图形 → 立即加/去描边；无选中 → 新形状预设。
  watch(
    () => [store.strokeEnabled, store.strokeToggleTick],
    () => {
      if (store.mode !== 'vector') return
      const on = store.strokeEnabled
      const targets = tintTargets()
      if (targets.length === 0) return
      // 只处理会实际变化的目标；取消勾选不动"本体描边"（无填充的直线/轮廓——去描边=删本体致线条消失）
      const changed = targets.filter((it) => {
        const p = it as paper.Path
        if (on) return !hasVisibleStroke(p)
        return hasVisibleStroke(p) && hasVisibleFill(p)
      })
      if (changed.length === 0) {
        syncStrokeWidthFromSelection()
        return
      }
      const color = styleStrokeColor()
      const w = store.strokeWidth > 0 ? store.strokeWidth : 4 // 勾选加描边默认粗细 4
      tintApply(() => {
        for (const it of changed) {
          const p = it as paper.Path
          if (on) {
            p.strokeColor = color
            p.strokeWidth = w
          } else {
            p.strokeColor = null
          }
        }
      })
      syncStrokeWidthFromSelection() // 刷新勾选态与线宽滑条
    }
  )

  // 线宽滑条（面板内，勾选描边后显示）：直改描边宽度，0=移除描边；
  // 无描边对象拖宽会先以描边通道色出现描边（直觉：拖宽即想看到描边）
  watch(
    () => store.strokeWidth,
    () => {
      if (store.mode !== 'vector') return
      const targets = tintTargets()
      if (targets.length === 0) return
      const w = store.strokeWidth
      tintApply(() => {
        for (const it of targets) {
          const p = it as paper.Path
          if (w <= 0) {
            // 0=去描边只对"真描边"（有填充的对象）生效；本体描边（直线/轮廓）保底可见
            if (hasVisibleFill(p)) {
              p.strokeColor = null
            } else if (!hasVisibleStroke(p)) {
              p.strokeColor = styleStrokeColor()
              p.strokeWidth = Math.max(1, p.strokeWidth || 4)
            } else {
              p.strokeWidth = Math.max(1, p.strokeWidth)
            }
          } else {
            if (!hasVisibleStroke(p)) p.strokeColor = styleStrokeColor()
            p.strokeWidth = w
          }
        }
      })
      syncStrokeWidthFromSelection() // 拖宽可能让无描边对象出现描边 → 刷新勾选态
    }
  )

  watch(() => store.colorEditing, (editing) => {
    if (!editing) {
      tintPushed = false
      if (tintTouched) {
        tintTouched = false
        markDirty()
      }
    }
  })

  // 选中矢量图形时线宽滑条同步为该图形实际描边宽（无描边=0）。
  // 不走 watch(vectorSelectedCount)：setSelection 在同一同步块内 count 1→0→1，
  // 新旧值相同 watch 不触发（图形 A 宽10 → 画 B 选中后滑条残留 10 的根因）——
  // 挂在 syncVectorSelBox（一切选中变化的必经点）内联调用。
  function syncStrokeWidthFromSelection() {
    if (store.mode !== 'vector') return
    // 直线工具操作焦点=直线本体：滑条保持直线组存值，不用选中对象覆盖
    if (store.activeTool === 'line') return
    if (selected.size === 0) {
      store.selectionHasStroke = false
      store.selectionHasBodyStroke = false
      store.selectionBodyOnly = false
      return
    }
    const targets = tintTargets()
    if (targets.length === 0) {
      store.selectionHasStroke = false
      store.selectionHasBodyStroke = false
      store.selectionBodyOnly = false
      return
    }
    let w = 0
    let has = false
    let hasBody = false
    let allBody = true
    for (const it of targets) {
      const p = it as paper.Path
      const stroked = hasVisibleStroke(p)
      // 本体描边 = 无可见填充（直线/描边轮廓形：描边就是对象本身）
      const isBody = stroked && !hasVisibleFill(p)
      if (stroked) {
        has = true
        if (w === 0) w = p.strokeWidth
      }
      if (isBody) hasBody = true
      else allBody = false
    }
    store.strokeWidth = w
    store.selectionHasStroke = has
    store.selectionHasBodyStroke = hasBody
    store.selectionBodyOnly = allBody
  }

  /** 橡皮手势状态：首次命中才压栈（未命中不产生空撤销步）；拖过整段只记一步、结束统一刷缩略图 */
  let erasePushed = false
  let eraseChanged = false
  /** 上一个擦除点（轨迹连续化：事件间距可超过擦除圆直径，插值补点防留空洞） */
  let eraseLast: { x: number; y: number } | null = null

  /**
   * 橡皮擦除核心（行为对齐 Scratch mergeEraser，读规格自实现）：
   * - 闭合填充形状 → 布尔差集局部挖洞；擦成多个实心块时拆为独立对象、洞归还所属块
   * - 开放笔画/无填充路径 → 与擦除圆求交点切段，删除被擦到的段（擦哪删哪，不整删）
   * - 逐点实时处理（比 Scratch 的 mouseup 一次性反馈更快）
   */

  /** 可见填充判定（对齐 Scratch：无填充或 alpha≈0 视为笔画，走切分分支） */
  function hasVisibleFill(item: paper.Item): boolean {
    const f = item.fillColor
    return !!f && f.alpha > 0.004
  }

  /**
   * 橡皮接触判定（对齐 Scratch touches=几何相交，替代点 hitTest）：
   * 点 hitTest 在圆心进入已咬空区域/贴边缘时会漏判 → 该刀跳过 → 漏咬出
   * 梯形回缩与尖角残留（擦除边缘不规则的根因）。几何判定与圆心位置无关：
   * 圆心在实心内，或橡皮圆（⊕描边半宽——视觉橡皮须碰到描边带）与对象相交。
   */
  function eraserTouches(
    item: paper.PathItem,
    p: { x: number; y: number },
    r: number
  ): boolean {
    const S = scope!
    if (item.contains(p)) return true
    let sw = 0
    if (item instanceof S.Path) {
      const sc = item.strokeColor
      if (sc && sc.alpha > 0.004) sw = (item.strokeWidth || 0) / 2
    }
    const probe = new S.Path.Circle(new S.Point(p.x, p.y), r + sw)
    const hit = item.intersects(probe)
    probe.remove()
    return hit
  }

  /** 递归收集与橡皮接触的可擦对象：PathItem 整体收（复合不深入）、组递归、跳过位图代理 */
  function collectErasable(
    items: paper.Item[],
    p: { x: number; y: number },
    r: number,
    out: paper.PathItem[]
  ) {
    const S = scope!
    for (const it of items) {
      if (isBitmapRaster(it)) continue
      if (it instanceof S.PathItem) {
        if (eraserTouches(it, p, r)) out.push(it)
      } else if (it.children) {
        collectErasable(it.children, p, r, out)
      }
    }
  }

  /**
   * 沿擦除圆切分路径并删除中点落在圆内的段（Scratch 开放笔画分支行为）：
   * 交点倒序 splitAt（保持前方交点位置有效）→ 逐段 contains 判定移除。
   * @returns 是否发生实际删除
   */
  function splitPathAtCircle(path: paper.Path, circle: paper.Path): boolean {
    const inter = path.getIntersections(circle)
    if (inter.length === 0) return false
    const subs: paper.Path[] = []
    for (let j = inter.length - 1; j >= 0; j--) {
      const split = path.splitAt(inter[j])
      if (split) {
        split.insertAbove(path)
        subs.push(split)
      }
    }
    subs.push(path)
    let removedAny = false
    for (let k = subs.length - 1; k >= 0; k--) {
      const s = subs[k]
      const loc = s.length > 1e-6 ? s.getLocationAt(s.length / 2) : null
      if (!loc || circle.contains(loc.point)) {
        s.remove()
        subs.splice(k, 1)
        removedAny = true
      }
    }
    // 擦剩退化残留（不足两点）的空路径清理
    if (path.parent && path.segments.length < 2) {
      path.remove()
      removedAny = true
    }
    return removedAny
  }

  /**
   * 布尔差集结果整理（对齐 Scratch separateCompoundPath 语义，自实现）：
   * 擦成多个实心块时拆为独立对象、洞（反向子路径）按包含关系归还所属块；
   * 单块（一个实心区域，无论带不带洞）保持原对象——渲染与选中语义都正确。
   */
  function separateErasedCompound(cp: paper.Item) {
    const S = scope!
    if (!(cp instanceof S.CompoundPath) || !cp.children) return
    const paths = cp.children.filter((c): c is paper.Path => c instanceof S.Path)
    const cws = paths.filter((c) => c.clockwise)
    const holes = paths.filter((c) => !c.clockwise)
    if (cws.length <= 1) return // 单块带洞 = 挖洞后的一整块，保持复合
    const parent = cp.parent
    if (!parent) return
    // 每块克隆为独立对象（样式取自原复合路径）
    const blocks: paper.Item[] = cws.map((cw) => {
      const b = cw.clone({ insert: false }) as paper.Path
      b.copyAttributes(cp, false)
      b.fillColor = cp.fillColor
      b.strokeColor = cp.strokeColor
      b.strokeWidth = cp.strokeWidth
      return b
    })
    // 洞按包含关系归还所属块（擦除产生的块互不重叠，归属唯一）
    for (const hole of holes) {
      const pt = hole.firstSegment?.point
      if (!pt) continue
      const idx = blocks.findIndex(
        (b) => b instanceof S.PathItem && b.contains(pt)
      )
      if (idx >= 0) {
        const owner = blocks[idx] as paper.PathItem
        const cut = owner.subtract(hole)
        if (cut && !cut.isEmpty()) {
          cut.insertAbove(owner)
          owner.remove()
          blocks[idx] = cut
        }
      }
    }
    for (const b of blocks) b.insertAbove(cp)
    cp.remove()
  }

  /**
   * 擦后局部修边（对齐 Scratch 修正逻辑：只修正被擦的那条边）：
   * 只扫描橡皮圆邻域内的顶点，删除布尔交界产生的低曲率多余点
   *（点到前后弦距离 < 0.75px 的内部点=微折锯齿；真实弧的弓高点>0.75 保留），
   * 删点后以直线连接 → 被擦边整齐，未擦区域一律不动（无全路径重拟合的形状漂移）。
   */
  function trimErasedEdges(item: paper.Item, c: { x: number; y: number }, radius: number) {
    const S = scope!
    const paths: paper.Path[] = []
    if (item instanceof S.Path) {
      paths.push(item)
    } else if (item instanceof S.CompoundPath && item.children) {
      for (const ch of item.children) {
        if (ch instanceof S.Path) paths.push(ch)
      }
    }
    const zone = radius * 2
    const z2 = zone * zone
    for (const pth of paths) {
      // 多轮扫描（删点会改变邻域索引），直到无点可删
      for (let round = 0; round < 8; round++) {
        const segs = pth.segments
        const n = segs.length
        if (n <= 3) break
        let removed = false
        const last = pth.closed ? n - 1 : n - 2
        for (let i = 1; i <= last; i++) {
          if (i >= pth.segments.length - 1 && !pth.closed) break
          const seg = pth.segments[i]
          if (!seg) break
          const p = seg.point
          const dx = p.x - c.x
          const dy = p.y - c.y
          if (dx * dx + dy * dy > z2) continue
          const prev = pth.segments[i - 1]
          const next = pth.segments[i + 1]
          if (!prev || !next) continue
          const a = prev.point
          const b = next.point
          const ax = b.x - a.x
          const ay = b.y - a.y
          const len = Math.hypot(ax, ay)
          if (len < 1e-6) {
            seg.remove()
            removed = true
            break
          }
          const d = Math.abs((p.x - a.x) * ay - (p.y - a.y) * ax) / len
          if (d < 0.75) {
            seg.remove()
            removed = true
            break
          }
        }
        if (!removed) break
      }
    }
  }

  function eraseAt(p: { x: number; y: number }) {
    if (!scope) return
    const S = scope
    const r = Math.max(2, store.brushSize / 2)
    const layer = activeLayer()
    if (!layer) return

    // 几何接触收集（可一圆同时作用多个相交对象；位图代理在收集时排除）
    const targets: paper.PathItem[] = []
    collectErasable(layer.children, p, r, targets)
    if (targets.length === 0) return
    if (!erasePushed) {
      pushHistory()
      erasePushed = true
    }

    let acted = false
    for (const target of targets) {
      try {
        const closedFilled =
          (target instanceof S.Path || target instanceof S.CompoundPath) &&
          target.closed &&
          hasVisibleFill(target)
        if (closedFilled) {
          // 闭合填充（形状/画笔 blob/复合）：橡皮像素圆布尔差集挖洞
          //（断口=橡皮圆弧切面，与矩形/圆形擦除统一）；擦断多块时拆为独立对象。
          // 注意：擦后不做全路径 simplify——那会挪动未擦区域的点（反复执行=形状漂移）
          // 并破坏精确圆弧断面（Scratch mergeEraser 同：布尔后直接落位）；
          // 断面本身是 paper 精确贝塞尔弧，天然光滑
          const circle = new S.Path.Circle(new S.Point(p.x, p.y), r)
          const result = target.subtract(circle)
          if (result && !result.isEmpty()) {
            trimErasedEdges(result, p, r) // 只修被擦边：删圆邻域内多余顶点，未擦区域不动
            result.insertBelow(target)
            target.remove()
            separateErasedCompound(result)
          } else {
            target.remove()
          }
          acted = true
        } else if (target instanceof S.Path) {
          // 开放笔画/无填充路径：切分圆 ⊕ cap 外伸（可见断开=橡皮直径）
          const capExt = target.strokeCap === 'butt' ? 0 : (target.strokeWidth || 0) / 2
          const circle = new S.Path.Circle(new S.Point(p.x, p.y), r + capExt)
          acted = splitPathAtCircle(target, circle) || acted
          circle.remove()
        } else {
          // 罕见兜底（无填充复合环等）：整体移除
          target.remove()
          acted = true
        }
      } catch {
        // 布尔运算极端退化时的保底：移除目标而非留下半损坏状态
        if (target.parent) target.remove()
        acted = true
      }
    }
    clearSelection()
    if (acted) eraseChanged = true
  }

  // ─── 文字工具（Scratch text-tool 同款：TEXT_EDIT_MODE / SELECT_MODE 双态）───
  // 行为规格来自 scratch-paint src/helper/tools/text-tool.js：
  // - 点击空白 → 新建 PointText（fontSize 40、填充色=绘制色）并进入编辑（textarea 覆盖）
  // - 编辑中：textarea 输入实时写 content；虚线边框示意编辑范围；Esc/点空白结束
  // - 结束编辑：空文字删除；非空进入 SELECT_MODE（可移动/缩放/旋转）
  // - SELECT_MODE 下双击文字（250ms）→ 重新进入编辑；点其他文字 → 编辑那个
  // - 编辑中途切工具/切帧/切模式 → 强制结束编辑（空删、非空保留并选中）

  const TEXT_DBL_MS = 250
  /** 编辑会话：当前正在编辑的 PointText；null=未在编辑 */
  let textBox: paper.PointText | null = null
  /** 文字工具内部模式（对齐 Scratch TEXT_EDIT_MODE / SELECT_MODE） */
  let textMode: 'none' | 'edit' | 'select' = 'none'
  /** 上次点击（双击判定） */
  let textLastClickTime = 0
  /** 本次编辑会话是否已压撤销栈（beginTextTool 在创建/重编辑前压） */
  let textPushed = false
  /** 编辑会话内是否有实际输入（无输入的重编辑结束时回滚空撤销步） */
  let textDirty = false

  /** 更新 store.textEdit（textarea 定位：内容左上角绝对坐标 + 线性 matrix 随旋转/缩放） */
  function syncTextEditOverlay() {
    if (!scope || !textBox || textMode !== 'edit') {
      store.textEdit = null
      return
    }
    const S = scope
    // internalBounds 在 PointText 局部坐标（相对 point，含负 y=基线上方）
    const ib = textBox.internalBounds
    const m = textBox.matrix
    // 内容左上角在项目坐标（画板逻辑坐标）中的位置
    const tl = m.transform(new S.Point(ib.x, ib.y))
    // 动态尺寸（对齐 Scratch resizeGuide）：贴合内容；空文字保一个光标位（约 0.5em 宽）
    const fs = Number(textBox.fontSize) || PAINT_TEXT_SIZE
    const hasContent = !!(textBox.content && textBox.content.length > 0)
    const w = hasContent ? Math.max(ib.width, 1) : fs * 0.5
    const h = hasContent ? Math.max(ib.height, fs * 0.5) : fs * PAINT_TEXT_LEADING_RATIO
    // 元素放在内容左上角；CSS matrix 只保留线性部分（旋转/缩放），
    // 平移由 left/top 承担——元素 (0,0) 经 matrix 线性变换后落在 tl，与 paper 渲染对齐。
    store.textEdit = {
      matrix: `matrix(${m.a}, ${m.b}, ${m.c}, ${m.d}, 0, 0)`,
      transformOrigin: '0 0',
      x: tl.x,
      y: tl.y,
      fontSize: fs,
      lineHeight: (Number(textBox.leading) || 0) / fs,
      color: textBox.fillColor ? textBox.fillColor.toCSS(true) : '#000',
      value: textBox.content ?? '',
      width: w,
      height: h,
    }
  }

  /** 结束编辑：空文字删除并回滚；非空保留。switchToSelect=true 时选中并切选择工具 */
  function endTextEdit(switchToSelect: boolean = true) {
    if (textMode !== 'edit' || !textBox) {
      return
    }
    const item = textBox
    const hadContent = !!item.content && item.content.trim().length > 0
    const changed = textDirty
    store.textEdit = null
    textBox = null
    textMode = 'none'
    textDirty = false
    item.opacity = 1 // 编辑中隐藏的 PointText 恢复可见
    if (!hadContent) {
      // 空文字：删除并回滚（新建时快照在创建前；重编辑时快照在改动前）
      if (item.parent) item.remove()
      if (textPushed) popHistory()
      textPushed = false
      clearSelection()
      return
    }
    if (!changed && textPushed) {
      // 重编辑但未改内容：回滚空步，避免多余撤销
      popHistory()
      textPushed = false
      setSelection([item])
      if (switchToSelect) store.setTool('select')
      syncVectorSelBox()
      return
    }
    // hadContent && changed：begin 时已压「改动前」快照，此处只清标记
    textPushed = false
    setSelection([item])
    if (switchToSelect) store.setTool('select')
    markDirty()
    syncVectorSelBox()
  }

  /** 开始编辑既有/新建 PointText（调用前须已 pushHistory 覆盖「编辑前」状态） */
  function beginTextEdit(item: paper.PointText, isNew: boolean) {
    if (!scope) return
    if (textMode === 'edit' && textBox === item) return
    if (textMode === 'edit') endTextEdit(false)
    ensurePaintFont()
    textBox = item
    textMode = 'edit'
    textDirty = false
    // 撤销快照：由调用方在创建 PointText / 重编辑前 push（保证栈顶=改动前）
    if (!isNew) {
      // 重编辑：若调用方未压栈则在此压（防御；正常 beginTextTool/double-click 已压）
      if (!textPushed) {
        pushHistory()
        textPushed = true
      }
    }
    // 样式：字体/字号/填充色（leading 对齐 Scratch 实验值）
    item.fontFamily = PAINT_FONT_FAMILY
    item.fontWeight = '500' // Medium：比 Regular 更清晰可读（画布渲染不吃浏览器 faux-bold）
    if (isNew) {
      item.fontSize = PAINT_TEXT_SIZE
      item.leading = PAINT_TEXT_SIZE * PAINT_TEXT_LEADING_RATIO
      item.fillColor = styleColor()
      item.strokeColor = null
    }
    item.justification = 'left'
    // 编辑中隐藏 PointText：textarea 独占显示——两层同时画同一段字会因亚像素/抗锯齿
    // 差异产生重影发糊（提交后恢复渲染即清晰）
    item.opacity = 0
    // 编辑中收起变换框（选中态由编辑会话接管）
    clearSelection()
    syncTextEditOverlay()
    scope.view.update()
    // 字体异步加载完成后重测 internalBounds（首帧可能用回退字体量宽，加载完再贴合一次）
    ensurePaintFont().then(() => {
      if (textMode === 'edit' && textBox === item) {
        syncTextEditOverlay()
        scope?.view.update()
      }
    })
  }

  /** textarea 输入 → 同步 content + 刷新 overlay 尺寸 */
  function onTextEditInput(value: string) {
    if (!textBox || textMode !== 'edit') return
    textDirty = true
    textBox.content = value
    syncTextEditOverlay()
    scope?.view.update()
  }

  /** 命中 PointText（文字工具专用：fill 命中即可编辑；位图代理是 Raster 不会命中） */
  function hitTextEditTarget(p: { x: number; y: number }): paper.PointText | null {
    if (!scope) return null
    const S = scope
    const tol = 2 / Math.max(0.1, store.zoom)
    const hit = S.project.hitTest(new S.Point(p.x, p.y), {
      fill: true,
      stroke: false,
      segments: false,
      tolerance: tol,
      match: (hr: paper.HitResult) => hr.item instanceof S.PointText,
    })
    return hit ? (hit.item as paper.PointText) : null
  }

  function beginTextTool(p: { x: number; y: number }, time: number) {
    if (!scope) return
    const S = scope
    const dbl = time - textLastClickTime < TEXT_DBL_MS
    textLastClickTime = time

    // 编辑中点击：结束当前编辑并选中（切 select），不再继续本手势
    if (textMode === 'edit' && textBox) {
      endTextEdit(true)
      return
    }

    // 双击已选中文字 → 重新编辑
    if (selected.size === 1) {
      const only = Array.from(selected)[0]
      if (only instanceof S.PointText && dbl && only.hitTest(new S.Point(p.x, p.y))) {
        pushHistory() // 重编辑：快照=改动前
        textPushed = true
        beginTextEdit(only, false)
        return
      }
    }

    const hit = hitTextEditTarget(p)
    if (hit) {
      // 点击已有文字 → 进入编辑
      pushHistory()
      textPushed = true
      beginTextEdit(hit, false)
      return
    }

    // 点空白：新建 PointText 进入编辑（对齐 Scratch：text 工具点空地=建新文字）
    pushHistory() // 新建：快照=创建前（含空 PointText 移除的回滚）
    textPushed = true
    const t = new S.PointText(new S.Point(p.x, p.y))
    t.content = ''
    beginTextEdit(t, true)
    // 初始光标：textarea 由 PaintArtboard 挂载后 focus
  }

  /** 切工具/切帧/卸载前收口（空删非空留；不强制切 select——尊重用户刚切到的工具） */
  function forceEndTextEdit() {
    if (textMode === 'edit') endTextEdit(false)
    textMode = 'none'
    textBox = null
    textPushed = false
    textDirty = false
    store.textEdit = null
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

  /**
   * 变换框手势起手（旋转 > 缩放 > 框内移动）。
   * 选择工具与「图形创建后自动选框」的其他绘制工具共用；命中返回 true。
   */
  function beginFrameGesture(p: { x: number; y: number }): boolean {
    if (selected.size === 0 || !selFrame) return false
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
      return true
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
      return true
    }
    if (hit.kind === 'move') {
      startMove(p)
      return true
    }
    return false
  }

  function beginSelect(p: { x: number; y: number }, shift: boolean, time = 0) {
    if (!scope) return

    // 文字编辑中点画布：先收口编辑（保留内容并选中），不继续本次选择手势
    if (textMode === 'edit') {
      endTextEdit(false)
      return
    }

    // 变换框手柄优先（旋转 > 缩放 > 框内移动），随后才是内容命中与框选
    // 框外：落到下方内容命中/框选（框选会 clearSelection 收起变换框）
    if (beginFrameGesture(p)) return

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
      // 双击 PointText → 进入文字编辑（对齐 Scratch text-tool SELECT_MODE 双击语义）
      if (
        !shift &&
        top instanceof scope!.PointText &&
        time - textLastClickTime < TEXT_DBL_MS &&
        store.activeTool === 'select'
      ) {
        textLastClickTime = time
        pushHistory() // 重编辑：快照=改动前
        textPushed = true
        beginTextEdit(top, false)
        return
      }
      textLastClickTime = time
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

  /** 选中内容的包围盒（画布像素坐标；位图代理不参与，避免撑满整帧） */
  function selectionBounds(): paper.Rectangle | null {
    let box: paper.Rectangle | null = null
    for (const item of selected) {
      if (item === bitmapRaster) continue
      const r = item.strokeBounds
      box = box ? box.unite(r) : r.clone()
    }
    return box
  }

  function continueSelect(p: { x: number; y: number }, shift: boolean) {
    if (selOp === 'move') {
      let dx = p.x - lastPointer.x
      let dy = p.y - lastPointer.y
      // 智能吸附：让选中内容的包围盒边缘/中心就近对齐候选线（地图编辑器注入，关闭时返回 null）
      const snap = (dx !== 0 || dy !== 0) ? options.smartSnap?.() ?? null : null
      if (snap) {
        const b = selectionBounds()
        if (b) {
          const off = snapRectOffset({
            left: b.x + dx,
            top: b.y + dy,
            right: b.x + b.width + dx,
            bottom: b.y + b.height + dy,
          }, snap.lines, snap.grid, snap.threshold)
          dx += off.dx
          dy += off.dy
        }
      }
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

  /**
   * 框选命中：按图形几何精确判断，而不是包围盒。
   * 包围盒会把“框外的大笔画”误带进来（例如框选空心笔画内部的一小块，整条大笔画被选中）。
   */
  function itemHitsRect(item: paper.Item, rect: paper.Rectangle, rectPath: paper.PathItem): boolean {
    // 组：任一子元素命中即视为整组命中（Group 整体选中，对齐 Scratch 对象语义）
    if (item.children && item.children.length > 0) {
      return item.children.some((child: paper.Item) => itemHitsRect(child, rect, rectPath))
    }
    const p = item as any
    // 文本等没有曲线的对象：退回包围盒
    if (typeof p.getCurves !== 'function') return rect.intersects(item.strokeBounds)
    const curves: paper.Curve[] = p.getCurves()
    if (curves.length === 0) return rect.intersects(item.strokeBounds)
    // 1) 图形穿过选框边界（真实交点）
    if (p.getIntersections(rectPath).length > 0) return true
    // 2) 图形整体落在选框内
    if (curves.some((c) => rect.contains(c.point1))) return true
    // 3) 选框整体落在填充图形内
    if (p.hasFill() && p.contains(rect.center)) return true
    // 4) 描边宽度压到选框（中心线在框外，但笔画很粗）
    if (p.hasStroke()) {
      const half = (p.getStrokeWidth() ?? 0) / 2
      if (half > 0) {
        const cx = rect.x + rect.width / 2
        const cy = rect.y + rect.height / 2
        const samples = [
          rect.topLeft, rect.topRight, rect.bottomLeft, rect.bottomRight,
          { x: cx, y: rect.y }, { x: cx, y: rect.y + rect.height },
          { x: rect.x, y: cy }, { x: rect.x + rect.width, y: cy },
          { x: cx, y: cy },
        ]
        for (const pt of samples) {
          const near = p.getNearestPoint(pt)
          if (near && Math.hypot(near.x - pt.x, near.y - pt.y) <= half) return true
        }
      }
    }
    return false
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
        const rectPath = new scope.Path.Rectangle({ rectangle: rect, insert: false })
        const layer = activeLayer()
        if (layer) {
          // 框选只圈矢量对象：位图代理是整帧，纳入会让每次框选都撑满全画板
          const hits = layer.children.filter((c) => c !== bitmapRaster && itemHitsRect(c, rect, rectPath))
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
    restoreFillPreview() // 悬停预览色不得进剪贴板
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
    penCancel() // 先丢弃进行中的半成品形状
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
    if (store.eyedropperActive) return // 拾色模式：点击由 PaintArtboard 冒泡消费取色
    const p = clientToArtboard(e)
    const tool = store.activeTool

    // 文字工具不 setPointerCapture：捕获会把后续指针/焦点事件钉在画布上，
    // textarea 刚挂载就被 blur → 单击后看不到输入光标
    if (tool !== 'text') {
      canvasRef.value?.setPointerCapture(e.pointerId)
    }

    // 图形创建后自动出现的选框（与位图模式统一）：形状/钢笔工具下也能直接操作选框，
    // 无需切换到选择工具；点击选框外 = 收起选框并继续用当前工具画下一个。
    // 己方手势进行中（正在拉直线/形状、正在落钢笔锚点）时不抢，避免打断绘制。
    if (isShapeTool(tool) && selected.size > 0 && selFrame) {
      const drawing = tool === 'pen' ? !!penPath : !!strokeStart
      if (!drawing) {
        if (beginFrameGesture(p)) return
        clearSelection()
      }
    }

    if (tool === 'brush') {
      beginBrush(p)
    } else if (tool === 'line' || tool === 'rect' || tool === 'ellipse') {
      beginShape(p, e.shiftKey)
    } else if (tool === 'pen') {
      penPress(p, e.detail)
    } else if (tool === 'fill') {
      fillPress(p)
    } else if (tool === 'eraser') {
      erasePushed = false
      eraseChanged = false
      eraseLast = p
      eraseAt(p)
    } else if (tool === 'select') {
      beginSelect(p, e.shiftKey, e.timeStamp)
    } else if (tool === 'reshape') {
      beginReshape(p, e.shiftKey, e.timeStamp)
    } else if (tool === 'text') {
      // 编辑中 textarea 吃指针事件；画布仍可点 = 结束编辑（下方 beginTextTool 处理）
      beginTextTool(p, e.timeStamp)
    }
    // eyedropper：由 PaintArtboard 冒泡消费
  }

  function onPointerMove(e: PointerEvent) {
    if (!scope) return
    // 自绘光标圈位置（hover 跟随，须在 buttons 判定前——不按键也要更新）
    if (
      store.mode === 'vector' &&
      (store.activeTool === 'eraser' || store.activeTool === 'brush')
    ) {
      const hp = clientToArtboard(e)
      store.cursorPos = { x: hp.x, y: hp.y }
    }
    // 变换框手势进行中（选择工具，或图形创建后自动选框的形状工具）：统一走选择手势
    if ((selOp === 'move' || selOp === 'scale' || selOp === 'rotate') && e.buttons === 1) {
      continueSelect(clientToArtboard(e), e.shiftKey)
      return
    }
    // 填充：悬停/按下拖动都走目标跟随预览（Scratch updateFillPreview 移动即预览，
    // 不区分按键状态——点空白还原也在此分支完成）
    if (store.mode === 'vector' && store.activeTool === 'fill') {
      fillMove(clientToArtboard(e))
      return
    }
    // 钢笔：橡皮筋预览锚跟随光标（不按键也要跟随）
    if (store.mode === 'vector' && store.activeTool === 'pen') {
      penMove(clientToArtboard(e))
      return
    }
    if (e.buttons !== 1) return
    const p = clientToArtboard(e)
    const tool = store.activeTool
    if (tool === 'brush') {
      continueBrush(p)
    } else if (tool === 'line' || tool === 'rect' || tool === 'ellipse') {
      continueShape(p, e.shiftKey)
    } else if (tool === 'eraser') {
      // 轨迹连续化：pointermove 事件间距可超过擦除圆直径（快速拖动一帧几十 px），
      // 逐事件点擦会在轨迹上留下永远擦不到的空洞——沿上一点按半径步长插值补擦
      // （与画笔引擎 fixedDistance 连续采样同等保证）
      const from = eraseLast ?? p
      const dx = p.x - from.x
      const dy = p.y - from.y
      const dist = Math.hypot(dx, dy)
      // 圆心距 = 半径/2（重叠 75%）：逐刀咬出的圆并集交界更密，断口包络更接近
      // 理想平滑带（步长=半径时交角明显，放大可见台阶）
      const step = Math.max(1, store.brushSize / 4)
      const n = Math.min(Math.ceil(dist / step), 64)
      if (n <= 1) {
        eraseAt(p)
      } else {
        for (let i = 1; i <= n; i++) {
          eraseAt({ x: from.x + (dx * i) / n, y: from.y + (dy * i) / n })
        }
      }
      eraseLast = p
    } else if (tool === 'select') {
      continueSelect(p, e.shiftKey)
    } else if (tool === 'reshape') {
      continueReshape(p, e.shiftKey, e.altKey)
    }
  }

  function onPointerUp(e: PointerEvent) {
    if (!scope) return
    const p = clientToArtboard(e)
    const tool = store.activeTool
    // 变换框手势收尾（形状工具操作自动选框时同样走这里，不能落进形状收尾）
    if (selOp === 'move' || selOp === 'scale' || selOp === 'rotate') {
      endSelect()
      return
    }
    if (tool === 'brush') {
      endBrush()
    } else if (tool === 'line' || tool === 'rect' || tool === 'ellipse') {
      endShape(p, e.shiftKey)
    } else if (tool === 'select') {
      endSelect()
    } else if (tool === 'reshape') {
      endReshape()
    } else if (tool === 'fill') {
      fillRelease()
    } else if (tool === 'eraser') {
      // 手势结束：整段只压了一步栈；有实际擦除才刷脏标与缩略图
      if (eraseChanged) markDirty()
      erasePushed = false
      eraseChanged = false
      eraseLast = null
    }
    selOp = 'none'
  }

  // ─── 光标 ───

  function updateCursor() {
    const canvas = canvasRef.value
    if (!canvas) return
    const tool = store.activeTool
    if (tool === 'brush' || tool === 'eraser') {
      // 原生光标隐藏，由 overlay 自绘圈接管——dataURL 圆圈光标在大 zoom 下
      // 尺寸超浏览器上限会直接失效（放大画布后光标消失的根因），Scratch 同为画布内圈
      canvas.style.cursor = 'none'
    } else if (
      tool === 'line' ||
      tool === 'rect' ||
      tool === 'ellipse' ||
      tool === 'pen' ||
      tool === 'fill' ||
      tool === 'text'
    ) {
      canvas.style.cursor = 'crosshair'
    } else {
      canvas.style.cursor = 'default'
    }
  }

  function onPointerLeave() {
    store.cursorPos = null
    if (!fillDown) restoreFillPreview() // 悬停未按下 → 离开还原；按下中走指针捕获 + 拖动分支
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

    // 自定义视口（地图画布）：矩阵与裁剪由适配器提供，逻辑坐标=图片绘制画布像素
    if (options.viewport) {
      const m = options.viewport.getViewMatrix(sw, sh)
      view.matrix = new scope.Matrix(m.a, m.b, m.c, m.d, m.tx, m.ty)
      canvas.style.clipPath = options.viewport.getClipPath(sw, sh) ?? ''
      priv._needsUpdate = true
      view.update()
      return
    }

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
    canvas.addEventListener('pointerleave', onPointerLeave)
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
      canvas.removeEventListener('pointerleave', onPointerLeave)
      canvas.style.clipPath = ''
      store.cursorPos = null
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
    penDiscard()
    blobPath = null
    blobLast = null
    brushStartPt = null
    clipboardItems = []
    frameJson = []
    frameRaster = []
    fillPreview = null // scope 已销毁，仅丢引用（无须还原）
    fillDown = false
    fillPushed = false
    clearReshapeOverlay()
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
    () => {
      restoreFillPreview() // 切工具/缩放 → 悬停态失效还原（再次移入会重新预览）
      if (store.activeTool !== 'pen') penCancel() // 切走钢笔：丢弃未闭合的半成品
      else if (penPath) syncPenState() // 缩放改变收尾命中半径 → 重算首锚热点状态
      updateCursor()
      // 切走文字/选择工具时收口编辑会话（空删非空留）
      if (textMode === 'edit' && store.activeTool !== 'text' && store.activeTool !== 'select') {
        forceEndTextEdit()
      }
    }
  )

  // 塑形工具互斥：进入=收起变换框、显示已选对象的锚点；离开=清锚点显示并恢复变换框
  watch(
    () => store.activeTool,
    (t, old) => {
      // 隐藏中的引擎不得改写共享选中/塑形投影（另一方编辑器正持有同一个 store）
      if (!isViewVisible()) return
      // 创建后自动选框：离开形状工具（且不是切到选择/塑形）= 收起选框（对齐位图模式语义）
      if (
        old !== t &&
        isShapeTool(old) &&
        t !== 'select' &&
        t !== 'reshape' &&
        selected.size > 0
      ) {
        clearSelection()
      }
      if (t !== 'reshape') {
        clearReshapeOverlay()
        syncVectorSelBox() // 切回 select 等：reshape 期间被抑制的变换框按选中状态重建
      } else {
        selFrame = null
        store.vectorSelBox = null
        syncReshapePts()
      }
    }
  )

  // 模式切换：离开矢量收起选中并摘除代理（位图层回到位图模式编辑）；
  // 进入矢量时同步代理（此时位图引擎 mode watch/commit 已先行收口，DOM 即最终像素）
  watch(() => store.mode, (m) => {
    restoreFillPreview()
    forceEndTextEdit() // 编辑态不得跨模式残留
    if (m !== 'vector') {
      penCancel() // 离开矢量：丢弃未闭合的半成品
      clearSelection()
      removeBitmapRaster()
    } else {
      syncBitmapRaster()
      syncVectorContentFlag()
    }
  })

  onBeforeUnmount(() => {
    detach()
    forceEndTextEdit()
    store.vectorSelBox = null
    store.vectorSelectedCount = 0
    store.vectorCanUngroup = false
    store.vectorCanUndo = false
    store.vectorCanRedo = false
    store.hasVectorClipboard = false
    store.vectorContent = false
  })

  /** 当前 project 的 JSON 快照（地图矢量图层保存/切换用） */
  function getProjectJson(): string | null {
    if (!scope) return null
    penCancel() // 地图暂存/保存前不保留半成品形状
    const layer = scope.project.activeLayer
    const live = layer ? layer.children.some(c => c !== bitmapRaster) : false
    return live ? snapshotForGesture() : null
  }

  /** 载入 JSON 场景（清空撤销栈，用于切回矢量图层时恢复） */
  function loadProjectJson(json: string | null) {
    if (!scope) return
    if (json) {
      restoreFrom(json)
    } else {
      clearSelection()
      penDiscard()
      scope.project.clear()
      if (scope.project.layers.length === 0) new scope.Layer()
      scope.project.activeLayer?.activate()
      scope.view.update()
      syncVectorContentFlag()
    }
    undoStack = []
    redoStack = []
    syncHistoryFlags()
    hooks.onContentChanged()
  }

  return {
    undo,
    redo,
    clearLayer,
    /** 视口/图片变换变化后强制重同步（地图适配器用） */
    refreshView: syncVectorView,
    getProjectJson,
    loadProjectJson,
    isReady: () => !!scope,
    deleteSelection,
    copySelection,
    cutSelection,
    pasteClipboard,
    flipSelection,
    groupSelection,
    ungroupSelection,
    layerMove,
    /** 钢笔：取消进行中的路径（返回是否有路径被取消） */
    penCancel: () => penCancel(),
    /** 钢笔：收尾闭合当前路径（返回是否成形） */
    penFinish,
    /** 收起选中（Esc 路由；清 selected 与变换框） */
    deselect: clearSelection,
    /** 塑形：选中锚点曲线化（顶栏「曲线」按钮） */
    curveSelectedPoints,
    /** 塑形：选中锚点折线化（顶栏「折线」按钮） */
    pointSelectedPoints,
    /** 塑形：方向键微移（返回是否已处理） */
    reshapeNudge,
    /** 塑形：删除选中锚点（返回是否已处理，优先于对象删除） */
    reshapeDeletePoints,
    /** 塑形：Escape 分级清除（先锚点后对象，返回是否已处理） */
    reshapeEscape,
    syncActiveFrame,
    onFrameAdded,
    onFrameRemoved,
    moveFrame,
    onLoadFrames,
    beforeExport,
    clearAllForBake,
    getFrameRaster,
    /** 按缩略图尺寸直绘矢量内容（不按全分辨率栅格化） */
    drawProjectToThumbnail,
    hasVectorContent,
    exportActiveFrame,
    /** 矢量剪贴板是否有内容（供顶栏粘贴按钮） */
    hasClipboard: () => clipboardItems.length > 0,
    /** 文字编辑：textarea input 事件（PaintArtboard 转发） */
    textEditInput: onTextEditInput,
    /** 文字编辑：结束编辑（Esc/blur/外部调用；空删非空留并切选择） */
    textEditCommit: () => endTextEdit(),
    /** 文字编辑是否进行中 */
    isTextEditing: () => textMode === 'edit',
  }
}
