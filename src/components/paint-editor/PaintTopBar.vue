<script setup lang="ts">
import { usePaintStore, ARTBOARD_MAX } from '../../stores/paint'

import iconClose from '../../assets/icons/关闭.svg'
import iconSave from '../../assets/icons/保存.svg'
import iconCrop from '../../assets/icons/裁切画板.svg'
import iconCopy from '../../assets/icons/copy.svg'
import iconPaste from '../../assets/icons/粘贴.svg'
import iconDeleteSel from '../../assets/icons/选中删除.svg'
import iconFlipH from '../../assets/icons/水平翻转.svg'
import iconFlipV from '../../assets/icons/垂直翻转.svg'
import iconGroup from '../../assets/icons/组合.svg'
import iconUngroup from '../../assets/icons/取消组合.svg'
import iconLayerUp from '../../assets/icons/上移图层.svg'
import iconLayerDown from '../../assets/icons/下移图层.svg'
import iconCurve from '../../assets/icons/曲线.svg'
import iconStraight from '../../assets/icons/折线.svg'

const props = defineProps<{
  /** 保存按钮提示（编辑模式为「保存回角色」） */
  saveTitle?: string
}>()

const emit = defineEmits<{
  close: []
  save: []
  crop: []
  copy: []
  paste: []
  deleteSel: []
  flipH: []
  flipV: []
  group: []
  ungroup: []
  layerUp: []
  layerDown: []
  /** 塑形：选中锚点曲线化/折线化 */
  curvePoints: []
  pointPoints: []
}>()

const store = usePaintStore()

// ─── 模式感知的可用状态（位图看选区/剪贴板，矢量看对象选中/矢量剪贴板）───
const isVector = () => store.mode === 'vector'
const canCopy = () => (isVector() ? store.vectorSelectedCount > 0 : !!store.selection)
const canPaste = () => (isVector() ? store.hasVectorClipboard : !!store.hasClipboard)

// ─── 塑形锚点形态 toggle：选中锚点含手柄=曲线态；无手柄或未选=折线态（默认折线）───
const reshapeCurveActive = () => store.reshapeHasPointed
// 激活侧点击为安全空操作；未激活侧仅在确有可转换锚点时可点
const curveDisabled = () => !store.reshapeHasUncurved && !store.reshapeHasPointed
const pointDisabled = () => false

/** 手动输入画板尺寸：clamp 1~2048，失焦/回车提交 */
function commitSize(axis: 'w' | 'h', e: Event) {
  const el = e.target as HTMLInputElement
  let v = Math.round(Number(el.value))
  if (!Number.isFinite(v)) {
    v = axis === 'w' ? store.artboardWidth : store.artboardHeight
  }
  v = Math.min(ARTBOARD_MAX, Math.max(1, v))
  if (axis === 'w') store.artboardWidth = v
  else store.artboardHeight = v
  el.value = String(v)
  store.resetView()
}
</script>

<template>
  <div class="paint-topbar">
    <!-- 左：矢量 | 位图 模式切换 -->
    <div class="mode-switch">
      <button
        class="mode-btn"
        :class="{ 'mode-btn-active': store.mode === 'vector' }"
        :disabled="!store.vectorEnabled"
        :title="store.vectorEnabled ? '矢量模式' : '矢量模式即将开放'"
        @click="store.setMode('vector')"
      >
        矢量
      </button>
      <button
        class="mode-btn"
        :class="{ 'mode-btn-active': store.mode === 'bitmap' }"
        title="位图模式"
        @click="store.setMode('bitmap')"
      >
        位图
      </button>
    </div>

    <!-- 中右：画板尺寸手动输入（1~2048，开画后锁定；追加模式全程锁定）+ 一键裁切到内容 -->
    <div
      class="size-inputs"
      :title="store.sizeForced ? '追加帧：画板尺寸与角色帧一致，不可修改' : store.dirty ? '开始绘制后不能修改画板尺寸（可用右侧裁切按钮裁掉空白）' : '画板尺寸'"
    >
      <input
        class="size-input"
        type="number"
        min="1"
        :max="ARTBOARD_MAX"
        :disabled="store.dirty || store.sizeForced"
        :value="store.artboardWidth"
        aria-label="画板宽度"
        @change="commitSize('w', $event)"
        @keydown.enter="commitSize('w', $event)"
      />
      <span class="size-x">×</span>
      <input
        class="size-input"
        type="number"
        min="1"
        :max="ARTBOARD_MAX"
        :disabled="store.dirty || store.sizeForced"
        :value="store.artboardHeight"
        aria-label="画板高度"
        @change="commitSize('h', $event)"
        @keydown.enter="commitSize('h', $event)"
      />
      <span class="size-unit">px</span>
    </div>
    <button
      class="icon-btn"
      :disabled="!store.dirty || store.mode !== 'bitmap' || store.vectorContent"
      v-tooltip="store.vectorContent ? '存在矢量内容时不能裁切（会与矢量层错位）' : '裁切画板到内容'"
      @click="emit('crop')"
    >
      <img :src="iconCrop" class="icon-sm" draggable="false" />
    </button>

    <!-- 塑形工具专属：选中锚点形态 toggle（曲线 ⇄ 折线，二选一激活；默认折线） -->
    <div v-if="store.mode === 'vector' && store.activeTool === 'reshape'" class="op-group">
      <button
        class="icon-btn"
        :class="{ 'icon-btn-active': reshapeCurveActive() }"
        :disabled="curveDisabled()"
        v-tooltip="reshapeCurveActive() ? '曲线（当前）' : '选中锚点转为曲线'"
        @click="emit('curvePoints')"
      >
        <img :src="iconCurve" class="icon-sm" draggable="false" />
      </button>
      <button
        class="icon-btn"
        :class="{ 'icon-btn-active': !reshapeCurveActive() }"
        :disabled="pointDisabled()"
        v-tooltip="!reshapeCurveActive() ? '折线（当前）' : '选中锚点转为折线（尖角）'"
        @click="emit('pointPoints')"
      >
        <img :src="iconStraight" class="icon-sm" draggable="false" />
      </button>
    </div>

    <!-- 选区/对象操作组（工业软件 options bar 风格，按模式切换可用性） -->
    <div class="op-group">
      <button class="icon-btn" :disabled="!canCopy()" v-tooltip="isVector() ? '复制对象 (Ctrl+C)' : '复制选区 (Ctrl+C)'" @click="emit('copy')">
        <img :src="iconCopy" class="icon-sm" draggable="false" />
      </button>
      <button class="icon-btn" :disabled="!canPaste()" v-tooltip="isVector() ? '粘贴对象 (Ctrl+V)' : '粘贴 (Ctrl+V)'" @click="emit('paste')">
        <img :src="iconPaste" class="icon-sm" draggable="false" />
      </button>
      <button class="icon-btn" :disabled="!canCopy()" v-tooltip="isVector() ? '删除对象 (Delete)' : '删除选区 (Delete)'" @click="emit('deleteSel')">
        <img :src="iconDeleteSel" class="icon-sm" draggable="false" />
      </button>
      <!-- 矢量专属：组合/解组/图层（位图无对象层级，整组隐藏） -->
      <template v-if="isVector()">
        <div class="op-divider"></div>
        <button class="icon-btn" :disabled="store.vectorSelectedCount < 2" v-tooltip="'组合选中对象'" @click="emit('group')">
          <img :src="iconGroup" class="icon-sm" draggable="false" />
        </button>
        <button class="icon-btn" :disabled="!store.vectorCanUngroup" v-tooltip="'取消组合'" @click="emit('ungroup')">
          <img :src="iconUngroup" class="icon-sm" draggable="false" />
        </button>
        <button class="icon-btn" :disabled="store.vectorSelectedCount < 1" v-tooltip="'上移一层'" @click="emit('layerUp')">
          <img :src="iconLayerUp" class="icon-sm" draggable="false" />
        </button>
        <button class="icon-btn" :disabled="store.vectorSelectedCount < 1" v-tooltip="'下移一层'" @click="emit('layerDown')">
          <img :src="iconLayerDown" class="icon-sm" draggable="false" />
        </button>
      </template>
      <div class="op-divider"></div>
      <button class="icon-btn" v-tooltip="'水平翻转（无选区时翻转整层/整帧）'" @click="emit('flipH')">
        <img :src="iconFlipH" class="icon-sm" draggable="false" />
      </button>
      <button class="icon-btn" v-tooltip="'垂直翻转（无选区时翻转整层/整帧）'" @click="emit('flipV')">
        <img :src="iconFlipV" class="icon-sm" draggable="false" />
      </button>
    </div>

    <div class="topbar-spacer"></div>

    <!-- 最右：关闭 + 保存 -->
    <div class="topbar-actions">
      <button class="back-btn" v-tooltip="'关闭'" @click="emit('close')">
        <img :src="iconClose" class="icon-sm icon-close" draggable="false" />
        <span>关闭</span>
      </button>
      <button
        class="save-btn"
        :disabled="!store.dirty"
        :title="store.dirty ? (props.saveTitle || '保存为新角色') : '画板为空，先画点什么'"
        @click="emit('save')"
      >
        <img :src="iconSave" class="icon-sm" draggable="false" />
        <span>保存</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.paint-topbar {
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 10px 0 4px;
  gap: 10px;
  background: var(--bg-base);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  user-select: none;
  position: relative;
  /* 窄窗口下按钮不压缩、不换行：内容超出由窗口裁剪，图标保持原样 */
  flex-wrap: nowrap;
  overflow: hidden;
}

/* 纯白 SVG 图标在暗色主题下直接可见，无需滤镜 */

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
  transition: background 0.15s;
}
.icon-btn:hover:not(:disabled) {
  background: var(--bg-hover);
}
.icon-btn:disabled {
  opacity: 0.35;
  cursor: default;
}
/* toggle 激活态（曲线/折线互斥）：对齐 mode-btn-active */
.icon-btn-active,
.icon-btn-active:hover:not(:disabled) {
  background: var(--bg-active);
}

.icon-sm {
  width: 18px;
  height: 18px;
  pointer-events: none;
}
/* 关闭图标单独缩小（须在 .icon-sm 之后，同权重后者生效） */
.icon-close {
  width: 13px;
  height: 13px;
}

/* 矢量|位图 分段切换（不参与压缩：窄窗口下文字不竖排） */
.mode-switch {
  display: flex;
  background: var(--bg-panel);
  border-radius: 6px;
  padding: 2px;
  gap: 2px;
  flex-shrink: 0;
}

.mode-btn {
  padding: 4px 12px;
  font-size: 12px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}
.mode-btn:hover:not(:disabled):not(.mode-btn-active) {
  color: var(--text-secondary);
}
/* 激活态：强调绿底 + 深色文字（亮绿底上深色对比最佳） */
.mode-btn-active {
  background: var(--accent);
  color: #16201a;
  font-weight: 600;
}
.mode-btn:disabled {
  opacity: 0.45;
  cursor: default;
}

.size-inputs {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.size-input {
  width: 54px;
  height: 26px;
  padding: 0 6px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 5px;
  outline: none;
  text-align: center;
  /* 隐藏 number 上下箭头，保持紧凑 */
  -moz-appearance: textfield;
  appearance: textfield;
}
.size-input::-webkit-outer-spin-button,
.size-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.size-input:hover:not(:disabled) {
  border-color: var(--text-muted);
}
.size-input:focus {
  border-color: var(--accent);
}
.size-input:disabled {
  opacity: 0.45;
  cursor: default;
}

.size-x {
  font-size: 12px;
  color: var(--text-muted);
}

.size-unit {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: -2px;
}

.topbar-spacer {
  flex: 1;
}

/* 选区/对象操作组 */
.op-group {
  display: flex;
  align-items: center;
  gap: 2px;
  padding-left: 8px;
  margin-left: 4px;
  border-left: 1px solid var(--border-light);
  flex-shrink: 0;
}

.op-divider {
  width: 1px;
  height: 16px;
  margin: 0 4px;
  background: var(--border-light);
}

/* 最右关闭/保存组：钉成与下方颜色面板同宽的列（左缘=面板左边框 200px，右缘=顶栏内边距） */
.topbar-actions {
  position: absolute;
  right: 10px;
  width: 190px; /* 面板 200px − 顶栏右 padding 10px */
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

/* 关闭：次级按钮（描边幽灵风，占列内剩余宽度） */
.back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 30px;
  flex: 1;
  min-width: 0;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
  background: transparent;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.back-btn:hover {
  background: var(--bg-hover);
  color: var(--text);
  border-color: var(--text-muted);
}

/* 保存：主操作（中深绿底 + 纯白图标/文字；brightness 1.15 = 背景与前景整体提亮 15%） */
.save-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 30px;
  flex: 1; /* 与关闭等宽 */
  min-width: 0;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: #ffffff;
  white-space: nowrap;
  background: #2b8a48;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  filter: brightness(1.15);
  transition: background 0.15s, opacity 0.15s;
}
.save-btn:hover:not(:disabled) {
  background: #33a056;
}
.save-btn:disabled {
  opacity: 0.45;
  cursor: default;
}
</style>
