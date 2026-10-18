<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { usePaintStore } from '../../stores/paint'
import { useBitmapCanvas } from './composables/useBitmapCanvas'

const store = usePaintStore()

const stageRef = ref<HTMLDivElement>()
const bitmapCanvas = ref<HTMLCanvasElement>()

// 位图绘制引擎（工具状态机/撤销重做/光标），canvas 就绪后自动绑定指针事件
const { undo, redo, clear, getCanvas } = useBitmapCanvas(bitmapCanvas)

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
const artboardStyle = computed(() => ({
  width: `${store.artboardWidth}px`,
  height: `${store.artboardHeight}px`,
  transform: `translate(${store.panX}px, ${store.panY}px) scale(${store.zoom})`,
}))

// 暴露给父页面：撤销/重做/清空按钮与保存管线
defineExpose({ undo, redo, clear, getCanvas })
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
        <!-- 位图画布：绝对定位叠在棋盘格上，透明背景；绘制引擎接管 pointer 事件 -->
        <canvas
          ref="bitmapCanvas"
          class="artboard-canvas"
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
  will-change: transform;
}

.artboard-checker {
  position: relative;
  width: 100%;
  height: 100%;
  background: repeating-conic-gradient(#ccc 0% 25%, #fff 0% 50%) 50% / 16px 16px;
  border: 1px solid var(--border-light);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
}

.artboard-canvas {
  position: absolute;
  inset: 0;
  display: block;
  /* 触摸操作交给 pointer 事件，禁用浏览器手势避免干扰绘制 */
  touch-action: none;
}
</style>
