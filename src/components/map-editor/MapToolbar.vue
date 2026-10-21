<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useMapStore } from '../../stores/map'
import { useResourceStore } from '../../stores/resource'
import type { MapTool } from '../../stores/map'
import CustomSelect from '../common/CustomSelect.vue'
import iconMove from '../../assets/icons/移动工具.svg'
import iconSelect from '../../assets/icons/选取工具.svg'
import iconPaint from '../../assets/icons/icon--paint.svg'
import iconErase from '../../assets/icons/清空.svg'
import iconNewMap from '../../assets/icons/新建地图.svg'
import iconImportMap from '../../assets/icons/导入地图.svg'
import iconExportMap from '../../assets/icons/导出地图.svg'
import iconGrid from '../../assets/icons/显示网格.svg'
import iconSnapGrid from '../../assets/icons/吸附锚点.svg'
import iconDelete from '../../assets/icons/选中删除.svg'
import iconCollisionRect from '../../assets/icons/矩形_rectangle.svg'
import iconCollisionPolygon from '../../assets/icons/折线.svg'
import iconCollisionVertex from '../../assets/icons/移动锚点.svg'
import iconCollisionClear from '../../assets/icons/重置.svg'
import iconCollisionShow from '../../assets/icons/hitbox.svg'

const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  'new-map': []
  'import-map': []
  'export-map': []
  'switch-map': [itemId: string]
  'delete-image': []
}>()

const mapStore = useMapStore()
const resourceStore = useResourceStore()

const isImageLayer = computed(() => mapStore.activeLayer?.type === 'image')

const hasSelectedImage = computed(() => !!mapStore.selectedImage)
const hasCollisionShape = computed(() => (mapStore.selectedImage?.collisionShape?.points?.length ?? 0) >= 3)

function toggleCollisionTool(tool: 'rect' | 'polygon' | 'vertex') {
  if (!hasSelectedImage.value) return
  mapStore.setImageCollisionTool(mapStore.imageCollisionTool === tool ? 'none' : tool)
}

// 切回普通工具时退出碰撞编辑，避免指针事件仍被碰撞工具截获
function onImageToolClick(tool: MapTool) {
  mapStore.setImageCollisionTool('none')
  mapStore.setTool(tool)
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

// 绘制模式专属工具（绘制 → 擦除 → 移动）
const drawingTools: { id: MapTool; icon: string; label: string }[] = [
  { id: 'draw', icon: iconPaint, label: '绘制' },
  { id: 'erase', icon: iconErase, label: '擦除' },
  { id: 'move', icon: iconMove, label: '移动' },
]

// 图像模式工具（选取 + 删除）
const imageTools: { id: MapTool; icon: string; label: string }[] = [
  { id: 'select', icon: iconSelect, label: '选取' },
]
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

    <!-- 图像模式：选取 + 删除 -->
    <template v-if="isImageLayer">
      <button
        v-for="tool in imageTools"
        :key="tool.id"
        class="toolbar-btn"
        :class="{ 'toolbar-btn-active': mapStore.currentTool === tool.id }"
        :disabled="disabled"
        v-tooltip="tool.label"
        @click="onImageToolClick(tool.id)"
      >
        <img :src="tool.icon" class="toolbar-icon" />
      </button>
      <button
        class="toolbar-btn"
        v-tooltip="'删除选中图像'"
        :disabled="disabled"
        @click="emit('delete-image')"
      >
        <img :src="iconDelete" class="toolbar-icon" />
      </button>

      <div class="toolbar-separator" />

      <!-- 图像碰撞编辑：先选中图片再使用 -->
      <button
        class="toolbar-btn"
        :class="{ 'toolbar-btn-active': mapStore.imageCollisionTool === 'rect' }"
        :disabled="disabled || !hasSelectedImage"
        v-tooltip="hasSelectedImage ? '矩形碰撞：在图片上拖动绘制' : '先在画布上选中图像实例'"
        @click="toggleCollisionTool('rect')"
      >
        <img :src="iconCollisionRect" class="toolbar-icon" />
      </button>
      <button
        class="toolbar-btn"
        :class="{ 'toolbar-btn-active': mapStore.imageCollisionTool === 'polygon' }"
        :disabled="disabled || !hasSelectedImage"
        v-tooltip="hasSelectedImage ? '多边形碰撞：逐点点击，点首点/回车闭合' : '先在画布上选中图像实例'"
        @click="toggleCollisionTool('polygon')"
      >
        <img :src="iconCollisionPolygon" class="toolbar-icon" />
      </button>
      <button
        class="toolbar-btn"
        :class="{ 'toolbar-btn-active': mapStore.imageCollisionTool === 'vertex' }"
        :disabled="disabled || !hasSelectedImage"
        v-tooltip="hasSelectedImage ? '编辑锚点：拖动顶点，点边插点，右键/Del 删点' : '先在画布上选中图像实例'"
        @click="toggleCollisionTool('vertex')"
      >
        <img :src="iconCollisionVertex" class="toolbar-icon" />
      </button>
      <button
        class="toolbar-btn"
        :disabled="disabled || !hasCollisionShape"
        v-tooltip="'清除碰撞'"
        @click="mapStore.clearImageCollision()"
      >
        <img :src="iconCollisionClear" class="toolbar-icon" />
      </button>
      <button
        class="toolbar-btn"
        :class="{ 'toolbar-btn-active': mapStore.showCollision }"
        :disabled="disabled"
        v-tooltip="'显示所有图像碰撞'"
        @click="mapStore.toggleShowCollision()"
      >
        <img :src="iconCollisionShow" class="toolbar-icon" />
      </button>
    </template>
    <!-- 绘制模式：选取、绘制、擦除、移动 -->
    <template v-else>
      <button
        v-for="tool in drawingTools"
        :key="tool.id"
        class="toolbar-btn"
        :class="{ 'toolbar-btn-active': mapStore.currentTool === tool.id }"
        :disabled="disabled"
        v-tooltip="tool.label"
        @click="mapStore.setTool(tool.id)"
      >
        <img :src="tool.icon" class="toolbar-icon" />
      </button>
    </template>

    <div class="toolbar-separator" />

    <button
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapStore.showGrid }"
      v-tooltip="'显示网格'"
      @click="mapStore.toggleGrid()"
    >
      <img :src="iconGrid" class="toolbar-icon" />
    </button>
    <button
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapStore.snapToGrid }"
      v-tooltip="'吸附网格'"
      @click="mapStore.toggleSnapToGrid()"
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
