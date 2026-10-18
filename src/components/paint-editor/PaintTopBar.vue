<script setup lang="ts">
import { usePaintStore, ARTBOARD_MAX } from '../../stores/paint'

import iconClose from '../../assets/icons/关闭_2.svg'
import iconUndo from '../../assets/icons/undo.svg'
import iconRedo from '../../assets/icons/redo.svg'
import iconZoomOut from '../../assets/icons/reduce-one.svg'
import iconZoomIn from '../../assets/icons/add-one.svg'
import iconSave from '../../assets/icons/保存.svg'
import iconCrop from '../../assets/icons/btn_preview_scale.svg'

const props = defineProps<{
  /** 顶栏标题（编辑既有角色时显示「绘制 - 角色名」） */
  title?: string
  /** 保存按钮提示（编辑模式为「保存回角色」） */
  saveTitle?: string
}>()

const emit = defineEmits<{
  close: []
  save: []
  undo: []
  redo: []
  crop: []
}>()

const store = usePaintStore()

function onZoomIn() {
  store.setZoom(store.zoom * 1.1)
}

function onZoomOut() {
  store.setZoom(store.zoom * 0.9)
}

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
    <!-- 左：关闭 + 标题 -->
    <div class="topbar-left">
      <button class="icon-btn" v-tooltip="'关闭'" @click="emit('close')">
        <img :src="iconClose" class="icon-sm" draggable="false" />
      </button>
      <span class="topbar-title">{{ props.title || '角色绘制' }}</span>
    </div>

    <!-- 中：矢量 | 位图 模式切换 -->
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
      :disabled="!store.dirty || store.mode !== 'bitmap'"
      v-tooltip="'裁切画板到内容'"
      @click="emit('crop')"
    >
      <img :src="iconCrop" class="icon-sm" draggable="false" />
    </button>

    <div class="topbar-spacer"></div>

    <!-- 右：撤销/重做、缩放、保存 -->
    <div class="topbar-right">
      <button class="icon-btn" :disabled="!store.canUndo" v-tooltip="'撤销'" @click="emit('undo')">
        <img :src="iconUndo" class="icon-sm" draggable="false" />
      </button>
      <button class="icon-btn" :disabled="!store.canRedo" v-tooltip="'重做'" @click="emit('redo')">
        <img :src="iconRedo" class="icon-sm" draggable="false" />
      </button>

      <div class="zoom-group">
        <button class="icon-btn" v-tooltip="'缩小'" @click="onZoomOut">
          <img :src="iconZoomOut" class="icon-sm" draggable="false" />
        </button>
        <button class="zoom-label" title="重置缩放" @click="store.resetView()">
          {{ Math.round(store.zoom * 100) }}%
        </button>
        <button class="icon-btn" v-tooltip="'放大'" @click="onZoomIn">
          <img :src="iconZoomIn" class="icon-sm" draggable="false" />
        </button>
      </div>

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
  padding: 0 10px;
  gap: 10px;
  background: var(--bg-base);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  user-select: none;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.topbar-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
}

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
  transition: background 0.15s;
}
.icon-btn:hover:not(:disabled) {
  background: var(--bg-hover);
}
.icon-btn:disabled {
  opacity: 0.35;
  cursor: default;
}

.icon-sm {
  width: 18px;
  height: 18px;
  pointer-events: none;
}

/* 矢量|位图 分段切换 */
.mode-switch {
  display: flex;
  background: var(--bg-panel);
  border-radius: 6px;
  padding: 2px;
  gap: 2px;
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
}
.mode-btn:hover:not(:disabled):not(.mode-btn-active) {
  color: var(--text-secondary);
}
.mode-btn-active {
  background: var(--bg-active);
  color: var(--text);
}
.mode-btn:disabled {
  opacity: 0.45;
  cursor: default;
}

.size-inputs {
  display: flex;
  align-items: center;
  gap: 4px;
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

.topbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.zoom-group {
  display: flex;
  align-items: center;
  gap: 2px;
  margin: 0 6px;
}

.zoom-label {
  min-width: 44px;
  height: 26px;
  font-size: 12px;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s;
}
.zoom-label:hover {
  background: var(--bg-hover);
}

.save-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 30px;
  padding: 0 14px;
  margin-left: 6px;
  font-size: 12px;
  font-weight: 600;
  color: #16201a;
  background: var(--accent);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s, opacity 0.15s;
}
.save-btn:hover:not(:disabled) {
  background: var(--accent-hover);
}
.save-btn:disabled {
  opacity: 0.45;
  cursor: default;
}
</style>
