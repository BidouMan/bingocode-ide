<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick, type CSSProperties } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { useMapStore, type MapResource, type ImageData as MapImageData, type SceneMarker } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import { useProjectStore } from '../../stores/project'
import { useEditorStore } from '../../stores/editor'
import { isSvgSource, rasterizeSvgImage, SVG_RASTER_SCALE } from '../../utils/svgRasterize'
import { imageWorldToLocal, imageLocalToWorld } from '../../utils/mapImageGeometry'
import { usePaintStore } from '../../stores/paint'
import { rgbaCss, hexToRgba } from '../paint-editor/utils/artboardExport'
import { useMapViewport } from '../../composables/useMapViewport'
import { useImageTransform } from '../../composables/useImageTransform'
import { useCollisionLayerEditor } from '../../composables/useCollisionLayerEditor'
import { useTilePainter } from '../../composables/useTilePainter'
import { usePaperScope } from '../paint-editor/composables/usePaperScope'
import { createBitmapPen } from '../paint-editor/utils/bitmapPen'
import { ensurePaintFont } from '../paint-editor/utils/paintFont'
import { collectSnapLines, snapRectOffset, snapThreshold } from '../../utils/smartSnap'
import { toUserX, toUserY } from '../../utils/coords'
import iconMarkerRaw from '../../assets/icons/标记.svg?raw'
import {
  createMapVectorViewport,
  computeMapVectorMatrix,
  type MapVectorFrame,
  type MapVectorMatrix,
} from './mapVectorViewport'

const emit = defineEmits<{
  'tile-painted': [x: number, y: number, tileId: number]
  'tile-erased': [x: number, y: number]
  'cursor-move': [x: number, y: number]
  'cursor-leave': []
  'layer-thumb-updated': [layerId: number, dataUrl: string]
  /** 双击标记：请编辑器把焦点交给标记浮条的名称输入 */
  'marker-activate': [id: string]
}>()

const cursorGridPos = ref<{ x: number; y: number } | null>(null)

const canvasRef = ref<HTMLDivElement>()
// 碰撞叠加层：屏幕坐标 canvas（位于矢量画布之上）
const collisionOverlayRef = ref<HTMLCanvasElement>()
let PIXI: any = null
let app: any = null
let tileContainer: any = null
// Pixi v8 的 resizeTo 只监听 window resize，页面从隐藏切到显示时不会重新量尺寸，
// 这里自行监听容器尺寸变化，避免画布小于容器导致网格显示不全
let resizeObserver: ResizeObserver | null = null

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()
const projectStore = useProjectStore()
const editorStore = useEditorStore()
const paintStore = usePaintStore()

// 解析资源路径为浏览器可加载的 URL
const resolvedPathCache = new Map<string, string>()
async function resolveImagePath(path: string): Promise<string> {
  const cached = resolvedPathCache.get(path)
  if (cached) return cached

  let url: string
  if (path.startsWith('/maps/')) {
    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')
      url = await invoke<string>('read_image_as_data_url', { path: `${engineDir}${path}` })
    } catch {
      url = ''
    }
  } else if (path.startsWith('assets/')) {
    // 中文路径下 convertFileSrc 会加载失败，统一走 data URL
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

  resolvedPathCache.set(path, url)
  return url
}

// Tile rendering state
let layerContainers: Map<number, any> = new Map()
let tileSprites: Map<string, any> = new Map() // "layerId:x,y" -> Sprite
let tileTextures: Map<string, any> = new Map() // "resourcePath:tileIndex" -> Texture
let sourceImageCache: Map<string, any> = new Map() // "resourcePath" -> HTMLImageElement

// ─── 增量渲染状态（切层/重渲染不再清空全部容器，避免画面闪烁、图层"打架"）───
/** 图层 id → 已渲染内容签名；签名未变则复用现有精灵 */
const layerRenderKeys = new Map<number, string>()
/** 上次渲染的图层结构（地图 + id/类型/顺序），变化时必须全量重建 */
let lastRenderStructureKey = ''

// ─── 矢量模式：当前矢量图层「之上」图层的快照（保证画布始终按图层顺序显示）───
const upperSnapshotRef = ref<HTMLCanvasElement>()
const upperSnapshotRect = ref<{ x: number; y: number; w: number; h: number } | null>(null)
/** 快照容器：矢量编辑时把上方图层容器移出舞台，只渲染进快照，避免与快照重复叠加 */
let upperSnapshotContainer: any = null
/** 最近一次渲染出的快照画布（DOM 挂载后拷贝过去） */
let upperSnapshotSource: HTMLCanvasElement | null = null
let upperSnapshotPendingRect: { x: number; y: number; w: number; h: number } | null = null
let upperSnapshotTimer: ReturnType<typeof setTimeout> | null = null

async function initPixi() {
  if (!canvasRef.value) return

  PIXI = await import('pixi.js')
  app = new PIXI.Application()
  await app.init({
    background: '#1e1e1e',
    resizeTo: canvasRef.value,
    antialias: true,
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
  })
  canvasRef.value.appendChild(app.canvas)

  // 容器尺寸变化时同步渲染器尺寸并重绘网格
  resizeObserver = new ResizeObserver(() => {
    if (!canvasRef.value || !app) return
    const w = canvasRef.value.clientWidth
    const h = canvasRef.value.clientHeight
    if (w <= 0 || h <= 0) return
    if (app.screen.width === w && app.screen.height === h) return
    app.renderer.resize(w, h)
    viewport.redraw()
    // resize 会清空画布，立即补一帧避免出现黑屏闪烁
    app.render()
    // 碰撞叠加层随容器尺寸同步
    resizeCollisionOverlay()
  })
  resizeObserver.observe(canvasRef.value)
  resizeCollisionOverlay()

  // 应用初始渲染模式
  applyRenderMode()

  tileContainer = new PIXI.Container()
  tileContainer.sortableChildren = true
  app.stage.addChild(tileContainer)

  viewport.drawGrid()
  viewport.drawAxes()
  viewport.drawGameWindow()
  setupInteraction()
  viewport.applyScale()
  viewport.centerView()
  await renderAllLayers()
}

// --- Tile Rendering ---

// 当前渲染模式的 scaleMode
let currentScaleMode: 'nearest' | 'linear' = 'linear'

/**
 * 场景级渲染模式（自动判定，忽略全局渲染设置，规则见 mapStore.sceneRenderMode）：
 * - 存在图块图层 → pixelated（整张画布最近邻）
 * - 存在位图图片图层 → pixelated（整张画布按位图模式）
 * - 全部为矢量图层 → smooth（按矢量渲染）
 */
function applyRenderMode() {
  if (!PIXI) return
  currentScaleMode = mapStore.sceneRenderMode === 'pixelated' ? 'nearest' : 'linear'
  // 清空纹理缓存，强制使用新的 scaleMode 重新创建
  tileTextures.clear()
}

async function loadImage(src: string): Promise<HTMLImageElement> {
  // 先解析路径
  const url = await resolveImagePath(src)
  if (!url) throw new Error(`无法加载图片: ${src}`)
  if (sourceImageCache.has(url)) return sourceImageCache.get(url)
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      sourceImageCache.set(url, img)
      resolve(img)
    }
    img.onerror = reject
    img.src = url
  })
}

async function getTileTexture(resource: MapResource, tileIndex: number): Promise<any> {
  const key = `${resource.path}:${tileIndex}:${resource.tileWidth}x${resource.tileHeight}`
  if (tileTextures.has(key)) return tileTextures.get(key)

  try {
    const img = await loadImage(resource.path)
    const cols = Math.floor(img.width / resource.tileWidth)
    const row = Math.floor(tileIndex / cols)
    const col = tileIndex % cols

    // SVG 瓦片超采样（借鉴 scratch-render）：切片按 2x 绘制。
    // 不用 resolution——renderTile 会显式设置 sprite.width=tileSize，
    // 2x 纹理自动压回逻辑尺寸，放大时更清晰
    const ss = isSvgSource(img.src) ? SVG_RASTER_SCALE : 1
    const canvas = document.createElement('canvas')
    canvas.width = resource.tileWidth * ss
    canvas.height = resource.tileHeight * ss
    const ctx = canvas.getContext('2d')!
    ctx.imageSmoothingEnabled = true
    ctx.drawImage(
      img,
      col * resource.tileWidth, row * resource.tileHeight,
      resource.tileWidth, resource.tileHeight,
      0, 0,
      canvas.width, canvas.height
    )

    const texture = PIXI.Texture.from(canvas)
    texture.source.scaleMode = currentScaleMode
    tileTextures.set(key, texture)
    return texture
  } catch {
    return null
  }
}

// 获取或创建图层容器
function getOrCreateLayerContainer(layerId: number): any {
  if (layerContainers.has(layerId)) return layerContainers.get(layerId)
  const container = new PIXI.Container()
  container.label = `layer_${layerId}`
  layerContainers.set(layerId, container)
  return container
}

// 清空某个图层容器内的所有子元素
function clearLayerContainer(layerId: number) {
  const container = layerContainers.get(layerId)
  if (!container) return
  const children = [...container.children]
  container.removeChildren()
  for (const child of children) child.destroy()
  const keysToRemove: string[] = []
  for (const [key] of tileSprites) {
    if (key.startsWith(`${layerId}:`)) keysToRemove.push(key)
  }
  for (const key of keysToRemove) tileSprites.delete(key)
}

/** 图片图层的渲染签名：路径/几何/透明度/采样方式变化时才重建精灵 */
function imageLayerSignature(img: any): string {
  return [
    img?.imagePath ?? '',
    img?.width ?? 0, img?.height ?? 0,
    img?.position?.[0] ?? 0, img?.position?.[1] ?? 0,
    img?.scaleX ?? img?.scale ?? 1,
    img?.scaleY ?? img?.scale ?? 1,
    img?.rotation ?? 0, img?.opacity ?? 1,
    currentScaleMode,
  ].join('|')
}

/** 图层内容签名：图块层按 tileRevision 整体重建，图片层按自身签名，碰撞层无内容 */
function layerContentKey(layer: any): string {
  if (layer.type === 'drawing') return `tiles:${mapStore.tileRevision}:${currentScaleMode}`
  if (layer.type === 'image') return `img:${imageLayerSignature(layer.image)}`
  return ''
}

/**
 * 保存绘制结果只会改写文件路径，画面内容仍是同一个会话画布：
 * 立即同步签名，避免下一次重渲染从磁盘重载造成闪烁（切层的"颜色打架"根因）。
 */
function syncLayerRenderKey(layerId: number) {
  const layer = mapStore.mapData.layers.find(l => l.id === layerId)
  if (!layer || layer.type !== 'image') return
  layerRenderKeys.set(layerId, layerContentKey(layer))
}

/** 取图层容器里已有的图片精灵（增量渲染时复用，避免销毁重建） */
function findLayerSprite(layerId: number): any {
  const container = layerContainers.get(layerId)
  if (!container || !PIXI) return null
  for (const child of container.children ?? []) {
    if (child instanceof PIXI.Sprite && !child.destroyed) return child
  }
  return null
}

function ensureLayerOrder() {
  const layers = mapStore.mapData.layers
  for (let i = 0; i < layers.length; i++) {
    const container = layerContainers.get(layers[i].id)
    if (container) {
      container.zIndex = i
      container.visible = layers[i].visible
    }
  }
  tileContainer.sortChildren()
}

async function renderTile(layerId: number, x: number, y: number, tileId: number) {
  if (tileId === 0) {
    removeTile(layerId, x, y)
    return
  }

  const key = `${layerId}:${x},${y}`

  // 通过 firstgid 范围找到对应的 tileSet
  const tileSets = mapStore.mapData.tileSets
  let matchedTileSet: any = null
  for (let i = tileSets.length - 1; i >= 0; i--) {
    if (tileId >= tileSets[i].firstgid) {
      matchedTileSet = tileSets[i]
      break
    }
  }
  if (!matchedTileSet) return
  const tileIndex = tileId - matchedTileSet.firstgid

  // 在地图级素材库中优先按 firstgid 精确匹配，回退到路径匹配
  const resource: MapResource | null = mapStore.mapData.resources.find(
    (r: MapResource) => r.firstgid === matchedTileSet.firstgid
  ) ?? mapStore.mapData.resources.find(
    (r: MapResource) => r.path === matchedTileSet.imagePath
  ) ?? null
  if (!resource) return

  const texture = await getTileTexture(resource, tileIndex)
  if (!texture) return

  let sprite = tileSprites.get(key)
  const tileSize = mapStore.mapData.tileSize

  if (sprite) {
    sprite.texture = texture
  } else {
    sprite = new PIXI.Sprite(texture)
    sprite.x = x * tileSize
    sprite.y = y * tileSize
    sprite.width = tileSize
    sprite.height = tileSize
    const container = getOrCreateLayerContainer(layerId)
    container.addChild(sprite)
    tileSprites.set(key, sprite)
  }
}

function removeTile(layerId: number, x: number, y: number) {
  const key = `${layerId}:${x},${y}`
  const sprite = tileSprites.get(key)
  if (sprite) {
    sprite.parent?.removeChild(sprite)
    sprite.destroy()
    tileSprites.delete(key)
  }
}

async function renderAllLayers() {
  if (!app || !PIXI) return

  const layers = mapStore.mapData.layers

  // 地图切换 / 图层增删 / 顺序变化：必须全量重建（图层 id 可能被复用，不能沿用旧内容）
  const structureKey = `${mapStore.mapLoadCount}:${layers.map(l => `${l.id}:${l.type}`).join(',')}`
  const structureChanged = structureKey !== lastRenderStructureKey
  if (structureChanged) {
    lastRenderStructureKey = structureKey
    layerRenderKeys.clear()
  }

  // 移除不再存在的图层容器
  const activeIds = new Set(layers.map(l => l.id))
  for (const [id, container] of layerContainers) {
    if (!activeIds.has(id)) {
      tileContainer.removeChild(container)
      container.destroy({ children: true })
      layerContainers.delete(id)
      layerRenderKeys.delete(id)
    }
  }

  // 确保每个图层都有容器，设置 zIndex 和可见性（但不 addChild）
  for (let i = 0; i < layers.length; i++) {
    const layer = layers[i]
    const container = getOrCreateLayerContainer(layer.id)
    container.zIndex = i
    container.visible = layer.visible
    if (structureChanged) clearLayerContainer(layer.id)
  }

  // 逐图层增量重建：签名未变则保留现有内容（切图/切层不再出现空画布闪烁）
  for (const layer of layers) {
    const key = layerContentKey(layer)
    if (layerRenderKeys.get(layer.id) !== key) {
      if (layer.type === 'drawing') {
        clearLayerContainer(layer.id)
        for (const [posKey, tileId] of Object.entries(layer.tiles)) {
          const [x, y] = posKey.split(',').map(Number)
          await renderTile(layer.id, x, y, tileId)
        }
      } else if (layer.type === 'image') {
        clearLayerContainer(layer.id)
        const container = getOrCreateLayerContainer(layer.id)
        await renderImageLayer(container, layer.image, layer.id)
      }
      if (app) layerRenderKeys.set(layer.id, key)
    } else if (layer.type === 'image') {
      // 内容未变：复用现有精灵，只确保会话纹理与命中缓存仍指向当前图层
      const sprite = findLayerSprite(layer.id)
      if (sprite) {
        if (paintSession && paintSession.layerId === layer.id) bindPaintTexture(sprite, layer.image)
        transform.noteRenderedImage(layer.image, sprite)
      } else {
        const container = getOrCreateLayerContainer(layer.id)
        await renderImageLayer(container, layer.image, layer.id)
        if (app) layerRenderKeys.set(layer.id, key)
      }
    }
  }

  // 按逆序添加容器到 tileContainer（后添加的在上面）
  // 这样绘制图层（index 大）自然在图像图层（index 小）上面
  tileContainer.removeChildren()
  for (let i = layers.length - 1; i >= 0; i--) {
    const container = layerContainers.get(layers[i].id)
    if (container) tileContainer.addChild(container)
  }

  // 图像精灵重建后重绘碰撞叠加层
  collision.drawOverlay()
  // 矢量模式下把当前图层之上的图层叠回矢量画布之上，保持整张画布仍按图层顺序显示
  refreshUpperLayerSnapshot()
}

async function renderImageLayer(container: any, imgData: any, layerId: number) {
  if (!imgData?.imagePath) return
  try {
    const img = await loadImage(imgData.imagePath)
    // SVG 超采样光栅化（借鉴 scratch-render）：2x canvas 上传为纹理；
    // 精灵 scale 按"逻辑尺寸/纹理像素尺寸"换算 —— 2x 纹理压回 640×480
    // 逻辑尺寸，既不超框，放大查看时又保留超采样的清晰度
    const texture = isSvgSource(img.src)
      ? PIXI.Texture.from(rasterizeSvgImage(img))
      : PIXI.Texture.from(img)
    texture.source.scaleMode = currentScaleMode
    const sprite = new PIXI.Sprite(texture)
    sprite.x = imgData.position?.[0] ?? 0
    sprite.y = imgData.position?.[1] ?? 0
    const scaleX = (imgData.scaleX ?? imgData.scale ?? 1)
    const scaleY = (imgData.scaleY ?? imgData.scale ?? 1)
    const logicalW = imgData.width || img.naturalWidth || 64
    const logicalH = imgData.height || img.naturalHeight || 64
    sprite.scale.set(
      (logicalW * scaleX) / (texture.width || logicalW),
      (logicalH * scaleY) / (texture.height || logicalH)
    )
    const rotation = (imgData.rotation ?? 0) * Math.PI / 180
    sprite.anchor.set(0.5, 0.5)
    sprite.x += (imgData.width || 64) * scaleX / 2
    sprite.y += (imgData.height || 64) * scaleY / 2
    sprite.rotation = rotation
    sprite.alpha = imgData.opacity ?? 1
    container.addChild(sprite)
    // 正在绘制的图层：显示绘制画布纹理，并按画布尺寸重算变换
    if (paintSession && paintSession.layerId === layerId) {
      bindPaintTexture(sprite, imgData)
    }
    transform.noteRenderedImage(imgData, sprite)
  } catch (err) {
    console.error('[MapCanvas] renderImageLayer error:', err)
  }
}

async function placeImage(resource: any, x: number, y: number) {
  let imgData: any
  try {
    const img = await loadImage(resource.path)
    // 上传/内置资源放置的图片是位图素材，默认按位图模式编辑
    imgData = {
      imagePath: resource.path,
      position: [x, y],
      rotation: 0,
      scale: 1,
      scaleX: 1,
      scaleY: 1,
      opacity: 1,
      width: img.naturalWidth || 64,
      height: img.naturalHeight || 64,
      collisionType: '图像',
      collisionEnabled: false,
      paintMode: 'bitmap',
    }
  } catch {
    imgData = {
      imagePath: resource.path,
      position: [x, y],
      rotation: 0,
      scale: 1,
      scaleX: 1,
      scaleY: 1,
      opacity: 1,
      width: 64,
      height: 64,
      collisionType: '图像',
      collisionEnabled: false,
      paintMode: 'bitmap',
    }
  }
  // 扁平模型：放置一张图片就新建一个图片图层（在最上层），名称统一为「图像图层」
  mapStore.addImageLayer('图像图层', imgData)

  // 放置后切换到选取工具；整图选中框不再自动显示
  mapEditorStore.setTool('select')
}

// 供外部（图层工具栏/内置资源库）直接按路径放置一张图片并建层
async function placeImageFromPath(path: string, x = 0, y = 0) {
  await placeImage({ path }, x, y)
}

// ====== 图片模式：直接在画布上绘制（位图工具） ======
interface ImagePaintSession {
  layerId: number
  mapName: string
  canvas: HTMLCanvasElement
  texture: any
  sprite: any
  lastPoint: { x: number; y: number } | null
  startPoint: { x: number; y: number } | null
  snapshot: ImageData | null
  dirty: boolean
  savePath: string
}

let paintSession: ImagePaintSession | null = null
let paintUndo: ImageData[] = []
let paintRedo: ImageData[] = []
let paintSaveTimer: ReturnType<typeof setTimeout> | null = null
const PAINT_UNDO_LIMIT = 8
// 撤销/重做可用性供悬浮工具条读取（栈本身不是响应式的，用版本号驱动）
const paintHistoryTick = ref(0)
function bumpPaintHistory() {
  paintHistoryTick.value++
}
const canUndoPaint = computed(() => paintHistoryTick.value >= 0 && !!paintSession && paintUndo.length > 0)
const canRedoPaint = computed(() => paintHistoryTick.value >= 0 && !!paintSession && paintRedo.length > 0)

// 选区内复制/粘贴剪贴板（画布会话内有效）
let paintClipboard: HTMLCanvasElement | null = null
let clipboardCenter = { x: 0, y: 0 }
let pasteCount = 0

// ====== 矢量绘制覆盖层（Paper.js，几何由 mapVectorViewport 适配） ======
const vectorCanvasRef = ref<HTMLCanvasElement>()
// 矢量内容绘制在独立 canvas 上，图层透明度需要单独应用（位图精灵走 sprite.alpha）
const vectorCanvasOpacity = computed(() => {
  const o = mapStore.selectedImage?.opacity ?? 1
  return String(Math.max(0, Math.min(1, o)))
})
const textAreaRef = ref<HTMLTextAreaElement>()
const vectorActive = ref(false)
const vectorMatrix = ref<MapVectorMatrix | null>(null)
// 矢量画笔/橡皮光标：屏幕坐标（相对地图画布容器），用 DOM 圆圈保证任意缩放下清晰
const vectorCursorPos = ref<{ x: number; y: number } | null>(null)
let vectorPanning = false
let vectorExiting = false
let enteringVector = false
// 切换图层时同步工具栏模式会触发 paintMode watcher，用该标记跳过（避免把"切层"误当成"用户切到位图"）
let suppressPaintModeWatch = false
// 矢量图层会话缓存：切换图层时保留 Paper JSON 与不含矢量的位图底稿，
// 切回来可继续编辑；保存时会把 JSON/底稿路径写入地图数据。
// image 记录归属的图像对象：图层 id 会被复用，必须校验归属，避免旧缓存串到新图层。
const vectorLayerCache = new Map<number, { json: string; base: HTMLCanvasElement; image: MapImageData }>()

/** 取图层对应的矢量缓存；归属不符（图层已删除/id 被复用）时直接丢弃 */
function cachedVectorEntry(layerId: number, img: MapImageData | null | undefined) {
  const entry = vectorLayerCache.get(layerId)
  if (!entry) return null
  if (!img || entry.image !== img) {
    vectorLayerCache.delete(layerId)
    return null
  }
  return entry
}
let vectorStoreSnapshot: {
  artboardWidth: number
  artboardHeight: number
  zoom: number
  panX: number
  panY: number
} | null = null

// 图片像素框选（归一化本地坐标）
let pixelSelection: { x0: number; y0: number; x1: number; y1: number } | null = null
let selectionGraphics: any = null

// 浮动选区：框选完成后像素被切成浮动层，出现变换框（8 缩放锚点 + 旋转锚点）
// 坐标统一使用绘制画布的像素空间，合成进 paintSession.canvas 后再交给纹理
let floatCanvas: HTMLCanvasElement | null = null
let floatBaseCanvas: HTMLCanvasElement | null = null
let floatOrigin: ImageData | null = null
let floatXf = { cx: 0, cy: 0, sx: 1, sy: 1, angle: 0 }
let floatOp: 'none' | 'create' | 'move' | 'scale' | 'rotate' = 'none'
let floatStartXf: { cx: number; cy: number; sx: number; sy: number; angle: number } | null = null
let floatGrab = { x: 0, y: 0 }
let scaleAnchorPx = { x: 0, y: 0 }
let scalePointer0 = { x: 0, y: 0 }
let scaleDir = { x: 1, y: 1 }
let scaleAxes = { x: true, y: true }
let scaleHalf0 = { x: 0, y: 0 }

function ensureSelectionGraphics() {
  if (!app || !PIXI) return
  if (!selectionGraphics) {
    selectionGraphics = new PIXI.Graphics()
    app.stage.addChild(selectionGraphics)
  }
}

function clearPixelSelection() {
  pixelSelection = null
  if (floatOp === 'create') floatOp = 'none'
  selectionGraphics?.clear()
}

function resetFloatingSelection() {
  const hadFloat = !!floatCanvas
  pixelSelection = null
  floatCanvas = null
  floatBaseCanvas = null
  floatOrigin = null
  floatOp = 'none'
  floatStartXf = null
  mapEditorStore.hasPixelSelection = false
  selectionGraphics?.clear()
  // 浮选内容已合成到画布：标记脏，切图层提交时才会落盘
  if (hadFloat && paintSession) {
    paintSession.dirty = true
    schedulePaintSave()
  }
}

/** 绘制会话必须属于当前选中的图片图层，避免异步切换期间读写到别的图层（串内容） */
function sessionMatchesSelection(): boolean {
  return !!paintSession && paintSession.layerId === mapStore.selectedImageLayerId
}

function makeOffscreenCanvas(w: number, h: number): HTMLCanvasElement {
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  return c
}

// 归一化框选 → 画布像素整数矩形
function selectionRectPx() {
  const s = paintSession
  if (!s || !pixelSelection) return null
  const { x0, y0, x1, y1 } = pixelSelection
  const cw = s.canvas.width
  const ch = s.canvas.height
  const x = Math.max(0, Math.min(cw, Math.floor(Math.min(x0, x1) * cw)))
  const y = Math.max(0, Math.min(ch, Math.floor(Math.min(y0, y1) * ch)))
  const w = Math.max(0, Math.min(cw, Math.ceil(Math.max(x0, x1) * cw)) - x)
  const h = Math.max(0, Math.min(ch, Math.ceil(Math.max(y0, y1) * ch)) - y)
  return { x, y, w, h }
}

/** 选区内是否存在非透明像素（全透明 = 没框到内容） */
function selectionHasContent(r: { x: number; y: number; w: number; h: number }): boolean {
  const ctx = paintCtx()
  if (!ctx || r.w <= 0 || r.h <= 0) return false
  try {
    const data = ctx.getImageData(r.x, r.y, r.w, r.h).data
    for (let i = 3; i < data.length; i += 4) {
      if (data[i] > 8) return true
    }
  } catch {
    // 读取失败时按"有内容"处理，避免直接吞掉选区
    return true
  }
  return false
}

function floatCornersPx(): { x: number; y: number }[] {
  if (!floatCanvas) return []
  const hw = (floatCanvas.width * floatXf.sx) / 2
  const hh = (floatCanvas.height * floatXf.sy) / 2
  const cos = Math.cos(floatXf.angle)
  const sin = Math.sin(floatXf.angle)
  return [
    { x: -hw, y: -hh },
    { x: hw, y: -hh },
    { x: hw, y: hh },
    { x: -hw, y: hh },
  ].map(l => ({
    x: floatXf.cx + l.x * cos - l.y * sin,
    y: floatXf.cy + l.x * sin + l.y * cos,
  }))
}

function floatCornersWorld(): { x: number; y: number }[] {
  const s = paintSession
  const img = sessionImage()
  if (!s || !img) return []
  return floatCornersPx().map(p =>
    imageLocalToWorld(img, { x: p.x / s.canvas.width, y: p.y / s.canvas.height })
  )
}

function pointInPolygon(p: { x: number; y: number }, poly: { x: number; y: number }[]): boolean {
  let inside = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[i]
    const b = poly[j]
    if ((a.y > p.y) !== (b.y > p.y) &&
        p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x) {
      inside = !inside
    }
  }
  return inside
}

// 浮动选区变换框几何（世界坐标）：角点、边中点、旋转锚点
function floatBoxWorld() {
  const cs = floatCornersWorld()
  if (cs.length !== 4) return null
  const [tl, tr, br, bl] = cs
  const mid = (a: { x: number; y: number }, b: { x: number; y: number }) => ({
    x: (a.x + b.x) / 2,
    y: (a.y + b.y) / 2,
  })
  const top = mid(tl, tr)
  const right = mid(tr, br)
  const bottom = mid(br, bl)
  const left = mid(bl, tl)
  const center = mid(tl, br)
  let nx = top.x - center.x
  let ny = top.y - center.y
  const nl = Math.hypot(nx, ny) || 1
  nx /= nl
  ny /= nl
  const scale = Math.max(0.1, viewport.currentScale.value)
  // 旋转锚点在顶边中点外法线 16 屏幕像素处
  const rotOff = 16 / scale
  return {
    tl, tr, br, bl, top, right, bottom, left, center,
    // 手柄顺序与 scaleHandleDef 索引一致：TL TR BR BL T B L R
    handles: [tl, tr, br, bl, top, bottom, left, right],
    rot: { x: top.x + nx * rotOff, y: top.y + ny * rotOff },
  }
}

function drawSelectionOverlay() {
  ensureSelectionGraphics()
  if (!selectionGraphics) return
  const g = selectionGraphics
  g.clear()
  const s = paintSession
  const img = sessionImage()
  if (!s || !img) return

  const scale = Math.max(0.1, viewport.currentScale.value)
  const hs = 8 / scale
  // 与矢量模式同一套选区样式：靛蓝描边 + 屏幕恒定线宽
  const SEL = 0x818cf8
  const SEL_DEEP = 0x6366f1
  const strokeW = 1.4 / scale

  if (floatCanvas) {
    const box = floatBoxWorld()
    if (!box) return
    const pts = [box.tl, box.tr, box.br, box.bl].flatMap(p => [p.x, p.y])
    g.poly(pts)
    g.fill({ color: SEL, alpha: 0.06 })
    g.poly(pts)
    g.stroke({ width: strokeW, color: SEL })
    // 旋转锚点连线
    g.moveTo(box.top.x, box.top.y)
    g.lineTo(box.rot.x, box.rot.y)
    g.stroke({ width: strokeW, color: SEL })
    // 缩放锚点（白底深靛边，与矢量一致）
    for (const h of box.handles) {
      g.rect(h.x - hs / 2, h.y - hs / 2, hs, hs)
      g.fill({ color: 0xffffff })
      g.stroke({ width: strokeW * 0.85, color: SEL_DEEP })
    }
    // 旋转锚点
    g.circle(box.rot.x, box.rot.y, hs * 0.6)
    g.fill({ color: 0xffffff })
    g.stroke({ width: strokeW * 0.85, color: SEL_DEEP })
    return
  }

  if (pixelSelection) {
    const { x0, y0, x1, y1 } = pixelSelection
    const pts = [
      imageLocalToWorld(img, { x: Math.min(x0, x1), y: Math.min(y0, y1) }),
      imageLocalToWorld(img, { x: Math.max(x0, x1), y: Math.min(y0, y1) }),
      imageLocalToWorld(img, { x: Math.max(x0, x1), y: Math.max(y0, y1) }),
      imageLocalToWorld(img, { x: Math.min(x0, x1), y: Math.max(y0, y1) }),
    ].flatMap(p => [p.x, p.y])
    g.poly(pts)
    g.fill({ color: SEL, alpha: 0.10 })
    g.poly(pts)
    g.stroke({ width: strokeW, color: SEL })
  }
}

// 以当前变换把浮动选区合成进绘制画布（基础层保留被挖空的原图）
function compositeFloat() {
  const s = paintSession
  const ctx = paintCtx()
  if (!s || !ctx || !floatCanvas || !floatBaseCanvas) return
  ctx.save()
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.clearRect(0, 0, s.canvas.width, s.canvas.height)
  ctx.drawImage(floatBaseCanvas, 0, 0)
  ctx.translate(floatXf.cx, floatXf.cy)
  ctx.rotate(floatXf.angle)
  ctx.scale(floatXf.sx, floatXf.sy)
  ctx.drawImage(floatCanvas, -floatCanvas.width / 2, -floatCanvas.height / 2)
  ctx.restore()
  s.texture.source.update()
  drawSelectionOverlay()
}

// 框选完成：把选区像素切成浮动层，立即进入变换框状态
function cutSelectionToFloat() {
  const s = paintSession
  const ctx = paintCtx()
  const r = selectionRectPx()
  if (!s || !ctx || !sessionMatchesSelection() || !r || r.w < 2 || r.h < 2) {
    clearPixelSelection()
    return
  }
  // 选区全是透明像素 = 没框到内容（与矢量模式一致：不建立空选区）
  if (!selectionHasContent(r)) {
    clearPixelSelection()
    return
  }
  cutRectToFloat(r)
}

/**
 * 把画布像素矩形切成浮动层并进入变换框状态。
 * origin = 生成该内容前的底稿（图形刚创建时传入，Esc 取消即回到创建前）；
 * pushHistory = false 时不额外压撤销（创建图形本身已经压过一步）。
 */
function cutRectToFloat(
  r: { x: number; y: number; w: number; h: number },
  origin: ImageData | null = null,
  pushHistory = true
) {
  const s = paintSession
  const ctx = paintCtx()
  if (!s || !ctx || !sessionMatchesSelection() || !r || r.w < 2 || r.h < 2) {
    clearPixelSelection()
    return
  }
  ctx.save()
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  if (pushHistory) pushPaintUndo()
  floatOrigin = origin ?? ctx.getImageData(0, 0, s.canvas.width, s.canvas.height)
  const base = makeOffscreenCanvas(s.canvas.width, s.canvas.height)
  const bctx = base.getContext('2d')!
  bctx.drawImage(s.canvas, 0, 0)
  bctx.clearRect(r.x, r.y, r.w, r.h)
  const fc = makeOffscreenCanvas(r.w, r.h)
  fc.getContext('2d')!.drawImage(s.canvas, r.x, r.y, r.w, r.h, 0, 0, r.w, r.h)
  ctx.restore()
  floatBaseCanvas = base
  floatCanvas = fc
  floatXf = { cx: r.x + r.w / 2, cy: r.y + r.h / 2, sx: 1, sy: 1, angle: 0 }
  pixelSelection = null
  floatOp = 'none'
  floatStartXf = null
  mapEditorStore.hasPixelSelection = true
  // 整层变换框与像素选区变换框会互相抢手柄，进入选区编辑时先收起整层框
  transform.removeTransformBox()
  compositeFloat()
  s.dirty = true
  schedulePaintSave()
}

// 提交浮动选区：当前合成结果即最终像素（画布已含浮动内容）
function bakeFloatingSelection() {
  if (!floatCanvas) return
  compositeFloat()
  const s = paintSession
  floatCanvas = null
  floatBaseCanvas = null
  floatOrigin = null
  floatOp = 'none'
  floatStartXf = null
  mapEditorStore.hasPixelSelection = false
  selectionGraphics?.clear()
  if (s) {
    s.dirty = true
    schedulePaintSave()
  }
}

// Esc 取消：恢复框选前的像素
function cancelFloatingSelection() {
  const s = paintSession
  const ctx = paintCtx()
  if (!s || !ctx || !floatCanvas) return
  if (floatOrigin) ctx.putImageData(floatOrigin, 0, 0)
  paintUndo.pop()
  bumpPaintHistory()
  floatCanvas = null
  floatBaseCanvas = null
  floatOrigin = null
  floatOp = 'none'
  floatStartXf = null
  mapEditorStore.hasPixelSelection = false
  s.texture.source.update()
  selectionGraphics?.clear()
  s.dirty = true
  schedulePaintSave()
}

// 删除浮动选区内容：只保留基础层（挖空后的原图）
function deleteFloatingPixels() {
  const s = paintSession
  const ctx = paintCtx()
  if (!s || !ctx || !floatCanvas || !floatBaseCanvas) return
  ctx.save()
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.clearRect(0, 0, s.canvas.width, s.canvas.height)
  ctx.drawImage(floatBaseCanvas, 0, 0)
  ctx.restore()
  floatCanvas = null
  floatBaseCanvas = null
  floatOrigin = null
  floatOp = 'none'
  floatStartXf = null
  mapEditorStore.hasPixelSelection = false
  s.texture.source.update()
  selectionGraphics?.clear()
  s.dirty = true
  schedulePaintSave()
}

// 工具栏删除：只删除浮动选区内容，不影响图层本身
function deleteSelection() {
  if (floatCanvas) deleteFloatingPixels()
}

// 复制浮动选区内容（保留原始像素，粘贴后可重新变换）
function copyFloatingSelection() {
  if (!floatCanvas) return
  const c = makeOffscreenCanvas(floatCanvas.width, floatCanvas.height)
  c.getContext('2d')!.drawImage(floatCanvas, 0, 0)
  paintClipboard = c
  clipboardCenter = { x: floatXf.cx, y: floatXf.cy }
  pasteCount = 0
  mapEditorStore.hasPaintClipboard = true
}

// 粘贴为新浮动选区（带递增偏移，避免与原内容完全重叠）
function pasteFloatingSelection() {
  if (!paintClipboard || !paintSession || !sessionMatchesSelection()) return
  const s = paintSession
  const ctx = paintCtx()
  if (!ctx) return
  if (floatCanvas) bakeFloatingSelection()
  // 粘贴后需要立即能拖动，切回选取工具
  mapEditorStore.setImageTool('select')
  paintStore.setTool('select')
  pushPaintUndo()
  floatOrigin = ctx.getImageData(0, 0, s.canvas.width, s.canvas.height)
  const base = makeOffscreenCanvas(s.canvas.width, s.canvas.height)
  base.getContext('2d')!.drawImage(s.canvas, 0, 0)
  const fc = makeOffscreenCanvas(paintClipboard.width, paintClipboard.height)
  fc.getContext('2d')!.drawImage(paintClipboard, 0, 0)
  floatBaseCanvas = base
  floatCanvas = fc
  pasteCount++
  const w = fc.width
  const h = fc.height
  const cx = Math.min(s.canvas.width - w / 2, Math.max(w / 2, clipboardCenter.x + 16 * pasteCount))
  const cy = Math.min(s.canvas.height - h / 2, Math.max(h / 2, clipboardCenter.y + 16 * pasteCount))
  floatXf = { cx, cy, sx: 1, sy: 1, angle: 0 }
  pixelSelection = null
  floatOp = 'none'
  floatStartXf = null
  mapEditorStore.hasPixelSelection = true
  transform.removeTransformBox()
  compositeFloat()
  s.dirty = true
  schedulePaintSave()
}

// 镜像翻转：有浮动选区翻转选区，无选区翻转整层像素
function flipSelection(axis: 'h' | 'v') {
  const s = paintSession
  const ctx = paintCtx()
  if (!s || !ctx) return
  if (floatCanvas) {
    if (axis === 'h') floatXf.sx *= -1
    else floatXf.sy *= -1
    compositeFloat()
    s.dirty = true
    schedulePaintSave()
    return
  }
  pushPaintUndo()
  const tmp = makeOffscreenCanvas(s.canvas.width, s.canvas.height)
  tmp.getContext('2d')!.drawImage(s.canvas, 0, 0)
  ctx.save()
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.clearRect(0, 0, s.canvas.width, s.canvas.height)
  ctx.translate(axis === 'h' ? s.canvas.width : 0, axis === 'v' ? s.canvas.height : 0)
  ctx.scale(axis === 'h' ? -1 : 1, axis === 'v' ? -1 : 1)
  ctx.drawImage(tmp, 0, 0)
  ctx.restore()
  s.texture.source.update()
  s.dirty = true
  schedulePaintSave()
}

function clipToSelection(ctx: CanvasRenderingContext2D) {
  if (!pixelSelection || !paintSession || !sessionMatchesSelection()) return
  const { x0, y0, x1, y1 } = pixelSelection
  ctx.beginPath()
  ctx.rect(
    Math.min(x0, x1) * paintSession.canvas.width,
    Math.min(y0, y1) * paintSession.canvas.height,
    Math.abs(x1 - x0) * paintSession.canvas.width,
    Math.abs(y1 - y0) * paintSession.canvas.height,
  )
  ctx.clip()
}

function isImagePaintTool(): boolean {
  return mapStore.activeMode === 'image'
    && mapEditorStore.imageTool !== 'select'
    && !!mapStore.selectedImage
}

// ─── 画笔/橡皮光标：用 Pixi 图形绘制圆圈，避免 dataURL 光标的锯齿 ───
let brushCursorGraphics: any = null
let brushCursorClient: { clientX: number; clientY: number } | null = null

function isBrushCursorActive(): boolean {
  const tool = mapEditorStore.imageTool
  return mapStore.activeMode === 'image'
    && mapEditorStore.paintMode !== 'vector'
    && (tool === 'brush' || tool === 'eraser')
}

// 绘制画布 1px 对应的世界坐标尺寸（含图片实例缩放）
function paintPixelWorldRatio(): number {
  const s = paintSession
  const img = sessionImage()
  if (!s || !img) return 1
  const scaleX = Math.abs(img.scaleX ?? img.scale ?? 1)
  return ((img.width || s.canvas.width) * scaleX) / Math.max(1, s.canvas.width)
}

function ensureBrushCursorGraphics(): any {
  if (!app || !PIXI) return null
  if (!brushCursorGraphics) {
    brushCursorGraphics = new PIXI.Graphics()
    app.stage.addChild(brushCursorGraphics)
  }
  return brushCursorGraphics
}

function redrawBrushCursor() {
  if (!isBrushCursorActive() || !brushCursorClient) {
    brushCursorGraphics?.clear()
    return
  }
  const g = ensureBrushCursorGraphics()
  if (!g) return
  const world = viewport.screenToWorld({
    clientX: brushCursorClient.clientX,
    clientY: brushCursorClient.clientY,
  } as PointerEvent)
  if (!world) return
  const scale = Math.max(0.1, viewport.currentScale.value)
  const radius = Math.max(0.5, (paintStore.brushSize / 2) * paintPixelWorldRatio())
  g.clear()
  // 双环（深/浅底都可见），线宽按视口缩放反比保持屏幕恒定
  g.circle(world.x, world.y, radius)
  g.stroke({ width: 3 / scale, color: 0x000000, alpha: 0.55 })
  g.circle(world.x, world.y, radius)
  g.stroke({ width: 1.5 / scale, color: 0xffffff, alpha: 0.95 })
}

function drawBrushCursorAt(clientX: number, clientY: number) {
  brushCursorClient = { clientX, clientY }
  if (app?.canvas) app.canvas.style.cursor = 'none'
  redrawBrushCursor()
}

function hideBrushCursor() {
  brushCursorClient = null
  brushCursorGraphics?.clear()
}

function updatePaintCursor() {
  if (!app?.canvas) return
  if (isBrushCursorActive()) {
    // 圆圈由 overlay 接管，隐藏原生指针（未移动前先保留十字）
    app.canvas.style.cursor = brushCursorClient ? 'none' : 'crosshair'
    if (brushCursorClient) redrawBrushCursor()
  } else {
    hideBrushCursor()
  }
}

/** 选取工具统一光标：位图/矢量模式下保持一致（原生箭头，隐藏画笔圆圈） */
function syncSelectCursor() {
  hideBrushCursor()
  vectorCursorPos.value = null
  viewport.setCursor('default')
  if (vectorCanvasRef.value) vectorCanvasRef.value.style.cursor = 'default'
}

/** 碰撞编辑光标：矢量画布覆盖在 Pixi 之上，两个画布必须同步 */
function setCollisionCursor(cursor: string) {
  viewport.setCursor(cursor)
  if (vectorCanvasRef.value) vectorCanvasRef.value.style.cursor = cursor
}

/** 碰撞层悬停反馈：锚点=正常指针、框内=移动、其他=十字；矩形/钢笔=十字 */
function updateCollisionCursor(world: { x: number; y: number }) {
  if (mapStore.activeMode !== 'collision') return
  if (mapEditorStore.collisionLayerTool !== 'select') {
    setCollisionCursor('crosshair')
    return
  }
  const kind = collision.hoverKindAt(world)
  setCollisionCursor(kind === 'vertex' ? 'default' : kind === 'inside' ? 'move' : 'crosshair')
}

/** 指针捕获：拖拽锚点/画碰撞时可以移出画布，事件仍回到画布，不会半路卡住 */
function capturePointer(canvas: HTMLCanvasElement | null | undefined, pointerId: number) {
  try {
    canvas?.setPointerCapture(pointerId)
  } catch { /* 部分 WebView 不支持捕获时保持原行为 */ }
}

function releasePointer(canvas: HTMLCanvasElement | null | undefined, pointerId: number) {
  try {
    if (canvas?.hasPointerCapture(pointerId)) canvas.releasePointerCapture(pointerId)
  } catch { /* ignore */ }
}

/** 碰撞叠加层尺寸与 DPR 同步（世界坐标绘制，需要与 Pixi 视口一致） */
function resizeCollisionOverlay() {
  const el = collisionOverlayRef.value
  const root = canvasRef.value
  if (!el || !root) return
  const dpr = window.devicePixelRatio || 1
  const w = Math.max(1, Math.round(root.clientWidth * dpr))
  const h = Math.max(1, Math.round(root.clientHeight * dpr))
  if (el.width !== w || el.height !== h) {
    el.width = w
    el.height = h
  }
  collision.drawOverlay()
}

function pickPaintSavePath(path: string, layerId: number): string {
  const base = (path.split('/').pop() || '图像').replace(/\.[^.]+$/, '')
  // 文件名带图层 id：不同图层即使同名/同一毫秒开始绘制也不会写到同一个文件
  return `assets/maps/${mapStore.mapData.name}/images/${base}-L${layerId}-draw-${Date.now().toString(36)}.png`
}

// 浮动选区手柄：0-3 角点，4-7 边中点（T B L R）
function scaleHandleDef(index: number) {
  if (!floatCanvas) return null
  const hw = Math.abs((floatCanvas.width * floatXf.sx) / 2)
  const hh = Math.abs((floatCanvas.height * floatXf.sy) / 2)
  const defs = [
    { dir: { x: -1, y: -1 }, axes: { x: true, y: true }, aLocal: { x: hw, y: hh } },
    { dir: { x: 1, y: -1 }, axes: { x: true, y: true }, aLocal: { x: -hw, y: hh } },
    { dir: { x: 1, y: 1 }, axes: { x: true, y: true }, aLocal: { x: -hw, y: -hh } },
    { dir: { x: -1, y: 1 }, axes: { x: true, y: true }, aLocal: { x: hw, y: -hh } },
    { dir: { x: 0, y: -1 }, axes: { x: false, y: true }, aLocal: { x: 0, y: hh } },
    { dir: { x: 0, y: 1 }, axes: { x: false, y: true }, aLocal: { x: 0, y: -hh } },
    { dir: { x: -1, y: 0 }, axes: { x: true, y: false }, aLocal: { x: hw, y: 0 } },
    { dir: { x: 1, y: 0 }, axes: { x: true, y: false }, aLocal: { x: -hw, y: 0 } },
  ]
  return defs[index] ?? null
}

type FloatHit = { kind: 'rotate' | 'move' | 'outside' } | { kind: 'scale'; index: number }

function hitTestFloat(world: { x: number; y: number }): FloatHit {
  const box = floatBoxWorld()
  if (!box) return { kind: 'outside' }
  const scale = Math.max(0.1, viewport.currentScale.value)
  // 命中区按屏幕像素恒定：8px 手柄 → 世界尺寸
  const tol = Math.max(6, 10 / scale)
  if (Math.hypot(world.x - box.rot.x, world.y - box.rot.y) <= tol * 0.8) {
    return { kind: 'rotate' }
  }
  for (let i = 0; i < box.handles.length; i++) {
    const h = box.handles[i]
    if (Math.abs(world.x - h.x) <= tol / 2 && Math.abs(world.y - h.y) <= tol / 2) {
      return { kind: 'scale', index: i }
    }
  }
  if (pointInPolygon(world, [box.tl, box.tr, box.br, box.bl])) return { kind: 'move' }
  return { kind: 'outside' }
}

// 选取工具按下：优先命中浮动选区手柄，否则在图片内开始新的框选
function handleSelectPointerDown(world: { x: number; y: number }) {
  const s = paintSession
  const img = sessionImage()
  if (!s || !img || !sessionMatchesSelection()) return
  const local = imageWorldToLocal(img, world.x, world.y)
  const p = { x: local.x * s.canvas.width, y: local.y * s.canvas.height }

  if (floatCanvas) {
    const hit = hitTestFloat(world)
    if (hit.kind === 'rotate') {
      floatStartXf = { ...floatXf }
      floatOp = 'rotate'
      return
    }
    if (hit.kind === 'scale') {
      const def = scaleHandleDef(hit.index)
      if (!def) return
      floatStartXf = { ...floatXf }
      floatOp = 'scale'
      scaleDir = { ...def.dir }
      scaleAxes = { ...def.axes }
      scaleHalf0 = {
        x: Math.abs((floatCanvas.width * floatXf.sx) / 2),
        y: Math.abs((floatCanvas.height * floatXf.sy) / 2),
      }
      const cos = Math.cos(floatXf.angle)
      const sin = Math.sin(floatXf.angle)
      scaleAnchorPx = {
        x: floatXf.cx + def.aLocal.x * cos - def.aLocal.y * sin,
        y: floatXf.cy + def.aLocal.x * sin + def.aLocal.y * cos,
      }
      const dx = p.x - scaleAnchorPx.x
      const dy = p.y - scaleAnchorPx.y
      scalePointer0 = { x: dx * cos + dy * sin, y: -dx * sin + dy * cos }
      return
    }
    if (hit.kind === 'move') {
      floatStartXf = { ...floatXf }
      floatOp = 'move'
      floatGrab = { x: p.x - floatXf.cx, y: p.y - floatXf.cy }
      return
    }
    // 点击框外：先提交浮动选区，再按点击位置开始新框选
    bakeFloatingSelection()
  }

  if (local.x < 0 || local.x > 1 || local.y < 0 || local.y > 1) {
    clearPixelSelection()
    return
  }
  floatOp = 'create'
  pixelSelection = { x0: local.x, y0: local.y, x1: local.x, y1: local.y }
  drawSelectionOverlay()
}

/** 浮动选区移动吸附：选区世界包围盒的左/中/右、上/中/下 就近对齐候选线 */
function snapFloatingMove(img: MapImageData) {
  const s = paintSession
  if (!s || !floatCanvas) return
  if (Math.abs(img.rotation ?? 0) > 1e-3) return
  const sx = img.scaleX ?? img.scale ?? 1
  const sy = img.scaleY ?? img.scale ?? 1
  if (sx <= 0 || sy <= 0) return
  const logicalW = Math.max(1e-6, (img.width || s.canvas.width) * sx)
  const logicalH = Math.max(1e-6, (img.height || s.canvas.height) * sy)
  // 浮动选区四角（画布像素）
  const hw = (floatCanvas.width * Math.abs(floatXf.sx)) / 2
  const hh = (floatCanvas.height * Math.abs(floatXf.sy)) / 2
  const cos = Math.cos(floatXf.angle)
  const sin = Math.sin(floatXf.angle)
  const corners = [[-hw, -hh], [hw, -hh], [hw, hh], [-hw, hh]].map(([lx, ly]) => ({
    x: floatXf.cx + lx * cos - ly * sin,
    y: floatXf.cy + lx * sin + ly * cos,
  }))
  // 画布像素 → 世界坐标
  const ox = img.position?.[0] ?? 0
  const oy = img.position?.[1] ?? 0
  const xs = corners.map(c => ox + (c.x / s.canvas.width) * logicalW)
  const ys = corners.map(c => oy + (c.y / s.canvas.height) * logicalH)
  const ts = Math.max(1, mapStore.mapData.tileSize)
  const offset = snapRectOffset(
    { left: Math.min(...xs), top: Math.min(...ys), right: Math.max(...xs), bottom: Math.max(...ys) },
    collectSnapLines(
      mapStore.mapData.layers,
      mapStore.mapData.width * ts,
      mapStore.mapData.height * ts,
      s.layerId,
    ),
    ts,
    snapThreshold(viewport.currentScale.value),
  )
  if (offset.dx === 0 && offset.dy === 0) return
  // 世界位移换回画布像素
  floatXf.cx += (offset.dx * s.canvas.width) / logicalW
  floatXf.cy += (offset.dy * s.canvas.height) / logicalH
}

function handleSelectPointerMove(world: { x: number; y: number }, shift: boolean): boolean {
  const s = paintSession
  const img = sessionImage()
  if (!s || !img || !sessionMatchesSelection()) return false

  if (floatOp === 'create') {
    if (pixelSelection) {
      const local = imageWorldToLocal(img, world.x, world.y)
      pixelSelection.x1 = Math.max(0, Math.min(1, local.x))
      pixelSelection.y1 = Math.max(0, Math.min(1, local.y))
      drawSelectionOverlay()
    }
    return true
  }

  if (!floatCanvas || !floatStartXf) return false
  const local = imageWorldToLocal(img, world.x, world.y)
  const p = { x: local.x * s.canvas.width, y: local.y * s.canvas.height }

  if (floatOp === 'move') {
    floatXf.cx = p.x - floatGrab.x
    floatXf.cy = p.y - floatGrab.y
    // 智能吸附：选区世界包围盒的边缘/中心就近对齐候选线
    if (mapEditorStore.smartSnap) snapFloatingMove(img)
    compositeFloat()
    return true
  }

  if (floatOp === 'rotate') {
    let angle = Math.atan2(p.y - floatXf.cy, p.x - floatXf.cx) + Math.PI / 2
    if (shift) {
      const step = Math.PI / 12
      angle = Math.round(angle / step) * step
    }
    floatXf.angle = angle
    compositeFloat()
    return true
  }

  if (floatOp === 'scale') {
    const cos = Math.cos(floatStartXf.angle)
    const sin = Math.sin(floatStartXf.angle)
    const dx = p.x - scaleAnchorPx.x
    const dy = p.y - scaleAnchorPx.y
    const p1Local = { x: dx * cos + dy * sin, y: -dx * sin + dy * cos }
    const dL = { x: p1Local.x - scalePointer0.x, y: p1Local.y - scalePointer0.y }
    // 锚定缩放：对侧边固定，中心移动 Δ/2、半尺寸增加 Δ·dir/2
    const ratioX = (scaleHalf0.x + (dL.x * scaleDir.x) / 2) / Math.max(0.001, scaleHalf0.x)
    const ratioY = (scaleHalf0.y + (dL.y * scaleDir.y) / 2) / Math.max(0.001, scaleHalf0.y)
    const signedScale = (absBase: number, ratio: number) => {
      const raw = absBase * ratio
      return (raw < 0 ? -1 : 1) * Math.max(0.02, Math.abs(raw))
    }
    if (shift) {
      // Shift 等比：两轴取同一比例，中心沿 down 时相对向量同步缩放
      const r = scaleAxes.x && scaleAxes.y
        ? (Math.abs(ratioX) > Math.abs(ratioY) ? ratioX : ratioY)
        : (scaleAxes.x ? ratioX : ratioY)
      floatXf.sx = signedScale(Math.abs(floatStartXf.sx), r)
      floatXf.sy = signedScale(Math.abs(floatStartXf.sy), r)
      const relX = floatStartXf.cx - scaleAnchorPx.x
      const relY = floatStartXf.cy - scaleAnchorPx.y
      floatXf.cx = scaleAnchorPx.x + relX * r
      floatXf.cy = scaleAnchorPx.y + relY * r
    } else {
      if (scaleAxes.x) floatXf.sx = signedScale(Math.abs(floatStartXf.sx), ratioX)
      if (scaleAxes.y) floatXf.sy = signedScale(Math.abs(floatStartXf.sy), ratioY)
      const cdx = scaleAxes.x ? dL.x / 2 : 0
      const cdy = scaleAxes.y ? dL.y / 2 : 0
      floatXf.cx = floatStartXf.cx + cdx * cos - cdy * sin
      floatXf.cy = floatStartXf.cy + cdx * sin + cdy * cos
    }
    compositeFloat()
    return true
  }

  return false
}

function handleSelectPointerUp() {
  // 会话已切到别的图层：放弃本次手势并清掉选框，避免落到错误图层
  if (!sessionMatchesSelection()) {
    resetFloatingSelection()
    return
  }
  if (floatOp === 'create') {
    const r = selectionRectPx()
    floatOp = 'none'
    if (!r || r.w < 2 || r.h < 2) {
      clearPixelSelection()
    } else {
      cutSelectionToFloat()
    }
    return
  }
  if (floatOp !== 'none') {
    floatOp = 'none'
    floatStartXf = null
    if (paintSession) {
      paintSession.dirty = true
      schedulePaintSave()
    }
    drawSelectionOverlay()
  }
}

function bindPaintTexture(sprite: any, imgData: any) {
  if (!paintSession) return
  // 精灵可能已被切层渲染销毁：绑定到销毁对象会导致画布更新不可见
  if (!sprite || sprite.destroyed) return
  const cw = paintSession.canvas.width
  const ch = paintSession.canvas.height
  const scaleX = (imgData.scaleX ?? imgData.scale ?? 1)
  const scaleY = (imgData.scaleY ?? imgData.scale ?? 1)
  const logicalW = imgData.width || cw
  const logicalH = imgData.height || ch
  sprite.texture = paintSession.texture
  sprite.anchor.set(0.5, 0.5)
  sprite.scale.set((logicalW * scaleX) / cw, (logicalH * scaleY) / ch)
  sprite.x = (imgData.position?.[0] ?? 0) + (logicalW * scaleX) / 2
  sprite.y = (imgData.position?.[1] ?? 0) + (logicalH * scaleY) / 2
  sprite.rotation = (imgData.rotation ?? 0) * Math.PI / 180
  sprite.alpha = imgData.opacity ?? 1
  paintSession.sprite = sprite
}

async function startPaintSession(): Promise<boolean> {
  // 选取工具也需要会话：框选/浮动选区都要读写图片像素
  if (mapStore.activeMode !== 'image' || !mapStore.selectedImage) return false
  const img = mapStore.selectedImage
  const layerId = mapStore.selectedImageLayerId
  if (!img || layerId < 0) return false
  if (paintSession && paintSession.layerId === layerId) return true
  await commitPaintSession(false)
  // 等待期间图层可能已切换：过期的调用直接放弃，避免旧会话覆盖新图层
  if (mapStore.selectedImageLayerId !== layerId) return false

  const PIXI_ = PIXI
  if (!PIXI_) return false
  try {
    const source = await loadImage(img.imagePath)
    if (mapStore.selectedImageLayerId !== layerId) return false
    const srcW = source.naturalWidth || source.width
    const srcH = source.naturalHeight || source.height
    // 绘制图层：可绘制范围 = 地图尺寸 + 四周出血（各半个地图），允许内容画到地图边界之外
    const isBackground = !!img.background
    const mapW = Math.max(1, mapStore.mapData.width * mapStore.mapData.tileSize)
    const mapH = Math.max(1, mapStore.mapData.height * mapStore.mapData.tileSize)
    // 已有矢量内容（底稿/矢量坐标以画布像素为准）时保持原画布原点，避免内容错位
    const hasVectorContent = !!img.vectorData || !!img.vectorBasePath || vectorLayerCache.has(layerId)
    const canRepad = isBackground && !hasVectorContent
    const offsetX = img.position?.[0] ?? 0
    const offsetY = img.position?.[1] ?? 0
    // 出血区 = 半个地图，上限 512px（避免大尺寸地图导致画布过大、内存暴涨）
    const padX = Math.min(Math.round(mapW / 2), 512)
    const padY = Math.min(Math.round(mapH / 2), 512)
    // 已有内容平移到新画布：世界坐标保持不变（世界原点落在画布 padX/padY 处）
    // 矢量图层不做平移，直接沿用原画布原点
    const drawX = canRepad ? padX + offsetX : 0
    const drawY = canRepad ? padY + offsetY : 0
    let canvasW = srcW
    let canvasH = srcH
    if (isBackground) {
      if (canRepad) {
        // 背景画板严格等于「地图尺寸 + 四周出血」：地图缩小时画板同步收缩，
        // 超出新画板的内容被裁掉（与 Tiled 调整地图尺寸行为一致）
        canvasW = mapW + padX * 2
        canvasH = mapH + padY * 2
      } else {
        // 矢量内容以画板像素坐标为基准：画板只扩不缩，避免矢量路径错位
        canvasW = Math.max(srcW, mapW)
        canvasH = Math.max(srcH, mapH)
      }
    }
    const canvas = document.createElement('canvas')
    canvas.width = canvasW
    canvas.height = canvasH
    if (canvas.width <= 0 || canvas.height <= 0) return false
    canvas.getContext('2d')!.drawImage(source, drawX, drawY)
    if (isBackground && (canvasW !== srcW || canvasH !== srcH || drawX !== 0 || drawY !== 0)) {
      img.width = canvasW
      img.height = canvasH
      // 只有重新排版时才移动原点；矢量图层沿用原原点，防止底稿与矢量路径错位
      if (canRepad) img.position = [-padX, -padY]
      img.scaleX = 1
      img.scaleY = 1
      img.scale = 1
    }
    const texture = PIXI_.Texture.from(canvas)
    texture.source.scaleMode = currentScaleMode
    let sprite: any = null
    const container = layerContainers.get(layerId)
    for (const child of container?.children ?? []) {
      if (child instanceof PIXI_.Sprite) { sprite = child; break }
    }
    const geometryChanged = isBackground && (canvasW !== srcW || canvasH !== srcH || drawX !== 0 || drawY !== 0)
    paintSession = {
      layerId,
      mapName: mapStore.mapData.name,
      canvas,
      texture,
      sprite,
      lastPoint: null,
      startPoint: null,
      snapshot: null,
      // 画布几何变化（加了出血区）时必须立刻落盘，否则存盘里的尺寸/位置与 PNG 不一致
      dirty: geometryChanged,
      savePath: pickPaintSavePath(img.imagePath, layerId),
    }
    if (sprite) bindPaintTexture(sprite, img)
    if (geometryChanged) schedulePaintSave()
    paintUndo = []
    paintRedo = []
    bumpPaintHistory()
    // 无条件重建该图层精灵：切层时渲染与会话创建存在竞态，
    // 若屏幕精灵绑定的是文件纹理，后续框选/绘制更新就不会显示（看起来像"残影"）
    scheduleRender()
    return true
  } catch (e) {
    console.error('[MapCanvas] 启动绘制失败:', e)
    return false
  }
}

function paintCtx(): CanvasRenderingContext2D | null {
  return paintSession?.canvas.getContext('2d') ?? null
}

function paintBrushAt(px: number, py: number, from: { x: number; y: number } | null) {
  const s = paintSession
  const ctx = paintCtx()
  if (!s || !ctx) return
  ctx.save()
  clipToSelection(ctx)
  if (mapEditorStore.imageTool === 'eraser') {
    ctx.globalCompositeOperation = 'destination-out'
    ctx.strokeStyle = 'rgba(0, 0, 0, 1)'
  } else {
    ctx.strokeStyle = rgbaCss(paintStore.fillColor, paintStore.opacity)
  }
  ctx.lineWidth = paintStore.brushSize
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  // 单击无移动也要留下一个圆点（与角色绘制一致）
  ctx.beginPath()
  if (from) {
    ctx.moveTo(from.x, from.y)
    ctx.lineTo(px, py)
  } else {
    ctx.moveTo(px, py)
    ctx.lineTo(px + 0.01, py + 0.01)
  }
  ctx.stroke()
  ctx.restore()
}

// Shift 约束：直线 45° 步进，矩形/椭圆等宽高（与角色绘制一致）
function constrainPoint(p: { x: number; y: number }, start: { x: number; y: number }, shift: boolean) {
  if (!shift) return p
  const dx = p.x - start.x
  const dy = p.y - start.y
  if (mapEditorStore.imageTool === 'line') {
    const angle = Math.atan2(dy, dx)
    const step = Math.PI / 4
    const snapped = Math.round(angle / step) * step
    const len = Math.hypot(dx, dy)
    return {
      x: start.x + Math.cos(snapped) * len,
      y: start.y + Math.sin(snapped) * len,
    }
  }
  const s = Math.max(Math.abs(dx), Math.abs(dy))
  return {
    x: start.x + (dx < 0 ? -s : s),
    y: start.y + (dy < 0 ? -s : s),
  }
}

function restorePaintSnapshot() {
  const s = paintSession
  const ctx = paintCtx()
  if (s?.snapshot && ctx) ctx.putImageData(s.snapshot, 0, 0)
}

function drawShapePreview(px: number, py: number, shift = false) {
  const s = paintSession
  const ctx = paintCtx()
  if (!s || !ctx || !s.startPoint) return
  restorePaintSnapshot()
  const end = constrainPoint({ x: px, y: py }, s.startPoint, shift)
  paintShapeInto(ctx, s.startPoint, end)
}

/**
 * 把形状按当前工具/配色画进指定 ctx（start/end 为画布像素坐标）。
 * applyClip = 是否套用当前像素选区裁剪（浮动对象渲染时沿同一坐标系平移，裁剪依然正确）。
 */
function paintShapeInto(
  ctx: CanvasRenderingContext2D,
  start: { x: number; y: number },
  end: { x: number; y: number },
  applyClip = true
) {
  const tool = mapEditorStore.imageTool
  // 位图形状：实心 / 轮廓 二选一（直线始终是描边）
  const fillOn = tool !== 'line' && paintStore.shapeStyle === 'fill'
  const strokeOn = tool === 'line' || paintStore.shapeStyle === 'outline'
  ctx.save()
  if (applyClip) clipToSelection(ctx)
  ctx.lineWidth = tool === 'line'
    ? Math.max(1, paintStore.lineWidth)
    : paintStore.strokeWidth > 0 ? paintStore.strokeWidth : 4
  ctx.lineJoin = 'round'
  ctx.lineCap = 'round'
  ctx.beginPath()
  if (tool === 'line') {
    ctx.moveTo(start.x, start.y)
    ctx.lineTo(end.x, end.y)
  } else if (tool === 'rect') {
    ctx.rect(
      Math.min(start.x, end.x), Math.min(start.y, end.y),
      Math.abs(end.x - start.x), Math.abs(end.y - start.y),
    )
  } else if (tool === 'ellipse') {
    ctx.ellipse(
      (start.x + end.x) / 2, (start.y + end.y) / 2,
      Math.abs(end.x - start.x) / 2, Math.abs(end.y - start.y) / 2,
      0, 0, Math.PI * 2,
    )
  }
  if (fillOn) {
    ctx.fillStyle = rgbaCss(paintStore.fillColor, paintStore.opacity)
    ctx.fill()
  }
  if (strokeOn) {
    // 轮廓与实心共用绘制色（位图模式只暴露一个颜色）
    ctx.strokeStyle = rgbaCss(paintStore.fillColor, paintStore.opacity)
    ctx.stroke()
  }
  ctx.restore()
}

function floodFillAt(px: number, py: number) {
  const s = paintSession
  const ctx = paintCtx()
  if (!s || !ctx) return
  const w = s.canvas.width
  const h = s.canvas.height
  const x0 = Math.floor(px)
  const y0 = Math.floor(py)
  if (x0 < 0 || y0 < 0 || x0 >= w || y0 >= h) return
  // 有框选时只在选区内填充
  let minX = 0, minY = 0, maxX = w - 1, maxY = h - 1
  if (pixelSelection) {
    minX = Math.floor(Math.min(pixelSelection.x0, pixelSelection.x1) * w)
    maxX = Math.ceil(Math.max(pixelSelection.x0, pixelSelection.x1) * w) - 1
    minY = Math.floor(Math.min(pixelSelection.y0, pixelSelection.y1) * h)
    maxY = Math.ceil(Math.max(pixelSelection.y0, pixelSelection.y1) * h) - 1
  }
  const image = ctx.getImageData(0, 0, w, h)
  const d = image.data
  const startIdx = (y0 * w + x0) * 4
  const target = [d[startIdx], d[startIdx + 1], d[startIdx + 2], d[startIdx + 3]]
  const fill = hexToRgba(paintStore.fillColor, paintStore.opacity)
  const fa = Math.round(fill.a * 255)
  if (target[0] === fill.r && target[1] === fill.g && target[2] === fill.b && target[3] === fa) return

  const stack: [number, number][] = [[x0, y0]]
  while (stack.length > 0) {
    const [x, y] = stack.pop()!
    if (x < 0 || y < 0 || x >= w || y >= h) continue
    if (x < minX || x > maxX || y < minY || y > maxY) continue
    const i = (y * w + x) * 4
    if (d[i] !== target[0] || d[i + 1] !== target[1] || d[i + 2] !== target[2] || d[i + 3] !== target[3]) continue
    d[i] = fill.r; d[i + 1] = fill.g; d[i + 2] = fill.b; d[i + 3] = fa
    stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1])
  }
  ctx.putImageData(image, 0, 0)
}

function pushPaintUndo() {
  const ctx = paintCtx()
  if (!paintSession || !ctx) return
  paintUndo.push(ctx.getImageData(0, 0, paintSession.canvas.width, paintSession.canvas.height))
  if (paintUndo.length > PAINT_UNDO_LIMIT) paintUndo.shift()
  paintRedo = []
  bumpPaintHistory()
}

/** 钢笔预览尺寸换算：屏幕像素 → 画布像素（视图缩放 × 图片实例缩放） */
function paintPenZoom(): number {
  const img = sessionImage()
  const sx = Math.abs(img?.scaleX ?? img?.scale ?? 1)
  return Math.max(0.1, viewport.currentScale.value * sx)
}

/**
 * 位图模式钢笔（自定义形状）：交互外观与矢量钢笔一致（锚点方块/首锚闭合提示/固定预览色），
 * 但不切换模式——闭合后按当前填充/描边设置直接烤成像素写回当前图片图层。
 */
const bitmapPen = createBitmapPen({
  ctx: paintCtx,
  snapshot: () => {
    const s = paintSession
    const ctx = paintCtx()
    if (!s || !ctx) return null
    return ctx.getImageData(0, 0, s.canvas.width, s.canvas.height)
  },
  restore: (img) => {
    paintCtx()?.putImageData(img, 0, 0)
  },
  pushHistory: pushPaintUndo,
  popHistory: () => {
    paintUndo.pop()
    bumpPaintHistory()
  },
  zoom: paintPenZoom,
  style: () => ({
    color: rgbaCss(paintStore.fillColor, paintStore.opacity),
    mode: paintStore.shapeStyle === 'outline' ? 'outline' : 'fill',
    lineWidth: paintStore.strokeWidth > 0 ? paintStore.strokeWidth : 4,
  }),
  clip: clipToSelection,
  onPreview: () => {
    paintSession?.texture.source.update()
  },
  onFinish: (bounds, origin, paint) => {
    // 闭合完成后自动进入编辑选框（与直线/矩形/椭圆一致）
    const s = paintSession
    if (!s) return
    const x = Math.max(0, Math.floor(bounds.x))
    const y = Math.max(0, Math.floor(bounds.y))
    const x1 = Math.min(s.canvas.width, Math.ceil(bounds.x + bounds.w))
    const y1 = Math.min(s.canvas.height, Math.ceil(bounds.y + bounds.h))
    activateShapeFloat({ x, y, w: x1 - x, h: y1 - y }, origin, paint)
  },
  onDirty: () => {
    const s = paintSession
    if (!s) return
    s.dirty = true
    s.texture.source.update()
    schedulePaintSave()
  },
})

function toCanvasPoint(world: { x: number; y: number }): { x: number; y: number } | null {
  const s = paintSession
  const img = sessionImage()
  if (!s || !img || !sessionMatchesSelection()) return null
  const local = imageWorldToLocal(img, world.x, world.y)
  return { x: local.x * s.canvas.width, y: local.y * s.canvas.height }
}

function paintBegin(world: { x: number; y: number }) {
  // 有浮动选区先落定，避免笔画与浮动内容叠加混乱
  if (floatCanvas) bakeFloatingSelection()
  const s = paintSession
  const ctx = paintCtx()
  const p = toCanvasPoint(world)
  if (!s || !ctx || !p) return
  pushPaintUndo()
  const tool = mapEditorStore.imageTool
  if (tool === 'fill') {
    floodFillAt(p.x, p.y)
    s.dirty = true
    s.texture.source.update()
    schedulePaintSave()
    return
  }
  if (tool === 'brush' || tool === 'eraser') {
    paintBrushAt(p.x, p.y, null)
    s.lastPoint = p
  } else {
    s.snapshot = ctx.getImageData(0, 0, s.canvas.width, s.canvas.height)
    s.startPoint = p
    s.lastPoint = p
  }
  s.dirty = true
  s.texture.source.update()
}

function paintMove(world: { x: number; y: number }, shift = false) {
  const s = paintSession
  const p = toCanvasPoint(world)
  if (!s || !p) return
  const tool = mapEditorStore.imageTool
  if (tool === 'brush' || tool === 'eraser') {
    paintBrushAt(p.x, p.y, s.lastPoint)
    s.lastPoint = p
  } else {
    drawShapePreview(p.x, p.y, shift)
    s.lastPoint = p
  }
  s.dirty = true
  s.texture.source.update()
}

/** 形状内容包围盒（画布像素，含描边外扩）：创建后自动建立编辑选框用 */
function shapeRectPx(
  start: { x: number; y: number },
  end: { x: number; y: number }
): { x: number; y: number; w: number; h: number } | null {
  const s = paintSession
  if (!s) return null
  const lw = mapEditorStore.imageTool === 'line'
    ? Math.max(1, paintStore.lineWidth)
    : paintStore.strokeWidth > 0 ? paintStore.strokeWidth : 4
  const pad = Math.ceil(lw / 2) + 1
  const x = Math.max(0, Math.floor(Math.min(start.x, end.x) - pad))
  const y = Math.max(0, Math.floor(Math.min(start.y, end.y) - pad))
  const x1 = Math.min(s.canvas.width, Math.ceil(Math.max(start.x, end.x) + pad))
  const y1 = Math.min(s.canvas.height, Math.ceil(Math.max(start.y, end.y) + pad))
  return { x, y, w: x1 - x, h: y1 - y }
}

/**
 * 新画的图形 → 独立浮动对象（Scratch 行为）：
 * 图层画布恢复成「落笔前底稿」，新图形按相同样式单独渲染到浮动画布。
 * 这样拖动/缩放/旋转时只移动图形本身，不会把选框里原有的像素一起带走；
 * 点空白或切工具时才把浮动图形合成回图层。
 */
function floatShapeFromPaint(
  rect: { x: number; y: number; w: number; h: number },
  origin: ImageData,
  paint: (target: CanvasRenderingContext2D) => void
) {
  const s = paintSession
  const ctx = paintCtx()
  if (!s || !ctx || !sessionMatchesSelection() || rect.w < 2 || rect.h < 2) {
    clearPixelSelection()
    return
  }
  const fc = makeOffscreenCanvas(rect.w, rect.h)
  const fctx = fc.getContext('2d')!
  fctx.save()
  fctx.translate(-rect.x, -rect.y) // 绘制函数用画布像素坐标，平移进浮动画布
  paint(fctx)
  fctx.restore()
  // 图层恢复成落笔前底稿（图形不再占图层像素，移动后能露出下方原有内容）
  const base = makeOffscreenCanvas(origin.width, origin.height)
  base.getContext('2d')!.putImageData(origin, 0, 0)
  floatBaseCanvas = base
  floatCanvas = fc
  floatXf = { cx: rect.x + rect.w / 2, cy: rect.y + rect.h / 2, sx: 1, sy: 1, angle: 0 }
  pixelSelection = null
  floatOp = 'none'
  floatStartXf = null
  floatOrigin = origin
  mapEditorStore.hasPixelSelection = true
  transform.removeTransformBox()
  compositeFloat()
  s.dirty = true
  schedulePaintSave()
}

/** 图形创建完立即进入编辑选框（Scratch 行为）：移动/缩放/旋转，点空白或切工具落定 */
function activateShapeFloat(
  rect: { x: number; y: number; w: number; h: number } | null,
  origin: ImageData | null,
  paint: ((target: CanvasRenderingContext2D) => void) | null = null
) {
  if (!rect || rect.w < 2 || rect.h < 2) return
  if (origin && paint) {
    floatShapeFromPaint(rect, origin, paint)
    return
  }
  // 兜底（拿不到落笔前底稿）：按矩形切图
  cutRectToFloat(rect, origin, false)
}

function paintEnd(world?: { x: number; y: number }, shift = false) {
  const s = paintSession
  if (!s) return
  if (s.startPoint) {
    const start = s.startPoint
    const origin = s.snapshot
    const p = world ? toCanvasPoint(world) : s.lastPoint
    restorePaintSnapshot()
    if (!p || !origin) {
      paintUndo.pop()
      bumpPaintHistory()
    } else {
      const end = constrainPoint(p, start, shift)
      const isClick = Math.abs(end.x - start.x) < 0.5 && Math.abs(end.y - start.y) < 0.5
      if (isClick) {
        // 零尺寸空点击：丢弃本次撤销记录，不产生可见变更
        paintUndo.pop()
        bumpPaintHistory()
      } else {
        drawShapePreview(p.x, p.y, shift)
        s.dirty = true
        s.texture.source.update()
        activateShapeFloat(shapeRectPx(start, end), origin, (target) =>
          paintShapeInto(target, start, end)
        )
      }
    }
  }
  s.lastPoint = null
  s.startPoint = null
  s.snapshot = null
  schedulePaintSave()
}

function schedulePaintSave() {
  if (paintSaveTimer) clearTimeout(paintSaveTimer)
  // 位图内容变更统一走这里：顺带刷新当前图层缩略图（防抖合并）
  scheduleLayerThumbUpdate()
  paintSaveTimer = setTimeout(() => {
    paintSaveTimer = null
    if (paintSession) void flushPaintSave(paintSession, false)
  }, 400)
}

async function flushPaintSave(session: ImagePaintSession, finalize: boolean) {
  if (!session.dirty) return
  session.dirty = false
  const root = projectStore.root
  if (!root) return
  try {
    const blob: Blob | null = await new Promise(r => session.canvas.toBlob(r, 'image/png'))
    if (!blob) return
    await invoke('create_dir', { path: `${root}/assets/maps/${session.mapName}/images` })
    await invoke('write_binary', {
      path: `${root}/${session.savePath}`,
      data: Array.from(new Uint8Array(await blob.arrayBuffer())),
    })
    if (mapStore.mapData.name === session.mapName) {
      const layer = mapStore.mapData.layers.find(l => l.id === session.layerId)
      if (layer && layer.type === 'image') {
        // 图层改指向新的绘制文件，旧路径的解析缓存要丢弃，避免切回时读到旧图
        resolvedPathCache.delete(layer.image.imagePath)
        layer.image.imagePath = session.savePath
        // 路径变了但画面仍是这块会话画布：同步签名，避免重渲染时从磁盘重载出现闪烁
        syncLayerRenderKey(session.layerId)
      }
    }
    resolvedPathCache.delete(session.savePath)
    if (finalize) mapStore.imageRevision++
  } catch (e) {
    session.dirty = true
    console.error('[MapCanvas] 保存绘制结果失败:', e)
  }
}

async function commitPaintSession(finalize = true) {
  // 未闭合的钢笔半成品不落盘（还原到底稿，同时回滚起笔压的撤销步）
  bitmapPen.cancel()
  if (paintSaveTimer) {
    clearTimeout(paintSaveTimer)
    paintSaveTimer = null
  }
  // 浮动选区先合成落定，保证落盘内容与画面一致
  if (floatCanvas) bakeFloatingSelection()
  const session = paintSession
  if (!session) return
  paintSession = null
  await flushPaintSave(session, finalize)
  // 切层时强制刷新一次渲染：让上一图层的精灵从磁盘重新加载，避免残留会话纹理
  if (!finalize) mapStore.imageRevision++
  paintUndo = []
  paintRedo = []
  bumpPaintHistory()
  resetFloatingSelection()
}

function undoPaint() {
  // 钢笔进行中：先整步丢弃半成品（与矢量钢笔一致），不打断到上一步
  if (bitmapPen.isActive()) {
    bitmapPen.cancel()
    return
  }
  const s = paintSession
  const ctx = paintCtx()
  if (!s || !ctx || paintUndo.length === 0) return
  resetFloatingSelection()
  paintRedo.push(ctx.getImageData(0, 0, s.canvas.width, s.canvas.height))
  ctx.putImageData(paintUndo.pop()!, 0, 0)
  bumpPaintHistory()
  s.texture.source.update()
  s.dirty = true
  schedulePaintSave()
}

function redoPaint() {
  if (bitmapPen.isActive()) {
    bitmapPen.cancel()
    return
  }
  const s = paintSession
  const ctx = paintCtx()
  if (!s || !ctx || paintRedo.length === 0) return
  resetFloatingSelection()
  paintUndo.push(ctx.getImageData(0, 0, s.canvas.width, s.canvas.height))
  ctx.putImageData(paintRedo.pop()!, 0, 0)
  bumpPaintHistory()
  s.texture.source.update()
  s.dirty = true
  schedulePaintSave()
}

// --- 交互 composables ---
const viewport = useMapViewport({
  canvasRef,
  getApp: () => app,
  getPIXI: () => PIXI,
  onZoom: () => {
    collision.drawOverlay()
    // 选区手柄按屏幕尺寸恒定，缩放后重绘
    drawSelectionOverlay()
    // 画笔圆圈光标随缩放变化
    redrawBrushCursor()
    // 矢量覆盖层随视口缩放
    syncVectorGeometry()
    // 缩放停下后按新倍率重拍上方图层快照，静置时保持清晰
    scheduleUpperSnapshotRefresh()
  },
})

const transform = useImageTransform({
  getApp: () => app,
  getPIXI: () => PIXI,
  getLayerContainers: () => layerContainers,
  screenToWorld: viewport.screenToWorld,
  onRenderRequest: () => scheduleRender(),
})

const collision = useCollisionLayerEditor({
  getApp: () => app,
  getScale: () => viewport.currentScale.value,
  getOverlayCanvas: () => collisionOverlayRef.value ?? null,
})

const painter = useTilePainter({
  getApp: () => app,
  getPIXI: () => PIXI,
  renderTile,
  getTileSprite: (key: string) => tileSprites.get(key),
  getTileTexture,
  onTilePainted: (x, y, tileId) => emit('tile-painted', x, y, tileId),
  onTileErased: (x, y) => emit('tile-erased', x, y),
  onRenderRequest: () => scheduleRender(),
})

// ====== 矢量绘制（覆盖层 + Paper.js 引擎） ======

/** 按图层 id 取图像数据：切换图层的瞬间 selectedImage 已指向新层，必须按会话所属图层取 */
function imageByLayerId(layerId: number): MapImageData | null {
  const layer = mapStore.mapData.layers.find(l => l.id === layerId)
  return layer && layer.type === 'image' ? layer.image : null
}

/** 当前绘制会话所属图层的图像数据（没有会话时退回选中图层） */
function sessionImage(): MapImageData | null {
  const s = paintSession
  return s ? imageByLayerId(s.layerId) : mapStore.selectedImage
}

/** 当前图片图层的绘制画布几何（图片像素坐标系） */
function vectorFrame(): MapVectorFrame | null {
  const s = paintSession
  // 会话所属图层优先：切图层时矢量内容仍属于旧图层，避免错位到新图层
  const img = s ? imageByLayerId(s.layerId) : mapStore.selectedImage
  if (!img || !s || !app || !canvasRef.value) return null
  const rect = canvasRef.value.getBoundingClientRect()
  return {
    image: img,
    canvas: s.canvas,
    stageX: app.stage.x,
    stageY: app.stage.y,
    scale: viewport.currentScale.value,
    rootRect: { left: rect.left, top: rect.top },
  }
}

// 卸载早于 usePaperScope 的 detach 收口：先把矢量内容烘进像素，避免 scope 销毁后丢内容
onBeforeUnmount(() => {
  if (!vectorActive.value) return
  bakeVectorRasterSync()
  vectorActive.value = false
})

const mapVectorViewport = createMapVectorViewport(vectorFrame)

/**
 * 矢量引擎的智能吸附配置：把世界坐标候选线换算到画布像素坐标。
 * 图层旋转/镜像时不吸附（轴对齐候选线无法准确换算）。
 */
function vectorSmartSnap(): { lines: { xs: number[]; ys: number[] }; grid: number; threshold: number } | null {
  if (!mapEditorStore.smartSnap) return null
  const s = paintSession
  if (!s) return null
  const img = imageByLayerId(s.layerId)
  if (!img) return null
  if (Math.abs(img.rotation ?? 0) > 1e-3) return null
  const sx = img.scaleX ?? img.scale ?? 1
  const sy = img.scaleY ?? img.scale ?? 1
  if (sx < 0 || sy < 0) return null
  const logicalW = Math.max(1e-6, (img.width || s.canvas.width) * sx)
  const logicalH = Math.max(1e-6, (img.height || s.canvas.height) * sy)
  const pxPerWorldX = s.canvas.width / logicalW
  const pxPerWorldY = s.canvas.height / logicalH
  const ts = Math.max(1, mapStore.mapData.tileSize)
  const world = collectSnapLines(
    mapStore.mapData.layers,
    mapStore.mapData.width * ts,
    mapStore.mapData.height * ts,
    s.layerId,
  )
  const ox = img.position?.[0] ?? 0
  const oy = img.position?.[1] ?? 0
  return {
    lines: {
      xs: world.xs.map(x => (x - ox) * pxPerWorldX),
      ys: world.ys.map(y => (y - oy) * pxPerWorldY),
    },
    grid: ts * pxPerWorldX,
    threshold: snapThreshold(viewport.currentScale.value) * pxPerWorldX,
  }
}

const vectorEngine = usePaperScope(
  vectorCanvasRef,
  vectorCanvasRef,
  {
    onFrameSwitched: () => {},
    // 每笔/每次矢量操作结束：只刷新当前图层缩略图
    onContentChanged: () => scheduleLayerThumbUpdate(),
    bitmapLayer: {
      getFrame: () => null,
      transformFrame: () => {},
      clearFrame: () => {},
    },
  },
  { viewport: mapVectorViewport, singleFrame: true, proxy: false, smartSnap: vectorSmartSnap }
)

/** 同步矢量视口矩阵 / 裁剪 / 叠加层投影；并让 handle 尺寸按屏幕恒定 */
function syncVectorGeometry() {
  if (!vectorActive.value) return
  const s = paintSession
  if (s) {
    // 画板尺寸随绘制画布（背景图可能随地图扩大）
    if (paintStore.artboardWidth !== s.canvas.width) paintStore.artboardWidth = s.canvas.width
    if (paintStore.artboardHeight !== s.canvas.height) paintStore.artboardHeight = s.canvas.height
  }
  const m = computeMapVectorMatrix(vectorFrame())
  vectorMatrix.value = m
  if (m) {
    const det = Math.abs(m.a * m.d - m.b * m.c)
    paintStore.zoom = Math.max(0.1, Math.sqrt(Math.max(det, 0.0001)))
  }
  vectorEngine.refreshView()
}

async function enterVectorMode(): Promise<boolean> {
  // 进入矢量模式前丢弃位图钢笔半成品（还没闭合的形状不应被烘焙进像素）
  bitmapPen.cancel()
  // 图形刚创建后的自动编辑选框：切换绘制模式同样算最终确定（先烘焙为像素再走矢量）
  bakeFloatingSelection()
  // 只有已处于"目标图层的矢量模式"时才能直接复用；
  // 否则必须先退出旧图层，避免新图层沿用上一图层的矢量内容
  if (vectorActive.value && paintSession?.layerId === mapStore.selectedImageLayerId) {
    paintStore.mode = 'vector'
    return true
  }
  if (enteringVector) return false
  if (vectorActive.value) await exitVectorMode(false)
  enteringVector = true
  try {
    return await enterVectorModeInner()
  } finally {
    enteringVector = false
  }
}

async function enterVectorModeInner(): Promise<boolean> {
  if (mapStore.activeMode !== 'image') return false
  // 先切到矢量模式：此时矢量画布可能已经挂载，Paper 的指针处理依赖 mode==='vector'
  paintStore.mode = 'vector'
  if (!mapStore.selectedImage && mapStore.activeLayer?.type === 'image') {
    mapStore.selectImage(mapStore.activeLayer.id)
  }
  if (!mapStore.selectedImage) return false
  if (!paintSession) {
    const ok = await startPaintSession()
    if (!ok) return false
  }
  const s = paintSession
  if (!s) return false
  // 会话必须属于当前选中图层，否则说明切换尚未完成，放弃以免串层
  if (s.layerId !== mapStore.selectedImageLayerId) return false
  const img = imageByLayerId(s.layerId)
  if (!img) return false
  // 记录该图层的编辑模式，切走再切回仍进入矢量
  img.paintMode = 'vector'
  // 恢复矢量图层：优先用内存缓存底稿，其次用存档里的 vectorBasePath
  const cached = cachedVectorEntry(s.layerId, img)
  if (cached) {
    const ctx = s.canvas.getContext('2d')!
    ctx.clearRect(0, 0, s.canvas.width, s.canvas.height)
    ctx.drawImage(cached.base, 0, 0)
    s.texture.source.update()
  } else if (img.vectorBasePath) {
    try {
      const baseImg = await loadImage(img.vectorBasePath)
      const ctx = s.canvas.getContext('2d')!
      ctx.clearRect(0, 0, s.canvas.width, s.canvas.height)
      ctx.drawImage(baseImg, 0, 0, s.canvas.width, s.canvas.height)
      s.texture.source.update()
    } catch { /* 底稿丢失时退回当前预览图 */ }
  }
  const initialJson = cached?.json ?? img.vectorData ?? null
  if (!vectorStoreSnapshot) {
    vectorStoreSnapshot = {
      artboardWidth: paintStore.artboardWidth,
      artboardHeight: paintStore.artboardHeight,
      zoom: paintStore.zoom,
      panX: paintStore.panX,
      panY: paintStore.panY,
    }
  }
  paintStore.mode = 'vector'
  paintStore.artboardWidth = s.canvas.width
  paintStore.artboardHeight = s.canvas.height
  // 工具状态与地图工具栏对齐（避免沿用角色绘制页上次的工具）
  paintStore.setTool(mapEditorStore.imageTool)
  ensurePaintFont()
  hideBrushCursor()
  vectorCursorPos.value = null
  vectorActive.value = true
  await nextTick()
  syncVectorGeometry()
  if (!vectorEngine.isReady()) {
    await new Promise(r => requestAnimationFrame(r))
  }
  vectorEngine.loadProjectJson(initialJson)
  // 进入矢量模式后把「本图层之上」的图层叠回矢量画布之上（不能因选中而置顶）
  refreshUpperLayerSnapshot()
  if ((mapEditorStore.imageTool === 'brush' || mapEditorStore.imageTool === 'eraser')
    && !vectorCursorPos.value && vectorCanvasRef.value) {
    vectorCanvasRef.value.style.cursor = 'crosshair'
  } else if (mapEditorStore.imageTool === 'select') {
    syncSelectCursor()
  }
  return true
}

/** 把矢量 project 栅格化并叠加进图片像素（同步部分；落盘由调用方 flush） */
function bakeVectorRasterSync(): ImagePaintSession | null {
  const s = paintSession
  if (!vectorActive.value || !s) return null
  vectorEngine.penCancel() // 烘焙前不保留进行中的半成品钢笔形状
  const raster = vectorEngine.getFrameRaster(0)
  if (raster) {
    pushPaintUndo()
    const ctx = paintCtx()
    if (ctx) {
      ctx.save()
      ctx.setTransform(1, 0, 0, 1, 0, 0)
      ctx.drawImage(raster, 0, 0, s.canvas.width, s.canvas.height)
      ctx.restore()
      s.texture.source.update()
      s.dirty = true
    }
  }
  vectorEngine.clearAllForBake()
  return s
}

async function commitVectorToPixels() {
  const s = bakeVectorRasterSync()
  if (s) await flushPaintSave(s, true)
}

/** 写一份 PNG 到地图图片目录，返回项目相对路径 */
async function writeVectorBaseFile(canvas: HTMLCanvasElement, fileName: string): Promise<string | null> {
  const root = projectStore.root
  if (!root) return null
  const mapName = mapStore.mapData.name
  const blob: Blob | null = await new Promise(r => canvas.toBlob(r, 'image/png'))
  if (!blob) return null
  const path = `assets/maps/${mapName}/images/${fileName}`
  try {
    await invoke('create_dir', { path: `${root}/assets/maps/${mapName}/images` })
    await invoke('write_binary', {
      path: `${root}/${path}`,
      data: Array.from(new Uint8Array(await blob.arrayBuffer())),
    })
    resolvedPathCache.delete(path)
    return path
  } catch (e) {
    console.error('[MapCanvas] 保存矢量底稿失败:', e)
    return null
  }
}

/**
 * 暂存矢量图层：保留 Paper JSON 与非矢量底稿，并把“底稿+矢量栅格”合成为预览 PNG。
 * 切换图层/保存时调用，之后切回该图层仍可继续矢量编辑。
 */
async function stashVectorLayer() {
  const s = paintSession
  // 关键：切换图层的瞬间 selectedImage 已指向新图层，
  // 必须按会话所属图层写回，否则会把旧图层的矢量内容写进新图层（图层串内容）
  const img = s ? imageByLayerId(s.layerId) : null
  if (!vectorActive.value || !s || !img) return
  const json = vectorEngine.getProjectJson()
  if (!json) {
    vectorEngine.clearAllForBake()
    return
  }
  const base = makeOffscreenCanvas(s.canvas.width, s.canvas.height)
  base.getContext('2d')!.drawImage(s.canvas, 0, 0)
  vectorLayerCache.set(s.layerId, { json, base, image: img })
  img.vectorData = json
  img.paintMode = 'vector'
  const baseName = `${(img.imagePath.split('/').pop() || '图像').replace(/\.[^.]+$/, '')}-L${s.layerId}-vecbase-${Date.now().toString(36)}.png`
  const basePath = await writeVectorBaseFile(base, baseName)
  if (basePath) img.vectorBasePath = basePath
  // 预览 PNG（底稿 + 矢量）供其他图层编辑时显示
  const raster = vectorEngine.getFrameRaster(0)
  const ctx = paintCtx()
  if (ctx && raster) {
    ctx.save()
    ctx.setTransform(1, 0, 0, 1, 0, 0)
    ctx.drawImage(raster, 0, 0, s.canvas.width, s.canvas.height)
    ctx.restore()
    s.texture.source.update()
    s.dirty = true
    await flushPaintSave(s, true)
  }
  vectorEngine.clearAllForBake()
}

/** 明确切到位图：矢量内容永久烘焙，移除可再编辑的矢量数据 */
async function convertVectorToBitmap() {
  // 先记住会话所属图层：烘焙过程中选中图层可能已经切走
  const layerId = paintSession?.layerId
  await commitVectorToPixels()
  const img = layerId !== undefined ? imageByLayerId(layerId) : null
  if (img) {
    img.vectorData = undefined
    img.vectorBasePath = undefined
    img.paintMode = 'bitmap'
  }
  if (layerId !== undefined) vectorLayerCache.delete(layerId)
}

async function exitVectorMode(switchUiToBitmap = true) {
  if (!vectorActive.value || vectorExiting) return
  vectorExiting = true
  try {
    if (switchUiToBitmap) await convertVectorToBitmap()
    else await stashVectorLayer()
    vectorActive.value = false
    paintStore.mode = switchUiToBitmap ? 'bitmap' : 'vector'
    // 退出矢量模式：上方图层快照作废，图层容器回到 Pixi 舞台
    if (upperSnapshotTimer) {
      clearTimeout(upperSnapshotTimer)
      upperSnapshotTimer = null
    }
    clearUpperSnapshot()
    if (switchUiToBitmap) mapEditorStore.setPaintMode('bitmap')
    paintStore.vectorSelBox = null
    paintStore.vectorSelectedCount = 0
    paintStore.vectorContent = false
    // 框选矩形也一并收起，避免切模式/切层后残留
    paintStore.selection = null
    paintStore.textEdit = null
    vectorMatrix.value = null
    vectorCursorPos.value = null
    // 矢量专属工具回退到位图可用工具
    const tool = mapEditorStore.imageTool
    if (tool === 'reshape' || tool === 'text' || tool === 'eyedropper') {
      mapEditorStore.setImageTool('brush')
      paintStore.setTool('brush')
    } else {
      paintStore.setTool(mapEditorStore.imageTool)
    }
    if (vectorStoreSnapshot) {
      paintStore.artboardWidth = vectorStoreSnapshot.artboardWidth
      paintStore.artboardHeight = vectorStoreSnapshot.artboardHeight
      paintStore.zoom = vectorStoreSnapshot.zoom
      paintStore.panX = vectorStoreSnapshot.panX
      paintStore.panY = vectorStoreSnapshot.panY
      vectorStoreSnapshot = null
    }
  } finally {
    vectorExiting = false
  }
}

// ─── 矢量模式图层顺序修正：把「当前矢量图层之上」的图层渲染成快照 ───

/** 把快照容器里的图层全部放回舞台树（Pixi 会正常渲染它们） */
function reattachUpperContainers() {
  if (!upperSnapshotContainer || !tileContainer) return
  const children = [...upperSnapshotContainer.children]
  if (children.length === 0) return
  for (const child of children) tileContainer.addChild(child)
  tileContainer.sortChildren()
}

/** 清空上方图层快照并让上方图层回到 Pixi 舞台 */
function clearUpperSnapshot() {
  reattachUpperContainers()
  upperSnapshotSource = null
  upperSnapshotPendingRect = null
  if (upperSnapshotRect.value) upperSnapshotRect.value = null
  const el = upperSnapshotRef.value
  if (el) {
    const ctx = el.getContext('2d')
    if (ctx) ctx.clearRect(0, 0, el.width, el.height)
  }
}

/** 把生成好的快照画布拷进 DOM 画布（覆盖层挂载后才可写） */
function paintUpperSnapshotToDom(retry = 0) {
  const rect = upperSnapshotPendingRect
  const src = upperSnapshotSource
  if (!rect || !src) return
  const el = upperSnapshotRef.value
  if (!el) {
    // 覆盖层还没挂载（进入矢量模式后要等一拍）——有限次补画，避免覆盖层不在时死循环
    if (retry < 3) void nextTick(() => paintUpperSnapshotToDom(retry + 1))
    return
  }
  if (el.width !== src.width || el.height !== src.height) {
    el.width = src.width
    el.height = src.height
  }
  const ctx = el.getContext('2d')
  if (ctx) {
    ctx.clearRect(0, 0, el.width, el.height)
    ctx.drawImage(src, 0, 0)
  }
  upperSnapshotRect.value = rect
}

/** 缩放结束后重拍快照（按新倍率渲染，静置时与 Pixi 画质一致） */
function scheduleUpperSnapshotRefresh(delay = 160) {
  if (upperSnapshotTimer) clearTimeout(upperSnapshotTimer)
  upperSnapshotTimer = setTimeout(() => {
    upperSnapshotTimer = null
    if (vectorActive.value) refreshUpperLayerSnapshot()
  }, delay)
}

/**
 * 矢量内容画在独立的 DOM canvas 上（恒在 Pixi 画布之上），因此选中矢量图层不能把它顶到最上层：
 * 若该图层之上还有图层，就把这些图层单独渲染成一张快照，叠在矢量画布之上，
 * 画布最终仍严格按图层顺序显示。快照坐标 = 画板坐标，缩放/平移由覆盖层的 CSS 矩阵跟随。
 */
function refreshUpperLayerSnapshot() {
  if (!app || !PIXI || !tileContainer) return
  // 上一轮的快照容器先归位，保证下面按完整图层树重新判断
  reattachUpperContainers()

  if (!vectorActive.value) {
    clearUpperSnapshot()
    return
  }
  const s = paintSession
  const layers = mapStore.mapData.layers
  const idx = s ? layers.findIndex(l => l.id === s.layerId) : -1
  const frame = vectorFrame()
  const m = frame ? computeMapVectorMatrix(frame) : null
  const det = m ? m.a * m.d - m.b * m.c : 0
  if (!s || idx < 0 || !frame || !m || Math.abs(det) < 1e-9) {
    clearUpperSnapshot()
    return
  }
  const upperLayers = layers.slice(idx + 1).filter(l => l.visible)
  if (upperLayers.length === 0) {
    clearUpperSnapshot()
    return
  }

  // 世界坐标 → 画板坐标（画板 = 矢量图层的绘制画布像素）
  const scale = frame.scale
  const sx = frame.stageX - m.tx
  const sy = frame.stageY - m.ty
  const a = (scale * m.d) / det
  const b = (-scale * m.b) / det
  const c = (-scale * m.c) / det
  const d = (scale * m.a) / det
  const tx = (m.d * sx - m.c * sy) / det
  const ty = (-m.b * sx + m.a * sy) / det

  // 快照区域 = 画板区域 ∪ 上方图层投影包围盒（矢量画板较小也不会裁掉上方大图层）
  let minX = 0
  let minY = 0
  let maxX = Math.max(1, s.canvas.width)
  let maxY = Math.max(1, s.canvas.height)
  for (const layer of upperLayers) {
    const container = layerContainers.get(layer.id)
    if (!container) continue
    // 容器无局部变换 → 局部包围盒即世界坐标包围盒
    const bb = container.getLocalBounds()
    if (!bb || bb.width <= 0 || bb.height <= 0) continue
    const corners = [
      [bb.minX, bb.minY], [bb.maxX, bb.minY],
      [bb.minX, bb.maxY], [bb.maxX, bb.maxY],
    ]
    for (const [wx, wy] of corners) {
      const ax = a * wx + c * wy + tx
      const ay = b * wx + d * wy + ty
      if (ax < minX) minX = ax
      if (ax > maxX) maxX = ax
      if (ay < minY) minY = ay
      if (ay > maxY) maxY = ay
    }
  }
  const artW = Math.max(1, maxX - minX)
  const artH = Math.max(1, maxY - minY)
  const dpr = app.renderer?.resolution || 1
  let res = Math.min(3, Math.max(1, vectorScreenScale.value * dpr))
  const MAX_PIXELS = 8_000_000
  if (artW * artH * res * res > MAX_PIXELS) {
    res = Math.max(0.25, Math.sqrt(MAX_PIXELS / (artW * artH)))
  }
  const rw = Math.max(1, Math.round(artW * res))
  const rh = Math.max(1, Math.round(artH * res))

  if (!upperSnapshotContainer) {
    upperSnapshotContainer = new PIXI.Container()
    upperSnapshotContainer.sortableChildren = true
  }
  // 上方图层容器本身无局部变换：只给快照容器套「世界 → 画板（含倍率）」矩阵
  upperSnapshotContainer.setFromMatrix(new PIXI.Matrix(
    a * res, b * res, c * res, d * res,
    (tx - minX) * res, (ty - minY) * res
  ))
  for (const layer of upperLayers) {
    const container = layerContainers.get(layer.id)
    if (container) upperSnapshotContainer.addChild(container)
  }
  try {
    const rt = PIXI.RenderTexture.create({ width: rw, height: rh })
    app.renderer.render({ container: upperSnapshotContainer, target: rt })
    const canvas = app.renderer.extract.canvas(rt) as HTMLCanvasElement
    rt.destroy(true)
    upperSnapshotSource = canvas
    upperSnapshotPendingRect = { x: minX, y: minY, w: artW, h: artH }
    paintUpperSnapshotToDom()
  } catch (e) {
    console.error('[MapCanvas] 上方图层快照渲染失败:', e)
    clearUpperSnapshot()
  }
}

// ─── 覆盖层投影（SVG 变换框 / 塑形锚点 / 光标 / 文字框）───

const VEC_SEL = '#818cf8'
const VEC_SEL_DEEP = '#6366f1'

const vectorOverlayStyle = computed(() => {
  const m = vectorMatrix.value
  if (!m) return null
  return {
    width: `${paintStore.artboardWidth}px`,
    height: `${paintStore.artboardHeight}px`,
    transform: `matrix(${m.a}, ${m.b}, ${m.c}, ${m.d}, ${m.tx}, ${m.ty})`,
    transformOrigin: '0 0',
  }
})

/** 上方图层快照的定位（画板坐标）；位图场景用像素采样，放大后保持像素块观感 */
const upperSnapshotStyle = computed<CSSProperties>(() => {
  const r = upperSnapshotRect.value
  if (!r) return { display: 'none' }
  return {
    display: 'block',
    left: `${r.x}px`,
    top: `${r.y}px`,
    width: `${r.w}px`,
    height: `${r.h}px`,
    imageRendering: mapStore.sceneRenderMode === 'pixelated' ? 'pixelated' : 'auto',
  }
})

const vectorScreenScale = computed(() => {
  const m = vectorMatrix.value
  if (!m) return 1
  return Math.max(0.1, Math.sqrt(Math.abs(m.a * m.d - m.b * m.c)))
})
const vectorBoxStroke = computed(() => 1.4 / vectorScreenScale.value)
const vectorHandleSize = computed(() => 8 / vectorScreenScale.value)
const vectorRotateRadius = computed(() => 4 / vectorScreenScale.value)
const vectorPointSize = computed(() => 8 / vectorScreenScale.value)

// ─── 钢笔（自定义形状）进行中预览：固定配色（不跟随颜色面板），屏幕尺寸恒定 ───
const vectorPenStroke = computed(() => 1.4 / vectorScreenScale.value)
const vectorPenDash = computed(() => {
  const s = vectorScreenScale.value
  return `${5 / s} ${3 / s}`
})
const vectorPenAnchorSize = computed(() => 6.5 / vectorScreenScale.value)
const vectorPenRing = computed(() => 9 / vectorScreenScale.value)
const vectorPenPoints = computed(() => {
  const ps = paintStore.penState
  if (!ps) return ''
  const pts = ps.cursor ? [...ps.anchors, ps.cursor] : ps.anchors
  return pts.map(p => `${p.x},${p.y}`).join(' ')
})

const vectorBoxPoints = computed(() => {
  const box = paintStore.vectorSelBox
  if (!box) return ''
  return box.corners.map(c => `${c.x},${c.y}`).join(' ')
})

const vectorCursorStyle = computed(() => {
  if (!vectorActive.value || paintStore.mode !== 'vector') return null
  const t = paintStore.activeTool
  if (t !== 'brush' && t !== 'eraser') return null
  const p = vectorCursorPos.value
  if (!p) return null
  const d = Math.max(4, paintStore.brushSize * vectorScreenScale.value)
  return {
    left: `${p.x - d / 2}px`,
    top: `${p.y - d / 2}px`,
    width: `${d}px`,
    height: `${d}px`,
  }
})

function updateVectorCursorScreen(e: PointerEvent) {
  if (!vectorActive.value || paintStore.mode !== 'vector') return
  const root = canvasRef.value
  if (!root) return
  const rect = root.getBoundingClientRect()
  vectorCursorPos.value = { x: e.clientX - rect.left, y: e.clientY - rect.top }
  // 圆圈由 DOM 接管后隐藏原生指针
  const t = paintStore.activeTool
  if (vectorCanvasRef.value && (t === 'brush' || t === 'eraser')) {
    vectorCanvasRef.value.style.cursor = 'none'
  }
}

function onVectorPointerLeave() {
  vectorCursorPos.value = null
  vectorPanning = false
  emit('cursor-leave')
}

// ─── 文字编辑（复用角色页 textEdit 投影）───
const vectorTextComposing = ref(false)
let vectorMeasureCtx: CanvasRenderingContext2D | null = null

function measureVectorText(value: string, fontSize: number, lineHeightRatio: number) {
  if (!vectorMeasureCtx) vectorMeasureCtx = document.createElement('canvas').getContext('2d')
  const lh = fontSize * lineHeightRatio
  const lines = value.split('\n')
  if (!vectorMeasureCtx || !value) return { w: fontSize * 0.5, h: lh }
  vectorMeasureCtx.font = `500 ${fontSize}px "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif`
  let maxW = 0
  for (const line of lines) {
    maxW = Math.max(maxW, vectorMeasureCtx.measureText(line || ' ').width)
  }
  return { w: Math.max(maxW, 1), h: Math.max(lines.length, 1) * lh }
}

function refreshVectorTextSize() {
  const te = paintStore.textEdit
  const el = textAreaRef.value
  if (!te || !el) return
  const size = measureVectorText(el.value, te.fontSize, te.lineHeight)
  if (Math.abs(te.width - size.w) > 0.5 || Math.abs(te.height - size.h) > 0.5) {
    te.width = size.w
    te.height = size.h
  }
}

const vectorTextEditStyle = computed(() => {
  const te = paintStore.textEdit
  if (!te) return null
  const base: Record<string, string> = {
    fontSize: `${te.fontSize}px`,
    lineHeight: String(te.lineHeight),
    color: te.color,
    left: `${te.x}px`,
    top: `${te.y}px`,
    width: `${Math.max(te.width, 1) + 1}px`,
    height: `${Math.max(te.height, 1)}px`,
  }
  if (te.matrix) {
    base.transform = te.matrix
    base.transformOrigin = te.transformOrigin
  }
  return base
})

function commitVectorTextEdit() {
  if (paintStore.textEdit) vectorEngine.textEditCommit()
}

function onVectorTextInput(e: Event) {
  const el = e.target as HTMLTextAreaElement
  refreshVectorTextSize()
  if (vectorTextComposing.value) return
  vectorEngine.textEditInput(el.value)
}

function onVectorTextCompositionStart() {
  vectorTextComposing.value = true
}

function onVectorTextCompositionEnd(e: CompositionEvent) {
  vectorTextComposing.value = false
  refreshVectorTextSize()
  vectorEngine.textEditInput((e.target as HTMLTextAreaElement).value)
}

function onVectorTextKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    e.preventDefault()
    commitVectorTextEdit()
  }
  e.stopPropagation()
}

watch(
  () => paintStore.textEdit,
  (te) => {
    if (te) {
      vectorTextComposing.value = false
      const focusTa = () => {
        const el = textAreaRef.value
        if (!el) return
        if (!el.value) el.value = te.value
        el.focus({ preventScroll: true })
        const len = el.value.length
        el.setSelectionRange(len, len)
      }
      nextTick(() => {
        focusTa()
        requestAnimationFrame(focusTa)
      })
    } else {
      vectorTextComposing.value = false
    }
  }
)

// ─── 矢量覆盖层上的平移/缩放转发 ───

/** 取色：位图 + 矢量合成后读取点击点像素色（与角色页一致） */
function pickVectorColor(e: PointerEvent): boolean {
  if (!paintStore.eyedropperActive) return false
  const frame = vectorFrame()
  const p = mapVectorViewport.clientToArtboard(e)
  if (!frame?.canvas || !p) return false
  const cw = frame.canvas.width
  const ch = frame.canvas.height
  const x = Math.floor(p.x)
  const y = Math.floor(p.y)
  if (x < 0 || y < 0 || x >= cw || y >= ch) {
    paintStore.endEyedropper()
    return true
  }
  const comp = makeOffscreenCanvas(cw, ch)
  const cctx = comp.getContext('2d')!
  cctx.drawImage(frame.canvas, 0, 0)
  const raster = vectorEngine.getFrameRaster(0)
  if (raster) cctx.drawImage(raster, 0, 0, cw, ch)
  const d = cctx.getImageData(x, y, 1, 1).data
  paintStore.endEyedropper()
  if (d[3] >= 16) {
    const hex = '#' + [d[0], d[1], d[2]].map(v => v.toString(16).padStart(2, '0')).join('')
    if (paintStore.eyedropperTarget === 'stroke') paintStore.strokeColor = hex
    else paintStore.fillColor = hex
  }
  return true
}

function onVectorPointerDownCapture(e: PointerEvent) {
  updateVectorCursorScreen(e)
  // 取色优先：点击画布取色并结束会话（不进入 paper 工具）
  if (e.button === 0 && paintStore.eyedropperActive) {
    e.preventDefault()
    e.stopImmediatePropagation()
    pickVectorColor(e)
    return
  }
  const pan = e.button === 1 || (e.button === 0 && (viewport.isSpacePressed() || e.altKey))
  if (pan) {
    e.preventDefault()
    e.stopImmediatePropagation()
    vectorPanning = true
    viewport.startPan(e.clientX, e.clientY)
    viewport.setCursor('default')
    return
  }
  // 矢量画布盖在 Pixi 之上：标记放置 / 取消选中也要在这里接管
  if (e.button === 0 && mapEditorStore.markerPlacing) {
    e.preventDefault()
    e.stopImmediatePropagation()
    const world = viewport.screenToWorld(e)
    if (world) {
      const id = mapStore.addMarker(world.x, world.y)
      mapEditorStore.cancelMarkerPlacing()
      markerGhost.value = null
      emit('marker-activate', id)
    }
    return
  }
  if (e.button === 0) mapEditorStore.setSelectedMarkerId(null)
}

function onVectorPointerMoveCapture(e: PointerEvent) {
  updateVectorCursorScreen(e)
  // 矢量画布盖在 Pixi 画布之上，这里也要上报坐标，否则矢量绘制时信息栏坐标不动
  const cursorWorld = viewport.screenToWorld(e)
  if (cursorWorld) emit('cursor-move', cursorWorld.x, cursorWorld.y)
  if (mapEditorStore.markerPlacing) markerGhost.value = cursorWorld
  if (vectorPanning) {
    e.stopImmediatePropagation()
    viewport.handlePanMove(e.clientX, e.clientY)
    syncVectorGeometry()
    collision.drawOverlay()
  }
}

function onVectorPointerUpCapture(e: PointerEvent) {
  if (!vectorPanning) return
  e.stopImmediatePropagation()
  vectorPanning = false
  viewport.endPan()
  viewport.setCursor('crosshair')
}

function onVectorWheel(e: WheelEvent) {
  e.preventDefault()
  viewport.onWheel(e)
}

// ─── 工具栏统一入口（按当前模式路由到位图/矢量）───

function undoActive() {
  if (vectorActive.value && paintStore.mode === 'vector') vectorEngine.undo()
  else undoPaint()
}

function redoActive() {
  if (vectorActive.value && paintStore.mode === 'vector') vectorEngine.redo()
  else redoPaint()
}

function copyActive() {
  if (vectorActive.value && paintStore.mode === 'vector') vectorEngine.copySelection()
  else copyFloatingSelection()
}

function pasteActive() {
  if (vectorActive.value && paintStore.mode === 'vector') {
    if (paintStore.hasVectorClipboard) vectorEngine.pasteClipboard()
  } else {
    pasteFloatingSelection()
  }
}

function deleteActive() {
  if (vectorActive.value && paintStore.mode === 'vector') vectorEngine.deleteSelection()
  else deleteSelection()
}

function flipActive(axis: 'h' | 'v') {
  if (vectorActive.value && paintStore.mode === 'vector') vectorEngine.flipSelection(axis)
  else flipSelection(axis)
}

function groupActive() {
  if (vectorActive.value && paintStore.mode === 'vector') vectorEngine.groupSelection()
}

function ungroupActive() {
  if (vectorActive.value && paintStore.mode === 'vector') vectorEngine.ungroupSelection()
}

function layerUpActive() {
  if (vectorActive.value && paintStore.mode === 'vector') vectorEngine.layerMove('up')
}

function layerDownActive() {
  if (vectorActive.value && paintStore.mode === 'vector') vectorEngine.layerMove('down')
}

// --- Interaction ---

function onPointerDown(e: PointerEvent) {
  if (e.button === 1 || (e.button === 0 && viewport.isSpacePressed()) || (e.button === 0 && e.altKey)) {
    viewport.startPan(e.clientX, e.clientY)
    viewport.setCursor('default')
    e.preventDefault()
    return
  }

  // 标记放置：左键点一下即落点并退出放置（空格/Alt 仍优先平移）
  if (mapEditorStore.markerPlacing && e.button === 0) {
    const worldPos = viewport.screenToWorld(e)
    if (worldPos) {
      const id = mapStore.addMarker(worldPos.x, worldPos.y)
      mapEditorStore.cancelMarkerPlacing()
      markerGhost.value = null
      // 落点后直接聚焦名称输入，顺手就能起名字
      emit('marker-activate', id)
    }
    return
  }

  // 画布空白处左键：取消标记选中
  if (e.button === 0) mapEditorStore.setSelectedMarkerId(null)

  // 位图取色：点击画布读取像素色并结束会话
  if (mapStore.activeMode === 'image' && paintStore.eyedropperActive) {
    const worldPos = viewport.screenToWorld(e)
    const p = worldPos ? toCanvasPoint(worldPos) : null
    const s = paintSession
    const ctx = paintCtx()
    if (p && s && ctx) {
      const x = Math.max(0, Math.min(s.canvas.width - 1, Math.floor(p.x)))
      const y = Math.max(0, Math.min(s.canvas.height - 1, Math.floor(p.y)))
      const d = ctx.getImageData(x, y, 1, 1).data
      paintStore.endEyedropper()
      if (d[3] >= 16) {
        const hex = '#' + [d[0], d[1], d[2]].map(v => v.toString(16).padStart(2, '0')).join('')
        if (paintStore.eyedropperTarget === 'stroke') paintStore.strokeColor = hex
        else paintStore.fillColor = hex
      }
      return
    }
  }

  // 碰撞层：指针事件全部交给碰撞层编辑器
  if (mapStore.activeMode === 'collision') {
    // 清掉可能残留的平移状态，避免普通拖动带动整块画布
    viewport.endPan()
    const worldPos = viewport.screenToWorld(e)
    if (worldPos) {
      // 捕获指针：拖出画布/移出地图范围后仍能继续拖动，不会卡住
      capturePointer(app?.canvas as HTMLCanvasElement | undefined, e.pointerId)
      collision.pointerDown(worldPos, e.button)
      updateCollisionCursor(worldPos)
    }
    return
  }

  // 点击变换手柄时交给变换逻辑，避免与选区框选冲突
  if (transform.isTransformBusy()) return

  // 图片模式的选择工具：像素/矢量选取
  if (mapStore.activeMode === 'image' && mapEditorStore.imageTool === 'select') {
    if (e.button !== 0) return
    const worldPos = viewport.screenToWorld(e)
    if (!mapStore.selectedImage) return
    // 开始框选时收起整图变换框，避免两个框同时出现
    transform.removeTransformBox()
    if (worldPos) {
      if (sessionMatchesSelection()) {
        handleSelectPointerDown(worldPos)
      } else {
        void startPaintSession().then(ok => {
          if (ok) handleSelectPointerDown(worldPos)
        })
      }
    }
    return
  }

  if (e.button === 0 && !e.altKey && !viewport.isSpacePressed()) {
    // 图片模式：直接在画布上绘制
    if (isImagePaintTool()) {
      const worldPos = viewport.screenToWorld(e)
      if (worldPos) {
        const startAndHandle = (handler: () => void) => {
          if (sessionMatchesSelection()) handler()
          else void startPaintSession().then(ok => { if (ok) handler() })
        }
        // 图形创建后自动出现的编辑选框：优先响应手柄/内部拖动（任意位图绘制工具下）
        if (floatCanvas && floatOp === 'none' && hitTestFloat(worldPos).kind !== 'outside') {
          // 浮动选区必然属于当前会话：同步处理，避免异步建会话后鼠标已松开导致手势卡住
          if (sessionMatchesSelection()) handleSelectPointerDown(worldPos)
          capturePointer(app?.canvas as HTMLCanvasElement | undefined, e.pointerId)
          return
        }
        startAndHandle(() => {
          // 点击选框外 = 完成确定（落定像素），随后继续当前工具的正常行为
          if (floatCanvas) bakeFloatingSelection()
          // 位图钢笔：单击落锚（不是拖拽笔画），需要绘制会话才能写像素
          if (mapEditorStore.imageTool === 'pen' && mapEditorStore.paintMode === 'bitmap') {
            const p = toCanvasPoint(worldPos)
            if (p) bitmapPen.press(p, e.detail)
          } else {
            paintBegin(worldPos)
          }
        })
        return
      }
    }

    // 图片模式选择工具只做像素框选，不再做整图点选（位图/矢量模式行为一致）
    const pos = viewport.screenToGrid(e)
    if (pos) painter.handlePaintPointerDown(e, pos)
  }
}

function onPointerMove(e: PointerEvent) {
  // 所有模式都实时上报鼠标世界像素坐标（信息栏显示用）；绘制/框选分支提前 return 也不影响
  const cursorWorld = viewport.screenToWorld(e)
  if (cursorWorld) emit('cursor-move', cursorWorld.x, cursorWorld.y)
  if (mapEditorStore.markerPlacing) markerGhost.value = cursorWorld
  // 碰撞层：未按键时确保平移状态已结束，不会出现"鼠标一动整块画布跟着走"
  if (mapStore.activeMode === 'collision' && e.buttons === 0) viewport.endPan()
  if (viewport.handlePanMove(e.clientX, e.clientY)) {
    syncVectorGeometry()
    // 叠加层在屏幕坐标绘制，平移后需要重绘
    collision.drawOverlay()
    return
  }

  // 碰撞层：拖动顶点 / 整框移动 / 矩形 / 钢笔预览
  if (mapStore.activeMode === 'collision') {
    const worldPos = viewport.screenToWorld(e)
    if (worldPos) {
      collision.pointerMove(worldPos)
      updateCollisionCursor(worldPos)
    }
    return
  }

  // 整图变换框拖动（拖动图片本体 / 缩放 / 旋转）优先于选区逻辑
  if (transform.handleTransformPointerMove(e)) return

  // 图片模式选取工具：更新框选矩形 / 拖动浮动选区（移动、缩放、旋转）
  if (mapStore.activeMode === 'image' && mapEditorStore.imageTool === 'select' && mapStore.selectedImage) {
    if (floatOp !== 'none') {
      const worldPos = viewport.screenToWorld(e)
      if (worldPos) handleSelectPointerMove(worldPos, e.shiftKey)
    }
    return
  }

  // 图片模式绘制工具：圆圈光标跟随鼠标并绘制
  if (isImagePaintTool()) {
    // 自动编辑选框的拖动（移动/缩放/旋转）优先
    if (floatOp !== 'none') {
      const worldPos = viewport.screenToWorld(e)
      if (worldPos) handleSelectPointerMove(worldPos, e.shiftKey)
      return
    }
    if (isBrushCursorActive()) drawBrushCursorAt(e.clientX, e.clientY)
    // 位图钢笔：橡皮筋预览跟随光标（无需按住鼠标）
    if (mapEditorStore.imageTool === 'pen' && mapEditorStore.paintMode === 'bitmap') {
      if (sessionMatchesSelection()) {
        const worldPos = viewport.screenToWorld(e)
        const p = worldPos ? toCanvasPoint(worldPos) : null
        if (p) bitmapPen.move(p)
      }
      return
    }
    if (e.buttons === 1 && sessionMatchesSelection()) {
      const worldPos = viewport.screenToWorld(e)
      if (worldPos) paintMove(worldPos, e.shiftKey)
    }
    return
  }

  const gridPos = viewport.screenToGrid(e)
  if (gridPos) {
    cursorGridPos.value = gridPos
    emit('cursor-move', gridPos.x, gridPos.y)
  } else {
    cursorGridPos.value = null
  }

  painter.handlePaintPointerMove(e, gridPos)
}

function onPointerUp(e: PointerEvent) {
  // 碰撞层：收尾矩形/顶点/整框拖拽
  if (mapStore.activeMode === 'collision') {
    // 空格/中键平移的收尾也必须执行，否则平移状态会残留，之后鼠标移动一直拖动画布
    viewport.endPan()
    releasePointer(app?.canvas as HTMLCanvasElement | undefined, e.pointerId)
    collision.pointerUp()
    return
  }

  // 整图变换框拖动结束优先处理，避免被选区逻辑吞掉
  if (transform.handleTransformPointerUp()) return

  // 图片模式选取工具：结束框选 / 结束移动缩放旋转
  if (mapStore.activeMode === 'image' && mapEditorStore.imageTool === 'select' && mapStore.selectedImage) {
    if (e.button === 0) handleSelectPointerUp()
    viewport.endPan()
    return
  }

  // 自动编辑选框的拖动收尾（移动/缩放/旋转）
  if (isImagePaintTool() && floatOp !== 'none') {
    handleSelectPointerUp()
    viewport.endPan()
    return
  }

  // 位图钢笔：落锚靠点击，不走拖拽笔画的收尾逻辑
  if (isImagePaintTool() && mapEditorStore.imageTool === 'pen' && mapEditorStore.paintMode === 'bitmap') {
    viewport.endPan()
    return
  }

  if (isImagePaintTool() && sessionMatchesSelection()) {
    paintEnd(viewport.screenToWorld(e) ?? undefined, e.shiftKey)
    viewport.endPan()
    return
  }

  // Move tool: drop tile at new position
  painter.handlePointerUp(cursorGridPos.value)

  viewport.endPan()
  painter.resetPaintKey()
  viewport.setCursor('default')
}

function onPointerLeave(e: PointerEvent) {
  viewport.endPan()
  painter.resetPaintKey()
  cursorGridPos.value = null
  markerGhost.value = null
  // 鼠标离开画布时清空信息栏坐标，避免残留上一次的位置
  emit('cursor-leave')
  painter.hidePreview()
  hideBrushCursor()
  // 绘制中离开画布：结束当前笔画（钢笔保留已落锚点，等用户回来继续）
  if (isImagePaintTool() && mapEditorStore.imageTool !== 'pen' && sessionMatchesSelection()) paintEnd()
  // 框选中离开画布：按当前尺寸收口，避免选框悬空
  if (mapStore.activeMode === 'image' && mapEditorStore.imageTool === 'select' && floatOp === 'create') {
    handleSelectPointerUp()
  }
  // 松手状态下离开画布才取消未完成的碰撞草稿；拖拽中（按钮仍按下）继续由指针捕获接管
  if (mapStore.activeMode === 'collision' && e.buttons === 0) {
    collision.resetOnLeave()
  }
}

function setupInteraction() {
  if (!app || !app.canvas) return
  const canvas = app.canvas as HTMLCanvasElement

  canvas.addEventListener('wheel', onWheel, { passive: false })
  canvas.addEventListener('pointerdown', onPointerDown)
  canvas.addEventListener('pointermove', onPointerMove)
  canvas.addEventListener('pointerup', onPointerUp)
  canvas.addEventListener('pointerleave', onPointerLeave)
  canvas.addEventListener('contextmenu', onContextMenu)
  // Scratch 风格拖拽：监听自定义事件
  canvas.addEventListener('scratch-drop', onScratchDrop as EventListener)
}

function onWheel(e: WheelEvent) {
  viewport.onWheel(e)
}

function onScratchDrop(e: CustomEvent) {
  const { resourceIndex } = e.detail
  const resource = mapStore.activeLayerResources[resourceIndex]
  if (!resource) return

  // 拖入的图片左上角自动对齐到坐标原点
  placeImage(resource, 0, 0)
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  e.stopPropagation()

  const imageData = e.dataTransfer?.getData('application/x-bingo-image')

  if (imageData) {
    try {
      const { resourceIndex } = JSON.parse(imageData)
      const resource = mapStore.activeLayerResources[resourceIndex]
      const worldPos = viewport.screenToWorld(e)
      if (resource && worldPos) {
        placeImage(resource, worldPos.x, worldPos.y)
      }
    } catch (err) {
      console.error('[MapCanvas] drop error:', err)
    }
    return
  }

  // 瓦片拖放
  const tileData = e.dataTransfer?.getData('application/x-bingo-tile')
  if (!tileData) {
    return
  }

  const pos = viewport.screenToGrid(e as any)
  if (!pos) return

  try {
    const { resourceIndex, tileIndex } = JSON.parse(tileData)
    if (mapStore.activeLayer) {
      const tileId = painter.encodeTileId(mapStore.activeLayer.id, resourceIndex, tileIndex)
      mapStore.setTile(pos.x, pos.y, tileId)
      painter.updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
    }
  } catch {}
}

function onKeyDown(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement).tagName
  const typing = tag === 'INPUT' || tag === 'TEXTAREA'
  // 标记：Esc 退出放置 / 取消选中；Delete 删除选中
  if (e.key === 'Escape') {
    if (mapEditorStore.markerPlacing) {
      mapEditorStore.cancelMarkerPlacing()
      markerGhost.value = null
      return
    }
    if (!typing && mapEditorStore.selectedMarkerId) {
      mapEditorStore.setSelectedMarkerId(null)
      return
    }
  }
  if (!typing && (e.key === 'Delete' || e.key === 'Backspace') && mapEditorStore.selectedMarkerId) {
    mapStore.removeMarker(mapEditorStore.selectedMarkerId)
    e.preventDefault()
    return
  }
  if (e.code === 'Space' && !e.repeat) {
    viewport.onSpaceDown()
    return
  }
  // 矢量模式快捷键：与角色绘制页一致（对象操作优先，屏蔽地图快捷键）
  if (vectorActive.value && paintStore.mode === 'vector') {
    const tag = (e.target as HTMLElement).tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA') return
    const mod = e.ctrlKey || e.metaKey
    if (paintStore.eyedropperActive) {
      paintStore.endEyedropper()
      e.preventDefault()
      return
    }
    // 钢笔：Esc 取消半成品、Enter 直接闭合收尾
    if (paintStore.activeTool === 'pen') {
      if (e.key === 'Escape' && vectorEngine.penCancel()) {
        e.preventDefault()
        return
      }
      if (e.key === 'Enter' && vectorEngine.penFinish()) {
        e.preventDefault()
        return
      }
    }
    if (e.key === 'Escape') {
      if (!vectorEngine.reshapeEscape()) vectorEngine.deselect()
      // 整图变换框也一并清除，避免选框残留无法取消
      transform.removeTransformBox()
      e.preventDefault()
      return
    }
    if (e.key === 'Delete' || e.key === 'Backspace') {
      if (vectorEngine.reshapeDeletePoints()) {
        e.preventDefault()
      } else if (paintStore.vectorSelectedCount > 0) {
        vectorEngine.deleteSelection()
        e.preventDefault()
      }
      return
    }
    if (e.key.startsWith('Arrow')) {
      if (vectorEngine.reshapeNudge(e.key, e.repeat)) e.preventDefault()
      return
    }
    if (mod && (e.key === 'c' || e.key === 'C')) {
      vectorEngine.copySelection()
      e.preventDefault()
      return
    }
    if (mod && (e.key === 'x' || e.key === 'X')) {
      vectorEngine.cutSelection()
      e.preventDefault()
      return
    }
    if (mod && (e.key === 'v' || e.key === 'V')) {
      if (paintStore.hasVectorClipboard) vectorEngine.pasteClipboard()
      e.preventDefault()
      return
    }
    return
  }
  // 图片模式选取工具：Esc 取消浮动选区 / 框选 / 整图选框，Delete 删除选区内容
  if (mapStore.activeMode === 'image' && mapEditorStore.imageTool === 'select') {
    if (e.key === 'Escape') {
      e.preventDefault()
      if (floatCanvas) cancelFloatingSelection()
      else if (pixelSelection) clearPixelSelection()
      else transform.removeTransformBox()
      return
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && floatCanvas) {
      e.preventDefault()
      deleteFloatingPixels()
      return
    }
  }
  // 图片模式：Ctrl/Cmd+C/V 复制粘贴选区（任意绘制工具下均可用）
  if (mapStore.activeMode === 'image' && (e.metaKey || e.ctrlKey)) {
    const tag = (e.target as HTMLElement).tagName
    if (tag === 'INPUT' || tag === 'TEXTAREA') return
    const key = e.key.toLowerCase()
    if (key === 'c' && floatCanvas) {
      e.preventDefault()
      copyFloatingSelection()
      return
    }
    if (key === 'v' && paintClipboard) {
      e.preventDefault()
      pasteFloatingSelection()
      return
    }
  }
  // 位图模式钢笔：Enter 闭合收尾、Esc 丢弃半成品（与矢量模式一致）
  if (mapStore.activeMode === 'image' && mapEditorStore.paintMode === 'bitmap'
    && mapEditorStore.imageTool === 'pen'
    && (e.target as HTMLElement).tagName !== 'INPUT'
    && (e.target as HTMLElement).tagName !== 'TEXTAREA') {
    if (e.key === 'Escape' && bitmapPen.cancel()) {
      e.preventDefault()
      return
    }
    if (e.key === 'Enter' && bitmapPen.finish()) {
      e.preventDefault()
      return
    }
  }
  // 图形刚创建后的自动编辑选框：Esc 取消（回到创建前），Delete 删除该图形
  if (mapStore.activeMode === 'image' && floatCanvas && floatOp === 'none') {
    if (e.key === 'Escape') {
      e.preventDefault()
      cancelFloatingSelection()
      return
    }
    if (e.key === 'Delete' || e.key === 'Backspace') {
      e.preventDefault()
      deleteFloatingPixels()
      return
    }
  }
  // 绘制模式下不响应地图快捷键（避免误删图层/切工具）
  if (isImagePaintTool()) return
  // Tool shortcuts (only when not typing in an input)
  if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'TEXTAREA') return

  // 碰撞层快捷键：Esc 取消/退出，Enter 闭合多边形，Delete 删除锚点/碰撞体
  if (mapStore.activeMode === 'collision' && collision.handleKeyDown(e)) return

  switch (e.key.toLowerCase()) {
    case 'b': mapEditorStore.setTool('draw'); break
    case 'e': mapEditorStore.setTool('erase'); break
    case 'g': mapEditorStore.toggleGrid(); break
    case 'm': mapEditorStore.setTool('move'); break
    case 'v': mapEditorStore.setTool('select'); break
    case 'f': mapEditorStore.setTool('fill'); break
  }
}

function onKeyUp(e: KeyboardEvent) {
  if (e.code === 'Space') {
    viewport.onSpaceUp()
  }
}

function redraw() {
  viewport.redraw()
}

// ─── 画布缩放（悬浮工具条）───
const zoomPercent = computed(() => Math.round(viewport.currentScale.value * 100))

function setZoomAtCenter(next: number) {
  const target = Math.max(0.5, Math.min(4, Math.round(next * 10) / 10))
  const a = app
  const scale = viewport.currentScale.value
  if (!a) {
    viewport.currentScale.value = target
    return
  }
  // 以画布中心为锚点缩放，避免视图跳动
  const cx = a.screen.width / 2
  const cy = a.screen.height / 2
  const wx = (cx - a.stage.x) / scale
  const wy = (cy - a.stage.y) / scale
  viewport.currentScale.value = target
  a.stage.scale.set(target, target)
  a.stage.x = cx - wx * target
  a.stage.y = cy - wy * target
  viewport.drawGrid()
  collision.drawOverlay()
  drawSelectionOverlay()
  redrawBrushCursor()
  syncVectorGeometry()
  // 工具条缩放停下后按新倍率重拍上方图层快照
  scheduleUpperSnapshotRefresh()
}

function zoomIn() {
  setZoomAtCenter(viewport.currentScale.value + 0.1)
}

function zoomOut() {
  setZoomAtCenter(viewport.currentScale.value - 0.1)
}

function resetZoom() {
  viewport.centerView()
  collision.drawOverlay()
  drawSelectionOverlay()
  syncVectorGeometry()
  scheduleUpperSnapshotRefresh()
}

function onMouseDown(e: MouseEvent) {
  e.stopPropagation()
  if (e.button === 2) e.preventDefault()
}

function onContextMenu(e: MouseEvent) {
  e.preventDefault()
}

// --- Watchers ---

watch(
  () => [mapStore.mapData.width, mapStore.mapData.height, mapStore.mapData.tileSize],
  () => {
    viewport.redraw()
    // tileSize 变化时需要重新渲染所有瓦片（sprite 尺寸依赖 tileSize）
    if (app) {
      tileTextures.clear()
      scheduleRender()
    }
  }
)

// 场景渲染模式变化（图层增删、位图↔矢量转换）→ 重新应用纹理采样方式
watch(
  () => mapStore.sceneRenderMode,
  () => {
    if (app) {
      applyRenderMode()
      scheduleRender()
    }
  }
)

watch(
  () => [mapStore.mapData.width, mapStore.mapData.height],
  ([w, h], prev) => {
    const ts = mapStore.mapData.tileSize
    const oldW = (prev?.[0] ?? w) * ts
    const oldH = (prev?.[1] ?? h) * ts
    // 兼容旧数据：曾经铺满整张画布的图片图层，在尺寸变化时标记为背景
    for (const layer of mapStore.mapData.layers) {
      if (layer.type !== 'image') continue
      const img = layer.image
      const atOrigin = (img.position?.[0] ?? 0) === 0 && (img.position?.[1] ?? 0) === 0
      const unitScale = Math.abs(img.scaleX ?? 1) === 1 && Math.abs(img.scaleY ?? 1) === 1
      if (!img.background && atOrigin && unitScale
        && Math.abs((img.width || 0) - oldW) < 0.5
        && Math.abs((img.height || 0) - oldH) < 0.5) {
        img.background = true
      }
    }
    // 地图尺寸变化：正在绘制的背景图层按新尺寸重建画板
    if (paintSession && mapStore.selectedImage?.background) {
      // 矢量内容先同步烘焙，避免重建画板时丢失
      if (vectorActive.value) {
        bakeVectorRasterSync()
        vectorActive.value = false
        paintStore.mode = 'bitmap'
        mapEditorStore.setPaintMode('bitmap')
      }
      void commitPaintSession(false).then(() => startPaintSession())
    }
  }
)

// 离开地图编辑器（切代码/角色/IDE 模式）时暂存矢量内容，切回仍可继续矢量编辑
watch(
  () => [editorStore.isGameMode, editorStore.activeEditorMode],
  () => {
    if (vectorActive.value && (!editorStore.isGameMode || editorStore.activeEditorMode !== 'map')) {
      void exitVectorMode(false)
    }
  }
)

// 矢量/位图模式切换：默认矢量；无选中图片时保持矢量 UI，选中图层后自动进入
watch(
  () => mapEditorStore.paintMode,
  async (mode) => {
    // 切换图层时同步模式不算用户操作：跳过，避免把矢量图层烘焙成位图
    if (suppressPaintModeWatch) {
      suppressPaintModeWatch = false
      return
    }
    // 用户主动切换：记录到当前图层，切走后仍按各自模式恢复
    const img = mapStore.selectedImage
    if (img) img.paintMode = mode
    if (mode === 'vector') {
      const ok = await enterVectorMode()
      if (ok) transform.removeTransformBox()
    } else {
      await exitVectorMode()
    }
    // 模式切换后统一选取工具光标（避免位图侧遗留十字/圆圈）
    if (mapEditorStore.imageTool === 'select') syncSelectCursor()
  }
)

watch(
  () => mapEditorStore.imageTool,
  (tool) => {
    if (mapStore.activeMode !== 'image') return
    // 切走钢笔：丢弃未闭合的半成品，避免预览线残留在像素里
    if (tool !== 'pen') bitmapPen.cancel()
    // 选取工具：两种模式统一光标，避免从画笔切过来遗留圆圈/十字
    if (tool === 'select') {
      syncSelectCursor()
      if (!(vectorActive.value && paintStore.mode === 'vector')) {
        // 位图模式选取工具需要绘制会话才能读写图片像素
        void startPaintSession()
      }
      return
    }
    if (vectorActive.value && paintStore.mode === 'vector') {
      // 切到画笔/橡皮但还没移动鼠标时先给十字，避免原生指针被隐藏后完全看不到
      if ((tool === 'brush' || tool === 'eraser') && !vectorCursorPos.value && vectorCanvasRef.value) {
        vectorCanvasRef.value.style.cursor = 'crosshair'
      }
      return
    }
    // 切换绘制工具前先落定浮动选区
    bakeFloatingSelection()
    clearPixelSelection()
    transform.removeTransformBox()
    viewport.setCursor('crosshair')
    void startPaintSession().then(() => updatePaintCursor())
    updatePaintCursor()
  }
)

// 矢量引擎主动切工具（如文字编辑结束）→ 同步地图工具栏高亮与光标：
// 工具栏读的是 imageTool，引擎只改 paintStore.activeTool，不同步就会出现
// “工具已变、图标还停在原来那个”
watch(
  () => paintStore.activeTool,
  (tool) => {
    if (!vectorActive.value || paintStore.mode !== 'vector') return
    if (mapEditorStore.imageTool === tool) return
    mapEditorStore.setImageTool(tool)
  }
)

// 矢量画布挂载期间始终保证 paintStore.mode 为 vector：
// Paper 的指针处理依赖该状态，任何异步时序导致 mode 落后都会让选取/框选"失效"
watch(vectorActive, (active) => {
  if (active) paintStore.mode = 'vector'
})

// 笔刷粗细变化 → 圆圈光标直径同步
watch(
  () => paintStore.brushSize,
  () => redrawBrushCursor()
)

watch(
  () => mapEditorStore.currentTool,
  (tool) => {
    if (tool !== 'draw' && tool !== 'erase' && tool !== 'fill') {
      painter.hidePreview()
    }
  }
)

// 切换地图时清理选中状态并重置视角
watch(
  () => mapStore.currentMapPath,
  () => {
    resetCanvasState()
    nextTick(() => {
      viewport.centerView()
      scheduleRender()
      collision.drawOverlay()
    })
  }
)

// 切到非图片图层时清除图片变换框；切到碰撞层时清理碰撞会话并刷新叠加层
watch(
  () => mapStore.activeLayerIndex,
  (idx) => {
    const layer = mapStore.mapData.layers[idx]
    if (!layer || layer.type !== 'image') {
      transform.removeTransformBox()
      mapStore.clearImageSelection()
    }
    if (layer?.type === 'collision') {
      setCollisionCursor(mapEditorStore.collisionLayerTool === 'select' ? 'default' : 'crosshair')
    }
    collision.cancelDraft()
    collision.drawOverlay()
  }
)

// 监听图层可见性变化
watch(
  () => mapStore.mapData.layers.map(l => `${l.id}:${l.visible}`),
  () => {
    ensureLayerOrder()
    // 碰撞层显隐同步叠加层
    collision.drawOverlay()
    // 矢量模式下上方图层集合随可见性变化，快照需同步重拍
    refreshUpperLayerSnapshot()
  }
)

// Watch for layer add/remove -> re-render all
watch(
  () => mapStore.mapData.layers.length,
  () => { scheduleRender() }
)

// 图层删除后立即清理其矢量缓存（图层 id 可能被后续新建图层复用）
watch(
  () => mapStore.mapData.layers.map(l => l.id).join(','),
  () => {
    const ids = new Set(mapStore.mapData.layers.map(l => l.id))
    for (const id of [...vectorLayerCache.keys()]) {
      if (!ids.has(id)) vectorLayerCache.delete(id)
    }
  }
)

// Watch tile changes (using cheap revision counter)
let renderQueued = false
let pendingRender = false

watch(
  () => mapStore.tileRevision,
  () => {
    scheduleRender()
  }
)

// Watch image changes
watch(
  () => mapStore.imageRevision,
  () => {
    if (transform.isImageDraggingNow()) return
    scheduleRender()
  }
)

// 选中实例变化（切图层 / 打开新地图）→ 同步本地变换框 + 重绘叠加层。
// mapLoadCount 参与依赖：不同地图的图层 id 都从 0 开始，仅看 id 无法区分换图
watch(
  () => [mapStore.selectedImageLayerId, mapStore.mapLoadCount] as const,
  async () => {
    const selImg = mapStore.selectedImage
    // 同步清空选区：此时 selectedImage 已指向新图层，
    // 若等到 await 之后再清，旧图层的浮动选区会短暂挂到新图层上（串层）
    resetFloatingSelection()
    paintClipboard = null
    pasteCount = 0
    mapEditorStore.hasPaintClipboard = false
    // 切换图层只切换绘制目标：整图变换框仅在用户主动点选图片时保留
    if (!transform.isSelectedImage(selImg)) transform.removeTransformBox()
    // 图层自身的编辑模式：显式记录优先，旧存档按是否有矢量数据推导
    const cached = cachedVectorEntry(mapStore.selectedImageLayerId, selImg)
    const layerMode: 'bitmap' | 'vector' = selImg
      ? (selImg.paintMode ?? ((selImg.vectorData || cached) ? 'vector' : 'bitmap'))
      : 'bitmap'
    const keepVector = layerMode === 'vector'
    // 工具栏模式跟随图层自身模式（立即同步 UI）；抑制 watcher，避免把切层误判成用户切位图而烘焙
    // 选中图块图层时（selImg 为空）不改变全局模式，避免影响后续新建绘制图层的默认模式
    if (selImg && mapEditorStore.paintMode !== layerMode) {
      suppressPaintModeWatch = true
      mapEditorStore.setPaintMode(layerMode)
    }
    // 切换图层前只暂存矢量内容（不烘焙）：每个图层保留自己的矢量数据，切回仍可编辑
    if (vectorActive.value) await exitVectorMode(false)
    collision.cancelDraft()
    // 切换图片图层：先落盘旧图层，再为新图层建会话 / 重新进入矢量模式
    const proceed = () => {
      if (mapStore.activeMode !== 'image' || !mapStore.selectedImage) return
      // 会话/画布启动前就锁定该图层的编辑模式，避免异步过程中沿用上一图层的模式
      paintStore.mode = layerMode
      if (keepVector) {
        void enterVectorMode()
      } else {
        void startPaintSession()
      }
      // 切层后按新模式统一选取工具光标（位图/矢量保持一致）
      if (mapEditorStore.imageTool === 'select') syncSelectCursor()
    }
    if (paintSession && paintSession.layerId !== mapStore.selectedImageLayerId) {
      void commitPaintSession(false).then(proceed)
    } else if (mapStore.activeMode === 'image' && mapStore.selectedImage) {
      // 图片模式下选中图层即预建会话，保证首次框选/绘制立即可用
      proceed()
    }
  }
)

// 碰撞层工具切换：清理未完成草稿并重置光标
watch(
  () => mapEditorStore.collisionLayerTool,
  () => {
    if (mapStore.activeMode !== 'collision') return
    collision.cancelDraft()
    setCollisionCursor(mapEditorStore.collisionLayerTool === 'select' ? 'default' : 'crosshair')
    collision.drawOverlay()
  }
)

// 统一的渲染调度：合并多次变更，用锁防止并发渲染
let renderIdleWaiters: Array<() => void> = []

/** 等待当前排队/进行中的渲染完成（保存缩略图前调用，避免拍到清空重建中的空画布） */
function whenRenderIdle(): Promise<void> {
  if (!renderQueued && !pendingRender) return Promise.resolve()
  return new Promise(resolve => renderIdleWaiters.push(resolve))
}

function scheduleRender() {
  pendingRender = true
  if (renderQueued) return
  renderQueued = true
  nextTick(async () => {
    try {
      while (pendingRender) {
        pendingRender = false
        // app 未就绪时轮询等待（initPixi 是异步的）
        while (!app) {
          await new Promise(r => requestAnimationFrame(r))
        }
        await renderAllLayers()
        // 图片变换 / 图层重渲染后同步矢量覆盖层矩阵
        syncVectorGeometry()
      }
    } finally {
      // 锁必须保持到渲染真正结束，否则 await 期间又会被新任务插进来并发渲染
      renderQueued = false
      const waiters = renderIdleWaiters
      renderIdleWaiters = []
      waiters.forEach(fn => fn())
    }
  })
}

// 保护性 watcher：如果 tileRevision 变化时 app 还没初始化，等就绪后补渲染
let pendingMapRender = false
watch(
  () => mapStore.tileRevision,
  () => {
    if (!app && !pendingMapRender) {
      pendingMapRender = true
      const checkReady = () => {
        if (app) {
          pendingMapRender = false
          // 统一走 scheduleRender，避免与排队中的渲染并发重建容器
          scheduleRender()
        } else {
          requestAnimationFrame(checkReady)
        }
      }
      requestAnimationFrame(checkReady)
    }
  }
)

// 切换地图时清理所有选中状态、变换框、拖拽状态
async function resetCanvasState() {
  // 先烘焙旧图层的矢量内容，再提交位图会话
  if (vectorActive.value) {
    await exitVectorMode(false)
  }
  void commitPaintSession()
  resetFloatingSelection()
  paintClipboard = null
  pasteCount = 0
  mapEditorStore.hasPaintClipboard = false
  transform.resetTransformState()
  mapStore.clearImageSelection()
  collision.cancelDraft()
  painter.resetMoveState()
  // 切换地图后图层 id 会被重新分配，旧缓存必须整体丢弃，避免串到新地图的图层
  vectorLayerCache.clear()
}

onMounted(() => {
  // 默认矢量模式：Pixi 就绪后尝试进入（无图片图层时保持矢量 UI，选中图层后自动进入）
  nextTick(async () => {
    await initPixi()
    if (mapEditorStore.paintMode === 'vector' && !vectorActive.value) void enterVectorMode()
  })
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  // 在 document 上注册 drop 事件，确保能接收拖放
  document.addEventListener('dragover', onDragOver)
  document.addEventListener('drop', onDrop)
})

onBeforeUnmount(() => {
  // 卸载无法 await：同步烘焙矢量内容后的像素，再交给 commitPaintSession 落盘
  if (layerThumbTimer) {
    clearTimeout(layerThumbTimer)
    layerThumbTimer = null
  }
  if (upperSnapshotTimer) {
    clearTimeout(upperSnapshotTimer)
    upperSnapshotTimer = null
  }
  if (vectorActive.value) {
    bakeVectorRasterSync()
    vectorActive.value = false
    paintStore.mode = 'bitmap'
  }
  clearUpperSnapshot()
  void commitPaintSession()
  resizeObserver?.disconnect()
  resizeObserver = null
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  window.removeEventListener('mousemove', onMarkerDragMove)
  document.removeEventListener('dragover', onDragOver)
  document.removeEventListener('drop', onDrop)
  if (app?.canvas) {
    const canvas = app.canvas as HTMLCanvasElement
    canvas.removeEventListener('wheel', onWheel)
    canvas.removeEventListener('pointerdown', onPointerDown)
    canvas.removeEventListener('pointermove', onPointerMove)
    canvas.removeEventListener('pointerup', onPointerUp)
    canvas.removeEventListener('pointerleave', onPointerLeave)
    canvas.removeEventListener('contextmenu', onContextMenu)
    canvas.removeEventListener('scratch-drop', onScratchDrop as EventListener)
  }
  if (app) {
    app.destroy(true)
    app = null
  }
  PIXI = null
  collision.dispose()
})

/**
 * 图块图层缩略图：直接按该图层自身的瓦片数据合成到离屏 canvas，
 * 不经过 Pixi 场景容器渲染，保证每个图层的缩略图只包含自己的内容。
 */
async function getLayerThumbnailDataUrl(layerId: number): Promise<string | null> {
  const layer = mapStore.mapData.layers.find(l => l.id === layerId)
  if (!layer || layer.type !== 'drawing') return null
  const entries = Object.entries(layer.tiles)
  if (entries.length === 0) return null

  const ts = mapStore.mapData.tileSize
  const mapW = mapStore.mapData.width * ts
  const mapH = mapStore.mapData.height * ts
  if (mapW <= 0 || mapH <= 0) return null

  const tilesets = mapStore.mapData.tileSets
  // GID → 图块集 → 素材（同一素材图片只加载一次）
  const imageCache = new Map<string, HTMLImageElement | null>()
  const resolveTile = (gid: number) => {
    let matched: any = null
    for (let i = tilesets.length - 1; i >= 0; i--) {
      if (gid >= tilesets[i].firstgid) { matched = tilesets[i]; break }
    }
    if (!matched) return null
    const resource = mapStore.mapData.resources.find(r => r.firstgid === matched.firstgid)
      ?? mapStore.mapData.resources.find(r => r.path === matched.imagePath)
    if (!resource) return null
    return { resource, tileIndex: gid - matched.firstgid }
  }

  const canvas = document.createElement('canvas')
  canvas.width = mapW
  canvas.height = mapH
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  ctx.imageSmoothingEnabled = false

  for (const [posKey, gid] of entries) {
    const [x, y] = posKey.split(',').map(Number)
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue
    const hit = resolveTile(gid)
    if (!hit) continue
    let img = imageCache.get(hit.resource.path)
    if (img === undefined) {
      try { img = await loadImage(hit.resource.path) } catch { img = null }
      imageCache.set(hit.resource.path, img)
    }
    if (!img) continue
    const iw = img.naturalWidth || img.width
    const cols = Math.max(1, Math.floor(iw / hit.resource.tileWidth))
    const col = hit.tileIndex % cols
    const row = Math.floor(hit.tileIndex / cols)
    ctx.drawImage(
      img,
      col * hit.resource.tileWidth, row * hit.resource.tileHeight,
      hit.resource.tileWidth, hit.resource.tileHeight,
      x * ts, y * ts, ts, ts,
    )
  }
  return canvas.toDataURL('image/png')
}

// ─── 图片图层缩略图即时刷新（每笔结束，只推当前图层）───
const LAYER_THUMB_MAX = 128
let layerThumbTimer: ReturnType<typeof setTimeout> | null = null

/** 用内存中的绘制画布生成当前图层缩略图（不读盘、不触发地图重渲染） */
function buildLayerThumbDataUrl(layerId: number): string | null {
  const s = paintSession
  if (!s || s.layerId !== layerId) return null
  const w = s.canvas.width
  const h = s.canvas.height
  if (!w || !h) return null
  const scale = Math.min(1, LAYER_THUMB_MAX / Math.max(w, h))
  const tw = Math.max(1, Math.round(w * scale))
  const th = Math.max(1, Math.round(h * scale))
  const c = document.createElement('canvas')
  c.width = tw
  c.height = th
  const ctx = c.getContext('2d')
  if (!ctx) return null
  ctx.imageSmoothingEnabled = mapStore.sceneRenderMode !== 'pixelated'
  ctx.drawImage(s.canvas, 0, 0, w, h, 0, 0, tw, th)
  // 矢量内容不在绘制画布里：按缩略图尺寸直绘后叠加，避免全分辨率栅格化
  if (vectorActive.value && paintStore.mode === 'vector') {
    const vec = document.createElement('canvas')
    vec.width = tw
    vec.height = th
    if (vectorEngine.drawProjectToThumbnail(vec)) ctx.drawImage(vec, 0, 0)
  }
  return c.toDataURL('image/png')
}

/** 每笔/每次操作结束后刷新当前图层缩略图（独立信号，不用 imageRevision 以免全量重渲染） */
function scheduleLayerThumbUpdate() {
  if (layerThumbTimer) clearTimeout(layerThumbTimer)
  layerThumbTimer = setTimeout(() => {
    layerThumbTimer = null
    const s = paintSession
    if (!s) return
    const url = buildLayerThumbDataUrl(s.layerId)
    if (url) emit('layer-thumb-updated', s.layerId, url)
  }, 60)
}

async function getThumbnailDataUrl(): Promise<string | null> {
  if (!app || !PIXI || !app.renderer) return null
  // 矢量编辑时上方图层被移出舞台单独渲染成快照：截图期间先归位，避免缩略图缺层
  const needSnapshotRestore = (upperSnapshotContainer?.children.length ?? 0) > 0
  try {
    // 渲染时会先清空图层容器再异步重建图片；必须等这次重建结束，
    // 否则保存时拍到的是全透明的空容器，缩略图就会变空白
    await whenRenderIdle()
    reattachUpperContainers()
    const tileSize = mapStore.mapData.tileSize
    const mapW = mapStore.mapData.width * tileSize
    const mapH = mapStore.mapData.height * tileSize
    if (mapW <= 0 || mapH <= 0) return null

    // Render only the tile container to a render texture at map size
    const rt = PIXI.RenderTexture.create({ width: Math.ceil(mapW), height: Math.ceil(mapH) })
    app.renderer.render(tileContainer, { renderTexture: rt })
    const canvas = app.renderer.extract.canvas(rt)
    const dataUrl = canvas.toDataURL('image/png')
    rt.destroy(true)
    return dataUrl
  } catch {
    return null
  } finally {
    if (needSnapshotRestore) refreshUpperLayerSnapshot()
  }
}

// ─── 场景标记：DOM 图钉叠加层（屏幕坐标，图标不随缩放变大） ───

/** 标记.svg 内联为 DOM，fill 换成 currentColor，颜色由 CSS 控制 */
const markerIconSvg = computed(() =>
  iconMarkerRaw
    .replace(/fill="#ffffff"/gi, 'fill="currentColor"')
    .replace(/fill:white/gi, 'fill="currentColor"'),
)

/** 图钉屏幕位置：视口变化后靠 viewVersion 触发重算 */
function markerScreenStyle(m: { x: number; y: number }) {
  void viewport.viewVersion.value
  if (!app) return { display: 'none' }
  const scale = viewport.currentScale.value
  return {
    left: `${app.stage.x + m.x * scale}px`,
    top: `${app.stage.y + m.y * scale}px`,
  }
}

/**
 * 标记的屏幕坐标（相对画布左上角），供编辑器把操作胶囊贴到图钉正下方。
 * 内部读取 viewVersion / 标记坐标，父组件 computed 调用后会自动随平移缩放和拖动更新。
 */
function markerScreenPos(id: string | null): { x: number; y: number } | null {
  void viewport.viewVersion.value
  if (!id || !app) return null
  const m = mapStore.mapData.markers.find(item => item.id === id)
  if (!m) return null
  const scale = viewport.currentScale.value
  return { x: app.stage.x + m.x * scale, y: app.stage.y + m.y * scale }
}

/** 图钉下方坐标文本：(用户坐标) */
function markerCoordText(p: { x: number; y: number } | null) {
  if (!p) return ''
  return `(${Math.round(toUserX(p.x))},${Math.round(toUserY(p.y))})`
}

let draggingMarkerId: string | null = null

function onMarkerDragMove(e: MouseEvent) {
  if (!draggingMarkerId) return
  const world = viewport.clientToWorld(e.clientX, e.clientY)
  if (world) mapStore.updateMarkerPosition(draggingMarkerId, world.x, world.y)
}

function onMarkerDragEnd() {
  draggingMarkerId = null
  window.removeEventListener('mousemove', onMarkerDragMove)
}

/** 点选 / 拖动标记（仅左键；拖动时全局监听，移出画布也不中断） */
function onMarkerMouseDown(m: SceneMarker, e: MouseEvent) {
  // 左右键都阻断画布事件：右键不再触发平移/放置
  e.stopPropagation()
  if (e.button !== 0) return
  e.preventDefault()
  // 选已有标记时退出放置，避免误加新点
  if (mapEditorStore.markerPlacing) {
    mapEditorStore.cancelMarkerPlacing()
    markerGhost.value = null
  }
  mapEditorStore.setSelectedMarkerId(m.id)
  draggingMarkerId = m.id
  window.addEventListener('mousemove', onMarkerDragMove)
  window.addEventListener('mouseup', onMarkerDragEnd, { once: true })
}

/** 双击标记：选中并把焦点交给浮条的名称输入。右键只负责选中，操作统一在浮条里 */
function onMarkerActivate(m: SceneMarker) {
  mapEditorStore.setSelectedMarkerId(m.id)
  emit('marker-activate', m.id)
}

// 放置时的幽灵图钉：跟随鼠标显示落点坐标
const markerGhost = ref<{ x: number; y: number } | null>(null)

// 进入放置时鼠标可能没再动过：直接用上一次记录的光标位置显示幽灵，避免光标“消失”
watch(
  () => mapEditorStore.markerPlacing,
  (placing) => {
    if (!placing) {
      markerGhost.value = null
      return
    }
    const cx = mapEditorStore.cursorX
    const cy = mapEditorStore.cursorY
    if (cx !== null && cy !== null) markerGhost.value = { x: cx, y: cy }
  },
)

defineExpose({
  redraw,
  cursorGridPos,
  renderAllLayers,
  showTransformBox: transform.showTransformBox,
  removeTransformBox: transform.removeTransformBox,
  resetCanvasState,
  getThumbnailDataUrl,
  getLayerThumbnailDataUrl,
  placeImageFromPath,
  undoActive,
  redoActive,
  copyActive,
  pasteActive,
  deleteActive,
  flipActive,
  groupActive,
  ungroupActive,
  layerUpActive,
  layerDownActive,
  canUndoPaint,
  canRedoPaint,
  zoomPercent,
  zoomIn,
  zoomOut,
  resetZoom,
  markerScreenPos,
  /** 地图保存/切换前：烘焙矢量内容但保留“矢量模式”选择，随后切图会自动重新进入 */
  exitVectorPaint: () => exitVectorMode(false),
})
</script>

<template>
  <div
    ref="canvasRef"
    class="map-canvas"
    :class="{ 'marker-placing': mapEditorStore.markerPlacing }"
    @mousedown="onMouseDown"
  >
    <!-- 矢量绘制画布：铺满地图画布、无 CSS transform，缩放/旋转由 paper view.matrix 处理 -->
    <canvas
      v-if="vectorActive"
      ref="vectorCanvasRef"
      class="map-vector-canvas"
      :style="{ opacity: vectorCanvasOpacity }"
      @wheel="onVectorWheel"
      @pointerdown.capture="onVectorPointerDownCapture"
      @pointermove.capture="onVectorPointerMoveCapture"
      @pointerup.capture="onVectorPointerUpCapture"
      @pointercancel.capture="onVectorPointerUpCapture"
      @pointerleave="onVectorPointerLeave"
    ></canvas>
    <!-- 矢量投影层：与图片像素坐标一致，整体套用仿射矩阵 -->
    <div
      v-if="vectorActive && paintStore.mode === 'vector' && vectorOverlayStyle"
      class="map-vector-overlay"
      :style="vectorOverlayStyle"
    >
      <!-- 上方图层快照：矢量画布恒在 Pixi 之上，用这张快照把「当前矢量图层之上」的图层按原顺序叠回去 -->
      <canvas ref="upperSnapshotRef" class="map-upper-snapshot" :style="upperSnapshotStyle"></canvas>
      <svg
        class="map-vector-svg"
        :viewBox="`0 0 ${paintStore.artboardWidth} ${paintStore.artboardHeight}`"
        preserveAspectRatio="none"
      >
        <!-- 框选矩形：矢量模式下拖拽框选对象时显示 -->
        <rect
          v-if="paintStore.selection"
          :x="paintStore.selection.x"
          :y="paintStore.selection.y"
          :width="paintStore.selection.w"
          :height="paintStore.selection.h"
          fill="rgba(129, 140, 248, 0.10)"
          :stroke="VEC_SEL"
          :stroke-width="vectorBoxStroke"
          stroke-linejoin="round"
        />
        <!-- 选中变换框 -->
        <template v-if="paintStore.vectorSelBox">
          <polygon
            :points="vectorBoxPoints"
            fill="none"
            stroke="rgba(18, 20, 38, 0.85)"
            :stroke-width="vectorBoxStroke * 1.8"
            stroke-linejoin="round"
          />
          <polygon
            :points="vectorBoxPoints"
            fill="none"
            :stroke="VEC_SEL"
            :stroke-width="vectorBoxStroke"
            stroke-linejoin="round"
          />
          <rect
            v-for="(h, i) in paintStore.vectorSelBox.handles"
            :key="i"
            :x="h.x - vectorHandleSize / 2"
            :y="h.y - vectorHandleSize / 2"
            :width="vectorHandleSize"
            :height="vectorHandleSize"
            fill="#ffffff"
            :stroke="VEC_SEL_DEEP"
            :stroke-width="vectorBoxStroke * 0.85"
          />
          <line
            :x1="paintStore.vectorSelBox.rotateTop.x"
            :y1="paintStore.vectorSelBox.rotateTop.y"
            :x2="paintStore.vectorSelBox.rotateAt.x"
            :y2="paintStore.vectorSelBox.rotateAt.y"
            :stroke="VEC_SEL"
            :stroke-width="vectorBoxStroke"
          />
          <circle
            :cx="paintStore.vectorSelBox.rotateAt.x"
            :cy="paintStore.vectorSelBox.rotateAt.y"
            :r="vectorRotateRadius"
            :fill="VEC_SEL"
            :stroke="VEC_SEL_DEEP"
            :stroke-width="vectorBoxStroke * 0.85"
          />
        </template>
        <!-- 塑形锚点 -->
        <template v-if="paintStore.reshapePts">
          <path
            v-for="(d, i) in paintStore.reshapeOutline || []"
            :key="'o' + i"
            :d="d"
            fill="none"
            :stroke="VEC_SEL"
            :stroke-width="vectorBoxStroke"
            stroke-linejoin="round"
          />
          <g v-for="(pt, i) in paintStore.reshapePts" :key="i">
            <template v-if="pt.handleIn">
              <line
                :x1="pt.x" :y1="pt.y" :x2="pt.handleIn.x" :y2="pt.handleIn.y"
                stroke="rgba(18, 20, 38, 0.7)" :stroke-width="vectorBoxStroke * 1.2"
              />
              <circle
                :cx="pt.handleIn.x" :cy="pt.handleIn.y" :r="vectorPointSize * 0.38"
                fill="#ffffff" :stroke="VEC_SEL_DEEP" :stroke-width="vectorBoxStroke * 0.85"
              />
            </template>
            <template v-if="pt.handleOut">
              <line
                :x1="pt.x" :y1="pt.y" :x2="pt.handleOut.x" :y2="pt.handleOut.y"
                stroke="rgba(18, 20, 38, 0.7)" :stroke-width="vectorBoxStroke * 1.2"
              />
              <circle
                :cx="pt.handleOut.x" :cy="pt.handleOut.y" :r="vectorPointSize * 0.38"
                fill="#ffffff" :stroke="VEC_SEL_DEEP" :stroke-width="vectorBoxStroke * 0.85"
              />
            </template>
            <circle
              :cx="pt.x" :cy="pt.y" :r="vectorPointSize / 2"
              :fill="pt.selected ? VEC_SEL : '#ffffff'"
              :stroke="VEC_SEL_DEEP" :stroke-width="vectorBoxStroke * 0.85"
            />
          </g>
        </template>
        <!-- 钢笔（自定义形状）进行中预览：固定配色（不跟随颜色面板）——
             虚线橡皮筋 + 已落锚点方块 + 首锚收尾热点（进入命中区脉冲高亮） -->
        <template v-if="paintStore.penState">
          <polyline
            :points="vectorPenPoints"
            fill="none"
            :stroke="VEC_SEL"
            :stroke-width="vectorPenStroke"
            :stroke-dasharray="vectorPenDash"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <circle
            v-if="paintStore.penState.cursor && !paintStore.penState.closing"
            :cx="paintStore.penState.cursor.x"
            :cy="paintStore.penState.cursor.y"
            :r="vectorPenAnchorSize * 0.42"
            :fill="VEC_SEL"
          />
          <rect
            v-for="(pt, i) in paintStore.penState.anchors"
            :key="'pen' + i"
            :x="pt.x - vectorPenAnchorSize / 2"
            :y="pt.y - vectorPenAnchorSize / 2"
            :width="vectorPenAnchorSize"
            :height="vectorPenAnchorSize"
            fill="#ffffff"
            :stroke="VEC_SEL_DEEP"
            :stroke-width="vectorPenStroke"
          />
          <circle
            v-if="paintStore.penState.anchors.length >= 3"
            class="pen-close-hotspot"
            :class="{ 'pen-close-hotspot-active': paintStore.penState.closing }"
            :cx="paintStore.penState.anchors[0].x"
            :cy="paintStore.penState.anchors[0].y"
            :r="vectorPenRing"
            :fill="paintStore.penState.closing ? 'rgba(129, 140, 248, 0.28)' : 'none'"
            :stroke="VEC_SEL"
            :stroke-width="vectorPenStroke"
          />
        </template>
      </svg>
      <textarea
        v-if="paintStore.textEdit"
        ref="textAreaRef"
        class="map-vector-text"
        :style="vectorTextEditStyle"
        spellcheck="false"
        autocomplete="off"
        @input="onVectorTextInput"
        @compositionstart="onVectorTextCompositionStart"
        @compositionend="onVectorTextCompositionEnd"
        @keydown="onVectorTextKeydown"
      ></textarea>
    </div>
    <!-- 矢量画笔/橡皮光标（屏幕坐标，DOM 圆圈抗锯齿） -->
    <div
      v-if="vectorCursorStyle"
      class="map-vector-brush-cursor"
      :style="vectorCursorStyle"
    ></div>
    <!-- 碰撞叠加层：屏幕坐标 canvas，置于矢量画布之上，避免被图像层遮挡 -->
    <canvas ref="collisionOverlayRef" class="map-collision-overlay"></canvas>
    <!-- 场景标记：DOM 图钉叠加层（图钉尖对准坐标，标签显示「标记名(用户坐标)」） -->
    <div class="map-marker-layer">
      <!-- 放置中的幽灵图钉：半透明，跟随鼠标并实时显示落点坐标 -->
      <div
        v-if="mapEditorStore.markerPlacing && markerGhost"
        class="map-marker is-ghost"
        :style="markerScreenStyle(markerGhost)"
      >
        <div class="map-marker-icon" v-html="markerIconSvg"></div>
        <span class="map-marker-label">
          <b>新标记</b><span>{{ markerCoordText(markerGhost) }}</span>
        </span>
      </div>
      <div
        v-for="m in mapStore.mapData.markers"
        :key="m.id"
        class="map-marker"
        :class="{ 'is-selected': m.id === mapEditorStore.selectedMarkerId }"
        :style="markerScreenStyle(m)"
        @mousedown="onMarkerMouseDown(m, $event)"
        @dblclick.stop="onMarkerActivate(m)"
        @contextmenu.prevent.stop="mapEditorStore.setSelectedMarkerId(m.id)"
      >
        <div class="map-marker-icon" v-html="markerIconSvg"></div>
        <span class="map-marker-label">
          <b>{{ m.name }}</b><span>{{ markerCoordText(m) }}</span>
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.map-canvas {
  position: relative;
  width: 100%;
  height: 100%;
  background: rgb(30, 30, 30);
  overflow: hidden;
  outline: none;
}

/* 放置标记：隐藏系统光标，由跟随鼠标的半透明幽灵图钉充当指针（覆盖各工具自设光标） */
.map-canvas.marker-placing {
  cursor: none;
}

.map-canvas.marker-placing > canvas {
  cursor: none !important;
}

.map-vector-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 10;
  touch-action: none;
}

/* 碰撞叠加层：屏幕坐标 canvas，位于矢量画布（z=10）与矢量投影层（z=11）之上 */
.map-collision-overlay {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 12;
}

.map-vector-overlay {
  position: absolute;
  left: 0;
  top: 0;
  pointer-events: none;
  z-index: 11;
}

/* 上方图层快照：坐标与画板一致（随覆盖层矩阵缩放/平移），位于矢量画布之上、选框之下 */
.map-upper-snapshot {
  position: absolute;
  pointer-events: none;
}

.map-vector-svg {
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
}

/* 钢笔首锚收尾热点：光标进入命中半径时描边脉冲，明确「点这里闭合」 */
.pen-close-hotspot-active {
  animation: pen-close-pulse 0.9s ease-in-out infinite;
}
@keyframes pen-close-pulse {
  0%, 100% { stroke-opacity: 1; }
  50% { stroke-opacity: 0.35; }
}

/* 文字编辑框：与 paper PointText 对齐（无 padding/border，尺寸由引擎写入） */
.map-vector-text {
  position: absolute;
  pointer-events: auto;
  margin: 0;
  padding: 0;
  border: none;
  outline: 1px dashed rgba(24, 27, 50, 0.7);
  outline-offset: 2px;
  background: transparent;
  resize: none;
  overflow: hidden;
  white-space: pre;
  font-family: 'HarmonyOS Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-weight: 500;
  caret-color: currentColor;
  box-sizing: content-box;
  transform-origin: 0 0;
}

.map-vector-cursor {
  position: absolute;
  width: 0;
  height: 0;
  overflow: visible;
  pointer-events: none;
}

/* 矢量画笔圆圈：屏幕坐标 DOM 圆环，任意缩放无锯齿 */
.map-vector-brush-cursor {
  position: absolute;
  box-sizing: border-box;
  border-radius: 50%;
  border: 1.5px solid rgba(255, 255, 255, 0.95);
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.55);
  pointer-events: none;
  z-index: 12;
}

/* 场景标记叠加层：铺满画布、默认不拦截事件，只有图钉可点 */
.map-marker-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 13;
}

.map-marker {
  position: absolute;
  width: 0;
  height: 0;
  --mk-ink: #e3e7ed;   /* 未选中：灰白 */
  --mk-red: #ff5252;   /* 选中：红 */
}

/* 图钉：钉尖位于 (left, top)，所以图标向上偏移半个宽/整高 */
.map-marker-icon {
  position: absolute;
  left: -13px;
  top: -26px;
  width: 26px;
  height: 26px;
  color: var(--mk-ink);
  pointer-events: auto;
  cursor: default;
  transition: color 0.16s ease, transform 0.16s ease;
}

.map-marker-icon :deep(svg) {
  width: 100%;
  height: 100%;
  display: block;
  overflow: visible;
}

/* 唯一的"阴影"：1px 深色描边（svg 是 1024 视图框，38 用户单位 ≈ 26px 下的 1px），
   浅色地图上也看得清；不用发光/模糊投影，避免显脏 */
.map-marker-icon :deep(path) {
  stroke: rgba(0, 0, 0, 0.62);
  stroke-width: 38;
  stroke-linejoin: round;
  paint-order: stroke fill;
}

/* 标签在图钉下方：标记名(用户坐标) */
.map-marker-label {
  position: absolute;
  left: 0;
  top: 5px;
  transform: translateX(-50%);
  display: inline-flex;
  align-items: baseline;
  gap: 3px;
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(14, 16, 20, 0.86);
  white-space: nowrap;
  pointer-events: auto;
  cursor: default;
  user-select: none;
  transition: background 0.16s ease, border-color 0.16s ease;
}

.map-marker-label b {
  font-size: 11px;
  font-weight: 600;
  line-height: 1.15;
  color: #e8ebf0;
  transition: color 0.16s ease;
}

.map-marker-label span {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 10px;
  line-height: 1.15;
  color: #98a0aa;
  transition: color 0.16s ease;
}

/* 选中态：灰白 → 红（只换颜色，不发光），轻微放大，标签染红 */
.map-marker.is-selected .map-marker-icon {
  color: var(--mk-red);
  transform: scale(1.07);
  transform-origin: 50% 88%;
}

.map-marker.is-selected .map-marker-label {
  background: rgba(255, 82, 82, 0.14);
  border-color: rgba(255, 82, 82, 0.45);
}

.map-marker.is-selected .map-marker-label b { color: #ffd3d3; }
.map-marker.is-selected .map-marker-label span { color: rgba(255, 188, 188, 0.72); }

/* 放置预览：半透明、不拦截事件 */
.map-marker.is-ghost {
  opacity: 0.55;
}

.map-marker.is-ghost .map-marker-icon {
  pointer-events: none;
}

.map-marker.is-ghost .map-marker-label {
  pointer-events: none;
}
</style>
