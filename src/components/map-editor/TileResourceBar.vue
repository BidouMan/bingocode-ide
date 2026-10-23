<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { useMapStore, type MapResource } from '../../stores/map'
import { useProjectStore } from '../../stores/project'
import MapResourceImportDialog from '../resource-panel/MapResourceImportDialog.vue'
import iconLibrary from '../../assets/icons/图片库.svg'
import iconUpload from '../../assets/icons/上传本地图片资源.svg'
import iconDelete from '../../assets/icons/选中删除.svg'
import iconReset from '../../assets/icons/重置.svg'
import iconChevron from '../../assets/icons/right_arrow.svg'

/**
 * 图块模式专用：画布下方的图块笔刷面板。
 * 每个图块都是独立“笔刷”，按调色板顺序从左到右、从上到下排列；
 * 支持拖拽重排、单独移除，图块集导入时可选择部分导入。
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
const showImportDialog = ref(false)
const collapsed = ref(false)

// 供图层工具栏的「本地上传」在图块模式下打开素材导入弹窗
function openImport() {
  showImportDialog.value = true
}

defineExpose({ openImport })

const currentResources = computed(() => mapStore.activeLayerResources)
const tileResources = computed(() => currentResources.value.filter(r => r.resourceType !== 'image'))

// ====== 全局缓存 ======
const globalUrlCache = new Map<string, string>()
const globalTileCache = new Map<string, { count: number; thumbnails: string[]; empty: boolean[] }>()
const imageLoadCache = new Map<string, HTMLImageElement>()

const tileCounts = ref<Map<string, number>>(new Map())
const tileThumbs = ref<Map<string, string>>(new Map())
// 空格子（整块全透明）标记：不进入笔刷调色板
const tileEmpty = ref<Map<string, boolean>>(new Map())
// 已经展开进调色板的素材（避免刷新时重复追加/复活已删除的图块）
let expandedResources = new Set<string>()

const paletteEntries = computed(() => mapStore.mapData.tilePalette ?? [])

interface PaletteItem {
  paletteIndex: number
  resource: MapResource
  resourceIndex: number
  tileIndex: number
  thumb: string
}

/** 调色板按保存顺序展开为界面条目（无效条目自动跳过） */
const paletteItems = computed<PaletteItem[]>(() => {
  const items: PaletteItem[] = []
  const resources = currentResources.value
  for (let i = 0; i < paletteEntries.value.length; i++) {
    const entry = paletteEntries.value[i]
    const resourceIndex = resources.findIndex(r => r.id === entry.resourceId)
    if (resourceIndex < 0) continue
    const resource = resources[resourceIndex]
    const count = tileCounts.value.get(resource.id) ?? 0
    if (entry.tileIndex < 0 || entry.tileIndex >= count) continue
    if (tileEmpty.value.get(`${resource.id}:${entry.tileIndex}`)) continue
    items.push({
      paletteIndex: i,
      resource,
      resourceIndex,
      tileIndex: entry.tileIndex,
      thumb: tileThumbs.value.get(`${resource.id}:${entry.tileIndex}`) || '',
    })
  }
  return items
})

const selectedPaletteIndex = computed(() => {
  if (mapStore.selectedResourceIndex < 0) return -1
  const item = paletteItems.value.find(it =>
    it.resourceIndex === mapStore.selectedResourceIndex
    && it.tileIndex === mapStore.selectedTileIndex
  )
  return item ? item.paletteIndex : -1
})

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

function cacheKey(res: MapResource) {
  return `${res.id}:${res.tileWidth}x${res.tileHeight}`
}

/** 整块全透明 = 空图块（不进入笔刷列表） */
function isCanvasEmpty(canvas: HTMLCanvasElement): boolean {
  const ctx = canvas.getContext('2d')
  if (!ctx) return true
  const d = ctx.getImageData(0, 0, canvas.width, canvas.height).data
  for (let i = 3; i < d.length; i += 4) {
    if (d[i] > 8) return false
  }
  return true
}

async function generateTileThumbnails() {
  const batchCounts = new Map<string, number>()
  const batchThumbs = new Map<string, string>()
  const batchEmpty = new Map<string, boolean>()

  for (const res of tileResources.value) {
    const key = cacheKey(res)
    const cached = globalTileCache.get(key)
    if (cached) {
      batchCounts.set(res.id, cached.count)
      for (let t = 0; t < cached.count; t++) {
        batchThumbs.set(`${res.id}:${t}`, cached.thumbnails[t] || '')
        batchEmpty.set(`${res.id}:${t}`, cached.empty?.[t] ?? false)
      }
      continue
    }

    try {
      const url = await getResourceUrl(res.path)
      if (!url) { batchCounts.set(res.id, 0); continue }
      const img = await loadImage(url)
      const cols = Math.floor(img.width / res.tileWidth)
      const count = cols * Math.floor(img.height / res.tileHeight)
      batchCounts.set(res.id, count)

      const thumbs: string[] = []
      const emptyFlags: boolean[] = []
      for (let tIdx = 0; tIdx < count; tIdx++) {
        const row = Math.floor(tIdx / cols)
        const col = tIdx % cols
        const canvas = document.createElement('canvas')
        canvas.width = res.tileWidth
        canvas.height = res.tileHeight
        const ctx = canvas.getContext('2d', { willReadFrequently: true })!
        ctx.drawImage(
          img,
          col * res.tileWidth, row * res.tileHeight,
          res.tileWidth, res.tileHeight,
          0, 0,
          res.tileWidth, res.tileHeight
        )
        const empty = isCanvasEmpty(canvas)
        emptyFlags.push(empty)
        thumbs.push(canvas.toDataURL())
        batchThumbs.set(`${res.id}:${tIdx}`, thumbs[tIdx])
        batchEmpty.set(`${res.id}:${tIdx}`, empty)
      }
      globalTileCache.set(key, { count, thumbnails: thumbs, empty: emptyFlags })
    } catch {
      batchCounts.set(res.id, 0)
    }
  }

  tileCounts.value = batchCounts
  tileThumbs.value = batchThumbs
  tileEmpty.value = batchEmpty
  syncPaletteWithResources(batchCounts, batchEmpty)
}

/** 把新素材的非空图块按顺序展开进调色板；已存在的素材不重复追加 */
function syncPaletteWithResources(
  counts: Map<string, number>,
  empty: Map<string, boolean>
) {
  const resources = tileResources.value
  if (mapStore.mapData.tilePalette === undefined) {
    const entries: { resourceId: string; tileIndex: number }[] = []
    for (const res of resources) {
      const count = counts.get(res.id) ?? 0
      for (let t = 0; t < count; t++) {
        if (empty.get(`${res.id}:${t}`)) continue
        entries.push({ resourceId: res.id, tileIndex: t })
      }
    }
    mapStore.setTilePalette(entries)
    expandedResources = new Set(
      resources.filter(r => (counts.get(r.id) ?? 0) > 0).map(r => r.id)
    )
    return
  }

  // 旧存档里可能已经包含空图块：顺手清掉
  const existing = mapStore.mapData.tilePalette ?? []
  const cleaned = existing.filter(e => !empty.get(`${e.resourceId}:${e.tileIndex}`))
  if (cleaned.length !== existing.length) mapStore.setTilePalette(cleaned)

  const newEntries: { resourceId: string; tileIndex: number }[] = []
  for (const res of resources) {
    if (expandedResources.has(res.id)) continue
    const count = counts.get(res.id) ?? 0
    if (count <= 0) continue // 加载失败时保留，下次刷新重试
    for (let t = 0; t < count; t++) {
      if (empty.get(`${res.id}:${t}`)) continue
      newEntries.push({ resourceId: res.id, tileIndex: t })
    }
    expandedResources.add(res.id)
  }
  if (newEntries.length > 0) mapStore.addPaletteEntries(newEntries)
}

async function refreshAll() {
  await generateTileThumbnails()
}

watch(() => mapStore.activeLayerIndex, refreshAll)
watch(() => currentResources.value.length, refreshAll)
watch(() => mapStore.mapData.tileSize, () => {
  globalTileCache.clear()
  refreshAll()
})
watch(() => mapStore.mapLoadCount, () => {
  // 载入地图后以当前素材为基线，避免把已删除的图块重新展开
  expandedResources = new Set(tileResources.value.map(r => r.id))
  refreshAll()
})

onMounted(() => {
  expandedResources = new Set(tileResources.value.map(r => r.id))
  refreshAll()
})

function onDeleteSelected() {
  const idx = selectedPaletteIndex.value
  if (idx >= 0) mapStore.removePaletteEntry(idx)
}

function onClearResources() {
  mapStore.clearResources()
  refreshAll()
}

function onDragStart(e: DragEvent, item: PaletteItem) {
  e.dataTransfer?.setData('application/x-bingo-tile', JSON.stringify({ resourceIndex: item.resourceIndex, tileIndex: item.tileIndex }))
  e.dataTransfer?.setData('application/x-bingo-palette', String(item.paletteIndex))
  e.dataTransfer!.effectAllowed = 'copyMove'
}

function onPaletteDrop(e: DragEvent, targetIndex: number) {
  const raw = e.dataTransfer?.getData('application/x-bingo-palette')
  if (!raw) return
  const from = Number(raw)
  if (!Number.isFinite(from)) return
  mapStore.movePaletteEntry(from, targetIndex)
}

// 将资源文件复制到当前地图目录，返回相对路径
async function copyResourceToMapDir(srcPath: string): Promise<string> {
  const projectRoot = projectStore.root
  const mapName = mapStore.mapData.name
  if (!projectRoot || !mapName) throw new Error('地图未就绪')
  // 同名文件重复导入时不能覆盖已有素材（否则图层/图块会串图）
  const rawName = srcPath.split('/').pop() || 'resource.png'
  const dot = rawName.lastIndexOf('.')
  const base = dot > 0 ? rawName.slice(0, dot) : rawName
  const ext = dot > 0 ? rawName.slice(dot) : ''
  const used = new Set(
    mapStore.mapData.resources.map(r => r.path.split('/').pop() || ''),
  )
  let fileName = rawName
  let seq = 2
  while (used.has(fileName)) fileName = `${base}-${seq++}${ext}`
  const relativePath = `assets/maps/${mapName}/images/${fileName}`
  await invoke<string>('copy_file_to_project', {
    src: srcPath,
    projectRoot,
    relativePath,
  })
  return relativePath
}

async function onResourceImported(options: {
  path: string
  mode: 'image' | 'tileset'
  size: string
  tileIndices?: number[]
}) {
  // 旧地图没有调色板时，先把已有素材展开，避免只导入新素材的图块
  if (mapStore.mapData.tilePalette === undefined) {
    await generateTileThumbnails()
  }

  let relativePath: string
  try {
    relativePath = await copyResourceToMapDir(options.path)
  } catch (e) {
    console.error('复制资源到项目目录失败:', e)
    relativePath = options.path
  }
  const [tw, th] = options.size.split('x').map(Number)
  const resourceId = mapStore.addResource({
    name: options.path.split('/').pop()?.split('.')[0] || '资源',
    path: relativePath,
    resourceType: options.mode === 'image' ? 'image' : 'tileset',
    tileWidth: tw,
    tileHeight: th,
    collisionType: '图像',
    collisionEnabled: false,
  })
  // 图块集：按用户勾选的图块展开（全部导入时即全部图块）
  if (options.mode === 'tileset') {
    expandedResources.add(resourceId)
    const indices = options.tileIndices ?? []
    mapStore.addPaletteEntries(indices.map(t => ({ resourceId, tileIndex: t })))
  }
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
      <button
        class="bar-tool-btn"
        v-tooltip="'移除选中图块'"
        :disabled="disabled || selectedPaletteIndex < 0"
        @click="onDeleteSelected"
      >
        <img :src="iconDelete" class="bar-tool-icon" />
      </button>
      <button class="bar-tool-btn" v-tooltip="'重置全部图块'" @click="onClearResources">
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
      <div v-if="paletteItems.length > 0" class="tile-grid">
        <div
          v-for="item in paletteItems"
          :key="`${item.resource.id}:${item.tileIndex}`"
          class="tile-cell"
          :class="{
            'tile-selected': item.resourceIndex === mapStore.selectedResourceIndex
              && item.tileIndex === mapStore.selectedTileIndex
          }"
          :title="`${item.resource.name} · #${item.tileIndex}`"
          :style="item.thumb ? { backgroundImage: `url(${item.thumb})`, backgroundSize: 'contain', backgroundRepeat: 'no-repeat', backgroundPosition: 'center', imageRendering: 'pixelated' } : {}"
          draggable="true"
          @dragstart="onDragStart($event, item)"
          @dragover.prevent
          @drop.stop.prevent="onPaletteDrop($event, item.paletteIndex)"
          @click="emit('select-tile', item.resourceIndex, item.tileIndex)"
        />
      </div>
      <div v-else class="resource-empty">
        暂无可用的图块笔刷
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

/* 单一调色板：从左到右横向排列，自动换行 */
.tile-grid {
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 3px;
  flex: 1;
  min-width: 0;
}

.tile-cell {
  width: 38px;
  height: 38px;
  aspect-ratio: 1;
  background: rgb(50, 53, 62);
  border: 1px solid transparent;
  border-radius: 3px;
  cursor: grab;
  transition: border-color 0.1s;
}

.tile-cell:hover {
  border-color: rgb(91, 199, 114);
}

.tile-selected {
  border-color: rgb(91, 199, 114) !important;
  background-color: rgb(60, 65, 75);
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
