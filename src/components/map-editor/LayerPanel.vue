<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useMapStore } from '../../stores/map'

const mapStore = useMapStore()
const editingLayerIndex = ref<number | null>(null)
const editingName = ref('')

function startRename(index: number) {
  editingLayerIndex.value = index
  editingName.value = mapStore.mapData.layers[index].name
  nextTick(() => {
    const input = document.querySelector('.layer-rename-input') as HTMLInputElement
    if (input) { input.focus(); input.select() }
  })
}

function confirmRename() {
  if (editingLayerIndex.value !== null && editingName.value.trim()) {
    mapStore.renameLayer(editingLayerIndex.value, editingName.value.trim())
  }
  editingLayerIndex.value = null
}

function cancelRename() {
  editingLayerIndex.value = null
}
</script>

<template>
  <div class="layer-panel">
    <div class="layer-header">图层</div>

    <div class="layer-toolbar">
      <button class="layer-tool-btn" title="新建图像图层" @click="mapStore.addLayer('图像图层', 'image')">
        <img src="../../assets/icons/图片库.svg" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" title="新建绘制图层" @click="mapStore.addLayer('绘制图层', 'drawing')">
        <img src="../../assets/icons/btn_preview_add.svg" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" title="删除图层" @click="mapStore.removeLayer(mapStore.activeLayerIndex)">
        <img src="../../assets/icons/选中删除.svg" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" title="上移图层" @click="mapStore.moveLayerUp(mapStore.activeLayerIndex)">
        <img src="../../assets/icons/上移图层.svg" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" title="下移图层" @click="mapStore.moveLayerDown(mapStore.activeLayerIndex)">
        <img src="../../assets/icons/下移图层.svg" class="layer-tool-icon" />
      </button>
    </div>

    <div class="layer-list">
      <div
        v-for="(layer, index) in [...mapStore.mapData.layers].reverse()"
        :key="layer.id"
        class="layer-item"
        :class="{ 'layer-item-active': mapStore.activeLayerIndex === mapStore.mapData.layers.length - 1 - index }"
        @click="mapStore.setActiveLayer(mapStore.mapData.layers.length - 1 - index)"
      >
        <button
          class="layer-vis-btn"
          :title="layer.visible ? '隐藏' : '显示'"
          @click.stop="mapStore.toggleLayerVisibility(mapStore.mapData.layers.length - 1 - index)"
        >
          <img :src="`../../assets/icons/${layer.visible ? 'icon_show.svg' : 'icon_hide.svg'}`" class="vis-icon" />
        </button>
        <template v-if="editingLayerIndex === mapStore.mapData.layers.length - 1 - index">
          <input
            class="layer-rename-input"
            v-model="editingName"
            @blur="confirmRename"
            @keydown.enter.prevent="confirmRename"
            @keydown.escape="cancelRename"
            @click.stop
          />
        </template>
        <template v-else>
          <span class="layer-name" @dblclick.stop="startRename(mapStore.mapData.layers.length - 1 - index)">
            {{ layer.name }}
          </span>
        </template>
      </div>
    </div>

    <div class="layer-mode-bar">
      <span class="layer-mode-text">
        {{ mapStore.activeLayer?.type === 'image' ? '图像' : '绘制' }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.layer-panel {
  display: flex;
  flex-direction: column;
}

.layer-header {
  text-align: center;
  color: rgb(156, 160, 164);
  font-size: 12px;
  padding: 8px 0;
  border-top: 1px solid rgb(55, 59, 68);
}

.layer-toolbar {
  display: flex;
  align-items: center;
  height: 30px;
  padding: 0 4px;
  gap: 2px;
}

.layer-tool-btn {
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

.layer-tool-btn:hover {
  background: rgb(61, 64, 72);
}

.layer-tool-icon {
  width: 20px;
  height: 20px;
}

.layer-list {
  flex: 1;
  overflow-y: auto;
}

.layer-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  cursor: pointer;
  transition: background 0.1s;
}

.layer-item:hover {
  background: rgb(61, 64, 72);
}

.layer-item-active {
  background: #3D6BE5;
  color: white;
}

.layer-vis-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background: transparent;
  border: none;
  cursor: pointer;
  border-radius: 2px;
  flex-shrink: 0;
}

.layer-vis-btn:hover {
  background: rgb(61, 64, 72);
}

.vis-icon {
  width: 14px;
  height: 14px;
}

.layer-name {
  font-size: 12px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.layer-rename-input {
  flex: 1;
  height: 18px;
  background: rgb(40, 43, 52);
  border: 1px solid rgb(91, 199, 114);
  border-radius: 2px;
  color: white;
  font-size: 12px;
  padding: 0 4px;
  outline: none;
}

.layer-mode-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 30px;
}

.layer-mode-text {
  font-size: 12px;
  color: rgb(156, 160, 164);
}
</style>
