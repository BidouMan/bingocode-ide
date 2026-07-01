<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { useMapStore, type MapResource } from '../../stores/map'
import CollisionEditor from './CollisionEditor.vue'
import MapResourceImportDialog from '../resource-panel/MapResourceImportDialog.vue'
import iconLibrary from '../../assets/icons/图片库.svg'
import iconUpload from '../../assets/icons/上传本地图片资源.svg'
import iconDelete from '../../assets/icons/选中删除.svg'
import iconReset from '../../assets/icons/重置.svg'
import iconMoveAnchor from '../../assets/icons/移动锚点.svg'
import iconAddAnchor from '../../assets/icons/添加锚点.svg'
import iconDelAnchor from '../../assets/icons/删除锚点.svg'
import iconResetAnchor from '../../assets/icons/重置锚点.svg'
import iconSnapAnchor from '../../assets/icons/吸附锚点.svg'

const emit = defineEmits<{
  'open-library': []
  'select-tile': [resourceIndex: number, tileIndex: number]
}>()

const mapStore = useMapStore()
const showImportDialog = ref(false)

// 当前图层的资源列表
const currentResources = computed(() => {
  const layer = mapStore.activeLayer
  console.log('[ResourceListPanel] computed currentResources:', {
    activeLayerIndex: mapStore.activeLayerIndex,
    layerName: layer?.name,
    layerType: layer?.type,
    resourceCount: layer?.resources?.length,
    allLayers: mapStore.mapData.layers.map(l => ({ name: l.name, type: l.type }))
  })
  return layer?.resources ?? []
})

// 监听图层变化
watch(() => mapStore.activeLayerIndex, (newIdx) => {
  console.log('[ResourceListPanel] activeLayerIndex changed to:', newIdx)
  const layer = mapStore.mapData.layers[newIdx]
  console.log('[ResourceListPanel] layer at newIdx:', layer ? { name: layer.name, type: layer.type } : null)
})

// Tile thumbnail cache
const tileThumbnails = ref<Map<string, string>>(new Map())
const tileCounts = ref<Map<number, number>>(new Map())
const imageLoadCache = ref<Map<string, HTMLImageElement>>(new Map())

function getTileCount(resource: MapResource): number {
  const idx = currentResources.value.indexOf(resource)
  return tileCounts.value.get(idx) ?? 0
}

function getTileThumbnail(rIdx: number, tIdx: number): string {
  return tileThumbnails.value.get(`${rIdx}:${tIdx}`) || ''
}

async function loadImage(src: string): Promise<HTMLImageElement> {
  if (imageLoadCache.value.has(src)) return imageLoadCache.value.get(src)!
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      imageLoadCache.value.set(src, img)
      resolve(img)
    }
    img.onerror = reject
    img.src = src
  })
}

async function generateTileThumbnails(resource: MapResource, rIdx: number) {
  try {
    const img = await loadImage(resource.path)
    const cols = Math.floor(img.width / resource.tileWidth)
    const rows = Math.floor(img.height / resource.tileHeight)
    const count = cols * rows
    tileCounts.value.set(rIdx, count)

    for (let tIdx = 0; tIdx < count; tIdx++) {
      const row = Math.floor(tIdx / cols)
      const col = tIdx % cols
      const canvas = document.createElement('canvas')
      canvas.width = resource.tileWidth
      canvas.height = resource.tileHeight
      const ctx = canvas.getContext('2d')!
      ctx.drawImage(
        img,
        col * resource.tileWidth, row * resource.tileHeight,
        resource.tileWidth, resource.tileHeight,
        0, 0,
        resource.tileWidth, resource.tileHeight
      )
      tileThumbnails.value.set(`${rIdx}:${tIdx}`, canvas.toDataURL())
    }
  } catch {
    tileCounts.value.set(rIdx, 0)
  }
}

async function refreshAllThumbnails() {
  tileThumbnails.value.clear()
  tileCounts.value.clear()
  for (let i = 0; i < currentResources.value.length; i++) {
    await generateTileThumbnails(currentResources.value[i], i)
  }
}

// 切换图层时刷新
watch(() => mapStore.activeLayerIndex, refreshAllThumbnails)
watch(() => currentResources.value.length, refreshAllThumbnails)

onMounted(refreshAllThumbnails)

function onDeleteResource() {
  const idx = mapStore.selectedResourceIndex
  if (idx >= 0) {
    mapStore.removeResource(idx)
    refreshAllThumbnails()
  }
}

function onClearResources() {
  mapStore.clearResources()
  refreshAllThumbnails()
}

function onResourceImported(options: { path: string; mode: 'image' | 'tileset'; size: string }) {
  const [tw, th] = options.size.split('x').map(Number)
  mapStore.addResource({
    name: options.path.split('/').pop()?.split('.')[0] || '资源',
    path: options.path,
    resourceType: options.mode,
    tileWidth: tw,
    tileHeight: th,
    collisionType: '图像',
    collisionEnabled: false,
    tileSetIndex: 0,
  })
  showImportDialog.value = false
  refreshAllThumbnails()
}

function onDragStart(e: DragEvent, rIdx: number, tIdx: number) {
  const isImageLayer = mapStore.activeLayer?.type === 'image'
  if (isImageLayer) {
    e.dataTransfer?.setData('application/x-bingo-image', JSON.stringify({ resourceIndex: rIdx }))
  } else {
    e.dataTransfer?.setData('application/x-bingo-tile', JSON.stringify({ resourceIndex: rIdx, tileIndex: tIdx }))
  }
  e.dataTransfer!.effectAllowed = 'copy'
}

function onResourceClick(rIdx: number) {
  const isImageLayer = mapStore.activeLayer?.type === 'image'
  if (isImageLayer) {
    mapStore.selectTile(rIdx, -1)
  } else {
    mapStore.selectTile(rIdx, 0)
  }
}
</script>

<template>
  <div class="resource-list-panel">
    <div class="resource-toolbar">
      <button class="res-tool-btn" title="打开资源库" @click="emit('open-library')">
        <img :src="iconLibrary" class="res-tool-icon" />
      </button>
      <button class="res-tool-btn" title="上传本地资源" @click="showImportDialog = true">
        <img :src="iconUpload" class="res-tool-icon" />
      </button>
      <button class="res-tool-btn" title="选中删除" @click="onDeleteResource">
        <img :src="iconDelete" class="res-tool-icon" />
      </button>
      <button class="res-tool-btn" title="重置" @click="onClearResources">
        <img :src="iconReset" class="res-tool-icon" />
      </button>
    </div>

    <div class="resource-list">
      <div
        v-for="(resource, rIdx) in currentResources"
        :key="rIdx"
        class="resource-group"
      >
        <div class="resource-name">{{ resource.name }}</div>
        <!-- 图像图层：显示完整图片 -->
        <div
          v-if="mapStore.activeLayer?.type === 'image'"
          class="image-resource-card"
          :class="{ 'image-selected': mapStore.selectedResourceIndex === rIdx }"
          draggable="true"
          @dragstart="onDragStart($event, rIdx, 0)"
          @click="onResourceClick(rIdx)"
        >
          <img :src="resource.path" class="image-preview" />
        </div>
        <!-- 绘制图层：显示瓦片网格 -->
        <div v-else class="tile-grid">
          <div
            v-for="tIdx in getTileCount(resource)"
            :key="tIdx"
            class="tile-cell"
            :class="{
              'tile-selected': mapStore.selectedResourceIndex === rIdx && mapStore.selectedTileIndex === tIdx - 1
            }"
            :style="getTileThumbnail(rIdx, tIdx - 1) ? { backgroundImage: `url(${getTileThumbnail(rIdx, tIdx - 1)})`, backgroundSize: 'contain', backgroundRepeat: 'no-repeat', backgroundPosition: 'center' } : {}"
            draggable="true"
            @dragstart="onDragStart($event, rIdx, tIdx - 1)"
            @click="emit('select-tile', rIdx, tIdx - 1)"
          />
        </div>
      </div>
      <div v-if="currentResources.length === 0" class="resource-empty">
        暂无资源
      </div>
    </div>

    <div class="res-col-toolbar">
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': mapStore.collisionTool === 'move' }"
        title="移动锚点"
        @click="mapStore.setCollisionTool('move')"
      >
        <img :src="iconMoveAnchor" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': mapStore.collisionTool === 'add' }"
        title="添加锚点"
        @click="mapStore.setCollisionTool('add')"
      >
        <img :src="iconAddAnchor" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': mapStore.collisionTool === 'delete' }"
        title="删除锚点"
        @click="mapStore.setCollisionTool('delete')"
      >
        <img :src="iconDelAnchor" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        title="重置锚点"
        @click="mapStore.setCollisionTool('reset')"
      >
        <img :src="iconResetAnchor" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': mapStore.snapToPixel }"
        title="吸附锚点"
        @click="mapStore.toggleSnapToPixel()"
      >
        <img :src="iconSnapAnchor" class="col-tool-icon" />
      </button>
    </div>

    <CollisionEditor />

    <div class="res-info-bar">
      <span class="res-info-text">资源:{{ mapStore.selectedResourceIndex >= 0 ? (currentResources[mapStore.selectedResourceIndex]?.name || '--') : '--' }}</span>
    </div>

    <MapResourceImportDialog
      v-if="showImportDialog"
      @close="showImportDialog = false"
      @imported="onResourceImported"
    />
  </div>
</template>

<style scoped>
.resource-list-panel {
  display: flex;
  flex-direction: column;
  width: 272px;
  min-width: 272px;
  background: rgb(34, 37, 43);
  border-right: 1px solid rgb(12, 12, 12);
}

.resource-toolbar {
  display: flex;
  align-items: center;
  height: 30px;
  padding: 0 8px;
  gap: 6px;
  flex-shrink: 0;
}

.res-tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
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
  margin: 0 8px;
  background: rgb(30, 30, 30);
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

.image-resource-card {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  margin: 2px;
  background: rgb(50, 53, 62);
  border: 2px solid transparent;
  border-radius: 4px;
  cursor: grab;
  transition: all 0.15s;
}

.image-resource-card:hover {
  border-color: rgb(91, 199, 114);
}

.image-selected {
  border-color: rgb(91, 251, 132) !important;
  background: rgb(60, 65, 75);
}

.image-preview {
  max-width: 100%;
  max-height: 80px;
  object-fit: contain;
}

.resource-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100px;
  color: rgb(80, 80, 80);
  font-size: 12px;
}

.res-col-toolbar {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 8px;
  gap: 6px;
  flex-shrink: 0;
}

.col-tool-btn {
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

.col-tool-btn:hover {
  background: rgb(61, 64, 72);
}

.col-tool-active {
  background: rgb(55, 59, 68);
  border: 1px solid rgb(65, 69, 82);
}

.col-tool-icon {
  width: 20px;
  height: 20px;
}

.res-info-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  background: rgb(34, 37, 43);
  flex-shrink: 0;
}

.res-info-text {
  font-size: 12px;
  color: rgb(156, 160, 164);
}
</style>
