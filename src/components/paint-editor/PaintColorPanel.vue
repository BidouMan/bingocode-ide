<script setup lang="ts">
import { ref, watch } from 'vue'
import { usePaintStore } from '../../stores/paint'

const store = usePaintStore()

// ─── HSV 模型（本地编辑状态，与 store 的 hex 颜色双向同步）───
const hue = ref(120) // 0-360
const sat = ref(0.64) // 0-1
const val = ref(0.98) // 0-1

function clamp(n: number, min: number, max: number) {
  return Math.min(max, Math.max(min, n))
}

function hsvToHex(h: number, s: number, v: number): string {
  const c = v * s
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1))
  const m = v - c
  let r = 0
  let g = 0
  let b = 0
  if (h < 60) { r = c; g = x }
  else if (h < 120) { r = x; g = c }
  else if (h < 180) { g = c; b = x }
  else if (h < 240) { g = x; b = c }
  else if (h < 300) { r = x; b = c }
  else { r = c; b = x }
  const toHex = (n: number) => Math.round((n + m) * 255).toString(16).padStart(2, '0')
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`
}

function hexToHsv(hex: string): { h: number; s: number; v: number } {
  const m = hex.match(/^#?([0-9a-f]{6})$/i)
  if (!m) return { h: 0, s: 0, v: 1 }
  const n = parseInt(m[1], 16)
  const r = ((n >> 16) & 0xff) / 255
  const g = ((n >> 8) & 0xff) / 255
  const b = (n & 0xff) / 255
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const d = max - min
  let h = 0
  if (d !== 0) {
    if (max === r) h = 60 * (((g - b) / d) % 6)
    else if (max === g) h = 60 * ((b - r) / d + 2)
    else h = 60 * ((r - g) / d + 4)
  }
  if (h < 0) h += 360
  return { h, s: max === 0 ? 0 : d / max, v: max }
}

// 外部颜色变化（reset 等）→ 重推 HSV；自身交互变化不回写防抖动
let internalChange = false

function commitColor() {
  internalChange = true
  store.fillColor = hsvToHex(hue.value, sat.value, val.value)
  internalChange = false
}

watch(
  () => store.fillColor,
  (hex) => {
    if (internalChange) return
    const hsv = hexToHsv(hex)
    hue.value = hsv.h
    sat.value = hsv.s
    val.value = hsv.v
  },
  { immediate: true }
)

// ─── SV 方块交互 ───
const svRef = ref<HTMLDivElement>()

function updateSvFromEvent(e: PointerEvent) {
  const el = svRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  sat.value = clamp((e.clientX - rect.left) / rect.width, 0, 1)
  val.value = clamp(1 - (e.clientY - rect.top) / rect.height, 0, 1)
  commitColor()
}

function onSvPointerDown(e: PointerEvent) {
  if (e.button !== 0) return
  svRef.value?.setPointerCapture(e.pointerId)
  updateSvFromEvent(e)
}

function onSvPointerMove(e: PointerEvent) {
  if (e.buttons !== 1) return
  updateSvFromEvent(e)
}

// ─── 色相条交互 ───
const hueRef = ref<HTMLDivElement>()

function updateHueFromEvent(e: PointerEvent) {
  const el = hueRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  hue.value = clamp(((e.clientX - rect.left) / rect.width) * 360, 0, 360)
  commitColor()
}

function onHuePointerDown(e: PointerEvent) {
  if (e.button !== 0) return
  hueRef.value?.setPointerCapture(e.pointerId)
  updateHueFromEvent(e)
}

function onHuePointerMove(e: PointerEvent) {
  if (e.buttons !== 1) return
  updateHueFromEvent(e)
}

// SV 方块底色 = 当前色相的纯色
const svBackground = () => `hsl(${hue.value}, 100%, 50%)`

// 尺寸滑条：按当前工具显示 笔刷大小 或 线宽
const showBrushSize = () => store.activeTool === 'brush' || store.activeTool === 'eraser'
const showStrokeWidth = () => store.activeTool === 'line' || store.activeTool === 'rect' || store.activeTool === 'ellipse'
</script>

<template>
  <div class="color-panel">
    <!-- 当前绘制色（所有工具共用，切换工具不变色） -->
    <div class="panel-label">绘制颜色</div>
    <div class="color-preview-row">
      <div class="color-swatch" :style="{ background: store.fillColor }"></div>
      <span class="color-hex">{{ store.fillColor.toUpperCase() }}</span>
    </div>

    <!-- 饱和度-明度方块 -->
    <div
      ref="svRef"
      class="sv-square"
      :style="{ background: svBackground() }"
      @pointerdown="onSvPointerDown"
      @pointermove="onSvPointerMove"
    >
      <div class="sv-bright"></div>
      <div class="sv-sat"></div>
      <div
        class="sv-marker"
        :style="{ left: `${sat * 100}%`, top: `${(1 - val) * 100}%` }"
      ></div>
    </div>

    <!-- 色相条 -->
    <div
      ref="hueRef"
      class="hue-strip"
      @pointerdown="onHuePointerDown"
      @pointermove="onHuePointerMove"
    >
      <div class="hue-marker" :style="{ left: `${(hue / 360) * 100}%` }"></div>
    </div>

    <!-- 不透明度 -->
    <div class="slider-row">
      <label class="slider-label">不透明度</label>
      <input
        v-model.number="store.opacity"
        class="paint-slider"
        type="range"
        min="0"
        max="100"
        step="1"
      />
      <span class="slider-value">{{ store.opacity }}%</span>
    </div>

    <!-- 笔刷大小（画笔/橡皮） -->
    <div v-if="showBrushSize()" class="slider-row">
      <label class="slider-label">笔刷大小</label>
      <input
        v-model.number="store.brushSize"
        class="paint-slider"
        type="range"
        min="1"
        max="64"
        step="1"
      />
      <span class="slider-value">{{ store.brushSize }}</span>
    </div>

    <!-- 线宽（直线/矩形/椭圆） -->
    <div v-if="showStrokeWidth()" class="slider-row">
      <label class="slider-label">线宽</label>
      <input
        v-model.number="store.strokeWidth"
        class="paint-slider"
        type="range"
        min="1"
        max="40"
        step="1"
      />
      <span class="slider-value">{{ store.strokeWidth }}</span>
    </div>
  </div>
</template>

<style scoped>
.color-panel {
  display: flex;
  flex-direction: column;
  width: 200px;
  padding: 12px;
  gap: 12px;
  background: var(--bg-base);
  border-left: 1px solid var(--border);
  flex-shrink: 0;
  overflow-y: auto;
  user-select: none;
}

/* 面板小节标题 */
.panel-label {
  font-size: 11px;
  color: var(--text-muted);
}

/* 当前颜色 */
.color-preview-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.color-swatch {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  border: 1px solid var(--border-light);
  flex-shrink: 0;
}

.color-hex {
  font-size: 12px;
  font-family: var(--font-mono, monospace);
  color: var(--text-secondary);
}

/* 饱和度-明度方块 */
.sv-square {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--border-light);
  cursor: crosshair;
  touch-action: none;
}
.sv-bright {
  position: absolute;
  inset: 0;
  background: linear-gradient(to right, #fff, rgba(255, 255, 255, 0));
}
.sv-sat {
  position: absolute;
  inset: 0;
  background: linear-gradient(to top, #000, rgba(0, 0, 0, 0));
}
.sv-marker {
  position: absolute;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.5), inset 0 0 0 1px rgba(0, 0, 0, 0.3);
  transform: translate(-50%, -50%);
  pointer-events: none;
}

/* 色相条 */
.hue-strip {
  position: relative;
  width: 100%;
  height: 16px;
  border-radius: 8px;
  border: 1px solid var(--border-light);
  background: linear-gradient(
    to right,
    #f00 0%,
    #ff0 17%,
    #0f0 33%,
    #0ff 50%,
    #00f 67%,
    #f0f 83%,
    #f00 100%
  );
  cursor: pointer;
  touch-action: none;
}
.hue-marker {
  position: absolute;
  top: 50%;
  width: 10px;
  height: 18px;
  border-radius: 3px;
  border: 2px solid #fff;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.5);
  transform: translate(-50%, -50%);
  pointer-events: none;
}

/* 滑条 */
.slider-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.slider-label {
  font-size: 11px;
  color: var(--text-muted);
}

.slider-value {
  font-size: 11px;
  color: var(--text-secondary);
  text-align: right;
}

.paint-slider {
  width: 100%;
  accent-color: var(--accent);
  cursor: pointer;
}
</style>
