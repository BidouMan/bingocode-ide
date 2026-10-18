<script setup lang="ts">
import { ask } from '@tauri-apps/plugin-dialog'
import { usePaintStore } from '../../stores/paint'

import iconAdd from '../../assets/icons/add-one.svg'
import iconCopy from '../../assets/icons/copy.svg'
import iconDelete from '../../assets/icons/icon--delete.svg'

const store = usePaintStore()

const emit = defineEmits<{
  add: []
  duplicate: []
  remove: [index: number]
}>()

async function onRemove() {
  if (store.frames.length <= 1) return
  const index = store.activeFrameIndex
  const ok = await ask(`删除第 ${index + 1} 帧？删除后无法撤销。`, {
    title: '角色绘制',
    kind: 'warning',
  })
  if (ok) emit('remove', index)
}
</script>

<template>
  <div class="frame-strip">
    <div class="frame-list">
      <button
        v-for="(f, i) in store.frames"
        :key="f.id"
        class="frame-card"
        :class="{ 'frame-card-active': i === store.activeFrameIndex }"
        :title="`第 ${i + 1} 帧`"
        @click="store.selectFrame(i)"
      >
        <img v-if="f.thumb" :src="f.thumb" class="frame-thumb" draggable="false" />
        <div v-else class="frame-thumb frame-thumb-empty"></div>
        <span class="frame-label">{{ i + 1 }}</span>
      </button>
    </div>

    <div class="frame-actions">
      <button class="frame-action-btn" v-tooltip="'新建空白帧'" @click="emit('add')">
        <img :src="iconAdd" draggable="false" />
      </button>
      <button class="frame-action-btn" v-tooltip="'复制当前帧'" @click="emit('duplicate')">
        <img :src="iconCopy" draggable="false" />
      </button>
      <button
        class="frame-action-btn"
        :disabled="store.frames.length <= 1"
        v-tooltip="'删除当前帧'"
        @click="onRemove"
      >
        <img :src="iconDelete" draggable="false" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.frame-strip {
  display: flex;
  align-items: center;
  height: 80px;
  padding: 0 10px;
  gap: 10px;
  background: var(--bg-base);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
  user-select: none;
}

.frame-list {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
  overflow-x: auto;
  overflow-y: hidden;
  height: 100%;
  padding: 8px 2px;
}

.frame-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  height: 60px;
  min-width: 68px;
  padding: 4px 6px;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  flex-shrink: 0;
}
.frame-card:hover {
  background: var(--bg-hover);
}
.frame-card-active {
  border-color: var(--accent);
  background: var(--bg-hover);
}

.frame-thumb {
  height: 36px;
  max-width: 60px;
  object-fit: contain;
  background: repeating-conic-gradient(#ccc 0% 25%, #fff 0% 50%) 50% / 8px 8px;
  border-radius: 3px;
}
.frame-thumb-empty {
  width: 48px;
  background: repeating-conic-gradient(#ccc 0% 25%, #fff 0% 50%) 50% / 8px 8px;
}

.frame-label {
  font-size: 10px;
  color: var(--text-secondary);
  line-height: 1;
}
.frame-card-active .frame-label {
  color: var(--accent);
}

.frame-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.frame-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  padding: 0;
  transition: background 0.15s;
}
.frame-action-btn:hover:not(:disabled) {
  background: var(--bg-hover);
}
.frame-action-btn:disabled {
  opacity: 0.35;
  cursor: default;
}
.frame-action-btn img {
  width: 18px;
  height: 18px;
  pointer-events: none;
}
</style>
