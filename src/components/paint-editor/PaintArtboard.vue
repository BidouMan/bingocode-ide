<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { usePaintStore } from '../../stores/paint'
import { useBitmapCanvas } from './composables/useBitmapCanvas'
import { usePaperScope } from './composables/usePaperScope'

const store = usePaintStore()

const stageRef = ref<HTMLDivElement>()
const bitmapCanvas = ref<HTMLCanvasElement>()
const vectorCanvas = ref<HTMLCanvasElement>()

// 位图绘制引擎（工具状态机/撤销重做/光标/多帧像素/选区），canvas 就绪后自动绑定指针事件
// 帧操作函数取别名：下方包装器编排双引擎（矢量槽位与位图像素数组保持下标对齐）
const {
  undo: bitmapUndo, redo: bitmapRedo, clear: bitmapClear, cropToContent,
  addFrame: bitmapAddFrame, removeFrame: bitmapRemoveFrame,
  loadFrames: bitmapLoadFrames, getFrameCanvases: bitmapGetFrameCanvases, getFrameNames,
  copySelection, pasteClipboard, deleteSelection, flipSelection, commitAndDeselect,
  getCanvas,
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

function focusStage() {
  stageRef.value?.focus()
}

/** 快捷键：按模式分发——矢量=对象操作；位图=选区操作 */
function onStageKeydown(e: KeyboardEvent) {
  const mod = e.ctrlKey || e.metaKey

  if (store.mode === 'vector') {
    if (e.key === 'Escape') {
      // 收起矢量选中（引擎侧同步清 selected 与变换框）
      vectorEngine.deselect()
      e.preventDefault()
    } else if (e.key === 'Delete' || e.key === 'Backspace') {
      if (store.vectorSelectedCount > 0) {
        vectorEngine.deleteSelection()
        e.preventDefault()
      }
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
  vectorEngine.onFrameRemoved(index)
  const ok = bitmapRemoveFrame(index)
  if (ok) vectorEngine.syncActiveFrame()
  return ok
}

/** 整体载入（编辑既有角色）：既有帧均为纯位图，矢量槽重置 */
function loadFrames(
  canvases: HTMLCanvasElement[],
  names: (string | null)[],
  activeIndex: number
) {
  bitmapLoadFrames(canvases, names, activeIndex)
  vectorEngine.onLoadFrames(canvases.length)
}

/**
 * 保存取帧：位图帧 + 矢量层叠加。
 * 先让矢量引擎固化活动帧快照（beforeExport 内部 flush 渲染并重导入保持编辑态），
 * 再对每帧把矢量层 drawImage 到位图帧副本上（不污染位图引擎的源像素）。
 */
function getFrameCanvasesComposed(): HTMLCanvasElement[] {
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
  if (store.mode === 'vector') vectorEngine.undo()
  else bitmapUndo()
}

function redoActive() {
  if (store.mode === 'vector') vectorEngine.redo()
  else bitmapRedo()
}

/** 清空：按模式清当前工作层 */
function clearActive() {
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
  commitAndDeselect()
})

// 暴露给父页面：动作按模式路由到对应引擎（父页面无需感知双引擎）
defineExpose({
  undo: undoActive,
  redo: redoActive,
  clear: clearActive,
  cropToContent,
  addFrame,
  removeFrame,
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
  getCanvas,
})
</script>

<template>
  <div
    ref="stageRef"
    class="paint-stage"
    tabindex="0"
    @wheel.prevent="onStageWheel"
    @mousedown="onStageMouseDown"
    @mousemove="onStageMouseMove"
    @mouseup="isPanning = false"
    @dblclick="onStageDblClick"
    @pointerdown="focusStage"
    @keydown="onStageKeydown"
  >
    <div class="artboard" :style="artboardStyle">
      <!-- 棋盘格透明底（与 SpriteEditorView 一致的 CSS conic 棋盘） -->
      <div class="artboard-checker">
        <!-- 位图画布：绝对定位叠在棋盘格上，透明背景；绘制引擎接管 pointer 事件。
             canvas-pixelated 常驻：位图像素数据任何模式下都按像素块渲染（对齐 Scratch——
             位图=像素块、矢量=平滑，两种内容渲染观感明显不同，与当前编辑模式无关） -->
        <canvas
          ref="bitmapCanvas"
          class="artboard-canvas canvas-pixelated"
          :width="store.artboardWidth"
          :height="store.artboardHeight"
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
      </div>
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

/* 位图模式像素渲染：多重声明渐进回退（旧引擎认 crisp-edges，新引擎 pixelated 覆盖生效） */
.canvas-pixelated {
  image-rendering: -moz-crisp-edges;
  image-rendering: crisp-edges;
  image-rendering: pixelated;
}
</style>
