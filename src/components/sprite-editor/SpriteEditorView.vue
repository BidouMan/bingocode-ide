<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount, nextTick } from 'vue'
import { useResourceStore } from '../../stores/resource'
import { useEditorStore } from '../../stores/editor'
import type { SpriteData, SpriteFrame, SpriteAnimation } from '../../composables/useSpriteData'
import { readBgsFromUrl } from '../../composables/useSpriteData'

import iconPrev from '../../assets/icons/btn_preview_prev.svg'
import iconPlay from '../../assets/icons/btn_preview_play.svg'
import iconPause from '../../assets/icons/btn_preview_pause.svg'
import iconNext from '../../assets/icons/btn_preview_next.svg'
import iconScale from '../../assets/icons/btn_preview_scale.svg'
import iconChangeBg from '../../assets/icons/btn_preview_change_bg.svg'
import iconAdd from '../../assets/icons/btn_preview_add.svg'
import iconLoop from '../../assets/icons/anim_loop.svg'
import iconLoopOff from '../../assets/icons/anim_loop_off.svg'

const resourceStore = useResourceStore()
const editorStore = useEditorStore()

const imageRenderingStyle = computed(() => {
  return editorStore.renderMode === 'pixelated' ? 'pixelated' : 'auto'
})

const currentSprite = ref<SpriteData | null>(null)
const selectedFrameIndex = ref(0)
const selectedAnim = ref<SpriteAnimation | null>(null)
const isPlaying = ref(false)
const previewScale = ref(1)
const fpsValue = ref(10)
const costumeHighlightIndex = ref(0)
const canvasDisplayIndex = ref(0)
const previewBgIndex = ref(0)

// 画布缩放和平移
const canvasZoom = ref(1)
const canvasPanX = ref(0)
const canvasPanY = ref(0)
const isPanning = ref(false)
const panStartX = ref(0)
const panStartY = ref(0)
const panStartOffsetX = ref(0)
const panStartOffsetY = ref(0)
const canvasRef = ref<HTMLDivElement | null>(null)

const costumeContextMenu = ref<{ show: boolean; x: number; y: number; index: number }>({ show: false, x: 0, y: 0, index: 0 })
const animContextMenu = ref<{ show: boolean; x: number; y: number; name: string }>({ show: false, x: 0, y: 0, name: '' })
const renamingAnim = ref<string | null>(null)
const renameInputRef = ref<HTMLInputElement | null>(null)
let playTimer: ReturnType<typeof setInterval> | null = null

watch(
  () => resourceStore.selectedSpriteId,
  (id) => {
    if (!id) return
    const item = resourceStore.sprites.find(s => s.id === id)
    if (item && item.path) loadSprite(item)
  },
  { immediate: true }
)

async function loadSprite(item: { id: string; name: string; path: string }) {
  try {
    currentSprite.value = await readBgsFromUrl(item.path)
    selectedFrameIndex.value = 0
    canvasDisplayIndex.value = 0
    costumeHighlightIndex.value = 0
    selectedAnim.value = null
    stopAnimation()
    canvasZoom.value = 1
    canvasPanX.value = 0
    canvasPanY.value = 0
    if (currentSprite.value.animations.length > 0) {
      const first = currentSprite.value.animations[0]
      selectedAnim.value = first
      fpsValue.value = first.fps || 10
      startAnimation(first)
    }
  } catch (e) {
    console.error('Failed to load sprite:', e)
  }
}

function selectFrame(index: number) {
  stopAnimation()
  selectedFrameIndex.value = index
  costumeHighlightIndex.value = index
  canvasDisplayIndex.value = index
}

function selectAnimation(anim: SpriteAnimation) {
  selectedAnim.value = anim
  fpsValue.value = anim.fps || 10
  startAnimation(anim)
}

function startAnimation(anim: SpriteAnimation) {
  stopAnimation()
  isPlaying.value = true
  selectedFrameIndex.value = anim.start - 1
  restartTimer()
}

function restartTimer() {
  if (playTimer) { clearInterval(playTimer); playTimer = null }
  if (!isPlaying.value || !selectedAnim.value) return
  const interval = 1000 / Math.max(fpsValue.value, 1)
  playTimer = setInterval(() => {
    if (!currentSprite.value || !selectedAnim.value) return
    selectedFrameIndex.value++
    if (selectedFrameIndex.value > selectedAnim.value.end - 1) {
      if (selectedAnim.value.loop !== false) {
        selectedFrameIndex.value = selectedAnim.value.start - 1
      } else {
        stopAnimation()
      }
    }
  }, interval)
}

function stopAnimation() {
  isPlaying.value = false
  if (playTimer) { clearInterval(playTimer); playTimer = null }
}

function togglePlay() {
  if (isPlaying.value) stopAnimation()
  else if (selectedAnim.value) startAnimation(selectedAnim.value)
}

function prevFrame() {
  if (!currentSprite.value) return
  stopAnimation()
  selectedFrameIndex.value = Math.max(0, selectedFrameIndex.value - 1)
  canvasDisplayIndex.value = selectedFrameIndex.value
  costumeHighlightIndex.value = selectedFrameIndex.value
}

function nextFrame() {
  if (!currentSprite.value) return
  stopAnimation()
  selectedFrameIndex.value = Math.min(currentSprite.value.frames.length - 1, selectedFrameIndex.value + 1)
  canvasDisplayIndex.value = selectedFrameIndex.value
  costumeHighlightIndex.value = selectedFrameIndex.value
}

function toggleScale() {
  previewScale.value = previewScale.value === 1 ? 2 : 1
}

function changeBg() {
  previewBgIndex.value = (previewBgIndex.value + 1) % 3
}

// 画布滚轮缩放 (以鼠标位置为中心)
function onCanvasWheel(e: WheelEvent) {
  e.preventDefault()
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  // 鼠标相对于画布中心的偏移
  const mouseX = e.clientX - rect.left - rect.width / 2
  const mouseY = e.clientY - rect.top - rect.height / 2

  const oldZoom = canvasZoom.value
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  const newZoom = Math.min(32, Math.max(0.1, oldZoom * delta))

  // 以鼠标位置为中心缩放: 保持鼠标下的像素点不动
  canvasPanX.value = mouseX - (mouseX - canvasPanX.value) * (newZoom / oldZoom)
  canvasPanY.value = mouseY - (mouseY - canvasPanY.value) * (newZoom / oldZoom)
  canvasZoom.value = newZoom
}

// 中键按下开始平移
function onCanvasMouseDown(e: MouseEvent) {
  if (e.button === 1) {
    e.preventDefault()
    e.stopPropagation()
    isPanning.value = true
    panStartX.value = e.clientX
    panStartY.value = e.clientY
    panStartOffsetX.value = canvasPanX.value
    panStartOffsetY.value = canvasPanY.value
  }
}

function onCanvasMouseMove(e: MouseEvent) {
  if (!isPanning.value) return
  canvasPanX.value = panStartOffsetX.value + (e.clientX - panStartX.value)
  canvasPanY.value = panStartOffsetY.value + (e.clientY - panStartY.value)
}

function onCanvasMouseUp(e: MouseEvent) {
  if (e.button === 1) {
    isPanning.value = false
  }
}

function onGlobalMouseUp(e: MouseEvent) {
  if (e.button === 1) {
    isPanning.value = false
  }
}

// 双击重置画布
function resetCanvas() {
  canvasZoom.value = 1
  canvasPanX.value = 0
  canvasPanY.value = 0
}

function getPreviewBgStyle() {
  const bgs = [
    { background: '#2b2b2b' },
    { background: '#ffffff' },
    { background: 'repeating-conic-gradient(#ccc 0% 25%, #fff 0% 50%) 50% / 16px 16px' },
  ]
  return bgs[previewBgIndex.value]
}

watch(fpsValue, () => {
  if (isPlaying.value && selectedAnim.value) {
    restartTimer()
  }
})

function addAnimation() {
  if (!currentSprite.value) return
  const total = currentSprite.value.frames.length
  let name = '动画'
  const existing = currentSprite.value.animations.map(a => a.name)
  let counter = 1
  while (existing.includes(name)) { name = `动画${counter}`; counter++ }
  const newAnim: SpriteAnimation = { name, start: 1, end: total, fps: 10, loop: true }
  currentSprite.value.animations.push(newAnim)
}

function deleteAnimation(name: string) {
  if (!currentSprite.value) return
  if (selectedAnim.value?.name === name) { stopAnimation(); selectedAnim.value = null }
  currentSprite.value.animations = currentSprite.value.animations.filter(a => a.name !== name)
}

function renameAnimation(oldName: string, newName: string) {
  const shouldResume = wasPlayingBeforeRename && renamingAnim.value === oldName
  renamingAnim.value = null
  if (!currentSprite.value || !newName.trim()) return
  const exists = currentSprite.value.animations.some(a => a.name === newName && a.name !== oldName)
  if (exists) return
  const anim = currentSprite.value.animations.find(a => a.name === oldName)
  if (anim) anim.name = newName.trim()
  if (selectedAnim.value?.name === oldName) selectedAnim.value.name = newName.trim()
  if (shouldResume && selectedAnim.value) startAnimation(selectedAnim.value)
}

function toggleLoop(anim: SpriteAnimation) {
  anim.loop = anim.loop === false ? true : false
}

function onCostumeContextMenu(e: MouseEvent, index: number) {
  e.preventDefault()
  costumeContextMenu.value = { show: true, x: e.clientX, y: e.clientY, index }
}

function deleteCostume(index: number) {
  if (!currentSprite.value) return
  currentSprite.value.frames.splice(index, 1)
  for (const anim of currentSprite.value.animations) {
    if (anim.end > currentSprite.value.frames.length) {
      anim.end = currentSprite.value.frames.length
    }
    if (anim.start > anim.end) anim.start = anim.end
  }
  if (selectedFrameIndex.value >= currentSprite.value.frames.length) {
    selectedFrameIndex.value = Math.max(0, currentSprite.value.frames.length - 1)
  }
  costumeContextMenu.value.show = false
}

function onAnimContextMenu(e: MouseEvent, name: string) {
  e.preventDefault()
  animContextMenu.value = { show: true, x: e.clientX, y: e.clientY, name }
}

let wasPlayingBeforeRename = false

function startRename(animName: string) {
  wasPlayingBeforeRename = isPlaying.value
  stopAnimation()
  renamingAnim.value = animName
  nextTick(() => {
    if (renameInputRef.value) {
      renameInputRef.value.focus()
      renameInputRef.value.select()
    }
  })
}

function closeContextMenus() {
  costumeContextMenu.value.show = false
  animContextMenu.value.show = false
}

// 注册全局 mouseup 监听
document.addEventListener('mouseup', onGlobalMouseUp)

onBeforeUnmount(() => {
  stopAnimation()
  document.removeEventListener('mouseup', onGlobalMouseUp)
})
</script>

<template>
  <div class="sprite-editor-page" @click="closeContextMenus">
    <!-- 左: 造型列表 (100px) -->
    <div class="costume-list">
      <div
        v-for="(frame, idx) in (currentSprite?.frames || [])"
        :key="idx"
        class="costume-item"
        :class="{ 'costume-item-active': costumeHighlightIndex === idx }"
        @click="selectFrame(idx)"
        @contextmenu="onCostumeContextMenu($event, idx)"
      >
        <img :src="frame.url" class="costume-thumb" :style="{ imageRendering: imageRenderingStyle }" />
        <span class="costume-frame-num">帧 {{ idx + 1 }}</span>
      </div>
    </div>

    <!-- 中: 画布 -->
    <div
      ref="canvasRef"
      class="sprite-canvas"
      :class="{ 'is-panning': isPanning }"
      @wheel.prevent="onCanvasWheel"
      @mousedown="onCanvasMouseDown"
      @mousemove="onCanvasMouseMove"
      @mouseup="onCanvasMouseUp"
      @mouseleave="onCanvasMouseUp"
      @dblclick="resetCanvas"
    >
      <div class="canvas-center-anchor">
        <div
          class="canvas-sprite-wrapper"
          :style="{
            transform: `translate(${canvasPanX}px, ${canvasPanY}px) scale(${canvasZoom})`
          }"
        >
          <img
            v-if="currentSprite?.frames[canvasDisplayIndex]"
            :src="currentSprite.frames[canvasDisplayIndex].url"
            class="canvas-sprite"
            :style="{ imageRendering: imageRenderingStyle }"
          />
        </div>
      </div>
    </div>

    <!-- 右: 预览面板 (264px) -->
    <div class="preview-panel">
      <div class="preview-label">ANIMATION</div>

      <!-- 预览区域 256×256 -->
      <div class="preview-bg">
        <div class="preview-image-box" :style="getPreviewBgStyle()">
          <img
            v-if="currentSprite?.frames[selectedFrameIndex]"
            :src="currentSprite.frames[selectedFrameIndex].url"
            class="preview-image"
            :style="{ transform: `scale(${previewScale})`, imageRendering: imageRenderingStyle }"
          />
          <!-- FPS 滑块 (悬浮在预览底部) -->
          <div class="fps-slider-overlay">
            <div class="fps-spacer"></div>
            <input type="range" v-model.number="fpsValue" min="1" max="60" class="fps-slider" />
            <div class="fps-spacer"></div>
          </div>
        </div>
      </div>

      <!-- 按钮栏 -->
      <div class="preview-btns">
        <button class="prev-btn" @click="prevFrame"><img :src="iconPrev" /></button>
        <button class="prev-btn" :class="{ active: isPlaying }" @click="togglePlay">
          <img :src="isPlaying ? iconPause : iconPlay" />
        </button>
        <button class="prev-btn" @click="nextFrame"><img :src="iconNext" /></button>
        <button class="prev-btn" @click="toggleScale"><img :src="iconScale" /></button>
        <button class="prev-btn" @click="changeBg"><img :src="iconChangeBg" /></button>
        <button class="prev-btn" @click="addAnimation"><img :src="iconAdd" /></button>
      </div>

      <!-- 动画列表 -->
      <div class="anim-list">
        <div
          v-for="anim in (currentSprite?.animations || [])"
          :key="anim.name"
          class="anim-item"
          :class="{ 'anim-item-active': selectedAnim?.name === anim.name }"
          @click="selectAnimation(anim)"
          @contextmenu="onAnimContextMenu($event, anim.name)"
        >
          <div class="anim-item-row">
            <template v-if="renamingAnim === anim.name">
              <input
                ref="renameInputRef"
                class="anim-rename-input"
                :value="anim.name"
                @blur="renameAnimation(anim.name, ($event.target as HTMLInputElement).value)"
                @keydown.enter="renameAnimation(anim.name, ($event.target as HTMLInputElement).value)"
                @keydown.escape="renamingAnim = null"
                @click.stop
              />
            </template>
            <template v-else>
              <span class="anim-name" @dblclick.stop="startRename(anim.name)">{{ anim.name }}</span>
            </template>
            <div class="anim-range">
              <input
                type="number"
                class="anim-spin"
                :value="anim.start"
                min="1"
                :max="currentSprite?.frames.length || 999"
                @change="anim.start = Math.max(1, Math.min(Number(($event.target as HTMLInputElement).value), anim.end))"
                @click.stop
              />
              <span class="anim-dash">-</span>
              <input
                type="number"
                class="anim-spin"
                :value="anim.end"
                min="1"
                :max="currentSprite?.frames.length || 999"
                @change="anim.end = Math.max(anim.start, Math.min(Number(($event.target as HTMLInputElement).value), currentSprite?.frames.length || 999))"
                @click.stop
              />
              <button class="anim-loop-btn" @click.stop="toggleLoop(anim)">
                <img :src="anim.loop !== false ? iconLoop : iconLoopOff" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 右键菜单: 造型 -->
    <Teleport to="body">
      <div
        v-if="costumeContextMenu.show"
        class="context-menu"
        :style="{ left: costumeContextMenu.x + 'px', top: costumeContextMenu.y + 'px' }"
        @click.stop
      >
        <div class="context-menu-item" @click="deleteCostume(costumeContextMenu.index)">
          删除造型: {{ costumeContextMenu.index + 1 }}
        </div>
      </div>
    </Teleport>

    <!-- 右键菜单: 动画 -->
    <Teleport to="body">
      <div
        v-if="animContextMenu.show"
        class="context-menu"
        :style="{ left: animContextMenu.x + 'px', top: animContextMenu.y + 'px' }"
        @click.stop
      >
        <div class="context-menu-item" @click="deleteAnimation(animContextMenu.name)">
          删除动作
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.sprite-editor-page {
  display: flex;
  height: 100%;
  background: rgb(34, 37, 43);
  user-select: none;
  -webkit-user-select: none;
}

/* ═══ 左: 造型列表 ═══ */
.costume-list {
  width: 100px;
  min-width: 100px;
  padding: 8px 4px;
  border-right: 1px solid rgb(12, 12, 12);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: rgb(34, 37, 43);
}
.costume-list::-webkit-scrollbar { width: 0; height: 0; }
.costume-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4px;
  border: 1px solid #2d2d2d;
  border-radius: 4px;
  cursor: pointer;
  background: #1e1e1e;
}
.costume-item:hover { background: #3e4451; border-color: #4a4f58; }
.costume-item.costume-item-active { border-color: transparent; background: #3e4451; box-shadow: inset 0 0 0 2px rgb(91, 199, 114); }
.costume-item.costume-item-active:hover { box-shadow: inset 0 0 0 2px rgb(91, 199, 114); }
.costume-thumb {
  width: 78px;
  height: 60px;
  object-fit: contain;
}
.costume-frame-num {
  font-size: 10px;
  color: #abb2bf;
  margin-top: 2px;
}

/* ═══ 中: 画布 ═══ */
.sprite-canvas {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgb(34, 37, 43);
  min-width: 0;
  overflow: hidden;
  cursor: default;
}
.sprite-canvas.is-panning {
  cursor: grabbing;
}
.canvas-center-anchor {
  display: flex;
  align-items: center;
  justify-content: center;
}
.canvas-sprite-wrapper {
  transform-origin: 0 0;
}
.canvas-sprite {
  display: block;
  background-color: #ffffff;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16'%3E%3Crect width='16' height='16' fill='%23fff'/%3E%3Crect width='8' height='8' fill='%23e0e0e0'/%3E%3Crect x='8' y='8' width='8' height='8' fill='%23e0e0e0'/%3E%3C/svg%3E");
}

/* ═══ 右: 预览面板 ═══ */
.preview-panel {
  width: 264px;
  min-width: 264px;
  border-left: 1px solid rgb(12, 12, 12);
  display: flex;
  flex-direction: column;
  background: rgb(34, 37, 43);
  padding: 0 8px;
}

.preview-label {
  color: #00FF8C;
  font-size: 12px;
  text-align: center;
  height: 26px;
  line-height: 26px;
  padding: 0;
  margin: 0;
  border: none;
  background: rgb(34, 37, 43);
  flex-shrink: 0;
}

/* 预览背景 */
.preview-bg {
  margin: 0;
  padding: 0;
}
.preview-image-box {
  position: relative;
  width: 100%;
  height: 256px;
  border: 1px solid rgb(69, 69, 69);
  background: #1E1E1E;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.preview-image {
  max-width: 248px;
  max-height: 248px;
}

/* FPS 滑块 (悬浮在预览底部) */
.fps-slider-overlay {
  position: absolute;
  bottom: 8px;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  padding: 4px 4px;
}
.fps-spacer { flex: 1; }
.fps-slider {
  flex: 2;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: rgb(55, 59, 68);
  border-radius: 2px;
  outline: none;
  margin: 0 4px;
}
.fps-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #9ca0a4;
  cursor: pointer;
}
.fps-slider::-webkit-slider-thumb:hover {
  background: #abb2bf;
}

/* 按钮栏 */
.preview-btns {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 6px 0;
}
.prev-btn {
  width: 38px;
  height: 24px;
  border: none;
  border-radius: 4px;
  background: rgb(40, 43, 52);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: background 0.12s;
}
.prev-btn:hover { background: rgb(62, 66, 79); }
.prev-btn.active { background: rgb(55, 120, 200); }
.prev-btn img { width: 28px; height: 16px; }

/* 动画列表 */
.anim-list {
  flex: 1;
  margin: 0;
  padding: 0;
  border: none;
  background: #1E1E1E;
  overflow-y: auto;
}
.anim-item {
  padding: 6px 8px;
  font-size: 12px;
  color: rgb(200, 200, 200);
  cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.anim-item:hover { background: #3e4451; }
.anim-item-active { background: #528bff; color: white; }
.anim-item-active:hover { background: #528bff; }

.anim-item-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.anim-name {
  flex-shrink: 0;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-left: 4px;
}
.anim-rename-input {
  flex-shrink: 0;
  width: 90px;
  height: 22px;
  background: rgb(30, 30, 40);
  border: 1px solid #528bff;
  border-radius: 3px;
  color: white;
  font-size: 12px;
  padding: 0 6px;
  outline: none;
  box-shadow: 0 0 0 1px rgba(82, 139, 255, 0.3);
}
.anim-range {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: auto;
}
.anim-spin {
  width: 35px;
  height: 20px;
  background: rgba(0,0,0,0.3);
  border: none;
  border-radius: 2px;
  color: white;
  font-size: 11px;
  text-align: center;
  padding: 0;
  outline: none;
  -moz-appearance: textfield;
}
.anim-spin::-webkit-outer-spin-button,
.anim-spin::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
.anim-dash { color: #9ca0a4; font-size: 11px; }
.anim-loop-btn {
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: background 0.12s;
}
.anim-loop-btn:hover { background: rgba(255,255,255,0.1); }
.anim-loop-btn img { width: 16px; height: 16px; }

/* 右键菜单 */
:global(.context-menu) {
  position: fixed;
  background: rgb(34, 37, 43);
  border: 1px solid rgb(60, 60, 60);
  border-radius: 6px;
  padding: 4px 0;
  z-index: 9999;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
  min-width: 120px;
}
:global(.context-menu-item) {
  padding: 6px 14px;
  font-size: 12px;
  color: rgb(200, 200, 200);
  cursor: pointer;
  transition: background 0.1s;
}
:global(.context-menu-item:hover) {
  background: rgb(61, 64, 72);
  color: white;
}
</style>
