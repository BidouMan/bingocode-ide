<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useMapStore } from '../../stores/map'
import iconShow from '../../assets/icons/icon_show.svg'
import iconHide from '../../assets/icons/icon_hide.svg'
import iconLibrary from '../../assets/icons/图片库.svg'
import iconAdd from '../../assets/icons/btn_preview_add.svg'
import iconDelete from '../../assets/icons/icon--delete.svg'
import iconUp from '../../assets/icons/上移图层.svg'
import iconDown from '../../assets/icons/下移图层.svg'

const props = defineProps<{
  disabled?: boolean
}>()

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
    <div class="layer-tag-name">图层管理</div>

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
          <img :src="layer.visible ? iconShow : iconHide" class="vis-icon" />
        </button>
        <button
          class="layer-lock-btn"
          :class="{ 'layer-locked': layer.locked }"
          :title="layer.locked ? '解锁' : '锁定'"
          @click.stop="mapStore.toggleLayerLock(mapStore.mapData.layers.length - 1 - index)"
        >
          {{ layer.locked ? '🔒' : '🔓' }}
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

    <div class="layer-toolbar">
      <button class="layer-tool-btn" title="新建图像图层" :disabled="disabled" @click="mapStore.addLayer('图像图层', 'image')">
        <img :src="iconLibrary" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" title="新建绘制图层" :disabled="disabled" @click="mapStore.addLayer('绘制图层', 'drawing')">
        <img :src="iconAdd" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" title="删除图层" :disabled="disabled" @click="mapStore.removeLayer(mapStore.activeLayerIndex)">
        <img :src="iconDelete" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" title="上移图层" :disabled="disabled" @click="mapStore.moveLayerUp(mapStore.activeLayerIndex)">
        <img :src="iconUp" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" title="下移图层" :disabled="disabled" @click="mapStore.moveLayerDown(mapStore.activeLayerIndex)">
        <img :src="iconDown" class="layer-tool-icon" />
      </button>
    </div>

    <div class="layer-info-bar">
      <span class="layer-info-text">模式{{ mapStore.activeLayer?.type === 'image' ? '图像' : mapStore.activeLayer?.type === 'drawing' ? '绘制' : '--' }}</span>
    </div>
  </div>
</template>

<style scoped>
.layer-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: rgb(34, 37, 43);
}

.layer-tag-name {
  text-align: center;
  color: #9ca0a4;
  font-size: 12px;
  height: 30px;
  line-height: 30px;
  border-top: 1px solid rgb(45, 45, 45);
  flex-shrink: 0;
}

.layer-toolbar {
  display: flex;
  align-items: center;
  height: 30px;
  padding: 0 8px;
  gap: 6px;
  flex-shrink: 0;
}

.layer-tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  height: 24px;
  background: rgb(40, 43, 52);
  border: none;
  border-radius: 4px;
  cursor: pointer;
  padding: 2px;
  transition: background 0.15s;
}

.layer-tool-btn:hover {
  background: rgb(61, 64, 72);
}

.layer-tool-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.layer-tool-icon {
  height: 20px;
}

.layer-list {
  flex: 1;
  overflow-y: auto;
  margin: 0 8px;
  background: rgb(30, 30, 30);
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
  background: #2c313a;
}

.layer-item-active {
  background: #2c313a;
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

.layer-lock-btn {
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
  font-size: 10px;
  opacity: 0.5;
  transition: opacity 0.15s;
}

.layer-lock-btn:hover {
  opacity: 1;
  background: rgb(61, 64, 72);
}

.layer-locked {
  opacity: 1;
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
  height: 24px;
  background: rgb(40, 43, 52);
  border: 1px solid rgb(91, 199, 114);
  border-radius: 4px;
  color: white;
  font-size: 12px;
  padding: 0 6px;
  outline: none;
  box-sizing: border-box;
}

.layer-info-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  background: rgb(34, 37, 43);
  flex-shrink: 0;
}

.layer-info-text {
  font-size: 12px;
  color: rgb(156, 160, 164);
}
</style>
