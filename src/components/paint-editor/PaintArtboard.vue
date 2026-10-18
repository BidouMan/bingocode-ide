<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { usePaintStore } from '../../stores/paint'
import { useBitmapCanvas } from './composables/useBitmapCanvas'

const store = usePaintStore()

const stageRef = ref<HTMLDivElement>()
const bitmapCanvas = ref<HTMLCanvasElement>()

// 位图绘制引擎（工具状态机/撤销重做/光标/多帧像素），canvas 就绪后自动绑定指针事件
const { undo, redo, clear, cropToContent, addFrame, removeFrame, loadFrames, getFrameCanvases, getFrameNames, getCanvas } =
  useBitmapCanvas(bitmapCanvas)

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

// 暴露给父页面：撤销/重做/清空/裁切/多帧操作与保存管线
defineExpose({ undo, redo, clear, cropToContent, addFrame, removeFrame, loadFrames, getFrameCanvases, getFrameNames, getCanvas })
</script>

<template>
  <div
    ref="stageRef"
    class="paint-stage"
    @wheel.prevent="onStageWheel"
    @mousedown="onStageMouseDown"
    @mousemove="onStageMouseMove"
    @mouseup="isPanning = false"
    @dblclick="onStageDblClick"
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

/* 位图模式像素渲染：多重声明渐进回退（旧引擎认 crisp-edges，新引擎 pixelated 覆盖生效） */
.canvas-pixelated {
  image-rendering: -moz-crisp-edges;
  image-rendering: crisp-edges;
  image-rendering: pixelated;
}
</style>
