<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useMapStore } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import { useResourceStore } from '../../stores/resource'
import CustomSelect from '../common/CustomSelect.vue'
import ImageLayerTools from './ImageLayerTools.vue'
import DrawingLayerTools from './DrawingLayerTools.vue'
import iconNewMap from '../../assets/icons/新建地图.svg'
import iconImportMap from '../../assets/icons/导入地图.svg'
import iconExportMap from '../../assets/icons/导出地图.svg'
import iconGrid from '../../assets/icons/显示网格.svg'
import iconSnapGrid from '../../assets/icons/吸附锚点.svg'

const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  'new-map': []
  'import-map': []
  'export-map': []
  'switch-map': [itemId: string]
  'delete-image': []
  'paint': []
}>()

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()
const resourceStore = useResourceStore()

const isImageLayer = computed(() => mapStore.activeLayer?.type === 'image')

const selectedMap = ref('')

const mapOptions = computed(() => {
  return resourceStore.maps.map(m => ({ label: m.name, value: m.id }))
})

// 当外部（如新建/导入）改变 currentMapPath 时，同步下拉框
watch(() => mapStore.currentMapPath, (path) => {
  if (path && resourceStore.maps.find(m => m.id === path)) {
    selectedMap.value = path
  }
}, { immediate: true })

function onMapChange(value: string) {
  // 不要在这里设置 selectedMap —— 让 currentMapPath watcher 来同步
  // 直接在 emit 前设置会导致竞态：async switchToMap 的 await 期间 watcher 会覆盖它
  emit('switch-map', value)
}
</script>

<template>
  <div class="map-toolbar">
    <button class="toolbar-btn" v-tooltip="'新建地图'" @click="emit('new-map')">
      <img :src="iconNewMap" class="toolbar-icon" />
    </button>
    <button class="toolbar-btn" v-tooltip="'导入 .bgm'" @click="emit('import-map')">
      <img :src="iconImportMap" class="toolbar-icon" />
    </button>
    <button class="toolbar-btn" v-tooltip="'导出 .bgm'" @click="emit('export-map')">
      <img :src="iconExportMap" class="toolbar-icon" />
    </button>

    <div class="toolbar-separator" />

    <!-- 图像模式工具 / 绘制模式工具 -->
    <ImageLayerTools
      v-if="isImageLayer"
      :disabled="disabled"
      @delete-image="emit('delete-image')"
      @paint="emit('paint')"
    />
    <DrawingLayerTools v-else :disabled="disabled" />

    <div class="toolbar-separator" />

    <button
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapEditorStore.showGrid }"
      v-tooltip="'显示网格'"
      @click="mapEditorStore.toggleGrid()"
    >
      <img :src="iconGrid" class="toolbar-icon" />
    </button>
    <button
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapEditorStore.snapToGrid }"
      v-tooltip="'吸附网格'"
      @click="mapEditorStore.toggleSnapToGrid()"
    >
      <img :src="iconSnapGrid" class="toolbar-icon" />
    </button>

    <div class="toolbar-spacer" />

    <div class="toolbar-select-wrapper">
      <CustomSelect :model-value="selectedMap" :options="mapOptions" @update:model-value="onMapChange" />
    </div>
  </div>
</template>

<style scoped>
.map-toolbar {
  display: flex;
  align-items: center;
  height: 30px;
  padding: 0 8px;
  gap: 4px;
  background: var(--bg-root);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
  transition: background 0.15s;
}

.toolbar-btn:hover {
  background: var(--bg-hover);
}

.toolbar-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.toolbar-btn:disabled:hover {
  background: transparent;
}

.toolbar-btn:active {
  background: rgb(72, 75, 82);
}

.toolbar-btn-active {
  background: rgb(46, 49, 58);
  border: 1px solid var(--border-light);
}

.toolbar-btn-active:hover {
  background: var(--border-light);
}

.toolbar-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.toolbar-separator {
  width: 1px;
  height: 20px;
  background: var(--border-light);
  margin: 0 2px;
}

.toolbar-spacer {
  flex: 1;
}

.toolbar-select-wrapper {
  width: 120px;
  flex-shrink: 0;
}
</style>
