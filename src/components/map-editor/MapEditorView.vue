<script setup lang="ts">
import { ref, watch, computed, nextTick } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import MapToolbar from './MapToolbar.vue'
import MapCanvas from './MapCanvas.vue'
import iconZoomOut from '../../assets/icons/reduce-one.svg'
import iconZoomIn from '../../assets/icons/add-one.svg'
import iconUndo from '../../assets/icons/undo.svg'
import iconRedo from '../../assets/icons/redo.svg'
import iconMapLibrary from '../../assets/icons/图片库.svg'
import TileResourceBar from './TileResourceBar.vue'
import PropertyPanel from './PropertyPanel.vue'
import LayerPanel from './LayerPanel.vue'
import TileCollisionPanel from './TileCollisionPanel.vue'
import PaintColorPanel from '../paint-editor/PaintColorPanel.vue'
import { useMapStore } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import { usePaintStore } from '../../stores/paint'
import { useResourceStore } from '../../stores/resource'
import { useProjectStore } from '../../stores/project'
import { useMapPersistence } from '../../composables/useMapPersistence'
import { useMapPaint } from '../../composables/useMapPaint'
import JSZip from 'jszip'
import { deserializeMap } from '../../utils/mapSerializer'
import { toUserX, toUserY } from '../../utils/coords'

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()
const paintStore = usePaintStore()
const resourceStore = useResourceStore()
const projectStore = useProjectStore()

const hasMaps = computed(() => resourceStore.maps.length > 0)

// 切换地图后鼠标未移动，清空坐标避免显示上一张地图的旧位置
watch(
  () => mapStore.mapLoadCount,
  () => {
    mapEditorStore.setCursorPos(null, null)
    // 切图后取消可能残留的放置状态
    mapEditorStore.cancelMarkerPlacing()
  },
)

/** 鼠标所在像素坐标（用户坐标：原点在地图左下角，y 向上为正） */
const cursorCoordText = computed(() => {
  const wx = mapEditorStore.cursorX
  const wy = mapEditorStore.cursorY
  if (wx === null || wy === null) return '--'
  return `${Math.round(toUserX(wx))},${Math.round(toUserY(wy))}`
})

/** 选中图片图层的图片尺寸：放在画布下方信息栏，属性面板里不再占一行 */
const imageSizeText = computed(() => {
  const img = mapStore.selectedImage
  if (!img) return ''
  return `图片尺寸:${Math.round(img.width || 0)}×${Math.round(img.height || 0)}`
})

// ====== 场景标记：选中后由右侧属性面板展示标记检视器 ======
/** 右栏当前页：绘制（颜色）/ 属性。标签常驻，切换只影响内容 */
const rightTab = ref<'paint' | 'props'>('props')

/** 右侧底部信息栏：描述当前最下方那块面板在做什么，避免和顶部 tab 名字重复 */
const rightInfoText = computed(() => {
  if (mapStore.activeMode === 'tile') return '碰撞编辑'
  return rightTab.value === 'paint' ? '绘制设置' : '地图设置'
})

/** 双击图钉：切回属性页、选中并把焦点交给属性面板的名称输入框 */
function onMarkerActivate(id: string) {
  rightTab.value = 'props'
  mapEditorStore.setSelectedMarkerId(id)
  nextTick(() => propertyPanelRef.value?.focusMarkerName())
}

/** 标记管理里双击 / 右键定位：把视口居中到该标记 */
function onFocusMarker(id: string) {
  mapCanvasRef.value?.centerMarker(id)
}

const mapCanvasRef = ref<InstanceType<typeof MapCanvas>>()
const layerPanelRef = ref<InstanceType<typeof LayerPanel>>()
const tileResourceBarRef = ref<{ uploadLocalTiles: () => void } | null>(null)
const propertyPanelRef = ref<InstanceType<typeof PropertyPanel>>()

// 切换图层 / 地图后把属性面板滚回顶部：否则会停留在上一层的滚动位置，看起来像空白
watch(
  () => [mapStore.activeLayerIndex, mapStore.activeMode, mapStore.mapLoadCount],
  () => {
    nextTick(() => {
      const el = propertyPanelRef.value?.$el as HTMLElement | undefined
      if (el) el.scrollTop = 0
    })
  },
)

/** 属性面板改写图像变换后：刷新画面并让变换框跟随新几何 */
function onImageTransformChanged() {
  mapStore.imageRevision++
  const img = mapStore.selectedImage
  if (img) mapCanvasRef.value?.showTransformBox(img)
}

// ====== 图片模式：直接在画布上绘制，颜色面板复用绘制页 ======
const mapPaint = useMapPaint()
// 图片图层且选用了绘制工具时，右栏默认停在颜色页；其它状态默认停在属性页
const isPainting = computed(() =>
  mapStore.activeMode === 'image' &&
  (mapEditorStore.paintMode === 'vector' || mapEditorStore.imageTool !== 'select')
)

// 随图层类型切到习惯的默认页：图片图层看颜色，图块等其它状态看属性
watch(
  isPainting,
  (painting) => {
    rightTab.value = painting ? 'paint' : 'props'
  },
  { immediate: true },
)

// 浮动画布工具条：撤销/重做按当前绘制模式取可用性
const canUndo = computed(() =>
  mapEditorStore.paintMode === 'vector'
    ? paintStore.vectorCanUndo
    : (mapCanvasRef.value?.canUndoPaint ?? false)
)
const canRedo = computed(() =>
  mapEditorStore.paintMode === 'vector'
    ? paintStore.vectorCanRedo
    : (mapCanvasRef.value?.canRedoPaint ?? false)
)

// 位图模式与全局绘制 store 对齐；矢量专属工具名切回位图时回退画笔
watch(
  () => mapEditorStore.paintMode,
  (mode) => {
    if (mode !== 'bitmap') return
    paintStore.setMode('bitmap')
    const t = mapEditorStore.imageTool
    if (t === 'reshape' || t === 'text' || t === 'eyedropper') {
      mapEditorStore.setImageTool('brush')
      paintStore.setTool('brush')
    }
  },
  { immediate: true }
)

// 绘制按钮/画笔工具：新建一张空白图片图层并启用指定工具
async function startImagePaint(tool: 'brush' | 'eraser' | 'fill' | 'line' | 'rect' | 'ellipse' | 'pen' | 'text' | 'reshape' | 'eyedropper' = 'brush') {
  const w = Math.max(1, mapStore.mapData.width * mapStore.mapData.tileSize)
  const h = Math.max(1, mapStore.mapData.height * mapStore.mapData.tileSize)
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/png'))
  if (!blob) return
  try {
    await mapPaint.saveMapImage(blob, w, h, mapStore.activeLayer?.id ?? -1, mapEditorStore.paintMode)
    mapEditorStore.setImageTool(tool)
    // 矢量专属工具需要矢量模式（新建图层后进入）；钢笔两种模式都支持
    if (tool === 'text' || tool === 'reshape' || tool === 'eyedropper') {
      mapEditorStore.setPaintMode('vector')
    }
  } catch (e) {
    console.error('[MapEditor] 创建绘制图层失败:', e)
  }
}

const emit = defineEmits<{
  // scope 决定内置资源库只显示图像还是图块：图层面板固定图像，图块面板固定图块
  'open-resource-lib': [scope: 'image' | 'tile']
  'open-map-library': []
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
  getThumbnailDataUrl: async () => (await mapCanvasRef.value?.getThumbnailDataUrl()) ?? null,
  onThumbnailUpdated: (itemId, dataUrl) => emit('map-thumbnail-updated', itemId, dataUrl),
})

// ====== 统一入口：currentMapPath 变化时自动保存当前 + 加载目标 ======
// 新建地图时设此标志跳过 watcher 的加载流程
let skipNextPathWatch = false
// 保存前先把矢量内容烘进当前图片像素，避免存档丢内容
async function flushVectorPaint() {
  await mapCanvasRef.value?.exitVectorPaint()
}

/** 空地图（无任何图层）默认创建一张空白图像图层，进入后可直接绘制 */
async function ensureDefaultLayer() {
  if (mapStore.mapData.layers.length > 0) return
  await startImagePaint('brush')
  await saveMapToProject()
}

watch(() => mapStore.currentMapPath, async (newPath, oldPath) => {
  if (!newPath || newPath === oldPath) return
  if (skipNextPathWatch) { skipNextPathWatch = false; return }
  if (!resourceStore.maps.find(m => m.id === newPath)) return

  if (oldPath) {
    // 根据 UUID 找到旧地图的名称，用名称路径保存（名称可能已被重命名）
    const oldItem = resourceStore.maps.find(m => m.id === oldPath)
    await flushVectorPaint()
    if (oldItem) await saveMapToProject(oldItem.name)
  }
  const loaded = await loadMapFromProject(newPath)
  // 无论加载成功或创建空地图，都确保 item.path 指向地图目录（供缩略图使用）
  const mapItem = resourceStore.maps.find(m => m.id === newPath)
  if (mapItem && projectStore.root) {
    mapItem.path = mapDirPath(mapItem.name)
  }
  let mapReady = loaded
  if (!loaded) {
    const item = resourceStore.maps.find(m => m.id === newPath)
    if (item) {
      mapStore.loadMap(createEmptyMapData(item.name))
      mapReady = true
    }
  }
  if (mapReady) await ensureDefaultLayer()
})

// ====== 自动保存（编辑时防抖保存到项目目录） ======
let autoSaveTimer: ReturnType<typeof setTimeout> | null = null
let savingItemId = ''
watch(() => JSON.stringify(mapStore.mapData), () => {
  if (autoSaveTimer) clearTimeout(autoSaveTimer)
  savingItemId = mapStore.currentMapPath
  autoSaveTimer = setTimeout(() => {
    if (mapStore.currentMapPath && mapStore.currentMapPath === savingItemId) {
      // 自动保存只写地图结构；矢量内容会在退出矢量模式/切图层时烘焙，避免打断编辑
      saveMapToProject()
    }
  }, 2000)
})

// 地图资源被清空（新建/打开项目、删除最后一张地图）时清掉编辑器内存残留：
// 否则空状态横幅下方仍会渲染上一个项目的场景，旧的自动保存还会把旧地图写回新项目目录
watch(hasMaps, (has) => {
  if (has) return
  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer)
    autoSaveTimer = null
  }
  savingItemId = ''
  mapStore.newMap()
}, { immediate: true })

// ====== 公开方法（供 MapToolbar 调用） ======

// 切换地图（MapToolbar dropdown 使用）：设 path → watcher 自动保存当前 + 加载目标
function switchToMap(itemId: string) {
  mapStore.setMapPath(itemId)
}

async function onNewMap() {
  if (mapStore.currentMapPath) {
    await flushVectorPaint()
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
  await ensureDefaultLayer()
}

async function onUploadLocal() {
  // 图块模式的本地上传直接打开系统窗口，选中的图片全部按图块处理
  if (mapStore.activeMode === 'tile') {
    tileResourceBarRef.value?.uploadLocalTiles()
    return
  }
  await onUploadImage()
}

/** 图片文件名去重：同名文件重复上传时不能覆盖地图已有素材（否则两层会串图） */
function uniqueImageFileName(fileName: string): string {
  const dot = fileName.lastIndexOf('.')
  const base = dot > 0 ? fileName.slice(0, dot) : fileName
  const ext = dot > 0 ? fileName.slice(dot) : ''
  const used = new Set(
    mapStore.mapData.resources.map(r => r.path.split('/').pop() || ''),
  )
  let name = fileName
  let seq = 2
  while (used.has(name)) name = `${base}-${seq++}${ext}`
  return name
}

async function onUploadImage() {
  const path = await invoke<string | null>('pick_image_file')
  if (!path) return
  const projectRoot = projectStore.root
  const mapName = mapStore.mapData.name
  if (!projectRoot || !mapName) return
  const fileName = uniqueImageFileName(path.split('/').pop() || 'resource.png')
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
        await flushVectorPaint()
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

function onOpenLibrary() {
  emit('open-resource-lib', 'tile')
}

/** 空地图横幅：打开内置地图库选择一张地图 */
function onChooseMap() {
  emit('open-map-library')
}

function onCursorMove(x: number, y: number) {
  mapEditorStore.setCursorPos(x, y)
}

function onSwitchPaintMode(mode: 'bitmap' | 'vector') {
  mapEditorStore.setPaintMode(mode)
}

/** 图块图层缩略图：只按该图层自身的瓦片数据合成 */
function getLayerThumbnail(layerId: number): string | null | Promise<string | null> {
  return mapCanvasRef.value?.getLayerThumbnailDataUrl(layerId) ?? null
}

/** 绘制过程中即时推送的单图层缩略图（只更新对应一条） */
function onLayerThumbUpdated(layerId: number, dataUrl: string) {
  layerPanelRef.value?.setLayerThumb(layerId, dataUrl)
}

defineExpose({ switchToMap, placeImageResource })
</script>

<template>
  <div class="map-editor-view">
    <div class="map-editor-body" :class="{ disabled: !hasMaps }">
      <div class="map-editor-left">
        <LayerPanel
          ref="layerPanelRef"
          :disabled="!hasMaps"
          :get-layer-thumbnail="getLayerThumbnail"
          @paint="startImagePaint"
          @open-library="emit('open-resource-lib', 'image')"
          @upload-image="onUploadLocal"
        />
      </div>
      <div class="map-editor-center">
        <div class="map-view">
          <MapToolbar
            :disabled="!hasMaps"
            @switch-map="switchToMap"
            @delete-selection="mapCanvasRef?.deleteActive()"
            @copy-selection="mapCanvasRef?.copyActive()"
            @paste-selection="mapCanvasRef?.pasteActive()"
            @flip-h="mapCanvasRef?.flipActive('h')"
            @flip-v="mapCanvasRef?.flipActive('v')"
            @group="mapCanvasRef?.groupActive()"
            @ungroup="mapCanvasRef?.ungroupActive()"
            @layer-up="mapCanvasRef?.layerUpActive()"
            @layer-down="mapCanvasRef?.layerDownActive()"
            @switch-paint-mode="onSwitchPaintMode"
            @create-paint-layer="startImagePaint"
            @resize-shape="(w, h) => mapCanvasRef?.resizeShapeSize(w, h)"
          />
          <div class="canvas-stage">
            <MapCanvas
              ref="mapCanvasRef"
              class="map-canvas-area"
              :class="{ disabled: !hasMaps }"
              @cursor-move="onCursorMove"
              @cursor-leave="mapEditorStore.setCursorPos(null, null)"
              @layer-thumb-updated="onLayerThumbUpdated"
              @marker-activate="onMarkerActivate"
            />
            <!-- 浮动视图工具条：撤销/重做/缩放（与角色绘制页一致） -->
            <div v-if="hasMaps" class="view-float-bar" @dblclick.stop>
              <button class="view-float-btn" v-tooltip="'缩小'" @click="mapCanvasRef?.zoomOut()">
                <img :src="iconZoomOut" width="16" height="16" draggable="false" />
              </button>
              <button class="view-float-zoom" v-tooltip="'重置缩放'" @click="mapCanvasRef?.resetZoom()">
                {{ mapCanvasRef?.zoomPercent ?? 100 }}%
              </button>
              <button class="view-float-btn" v-tooltip="'放大'" @click="mapCanvasRef?.zoomIn()">
                <img :src="iconZoomIn" width="16" height="16" draggable="false" />
              </button>
              <div class="view-float-divider"></div>
              <button
                class="view-float-btn"
                :disabled="!canUndo"
                v-tooltip="'撤销绘制'"
                @click="mapCanvasRef?.undoActive()"
              >
                <img :src="iconUndo" width="14" height="14" draggable="false" />
              </button>
              <button
                class="view-float-btn"
                :disabled="!canRedo"
                v-tooltip="'重做绘制'"
                @click="mapCanvasRef?.redoActive()"
              >
                <img :src="iconRedo" width="14" height="14" draggable="false" />
              </button>
            </div>
          </div>
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
            <span class="info-label">场景大小:{{ mapStore.mapData.width * mapStore.mapData.tileSize }}×{{ mapStore.mapData.height * mapStore.mapData.tileSize }}</span>
            <span v-if="mapStore.activeMode === 'image' && imageSizeText" class="info-label">{{ imageSizeText }}</span>
            <span class="info-label">坐标:{{ cursorCoordText }}</span>
            <span class="info-spacer" />
          </div>
        </div>
      </div>
      <div class="map-editor-right">
        <!-- 右侧面板常驻「绘制 / 属性」切换：任何工具状态下都显示，结构保持一致 -->
        <div class="right-tabs">
          <button class="right-tab" :class="{ 'right-tab-active': rightTab === 'paint' }" @click="rightTab = 'paint'">绘制</button>
          <button class="right-tab" :class="{ 'right-tab-active': rightTab === 'props' }" @click="rightTab = 'props'">属性</button>
        </div>
        <div class="right-body">
          <PaintColorPanel v-show="rightTab === 'paint'" />
          <PropertyPanel
            v-show="rightTab === 'props'"
            ref="propertyPanelRef"
            class="right-props"
            :disabled="!hasMaps"
            @transform-changed="onImageTransformChanged"
            @focus-marker="onFocusMarker"
          />
        </div>
        <!-- 图块模式的碰撞编辑器上移，底部保留与画布/图层一致的信息栏 -->
        <template v-if="mapStore.activeMode === 'tile'">
          <TileCollisionPanel
            :key="`${mapStore.currentMapPath}-${mapStore.activeLayer?.id ?? -1}`"
            class="right-collision"
          />
        </template>
        <!-- 底部信息栏常驻，和左侧「图层管理」、画布「坐标」保持同一结构 -->
        <div class="right-info-bar">
          <span class="right-info-text">{{ rightInfoText }}</span>
        </div>
      </div>
    </div>
    <div v-if="!hasMaps" class="map-empty-banner">
      <div class="empty-content">
        <img :src="iconMapLibrary" class="empty-icon" alt="" />
        <p class="empty-text">请先选择、绘制或上传地图</p>
        <div class="empty-actions">
          <button class="empty-btn" @click="onChooseMap">选择地图</button>
          <button class="empty-btn empty-btn-secondary" @click="onNewMap">绘制地图</button>
          <button class="empty-btn empty-btn-secondary" @click="onImportMap">上传地图</button>
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

.map-view {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.right-tabs {
  display: flex;
  height: 44px;
  flex-shrink: 0;
  border-bottom: 1px solid rgb(45, 45, 45);
}

.right-tab {
  flex: 1;
  background: transparent;
  border: none;
  color: #9ca0a4;
  font-size: 12px;
  cursor: default;
}

.right-tab-active {
  color: #fff;
  background: rgb(46, 49, 58);
}

/* 右栏内容区：绘制（颜色）与属性共用，常驻在标签栏下方 */
.right-body {
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

.right-body :deep(.color-panel) {
  width: 100%;
  height: 100%;
  border-left: none;
}

.right-body :deep(.property-panel) {
  flex: 1;
  overflow-y: auto;
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

.canvas-stage {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
}

.map-canvas-area {
  flex: 1;
  min-height: 0;
}

/* ─── 浮动视图工具条（画布右下；与角色绘制页 / 代码编辑器胶囊风格一致）─── */
.view-float-bar {
  position: absolute;
  bottom: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 0;
  background: rgba(30, 32, 40, 0.92);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 4px;
  z-index: 30;
}

.view-float-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 30px;
  height: 26px;
  padding: 0 6px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: default;
  transition: background 0.15s ease;
}

.view-float-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.08);
}

.view-float-btn:active:not(:disabled) {
  background: rgba(255, 255, 255, 0.12);
}

.view-float-btn:disabled {
  opacity: 0.35;
  cursor: default;
}

.view-float-zoom {
  min-width: 44px;
  height: 26px;
  padding: 0 4px;
  background: transparent;
  border: none;
  border-radius: 6px;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: default;
  white-space: nowrap;
  transition: color 0.15s, background 0.15s;
}

.view-float-zoom:hover {
  color: var(--text);
  background: rgba(255, 255, 255, 0.08);
}

.view-float-divider {
  width: 1px;
  height: 14px;
  background: rgba(255, 255, 255, 0.1);
  margin: 0 4px;
}



.map-info-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  gap: 20px;
  /* 比面板更深一档 + 一条细分隔线，保证是独立的一条信息栏 */
  background: rgb(26, 28, 33);
  border-top: 1px solid rgba(255, 255, 255, 0.07);
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
  overflow: hidden;
  border-left: 1px solid var(--border);
  background: var(--bg-root);
  position: relative;
  z-index: 20;
}

/* 属性区占满剩余高度并自行滚动，碰撞编辑区因此贴在右栏底部 */
.right-props {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
}

.right-collision {
  flex-shrink: 0;
}

/* 右栏底部信息栏：与画布 / 图层区域的信息栏同款 */
.right-info-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  flex-shrink: 0;
  /* 比面板更深一档 + 一条细分隔线，保证是独立的一条信息栏 */
  background: rgb(26, 28, 33);
  border-top: 1px solid rgba(255, 255, 255, 0.07);
}

.right-info-text {
  font-size: 12px;
  color: rgb(156, 160, 164);
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
  cursor: default;
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
