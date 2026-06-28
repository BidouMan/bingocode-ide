<script setup lang="ts">
import MapToolbar from './MapToolbar.vue'
import MapCanvas from './MapCanvas.vue'
import ResourceListPanel from './ResourceListPanel.vue'
import PropertyPanel from './PropertyPanel.vue'
import LayerPanel from './LayerPanel.vue'
import { useMapStore } from '../../stores/map'

const mapStore = useMapStore()

function onNewMap() {
  // TODO: Task 10 - map file operations
}

function onImportMap() {
  // TODO: Task 10 - map file operations
}

function onExportMap() {
  // TODO: Task 10 - map file operations
}

function onOpenLibrary() {
  // TODO: Task 8 - map library page
}

function onUploadResource() {
  // TODO: Task 9 - resource import dialog
}
</script>

<template>
  <div class="map-editor-view">
    <MapToolbar
      @new-map="onNewMap"
      @import-map="onImportMap"
      @export-map="onExportMap"
    />
    <div class="map-editor-body">
      <ResourceListPanel
        @open-library="onOpenLibrary"
        @upload-resource="onUploadResource"
      />
      <div class="map-editor-center">
        <MapCanvas class="map-canvas-area" />
        <div class="map-info-bar">
          <span class="info-label">名称: {{ mapStore.mapData.name }}</span>
          <span class="info-label">尺寸: {{ mapStore.mapData.width }} × {{ mapStore.mapData.height }}</span>
          <span class="info-label">瓦片: {{ mapStore.mapData.tileSize }}px</span>
        </div>
      </div>
      <div class="map-editor-right">
        <PropertyPanel />
        <LayerPanel />
      </div>
    </div>
  </div>
</template>

<style scoped>
.map-editor-view {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: rgb(30, 30, 30);
}

.map-editor-body {
  flex: 1;
  min-height: 0;
  display: flex;
}

.map-editor-center {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.map-canvas-area {
  flex: 1;
  min-height: 0;
}

.map-info-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  gap: 20px;
  background: rgb(34, 37, 43);
}

.info-label {
  font-size: 12px;
  color: rgb(156, 160, 164);
  padding: 0 6px;
}

.map-editor-right {
  display: flex;
  flex-direction: column;
  width: 256px;
  min-width: 256px;
}
</style>
