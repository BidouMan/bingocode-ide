<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useMapStore } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import { useResourceStore } from '../../stores/resource'
import CustomSelect from '../common/CustomSelect.vue'
import ImageLayerTools from './ImageLayerTools.vue'
import DrawingLayerTools from './DrawingLayerTools.vue'
import CollisionLayerTools from './CollisionLayerTools.vue'
import iconGrid from '../../assets/icons/显示网格.svg'
import iconSnapGrid from '../../assets/icons/吸附锚点.svg'

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
}>()

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()
const resourceStore = useResourceStore()

const isImageLayer = computed(() => mapStore.activeMode === 'image')
const isCollisionLayer = computed(() => mapStore.activeMode === 'collision')

// 碰撞层：当前碰撞体的物理属性与禁用开关
const activeCollisionPolygon = computed(() => mapStore.activeCollisionPolygon)
// 用户自定义类型：从当前碰撞层已使用过的类型中收集，选择自定义后可复用
const customPolygonTypes = computed(() => {
  const used = new Set<string>()
  const selfType = activeCollisionPolygon.value?.collisionType
  for (const poly of mapStore.activeCollisionPolygons) {
    const t = poly.collisionType
    if (t && t !== '墙体' && t !== '跳板' && t !== '自定义' && t !== selfType) used.add(t)
  }
  return [...used]
})
const polygonTypeOptions = computed(() => [
  { label: '墙体', value: '墙体' },
  { label: '跳板', value: '跳板' },
  ...customPolygonTypes.value.map(t => ({ label: t, value: t })),
  { label: '自定义', value: '自定义' },
])
const polygonTypeValue = computed(() => activeCollisionPolygon.value?.collisionType || '墙体')
function onPolygonTypeChange(val: string) {
  const poly = activeCollisionPolygon.value
  if (poly) mapStore.setCollisionPolygonType(poly.id, val)
}
// 自定义类型：类型不是内置的墙体/跳板时视为自定义，显示名称输入框
const isCustomPolygonType = computed(() => {
  const t = activeCollisionPolygon.value?.collisionType
  return !!t && t !== '墙体' && t !== '跳板'
})
const customTypeText = computed(() => {
  const t = activeCollisionPolygon.value?.collisionType ?? ''
  return t === '自定义' ? '' : t
})
function onCustomTypeInput(e: Event) {
  const poly = activeCollisionPolygon.value
  if (!poly) return
  const raw = (e.target as HTMLInputElement).value
  // 输入过程中保留原始值（避免中文输入法组字被打断），空值回退到「自定义」
  mapStore.setCollisionPolygonType(poly.id, raw.trim() ? raw : '自定义')
}
function onCustomTypeBlur(e: Event) {
  const poly = activeCollisionPolygon.value
  if (!poly) return
  const name = (e.target as HTMLInputElement).value.trim()
  mapStore.setCollisionPolygonType(poly.id, name || '自定义')
}
function onPolygonDisabledChange(e: Event) {
  const poly = activeCollisionPolygon.value
  if (poly) mapStore.setCollisionPolygonDisabled(poly.id, (e.target as HTMLInputElement).checked)
}
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
    <!-- 工具跟着当前图层类型切换：图片=图像工具，碰撞=碰撞工具，图块=绘制工具 -->
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
      />
      <CollisionLayerTools v-else-if="isCollisionLayer" :disabled="disabled" />
      <DrawingLayerTools v-else :disabled="disabled" />
    </div>

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

    <!-- 碰撞层：物理属性下拉 + 禁用开关 -->
    <template v-if="isCollisionLayer">
      <div class="toolbar-separator" />
      <div class="toolbar-select-wrapper collision-type-select">
        <CustomSelect
          :model-value="polygonTypeValue"
          :options="polygonTypeOptions"
          :disabled="disabled || !activeCollisionPolygon"
          @update:model-value="onPolygonTypeChange"
        />
      </div>
      <input
        v-if="isCustomPolygonType"
        class="toolbar-type-input"
        :value="customTypeText"
        :disabled="disabled || !activeCollisionPolygon"
        placeholder="类型名称"
        @input="onCustomTypeInput"
        @blur="onCustomTypeBlur"
      />
      <label class="toolbar-checkbox" :class="{ 'toolbar-checkbox-disabled': !activeCollisionPolygon }">
        <input
          type="checkbox"
          :checked="activeCollisionPolygon?.disabled === true"
          :disabled="disabled || !activeCollisionPolygon"
          @change="onPolygonDisabledChange"
        />
        <span class="toolbar-checkbox-text">禁用</span>
      </label>
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

/* 碰撞层物理属性下拉：比地图选择更紧凑 */
.collision-type-select {
  width: 100px;
}

/* 自定义类型名称输入框：紧跟在类型下拉右侧 */
.toolbar-type-input {
  width: 84px;
  height: 24px;
  flex-shrink: 0;
  background: rgb(40, 43, 52);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: white;
  padding: 0 6px;
  font-size: 12px;
  outline: none;
  box-sizing: border-box;
  transition: background 0.15s, border-color 0.15s;
}

.toolbar-type-input:hover {
  background: var(--bg-panel);
  border-color: rgb(65, 69, 82);
}

.toolbar-type-input:focus {
  background: var(--border-light);
  border-color: rgb(65, 69, 82);
  color: white;
}

.toolbar-type-input::placeholder {
  color: #6b7076;
}

.toolbar-type-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toolbar-checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  margin-left: 8px;
  cursor: pointer;
  user-select: none;
}

.toolbar-checkbox input[type="checkbox"] {
  width: 15px;
  height: 15px;
  accent-color: #528bff;
  cursor: pointer;
  margin: 0;
}

.toolbar-checkbox-text {
  color: #9ca0a4;
  font-size: 12px;
}

.toolbar-checkbox-disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
