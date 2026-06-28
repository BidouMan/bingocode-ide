<script setup lang="ts">
import { useMapStore } from '../../stores/map'
import CollisionEditor from './CollisionEditor.vue'

const emit = defineEmits<{
  'open-library': []
  'upload-resource': []
  'delete-resource': [index: number]
  'clear-resources': []
  'select-tile': [resourceIndex: number, tileIndex: number]
}>()

const mapStore = useMapStore()

function getTileCount(resource: any) {
  if (!resource.tileWidth || !resource.tileHeight) return 0
  return 32
}
</script>

<template>
  <div class="resource-list-panel">
    <div class="resource-toolbar">
      <button class="res-tool-btn" title="打开资源库" @click="emit('open-library')">
        <img src="../../assets/icons/图片库.svg" class="res-tool-icon" />
      </button>
      <button class="res-tool-btn" title="上传本地资源" @click="emit('upload-resource')">
        <img src="../../assets/icons/上传本地图片资源.svg" class="res-tool-icon" />
      </button>
      <button class="res-tool-btn" title="选中删除" @click="emit('delete-resource', mapStore.selectedResourceIndex)">
        <img src="../../assets/icons/选中删除.svg" class="res-tool-icon" />
      </button>
      <button class="res-tool-btn" title="重置" @click="emit('clear-resources')">
        <img src="../../assets/icons/重置.svg" class="res-tool-icon" />
      </button>
    </div>

    <div class="resource-list">
      <div
        v-for="(resource, rIdx) in mapStore.mapResources"
        :key="rIdx"
        class="resource-group"
      >
        <div class="resource-name">{{ resource.name }}</div>
        <div class="tile-grid">
          <div
            v-for="tIdx in getTileCount(resource)"
            :key="tIdx"
            class="tile-cell"
            :class="{
              'tile-selected': mapStore.selectedResourceIndex === rIdx && mapStore.selectedTileIndex === tIdx
            }"
            @click="emit('select-tile', rIdx, tIdx)"
          />
        </div>
      </div>
      <div v-if="mapStore.mapResources.length === 0" class="resource-empty">
        暂无资源
      </div>
    </div>

    <CollisionEditor />

    <div class="res-info-bar">
      <span v-if="mapStore.selectedResourceIndex >= 0">
        {{ mapStore.mapResources[mapStore.selectedResourceIndex]?.name || '' }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.resource-list-panel {
  display: flex;
  flex-direction: column;
  width: 256px;
  min-width: 256px;
  background: rgb(34, 37, 43);
  border-right: 1px solid rgb(12, 12, 12);
}

.resource-toolbar {
  display: flex;
  align-items: center;
  height: 30px;
  padding: 0 4px;
  gap: 2px;
}

.res-tool-btn {
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

.res-tool-btn:hover {
  background: rgb(61, 64, 72);
}

.res-tool-icon {
  width: 20px;
  height: 20px;
}

.resource-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

.resource-group {
  margin-bottom: 8px;
}

.resource-name {
  font-size: 11px;
  color: rgb(156, 160, 164);
  padding: 4px 4px 2px;
}

.tile-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 1px;
  padding: 2px;
}

.tile-cell {
  aspect-ratio: 1;
  background: rgb(50, 53, 62);
  border: 1px solid transparent;
  border-radius: 2px;
  cursor: pointer;
  transition: border-color 0.1s;
}

.tile-cell:hover {
  border-color: rgb(91, 199, 114);
}

.tile-selected {
  border-color: rgb(91, 199, 114) !important;
  background: rgb(60, 65, 75);
}

.resource-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100px;
  color: rgb(80, 80, 80);
  font-size: 12px;
}

.res-info-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  font-size: 12px;
  color: rgb(156, 160, 164);
}
</style>
