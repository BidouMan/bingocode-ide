<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { useMapStore, type MapResource } from '../../stores/map'
import { useProjectStore } from '../../stores/project'
import { useEditorStore } from '../../stores/editor'
import MapResourceImportDialog from '../resource-panel/MapResourceImportDialog.vue'
import iconLibrary from '../../assets/icons/图片库.svg'
import iconUpload from '../../assets/icons/上传本地图片资源.svg'
import iconDelete from '../../assets/icons/选中删除.svg'
import iconReset from '../../assets/icons/重置.svg'
import iconChevron from '../../assets/icons/right_arrow.svg'

/**
 * 图块模式专用：画布下方的横向素材面板。
 * 图块绘制工具 + 素材库 + 瓦片网格，宽度铺满画布区域，可收起。
 */
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
const collapsed = ref(false)

// 供图层工具栏的「本地上传」在图块模式下打开素材导入弹窗
function openImport() {
  showImportDialog.value = true
}

defineExpose({ openImport })

const currentResources = computed(() => mapStore.activeLayerResources)

// ====== 全局缓存（跨图层切换复用，不清空） ======
const globalUrlCache = new Map<string, string>()
const globalTileCache = new Map<string, { count: number; thumbnails: string[] }>()
const imageLoadCache = new Map<string, HTMLImageElement>()

const currentTileCounts = ref<Map<number, number>>(new Map())
const currentTileThumbnails = ref<Map<string, string>>(new Map())
const resolvedUrls = ref<Map<string, string>>(new Map())

async function getResourceUrl(path: string): Promise<string> {
  const cached = globalUrlCache.get(path)
  if (cached) return cached

  let url: string
  if (path.startsWith('/maps/')) {
    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')
      url = await invoke<string>('read_image_as_data_url', { path: `${engineDir}${path}` })
    } catch (e) {
      console.warn('加载内置资源失败:', path, e)
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

async function generateTileThumbnails() {
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
      const count = cols * Math.floor(img.height / res.tileHeight)
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

async function refreshAll() {
  const urlMap = new Map<string, string>()
  await Promise.all(currentResources.value.map(async (res) => {
    if (!urlMap.has(res.path)) {
      urlMap.set(res.path, await getResourceUrl(res.path))
    }
  }))
  resolvedUrls.value = urlMap
  await generateTileThumbnails()
}

watch(() => mapStore.activeLayerIndex, refreshAll)
watch(() => currentResources.value.length, refreshAll)
watch(() => mapStore.mapData.tileSize, () => {
  globalTileCache.clear()
  refreshAll()
})
watch(() => mapStore.mapLoadCount, refreshAll)
watch(() => editorStore.renderMode, () => {
  globalTileCache.clear()
  refreshAll()
})

onMounted(refreshAll)

const imageRenderingStyle = computed(() => {
  return editorStore.renderMode === 'pixelated' ? 'pixelated' : 'auto'
})

function onDeleteResource() {
  const idx = mapStore.selectedResourceIndex
  if (idx >= 0) {
    mapStore.removeResource(idx)
    refreshAll()
  }
}

function onClearResources() {
  mapStore.clearResources()
  refreshAll()
}

function onDragStart(e: DragEvent, rIdx: number, tIdx: number) {
  e.dataTransfer?.setData('application/x-bingo-tile', JSON.stringify({ resourceIndex: rIdx, tileIndex: tIdx }))
  e.dataTransfer!.effectAllowed = 'copy'
}

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

async function onResourceImported(options: { path: string; mode: 'image' | 'tileset'; size: string }) {
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
    resourceType: 'tileset',
    tileWidth: tw,
    tileHeight: th,
    collisionType: '图像',
    collisionEnabled: false,
  })
  showImportDialog.value = false
  refreshAll()
}
</script>

<template>
  <div class="tile-resource-bar" :class="{ collapsed }">
    <div class="bar-toolbar">
      <button class="bar-tool-btn" v-tooltip="'打开资源库'" @click="emit('open-library')">
        <img :src="iconLibrary" class="bar-tool-icon" />
      </button>
      <button class="bar-tool-btn" v-tooltip="'上传本地资源'" :disabled="disabled" @click="openImport">
        <img :src="iconUpload" class="bar-tool-icon" />
      </button>
      <button class="bar-tool-btn" v-tooltip="'选中删除'" @click="onDeleteResource">
        <img :src="iconDelete" class="bar-tool-icon" />
      </button>
      <button class="bar-tool-btn" v-tooltip="'重置'" @click="onClearResources">
        <img :src="iconReset" class="bar-tool-icon" />
      </button>
      <div class="bar-spacer" />
      <button
        class="bar-tool-btn collapse-btn"
        :class="{ 'collapse-rotated': !collapsed }"
        v-tooltip="collapsed ? '展开素材' : '收起素材'"
        @click="collapsed = !collapsed"
      >
        <img :src="iconChevron" class="bar-tool-icon" />
      </button>
    </div>

    <div class="bar-body">
      <div
        v-for="(resource, rIdx) in currentResources"
        :key="resource.id"
        class="resource-group"
      >
        <div class="resource-name" :title="resource.name">{{ resource.name }}</div>
        <div class="tile-grid">
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

    <MapResourceImportDialog
      v-if="showImportDialog"
      layer-type="drawing"
      @close="showImportDialog = false"
      @imported="onResourceImported"
    />
  </div>
</template>

<style scoped>
.tile-resource-bar {
  display: flex;
  flex-direction: column;
  height: 156px;
  flex-shrink: 0;
  background: var(--bg-root);
  border-top: 1px solid var(--border);
}

.tile-resource-bar.collapsed {
  height: 30px;
}

.tile-resource-bar.collapsed .bar-body {
  display: none;
}

.bar-toolbar {
  display: flex;
  align-items: center;
  height: 30px;
  padding: 0 8px;
  gap: 4px;
  flex-shrink: 0;
}

.bar-tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  padding: 3px;
  transition: background 0.15s;
}

.bar-tool-btn:hover {
  background: var(--bg-hover);
}

.bar-tool-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.bar-tool-icon {
  width: 20px;
  height: 20px;
}

.bar-spacer {
  flex: 1;
}

.collapse-btn img {
  transition: transform 0.15s;
}

/* 展开时箭头朝下，收起时朝右 */
.collapse-rotated img {
  transform: rotate(90deg);
}

.bar-body {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 4px 10px 8px;
  overflow: auto;
  background: rgb(30, 30, 30);
}

.resource-group {
  flex-shrink: 0;
  width: 232px;
}

.resource-name {
  font-size: 11px;
  color: rgb(156, 160, 164);
  padding: 2px 2px 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.tile-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 2px;
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

.resource-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 200px;
  height: 100%;
  color: rgb(80, 80, 80);
  font-size: 12px;
}
</style>
