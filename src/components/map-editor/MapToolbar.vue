<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useMapStore } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import { useResourceStore } from '../../stores/resource'
import { usePaintStore, ARTBOARD_MAX } from '../../stores/paint'
import CustomSelect from '../common/CustomSelect.vue'
import ImageLayerTools from './ImageLayerTools.vue'
import DrawingLayerTools from './DrawingLayerTools.vue'
import ShapeLayerTools from './ShapeLayerTools.vue'
import iconGrid from '../../assets/icons/显示网格.svg'
import iconSnapGrid from '../../assets/icons/吸附锚点.svg'
import iconMarker from '../../assets/icons/标记.svg'
import iconShow from '../../assets/icons/icon_show.svg'
import iconHide from '../../assets/icons/icon_hide.svg'

const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  'switch-map': [itemId: string]
  'delete-selection': []
  'copy-selection': []
  'paste-selection': []
  'flip-h': []
  'flip-v': []
  'group': []
  'ungroup': []
  'layer-up': []
  'layer-down': []
  'switch-paint-mode': [mode: 'bitmap' | 'vector']
  'create-paint-layer': [tool: 'brush' | 'eraser' | 'fill' | 'line' | 'rect' | 'ellipse' | 'pen' | 'text' | 'reshape' | 'eyedropper']
  'resize-shape': [w: number, h: number]
  /** 图片工具被按下（含重复点击）：上层据此切换右侧分页 */
  'tool-picked': [tool: 'select' | 'reshape' | 'brush' | 'eraser' | 'fill' | 'text' | 'line' | 'rect' | 'ellipse' | 'pen' | 'eyedropper']
}>()

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()
const resourceStore = useResourceStore()
const paintStore = usePaintStore()

// 图片图层里选中了绘制图形（位图浮动选区 / 矢量选框）时才显示尺寸输入
const shapeSelected = computed(() => mapStore.activeMode === 'image' && paintStore.shapeSize !== null)
const shapeW = computed(() => Math.round(paintStore.shapeSize?.w ?? 0))
const shapeH = computed(() => Math.round(paintStore.shapeSize?.h ?? 0))

/** 输入图形宽高：保持中心不变，未编辑的那一轴沿用原始精确值 */
function commitShapeSize(axis: 'w' | 'h', e: Event) {
  const el = e.target as HTMLInputElement
  const s = paintStore.shapeSize
  if (!s) return
  let v = Math.round(Number(el.value))
  if (!Number.isFinite(v)) v = axis === 'w' ? Math.round(s.w) : Math.round(s.h)
  v = Math.min(ARTBOARD_MAX, Math.max(1, v))
  const w = axis === 'w' ? v : Math.max(1, s.w)
  const h = axis === 'h' ? v : Math.max(1, s.h)
  emit('resize-shape', w, h)
  el.value = String(axis === 'w' ? Math.round(paintStore.shapeSize?.w ?? w) : Math.round(paintStore.shapeSize?.h ?? h))
}

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
        @delete-selection="emit('delete-selection')"
        @copy-selection="emit('copy-selection')"
        @paste-selection="emit('paste-selection')"
        @flip-h="emit('flip-h')"
        @flip-v="emit('flip-v')"
        @group="emit('group')"
        @ungroup="emit('ungroup')"
        @layer-up="emit('layer-up')"
        @layer-down="emit('layer-down')"
        @switch-paint-mode="(mode) => emit('switch-paint-mode', mode)"
        @create-layer="(tool) => emit('create-paint-layer', tool)"
        @tool-picked="(tool) => emit('tool-picked', tool)"
      />
      <ShapeLayerTools v-else-if="isShapeLayer" :disabled="disabled" />
      <DrawingLayerTools v-else :disabled="disabled" />
    </div>

    <!-- 标记：紧跟在工具区（自定义形状）右侧 -->
    <button
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapEditorStore.markerPlacing }"
      v-tooltip="mapEditorStore.markerPlacing ? '取消放置标记' : '标记'"
      @click="mapEditorStore.toggleMarkerPlacing()"
    >
      <img :src="iconMarker" class="toolbar-icon" />
    </button>

    <!-- 有被隐藏的标记时才出现：临时把它们弱化显示出来，方便重新选中 -->
    <button
      v-if="hasHiddenMarkers"
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapEditorStore.showHiddenMarkers }"
      v-tooltip="mapEditorStore.showHiddenMarkers ? '重新隐藏这些标记' : '显示隐藏的标记'"
      @click="mapEditorStore.toggleShowHiddenMarkers()"
    >
      <img :src="mapEditorStore.showHiddenMarkers ? iconHide : iconShow" class="toolbar-icon" />
    </button>

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
      :class="{ 'toolbar-btn-active': mapEditorStore.smartSnap }"
      v-tooltip="'智能吸附（像素 / 网格 / 图像边缘与中心）'"
      @click="mapEditorStore.toggleSmartSnap()"
    >
      <img :src="iconSnapGrid" class="toolbar-icon" />
    </button>

    <!-- 选中绘制图形时：显示图形宽高（与角色绘制页顶栏一致） -->
    <template v-if="shapeSelected">
      <div class="toolbar-separator" />
      <div class="shape-size-inputs" title="选中图形尺寸（输入后回车生效）">
        <input
          class="shape-size-input"
          type="number"
          min="1"
          :max="ARTBOARD_MAX"
          :value="shapeW"
          aria-label="图形宽度"
          @change="commitShapeSize('w', $event)"
          @keydown.enter="commitShapeSize('w', $event)"
        />
        <span class="shape-size-x">×</span>
        <input
          class="shape-size-input"
          type="number"
          min="1"
          :max="ARTBOARD_MAX"
          :value="shapeH"
          aria-label="图形高度"
          @change="commitShapeSize('h', $event)"
          @keydown.enter="commitShapeSize('h', $event)"
        />
        <span class="shape-size-unit">px</span>
      </div>
    </template>

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

/* 工具区：内容可横向滚动，滚动条隐藏（滚轮可横向滚动）。
   上下 padding 留给工具按钮外置的选中指示条（overflow 裁剪边界是 padding box，
   没有这段 padding 时 bottom:-4px 的绿条会被裁掉） */
.tool-area {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  flex: 0 1 auto;
  padding: 7px 0;
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
