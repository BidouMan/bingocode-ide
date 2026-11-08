<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useMapStore } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import { useResourceStore } from '../../stores/resource'
import CustomSelect from '../common/CustomSelect.vue'
import ImageLayerTools from './ImageLayerTools.vue'
import DrawingLayerTools from './DrawingLayerTools.vue'
import ShapeLayerTools from './ShapeLayerTools.vue'
import iconMarker from '../../assets/icons/标记.svg'

const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  'switch-map': [itemId: string]
  /** 图像图层：复制图层 / 镜像 / 进入绘制页 */
  'copy-image-layer': []
  'flip-image-h': []
  'flip-image-v': []
  'edit-image': []
}>()

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()
const resourceStore = useResourceStore()

const isImageLayer = computed(() => mapStore.activeMode === 'image')
const isShapeLayer = computed(() => mapStore.activeMode === 'shape')

// 有被隐藏的标记时出现「显示隐藏标记」按钮；全部恢复后自动关掉临时显示，避免状态残留
const hasHiddenMarkers = computed(() => mapStore.mapData.markers.some(m => m.visible === false))
watch(hasHiddenMarkers, (has) => {
  if (!has) mapEditorStore.showHiddenMarkers = false
})

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

/** 工具区超宽时，鼠标滚轮转横向滚动（小屏也能访问全部工具） */
function onToolAreaWheel(e: WheelEvent) {
  const el = e.currentTarget as HTMLElement
  if (!el || el.scrollWidth <= el.clientWidth) return
  if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return
  el.scrollLeft += e.deltaY
  e.preventDefault()
}
</script>

<template>
  <div class="map-toolbar">
    <!-- 工具跟着当前图层类型切换：图片=图像工具，形状=形状工具，图块=绘制工具 -->
    <div class="tool-area" @wheel="onToolAreaWheel">
      <ImageLayerTools
        v-if="isImageLayer"
        :disabled="disabled"
        @copy-layer="emit('copy-image-layer')"
        @edit-image="emit('edit-image')"
        @flip-h="emit('flip-image-h')"
        @flip-v="emit('flip-image-v')"
      />
      <ShapeLayerTools v-else-if="isShapeLayer" :disabled="disabled" />
      <DrawingLayerTools v-else :disabled="disabled" />
    </div>

    <!-- 标记：紧跟在工具区（自定义形状）右侧 -->
    <button
      class="tool-chip"
      :class="{ active: mapEditorStore.markerPlacing }"
      v-tooltip="mapEditorStore.markerPlacing ? '取消放置标记' : '标记'"
      @click="mapEditorStore.toggleMarkerPlacing()"
    >
      <img :src="iconMarker" class="tool-chip-icon ic-marker" />标记
    </button>

    <!-- 有被隐藏的标记时才出现：临时把它们弱化显示出来，方便重新选中 -->
    <button
      v-if="hasHiddenMarkers"
      class="tool-chip check-chip"
      :class="{ active: mapEditorStore.showHiddenMarkers }"
      v-tooltip="mapEditorStore.showHiddenMarkers ? '重新隐藏这些标记' : '显示隐藏的标记'"
      @click="mapEditorStore.toggleShowHiddenMarkers()"
    >
      <span class="chip-check" :class="{ on: mapEditorStore.showHiddenMarkers }"></span>
      {{ mapEditorStore.showHiddenMarkers ? '恢复隐藏' : '显示隐藏标记' }}
    </button>

    <button
      class="tool-chip check-chip"
      :class="{ active: mapEditorStore.showGrid }"
      v-tooltip="'显示网格'"
      @click="mapEditorStore.toggleGrid()"
    >
      <span class="chip-check" :class="{ on: mapEditorStore.showGrid }"></span>网格
    </button>
    <button
      class="tool-chip check-chip"
      :class="{ active: mapEditorStore.smartSnap }"
      v-tooltip="'智能吸附（像素 / 网格 / 图像边缘与中心）'"
      @click="mapEditorStore.toggleSmartSnap()"
    >
      <span class="chip-check" :class="{ on: mapEditorStore.smartSnap }"></span>吸附
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
  height: 44px;
  padding: 0 10px;
  gap: 6px;
  background: var(--bg-root);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.toolbar-spacer {
  flex: 1;
}

/* 工具区：内容可横向滚动，滚动条隐藏（滚轮可横向滚动） */
.tool-area {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 0 1 auto;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.tool-area::-webkit-scrollbar {
  display: none;
}

.toolbar-select-wrapper {
  width: 120px;
  flex-shrink: 0;
}

/* 选中图形尺寸输入 */
.shape-size-inputs {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.shape-size-input {
  width: 54px;
  height: 26px;
  padding: 0 6px;
  font-size: 12px;
  color: white;
  background: rgb(40, 43, 52);
  border: 1px solid var(--border-light);
  border-radius: 5px;
  outline: none;
  text-align: center;
  box-sizing: border-box;
  /* 隐藏 number 上下箭头，保持紧凑 */
  -moz-appearance: textfield;
  appearance: textfield;
}

.shape-size-input::-webkit-outer-spin-button,
.shape-size-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.shape-size-input:hover {
  background: var(--bg-panel);
  border-color: var(--text-muted);
}

/* 激活（正在输入）时才用强调色描边 */
.shape-size-input:focus {
  background: var(--border-light);
  border-color: var(--accent);
}

.shape-size-x {
  font-size: 12px;
  color: var(--text-muted);
}

.shape-size-unit {
  font-size: 11px;
  color: var(--text-muted);
}
</style>

<style scoped src="./ToolbarChip.css"></style>
