<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import MapToolbar from './MapToolbar.vue'
import MapCanvas from './MapCanvas.vue'
import TileResourceBar from './TileResourceBar.vue'
import PropertyPanel from './PropertyPanel.vue'
import LayerPanel from './LayerPanel.vue'
import TileCollisionPanel from './TileCollisionPanel.vue'
import { useMapStore } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import { useResourceStore } from '../../stores/resource'
import { useProjectStore } from '../../stores/project'
import { useMapPersistence } from '../../composables/useMapPersistence'
import JSZip from 'jszip'
import { serializeMap, deserializeMap } from '../../utils/mapSerializer'

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()
const resourceStore = useResourceStore()
const projectStore = useProjectStore()

const hasMaps = computed(() => resourceStore.maps.length > 0)

const mapCanvasRef = ref<InstanceType<typeof MapCanvas>>()
const tileResourceBarRef = ref<{ openImport: () => void } | null>(null)

const emit = defineEmits<{
  'open-resource-lib': []
  'open-paint': []
  'map-thumbnail-updated': [itemId: string, dataUrl: string]
}>()

// ====== 持久化：map.json 读写、.bgm 修复、路径解析 ======
const {
  mapDirPath,
  saveMapToProject,
  loadMapFromProject,
  resolveRelativePaths,
  createEmptyMapData,
} = useMapPersistence({
  getThumbnailDataUrl: () => mapCanvasRef.value?.getThumbnailDataUrl() ?? null,
  onThumbnailUpdated: (itemId, dataUrl) => emit('map-thumbnail-updated', itemId, dataUrl),
})

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

  // 默认名字统一为「地图N」顺序名
  const name = resourceStore.nextSequentialName('map', '地图')
  const id = resourceStore.addItem({ name, type: 'map', path: '' })
  const item = resourceStore.maps.find(m => m.id === id)
  if (item && projectStore.root) item.path = mapDirPath(name)
  skipNextPathWatch = true
  mapStore.setMapPath(id)
  mapStore.loadMap(createEmptyMapData(name))
}

async function onUploadLocal() {
  // 图块模式的本地上传交给下方素材面板的导入弹窗（需要选择图块尺寸）
  if (mapStore.activeMode === 'tile') {
    tileResourceBarRef.value?.openImport()
    return
  }
  await onUploadImage()
}

async function onUploadImage() {
  const path = await invoke<string | null>('pick_image_file')
  if (!path) return
  const projectRoot = projectStore.root
  const mapName = mapStore.mapData.name
  if (!projectRoot || !mapName) return
  const fileName = path.split('/').pop() || 'resource.png'
  const relativePath = `assets/maps/${mapName}/images/${fileName}`
  try {
    await invoke('copy_file_to_project', { src: path, projectRoot, relativePath })
  } catch (e) {
    console.error('[MapEditor] 复制资源到项目目录失败:', e)
    return
  }
  mapStore.addResource({
    name: fileName.split('.')[0] || '资源',
    path: relativePath,
    resourceType: 'image',
    tileWidth: 64,
    tileHeight: 64,
    collisionType: '图像',
    collisionEnabled: false,
  })
  await placeImageResource(relativePath)
}

// 供外部（内置资源库）按路径直接放置一张图片并建层
async function placeImageResource(path: string) {
  await mapCanvasRef.value?.placeImageFromPath(path, 0, 0)
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

        // 导入到项目目录，默认名字统一为「地图N」顺序名
        const name = resourceStore.nextSequentialName('map', '地图')
        // 获取原始地图名，用于更新瓦片集图片路径
        const originalName = saveData.name || mapData.name
        const id = resourceStore.addItem({ name, type: 'map', path: '' })

        // 将相对路径解析为绝对路径（.bgm 内的 map.json 使用相对路径）
        const dir = mapDirPath(name)
        resolveRelativePaths(mapData, dir)

        mapStore.loadMap(mapData)
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
          for (const resource of mapData.resources) {
            if (resource.path && resource.path.includes(originalName)) {
              resource.path = resource.path.replace(originalName, name)
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
  mapEditorStore.setCursorPos(x, y)
}

function onDeleteImage() {
  mapCanvasRef.value?.deleteSelectedImage()
}

defineExpose({ switchToMap, placeImageResource })
</script>

<template>
  <div class="map-editor-view">
    <div class="map-editor-body" :class="{ disabled: !hasMaps }">
      <div class="map-editor-left">
        <LayerPanel
          :disabled="!hasMaps"
          @paint="emit('open-paint')"
          @open-library="emit('open-resource-lib')"
          @upload-image="onUploadLocal"
        />
      </div>
      <div class="map-editor-center">
        <MapToolbar
          :disabled="!hasMaps"
          @new-map="onNewMap"
          @import-map="onImportMap"
          @export-map="onExportMap"
          @switch-map="switchToMap"
          @delete-image="onDeleteImage"
          @paint="emit('open-paint')"
        />
        <MapCanvas ref="mapCanvasRef" class="map-canvas-area" :class="{ disabled: !hasMaps }" @cursor-move="onCursorMove" />
        <!-- 图块模式：素材面板从画布下方展开 -->
        <TileResourceBar
          v-if="mapStore.activeMode === 'tile'"
          ref="tileResourceBarRef"
          :disabled="!hasMaps"
          @open-library="onOpenLibrary"
          @select-tile="(rIdx, tIdx) => mapStore.selectTile(rIdx, tIdx)"
        />
        <div class="map-info-bar">
          <span class="info-spacer" />
          <span class="info-label">ID:{{ mapStore.currentMapPath ? mapStore.currentMapPath.split('/').pop()?.split('.')[0] ?? '--' : '--' }}</span>
          <span class="info-label">场景大小:{{ mapStore.mapData.width * mapStore.mapData.tileSize }}×{{ mapStore.mapData.height * mapStore.mapData.tileSize }}</span>
          <span class="info-label">坐标:{{ mapEditorStore.cursorX !== null ? mapEditorStore.cursorX * mapStore.mapData.tileSize : '--' }},{{ mapEditorStore.cursorY !== null ? mapEditorStore.cursorY * mapStore.mapData.tileSize : '--' }}</span>
          <span class="info-label">资源尺寸:{{ mapStore.selectedResource?.tileWidth ?? '--' }}×{{ mapStore.selectedResource?.tileHeight ?? '--' }}</span>
          <span class="info-spacer" />
        </div>
      </div>
      <div class="map-editor-right">
        <PropertyPanel :disabled="!hasMaps" />
        <!-- 碰撞编辑器仅图块模式使用；图像模式在画布上按实例编辑 -->
        <TileCollisionPanel v-if="mapStore.activeMode === 'tile'" />
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
          <button class="empty-btn" @click="onNewMap">绘制地图</button>
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

.map-editor-left {
  display: flex;
  flex-direction: column;
  width: 272px;
  min-width: 272px;
  min-height: 0;
  border-right: 1px solid var(--border);
  background: var(--bg-root);
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
  min-height: 0;
  overflow-y: auto;
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
