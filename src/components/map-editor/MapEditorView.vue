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
import iconCopy from '../../assets/icons/copy.svg'
import iconDelete from '../../assets/icons/选中删除.svg'
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
import { toUserX, toUserY, toWorldX, toWorldY } from '../../utils/coords'

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

// ====== 场景标记：选中后在图钉正下方弹出操作胶囊 ======
const selectedMarker = computed(() => mapStore.selectedMarker)
const markerNameInputRef = ref<HTMLInputElement>()
const markerMenuRef = ref<HTMLElement>()
// 胶囊实际宽度：用于贴边时水平内收，避免溢出画布
const markerMenuWidth = ref(0)
// 图钉到胶囊的间距：留出标签高度，避免遮挡
const MARKER_MENU_GAP = 30
const MARKER_MENU_HEIGHT = 34

/** 胶囊位置：默认贴在图钉正下方；下方空间不足时翻到图钉上方 */
const markerMenuPos = computed(() => {
  const id = mapEditorStore.selectedMarkerId
  if (!id) return null
  const canvas = mapCanvasRef.value
  const anchor = canvas?.markerScreenPos(id)
  if (!canvas || !anchor) return null
  const host = canvas.$el as HTMLElement
  const width = markerMenuWidth.value || 300
  const half = width / 2
  const minX = half + 10
  const maxX = Math.max(minX, host.clientWidth - half - 10)
  const left = Math.min(Math.max(anchor.x, minX), maxX)
  const belowTop = anchor.y + MARKER_MENU_GAP
  // 画布底部放不下就翻到图钉上方（图钉高 26px，再留 8px 呼吸）
  const flip = belowTop + MARKER_MENU_HEIGHT > host.clientHeight - 8
  const top = flip ? Math.max(8, anchor.y - 26 - 8 - MARKER_MENU_HEIGHT) : belowTop
  return { left, top, flip }
})

/** 胶囊内容变化后重新测量宽度（渲染完成后读取，保证钳制准确） */
watch(
  () => [mapEditorStore.selectedMarkerId, selectedMarker.value?.name],
  () => {
    markerMenuWidth.value = markerMenuRef.value?.offsetWidth ?? 0
  },
  { flush: 'post' },
)

/** 改名失焦/回车生效；空名或重名回填原名 */
function onMarkerNameChange(e: Event) {
  const marker = selectedMarker.value
  const el = e.target as HTMLInputElement
  if (!marker) return
  if (!mapStore.renameMarker(marker.id, el.value)) el.value = marker.name
}

/** 坐标输入：用户坐标 ↔ 世界坐标；空值或非数字回填当前值 */
function onMarkerCoordChange(axis: 'x' | 'y', e: Event) {
  const marker = selectedMarker.value
  const el = e.target as HTMLInputElement
  if (!marker) return
  const raw = el.value.trim()
  const value = Number(raw)
  if (!raw || !Number.isFinite(value)) {
    el.value = String(Math.round(axis === 'x' ? toUserX(marker.x) : toUserY(marker.y)))
    return
  }
  const user = Math.round(value)
  if (axis === 'x') mapStore.updateMarkerPosition(marker.id, toWorldX(user), marker.y)
  else mapStore.updateMarkerPosition(marker.id, marker.x, toWorldY(user))
  el.value = String(user)
}

function onMarkerXChange(e: Event) {
  onMarkerCoordChange('x', e)
}

function onMarkerYChange(e: Event) {
  onMarkerCoordChange('y', e)
}

/** 名称/坐标输入框按回车直接生效并退出编辑 */
function blurMarkerInput(e: KeyboardEvent) {
  (e.target as HTMLInputElement).blur()
}

/** 双击图钉：选中并直接把焦点放到胶囊的名称输入框 */
function onMarkerActivate(id: string) {
  mapEditorStore.setSelectedMarkerId(id)
  nextTick(() => {
    markerNameInputRef.value?.focus()
    markerNameInputRef.value?.select()
  })
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
const paintRightTab = ref<'paint' | 'props'>('paint')
// 选中绘制工具即进入绘制模式（画布本身不切换）
const isPainting = computed(() =>
  mapStore.activeMode === 'image' &&
  (mapEditorStore.paintMode === 'vector' || mapEditorStore.imageTool !== 'select')
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

            <!-- 标记操作胶囊：贴在选中图钉正下方，水平居中，完全圆角 -->
            <div
              v-if="hasMaps && selectedMarker && markerMenuPos"
              ref="markerMenuRef"
              class="marker-menu"
              :style="{
                left: `${markerMenuPos.left}px`,
                top: `${markerMenuPos.top}px`,
              }"
              @mousedown.stop
              @contextmenu.prevent
            >
              <input
                ref="markerNameInputRef"
                class="marker-name-input"
                :value="selectedMarker.name"
                maxlength="20"
                placeholder="标记名"
                @change="onMarkerNameChange"
                @keydown.enter="blurMarkerInput"
              />
              <div class="marker-coord-group">
                <span class="marker-axis">X</span>
                <input
                  class="marker-coord-input"
                  :value="Math.round(toUserX(selectedMarker.x))"
                  @change="onMarkerXChange"
                  @keydown.enter="blurMarkerInput"
                />
                <span class="marker-axis">Y</span>
                <input
                  class="marker-coord-input"
                  :value="Math.round(toUserY(selectedMarker.y))"
                  @change="onMarkerYChange"
                  @keydown.enter="blurMarkerInput"
                />
              </div>
              <div class="marker-menu-divider"></div>
              <button
                class="marker-float-btn"
                v-tooltip="'复制'"
                @click="mapStore.duplicateMarker(selectedMarker.id)"
              >
                <img :src="iconCopy" width="14" height="14" draggable="false" />
              </button>
              <button
                class="marker-float-btn marker-float-btn-danger"
                v-tooltip="'删除'"
                @click="mapStore.removeMarker(selectedMarker.id)"
              >
                <img :src="iconDelete" width="14" height="14" draggable="false" />
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
            <span class="info-label">坐标:{{ cursorCoordText }}</span>
            <span class="info-spacer" />
          </div>
        </div>
      </div>
      <div class="map-editor-right">
        <template v-if="isPainting">
          <div class="right-tabs">
            <button class="right-tab" :class="{ 'right-tab-active': paintRightTab === 'paint' }" @click="paintRightTab = 'paint'">绘制</button>
            <button class="right-tab" :class="{ 'right-tab-active': paintRightTab === 'props' }" @click="paintRightTab = 'props'">属性</button>
          </div>
          <div class="paint-right-body">
            <PaintColorPanel v-show="paintRightTab === 'paint'" />
            <PropertyPanel
              v-show="paintRightTab === 'props'"
              :disabled="!hasMaps"
              :show-header="false"
              @transform-changed="onImageTransformChanged"
            />
          </div>
        </template>
        <template v-else>
          <PropertyPanel
            ref="propertyPanelRef"
            class="right-props"
            :disabled="!hasMaps"
            @transform-changed="onImageTransformChanged"
          />
          <!-- 图块模式的碰撞编辑器上移，底部保留与画布/图层一致的信息栏 -->
          <TileCollisionPanel
            v-if="mapStore.activeMode === 'tile'"
            :key="`${mapStore.currentMapPath}-${mapStore.activeLayer?.id ?? -1}`"
            class="right-collision"
          />
          <div v-if="mapStore.activeMode === 'tile'" class="right-info-bar">
            <span class="right-info-text">碰撞编辑</span>
          </div>
        </template>
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

.paint-right-body {
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}

.paint-right-body :deep(.color-panel) {
  width: 100%;
  height: 100%;
  border-left: none;
}

.paint-right-body :deep(.property-panel) {
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

/* ─── 标记操作胶囊：贴在选中图钉正下方，水平居中 ─── */
.marker-menu {
  position: absolute;
  display: flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 6px;
  transform: translateX(-50%);
  background: rgba(30, 32, 40, 0.94);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 999px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
  white-space: nowrap;
  z-index: 30;
}

.marker-name-input {
  width: 100px;
  height: 24px;
  padding: 0 10px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid transparent;
  border-radius: 999px;
  color: var(--text);
  font-size: 12px;
  text-align: center;
  outline: none;
  transition: border-color 0.15s, background 0.15s;
}

.marker-name-input:focus {
  border-color: #5bfb84;
  background: rgba(0, 0, 0, 0.3);
}

/* X / Y 坐标：合并成一枚胶囊小分组，输入框无边框，聚焦时才显绿边 */
.marker-coord-group {
  display: flex;
  align-items: center;
  gap: 2px;
  height: 24px;
  padding: 0 8px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 999px;
}

.marker-axis {
  color: rgb(139, 143, 150);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.5px;
  user-select: none;
}

.marker-coord-input {
  width: 40px;
  height: 20px;
  padding: 0 2px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: var(--text);
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  text-align: center;
  outline: none;
  transition: background 0.15s;
}

.marker-coord-input:hover {
  background: rgba(255, 255, 255, 0.08);
}

.marker-coord-input:focus {
  background: rgba(0, 0, 0, 0.35);
  box-shadow: inset 0 0 0 1px #5bfb84;
}

.marker-menu-divider {
  width: 1px;
  height: 16px;
  background: rgba(255, 255, 255, 0.1);
  margin: 0 1px;
}

.marker-float-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  border-radius: 50%;
  cursor: default;
  opacity: 0.8;
  transition: background 0.15s, opacity 0.15s;
}

.marker-float-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  opacity: 1;
}

.marker-float-btn-danger:hover {
  background: rgba(224, 108, 108, 0.16);
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
  background: var(--bg-root);
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
