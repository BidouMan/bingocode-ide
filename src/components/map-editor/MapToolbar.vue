<script setup lang="ts">
import { useMapStore } from '../../stores/map'
import type { MapTool } from '../../stores/map'

const emit = defineEmits<{
  'new-map': []
  'import-map': []
  'export-map': []
}>()

const mapStore = useMapStore()

const tools: { id: MapTool; icon: string; label: string }[] = [
  { id: 'move', icon: '移动工具.svg', label: '移动' },
  { id: 'select', icon: '选取工具.svg', label: '选取' },
  { id: 'draw', icon: 'icon--paint.svg', label: '绘制' },
  { id: 'erase', icon: '清空.svg', label: '擦除' },
]
</script>

<template>
  <div class="map-toolbar">
    <button class="toolbar-btn" title="新建地图" @click="emit('new-map')">
      <img src="../../assets/icons/新建地图.svg" class="toolbar-icon" />
    </button>
    <button class="toolbar-btn" title="导入 .bgm" @click="emit('import-map')">
      <img src="../../assets/icons/导入地图.svg" class="toolbar-icon" />
    </button>
    <button class="toolbar-btn" title="导出 .bgm" @click="emit('export-map')">
      <img src="../../assets/icons/导出地图.svg" class="toolbar-icon" />
    </button>

    <div class="toolbar-separator" />

    <button
      v-for="tool in tools"
      :key="tool.id"
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapStore.currentTool === tool.id }"
      :title="tool.label"
      @click="mapStore.setTool(tool.id)"
    >
      <img :src="`../../assets/icons/${tool.icon}`" class="toolbar-icon" />
    </button>

    <div class="toolbar-separator" />

    <button
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapStore.showGrid }"
      title="显示网格"
      @click="mapStore.toggleGrid()"
    >
      <img src="../../assets/icons/显示网格.svg" class="toolbar-icon" />
    </button>

    <div class="toolbar-spacer" />

    <select class="map-selector">
      <option>未命名地图</option>
    </select>
  </div>
</template>

<style scoped>
.map-toolbar {
  display: flex;
  align-items: center;
  height: 30px;
  padding: 0 4px;
  gap: 2px;
  background: rgb(34, 37, 43);
  border-bottom: 1px solid rgb(12, 12, 12);
  flex-shrink: 0;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  padding: 4px;
  transition: background 0.15s;
}

.toolbar-btn:hover {
  background: rgb(61, 64, 72);
}

.toolbar-btn:active {
  background: rgb(72, 75, 82);
}

.toolbar-btn-active {
  background: rgb(46, 49, 58);
  border: 1px solid rgb(55, 59, 68);
}

.toolbar-btn-active:hover {
  background: rgb(55, 59, 68);
}

.toolbar-icon {
  width: 20px;
  height: 20px;
}

.toolbar-separator {
  width: 1px;
  height: 20px;
  background: rgb(55, 59, 68);
  margin: 0 2px;
}

.toolbar-spacer {
  flex: 1;
}

.map-selector {
  border: 1px solid rgb(55, 59, 68);
  border-radius: 4px;
  background: rgb(40, 43, 52);
  color: white;
  padding: 3px 8px;
  font-size: 12px;
  min-width: 100px;
  outline: none;
}

.map-selector:hover {
  border: 1px solid rgb(65, 69, 82);
  background: rgb(50, 53, 62);
}
</style>
