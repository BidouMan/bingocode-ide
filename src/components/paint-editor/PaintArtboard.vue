<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { usePaintStore } from '../../stores/paint'
import { useBitmapCanvas } from './composables/useBitmapCanvas'
import { usePaperScope } from './composables/usePaperScope'
import { ensurePaintFont } from './utils/paintFont'
import iconUndo from '../../assets/icons/undo.svg'
import iconRedo from '../../assets/icons/redo.svg'
import iconZoomOut from '../../assets/icons/reduce-one.svg'
import iconZoomIn from '../../assets/icons/add-one.svg'

const store = usePaintStore()

const stageRef = ref<HTMLDivElement>()
const bitmapCanvas = ref<HTMLCanvasElement>()
const vectorCanvas = ref<HTMLCanvasElement>()

// 位图绘制引擎（工具状态机/撤销重做/光标/多帧像素/选区），canvas 就绪后自动绑定指针事件
// 帧操作函数取别名：下方包装器编排双引擎（矢量槽位与位图像素数组保持下标对齐）
const {
  undo: bitmapUndo, redo: bitmapRedo, clear: bitmapClear, cropToContent,
  addFrame: bitmapAddFrame, removeFrame: bitmapRemoveFrame, moveFrame: bitmapMoveFrame,
  loadFrames: bitmapLoadFrames, getFrameCanvases: bitmapGetFrameCanvases, getFrameNames,
  copySelection, pasteClipboard, deleteSelection, flipSelection, commitAndDeselect,
  replacePixelsForBake: bitmapBakeReplacePixels,
  transformWholeFrame: bitmapTransformFrame,
  getCanvas,
  textEditInput: bitmapTextInput, textEditCommit: bitmapTextCommit,
  penFinish: bitmapPenFinish, penCancel: bitmapPenCancel,
} = useBitmapCanvas(bitmapCanvas)

// 矢量绘制引擎（paper 场景图/对象操作/多帧 JSON 快照），坐标与位图同源（clientToArtboard）
const vectorEngine = usePaperScope(vectorCanvas, bitmapCanvas, {
  // 帧切换：新旧两帧缩略图都重新合成（旧帧由位图引擎先写了纯位图缩略图，此处补矢量层）
  onFrameSwitched: (oldIndex, newIndex) => {
    regenThumb(oldIndex)
    regenThumb(newIndex)
  },
  // 矢量内容变更：刷新活动帧缩略图
  onContentChanged: () => regenThumb(),
  // 位图代理（Scratch 同款 image 对象）：矢量场景 → 位图层真源的桥
  bitmapLayer: {
    getFrame: () => bitmapCanvas.value ?? null,
    transformFrame: (m) => bitmapTransformFrame(m),
    clearFrame: () => bitmapClear(),
  },
})

/**
 * 合成第 index 帧缩略图（位图层 + 矢量层叠加，高 44px 等比，与位图引擎 updateThumb 同规格）。
 * 活动帧位图取 DOM canvas（真源）；非活动帧取位图引擎离屏数组（需 flush 活动帧，模式切换后安全）。
 */
function regenThumb(index = store.activeFrameIndex) {
  const meta = store.frames[index]
  if (!meta) return
  const vec = vectorEngine.getFrameRaster(index)
  const isActive = index === store.activeFrameIndex
  // 非活动帧且无矢量内容：位图引擎已写过缩略图，无需覆盖
  if (!vec && !isActive) return
  const bmp = isActive ? bitmapCanvas.value : bitmapGetFrameCanvases()[index]
  if (!bmp || bmp.height === 0) return
  const th = 44
  const tw = Math.max(1, Math.round((bmp.width / bmp.height) * th))
  const tc = document.createElement('canvas')
  tc.width = tw
  tc.height = th
  const tctx = tc.getContext('2d')!
  tctx.imageSmoothingEnabled = true
  tctx.drawImage(bmp, 0, 0, tw, th)
  if (vec) tctx.drawImage(vec, 0, 0, tw, th)
  meta.thumb = tc.toDataURL('image/png')
}

// ─── 拾色放大镜（Scratch 同款）：激活后圆形镜片跟随光标，最近邻放大光标下像素，中心准心 ───
const LENS_SIZE = 92 // 镜片直径（屏幕 px，恒定不随画板缩放）
const LENS_ZOOM = 10 // 放大倍率（镜内 1 个画板逻辑像素 = 10 镜内 px）
const pickLensRef = ref<HTMLCanvasElement>()
/** 镜中心相对 stage 的屏幕坐标；null=隐藏（未激活/光标离开舞台） */
const pickLensPos = ref<{ x: number; y: number } | null>(null)
/** 合成缓存（激活时构建一次：拾色期间内容不变，避免 pointermove 高频重渲染矢量层） */
let pickComposite: HTMLCanvasElement | null = null

/** 位图层⊕矢量层合成一张离屏图（与显示/保存同序） */
function buildPickComposite(): HTMLCanvasElement | null {
  const bc = bitmapCanvas.value
  if (!bc) return null
  const w = store.artboardWidth
  const h = store.artboardHeight
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  const ctx = c.getContext('2d', { willReadFrequently: true })
  if (!ctx) return null
  ctx.drawImage(bc, 0, 0, w, h)
  const vec = vectorEngine.getFrameRaster(store.activeFrameIndex)
  if (vec) ctx.drawImage(vec, 0, 0, w, h)
  return c
}

/** 鼠标 client 坐标 → 画板逻辑坐标 */
function clientToArtboard(clientX: number, clientY: number): { x: number; y: number } | null {
  const bc = bitmapCanvas.value
  if (!bc) return null
  const rect = bc.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0) return null
  const w = store.artboardWidth
  const h = store.artboardHeight
  return {
    x: ((clientX - rect.left) / rect.width) * w,
    y: ((clientY - rect.top) / rect.height) * h,
  }
}

/** 把镜片画到 canvas（位置已就绪；lens 由模板 v-if 挂载） */
function paintPickLens(lens: HTMLCanvasElement, p: { x: number; y: number }) {
  if (!pickComposite) return
  // dpr 适配：物理像素绘制，CSS 尺寸恒定
  const dpr = window.devicePixelRatio || 1
  const px = Math.round(LENS_SIZE * dpr)
  if (lens.width !== px) {
    lens.width = px
    lens.height = px
  }
  const ctx = lens.getContext('2d')
  if (!ctx) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.imageSmoothingEnabled = false
  ctx.clearRect(0, 0, LENS_SIZE, LENS_SIZE)
  const src = LENS_SIZE / LENS_ZOOM
  ctx.drawImage(pickComposite, p.x - src / 2, p.y - src / 2, src, src, 0, 0, LENS_SIZE, LENS_SIZE)
}

/** 重绘镜片：先写位置（v-if 挂载 canvas），首次 move 时 canvas 未挂载则 nextTick 补画 */
function drawPickLens(clientX: number, clientY: number) {
  const stage = stageRef.value
  if (!stage || !pickComposite) return
  const p = clientToArtboard(clientX, clientY)
  if (!p) return
  const sr = stage.getBoundingClientRect()
  // 镜中心 = 光标位置：准心指哪取哪（中心采样点即光标像素）
  pickLensPos.value = {
    x: clientX - sr.left,
    y: clientY - sr.top,
  }
  const lens = pickLensRef.value
  if (!lens) {
    // 首次 move：canvas 因 v-if 尚未挂载，DOM 更新后补画一帧
    nextTick(() => {
      const l = pickLensRef.value
      if (l && store.eyedropperActive && pickLensPos.value) paintPickLens(l, p)
    })
    return
  }
  paintPickLens(lens, p)
}

function onStagePointerLeavePick() {
  if (store.eyedropperActive) pickLensPos.value = null
}

// 激活/退出拾色：构建/释放合成缓存（首次 move 前镜不显示）
watch(
  () => store.eyedropperActive,
  (v) => {
    pickComposite = v ? buildPickComposite() : null
    pickLensPos.value = null
  }
)

// ─── 缩放/平移（与 SpriteEditorView 同款交互：滚轮以光标为锚缩放、中键拖拽平移、双击复位）───
const isPanning = ref(false)
let panStartX = 0
let panStartY = 0
let panBaseX = 0
let panBaseY = 0

function onStageWheel(e: WheelEvent) {
  const rect = stageRef.value?.getBoundingClientRect()
  if (!rect) return
  // 鼠标相对舞台中心的偏移
  const mouseX = e.clientX - rect.left - rect.width / 2
  const mouseY = e.clientY - rect.top - rect.height / 2

  const oldZoom = store.zoom
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  const newZoom = Math.min(32, Math.max(0.1, oldZoom * delta))

  // 以鼠标位置为中心缩放：保持鼠标下的点不动
  store.panX = mouseX - (mouseX - store.panX) * (newZoom / oldZoom)
  store.panY = mouseY - (mouseY - store.panY) * (newZoom / oldZoom)
  store.setZoom(newZoom)
}

function onStageMouseDown(e: MouseEvent) {
  if (e.button === 1) {
    e.preventDefault()
    e.stopPropagation()
    isPanning.value = true
    panStartX = e.clientX
    panStartY = e.clientY
    panBaseX = store.panX
    panBaseY = store.panY
  }
}

function onStageMouseMove(e: MouseEvent) {
  if (store.eyedropperActive) {
    drawPickLens(e.clientX, e.clientY)
    return
  }
  if (!isPanning.value) return
  store.panX = panBaseX + (e.clientX - panStartX)
  store.panY = panBaseY + (e.clientY - panStartY)
}

function onGlobalMouseUp(e: MouseEvent) {
  if (e.button === 1) {
    isPanning.value = false
  }
}

function onStageDblClick() {
  store.resetView()
}

onMounted(() => {
  window.addEventListener('mouseup', onGlobalMouseUp)
  ensurePaintFont() // 预加载绘制字体（文字工具首次使用前就绪）
})

onUnmounted(() => {
  window.removeEventListener('mouseup', onGlobalMouseUp)
})

// ─── 画板几何 ───
// 100% 缩放且未平移时不写 transform：恒等 transform 也会把元素提升为合成图层，
// WebKit 下可能导致 image-rendering: pixelated 被平滑缩放路径覆盖（显示发糊）
const artboardStyle = computed(() => {
  const style: Record<string, string> = {
    width: `${store.artboardWidth}px`,
    height: `${store.artboardHeight}px`,
  }
  if (store.zoom !== 1 || store.panX !== 0 || store.panY !== 0) {
    style.transform = `translate(${store.panX}px, ${store.panY}px) scale(${store.zoom})`
  }
  return style
})

// ─── 选区蚂蚁线（框选拖动预览；有浮动选区时改由 SVG 变换框渲染）───
const selectionStyle = computed(() => {
  const r = store.selection
  if (!r || r.w <= 0 || r.h <= 0) return null
  return {
    left: `${r.x}px`,
    top: `${r.y}px`,
    width: `${r.w}px`,
    height: `${r.h}px`,
  }
})

// ─── 变换框 SVG 矢量 UI（独立图层：不碰图像像素、任意缩放平滑无锯齿）───
// 选区主题色：在这里修改选框颜色（SEL=框线/旋转柄主色，SEL_DEEP=手柄描边；十六进制）
const SEL = '#818cf8' // 主色：框线芯、旋转柄（rgb 129,140,248）
const SEL_DEEP = '#6366f1' // 同系加深：手柄/旋转点描边（白底上保对比）
const boxStrokeInv = computed(() => 1 / Math.max(0.1, store.zoom))
const boxHandleSize = computed(() => 7 / Math.max(0.1, store.zoom))
const boxPoints = computed(() => {
  const box = store.transformBox
  if (!box) return ''
  return box.corners.map(c => `${c.x},${c.y}`).join(' ')
})
/** 矢量选中变换框（定向矩形，可随旋转手势带角度） */
const vectorBoxPoints = computed(() => {
  const box = store.vectorSelBox
  if (!box) return ''
  return box.corners.map(c => `${c.x},${c.y}`).join(' ')
})

// ─── 塑形锚点 overlay（SVG，屏幕尺寸恒定：8px 锚点圆点 / 6.5px 手柄圆点）───
const boxPtSize = computed(() => 8 / Math.max(0.1, store.zoom))
const boxHandleDot = computed(() => 6.5 / Math.max(0.1, store.zoom))

// ─── 钢笔（自定义形状）进行中预览 overlay ───
// 固定配色：预览虚线/锚点不跟随颜色面板（与变换框同色系，白底锚点在任意底色上可见）
const PEN = '#818cf8' // 预览线 / 收尾热点环
const PEN_DEEP = '#6366f1' // 锚点方块描边
const penStrokeW = computed(() => 1.4 / Math.max(0.1, store.zoom))
const penDashArray = computed(() => {
  const z = Math.max(0.1, store.zoom)
  return `${5 / z} ${3 / z}`
})
const penAnchorSize = computed(() => 6.5 / Math.max(0.1, store.zoom))
/** 首锚收尾热点半径（与引擎 10px 命中半径视觉对齐，屏幕恒定） */
const penCloseRingR = computed(() => 9 / Math.max(0.1, store.zoom))
/** 预览折线：已落锚点 + 橡皮筋末端（光标） */
const penPolyline = computed(() => {
  const ps = store.penState
  if (!ps) return ''
  const pts = ps.cursor ? [...ps.anchors, ps.cursor] : ps.anchors
  return pts.map((p) => `${p.x},${p.y}`).join(' ')
})

/**
 * 画笔/橡皮自绘光标圈（矢量模式，Scratch 同款画布内圈）：
 * 位于 overlay（与 artboard 同 transform）→ 位置用画板逻辑坐标、
 * 直径=brushSize 逻辑尺寸，随视图缩放屏幕尺寸自动正确（dataURL 光标超浏览器上限会失效）。
 * 用 SVG 双圆而非 div+box-shadow：阴影环在 translate 亚像素定位下会断裂成细小黑线段。
 */
const brushCursorStyle = computed(() => {
  const t = store.activeTool
  if (t !== 'eraser' && t !== 'brush') return null
  const c = store.cursorPos
  if (!c) return null
  return {
    left: `${c.x}px`,
    top: `${c.y}px`,
  }
})

function focusStage() {
  stageRef.value?.focus()
}

// ─── 浮动视图工具条（画布右下，对齐代码编辑器 ide-float-bar 风格）：撤销/重做/缩放 ───
const floatCanUndo = () => (store.mode === 'vector' ? store.vectorCanUndo : store.canUndo)
const floatCanRedo = () => (store.mode === 'vector' ? store.vectorCanRedo : store.canRedo)
// 固定 ±10 个百分点步进（整数百分比防浮点漂移：100→110→120，来回点可精确回到原值）
function onZoomIn() {
  store.setZoom(Math.round((store.zoom + 0.1) * 100) / 100)
}
function onZoomOut() {
  store.setZoom(Math.round((store.zoom - 0.1) * 100) / 100)
}

// ─── 拾色（吸管）：从合成缓存读点击点像素色，写入目标通道后退出 ───
function onStagePointerDownForPick(e: PointerEvent) {
  // 文字编辑中不抢焦点（stage.focus 会 blur 掉 textarea → 光标消失）
  if (!store.textEdit) focusStage()
  if (!store.eyedropperActive) return
  e.preventDefault()
  e.stopPropagation()
  const bc = bitmapCanvas.value
  const comp = pickComposite ?? buildPickComposite()
  if (!bc || !comp) {
    store.endEyedropper()
    return
  }
  const rect = bc.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0) {
    store.endEyedropper()
    return
  }
  const w = store.artboardWidth
  const h = store.artboardHeight
  const x = Math.floor(((e.clientX - rect.left) / rect.width) * w)
  const y = Math.floor(((e.clientY - rect.top) / rect.height) * h)
  const ctx = comp.getContext('2d', { willReadFrequently: true })
  if (!ctx) {
    store.endEyedropper()
    return
  }
  const d = ctx.getImageData(Math.min(Math.max(x, 0), w - 1), Math.min(Math.max(y, 0), h - 1), 1, 1).data
  // 一次性取色：结束会话并回退到取色前的工具（面板吸管则不动工具）
  store.endEyedropper()
  if (d[3] >= 16) {
    const hex =
      '#' +
      [d[0], d[1], d[2]]
        .map((v) => v.toString(16).padStart(2, '0'))
        .join('')
    if (store.eyedropperTarget === 'stroke') store.strokeColor = hex
    else store.fillColor = hex
  }
}

/** 快捷键：按模式分发——矢量=对象操作；位图=选区操作 */
function onStageKeydown(e: KeyboardEvent) {
  const mod = e.ctrlKey || e.metaKey

  // 文字编辑中：Esc 结束编辑；其余键交给 textarea（本 handler 不应收到——
  // 但 textarea blur/合成事件可能冒泡到 stage，防御性放行）
  if (store.textEdit) {
    if (e.key === 'Escape') {
      commitTextEdit()
      e.preventDefault()
    }
    return
  }

  // 拾色模式：Esc 取消（优先于一切快捷键）；回退到取色前的工具
  if (store.eyedropperActive) {
    store.endEyedropper()
    e.preventDefault()
    return
  }

  if (store.mode === 'vector') {
    // 钢笔：Esc 取消半成品、Enter 直接闭合收尾
    if (store.activeTool === 'pen') {
      if (e.key === 'Escape' && vectorEngine.penCancel()) {
        e.preventDefault()
        return
      }
      if (e.key === 'Enter' && vectorEngine.penFinish()) {
        e.preventDefault()
        return
      }
    }
    if (e.key === 'Escape') {
      // 塑形：先清锚点选择再清对象选择；其余收起矢量选中
      if (!vectorEngine.reshapeEscape()) vectorEngine.deselect()
      e.preventDefault()
    } else if (e.key === 'Delete' || e.key === 'Backspace') {
      // 塑形有锚点选中时删锚点，否则删整个对象
      if (vectorEngine.reshapeDeletePoints()) {
        e.preventDefault()
      } else if (store.vectorSelectedCount > 0) {
        vectorEngine.deleteSelection()
        e.preventDefault()
      }
    } else if (e.key.startsWith('Arrow')) {
      // 塑形方向键微移（优先锚点；按住 repeat 合并为一步撤销）
      if (vectorEngine.reshapeNudge(e.key, e.repeat)) e.preventDefault()
    } else if (mod && (e.key === 'c' || e.key === 'C')) {
      vectorEngine.copySelection()
      e.preventDefault()
    } else if (mod && (e.key === 'x' || e.key === 'X')) {
      vectorEngine.cutSelection()
      e.preventDefault()
    } else if (mod && (e.key === 'v' || e.key === 'V')) {
      if (store.hasVectorClipboard) {
        vectorEngine.pasteClipboard()
        e.preventDefault()
      }
    }
    return
  }

  // 位图模式钢笔：Enter 闭合收尾、Esc 丢弃半成品（与矢量模式一致）
  if (store.activeTool === 'pen') {
    if (e.key === 'Escape' && bitmapPenCancel()) {
      e.preventDefault()
      return
    }
    if (e.key === 'Enter' && bitmapPenFinish()) {
      e.preventDefault()
      return
    }
  }

  if (e.key === 'Escape') {
    commitAndDeselect()
    e.preventDefault()
  } else if (e.key === 'Delete' || e.key === 'Backspace') {
    if (store.selection) {
      deleteSelection()
      e.preventDefault()
    }
  } else if (mod && (e.key === 'c' || e.key === 'C')) {
    if (store.selection) {
      copySelection()
      e.preventDefault()
    }
  } else if (mod && (e.key === 'v' || e.key === 'V')) {
    if (store.hasClipboard) {
      pasteClipboard()
      e.preventDefault()
    }
  } else if (mod && (e.key === 'x' || e.key === 'X')) {
    if (store.selection) {
      copySelection()
      deleteSelection()
      e.preventDefault()
    }
  }
}

// ─── 双引擎编排：帧操作/保存/顶栏动作按模式路由 ───

/**
 * 新建/复制帧：先对齐矢量槽位，再走位图引擎。
 * 不在此显式 sync：两引擎的 activeFrameIndex watcher 按注册序（位图先、矢量后）在同一 flush 中
 * 依次执行——位图先 flush/load 完成 DOM 切换，矢量再导出/导入并经 onFrameSwitched 合成新旧帧
 * 缩略图（若此处提前同步，位图 DOM 尚未切换，缩略图会拿旧帧位图 + 新帧矢量错配合成）。
 */
function addFrame(duplicate: boolean) {
  commitTextEdit()
  const newIndex = store.frames.length
  vectorEngine.onFrameAdded(duplicate, newIndex)
  bitmapAddFrame(duplicate)
}

/**
 * 删除帧：矢量槽位先行（histMap 删除须在位图 splice store.frames 之前取到帧 id），
 * 位图引擎内部同步完成 DOM 切换后，矢量显式 sync（删活动帧时 activeFrameIndex 可能不变、
 * watcher 不触发，必须显式；hooks 内完成新旧帧缩略图合成）。
 */
function removeFrame(index: number): boolean {
  if (store.frames.length <= 1 || index < 0 || index >= store.frames.length) return false
  commitTextEdit()
  vectorEngine.onFrameRemoved(index)
  const ok = bitmapRemoveFrame(index)
  if (ok) vectorEngine.syncActiveFrame()
  return ok
}

/**
 * 拖拽排序：双引擎帧槽同步换位，落点帧成为当前编辑帧。
 * 先收口文字编辑与位图浮动选区，避免像素/变换框滞留在旧下标。
 */
function moveFrame(from: number, to: number) {
  if (store.frames.length <= 1 || from === to) return
  if (from < 0 || to < 0 || from >= store.frames.length || to >= store.frames.length) return
  commitTextEdit()
  commitAndDeselect()
  vectorEngine.moveFrame(from, to)
  bitmapMoveFrame(from, to)
  store.selectFrame(to)
}

/** 整体载入（编辑既有角色）：既有帧均为纯位图，矢量槽重置 */
function loadFrames(
  canvases: HTMLCanvasElement[],
  names: (string | null)[],
  activeIndex: number
) {
  commitTextEdit() // 载入前收口编辑中的文字
  bitmapLoadFrames(canvases, names, activeIndex)
  vectorEngine.onLoadFrames(canvases.length)
}

/**
 * 保存取帧：位图帧 + 矢量层叠加。
 * 先让矢量引擎固化活动帧快照（beforeExport 内部 flush 渲染并重导入保持编辑态），
 * 再对每帧把矢量层 drawImage 到位图帧副本上（不污染位图引擎的源像素）。
 */
function getFrameCanvasesComposed(): HTMLCanvasElement[] {
  commitTextEdit() // 导出前收口编辑中的文字（避免 textarea 内容未落进场景/像素）
  vectorEngine.beforeExport()
  const bases = bitmapGetFrameCanvases()
  if (!vectorEngine.hasVectorContent()) return bases
  const w = store.artboardWidth
  const h = store.artboardHeight
  return bases.map((base, i) => {
    const vec = vectorEngine.getFrameRaster(i)
    if (!vec) return base
    const out = document.createElement('canvas')
    out.width = base.width
    out.height = base.height
    const ctx = out.getContext('2d')!
    ctx.drawImage(base, 0, 0)
    ctx.drawImage(vec, 0, 0, w, h)
    return out
  })
}

/** 顶栏撤销/重做：按模式路由到对应引擎栈 */
function undoActive() {
  commitTextEdit()
  if (store.mode === 'vector') vectorEngine.undo()
  else bitmapUndo()
}

function redoActive() {
  commitTextEdit()
  if (store.mode === 'vector') vectorEngine.redo()
  else bitmapRedo()
}

/** 清空：按模式清当前工作层 */
function clearActive() {
  commitTextEdit()
  if (store.mode === 'vector') vectorEngine.clearLayer()
  else bitmapClear()
}

/** 顶栏复制/粘贴/删除/翻转：按模式路由 */
function copyActive() {
  if (store.mode === 'vector') vectorEngine.copySelection()
  else copySelection()
}

function pasteActive() {
  if (store.mode === 'vector') vectorEngine.pasteClipboard()
  else pasteClipboard()
}

function deleteActive() {
  if (store.mode === 'vector') vectorEngine.deleteSelection()
  else deleteSelection()
}

function flipActive(axis: 'h' | 'v') {
  if (store.mode === 'vector') vectorEngine.flipSelection(axis)
  else flipSelection(axis)
}

/** 位图浮动选区收口（模式切换时调用，避免浮动选区跨模式残留） */
function commitBitmapSelection() {
  commitAndDeselect()
}

// 模式切换：离开位图先烘焙浮动选区（矢量侧清选由引擎内部 mode watch 处理）
watch(() => store.mode, () => {
  bitmapPenCancel() // 未闭合的钢笔半成品不跨模式残留
  commitTextEdit() // 编辑态不得跨模式残留（引擎内也有兜底，此处保证顺序在 commitAndDeselect 前）
  commitAndDeselect()
})

// ─── 文字编辑 textarea 覆盖层 ───
const textAreaRef = ref<HTMLTextAreaElement>()
/**
 * IME 组词进行中（拼音输入法 composition）：
 * 组词期间 input 事件会带中间态（如 "ni" / "nih"），若此时同步进 PointText，
 * 会把每个音节都当成最终文本提交 → 出现 "nnini'hni..." 乱码。
 * 组词结束（compositionend）才把最终值写入引擎。
 */
const textComposing = ref(false)

/** 离屏测宽 ctx（组词中引擎不收中间态，UI 层自量 textarea 内容撑开边框） */
let measureCtx: CanvasRenderingContext2D | null = null

/**
 * 按当前字符串测内容框（画板逻辑坐标）。
 * 组词期间引擎不更新 internalBounds，必须在 UI 层自己量——否则边框停在初始光标宽，字全挤在一起。
 */
function measureTextContentSize(
  value: string,
  fontSize: number,
  lineHeightRatio: number
): { w: number; h: number } {
  if (!measureCtx) {
    measureCtx = document.createElement('canvas').getContext('2d')
  }
  const lh = fontSize * lineHeightRatio
  const lines = value.split('\n')
  if (!measureCtx || !value) {
    return { w: fontSize * 0.5, h: lh } // 空：一个光标位
  }
  measureCtx.font = `500 ${fontSize}px "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif`
  let maxW = 0
  for (const line of lines) {
    // 空行按一个空格宽计（保持多行高度正确）
    maxW = Math.max(maxW, measureCtx.measureText(line || ' ').width)
  }
  return { w: Math.max(maxW, 1), h: Math.max(lines.length, 1) * lh }
}

/** 用 DOM 当前值刷新边框尺寸（input/composition 全程调用，不依赖引擎） */
function refreshTextEditSizeFromDom() {
  const te = store.textEdit
  const el = textAreaRef.value
  if (!te || !el) return
  const size = measureTextContentSize(el.value, te.fontSize, te.lineHeight)
  // 幅度阈值防高频无谓响应式写入
  if (Math.abs(te.width - size.w) > 0.5 || Math.abs(te.height - size.h) > 0.5) {
    te.width = size.w
    te.height = size.h
  }
}

/** textarea 样式：画板逻辑坐标系内定位（随 artboardStyle 父 transform 缩放），尺寸动态贴合内容 */
const textEditStyle = computed(() => {
  const te = store.textEdit
  if (!te) return null
  const base: Record<string, string> = {
    fontSize: `${te.fontSize}px`,
    lineHeight: String(te.lineHeight),
    color: te.color,
    left: `${te.x}px`,
    top: `${te.y}px`,
    // 动态贴合内容（引擎按 internalBounds/measureText 写入；+1 防末字裁切，对齐 Scratch）
    width: `${Math.max(te.width, 1) + 1}px`,
    height: `${Math.max(te.height, 1)}px`,
  }
  // 矢量：附加线性 matrix（旋转/缩放）；位图无 matrix
  if (te.matrix) {
    base.transform = te.matrix
    base.transformOrigin = te.transformOrigin
  }
  return base
})

function commitTextEdit() {
  if (!store.textEdit) return
  if (store.mode === 'vector') vectorEngine.textEditCommit()
  else bitmapTextCommit()
}

/** 把 textarea 当前值同步进引擎（组词中跳过） */
function syncTextAreaToEngine(value: string) {
  if (store.mode === 'vector') vectorEngine.textEditInput(value)
  else bitmapTextInput(value)
}

function onTextAreaInput(e: Event) {
  const el = e.target as HTMLTextAreaElement
  // 边框始终跟随 DOM 实际内容（含 IME 中间态拼音）
  refreshTextEditSizeFromDom()
  // 组词中内容不同步：中间态只活在 textarea，不进 PointText
  if (textComposing.value) return
  syncTextAreaToEngine(el.value)
}

function onTextAreaCompositionStart() {
  textComposing.value = true
}

function onTextAreaCompositionEnd(e: CompositionEvent) {
  textComposing.value = false
  const el = e.target as HTMLTextAreaElement
  refreshTextEditSizeFromDom()
  // 组词结束：最终值（可能含多字）一次性写入引擎
  syncTextAreaToEngine(el.value)
}

function onTextAreaKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.preventDefault()
    commitTextEdit()
  }
  // 阻止键事件冒泡到 stage 快捷键（Delete/方向键等）
  e.stopPropagation()
}

// 出现编辑会话 → textarea 聚焦（Scratch element.focus preventScroll 同款）。
// 不用 :value 受控绑定：组词期间受控回写会打断 IME，改为挂载时一次性写入初值。
// 双保险：nextTick + rAF——单靠 nextTick 时，pointerdown 默认焦点转移可能后到又抢走。
watch(() => store.textEdit, (te) => {
  if (te) {
    textComposing.value = false
    const focusTa = () => {
      const el = textAreaRef.value
      if (!el) return
      if (!el.value) el.value = te.value // 空时写初值；已有内容不动（不打断 IME）
      el.focus({ preventScroll: true })
      const len = el.value.length
      el.setSelectionRange(len, len)
    }
    nextTick(() => {
      focusTa()
      requestAnimationFrame(focusTa)
    })
  } else {
    textComposing.value = false
  }
})

/**
 * vector → bitmap 单向烘焙（对齐 Scratch 模式转换语义）：
 * 切到位图时把全部帧矢量层烘进位图层并清空矢量层与两套撤销栈——转换不可逆，
 * 之后切回矢量仅切换编辑环境，旧素材保持位图不自动变回矢量（可在矢量模式追加新内容）。
 * 无矢量内容时为纯模式切换（不清位图历史）。
 */
function bakeVectorToBitmap() {
  if (!vectorEngine.hasVectorContent()) return
  const composed = getFrameCanvasesComposed() // 位图⊕矢量全帧合成（内部先固化矢量活动帧槽）
  bitmapBakeReplacePixels(composed)
  vectorEngine.clearAllForBake()
  store.dirty = true
}

watch(
  () => store.mode,
  (m, oldM) => {
    if (oldM === 'vector' && m === 'bitmap') bakeVectorToBitmap()
  }
)

// 暴露给父页面：动作按模式路由到对应引擎（父页面无需感知双引擎）
defineExpose({
  undo: undoActive,
  redo: redoActive,
  clear: clearActive,
  cropToContent,
  addFrame,
  removeFrame,
  moveFrame,
  loadFrames,
  getFrameCanvases: getFrameCanvasesComposed,
  getFrameNames,
  copySelection: copyActive,
  pasteClipboard: pasteActive,
  deleteSelection: deleteActive,
  flipSelection: flipActive,
  commitAndDeselect: commitBitmapSelection,
  groupSelection: () => vectorEngine.groupSelection(),
  ungroupSelection: () => vectorEngine.ungroupSelection(),
  layerMove: (dir: 'up' | 'down') => vectorEngine.layerMove(dir),
  /** 塑形：选中锚点曲线化/折线化（顶栏按钮路由） */
  curveSelectedPoints: () => vectorEngine.curveSelectedPoints(),
  pointSelectedPoints: () => vectorEngine.pointSelectedPoints(),
  getCanvas,
})
</script>

<template>
  <div
    ref="stageRef"
    class="paint-stage"
    :class="{ picking: store.eyedropperActive }"
    tabindex="0"
    @wheel.prevent="onStageWheel"
    @mousedown="onStageMouseDown"
    @mousemove="onStageMouseMove"
    @mouseup="isPanning = false"
    @dblclick="onStageDblClick"
    @pointerdown="onStagePointerDownForPick"
    @pointerleave="onStagePointerLeavePick"
    @keydown="onStageKeydown"
  >
    <div class="artboard" :style="artboardStyle">
      <!-- 棋盘格透明底（与 SpriteEditorView 一致的 CSS conic 棋盘） -->
      <div class="artboard-checker">
        <!-- 位图画布：绝对定位叠在棋盘格上，透明背景；绘制引擎接管 pointer 事件。
             canvas-pixelated 常驻：位图像素数据任何模式下都按像素块渲染（对齐 Scratch——
             位图=像素块、矢量=平滑，两种内容渲染观感明显不同，与当前编辑模式无关）。
             矢量模式下隐藏显示：由场景内位图代理（Raster image）接管显示，
             否则代理被移动/变换时下层原图重影 -->
        <canvas
          ref="bitmapCanvas"
          class="artboard-canvas canvas-pixelated"
          :width="store.artboardWidth"
          :height="store.artboardHeight"
          :style="{ visibility: store.mode === 'vector' ? 'hidden' : 'visible' }"
        ></canvas>
      </div>
    </div>
    <!-- 矢量画布：Scratch 同款架构——铺满舞台、不进 artboard 的 CSS transform 管道，
         缩放/平移由引擎写入 paper view.matrix（按屏幕像素重新栅格化，画布本身不被拉伸→无合成器重采样发糊）。
         叠于位图层之上（双层共存，导出叠加）；仅矢量模式接收 pointer 事件（门控），位图模式事件穿透到下层。
         clip-path 由引擎裁剪到 artboard 视觉盒（防矢量笔画画出画板） -->
    <canvas
      ref="vectorCanvas"
      class="vector-canvas"
      :style="{ pointerEvents: store.mode === 'vector' ? 'auto' : 'none' }"
    ></canvas>
    <!-- 选区 overlay 层：与 artboard 逐像素同位同变换（复用同一 artboardStyle 计算），
         浮于矢量画布之上——选区框/蚂蚁线必须盖住两层内容 -->
    <div class="paint-overlay">
      <div class="paint-overlay-box" :style="artboardStyle">
        <!-- 选区蚂蚁线（仅框选拖动中的进行态预览） -->
        <div v-if="selectionStyle && !store.floatActive" class="selection-ants" :style="selectionStyle"></div>
        <!-- 矢量选中变换框：定向矩形（可带旋转角）+ 8 缩放手柄 + 旋转柄，
             与位图浮动选区同一 SVG overlay 方案（不走 paper.item.selected，防烙印进画布） -->
        <svg
          v-if="store.vectorSelBox && store.mode === 'vector'"
          class="transform-box"
          :viewBox="`0 0 ${store.artboardWidth} ${store.artboardHeight}`"
          preserveAspectRatio="none"
        >
          <!-- 框线：暗色打底（任何底色可见）+ 低饱和蓝紫实线芯 -->
          <polygon
            :points="vectorBoxPoints"
            fill="none"
            stroke="rgba(18, 20, 38, 0.85)"
            :stroke-width="2.5 * boxStrokeInv"
            stroke-linejoin="round"
          />
          <polygon
            :points="vectorBoxPoints"
            fill="none"
            :stroke="SEL"
            :stroke-width="1.4 * boxStrokeInv"
            stroke-linejoin="round"
          />
          <!-- 8 个缩放手柄：白底 + 蓝紫描边（专业软件风格） -->
          <rect
            v-for="(h, i) in store.vectorSelBox.handles"
            :key="i"
            :x="h.x - boxHandleSize / 2"
            :y="h.y - boxHandleSize / 2"
            :width="boxHandleSize"
            :height="boxHandleSize"
            fill="#ffffff"
            :stroke="SEL_DEEP"
            :stroke-width="1.2 * boxStrokeInv"
          />
          <!-- 旋转柄：连接线 + 蓝紫圆点 -->
          <line
            :x1="store.vectorSelBox.rotateTop.x"
            :y1="store.vectorSelBox.rotateTop.y"
            :x2="store.vectorSelBox.rotateAt.x"
            :y2="store.vectorSelBox.rotateAt.y"
            stroke="rgba(18, 20, 38, 0.6)"
            :stroke-width="2.5 * boxStrokeInv"
          />
          <line
            :x1="store.vectorSelBox.rotateTop.x"
            :y1="store.vectorSelBox.rotateTop.y"
            :x2="store.vectorSelBox.rotateAt.x"
            :y2="store.vectorSelBox.rotateAt.y"
            :stroke="SEL"
            :stroke-width="1.4 * boxStrokeInv"
          />
          <circle
            :cx="store.vectorSelBox.rotateAt.x"
            :cy="store.vectorSelBox.rotateAt.y"
            :r="4 * boxStrokeInv"
            :fill="SEL"
            :stroke="SEL_DEEP"
            :stroke-width="1.2 * boxStrokeInv"
          />
        </svg>
        <!-- 塑形选中对象高亮（reshape 工具）：轮廓线 + 锚点圆点 + 选中点的贝塞尔手柄
             （手柄仅选中锚点下发；所属项被全选时引擎隐藏，对齐 Scratch） -->
        <svg
          v-if="store.reshapePts && store.mode === 'vector'"
          class="transform-box"
          :viewBox="`0 0 ${store.artboardWidth} ${store.artboardHeight}`"
          preserveAspectRatio="none"
        >
          <!-- 对象轮廓（描边高亮盖在内容上、锚点之下；1.5/zoom → 屏幕恒定 1.5px） -->
          <path
            v-for="(d, i) in store.reshapeOutline || []"
            :key="'o' + i"
            :d="d"
            fill="none"
            :stroke="SEL"
            :stroke-width="1.5 * boxStrokeInv"
            stroke-linejoin="round"
            stroke-linecap="round"
          />
          <g v-for="(pt, i) in store.reshapePts" :key="i">
            <template v-if="pt.handleIn">
              <line
                :x1="pt.x"
                :y1="pt.y"
                :x2="pt.handleIn.x"
                :y2="pt.handleIn.y"
                stroke="rgba(18, 20, 38, 0.7)"
                :stroke-width="1.8 * boxStrokeInv"
              />
              <circle
                :cx="pt.handleIn.x"
                :cy="pt.handleIn.y"
                :r="boxHandleDot / 2"
                fill="#ffffff"
                :stroke="SEL_DEEP"
                :stroke-width="1.2 * boxStrokeInv"
              />
            </template>
            <template v-if="pt.handleOut">
              <line
                :x1="pt.x"
                :y1="pt.y"
                :x2="pt.handleOut.x"
                :y2="pt.handleOut.y"
                stroke="rgba(18, 20, 38, 0.7)"
                :stroke-width="1.8 * boxStrokeInv"
              />
              <circle
                :cx="pt.handleOut.x"
                :cy="pt.handleOut.y"
                :r="boxHandleDot / 2"
                fill="#ffffff"
                :stroke="SEL_DEEP"
                :stroke-width="1.2 * boxStrokeInv"
              />
            </template>
            <!-- 锚点圆点：未选中白底、选中填充主色 -->
            <circle
              :cx="pt.x"
              :cy="pt.y"
              :r="boxPtSize / 2"
              :fill="pt.selected ? SEL : '#ffffff'"
              :stroke="SEL_DEEP"
              :stroke-width="1.4 * boxStrokeInv"
            />
          </g>
        </svg>
        <!-- 钢笔（自定义形状）进行中预览：固定配色（不跟随颜色面板）——
             虚线橡皮筋 + 已落锚点方块 + 首锚收尾热点（进入命中区脉冲高亮，指示可闭合） -->
        <svg
          v-if="store.penState && store.mode === 'vector'"
          class="transform-box"
          :viewBox="`0 0 ${store.artboardWidth} ${store.artboardHeight}`"
          preserveAspectRatio="none"
        >
          <polyline
            :points="penPolyline"
            fill="none"
            :stroke="PEN"
            :stroke-width="penStrokeW"
            :stroke-dasharray="penDashArray"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <!-- 下一锚点落点提示（收尾命中时隐藏，避免与首锚热点重叠） -->
          <circle
            v-if="store.penState.cursor && !store.penState.closing"
            :cx="store.penState.cursor.x"
            :cy="store.penState.cursor.y"
            :r="penAnchorSize * 0.42"
            :fill="PEN"
          />
          <!-- 已落锚点：白底小方块（角点样式，屏幕尺寸恒定） -->
          <rect
            v-for="(pt, i) in store.penState.anchors"
            :key="'pen' + i"
            :x="pt.x - penAnchorSize / 2"
            :y="pt.y - penAnchorSize / 2"
            :width="penAnchorSize"
            :height="penAnchorSize"
            fill="#ffffff"
            :stroke="PEN_DEEP"
            :stroke-width="penStrokeW"
          />
          <!-- 首锚收尾热点：≥3 点常驻提示环；光标进入命中半径 → 填充 + 脉冲 -->
          <circle
            v-if="store.penState.anchors.length >= 3"
            class="pen-close-hotspot"
            :class="{ 'pen-close-hotspot-active': store.penState.closing }"
            :cx="store.penState.anchors[0].x"
            :cy="store.penState.anchors[0].y"
            :r="penCloseRingR"
            :fill="store.penState.closing ? 'rgba(129, 140, 248, 0.28)' : 'none'"
            :stroke="PEN"
            :stroke-width="penStrokeW"
          />
        </svg>
        <!-- 变换框（浮动选区）：独立 SVG 矢量图层——专业绘图软件做法，
             绝不画进图像画布（防烙印），矢量渲染任意缩放平滑 -->
        <svg
          v-if="store.transformBox"
          class="transform-box"
          :viewBox="`0 0 ${store.artboardWidth} ${store.artboardHeight}`"
          preserveAspectRatio="none"
        >
          <!-- 框线：暗色打底（任何底色可见）+ 低饱和蓝紫实线芯 -->
          <polygon
            :points="boxPoints"
            fill="none"
            stroke="rgba(18, 20, 38, 0.85)"
            :stroke-width="2.5 * boxStrokeInv"
            stroke-linejoin="round"
          />
          <polygon
            :points="boxPoints"
            fill="none"
            :stroke="SEL"
            :stroke-width="1.4 * boxStrokeInv"
            stroke-linejoin="round"
          />
          <!-- 8 个缩放手柄：白底 + 蓝紫描边（专业软件风格） -->
          <rect
            v-for="(h, i) in store.transformBox.handles"
            :key="i"
            :x="h.x - boxHandleSize / 2"
            :y="h.y - boxHandleSize / 2"
            :width="boxHandleSize"
            :height="boxHandleSize"
            fill="#ffffff"
            :stroke="SEL_DEEP"
            :stroke-width="1.2 * boxStrokeInv"
          />
          <!-- 旋转柄：连接线 + 蓝紫圆点 -->
          <line
            :x1="store.transformBox.rotateTop.x"
            :y1="store.transformBox.rotateTop.y"
            :x2="store.transformBox.rotateAt.x"
            :y2="store.transformBox.rotateAt.y"
            stroke="rgba(18, 20, 38, 0.6)"
            :stroke-width="2.5 * boxStrokeInv"
          />
          <line
            :x1="store.transformBox.rotateTop.x"
            :y1="store.transformBox.rotateTop.y"
            :x2="store.transformBox.rotateAt.x"
            :y2="store.transformBox.rotateAt.y"
            :stroke="SEL"
            :stroke-width="1.4 * boxStrokeInv"
          />
          <circle
            :cx="store.transformBox.rotateAt.x"
            :cy="store.transformBox.rotateAt.y"
            :r="4 * boxStrokeInv"
            :fill="SEL"
            :stroke="SEL_DEEP"
            :stroke-width="1.2 * boxStrokeInv"
          />
        </svg>
        <!-- 画笔/橡皮自绘光标圈（矢量模式；SVG 双圆 = 深浅底可见，0 尺寸 svg + overflow visible
             以定位点为圆心；r 用画板逻辑坐标随视图正确缩放） -->
        <svg
          v-if="brushCursorStyle"
          class="brush-cursor-ring"
          :style="brushCursorStyle"
          overflow="visible"
        >
          <circle :r="store.brushSize / 2" fill="none" stroke="rgba(0, 0, 0, 0.55)" :stroke-width="3 / Math.max(0.1, store.zoom)" />
          <circle :r="store.brushSize / 2" fill="none" stroke="rgba(255, 255, 255, 0.95)" :stroke-width="1.5 / Math.max(0.1, store.zoom)" />
        </svg>
        <!-- 文字编辑 textarea（Scratch 同款透明覆盖层）：与 PointText/栅格化文字逐字对齐，
             虚线外框示意编辑范围；pointer-events: auto 接收键鼠（父层 none 不穿透） -->
        <textarea
          v-if="store.textEdit"
          ref="textAreaRef"
          class="text-edit-area"
          :style="textEditStyle"
          spellcheck="false"
          autocomplete="off"
          @input="onTextAreaInput"
          @compositionstart="onTextAreaCompositionStart"
          @compositionend="onTextAreaCompositionEnd"
          @keydown="onTextAreaKeydown"
        ></textarea>
      </div>
    </div>
    <!-- 拾色放大镜（Scratch 同款）：屏幕坐标跟随光标，中心准心对准取样像素；
         canvas 最近邻放大合成图，中心十字线指示精确取色点 -->
    <div
      v-if="store.eyedropperActive && pickLensPos"
      class="pick-lens"
      :style="{ left: `${pickLensPos.x}px`, top: `${pickLensPos.y}px` }"
    >
      <canvas ref="pickLensRef" class="pick-lens-canvas" :width="LENS_SIZE" :height="LENS_SIZE"></canvas>
      <!-- 中心准心：横竖线 + 中心点（指示镜中心=取样像素） -->
      <div class="pick-lens-cross-h"></div>
      <div class="pick-lens-cross-v"></div>
    </div>
    <!-- 浮动视图工具条：撤销/重做/缩放（顶栏窄窗口避让，拾色时隐藏防遮挡）。
         @dblclick.stop：快速连点按钮会被浏览器判成 dblclick 冒泡到舞台触发双击复位——必须拦截 -->
    <div v-show="!store.eyedropperActive" class="view-float-bar" @dblclick.stop>
      <button class="view-float-btn" v-tooltip="'缩小'" @click="onZoomOut">
        <img :src="iconZoomOut" width="16" height="16" draggable="false" />
      </button>
      <button class="view-float-zoom" v-tooltip="'重置缩放'" @click="store.resetView()">
        {{ Math.round(store.zoom * 100) }}%
      </button>
      <button class="view-float-btn" v-tooltip="'放大'" @click="onZoomIn">
        <img :src="iconZoomIn" width="16" height="16" draggable="false" />
      </button>
      <div class="view-float-divider"></div>
      <button
        class="view-float-btn"
        :disabled="!floatCanUndo()"
        v-tooltip="store.mode === 'vector' ? '撤销（矢量）' : '撤销'"
        @click="undoActive()"
      >
        <img :src="iconUndo" width="14" height="14" draggable="false" />
      </button>
      <button
        class="view-float-btn"
        :disabled="!floatCanRedo()"
        v-tooltip="store.mode === 'vector' ? '重做（矢量）' : '重做'"
        @click="redoActive()"
      >
        <img :src="iconRedo" width="14" height="14" draggable="false" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.paint-stage {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-root);
  overflow: hidden;
  position: relative;
}

/* 去掉浏览器默认焦点环（tabindex=0 聚焦时会在舞台外圈画深蓝框，与绘制内容无关） */
.paint-stage:focus,
.paint-stage:focus-visible {
  outline: none;
}

/* 拾色模式：放大镜准心接管取样指示，隐藏系统光标（对齐 Scratch） */
.paint-stage.picking,
.paint-stage.picking canvas {
  cursor: none !important;
}

/* ─── 拾色放大镜 ─── */
.pick-lens {
  position: absolute;
  z-index: 20;
  width: 92px;
  height: 92px;
  /* 以镜中心定位（left/top = 中心点） */
  transform: translate(-50%, -50%);
  pointer-events: none;
}
.pick-lens-canvas {
  position: absolute;
  inset: 0;
  display: block;
  width: 92px;
  height: 92px;
  border-radius: 50%;
  /* 双环：深色打底 + 白色内环（任何底色上可见） */
  box-shadow:
    0 0 0 2px rgba(18, 20, 30, 0.85),
    0 0 0 3.5px rgba(255, 255, 255, 0.95),
    0 4px 16px rgba(0, 0, 0, 0.35);
  background: repeating-conic-gradient(#ccc 0% 25%, #fff 0% 50%) 50% / 12px 12px;
}
/* 中心准心十字线（贯穿镜片） */
.pick-lens-cross-h,
.pick-lens-cross-v {
  position: absolute;
  left: 50%;
  top: 50%;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 0 0 0.5px rgba(0, 0, 0, 0.55);
}
.pick-lens-cross-h {
  width: 18px;
  height: 1px;
  transform: translate(-50%, -50%);
}
.pick-lens-cross-v {
  width: 1px;
  height: 18px;
  transform: translate(-50%, -50%);
}

.artboard {
  position: relative;
  flex-shrink: 0;
  transform-origin: center center;
}

.artboard-checker {
  position: relative;
  width: 100%;
  height: 100%;
  background: repeating-conic-gradient(#ccc 0% 25%, #fff 0% 50%) 50% / 16px 16px;
  /* 用 outline 而非 border：border 会挤压 1px 布局让 canvas CSS 尺寸 ≠ 逻辑尺寸产生拉伸模糊 */
  outline: 1px solid var(--border-light);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
}

.artboard-canvas {
  position: absolute;
  inset: 0;
  display: block;
  /* 触摸操作交给 pointer 事件，禁用浏览器手势避免干扰绘制 */
  touch-action: none;
}

/* 矢量画布：铺满舞台（Scratch 同款——不随画板 transform 拉伸，缩放走 paper view.matrix）。
   宽高 100% 必须显式声明：canvas 是替换元素，仅 inset:0 时按内在尺寸 300×150 而非撑满 */
.vector-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
  touch-action: none;
}

/* 选区 overlay 层：全舞台 flex 居中复刻 artboard 布局 + 同一 artboardStyle 变换 → 逐像素同位 */
.paint-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 5;
}

.paint-overlay-box {
  position: relative;
  transform-origin: center center;
  pointer-events: none;
}

/* 选区蚂蚁线（框选拖动态）：深色虚线 + 蓝紫衬线（与变换框同色系） */
.selection-ants {
  position: absolute;
  pointer-events: none;
  outline: 1px dashed rgba(24, 27, 50, 0.95);
  box-shadow: 0 0 0 1px #818cf8;
  z-index: 5;
}

/* 变换框：独立矢量图层，随画板 transform 缩放但自身矢量渲染平滑 */
.transform-box {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 6;
  overflow: visible;
}

/* 钢笔首锚收尾热点：光标进入命中半径时描边脉冲，明确「点这里闭合」 */
.pen-close-hotspot-active {
  animation: pen-close-pulse 0.9s ease-in-out infinite;
}
@keyframes pen-close-pulse {
  0%, 100% { stroke-opacity: 1; }
  50% { stroke-opacity: 0.35; }
}

/* 画笔/橡皮自绘光标圈：0 尺寸 svg 锚定在光标逻辑坐标，overflow visible 画圆，
   随画板 transform 缩放（任意 zoom 屏幕尺寸正确）；SVG 双圆避免阴影环亚像素断裂 */
.brush-cursor-ring {
  position: absolute;
  width: 0;
  height: 0;
  overflow: visible;
  pointer-events: none;
  z-index: 7;
}

/* ─── 浮动视图工具条（画布右下；对齐代码编辑器 ide-float-bar 胶囊风格）─── */
.view-float-bar {
  position: absolute;
  bottom: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 0;
  background: rgba(30, 32, 40, 0.92);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 4px;
  z-index: 30;
}
.view-float-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 30px;
  height: 26px;
  padding: 0 6px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s ease;
}
.view-float-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
}
.view-float-btn:active:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
}
.view-float-btn:disabled {
  opacity: 0.35;
  cursor: default;
}
.view-float-zoom {
  min-width: 44px;
  height: 26px;
  padding: 0 4px;
  background: transparent;
  border: none;
  border-radius: 6px;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.15s, background 0.15s;
}
.view-float-zoom:hover {
  color: var(--text);
  background: rgba(255, 255, 255, 0.08);
}
.view-float-divider {
  width: 1px;
  height: 14px;
  background: rgba(255, 255, 255, 0.1);
  margin: 0 4px;
}

/* ─── 文字编辑覆盖层（Scratch text-tool 同款）─── */
.text-edit-area {
  position: absolute;
  pointer-events: auto;
  z-index: 9;
  /* 与 PointText 渲染对齐：无边框无衬距（padding/border 会偏移字形），透明底，不换行。
     尺寸由引擎按内容 internalBounds 动态写入 width/height（对齐 Scratch resizeGuide） */
  margin: 0;
  padding: 0;
  border: none;
  outline: 1px dashed rgba(24, 27, 50, 0.7);
  outline-offset: 2px;
  background: transparent;
  resize: none;
  overflow: hidden;
  white-space: pre;
  font-family: 'HarmonyOS Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-weight: 500;
  /* 光标跟随当前文字色（te.color = 绘制色） */
  caret-color: currentColor;
  box-sizing: content-box;
  /* 合成器不拉伸：textarea 随 artboard transform 缩放，文字用逻辑字号渲染 */
  transform-origin: 0 0;
}

/* 位图模式像素渲染：多重声明渐进回退（旧引擎认 crisp-edges，新引擎 pixelated 覆盖生效） */
.canvas-pixelated {
  image-rendering: -moz-crisp-edges;
  image-rendering: crisp-edges;
  image-rendering: pixelated;
}
</style>
