<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { usePaintStore } from '../../stores/paint'
import { useBitmapCanvas } from './composables/useBitmapCanvas'

const store = usePaintStore()

const stageRef = ref<HTMLDivElement>()
const bitmapCanvas = ref<HTMLCanvasElement>()

// 位图绘制引擎（工具状态机/撤销重做/光标/多帧像素/选区），canvas 就绪后自动绑定指针事件
const {
  undo, redo, clear, cropToContent,
  addFrame, removeFrame, loadFrames, getFrameCanvases, getFrameNames,
  copySelection, pasteClipboard, deleteSelection, flipSelection, commitAndDeselect,
  getCanvas,
} = useBitmapCanvas(bitmapCanvas)

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

function focusStage() {
  stageRef.value?.focus()
}

/** 快捷键：Esc 取消选区、Delete 删除选区、Ctrl/Cmd+C/V/X 复制粘贴剪切 */
function onStageKeydown(e: KeyboardEvent) {
  const mod = e.ctrlKey || e.metaKey
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

// 暴露给父页面：撤销/重做/清空/裁切/多帧/选区操作与保存管线
defineExpose({
  undo, redo, clear, cropToContent,
  addFrame, removeFrame, loadFrames, getFrameCanvases, getFrameNames,
  copySelection, pasteClipboard, deleteSelection, flipSelection, commitAndDeselect,
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
             位图模式 1:1 像素网格：width/height 属性 = 逻辑尺寸（画板尺寸即输出尺寸），
             canvas-pixelated 类获得 Scratch 同款像素渲染（矢量模式不加此类=平滑） -->
        <canvas
          ref="bitmapCanvas"
          class="artboard-canvas"
          :class="{ 'canvas-pixelated': store.mode === 'bitmap' }"
          :width="store.artboardWidth"
          :height="store.artboardHeight"
        ></canvas>
        <!-- 选区蚂蚁线（仅框选拖动中的进行态预览） -->
        <div v-if="selectionStyle && !store.floatActive" class="selection-ants" :style="selectionStyle"></div>
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
            :stroke-width="1.2 * boxStrokeInv"
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
