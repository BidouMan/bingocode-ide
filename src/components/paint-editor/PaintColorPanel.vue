<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { usePaintStore } from '../../stores/paint'
import iconPick from '../../assets/icons/取色器.svg'

const store = usePaintStore()

// ─── 编辑手势跟踪：面板内按下 → 编辑中；window 松手（含捕获元素上的释放）→ 结束。
// 引擎据此把一次拖动的连续改色合并为一步撤销、缩略图只在结束时刷新 ───
function onPanelPointerDown() {
  store.colorEditing = true
}
function endColorEdit() {
  store.colorEditing = false
}
onMounted(() => {
  window.addEventListener('pointerup', endColorEdit)
  window.addEventListener('pointerdown', onWindowPointerDown)
})
onBeforeUnmount(() => {
  window.removeEventListener('pointerup', endColorEdit)
  window.removeEventListener('pointerdown', onWindowPointerDown)
})

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

// ─── 描边勾选区（Scratch 模型：仅形状预设与选中图形编辑；画笔/橡皮/直线不显示）───
// 勾选态：有选中图形=其实际描边态（引擎同步）；其余=新形状预设 strokeEnabled。
const showStrokeSection = () => {
  if (store.activeTool === 'brush' || store.activeTool === 'eraser' || store.activeTool === 'line') {
    return false
  }
  if (store.activeTool === 'rect' || store.activeTool === 'ellipse') return true
  // 选择/塑形等：有选中矢量图形时可编辑其描边
  return store.mode === 'vector' && store.vectorSelectedCount > 0
}
const strokeChecked = () => {
  if (store.mode === 'vector' && store.vectorSelectedCount > 0) return store.selectionHasStroke
  return store.strokeEnabled
}
// 选中图形全部为"本体描边"（直线/描边轮廓）：本体不可去描边 → 勾选框禁用
const strokeToggleDisabled = () =>
  store.mode === 'vector' && store.vectorSelectedCount > 0 && store.selectionBodyOnly
// 粗细下限：选中含本体描边对象时抬到 1（拖到 0 会删本体致整条线消失）
const strokeMin = () =>
  store.mode === 'vector' && store.vectorSelectedCount > 0 && store.selectionHasBodyStroke ? 1 : 0

function onStrokeToggle(e: Event) {
  store.strokeEnabled = (e.target as HTMLInputElement).checked
  store.strokeToggleTick++ // 预设残留时 strokeEnabled 新旧值可能相同，tick 保证 watch 必触发
}

// 勾选收起时同步关闭描边色弹层（防下次勾选时弹层自动弹开）
watch(strokeChecked, (v) => {
  if (!v) strokePop.value = false
})

// ─── 描边色弹层（迷你 SV+色相条，编辑 store.strokeColor）───
const strokePop = ref(false)
const sHue = ref(0)
const sSat = ref(0)
const sVal = ref(1)
let internalS = false

function commitStrokeColor() {
  internalS = true
  store.strokeColor = hsvToHex(sHue.value, sSat.value, sVal.value)
  internalS = false
}

watch(
  () => store.strokeColor,
  (hex) => {
    if (internalS) return
    const hsv = hexToHsv(hex)
    sHue.value = hsv.h
    sSat.value = hsv.s
    sVal.value = hsv.v
  },
  { immediate: true }
)

// 点击弹层外部关闭
function onWindowPointerDown(e: PointerEvent) {
  if (!strokePop.value) return
  const t = e.target as HTMLElement | null
  if (!t || !t.closest('.stroke-color-wrap')) strokePop.value = false
}

// ─── 拾色（吸管）：开启后点击画板取该点像素色写入目标通道（引擎在画板点击时消费）───
function startPick(target: 'fill' | 'stroke') {
  if (store.eyedropperActive && store.eyedropperTarget === target) {
    store.eyedropperActive = false // 再点同按钮=取消
  } else {
    store.eyedropperTarget = target
    store.eyedropperActive = true
  }
}

const sSvRef = ref<HTMLDivElement>()
const sHueRef = ref<HTMLDivElement>()

function updatePopSvFromEvent(e: PointerEvent) {
  const el = sSvRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  sSat.value = clamp((e.clientX - rect.left) / rect.width, 0, 1)
  sVal.value = clamp(1 - (e.clientY - rect.top) / rect.height, 0, 1)
  commitStrokeColor()
}

function onPopSvPointerDown(e: PointerEvent) {
  if (e.button !== 0) return
  sSvRef.value?.setPointerCapture(e.pointerId)
  updatePopSvFromEvent(e)
}

function onPopSvPointerMove(e: PointerEvent) {
  if (e.buttons !== 1) return
  updatePopSvFromEvent(e)
}

function updatePopHueFromEvent(e: PointerEvent) {
  const el = sHueRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  sHue.value = clamp(((e.clientX - rect.left) / rect.width) * 360, 0, 360)
  commitStrokeColor()
}

function onPopHuePointerDown(e: PointerEvent) {
  if (e.button !== 0) return
  sHueRef.value?.setPointerCapture(e.pointerId)
  updatePopHueFromEvent(e)
}

function onPopHuePointerMove(e: PointerEvent) {
  if (e.buttons !== 1) return
  updatePopHueFromEvent(e)
}

const sSvBackground = () => `hsl(${sHue.value}, 100%, 50%)`

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

// 尺寸滑条：按当前工具显示 笔刷大小
// 尺寸滑条：按当前工具显示 笔刷大小
const showBrushSize = () => store.activeTool === 'brush' || store.activeTool === 'eraser'
// 直线本体粗细（独立于描边机制，默认 8）
const showLineWidth = () => store.activeTool === 'line'
</script>

<template>
  <div class="color-panel" @pointerdown="onPanelPointerDown">
    <!-- 当前绘制色（所有工具共用，切换工具不变色） -->
    <div class="panel-label">绘制颜色</div>
    <!-- 当前绘制色：吸管 + 色块（统一 24px，与描边行按钮成列对齐）+ hex -->
    <div class="color-preview-row">
      <button
        class="pick-btn"
        :class="{ 'pick-btn-active': store.eyedropperActive && store.eyedropperTarget === 'fill' }"
        title="从画板拾取颜色"
        @click="startPick('fill')"
      >
        <img :src="iconPick" class="pick-icon" draggable="false" />
      </button>
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

    <!-- 线宽（直线本体粗细，独立于描边机制，默认 8） -->
    <div v-if="showLineWidth()" class="slider-row">
      <label class="slider-label">线宽</label>
      <input
        v-model.number="store.lineWidth"
        class="paint-slider"
        type="range"
        min="1"
        max="40"
        step="1"
      />
      <span class="slider-value">{{ store.lineWidth }}</span>
    </div>

    <!-- 描边（Scratch 模型：仅形状预设与选中图形编辑；勾选后展开颜色与粗细） -->
    <div v-if="showStrokeSection()" class="stroke-section">
      <label class="stroke-toggle-label">
        <input
          type="checkbox"
          class="stroke-check"
          :checked="strokeChecked()"
          :disabled="strokeToggleDisabled()"
          @change="onStrokeToggle"
        />
        描边
      </label>
      <!-- 勾选后展开：吸管 + 描边色块（与主色行按钮成列对齐）+ 描边粗细 -->
      <template v-if="strokeChecked()">
        <div v-if="store.mode === 'vector'" class="stroke-color-row">
          <button
            class="pick-btn"
            :class="{ 'pick-btn-active': store.eyedropperActive && store.eyedropperTarget === 'stroke' }"
            title="从画板拾取描边颜色"
            @click="startPick('stroke')"
          >
            <img :src="iconPick" class="pick-icon" draggable="false" />
          </button>
          <div class="stroke-color-wrap">
            <button
              class="stroke-color-btn"
              :style="{ background: store.strokeColor }"
              title="描边颜色"
              @click.stop="strokePop = !strokePop"
            ></button>
            <div v-if="strokePop" class="stroke-pop">
              <div
                ref="sSvRef"
                class="sv-square"
                :style="{ background: sSvBackground() }"
                @pointerdown="onPopSvPointerDown"
                @pointermove="onPopSvPointerMove"
              >
                <div class="sv-bright"></div>
                <div class="sv-sat"></div>
                <div
                  class="sv-marker"
                  :style="{ left: `${sSat * 100}%`, top: `${(1 - sVal) * 100}%` }"
                ></div>
              </div>
              <div
                ref="sHueRef"
                class="hue-strip"
                @pointerdown="onPopHuePointerDown"
                @pointermove="onPopHuePointerMove"
              >
                <div class="hue-marker" :style="{ left: `${(sHue / 360) * 100}%` }"></div>
              </div>
              <div class="stroke-pop-hex">{{ store.strokeColor.toUpperCase() }}</div>
            </div>
          </div>
        </div>
        <!-- 描边粗细（0=无描边/移除描边；选中本体描边对象时下限 1，防删本体致线条消失） -->
        <div class="slider-row">
          <label class="slider-label">描边粗细</label>
          <input
            v-model.number="store.strokeWidth"
            class="paint-slider"
            type="range"
            :min="strokeMin()"
            max="40"
            step="1"
            :title="strokeMin() > 0 ? '本体描边（直线/轮廓）最细 1' : '0 = 无描边'"
          />
          <span class="slider-value">{{ store.strokeWidth || '无' }}</span>
        </div>
      </template>
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

/* 描边勾选区 */
.stroke-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 4px;
  border-top: 1px solid var(--border-light);
}

.stroke-toggle-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

.stroke-check {
  width: 14px;
  height: 14px;
  margin: 0;
  accent-color: var(--accent);
  cursor: pointer;
}
.stroke-check:disabled {
  cursor: default;
  opacity: 0.6;
}

.stroke-color-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* flex 容器消除 inline 基线间隙——否则与相邻按钮出现一高一低 */
.stroke-color-wrap {
  position: relative;
  display: flex;
}

.stroke-color-btn {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid var(--border-light);
  cursor: pointer;
  padding: 0;
}
.stroke-color-btn:hover {
  border-color: var(--text-muted);
}

.stroke-pop {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  z-index: 30;
  width: 170px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}

.stroke-pop-hex {
  font-size: 11px;
  font-family: var(--font-mono, monospace);
  color: var(--text-secondary);
  text-align: center;
}

/* 当前颜色（色块/按钮统一 24px） */
.color-preview-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.color-swatch {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid var(--border-light);
  flex-shrink: 0;
}

.color-hex {
  font-size: 12px;
  font-family: var(--font-mono, monospace);
  color: var(--text-secondary);
  flex: 1;
}

/* 拾色按钮（与色块同尺寸 24px） */
.pick-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  background: transparent;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s, border-color 0.15s;
}
.pick-btn:hover {
  border-color: var(--text-muted);
}
.pick-btn-active {
  background: var(--bg-active);
  border-color: var(--accent);
}

.pick-icon {
  width: 15px;
  height: 15px;
  pointer-events: none;
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
