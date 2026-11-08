<script setup lang="ts">
import { ref, reactive, watch, computed, nextTick, onBeforeUnmount } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import MapToolbar from './MapToolbar.vue'
import MapCanvas from './MapCanvas.vue'
import iconZoomOut from '../../assets/icons/reduce-one.svg'
import iconZoomIn from '../../assets/icons/add-one.svg'
import iconUndo from '../../assets/icons/undo.svg'
import iconRedo from '../../assets/icons/redo.svg'
import iconMapLibrary from '../../assets/icons/图片库.svg'
import TileResourceBar from './TileResourceBar.vue'
import DrawingLayerTools from './DrawingLayerTools.vue'
import PropertyPanel from './PropertyPanel.vue'
import LayerPanel from './LayerPanel.vue'
import TileCollisionPanel from './TileCollisionPanel.vue'
import { useMapStore } from '../../stores/map'
import type { MapData, TilePaletteEntry } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import { useResourceStore } from '../../stores/resource'
import { useProjectStore } from '../../stores/project'
import { useMapPersistence } from '../../composables/useMapPersistence'
import JSZip from 'jszip'
import { deserializeMap } from '../../utils/mapSerializer'
import { toUserX, toUserY } from '../../utils/coords'
import { canFitTileSize } from '../../utils/tileAssetFit'

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()
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

// ====== 右栏分页：属性 + 图层类型的专属页（图块 = 图块，碰撞层 = 碰撞；图片图层只有属性） ======
type RightTab = 'props' | 'tile' | 'shape'

/**
 * 每种图层类型各自记住上次停留的分页。
 * 切图层、切地图都不重置——面板不自己动，用户停在哪页就一直在哪页（Photoshop / Godot 的停放面板习惯）。
 */
const rightTabByMode = reactive<Record<'image' | 'tile' | 'shape', RightTab>>({
  image: 'props',
  tile: 'props',
  shape: 'props',
})

/** 当前图层类型对应的分页（只读；切换统一走 setRightTab） */
const rightTab = computed(() => rightTabByMode[mapStore.activeMode])

/** 切分页：只改当前图层类型记住的那一格，不影响其它类型的记忆 */
function setRightTab(tab: RightTab) {
  rightTabByMode[mapStore.activeMode] = tab
}

/** 右侧底部信息栏：描述当前最下方那块面板在做什么，避免和顶部 tab 名字重复 */
const rightInfoText = computed(() => {
  if (rightTab.value === 'tile') return '图块设置'
  if (rightTab.value === 'shape') return '碰撞设置'
  return '地图设置'
})

/** 双击图钉：切回属性页、选中并把焦点交给属性面板的名称输入框 */
function onMarkerActivate(id: string) {
  setRightTab('props')
  mapEditorStore.setSelectedMarkerId(id)
  nextTick(() => propertyPanelRef.value?.focusMarkerName())
}

/** 标记管理里双击 / 右键定位：把视口居中到该标记 */
function onFocusMarker(id: string) {
  mapCanvasRef.value?.centerMarker(id)
}

/** 形状列表里双击定位：把视口居中到该形状 */
function onFocusShape(id: string) {
  mapCanvasRef.value?.centerShape(id)
}

const mapCanvasRef = ref<InstanceType<typeof MapCanvas>>()
const layerPanelRef = ref<InstanceType<typeof LayerPanel>>()
const tileResourceBarRef = ref<{
  uploadLocalTiles: () => void
  requestCenterPaletteView: () => void
} | null>(null)
const propertyPanelRef = ref<InstanceType<typeof PropertyPanel>>()

// ====== 画布下方图块工作区：可拖拽高度 ======
/** 工作区高度：默认约为原来的 2/3，拖动顶部横条可调整 */
const tileWorkspaceHeight = ref(204)
const TILE_WORKSPACE_MIN_HEIGHT = 140
const TILE_WORKSPACE_MAX_HEIGHT = 620
let resizingTileWorkspace = false
let resizeStartY = 0
let resizeStartHeight = 0

function onTileWorkspaceResizeStart(e: PointerEvent) {
  if (e.button !== 0) return
  e.preventDefault()
  resizingTileWorkspace = true
  resizeStartY = e.clientY
  resizeStartHeight = tileWorkspaceHeight.value
  document.body.style.cursor = 'row-resize'
  window.addEventListener('pointermove', onTileWorkspaceResizeMove)
  window.addEventListener('pointerup', onTileWorkspaceResizeEnd)
}

function onTileWorkspaceResizeMove(e: PointerEvent) {
  if (!resizingTileWorkspace) return
  const next = resizeStartHeight + (resizeStartY - e.clientY)
  tileWorkspaceHeight.value = Math.min(
    TILE_WORKSPACE_MAX_HEIGHT,
    Math.max(TILE_WORKSPACE_MIN_HEIGHT, Math.round(next)),
  )
}

function onTileWorkspaceResizeEnd() {
  if (!resizingTileWorkspace) return
  resizingTileWorkspace = false
  document.body.style.cursor = ''
  window.removeEventListener('pointermove', onTileWorkspaceResizeMove)
  window.removeEventListener('pointerup', onTileWorkspaceResizeEnd)
}

onBeforeUnmount(() => {
  onTileWorkspaceResizeEnd()
  cancelAutoSave()
})

// 切换图层 / 地图 / 右栏分页后把属性面板滚回顶部：否则会停留在上一页的滚动位置，看起来像空白
watch(
  () => [mapStore.activeLayerIndex, mapStore.activeMode, mapStore.mapLoadCount, rightTab.value],
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

// 形状层：选中 / 新建形状后自动切到「形状」页（选择集合每次变更都会触发，重复点同一个形状也算）
watch(
  () => mapEditorStore.activeShapeIds,
  (ids) => {
    if (ids.length && mapStore.activeMode === 'shape') setRightTab('shape')
  },
)

// 浮动画布工具条：撤销/重做只服务图块层（图片的像素编辑已迁到绘制页）
const canUndo = computed(() => (mapStore.activeMode === 'tile' ? mapStore.canUndoTile : false))
const canRedo = computed(() => (mapStore.activeMode === 'tile' ? mapStore.canRedoTile : false))

/** 「绘制图层」按钮：新建空白画板并跳转绘制页（保存后自动插入图层） */
function requestPaintLayer() {
  if (!mapStore.currentMapPath) return
  const w = Math.max(1, mapStore.mapData.width * mapStore.mapData.tileSize)
  const h = Math.max(1, mapStore.mapData.height * mapStore.mapData.tileSize)
  emit('open-paint-image', {
    imagePath: '',
    width: w,
    height: h,
    insertIndex: mapStore.activeLayerIndex,
  })
}

/** 双击图像图层 / 「编辑图像」：再次进入绘制页修改该素材 */
function onEditImageLayer(layerId?: number) {
  const layer = layerId != undefined
    ? mapStore.mapData.layers.find(l => l.id === layerId)
    : mapStore.activeLayer
  if (!layer || layer.type !== 'image') return
  emit('open-paint-image', {
    imagePath: layer.image.imagePath,
    width: layer.image.width || 1,
    height: layer.image.height || 1,
    insertIndex: -1,
  })
}

const emit = defineEmits<{
  // scope 决定内置资源库只显示图像还是图块：图层面板固定图像，图块面板固定图块
  'open-resource-lib': [scope: 'image' | 'tile']
  'open-map-library': []
  'map-thumbnail-updated': [itemId: string, dataUrl: string]
  /** 退出绘制测试：回到素材整理页 */
  'tile-test-exit': []
  /** 进入绘制页：imagePath 为空 = 新建空白图像图层；非空 = 再次编辑这张图片 */
  'open-paint-image': [req: { imagePath: string; width: number; height: number; insertIndex: number }]
}>()

// ====== 持久化：map.json 读写、.bgm 修复、路径解析 ======
const {
  mapDirPath,
  saveMapToProject: persistMap,
  loadMapFromProject,
  resolveRelativePaths,
  createEmptyMapData,
} = useMapPersistence({
  getThumbnailDataUrl: async () => (await mapCanvasRef.value?.getThumbnailDataUrl()) ?? null,
  onThumbnailUpdated: (itemId, dataUrl) => emit('map-thumbnail-updated', itemId, dataUrl),
})

// ====== 自动保存：脏标记 + 防抖 + 空闲执行 ======
// 行业做法（Unreal / Godot / Blender）：编辑时只打脏标记，用定时器在空闲时保存；
// 不在每次数据变化时序列化整张地图。这里监听 store 的廉价 mapDataRevision。
let autoSaveTimer: ReturnType<typeof setTimeout> | null = null
let autoSaveIdleHandle: number | null = null
/** 地图刚加载完的短暂窗口内不立刻触发自动保存 */
let autoSaveSuppressUntil = 0
/** 最近一次成功保存时的数据签名：没变就跳过，避免打开地图后立刻无意义回写 */
let lastSavedSignal = ''

/** 廉价数据签名（只拼计数器，不做任何序列化） */
function dataSignal() {
  return [
    mapStore.mapDataRevision,
    mapStore.tileRevision,
    mapStore.imageRevision,
    mapStore.shapeRevision,
  ].join(':')
}

function cancelAutoSave() {
  if (autoSaveTimer) {
    clearTimeout(autoSaveTimer)
    autoSaveTimer = null
  }
  if (autoSaveIdleHandle != null) {
    const cancelIdle = (window as any).cancelIdleCallback as ((handle: number) => void) | undefined
    if (cancelIdle) cancelIdle(autoSaveIdleHandle)
    autoSaveIdleHandle = null
  }
}

/** 统一保存入口：先取消待执行的自动保存，避免同一次改动重复写盘 */
async function saveMapToProject(mapName?: string) {
  cancelAutoSave()
  // 先记下本次保存覆盖的数据版本；保存期间新产生的修改不应被视为已保存
  const savedSignal = dataSignal()
  await persistMap(mapName)
  lastSavedSignal = savedSignal
}

function runAutoSave() {
  autoSaveIdleHandle = null
  // 绘制测试只有内存数据，任何情况都不写盘
  if (tileTestMode.value || !mapStore.currentMapPath) return
  // 地图已从素材列表删除（目录也一起删了）时绝不能再写回：
  // 否则会凭空造出一份只有 map.json + 缩略图、绘制图片全丢的空壳地图
  if (!resourceStore.maps.some(m => m.id === mapStore.currentMapPath)) return
  // 数据没变（例如刚打开地图、载入过程顺带 bump 了计数器）就跳过
  const signal = dataSignal()
  if (signal === lastSavedSignal) return
  lastSavedSignal = signal
  // 自动保存只写地图结构；矢量内容会在切图层 / 退出矢量模式时烘焙，避免打断编辑
  void persistMap()
}

function scheduleAutoSave() {
  if (!mapStore.currentMapPath) return
  if (autoSaveTimer) clearTimeout(autoSaveTimer)
  autoSaveTimer = setTimeout(() => {
    autoSaveTimer = null
    // 放到浏览器空闲时段做序列化 + 写盘，尽量不打断用户操作
    const requestIdle = (window as any).requestIdleCallback as
      | ((cb: () => void, opts?: { timeout: number }) => number)
      | undefined
    if (requestIdle) autoSaveIdleHandle = requestIdle(runAutoSave, { timeout: 4000 })
    else runAutoSave()
    // 加载地图后的短时间窗口内不立刻回写（避免刚打开就产生一次无意义保存）
  }, Math.max(1500, autoSaveSuppressUntil - Date.now() + 200))
}

// 脏标记 + 画布/图片/形状的廉价计数器都视为“需要保存”
watch(
  () => [mapStore.mapDataRevision, mapStore.tileRevision, mapStore.imageRevision, mapStore.shapeRevision],
  scheduleAutoSave,
)

// ====== 统一入口：currentMapPath 变化时自动保存当前 + 加载目标 ======
// 新建地图时设此标志跳过 watcher 的加载流程
let skipNextPathWatch = false

/** 空地图（无任何图层）默认创建一张空白图块图层，进入后可直接画图块 */
async function ensureDefaultLayer() {
  if (mapStore.mapData.layers.length > 0) return
  mapStore.addLayer('图块图层')
  await saveMapToProject()
}

watch(() => mapStore.currentMapPath, async (newPath, oldPath) => {
  if (!newPath || newPath === oldPath) return
  if (skipNextPathWatch) { skipNextPathWatch = false; return }
  if (!resourceStore.maps.find(m => m.id === newPath)) return
  // 加载/切换地图期间产生的 revision 变化不应立刻回写
  autoSaveSuppressUntil = Date.now() + 1500

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
  let mapReady = loaded
  if (!loaded) {
    const item = resourceStore.maps.find(m => m.id === newPath)
    if (item) {
      mapStore.loadMap(createEmptyMapData(item.name))
      mapReady = true
    }
  }
  if (mapReady) await ensureDefaultLayer()
  // 载入流程本身会 bump 各 revision，这里把签名对齐，避免刚打开就触发一次自动保存
  lastSavedSignal = dataSignal()
})

// 地图资源被清空（新建/打开项目、删除最后一张地图）时清掉编辑器内存残留：
// 否则空状态横幅下方仍会渲染上一个项目的场景，旧的自动保存还会把旧地图写回新项目目录
watch(hasMaps, (has) => {
  if (has) return
  cancelAutoSave()
  mapStore.newMap()
}, { immediate: true })

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

/** 图块图层缩略图：只按该图层自身的瓦片数据合成 */
function getLayerThumbnail(layerId: number): string | null | Promise<string | null> {
  return mapCanvasRef.value?.getLayerThumbnailDataUrl(layerId) ?? null
}

/** 绘制过程中即时推送的单图层缩略图（只更新对应一条） */
function onLayerThumbUpdated(layerId: number, dataUrl: string) {
  layerPanelRef.value?.setLayerThumb(layerId, dataUrl)
}

// ====== 图像图层：常规变换（复制 / 旋转 / 镜像） ======
/** 复制当前图像图层：连同图片文件一起复制，避免两个图层共用同一张素材 */
async function onCopyImageLayer() {
  const layer = mapStore.activeLayer
  const projectRoot = projectStore.root
  if (!layer || layer.type !== 'image' || !projectRoot) return
  const img = layer.image
  const mapName = mapStore.mapData.name || '未命名地图'
  const fileName = img.imagePath.split('/').pop() || 'image.png'
  const dot = fileName.lastIndexOf('.')
  const base = dot > 0 ? fileName.slice(0, dot) : fileName
  const ext = dot > 0 ? fileName.slice(dot) : '.png'
  const used = new Set(mapStore.mapData.resources.map(r => r.path.split('/').pop() || ''))
  let name = `${base}-副本`
  let seq = 2
  while (used.has(`${name}${ext}`)) name = `${base}-副本${seq++}`
  const relPath = `assets/maps/${mapName}/images/${name}${ext}`
  try {
    const data = await invoke<number[]>('read_binary', { path: `${projectRoot}/${img.imagePath}` })
    await invoke('write_binary', { path: `${projectRoot}/${relPath}`, data })
  } catch (e) {
    console.error('[MapEditor] 复制图片失败:', e)
    return
  }
  mapStore.addResource({
    name,
    path: relPath,
    resourceType: 'image',
    tileWidth: img.width,
    tileHeight: img.height,
    collisionType: '图像',
    collisionEnabled: false,
  })
  // 偏移少许，复制后两层不会完全重叠在一起
  mapStore.addImageAt(mapStore.activeLayerIndex, {
    ...img,
    imagePath: relPath,
    position: [img.position[0] + 16, img.position[1] + 16],
  }, `${layer.name} 副本`)
}

/** 水平 / 垂直镜像：直接翻转图片像素并覆盖原素材 */
async function onFlipImageLayer(axis: 'h' | 'v') {
  const img = mapStore.selectedImage
  const projectRoot = projectStore.root
  if (!img || !projectRoot) return
  try {
    const src = await invoke<string>('read_image_as_data_url', { path: `${projectRoot}/${img.imagePath}` })
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image()
      el.onload = () => resolve(el)
      el.onerror = reject
      el.src = src
    })
    const canvas = document.createElement('canvas')
    canvas.width = image.naturalWidth
    canvas.height = image.naturalHeight
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    if (axis === 'h') {
      ctx.translate(canvas.width, 0)
      ctx.scale(-1, 1)
    } else {
      ctx.translate(0, canvas.height)
      ctx.scale(1, -1)
    }
    ctx.drawImage(image, 0, 0)
    const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/png'))
    if (!blob) return
    const bytes = Array.from(new Uint8Array(await blob.arrayBuffer()))
    await invoke('write_binary', { path: `${projectRoot}/${img.imagePath}`, data: bytes })
    mapCanvasRef.value?.reloadImages()
  } catch (e) {
    console.error('[MapEditor] 镜像图片失败:', e)
  }
}

// ====== 绘制测试（dev 素材整理页调用）：临时地图，绝不落盘 ======
interface TileTestItem {
  /** 素材路径（如 /maps/tiles/砖块/草地.png），直接交给图块渲染 */
  path: string
  name: string
  /** tile=单张图块；tileset=多格图集（按测试地图格子切） */
  assetKind?: 'tile' | 'tileset'
  /** 图集在素材库里设定的每格边长；有值时按它切，不再按测试格子猜 */
  tileSize?: number
}

const tileTestMode = ref(false)
/** 进入测试前的真实地图快照（含未落盘的改动），退出时原样还原 */
let tileTestBackup: {
  mapData: MapData
  mapPath: string
  viewCenter: { x: number; y: number } | null
} | null = null

/** 加载测试素材图片：/maps/** 是引擎素材库路径，走数据 URL 读 */
async function loadTestImage(path: string): Promise<HTMLImageElement> {
  let url = path
  if (path.startsWith('/maps/')) {
    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')
      url = await invoke<string>('read_image_as_data_url', { path: `${engineDir}${path}` })
    } catch {
      url = path
    }
  }
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error(`加载图片失败: ${path}`))
    img.src = url
  })
}

/** 单图块尺寸和测试格子不一致时，在内存里按最近邻缩放到格子尺寸（不写任何文件） */
function fitTileToGrid(img: HTMLImageElement, size: number): string {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  if (!ctx) return img.src
  ctx.imageSmoothingEnabled = false
  ctx.drawImage(img, 0, 0, img.naturalWidth, img.naturalHeight, 0, 0, size, size)
  return canvas.toDataURL('image/png')
}

/**
 * 图集每格尺寸和测试格子不一致时，整张图在内存里按最近邻归一化（不写文件）。
 * 整数倍整图缩放；非整数倍逐块缩放，保证每块都正好落在格子里。
 */
function fitSheetToGrid(img: HTMLImageElement, native: number, size: number): string {
  const cols = Math.floor(img.naturalWidth / native)
  const rows = Math.floor(img.naturalHeight / native)
  if (cols <= 0 || rows <= 0) return img.src
  const width = cols * size
  const height = rows * size
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) return img.src
  ctx.imageSmoothingEnabled = false
  if (canFitTileSize(native, size)) {
    ctx.drawImage(img, 0, 0, cols * native, rows * native, 0, 0, width, height)
  } else {
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        ctx.drawImage(
          img,
          c * native, r * native, native, native,
          c * size, r * size, size, size,
        )
      }
    }
  }
  return canvas.toDataURL('image/png')
}

/** 从素材整理页进入绘制测试：用选中素材拼一张纯内存地图，画完直接退出 */
async function startTileTest(items: TileTestItem[]) {
  if (items.length === 0) return
  // 已经在测试中（再点一次）：先退出还原，再重新进入，保证快照不被覆盖成测试数据
  if (tileTestMode.value) exitTileTest(false)
  else {
    // 取消可能还在排队中的自动保存：否则它会拿着测试地图的数据写盘
    cancelAutoSave()
    tileTestBackup = {
      mapData: JSON.parse(JSON.stringify(mapStore.mapData)),
      mapPath: mapStore.currentMapPath,
      // 记住原地图视角，退出测试时还原，不要让用户重新找位置
      viewCenter: mapCanvasRef.value?.getViewCenter() ?? null,
    }
  }

  // 先一次性读入所有图片，后续统一按测试格子归一化（全程只在内存里，不写文件）
  const images = await Promise.all(items.map(item => loadTestImage(item.path).catch(() => null)))
  const sizes = images.map(img => (img
    ? { w: img.naturalWidth, h: img.naturalHeight }
    : { w: mapStore.mapData.tileSize, h: mapStore.mapData.tileSize }))
  /** 取出现次数最多的尺寸（并列时取先出现的） */
  function mostFrequent(values: number[]): number {
    const freq = new Map<number, number>()
    for (const v of values) freq.set(v, (freq.get(v) ?? 0) + 1)
    let best = 0
    let bestCount = 0
    for (const [v, count] of freq) {
      if (count > bestCount) {
        best = v
        bestCount = count
      }
    }
    return best
  }

  // 格子尺寸优先采用素材库里为图集设定好的尺寸；没设定过的图集按默认 16
  const configuredSizes = items
    .filter(it => it.assetKind === 'tileset')
    .map(it => (it.tileSize && it.tileSize > 0 ? Math.round(it.tileSize) : 16))
  const singleSizes = sizes
    .filter((_, i) => items[i].assetKind !== 'tileset')
    .map(s => s.w)
  let tileSize = configuredSizes.length ? mostFrequent(configuredSizes) : mostFrequent(singleSizes)
  // 只选了未设定尺寸的图集：按常见图块尺寸找一个能整除整张图集的
  if (!tileSize) {
    const sheets = sizes.filter((_, i) => items[i].assetKind === 'tileset')
    tileSize = [16, 32, 8].find(n => sheets.every(s => s.w % n === 0 && s.h % n === 0)) ?? 16
  }
  tileSize = Math.max(8, Math.round(tileSize))

  const data = createEmptyMapData('绘制测试')
  data.width = 32
  data.height = 24
  data.tileSize = tileSize
  data.tileSizeExplicit = true

  const groupId = 'test-tiles'
  data.tilesetGroups = [{ id: groupId, name: '测试素材' }]

  const palette: TilePaletteEntry[] = []
  let firstgid = 1
  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    const id = `test-res-${i}`
    const kind: 'tile' | 'tileset' = item.assetKind === 'tileset' ? 'tileset' : 'tile'
    const size = sizes[i] ?? { w: tileSize, h: tileSize }
    // 单图块：尺寸和格子不一致时按最近邻缩放到格子（内存 data URL），切块恒为一格；
    // 图集：设定了图块尺寸就按设定值切，未设定才按测试地图的格子切
    let srcPath = item.path
    let cutW = tileSize
    let cutH = tileSize
    // 图集按格子缩放后的整图尺寸（调色板按它算块数）
    let sheetW = size.w
    let sheetH = size.h
    if (kind === 'tile') {
      const img = images[i]
      if (img && (size.w !== tileSize || size.h !== tileSize)) {
        srcPath = fitTileToGrid(img, tileSize)
      }
    } else {
      // 未设定尺寸的图集按默认 16 切（与素材库导入保持一致）
      const native = item.tileSize && item.tileSize > 0 ? Math.round(item.tileSize) : 16
      const img = images[i]
      // 和测试格子不一致：一律归一化到格子（整数倍整图缩放，非整数倍逐块缩放）
      if (native && native !== tileSize && img) {
        srcPath = fitSheetToGrid(img, native, tileSize)
        sheetW = Math.floor(size.w / native) * tileSize
        sheetH = Math.floor(size.h / native) * tileSize
      }
    }
    data.resources.push({
      id,
      firstgid,
      name: item.name,
      path: srcPath,
      resourceType: kind,
      tileWidth: cutW,
      tileHeight: cutH,
      collisionType: '图像',
      collisionEnabled: false,
      groupId,
      assetKind: kind,
      ...(kind === 'tile' ? { nativeTileSize: size.w } : item.tileSize ? { nativeTileSize: item.tileSize } : {}),
    })
    data.tileSets.push({
      id,
      name: item.name,
      imagePath: srcPath,
      resourceType: kind,
      tileWidth: cutW,
      tileHeight: cutH,
      firstgid,
      collisionType: '图像',
      collisionEnabled: false,
      tiles: [],
    })
    firstgid += 10000

    if (kind === 'tileset') {
      // 图集按实际切片尺寸计块数：整张图集的前 128 块都放进调色板
      const cols = Math.max(1, Math.floor(sheetW / cutW))
      const rows = Math.max(1, Math.floor(sheetH / cutH))
      const count = Math.min(cols * rows, 128)
      for (let idx = 0; idx < count; idx++) palette.push({ resourceId: id, tileIndex: idx })
    } else {
      palette.push({ resourceId: id, tileIndex: 0 })
    }
  }
  data.tilePalette = palette
  data.layers = [{ id: 0, name: '图块', type: 'drawing', visible: true, locked: false, tiles: {}, groupId }]

  // path 置空：自动保存只在有 path 时触发，这样怎么画都不会写任何文件
  mapStore.setMapPath('')
  mapStore.loadMap(data)
  // loadMap 里的 migrateLayerTilesets 会自动选中调色板第一项，
  // 测试模式下不该有默认选中：用户没主动选，画布上乱点就会画出一块「意外」的砖
  mapStore.selectedResourceIndex = -1
  mapStore.selectedTileIndex = -1
  mapStore.selectedTileEntryKey = ''
  tileTestMode.value = true
  // 等提示条撑开、画布重新布局后再把测试地图居中，避免停在左上角。
  // 容器尺寸由 ResizeObserver 更新，可能晚于一帧，再补一次居中（幂等）
  await nextTick()
  requestAnimationFrame(() => {
    mapCanvasRef.value?.centerMap()
    // 调色板里的图块也居中显示（异步布局就绪后由组件内部补一次）
    tileResourceBarRef.value?.requestCenterPaletteView()
    setTimeout(() => mapCanvasRef.value?.centerMap(), 60)
    // 图块工作区若是刚挂载出来，组件实例可能晚一拍才就绪
    setTimeout(() => tileResourceBarRef.value?.requestCenterPaletteView(), 200)
  })
}

/** 退出绘制测试：丢弃测试地图，还原进入前的真实地图（含未保存的改动） */
function exitTileTest(notify = true) {
  if (!tileTestMode.value) return
  tileTestMode.value = false
  const backup = tileTestBackup
  tileTestBackup = null
  if (!backup) return
  // 只有恢复到非空路径时才需要跳过路径监听（空路径本来就不会触发加载）
  skipNextPathWatch = backup.mapPath !== ''
  mapStore.setMapPath(backup.mapPath)
  mapStore.loadMap(backup.mapData)
  // 还原过程 bump 了 revision：对齐签名，避免立刻把同一份数据再写一次盘
  lastSavedSignal = dataSignal()
  // 视角也还原：回到进入测试前看的位置
  if (backup.viewCenter) {
    mapCanvasRef.value?.centerOnWorld(backup.viewCenter.x, backup.viewCenter.y)
  }
  // 退出后回到素材整理页继续处理素材（重新进入测试时不需要切页）
  if (notify) emit('tile-test-exit')
}

defineExpose({
  switchToMap,
  placeImageResource,
  startTileTest,
  /** 绘制页覆盖保存后：清缓存并重建图像图层（转发到画布） */
  reloadImages: () => mapCanvasRef.value?.reloadImages(),
  /** 绘制页保存返回后：强制刷新一帧，保证新图层立即可见 */
  renderNow: () => mapCanvasRef.value?.renderNow(),
  /** 绘制页改过画布尺寸返回后：选中图片的变换框按最新宽高重建 */
  refreshTransformBox: () => mapCanvasRef.value?.refreshTransformBox(),
})
</script>

<template>
  <div class="map-editor-view">
    <div class="map-editor-body" :class="{ disabled: !hasMaps && !tileTestMode }">
      <div v-if="!tileTestMode" class="map-editor-left">
        <LayerPanel
          ref="layerPanelRef"
          :disabled="!hasMaps"
          :get-layer-thumbnail="getLayerThumbnail"
          @paint="requestPaintLayer"
          @edit-image="onEditImageLayer"
          @open-library="emit('open-resource-lib', 'image')"
          @upload-image="onUploadLocal"
        />
      </div>
      <div class="map-editor-center">
        <div class="map-view">
          <!-- 测试模式：顶部工具条（画笔 / 直线 / 矩形 / 擦除），不落盘 -->
          <div v-if="tileTestMode" class="tile-test-bar">
            <span class="tile-test-title">绘制测试</span>
            <span class="tile-test-sep" />
            <div class="tile-test-tools">
              <DrawingLayerTools />
            </div>
            <div class="tile-test-spacer" />
            <button class="tile-test-exit" @click="exitTileTest()">退出测试</button>
          </div>
          <MapToolbar
            v-if="!tileTestMode"
            :disabled="!hasMaps"
            @switch-map="switchToMap"
            @copy-image-layer="onCopyImageLayer"
            @flip-image-h="onFlipImageLayer('h')"
            @flip-image-v="onFlipImageLayer('v')"
            @edit-image="onEditImageLayer()"
          />
          <div class="canvas-stage">
            <MapCanvas
              ref="mapCanvasRef"
              class="map-canvas-area"
              :class="{ disabled: !hasMaps && !tileTestMode }"
              @cursor-move="onCursorMove"
              @cursor-leave="mapEditorStore.setCursorPos(null, null)"
              @layer-thumb-updated="onLayerThumbUpdated"
              @marker-activate="onMarkerActivate"
            />
            <!-- 浮动视图工具条：撤销/重做/缩放（与角色绘制页一致） -->
            <div v-if="hasMaps || tileTestMode" class="view-float-bar" @dblclick.stop>
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
          <!-- 图块模式：画布下方的图块工作区（左调色板 / 右碰撞预览，高度可拖拽） -->
          <div
            v-if="mapStore.activeMode === 'tile'"
            class="tile-workspace"
            :style="{ height: `${tileWorkspaceHeight}px` }"
          >
            <div
              class="tile-workspace-resizer"
              v-tooltip="'拖动调整高度'"
              @pointerdown="onTileWorkspaceResizeStart"
            />
            <div class="tile-workspace-body">
              <div class="tile-workspace-palette">
                <TileResourceBar
                  ref="tileResourceBarRef"
                  :disabled="!hasMaps && !tileTestMode"
                  @open-library="onOpenLibrary"
                  @select-tile="(rIdx, tIdx, entry) => mapStore.selectTile(rIdx, tIdx, entry)"
                />
              </div>
              <div class="tile-workspace-collision">
                <TileCollisionPanel
                  :key="`${mapStore.currentMapPath}-${mapStore.activeLayer?.id ?? -1}`"
                />
              </div>
            </div>
          </div>
          <div class="map-info-bar">
            <span class="info-spacer" />
            <span class="info-label">场景大小:{{ mapStore.mapData.width * mapStore.mapData.tileSize }}×{{ mapStore.mapData.height * mapStore.mapData.tileSize }}</span>
            <span v-if="mapStore.activeMode === 'image' && imageSizeText" class="info-label">{{ imageSizeText }}</span>
            <span class="info-label">坐标:{{ cursorCoordText }}</span>
            <span v-if="mapEditorStore.hintMessage" class="info-warn">{{ mapEditorStore.hintMessage }}</span>
            <span class="info-spacer" />
          </div>
        </div>
      </div>
      <div v-if="!tileTestMode" class="map-editor-right">
        <!-- 右侧面板分页：属性常驻；第二页跟着图层类型走（图块=图块，碰撞层=碰撞） -->
        <div class="right-tabs">
          <button class="right-tab" :class="{ 'right-tab-active': rightTab === 'props' }" @click="setRightTab('props')">属性</button>
          <button
            v-if="mapStore.activeMode === 'shape'"
            class="right-tab"
            :class="{ 'right-tab-active': rightTab === 'shape' }"
            @click="setRightTab('shape')"
          >碰撞</button>
          <button
            v-else-if="mapStore.activeMode === 'tile'"
            class="right-tab"
            :class="{ 'right-tab-active': rightTab === 'tile' }"
            @click="setRightTab('tile')"
          >图块</button>
        </div>
        <div class="right-body">
          <PropertyPanel
            ref="propertyPanelRef"
            class="right-props"
            :disabled="!hasMaps"
            :shape-page="rightTab === 'shape'"
            :tile-page="rightTab === 'tile'"
            @transform-changed="onImageTransformChanged"
            @focus-marker="onFocusMarker"
            @focus-shape="onFocusShape"
            @new-tileset-group="mapStore.addTilesetGroupToActiveLayer()"
          />
        </div>
        <!-- 底部信息栏常驻，和左侧「图层管理」、画布「坐标」保持同一结构 -->
        <div class="right-info-bar">
          <span class="right-info-text">{{ rightInfoText }}</span>
        </div>
      </div>
    </div>
    <div v-if="!hasMaps && !tileTestMode" class="map-empty-banner">
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

/* 绘制测试工具条：画笔 / 直线 / 矩形 / 擦除，画完直接退出 */
.tile-test-bar {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  height: 38px;
  padding: 0 8px;
  background: var(--bg-base);
  border-bottom: 1px solid var(--border-light);
}

.tile-test-title {
  font-size: 12px;
  color: var(--accent);
}

.tile-test-sep {
  width: 1px;
  height: 18px;
  background: var(--border-light);
  flex-shrink: 0;
}

.tile-test-tools {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tile-test-spacer {
  flex: 1;
}

.tile-test-exit {
  height: 22px;
  padding: 0 10px;
  background: var(--bg-hover);
  border: 1px solid var(--border-light);
  border-radius: 3px;
  color: var(--text);
  font-size: 12px;
  cursor: default;
}

.tile-test-exit:hover {
  background: var(--bg-active);
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

/* 画布下方的图块工作区：左调色板 + 右碰撞预览，顶部两排工具栏拼成一条顶栏 */
.tile-workspace {
  position: relative;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  min-height: 0;
  border-top: 1px solid var(--border);
  background: var(--bg-root);
}

/* 拖拽条：压在上边界上，不占布局高度（否则会多出一条空带） */
.tile-workspace-resizer {
  position: absolute;
  top: -3px;
  left: 0;
  right: 0;
  height: 6px;
  z-index: 10;
  cursor: row-resize;
}

.tile-workspace-resizer::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 2px;
  height: 2px;
  background: transparent;
  transition: background 0.12s;
}

.tile-workspace-resizer:hover::before {
  background: rgba(255, 255, 255, 0.12);
}

.tile-workspace-body {
  flex: 1;
  min-height: 0;
  display: flex;
}

.tile-workspace-palette {
  flex: 1;
  min-width: 0;
  display: flex;
}

.tile-workspace-palette :deep(.tile-resource-bar) {
  flex: 1 1 auto;
  min-width: 0;
  height: auto;
  border-top: none;
}

/* 调色板工具栏与碰撞工具栏对齐成同一条顶栏：与顶部工具栏同高 44px */
.tile-workspace-palette :deep(.bar-toolbar) {
  height: 44px;
  padding: 0 8px;
  background: rgb(26, 28, 33);
  border-bottom: 1px solid var(--border);
}

/* 收起按钮在图中工作区里不再使用：调色板始终占满左侧 */
.tile-workspace-palette :deep(.collapse-btn) {
  display: none;
}

.tile-workspace-collision :deep(.col-toolbar) {
  height: 44px;
  padding: 0 8px;
  background: rgb(26, 28, 33);
  border-bottom: 1px solid var(--border);
}

/* 碰撞预览宽度：4 个按钮不挤，和左侧调色板比例更协调 */
.tile-workspace-collision {
  width: 200px;
  min-width: 200px;
  display: flex;
  flex-direction: column;
  border-left: 1px solid var(--border);
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

/* 画布临时提示（如自定义形状自交）：暖色，和常规信息区分 */
.info-warn {
  font-size: 12px;
  color: #e5b36b;
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
