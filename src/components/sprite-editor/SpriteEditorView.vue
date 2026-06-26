<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useResourceStore } from '../../stores/resource'
import type { SpriteData, SpriteFrame, SpriteAnimation } from '../../composables/useSpriteData'
import { readBgsFromUrl } from '../../composables/useSpriteData'

import iconPrev from '../../assets/icons/btn_preview_prev.svg'
import iconPlay from '../../assets/icons/btn_preview_play.svg'
import iconPause from '../../assets/icons/btn_preview_pause.svg'
import iconNext from '../../assets/icons/btn_preview_next.svg'
import iconScale from '../../assets/icons/btn_preview_scale.svg'
import iconChangeBg from '../../assets/icons/btn_preview_change_bg.svg'
import iconAdd from '../../assets/icons/btn_preview_add.svg'

const resourceStore = useResourceStore()

const currentSprite = ref<SpriteData | null>(null)
const selectedFrameIndex = ref(0)
const selectedAnim = ref<SpriteAnimation | null>(null)
const isPlaying = ref(false)
const previewScale = ref(1)
const fpsValue = ref(10)
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
    selectedAnim.value = null
    stopAnimation()
  } catch (e) {
    console.error('Failed to load sprite:', e)
  }
}

function selectFrame(index: number) {
  selectedFrameIndex.value = index
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
  selectedFrameIndex.value = Math.max(0, selectedFrameIndex.value - 1)
}

function nextFrame() {
  if (!currentSprite.value) return
  selectedFrameIndex.value = Math.min(currentSprite.value.frames.length - 1, selectedFrameIndex.value + 1)
}

function toggleScale() {
  previewScale.value = previewScale.value === 1 ? 2 : 1
}

onBeforeUnmount(() => stopAnimation())
</script>

<template>
  <div class="sprite-editor-page">
    <!-- 左: 造型列表 (100px) -->
    <div class="costume-list">
      <div
        v-for="(frame, idx) in (currentSprite?.frames || [])"
        :key="idx"
        class="costume-item"
        :class="{ 'costume-item-active': selectedFrameIndex === idx }"
        @click="selectFrame(idx)"
      >
        <img :src="frame.url" class="costume-thumb" />
      </div>
    </div>

    <!-- 中: 画布 -->
    <div class="sprite-canvas">
      <div class="canvas-checkerboard">
        <img
          v-if="currentSprite?.frames[selectedFrameIndex]"
          :src="currentSprite.frames[selectedFrameIndex].url"
          class="canvas-sprite"
          :style="{ transform: `scale(${previewScale})` }"
        />
      </div>
    </div>

    <!-- 右: 预览面板 (264px) -->
    <div class="preview-panel">
      <div class="preview-label">ANIMATION</div>

      <!-- 预览区域 256×256 -->
      <div class="preview-bg">
        <div class="preview-image-box">
          <img
            v-if="currentSprite?.frames[selectedFrameIndex]"
            :src="currentSprite.frames[selectedFrameIndex].url"
            class="preview-image"
          />
        </div>
        <!-- FPS 滑块 -->
        <div class="fps-slider-row">
          <div class="fps-spacer"></div>
          <input type="range" v-model.number="fpsValue" min="1" max="60" class="fps-slider" />
          <div class="fps-spacer"></div>
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
        <button class="prev-btn"><img :src="iconChangeBg" /></button>
        <button class="prev-btn"><img :src="iconAdd" /></button>
      </div>

      <!-- 动画列表 -->
      <div class="anim-list">
        <div
          v-for="anim in (currentSprite?.animations || [])"
          :key="anim.name"
          class="anim-item"
          :class="{ 'anim-item-active': selectedAnim?.name === anim.name }"
          @click="selectAnimation(anim)"
        >
          {{ anim.name }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sprite-editor-page {
  display: flex;
  height: 100%;
  background: rgb(34, 37, 43);
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
  align-items: center;
  justify-content: center;
  padding: 4px;
  border-radius: 4px;
  cursor: pointer;
  background: transparent;
}
.costume-item:hover { background: transparent; }
.costume-item-active { background: transparent; }
.costume-thumb {
  width: 80px;
  height: 80px;
  object-fit: contain;
  image-rendering: pixelated;
}

/* ═══ 中: 画布 ═══ */
.sprite-canvas {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgb(34, 37, 43);
  min-width: 0;
}
.canvas-checkerboard {
  display: flex;
  align-items: center;
  justify-content: center;
  background-image:
    linear-gradient(45deg, rgb(40, 40, 40) 25%, transparent 25%),
    linear-gradient(-45deg, rgb(40, 40, 40) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, rgb(40, 40, 40) 75%),
    linear-gradient(-45deg, transparent 75%, rgb(40, 40, 40) 75%);
  background-size: 20px 20px;
  background-position: 0 0, 0 10px, 10px -10px, -10px 0;
  padding: 40px;
}
.canvas-sprite {
  image-rendering: pixelated;
  transition: transform 0.15s;
}

/* ═══ 右: 预览面板 ═══ */
.preview-panel {
  width: 264px;
  min-width: 264px;
  border-left: 1px solid rgb(12, 12, 12);
  display: flex;
  flex-direction: column;
  background: rgb(34, 37, 43);
  padding: 0;
}

.preview-label {
  color: #00FF8C;
  font-size: 12px;
  text-align: center;
  padding: 6px;
  margin: 6px;
  border: none;
  background: rgb(34, 37, 43);
}

/* 预览背景 */
.preview-bg {
  margin: 0;
  padding: 0;
}
.preview-image-box {
  width: 256px;
  height: 256px;
  margin: 0 4px;
  border: 1px solid rgb(69, 69, 69);
  background: #1E1E1E;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  overflow: hidden;
}
.preview-image {
  max-width: 248px;
  max-height: 248px;
  image-rendering: pixelated;
}

/* FPS 滑块 */
.fps-slider-row {
  display: flex;
  align-items: center;
  padding: 4px 4px 8px 4px;
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
  margin-top: -4px;
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
  padding: 8px;
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
  margin: 0 4px;
  padding: 0;
  border: none;
  background: #1E1E1E;
  overflow-y: auto;
}
.anim-item {
  padding: 8px 12px;
  font-size: 12px;
  color: rgb(200, 200, 200);
  cursor: pointer;
  transition: background 0.12s;
}
.anim-item:hover { background: #3e4451; }
.anim-item-active { background: #528bff; color: white; }
.anim-item-active:hover { background: #528bff; }
</style>
