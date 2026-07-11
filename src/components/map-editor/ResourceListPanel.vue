<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { useMapStore, type MapResource } from '../../stores/map'
import { useProjectStore } from '../../stores/project'
import { useEditorStore } from '../../stores/editor'
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

const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  'open-library': []
  'select-tile': [resourceIndex: number, tileIndex: number]
}>()

const mapStore = useMapStore()
const projectStore = useProjectStore()
const editorStore = useEditorStore()
const showImportDialog = ref(false)
const collisionEditorRef = ref<InstanceType<typeof CollisionEditor>>()

// 将资源文件复制到当前地图目录，返回相对路径
async function copyResourceToMapDir(srcPath: string): Promise<string> {
  const projectRoot = projectStore.root
  const mapName = mapStore.mapData.name
  if (!projectRoot || !mapName) throw new Error('地图未就绪')
  const fileName = srcPath.split('/').pop() || 'resource.png'
  const relativePath = `assets/maps/${mapName}/images/${fileName}`
  await invoke<string>('copy_file_to_project', {
    src: srcPath,
    projectRoot,
    relativePath,
  })
  return relativePath
}

// 当前图层的资源列表
const currentResources = computed(() => {
  const layer = mapStore.activeLayer
  return layer?.resources ?? []
})

// 监听图层变化
watch(() => mapStore.activeLayerIndex, () => {})

// ====== 全局缓存（跨图层切换复用，不清空） ======
// URL 缓存：path → data URL / convertFileSrc URL
const globalUrlCache = new Map<string, string>()
// 瓦片缩略图缓存：resourcePath → tileThumbnails[]
const globalTileCache = new Map<string, { count: number; thumbnails: string[] }>()
// 图片元素缓存
const imageLoadCache = new Map<string, HTMLImageElement>()

// ====== 当前图层的响应式数据（每次切换只更新这个） ======
const currentTileCounts = ref<Map<number, number>>(new Map())
const currentTileThumbnails = ref<Map<string, string>>(new Map())
const resolvedUrls = ref<Map<string, string>>(new Map())

async function getResourceUrl(path: string): Promise<string> {
  const cached = globalUrlCache.get(path)
  if (cached) return cached

  let url: string
  if (path.startsWith('/maps/')) {
    // 内置资源：引擎 assets 目录
    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')
      url = await invoke<string>('read_image_as_data_url', { path: `${engineDir}${path}` })
    } catch (e) {
      console.warn('加载内置资源失败:', path, e)
      url = ''
    }
  } else if (path.startsWith('assets/')) {
    // 项目目录中的相对路径
    const fullPath = `${projectStore.root}/${path}`
    url = convertFileSrc(fullPath)
  } else {
    // 绝对文件系统路径（用户导入的原始文件）
    url = convertFileSrc(path)
  }

  globalUrlCache.set(path, url)
  return url
}

function getTileCount(resource: MapResource): number {
  const idx = currentResources.value.indexOf(resource)
  return currentTileCounts.value.get(idx) ?? 0
}

function getTileThumbnail(rIdx: number, tIdx: number): string {
  return currentTileThumbnails.value.get(`${rIdx}:${tIdx}`) || ''
}

async function loadImage(src: string): Promise<HTMLImageElement> {
  const cached = imageLoadCache.get(src)
  if (cached) return cached
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      imageLoadCache.set(src, img)
      resolve(img)
    }
    img.onerror = reject
    img.src = src
  })
}

// 为绘制图层生成瓦片缩略图（结果缓存到 globalTileCache）
async function generateTileThumbnailsForLayer() {
  const layer = mapStore.activeLayer
  if (!layer || layer.type !== 'drawing') return

  const batchCounts = new Map<number, number>()
  const batchThumbs = new Map<string, string>()

  for (let i = 0; i < currentResources.value.length; i++) {
    const res = currentResources.value[i]
    const cached = globalTileCache.get(res.path)
    if (cached) {
      batchCounts.set(i, cached.count)
      for (let t = 0; t < cached.count; t++) {
        batchThumbs.set(`${i}:${t}`, cached.thumbnails[t] || '')
      }
      continue
    }

    try {
      const url = await getResourceUrl(res.path)
      if (!url) { batchCounts.set(i, 0); continue }
      const img = await loadImage(url)
      const cols = Math.floor(img.width / res.tileWidth)
      const rows = Math.floor(img.height / res.tileHeight)
      const count = cols * rows
      batchCounts.set(i, count)

      const thumbs: string[] = []
      for (let tIdx = 0; tIdx < count; tIdx++) {
        const row = Math.floor(tIdx / cols)
        const col = tIdx % cols
        const canvas = document.createElement('canvas')
        canvas.width = res.tileWidth
        canvas.height = res.tileHeight
        const ctx = canvas.getContext('2d')!
        ctx.drawImage(
          img,
          col * res.tileWidth, row * res.tileHeight,
          res.tileWidth, res.tileHeight,
          0, 0,
          res.tileWidth, res.tileHeight
        )
        const dataUrl = canvas.toDataURL()
        thumbs.push(dataUrl)
        batchThumbs.set(`${i}:${tIdx}`, dataUrl)
      }
      globalTileCache.set(res.path, { count, thumbnails: thumbs })
    } catch {
      batchCounts.set(i, 0)
    }
  }

  currentTileCounts.value = batchCounts
  currentTileThumbnails.value = batchThumbs
}

// 切换图层时刷新：只解析 URL（快），绘制图层才生成瓦片缩略图
async function refreshAllThumbnails() {
  const urlMap = new Map<string, string>()
  const resources = currentResources.value
  await Promise.all(resources.map(async (res) => {
    if (!urlMap.has(res.path)) {
      urlMap.set(res.path, await getResourceUrl(res.path))
    }
  }))
  resolvedUrls.value = urlMap

  // 绘制图层才生成瓦片缩略图
  const layer = mapStore.activeLayer
  if (layer?.type === 'drawing') {
    await generateTileThumbnailsForLayer()
  } else {
    currentTileCounts.value = new Map()
    currentTileThumbnails.value = new Map()
  }
}

function getResolvedUrl(path: string): string {
  return resolvedUrls.value.get(path) || ''
}

// 切换图层或图块尺寸变化时刷新
watch(() => mapStore.activeLayerIndex, refreshAllThumbnails)
watch(() => currentResources.value.length, refreshAllThumbnails)
watch(() => mapStore.mapData.tileSize, () => {
  // 图块尺寸变化时清空瓦片缓存并重新生成
  globalTileCache.clear()
  refreshAllThumbnails()
})
// 地图加载时精确刷新缩略图（loadMap 递增 mapLoadCount，此时 currentResources 已更新）
// 不清理 globalTileCache：相同路径的 tileset 复用缓存，无需重新生成
watch(() => mapStore.mapLoadCount, () => {
  refreshAllThumbnails()
})

// 渲染模式变化时刷新缩略图
watch(() => editorStore.renderMode, () => {
  globalTileCache.clear()
  refreshAllThumbnails()
})

onMounted(refreshAllThumbnails)

// 根据渲染模式返回 CSS image-rendering 值
const imageRenderingStyle = computed(() => {
  return editorStore.renderMode === 'pixelated' ? 'pixelated' : 'auto'
})

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

async function onResourceImported(options: { path: string; mode: 'image' | 'tileset'; size: string }) {
  const isImageLayer = mapStore.activeLayer?.type === 'image'
  // 复制资源文件到项目地图目录
  let relativePath: string
  try {
    relativePath = await copyResourceToMapDir(options.path)
  } catch (e) {
    console.error('复制资源到项目目录失败:', e)
    relativePath = options.path
  }
  const [tw, th] = options.size.split('x').map(Number)
  mapStore.addResource({
    name: options.path.split('/').pop()?.split('.')[0] || '资源',
    path: relativePath,
    resourceType: isImageLayer ? 'image' : options.mode,
    tileWidth: isImageLayer ? 64 : tw,
    tileHeight: isImageLayer ? 64 : th,
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

// Scratch 风格拖拽：mousedown 开始
function onResourceMouseDown(e: MouseEvent, rIdx: number) {
  if (e.button !== 0) return
  const isImageLayer = mapStore.activeLayer?.type === 'image'
  if (!isImageLayer) return

  const resource = currentResources.value[rIdx]
  if (!resource) return

  // 创建拖拽预览元素
  const preview = document.createElement('img')
  preview.id = 'drag-preview'
  preview.src = getResolvedUrl(resource.path)
  preview.draggable = false
  preview.style.cssText = `
    position: fixed;
    pointer-events: none;
    z-index: 9999;
    opacity: 0.8;
    width: 64px;
    height: 64px;
    object-fit: contain;
    transform: translate(-50%, -50%);
  `
  preview.style.left = e.clientX + 'px'
  preview.style.top = e.clientY + 'px'
  document.body.appendChild(preview)

  // 存储拖拽数据
  window.__scratchDragData = { resourceIndex: rIdx }

  // 监听 mousemove 和 mouseup
  const onMouseMove = (ev: MouseEvent) => {
    preview.style.left = ev.clientX + 'px'
    preview.style.top = ev.clientY + 'px'
  }

  const onMouseUp = (ev: MouseEvent) => {
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
    preview.remove()

    // 检查是否在 canvas 区域释放
    const canvasEl = document.querySelector('.map-canvas canvas')
    if (canvasEl) {
      const rect = canvasEl.getBoundingClientRect()
      if (ev.clientX >= rect.left && ev.clientX <= rect.right &&
          ev.clientY >= rect.top && ev.clientY <= rect.bottom) {
        // 触发自定义事件，通知 canvas 放置图像
        const event = new CustomEvent('scratch-drop', {
          detail: {
            resourceIndex: window.__scratchDragData?.resourceIndex,
            clientX: ev.clientX,
            clientY: ev.clientY,
          }
        })
        canvasEl.dispatchEvent(event)
      }
    }

    window.__scratchDragData = null
  }

  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
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
      <button class="res-tool-btn" v-tooltip="'打开资源库'" @click="emit('open-library')">
        <img :src="iconLibrary" class="res-tool-icon" />
      </button>
      <button class="res-tool-btn import-btn" v-tooltip="'上传本地资源'" :disabled="disabled" @click="showImportDialog = true">
        <img :src="iconUpload" class="res-tool-icon" />
      </button>
      <button class="res-tool-btn" v-tooltip="'选中删除'" @click="onDeleteResource">
        <img :src="iconDelete" class="res-tool-icon" />
      </button>
      <button class="res-tool-btn" v-tooltip="'重置'" @click="onClearResources">
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
          @mousedown.prevent="onResourceMouseDown($event, rIdx)"
          @click="onResourceClick(rIdx)"
        >
          <img :src="getResolvedUrl(resource.path)" class="image-preview" draggable="false" :style="{ imageRendering: imageRenderingStyle }" />
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
            :style="getTileThumbnail(rIdx, tIdx - 1) ? { backgroundImage: `url(${getTileThumbnail(rIdx, tIdx - 1)})`, backgroundSize: 'contain', backgroundRepeat: 'no-repeat', backgroundPosition: 'center', imageRendering: imageRenderingStyle } : {}"
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
        v-tooltip="'移动锚点'"
        @click="mapStore.setCollisionTool('move')"
      >
        <img :src="iconMoveAnchor" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': mapStore.collisionTool === 'add' }"
        v-tooltip="'添加锚点'"
        @click="mapStore.setCollisionTool('add')"
      >
        <img :src="iconAddAnchor" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': mapStore.collisionTool === 'delete' }"
        v-tooltip="'删除锚点'"
        @click="mapStore.setCollisionTool('delete')"
      >
        <img :src="iconDelAnchor" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        v-tooltip="'重置锚点'"
        @click="collisionEditorRef?.resetCollision()"
      >
        <img :src="iconResetAnchor" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': mapStore.snapToPixel }"
        v-tooltip="'吸附锚点'"
        @click="mapStore.toggleSnapToPixel()"
      >
        <img :src="iconSnapAnchor" class="col-tool-icon" />
      </button>
    </div>

    <!-- 碰撞编辑器 -->
    <CollisionEditor ref="collisionEditorRef" />

    <div class="res-info-bar">
      <span class="res-info-text">资源:{{ mapStore.selectedResourceIndex >= 0 ? (currentResources[mapStore.selectedResourceIndex]?.name || '--') : '--' }}</span>
    </div>

    <MapResourceImportDialog
      v-if="showImportDialog"
      :layer-type="mapStore.activeLayer?.type || 'image'"
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
  background: var(--bg-root);
  border-right: 1px solid var(--border);
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
  background: var(--bg-hover);
}

.import-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
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
  border-color: var(--accent) !important;
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
  background: var(--bg-hover);
}

.col-tool-active {
  background: var(--border-light);
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
  background: var(--bg-root);
  flex-shrink: 0;
}

.res-info-text {
  font-size: 12px;
  color: rgb(156, 160, 164);
}
</style>
