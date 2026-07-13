<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import MapToolbar from './MapToolbar.vue'
import MapCanvas from './MapCanvas.vue'
import ResourceListPanel from './ResourceListPanel.vue'
import PropertyPanel from './PropertyPanel.vue'
import LayerPanel from './LayerPanel.vue'
import { useMapStore } from '../../stores/map'
import { useResourceStore } from '../../stores/resource'
import { useProjectStore } from '../../stores/project'
import JSZip from 'jszip'
import { serializeMap, deserializeMap } from '../../utils/mapSerializer'

const mapStore = useMapStore()
const resourceStore = useResourceStore()
const projectStore = useProjectStore()

const hasMaps = computed(() => resourceStore.maps.length > 0)

const mapCanvasRef = ref<InstanceType<typeof MapCanvas>>()

const emit = defineEmits<{
  'open-resource-lib': []
}>()

// ====== 统一数据源：项目目录 maps/<地图名>/map.json ======

// 获取某个地图对应的目录和文件路径（使用地图名，直观可读）
function mapDirPath(mapName: string): string {
  return `${projectStore.root}/assets/maps/${mapName}`
}
function mapJsonPath(mapName: string): string {
  return `${mapDirPath(mapName)}/map.json`
}

// 保存当前地图到项目目录
async function saveMapToProject(mapName?: string): Promise<void> {
  const name = mapName ?? mapStore.mapData.name
  if (!name) {
    console.warn('[MapEditor] saveMapToProject: 地图名为空，跳过保存')
    return
  }
  if (!projectStore.root) {
    await projectStore.initProject()
  }
  if (!projectStore.root) {
    console.warn('[MapEditor] saveMapToProject: 项目目录未就绪，无法保存')
    return
  }
  const dirPath = mapDirPath(name)
  const savePath = mapJsonPath(name)
  try {
    const saveData = serializeMap(mapStore.mapData)
    const json = JSON.stringify(saveData)
    await invoke('write_file', { path: savePath, content: json })

    // 同时生成 thumbnail.png 快照
    const thumbDataUrl = mapCanvasRef.value?.getThumbnailDataUrl()
    if (thumbDataUrl && thumbDataUrl.startsWith('data:image/')) {
      const base64 = thumbDataUrl.split(',')[1]
      const raw = Uint8Array.from(atob(base64), c => c.charCodeAt(0))
      await invoke('write_binary', { path: `${dirPath}/thumbnail.png`, data: Array.from(raw) })
    }

    // 更新 resource store 中该 map 的 path，供左侧缩略图加载
    const item = resourceStore.maps.find(m => m.name === name)
    if (item) item.path = dirPath
  } catch (e) {
    console.error('[MapEditor] 保存地图到项目目录失败:', e)
  }
}

// 从项目目录加载地图数据
async function loadMapFromProject(itemId: string): Promise<boolean> {
  if (!projectStore.root) {
    await projectStore.initProject()
  }
  if (!projectStore.root) return false

  // 优先从预解析缓存读取
  const cached = resourceStore.getCachedMapData(itemId)
  if (cached) {
    mapStore.loadMap(cached)
    return true
  }

  // 缓存未命中，从磁盘读取
  const item = resourceStore.maps.find(m => m.id === itemId)
  const mapName = item?.name ?? mapStore.mapData.name
  if (!mapName) return false
  const filePath = mapJsonPath(mapName)
  try {
    const exists = await invoke<boolean>('path_exists', { path: filePath })
    if (!exists) return false
    const json = await invoke<string>('read_file', { path: filePath })
    const saveData = JSON.parse(json)
    const mapData = deserializeMap(saveData)
    mapStore.loadMap(mapData)
    return true
  } catch (e) {
    console.error(`[MapEditor] loadMapFromProject: 失败 path=${filePath}`, e)
    return false
  }
}

// 创建空地图数据（资源项刚创建时使用）
function createEmptyMapData(name: string): import('../../stores/map').MapData {
  return {
    name,
    version: 5,
    width: 40,
    height: 30,
    tileSize: 16,
    gravity: false,
    collisionType: '图像',
    collisionEnabled: false,
    layers: [
      {
        id: 0,
        name: '图像图层',
        type: 'image' as const,
        visible: true,
        locked: false,
        tiles: {} as Record<string, number>,
        resources: [],
        images: [],
      },
    ],
    tileSets: [],
  }
}

// ====== 统一入口：currentMapPath 变化时自动保存当前 + 加载目标 ======
// 新建地图时设此标志跳过 watcher 的加载流程
let skipNextPathWatch = false
watch(() => mapStore.currentMapPath, async (newPath, oldPath) => {
  if (!newPath || newPath === oldPath) return
  if (skipNextPathWatch) { skipNextPathWatch = false; return }
  if (!resourceStore.maps.find(m => m.id === newPath)) return

  if (oldPath) {
    // 根据 UUID 找到旧地图的名称，用名称路径保存（名称可能已被重命名）
    const oldItem = resourceStore.maps.find(m => m.id === oldPath)
    if (oldItem) await saveMapToProject(oldItem.name)
  }
  const loaded = await loadMapFromProject(newPath)
  // 无论加载成功或创建空地图，都确保 item.path 指向地图目录（供缩略图使用）
  const mapItem = resourceStore.maps.find(m => m.id === newPath)
  if (mapItem && projectStore.root) {
    mapItem.path = mapDirPath(mapItem.name)
  }
  if (!loaded) {
    const item = resourceStore.maps.find(m => m.id === newPath)
    if (item) {
      mapStore.loadMap(createEmptyMapData(item.name))
    }
  }
})

// ====== 自动保存（编辑时防抖保存到项目目录） ======
let autoSaveTimer: ReturnType<typeof setTimeout> | null = null
let savingItemId = ''
watch(() => JSON.stringify(mapStore.mapData), () => {
  if (autoSaveTimer) clearTimeout(autoSaveTimer)
  savingItemId = mapStore.currentMapPath
  autoSaveTimer = setTimeout(() => {
    if (mapStore.currentMapPath && mapStore.currentMapPath === savingItemId) {
      saveMapToProject()
    }
  }, 2000)
})

// ====== 公开方法（供 MapToolbar 调用） ======

// 切换地图（MapToolbar dropdown 使用）：设 path → watcher 自动保存当前 + 加载目标
function switchToMap(itemId: string) {
  mapStore.setMapPath(itemId)
}

async function onNewMap() {
  if (mapStore.currentMapPath) {
    await saveMapToProject()
  }

  const mapCount = resourceStore.maps.length
  const name = `地图${mapCount + 1}`
  const id = resourceStore.addItem({ name, type: 'map', path: '' })
  const item = resourceStore.maps.find(m => m.id === id)
  if (item && projectStore.root) item.path = mapDirPath(name)
  skipNextPathWatch = true
  mapStore.setMapPath(id)
  mapStore.loadMap(createEmptyMapData(name))
}

async function onImportMap() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.bgm,.zip'
  input.onchange = async (e: Event) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (!file) return

    try {
      const zip = await JSZip.loadAsync(file)

      const mapJsonEntry = zip.file('map.json')
      if (mapJsonEntry) {
        const saveData = JSON.parse(await mapJsonEntry.async('text'))
        const mapData = deserializeMap(saveData)
        mapStore.loadMap(mapData)
        // 导入到项目目录，使用文件名作为资源名
        const name = file.name.replace(/\.bgm$/i, '')
        // 获取原始地图名，用于更新瓦片集图片路径
        const originalName = saveData.name || mapData.name
        const id = resourceStore.addItem({ name, type: 'map', path: '' })
        skipNextPathWatch = true
        mapStore.setMapPath(id)
        mapData.name = name
        // 更新瓦片集的图片路径：将原始地图名替换为新地图名
        if (originalName && originalName !== name) {
          for (const tileSet of mapData.tileSets) {
            if (tileSet.imagePath && tileSet.imagePath.includes(originalName)) {
              tileSet.imagePath = tileSet.imagePath.replace(originalName, name)
            }
          }
        }
        // 先设 path 让 saveMapToProject 能找到资源项
        const importItem = resourceStore.maps.find(m => m.id === id)
        if (importItem && projectStore.root) importItem.path = mapDirPath(name)
        await saveMapToProject()
        return
      }

      alert('无效的地图文件格式，请使用 .bgm 格式')
    } catch (err) {
      alert('导入地图失败: ' + (err as Error).message)
    }
  }
  input.click()
}

async function onExportMap() {
  try {
    const zip = new JSZip()
    const data = mapStore.mapData

    const saveData = serializeMap(data)
    zip.file('map.json', JSON.stringify(saveData, null, 2))

    const thumbDataUrl = mapCanvasRef.value?.getThumbnailDataUrl()
    if (thumbDataUrl && thumbDataUrl.startsWith('data:')) {
      const base64 = thumbDataUrl.split(',')[1]
      zip.file('thumbnail.png', base64, { base64: true })
    }

    // 打包 images 目录中的图片
    if (projectStore.root && data.name) {
      const imagesDir = mapDirPath(data.name) + '/images'
      try {
        const entries = await invoke<string[]>('list_dir', { path: imagesDir })
        for (const entry of entries) {
          if (!entry.endsWith('/')) {
            const filePath = `${imagesDir}/${entry}`
            const content = await invoke<number[]>('read_binary', { path: filePath })
            zip.file(`images/${entry}`, new Uint8Array(content))
          }
        }
      } catch (e) {
        // images 目录可能不存在，忽略
      }
    }

    const blob = await zip.generateAsync({ type: 'blob' })

    // 尝试用 File System API（现代浏览器）
    if ('showSaveFilePicker' in window) {
      const handle = await (window as any).showSaveFilePicker({
        suggestedName: `${data.name}.bgm`,
        types: [{ description: '地图文件', accept: { 'application/zip': ['.bgm'] } }],
      })
      const writable = await handle.createWritable()
      await writable.write(blob)
      await writable.close()
    } else {
      // 回退到 blob URL 下载
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.style.display = 'none'
      link.href = url
      link.download = `${data.name}.bgm`
      document.body.appendChild(link)
      link.click()
      setTimeout(() => {
        document.body.removeChild(link)
        URL.revokeObjectURL(url)
      }, 100)
    }
  } catch (e) {
    console.error('导出地图失败:', e)
  }
}

function onOpenLibrary() {
  emit('open-resource-lib')
}

function onCursorMove(x: number, y: number) {
  mapStore.setCursorPos(x, y)
}

function onDeleteImage() {
  mapCanvasRef.value?.deleteSelectedImage()
}

defineExpose({ switchToMap })
</script>

<template>
  <div class="map-editor-view">
    <div class="map-editor-body" :class="{ disabled: !hasMaps }">
      <ResourceListPanel
        :disabled="!hasMaps"
        @open-library="onOpenLibrary"
        @select-tile="(rIdx, tIdx) => mapStore.selectTile(rIdx, tIdx)"
      />
      <div class="map-editor-center">
        <MapToolbar
          :disabled="!hasMaps"
          @new-map="onNewMap"
          @import-map="onImportMap"
          @export-map="onExportMap"
          @switch-map="switchToMap"
          @delete-image="onDeleteImage"
        />
        <MapCanvas ref="mapCanvasRef" class="map-canvas-area" :class="{ disabled: !hasMaps }" @cursor-move="onCursorMove" />
        <div class="map-info-bar">
          <span class="info-spacer" />
          <span class="info-label">ID:{{ mapStore.currentMapPath ? mapStore.currentMapPath.split('/').pop()?.split('.')[0] ?? '--' : '--' }}</span>
          <span class="info-label">场景大小:{{ mapStore.mapData.width * mapStore.mapData.tileSize }}×{{ mapStore.mapData.height * mapStore.mapData.tileSize }}</span>
          <span class="info-label">坐标:{{ mapStore.cursorX !== null ? mapStore.cursorX * mapStore.mapData.tileSize : '--' }},{{ mapStore.cursorY !== null ? mapStore.cursorY * mapStore.mapData.tileSize : '--' }}</span>
          <span class="info-label">资源尺寸:{{ mapStore.selectedResource?.tileWidth ?? '--' }}×{{ mapStore.selectedResource?.tileHeight ?? '--' }}</span>
          <span class="info-spacer" />
        </div>
      </div>
      <div class="map-editor-right">
        <PropertyPanel :disabled="!hasMaps" />
        <LayerPanel :disabled="!hasMaps" />
      </div>
    </div>
    <div v-if="!hasMaps" class="map-empty-banner">
      <div class="empty-content">
        <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" />
          <path d="M3 9h18M9 21V9" />
        </svg>
        <p class="empty-text">请先创建或导入地图</p>
        <div class="empty-actions">
          <button class="empty-btn" @click="onNewMap">创建地图</button>
          <button class="empty-btn empty-btn-secondary" @click="onImportMap">导入地图</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.map-editor-view {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: rgb(30, 30, 30);
  position: relative;
}

.map-editor-body {
  flex: 1;
  min-height: 0;
  display: flex;
}

.map-editor-center {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.map-canvas-area {
  flex: 1;
  min-height: 0;
}

.map-info-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  gap: 20px;
  background: var(--bg-root);
  flex-shrink: 0;
}

.info-spacer {
  flex: 1;
}

.info-label {
  font-size: 12px;
  color: rgb(156, 160, 164);
  white-space: nowrap;
}

.map-editor-right {
  display: flex;
  flex-direction: column;
  width: 272px;
  min-width: 272px;
  border-left: 1px solid var(--border);
  background: var(--bg-root);
}

.map-empty-banner {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: rgba(41, 44, 52, 0.95);
  z-index: 10;
}

.empty-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.empty-icon {
  width: 48px;
  height: 48px;
  color: #3D4048;
}

.empty-text {
  color: #8B8FA3;
  font-size: 14px;
  margin: 0;
}

.empty-actions {
  display: flex;
  gap: 12px;
}

.empty-btn {
  padding: 8px 24px;
  border-radius: 6px;
  border: 1px solid #3D4048;
  background: #4B9B5C;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}

.empty-btn:hover {
  background: #5bc772;
  border-color: #5bc772;
}

.empty-btn-secondary {
  background: #3D4048;
}

.empty-btn-secondary:hover {
  background: #4D5058;
  border-color: #4D5058;
}

.map-editor-body.disabled,
.map-canvas-area.disabled {
  opacity: 0.6;
  pointer-events: none;
}
</style>
