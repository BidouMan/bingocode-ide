<script setup lang="ts">
import { usePaintStore, ARTBOARD_PRESETS } from '../../stores/paint'

import iconClose from '../../assets/icons/关闭_2.svg'
import iconUndo from '../../assets/icons/undo.svg'
import iconRedo from '../../assets/icons/redo.svg'
import iconZoomOut from '../../assets/icons/reduce-one.svg'
import iconZoomIn from '../../assets/icons/add-one.svg'
import iconSave from '../../assets/icons/保存.svg'

const emit = defineEmits<{
  close: []
  save: []
  undo: []
  redo: []
}>()

const store = usePaintStore()

function onZoomIn() {
  store.setZoom(store.zoom * 1.1)
}

function onZoomOut() {
  store.setZoom(store.zoom * 0.9)
}

function onPresetChange(e: Event) {
  const value = (e.target as HTMLSelectElement).value
  const preset = ARTBOARD_PRESETS.find(p => `${p.w}x${p.h}` === value)
  if (preset) {
    store.artboardWidth = preset.w
    store.artboardHeight = preset.h
    store.resetView()
  }
}
</script>

<template>
  <div class="paint-topbar">
    <!-- 左：关闭 + 标题 -->
    <div class="topbar-left">
      <button class="icon-btn" v-tooltip="'关闭'" @click="emit('close')">
        <img :src="iconClose" class="icon-sm" draggable="false" />
      </button>
      <span class="topbar-title">角色绘制</span>
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

    <!-- 中右：画板尺寸（开画后锁定） -->
    <select
      class="size-select"
      :value="`${store.artboardWidth}x${store.artboardHeight}`"
      :disabled="store.dirty"
      :title="store.dirty ? '开始绘制后不能修改画板尺寸' : '画板尺寸'"
      @change="onPresetChange"
    >
      <option v-for="p in ARTBOARD_PRESETS" :key="p.w" :value="`${p.w}x${p.h}`">{{ p.label }}</option>
    </select>

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
        :title="store.dirty ? '保存为新角色' : '画板为空，先画点什么'"
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

.size-select {
  height: 26px;
  padding: 0 6px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 5px;
  cursor: pointer;
  outline: none;
}
.size-select:hover {
  border-color: var(--text-muted);
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
