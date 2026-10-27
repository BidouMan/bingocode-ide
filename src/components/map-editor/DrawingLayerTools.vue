<script setup lang="ts">
import { useMapEditorStore } from '../../stores/mapEditor'
import type { MapTool } from '../../stores/map'
import iconMove from '../../assets/icons/移动工具.svg'
import iconPaint from '../../assets/icons/icon--paint.svg'
import iconErase from '../../assets/icons/清空.svg'

defineProps<{ disabled?: boolean }>()

const mapEditorStore = useMapEditorStore()

const drawingTools: { id: MapTool; icon: string; label: string }[] = [
  { id: 'draw', icon: iconPaint, label: '绘制' },
  { id: 'erase', icon: iconErase, label: '擦除' },
  { id: 'move', icon: iconMove, label: '移动' },
]
</script>

<template>
  <button
    v-for="tool in drawingTools"
    :key="tool.id"
    class="toolbar-btn"
    :class="{ 'toolbar-btn-active': mapEditorStore.currentTool === tool.id }"
    :disabled="disabled"
    v-tooltip="tool.label"
    @click="mapEditorStore.setTool(tool.id)"
  >
    <img :src="tool.icon" class="toolbar-icon" />
  </button>
</template>

<style scoped>
.toolbar-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: default;
  padding: 0;
  flex-shrink: 0;
  transition: background 0.15s;
}

.toolbar-btn:hover { background: var(--bg-hover); }
.toolbar-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.toolbar-btn:disabled:hover { background: transparent; }
.toolbar-btn:active { background: rgb(72, 75, 82); }
.toolbar-btn-active { background: rgb(46, 49, 58); border: 1px solid var(--border-light); }
.toolbar-btn-active:hover { background: var(--border-light); }
.toolbar-icon { width: 20px; height: 20px; flex-shrink: 0; }
</style>
