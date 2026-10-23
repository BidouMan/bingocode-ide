<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { useMapStore } from '../../stores/map'
import { useProjectStore } from '../../stores/project'
import iconShow from '../../assets/icons/icon_show.svg'
import iconHide from '../../assets/icons/icon_hide.svg'
import iconAdd from '../../assets/icons/新建图块图层.svg'
import iconDelete from '../../assets/icons/icon--delete.svg'
import iconUp from '../../assets/icons/上移图层.svg'
import iconDown from '../../assets/icons/下移图层.svg'
import iconPaint from '../../assets/icons/icon--paint.svg'
import iconLibrary from '../../assets/icons/图片库.svg'
import iconUpload from '../../assets/icons/上传本地图片资源.svg'
import iconImageType from '../../assets/icons/图像.svg'
import iconTileType from '../../assets/icons/图块.svg'
import iconUnlock from '../../assets/icons/解锁.svg'
import iconLock from '../../assets/icons/锁定.svg'

const props = defineProps<{
  disabled?: boolean
  /** 图块图层缩略图提供者（只渲染该图层自身，避免串层） */
  getLayerThumbnail?: (layerId: number) => string | null | Promise<string | null>
}>()

const emit = defineEmits<{
  paint: []
  'open-library': []
  'upload-image': []
}>()

const mapStore = useMapStore()
const projectStore = useProjectStore()

const editingLayerIndex = ref<number | null>(null)
const editingName = ref('')
const listRef = ref<HTMLDivElement>()

// 缩略图渲染：跟随场景渲染模式（图块/位图场景像素渲染，全矢量场景平滑）
const imageRenderingStyle = computed(() => {
  return mapStore.sceneRenderMode === 'pixelated' ? 'pixelated' : 'auto'
})

// 显示顺序：数组末尾是最上层，列表顶部也应是最上层
const displayLayers = computed(() => {
  return mapStore.mapData.layers
    .map((layer, index) => ({ layer, index }))
    .reverse()
})

// ====== 图片图层缩略图 ======
const thumbUrls = ref<Map<number, string>>(new Map())
const urlCache = new Map<string, string>()

async function resolveThumbUrl(path: string): Promise<string> {
  const cached = urlCache.get(path)
  if (cached !== undefined) return cached
  let url: string
  if (path.startsWith('/maps/')) {
    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')
      url = await invoke<string>('read_image_as_data_url', { path: `${engineDir}${path}` })
    } catch {
      url = ''
    }
  } else if (path.startsWith('assets/')) {
    const fullPath = `${projectStore.root}/${path}`
    try {
      url = await invoke<string>('read_image_as_data_url', { path: fullPath })
    } catch {
      url = convertFileSrc(fullPath)
    }
  } else {
    try {
      url = await invoke<string>('read_image_as_data_url', { path })
    } catch {
      url = convertFileSrc(path)
    }
  }
  urlCache.set(path, url)
  return url
}

async function refreshThumbs() {
  // 图片可能被内联绘制原地覆盖，清空 URL 缓存以拿到最新内容
  urlCache.clear()
  const next = new Map<number, string>()
  for (const layer of mapStore.mapData.layers) {
    if (layer.type === 'image' && layer.image?.imagePath) {
      next.set(layer.id, await resolveThumbUrl(layer.image.imagePath))
    } else if (layer.type === 'drawing' && props.getLayerThumbnail) {
      // 图块图层：只取该图层自身渲染结果；未绘制图块时为空（不显示占位图）
      const url = await props.getLayerThumbnail(layer.id)
      if (url) next.set(layer.id, url)
    }
  }
  thumbUrls.value = next
}

/** 只刷新当前图块图层的缩略图（绘制时高频调用，其他图层内容没变无需重算） */
async function refreshTileThumbs() {
  if (!props.getLayerThumbnail) return
  const active = mapStore.activeLayer
  if (!active || active.type !== 'drawing') return
  const url = await props.getLayerThumbnail(active.id)
  const next = new Map(thumbUrls.value)
  if (url) next.set(active.id, url)
  else next.delete(active.id)
  thumbUrls.value = next
}

watch(() => mapStore.imageRevision, refreshThumbs)
// 地图载入后 Pixi 渲染有延迟，稍后再补一次图块缩略图
let loadThumbTimer: ReturnType<typeof setTimeout> | null = null
watch(() => mapStore.mapLoadCount, () => {
  refreshThumbs()
  if (loadThumbTimer) clearTimeout(loadThumbTimer)
  loadThumbTimer = setTimeout(() => {
    loadThumbTimer = null
    refreshThumbs()
  }, 300)
})
// 图层增删后补齐缩略图
watch(() => mapStore.mapData.layers.length, () => refreshThumbs())
// 图块绘制后等 Pixi 渲染完成再取该图层缩略图
let tileThumbTimer: ReturnType<typeof setTimeout> | null = null
watch(() => mapStore.tileRevision, () => {
  if (tileThumbTimer) clearTimeout(tileThumbTimer)
  tileThumbTimer = setTimeout(() => {
    tileThumbTimer = null
    refreshTileThumbs()
  }, 120)
})
onMounted(refreshThumbs)
onBeforeUnmount(() => {
  if (tileThumbTimer) clearTimeout(tileThumbTimer)
  if (loadThumbTimer) clearTimeout(loadThumbTimer)
})

// ====== 选中 / 重命名 ======
function selectLayer(index: number) {
  if (suppressClick) {
    suppressClick = false
    return
  }
  mapStore.setActiveLayer(index)
}

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

// ====== 拖拽排序 ======
const draggingIndex = ref(-1)
const dropDisplayIndex = ref(-1)
const dragging = ref(false)
let dragStartY = 0
let suppressClick = false

function onRowPointerDown(e: MouseEvent, modelIndex: number) {
  if (e.button !== 0) return
  if ((e.target as HTMLElement).closest('button,input')) return
  if (mapStore.mapData.layers.length < 2) return
  dragStartY = e.clientY
  dragging.value = false
  draggingIndex.value = modelIndex
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
}

function onDragMove(e: MouseEvent) {
  if (!dragging.value && Math.abs(e.clientY - dragStartY) < 4) return
  dragging.value = true
  const rows = listRef.value?.querySelectorAll<HTMLElement>('.layer-item')
  if (!rows || rows.length === 0) return
  let insert = rows.length
  for (let i = 0; i < rows.length; i++) {
    const rect = rows[i].getBoundingClientRect()
    if (e.clientY < rect.top + rect.height / 2) {
      insert = i
      break
    }
  }
  dropDisplayIndex.value = insert
}

function onDragEnd() {
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  suppressClick = dragging.value
  if (suppressClick) {
    // 拖拽结束时 click 可能落在容器上，延迟复位避免吞掉下一次正常点击
    setTimeout(() => { suppressClick = false }, 0)
  }
  if (dragging.value && dropDisplayIndex.value >= 0 && draggingIndex.value >= 0) {
    applyReorder(draggingIndex.value, dropDisplayIndex.value)
  }
  draggingIndex.value = -1
  dropDisplayIndex.value = -1
  dragging.value = false
}

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
})

// displayIndex 是"插入到显示列表的第几个位置"（0 表示最上层之上）
function applyReorder(from: number, insertDisplayIndex: number) {
  const count = mapStore.mapData.layers.length
  const displayOrder = Array.from({ length: count }, (_, d) => count - 1 - d)
  const fromDisplay = displayOrder.indexOf(from)
  const rest = displayOrder.filter(i => i !== from)
  const insertAt = insertDisplayIndex > fromDisplay ? insertDisplayIndex - 1 : insertDisplayIndex
  rest.splice(Math.max(0, Math.min(insertAt, rest.length)), 0, from)
  // rest 是最终显示顺序（顶→底），换算成模型索引（底→顶）
  const to = rest.length - 1 - rest.indexOf(from)
  if (to !== from) mapStore.moveLayerTo(from, to)
}
</script>

<template>
  <div class="layer-panel">
    <div class="layer-toolbar">
      <!-- 工具栏固定不变：图像相关入口在图块模式下仍保留，点击后新建图片图层 -->
      <button class="layer-tool-btn" v-tooltip="'绘制图像'" :disabled="disabled" @click="emit('paint')">
        <img :src="iconPaint" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" v-tooltip="'打开内置资源'" :disabled="disabled" @click="emit('open-library')">
        <img :src="iconLibrary" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" v-tooltip="'新建图块图层'" :disabled="disabled" @click="mapStore.addLayer('图块图层')">
        <img :src="iconAdd" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" v-tooltip="'本地上传'" :disabled="disabled" @click="emit('upload-image')">
        <img :src="iconUpload" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" v-tooltip="'删除图层'" :disabled="disabled || mapStore.activeLayerIndex < 0" @click="mapStore.removeLayer(mapStore.activeLayerIndex)">
        <img :src="iconDelete" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" v-tooltip="'上移图层'" :disabled="disabled" @click="mapStore.moveLayerUp(mapStore.activeLayerIndex)">
        <img :src="iconUp" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" v-tooltip="'下移图层'" :disabled="disabled" @click="mapStore.moveLayerDown(mapStore.activeLayerIndex)">
        <img :src="iconDown" class="layer-tool-icon" />
      </button>
    </div>

    <div ref="listRef" class="layer-list">
      <div
        v-for="(item, dIdx) in displayLayers"
        :key="item.layer.id"
        class="layer-item"
        :class="{
          'layer-item-active': mapStore.activeLayerIndex === item.index,
          'layer-item-dragging': dragging && draggingIndex === item.index,
          'insert-before': dragging && dropDisplayIndex === dIdx,
          'insert-after': dragging && dropDisplayIndex === displayLayers.length && dIdx === displayLayers.length - 1,
        }"
        @click="selectLayer(item.index)"
        @mousedown="onRowPointerDown($event, item.index)"
      >
        <div class="layer-thumb">
          <img
            v-if="thumbUrls.get(item.layer.id)"
            :src="thumbUrls.get(item.layer.id)"
            class="layer-thumb-img"
            :style="{ imageRendering: imageRenderingStyle }"
            draggable="false"
          />
        </div>

        <!-- 图层类型图标：图像 / 图块 -->
        <img
          :src="item.layer.type === 'image' ? iconImageType : iconTileType"
          class="layer-type-icon"
          draggable="false"
        />

        <template v-if="editingLayerIndex === item.index">
          <input
            class="layer-rename-input"
            v-model="editingName"
            @blur="confirmRename"
            @keydown.enter.prevent="confirmRename"
            @keydown.escape="cancelRename"
            @click.stop
            @mousedown.stop
          />
        </template>
        <template v-else>
          <span class="layer-name" @dblclick.stop="startRename(item.index)">
            {{ item.layer.name }}
          </span>
        </template>

        <button
          class="layer-vis-btn"
          v-tooltip="item.layer.visible ? '隐藏' : '显示'"
          @click.stop="mapStore.toggleLayerVisibility(item.index)"
        >
          <img :src="item.layer.visible ? iconShow : iconHide" class="vis-icon" />
        </button>
        <button
          class="layer-lock-btn"
          :class="{ 'layer-locked': item.layer.locked }"
          v-tooltip="item.layer.locked ? '解锁' : '锁定'"
          @click.stop="mapStore.toggleLayerLock(item.index)"
        >
          <img :src="item.layer.locked ? iconLock : iconUnlock" class="lock-icon" />
        </button>
      </div>

      <div v-if="displayLayers.length === 0" class="layer-empty">暂无图层</div>
    </div>

    <div class="layer-info-bar">
      <span class="layer-info-text">模式{{ mapStore.activeMode === 'image' ? '图像' : '图块' }}</span>
    </div>
  </div>
</template>

<style scoped>
.layer-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: var(--bg-root);
}

.layer-toolbar {
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 8px;
  gap: 4px;
  flex-shrink: 0;
  border-bottom: 1px solid rgb(45, 45, 45);
}

.layer-tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  height: 28px;
  background: rgb(40, 43, 52);
  border: none;
  border-radius: 4px;
  cursor: pointer;
  padding: 2px;
  transition: background 0.15s;
}

.layer-tool-btn:hover {
  background: var(--bg-hover);
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
  padding: 2px 0;
  background: rgb(30, 30, 30);
}

.layer-item {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 54px;
  padding: 0 6px;
  border-radius: 4px;
  cursor: grab;
  transition: background 0.12s;
  position: relative;
}

.layer-item:hover {
  background: rgb(40, 43, 52);
}

.layer-item-active {
  background: rgb(60, 65, 75);
}

.layer-item-dragging {
  opacity: 0.45;
}

/* 拖拽插入位置指示线 */
.insert-before::before,
.insert-after::after {
  content: '';
  position: absolute;
  left: 2px;
  right: 2px;
  height: 2px;
  background: var(--accent);
  border-radius: 1px;
}

.insert-before::before {
  top: -1px;
}

.insert-after::after {
  bottom: -1px;
}

.layer-thumb {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  background: rgb(50, 53, 62);
  border-radius: 5px;
  overflow: hidden;
}

.layer-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}

/* 图层类型图标（图像 / 图块） */
.layer-type-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  opacity: 0.8;
  pointer-events: none;
}

.layer-name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: rgb(196, 200, 206);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  user-select: none;
}

.layer-rename-input {
  flex: 1;
  min-width: 0;
  height: 22px;
  background: rgb(40, 43, 52);
  border: 1px solid var(--border-light);
  border-radius: 3px;
  color: #fff;
  font-size: 12px;
  padding: 0 4px;
  outline: none;
}

.layer-vis-btn,
.layer-lock-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
}

.layer-vis-btn:hover,
.layer-lock-btn:hover {
  background: rgb(70, 74, 84);
}

.vis-icon {
  width: 18px;
  height: 18px;
  opacity: 0.85;
}

.lock-icon {
  width: 16px;
  height: 16px;
  opacity: 0.8;
}

.layer-locked .lock-icon {
  opacity: 1;
}

.layer-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 80px;
  color: rgb(80, 80, 80);
  font-size: 12px;
}

.layer-info-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  background: var(--bg-root);
  flex-shrink: 0;
}

.layer-info-text {
  font-size: 12px;
  color: rgb(156, 160, 164);
}
</style>
