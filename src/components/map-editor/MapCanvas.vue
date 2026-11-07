<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick, type CSSProperties } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { useMapStore, type MapResource, type ImageData as MapImageData, type SceneMarker } from '../../stores/map'
import { useResourceStore } from '../../stores/resource'
import { useMapEditorStore } from '../../stores/mapEditor'
import { useProjectStore } from '../../stores/project'
import { useEditorStore } from '../../stores/editor'
import { isSvgSource, rasterizeSvgImage, SVG_RASTER_SCALE } from '../../utils/svgRasterize'
import { imageWorldToLocal, imageLocalToWorld } from '../../utils/mapImageGeometry'
import { usePaintStore } from '../../stores/paint'
import { rgbaCss, hexToRgba } from '../paint-editor/utils/artboardExport'
import { useMapViewport } from '../../composables/useMapViewport'
import { useImageTransform } from '../../composables/useImageTransform'
import { useShapeLayerEditor } from '../../composables/useShapeLayerEditor'
import { useTilePainter } from '../../composables/useTilePainter'
import { usePaperScope } from '../paint-editor/composables/usePaperScope'
import { createBitmapPen } from '../paint-editor/utils/bitmapPen'
import { ensurePaintFont } from '../paint-editor/utils/paintFont'
import { collectSnapLines, snapAxisValue, snapRectOffset, snapThreshold } from '../../utils/smartSnap'
import {
  SELECTION_COLOR as VEC_SEL,
  SELECTION_COLOR_DEEP as VEC_SEL_DEEP,
  SELECTION_COLOR_HEX,
  SELECTION_COLOR_DEEP_HEX,
  SELECTION_FILL_ALPHA,
  SELECTION_STROKE_PX,
} from '../../utils/selectionStyle'
import { toUserX, toUserY } from '../../utils/coords'
import { tileBaseGid, tileFlipFlags } from '../../utils/tileGid'
import {
  createLayerTransform,
  tileSpriteTransform,
  worldToTile,
  type TileLayerTransform,
} from '../../utils/tileLayerTransform'
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
const resourceStore = useResourceStore()

// 解析资源路径为浏览器可加载的 URL
const resolvedPathCache = new Map<string, string>()
async function resolveImagePath(path: string): Promise<string> {
  const cached = resolvedPathCache.get(path)
  if (cached) return cached

  // 绘制测试里的内存缩放图是 data URL，直接可加载
  if (path.startsWith('data:')) {
    resolvedPathCache.set(path, path)
    return path
  }

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
      // 读盘失败的地址不缓存：否则文件补回来后画面也永远回不来
      return convertFileSrc(fullPath)
    }
  } else {
    try {
      url = await invoke<string>('read_image_as_data_url', { path })
    } catch {
      return convertFileSrc(path)
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
/** 已渲染的图块内容：layerId → ("x,y" → GID)，用于增量比对，只重建真正变化的格子 */
let renderedTileGids: Map<number, Map<string, number>> = new Map()

// ─── 增量渲染状态（切层/重渲染不再清空全部容器，避免画面闪烁、图层"打架"）───
/** 图层 id → 已渲染内容签名；签名未变则复用现有精灵 */
const layerRenderKeys = new Map<number, string>()
/** 上次渲染的图层结构（地图 + id/类型/顺序） */
let lastRenderStructureKey = ''
/** 上次渲染时的图层 id 集合：结构变化（增删图层）时只重建新出现的图层 */
let lastStructureLayerIds = new Set<number>()
/** 上次渲染的地图序号：换图时即使图层 id 相同也必须全部重建 */
let lastRenderMapLoadCount = -1

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
  // 地图编辑器是按需渲染（手动调用 app.render()），不需要 PixiJS 持续 ticker。
  // 不停止的话，即使切到代码页面（v-show 隐藏），ticker 仍以 60fps 渲染空场景，
  // WebView2 GPU 进程会持续占满 CPU。
  app.ticker.stop()
  canvasRef.value.appendChild(app.canvas)
  // Pixi 画布必须绝对定位在容器左上角：模板里前序元素/空白文本会产生行盒，
  // inline canvas 会被往下挤，导致鼠标坐标与叠加层整体错位
  app.canvas.classList.add('map-pixi-canvas')

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
    img.onerror = () => {
      // 失败多半是读盘失败后的回退地址：清掉路径缓存，下次重新读盘再试
      resolvedPathCache.delete(src)
      reject(new Error(`无法加载图片: ${src}`))
    }
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
  renderedTileGids.delete(layerId)
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

/** 图块层整层变换签名：位置 / 缩放 / 旋转变化时整体重建 */
function layerTransformKey(layer: any): string {
  return [
    layer.offsetX ?? 0, layer.offsetY ?? 0,
    layer.scaleX ?? 1, layer.scaleY ?? 1,
    layer.rotation ?? 0,
    mapStore.mapData.width, mapStore.mapData.height, mapStore.mapData.tileSize,
  ].join(',')
}

/** 图层内容签名：图块层只跟整层变换 / 采样方式走（图块内容由增量比对，不再整层重建），图片层按自身签名，形状层无内容 */
function layerContentKey(layer: any): string {
  if (layer.type === 'drawing') {
    return `tiles:${currentScaleMode}:${layerTransformKey(layer)}`
  }
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
  tileContainer?.sortChildren()
}

async function renderTile(layerId: number, x: number, y: number, tileId: number) {
  if (tileId === 0) {
    removeTile(layerId, x, y)
    return
  }

  const key = `${layerId}:${x},${y}`

  // GID 高位是图块镜像标志，查图块集前先剥掉
  const baseGid = tileBaseGid(tileId)
  const flags = tileFlipFlags(tileId)

  // 通过 firstgid 范围找到对应的 tileSet
  const tileSets = mapStore.mapData.tileSets
  let matchedTileSet: any = null
  for (let i = tileSets.length - 1; i >= 0; i--) {
    if (baseGid >= tileSets[i].firstgid) {
      matchedTileSet = tileSets[i]
      break
    }
  }
  if (!matchedTileSet) return
  const tileIndex = baseGid - matchedTileSet.firstgid

  // 在地图级素材库中优先按 id/firstgid 精确匹配，回退到路径匹配。
  // 必须排除图片素材：它们的 firstgid 只是占位值，抢到匹配会画出空白/巨大图
  const resource: MapResource | null = mapStore.mapData.resources.find(
    (r: MapResource) => r.resourceType !== 'image' && r.id === matchedTileSet.id
  ) ?? mapStore.mapData.resources.find(
    (r: MapResource) => r.resourceType !== 'image' && r.firstgid === matchedTileSet.firstgid
  ) ?? mapStore.mapData.resources.find(
    (r: MapResource) => r.resourceType !== 'image' && r.path === matchedTileSet.imagePath
  ) ?? null
  if (!resource) return

  const texture = await getTileTexture(resource, tileIndex)
  if (!texture) return

  let sprite = tileSprites.get(key)
  const tileSize = mapStore.mapData.tileSize

  if (!sprite) {
    sprite = new PIXI.Sprite(texture)
    sprite.anchor.set(0.5)
    const container = getOrCreateLayerContainer(layerId)
    container.addChild(sprite)
    tileSprites.set(key, sprite)
  } else if (sprite.texture !== texture) {
    sprite.texture = texture
  }
  // 位置按整层变换后的图块中心摆放（锚点 0.5），尺寸永远是素材自己的切片大小 × 整层缩放
  // （同 Tiled / Unity 的网格模型；SVG 2x 超采样纹理也在这里压回逻辑尺寸）
  const t = layerTileTransform(layerId)
  const st = tileSpriteTransform(t, x, y, tileSize, resource.tileWidth, resource.tileHeight)
  sprite.anchor.set(0.5)
  sprite.x = st.x
  sprite.y = st.y
  sprite.rotation = st.rotation
  sprite.width = resource.tileWidth * Math.abs(st.scaleX)
  sprite.height = resource.tileHeight * Math.abs(st.scaleY)
  // 负缩放实现镜像：整层缩放方向 × 图块自身的镜像标志
  const sx = (st.scaleX < 0 ? -1 : 1) * (flags.flipH ? -1 : 1)
  const sy = (st.scaleY < 0 ? -1 : 1) * (flags.flipV ? -1 : 1)
  sprite.scale.x = Math.abs(sprite.scale.x) * sx
  sprite.scale.y = Math.abs(sprite.scale.y) * sy
  // 记录已渲染的 GID：下一次增量比对时内容没变就不再碰它
  let gids = renderedTileGids.get(layerId)
  if (!gids) {
    gids = new Map<string, number>()
    renderedTileGids.set(layerId, gids)
  }
  gids.set(`${x},${y}`, tileId)
}

function removeTile(layerId: number, x: number, y: number) {
  const key = `${layerId}:${x},${y}`
  const sprite = tileSprites.get(key)
  if (sprite) {
    sprite.parent?.removeChild(sprite)
    sprite.destroy()
    tileSprites.delete(key)
  }
  renderedTileGids.get(layerId)?.delete(`${x},${y}`)
}

async function renderAllLayers() {
  if (!app || !PIXI) return

  const layers = mapStore.mapData.layers

  // 地图切换 / 图层增删 / 顺序变化会影响图层 id 的复用，需要判断哪些容器必须重建
  const structureKey = `${mapStore.mapLoadCount}:${layers.map(l => `${l.id}:${l.type}`).join(',')}`
  const structureChanged = structureKey !== lastRenderStructureKey
  const mapLoadCount = mapStore.mapLoadCount
  const mapChanged = mapLoadCount !== lastRenderMapLoadCount
  const previousLayerIds = lastStructureLayerIds
  if (structureChanged) {
    lastRenderStructureKey = structureKey
    lastStructureLayerIds = new Set(layers.map(l => l.id))
    lastRenderMapLoadCount = mapLoadCount
  }

  // 移除不再存在的图层容器
  const activeIds = new Set(layers.map(l => l.id))
  for (const [id, container] of layerContainers) {
    if (!activeIds.has(id)) {
      tileContainer.removeChild(container)
      container.destroy({ children: true })
      layerContainers.delete(id)
      layerRenderKeys.delete(id)
      renderedTileGids.delete(id)
    }
  }

  // 确保每个图层都有容器，设置 zIndex 和可见性（但不 addChild）
  for (let i = 0; i < layers.length; i++) {
    const layer = layers[i]
    const container = getOrCreateLayerContainer(layer.id)
    container.zIndex = i
    container.visible = layer.visible
    // 只清理真正需要重建的图层：换图时全部清理；增删图层时只清理新出现的 id。
    // 已有图层保留精灵和内容签名，新增一个图层不会把整张地图的图块全部重画。
    if (structureChanged && (mapChanged || !previousLayerIds.has(layer.id))) {
      clearLayerContainer(layer.id)
      layerRenderKeys.delete(layer.id)
    }
  }

  // 逐图层增量重建：签名未变则保留现有内容（切图/切层不再出现空画布闪烁）
  for (const layer of layers) {
    const key = layerContentKey(layer)
    if (layerRenderKeys.get(layer.id) !== key) {
      if (layer.type === 'drawing') {
        clearLayerContainer(layer.id)
        const gids = new Map<string, number>()
        renderedTileGids.set(layer.id, gids)
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
    } else if (layer.type === 'drawing') {
      // 图块内容变了（画/擦/撤销）：只处理真正变化的格子，不再整层销毁重建
      await syncLayerTiles(layer)
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
  // 视口裁剪放到下一帧统一处理，避免每次落笔都遍历全部精灵
  scheduleSpriteVisibility()
  // 矢量模式下把当前图层之上的图层叠回矢量画布之上，保持整张画布仍按图层顺序显示
  refreshUpperLayerSnapshot()
}

/**
 * 图块层增量同步：只重建与上次渲染不一致的格子。
 * 遍历开销是 O(已画格数)（只是 Map 比对，不分配精灵），真正变化的才 await 重建。
 */
async function syncLayerTiles(layer: any) {
  let gids = renderedTileGids.get(layer.id)
  if (!gids) {
    gids = new Map<string, number>()
    renderedTileGids.set(layer.id, gids)
  }

  // 1) 新增格子 / 内容变化（画、填充、改朝向、撤销恢复）
  for (const posKey in layer.tiles) {
    const tileId = layer.tiles[posKey]
    if (gids.get(posKey) === tileId) continue
    const comma = posKey.indexOf(',')
    const x = Number(posKey.slice(0, comma))
    const y = Number(posKey.slice(comma + 1))
    await renderTile(layer.id, x, y, tileId)
  }

  // 2) 已删除的格子（擦除、撤销、图层批量删除）——迭代中删除 Map 是安全的
  for (const posKey of gids.keys()) {
    if (posKey in layer.tiles) continue
    const comma = posKey.indexOf(',')
    const x = Number(posKey.slice(0, comma))
    const y = Number(posKey.slice(comma + 1))
    removeTile(layer.id, x, y)
  }
}

// ─── 视口裁剪：屏幕外的图块精灵不参与绘制 ───
/** 缩略图截图期间暂停裁剪，保证截图包含整张地图 */
let thumbnailCaptureDepth = 0
let visibilityFrame = 0

function updateSpriteVisibility() {
  if (!app || thumbnailCaptureDepth > 0) return
  const scale = Math.max(0.05, viewport.currentScale.value)
  const pad = mapStore.mapData.tileSize * 2
  const left = -app.stage.x / scale - pad
  const top = -app.stage.y / scale - pad
  const right = left + app.screen.width / scale + pad * 2
  const bottom = top + app.screen.height / scale + pad * 2
  for (const sprite of tileSprites.values()) {
    if (!sprite || sprite.destroyed) continue
    // 移动工具正在拖拽的原始图块被工具临时隐藏，不要在这里翻出来
    if (sprite.__toolHidden) continue
    // 旋转 / 镜像时用旋转后的包围盒近似（多算一点没关系，宁可多画不可漏画）
    const w = Math.abs(sprite.width || 0)
    const h = Math.abs(sprite.height || 0)
    const rot = Math.abs(sprite.rotation || 0)
    const cos = Math.abs(Math.cos(rot))
    const sin = Math.abs(Math.sin(rot))
    const hw = (w * cos + h * sin) / 2
    const hh = (w * sin + h * cos) / 2
    sprite.visible = sprite.x + hw > left && sprite.x - hw < right
      && sprite.y + hh > top && sprite.y - hh < bottom
  }
}

/** 每帧最多做一次裁剪计算（平移/缩放的每一帧都能跟上，又不重复计算） */
function scheduleSpriteVisibility() {
  if (visibilityFrame || thumbnailCaptureDepth > 0) return
  visibilityFrame = requestAnimationFrame(() => {
    visibilityFrame = 0
    updateSpriteVisibility()
  })
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
  paintStore.shapeSize = null
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
  // 与矢量模式 / 角色绘制页同一套选区样式：靛蓝描边 + 屏幕恒定线宽
  const SEL = SELECTION_COLOR_HEX
  const SEL_DEEP = SELECTION_COLOR_DEEP_HEX
  const strokeW = SELECTION_STROKE_PX / scale

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
    g.fill({ color: SEL, alpha: SELECTION_FILL_ALPHA })
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
  syncFloatShapeSize()
}

/** 地图工具栏尺寸输入框：显示浮动图形本体宽高（未旋转，画布像素）；无浮选时为空 */
function syncFloatShapeSize() {
  paintStore.shapeSize = floatCanvas
    ? {
        w: Math.abs(floatCanvas.width * floatXf.sx),
        h: Math.abs(floatCanvas.height * floatXf.sy),
      }
    : null
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
  paintStore.shapeSize = null
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
  paintStore.shapeSize = null
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
  paintStore.shapeSize = null
  s.dirty = true
  schedulePaintSave()
}

// 工具栏删除：只删除浮动选区内容，不影响图层本身
function deleteSelection() {
  if (floatCanvas) deleteFloatingPixels()
}

/**
 * 工具栏数值改尺寸（位图）：把浮动图形缩放到精确宽高。
 * 中心与旋转角不变（居中锚定，与角色绘制页一致）；翻转态只改绝对值。
 */
function resizeFloatShape(w: number, h: number) {
  if (!floatCanvas) return
  const bw = floatCanvas.width
  const bh = floatCanvas.height
  if (bw <= 0 || bh <= 0) return
  const sx = (floatXf.sx < 0 ? -1 : 1) * (Math.max(1, w) / bw)
  const sy = (floatXf.sy < 0 ? -1 : 1) * (Math.max(1, h) / bh)
  if (Math.abs(sx - floatXf.sx) < 1e-6 && Math.abs(sy - floatXf.sy) < 1e-6) return
  floatXf.sx = sx
  floatXf.sy = sy
  compositeFloat()
  if (paintSession) {
    paintSession.dirty = true
    schedulePaintSave()
  }
}

/** 工具栏数值改选中对象尺寸：矢量 → paper 选框，位图 → 浮动图形 */
function resizeShapeSize(w: number, h: number) {
  if (vectorActive.value && paintStore.mode === 'vector') {
    vectorEngine.resizeSelectionTo(w, h)
  } else {
    resizeFloatShape(w, h)
  }
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

/** 形状层悬停反馈：锚点=正常指针、框内=移动、其他=十字；矩形/钢笔=十字 */
function updateCollisionCursor(world: { x: number; y: number }) {
  if (mapStore.activeMode !== 'shape') return
  if (mapEditorStore.shapeTool !== 'select') {
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

/**
 * 叠加层几何对齐：叠加层必须覆盖 Pixi 画布本身（而不是只假设与容器同尺寸/同位置）。
 * 画布尺寸、CSS 布局或 DPR 变化后，backing store 与显示尺寸不一致会导致线条偏移、拉伸模糊。
 */
function syncCollisionOverlay() {
  const el = collisionOverlayRef.value
  const root = canvasRef.value
  if (!el || !root) return
  const rootRect = root.getBoundingClientRect()
  const pixiCanvas = app?.canvas as HTMLCanvasElement | undefined
  const targetRect = pixiCanvas ? pixiCanvas.getBoundingClientRect() : rootRect
  const cssW = Math.max(1, targetRect.width)
  const cssH = Math.max(1, targetRect.height)
  const dpr = window.devicePixelRatio || 1
  const bw = Math.max(1, Math.round(cssW * dpr))
  const bh = Math.max(1, Math.round(cssH * dpr))
  el.style.left = `${targetRect.left - rootRect.left}px`
  el.style.top = `${targetRect.top - rootRect.top}px`
  // CSS 尺寸用 backing / dpr，保证像素比严格等于 dpr，避免被浏览器二次拉伸而发虚
  el.style.width = `${bw / dpr}px`
  el.style.height = `${bh / dpr}px`
  if (el.width !== bw || el.height !== bh) {
    el.width = bw
    el.height = bh
  }
}

/** 碰撞叠加层尺寸与 DPR 同步（世界坐标绘制，需要与 Pixi 视口一致） */
function resizeCollisionOverlay() {
  syncCollisionOverlay()
  collision.drawOverlay()
}

function pickPaintSavePath(path: string, layerId: number): string {
  // 去掉历史会话叠加的后缀：老逻辑每次会话都在当前文件名后面再拼一段
  // -L<id>-draw-<ts>，名字会越滚越长（超过系统 255 字节上限后写盘直接失败）
  const base = (path.split('/').pop() || '图像')
    .replace(/\.[^.]+$/, '')
    .replace(/(-L\d+-(draw|vecbase)-[0-9a-z]+)+$/, '')
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

/** 绘制选框锚点吸附：拖拽落点的世界坐标就近对齐候选线（旋转/镜像时不吸附） */
function snapFloatHandlePoint(
  world: { x: number; y: number },
  img: MapImageData,
): { x: number; y: number } {
  const s = paintSession
  if (!s) return world
  if (Math.abs(img.rotation ?? 0) > 1e-3) return world
  const sx = img.scaleX ?? img.scale ?? 1
  const sy = img.scaleY ?? img.scale ?? 1
  if (sx <= 0 || sy <= 0) return world
  const ts = Math.max(1, mapStore.mapData.tileSize)
  const lines = collectSnapLines(
    mapStore.mapData.layers,
    mapStore.mapData.width * ts,
    mapStore.mapData.height * ts,
    s.layerId,
  )
  const threshold = snapThreshold(viewport.currentScale.value)
  return {
    x: snapAxisValue(world.x, lines.xs, ts, threshold),
    y: snapAxisValue(world.y, lines.ys, ts, threshold),
  }
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
    // 智能吸附：拖拽锚点时落点就近对齐候选线（与选区移动吸附同一套阈值/候选线）
    const sp = mapEditorStore.smartSnap ? snapFloatHandlePoint(world, img) : world
    const lp = imageWorldToLocal(img, sp.x, sp.y)
    const ps = { x: lp.x * s.canvas.width, y: lp.y * s.canvas.height }
    const cos = Math.cos(floatStartXf.angle)
    const sin = Math.sin(floatStartXf.angle)
    const dx = ps.x - scaleAnchorPx.x
    const dy = ps.y - scaleAnchorPx.y
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
    const source = await loadImage(img.imagePath).catch(() => null)
    if (!source) {
      // 图片文件丢失（项目目录被重置 / 被外部清理）时不能直接判定会话失败，
      // 否则这一层的所有绘制工具都会永久失效。确认文件确实不在后用图层记录的尺寸重建空白画板
      const fullPath = img.imagePath.startsWith('assets/')
        ? `${projectStore.root}/${img.imagePath}`
        : img.imagePath
      const exists = await invoke<boolean>('path_exists', { path: fullPath }).catch(() => true)
      if (exists) throw new Error(`无法加载图片: ${img.imagePath}`)
      console.warn('[MapCanvas] 绘制图层图片不存在，已重建空白画板:', img.imagePath)
    }
    if (mapStore.selectedImageLayerId !== layerId) return false
    // 绘制图层：画布尺寸 = 地图尺寸（不再设固定出血区，超出范围由落笔时自动扩展，见 ensurePaintCanvasCoversWorld）
    const isBackground = !!img.background
    const mapW = Math.max(1, mapStore.mapData.width * mapStore.mapData.tileSize)
    const mapH = Math.max(1, mapStore.mapData.height * mapStore.mapData.tileSize)
    // 图片丢失时按图层记录的尺寸复原画板，保持原来的绘制范围
    const srcW = source ? (source.naturalWidth || source.width) : Math.max(1, Math.round(img.width || mapW))
    const srcH = source ? (source.naturalHeight || source.height) : Math.max(1, Math.round(img.height || mapH))
    // 已有矢量内容（底稿/矢量坐标以画布像素为准）时保持原画布原点，避免内容错位
    const hasVectorContent = !!img.vectorData || !!img.vectorBasePath || vectorLayerCache.has(layerId)
    const canRepad = isBackground && !hasVectorContent
    const offsetX = img.position?.[0] ?? 0
    const offsetY = img.position?.[1] ?? 0
    let canvasW = srcW
    let canvasH = srcH
    let drawX = 0
    let drawY = 0
    let newPosX = offsetX
    let newPosY = offsetY
    if (isBackground) {
      if (canRepad) {
        // 背景画板 = 地图尺寸；旧版「出血区」图层迁移：内容按原 position 偏移画入，
        // 超出地图范围的旧出血区内容被裁掉，原点归零与地图左上角对齐
        canvasW = mapW
        canvasH = mapH
        drawX = offsetX
        drawY = offsetY
        newPosX = 0
        newPosY = 0
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
    if (source) canvas.getContext('2d')!.drawImage(source, drawX, drawY)
    const geometryChanged = isBackground && canRepad && (canvasW !== srcW || canvasH !== srcH || offsetX !== 0 || offsetY !== 0)
    if (geometryChanged) {
      img.width = canvasW
      img.height = canvasH
      img.position = [newPosX, newPosY]
      img.scaleX = 1
      img.scaleY = 1
      img.scale = 1
      // 画板尺寸重排直接改了 mapData，通知自动保存机制“脏了”
      mapStore.markMapDataDirty()
    }
    const texture = PIXI_.Texture.from(canvas)
    texture.source.scaleMode = currentScaleMode
    let sprite: any = null
    const container = layerContainers.get(layerId)
    for (const child of container?.children ?? []) {
      if (child instanceof PIXI_.Sprite) { sprite = child; break }
    }
    paintSession = {
      layerId,
      mapName: mapStore.mapData.name,
      canvas,
      texture,
      sprite,
      lastPoint: null,
      startPoint: null,
      snapshot: null,
      // 画布几何变化（尺寸/位置重排）时必须立刻落盘，否则存盘里的尺寸/位置与 PNG 不一致；
      // 原图丢失时也要立刻落盘，把图层指向的文件名修正到新文件
      dirty: geometryChanged || !source,
      savePath: pickPaintSavePath(img.imagePath, layerId),
    }
    if (sprite) bindPaintTexture(sprite, img)
    if (geometryChanged || !source) schedulePaintSave()
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

/** 绘制画布单边上限（WebGL 纹理常见上限 8192，保守取值，避免大纹理上传失败） */
const MAX_PAINT_CANVAS_SIDE = 8192
/** 绘制画布总面积上限（≈ 122MB RGBA8，防止内存暴涨） */
const MAX_PAINT_CANVAS_AREA = 32_000_000
/** 画布自动扩展步长：对齐到 256px，减少频繁重建开销 */
const PAINT_EXPAND_STEP = 256

/**
 * 确保绘制画布覆盖指定的世界坐标矩形。
 * 超出当前画布范围时自动向外扩展（按步长对齐），触达上限时提示并返回 null。
 * 返回 { dx, dy } 表示画布像素坐标需要整体平移的量（用于同步钢笔锚点等）；
 * 返回 null 表示未扩展或被上限拦截。
 * 注意：扩展后画布像素坐标已变化，调用方需重新调用 toCanvasPoint 获取最新坐标。
 */
function ensurePaintCanvasCoversWorld(worldRect: { x: number; y: number; w: number; h: number }): { dx: number; dy: number } | null {
  const s = paintSession
  const img = sessionImage()
  const PIXI_ = PIXI
  if (!s || !img || !sessionMatchesSelection() || !PIXI_) return null

  // 世界矩形 → 画布像素矩形：px = (world.x - pos.x) / scaleX
  const posX = img.position?.[0] ?? 0
  const posY = img.position?.[1] ?? 0
  const scaleX = Math.abs(img.scaleX ?? img.scale ?? 1) || 1
  const scaleY = Math.abs(img.scaleY ?? img.scale ?? 1) || 1
  const px0 = (worldRect.x - posX) / scaleX
  const py0 = (worldRect.y - posY) / scaleY
  const px1 = (worldRect.x + worldRect.w - posX) / scaleX
  const py1 = (worldRect.y + worldRect.h - posY) / scaleY

  const left = Math.min(px0, px1)
  const right = Math.max(px0, px1)
  const top = Math.min(py0, py1)
  const bottom = Math.max(py0, py1)

  const cw = s.canvas.width
  const ch = s.canvas.height
  const expandLeft = left < 0 ? Math.ceil(-left / PAINT_EXPAND_STEP) * PAINT_EXPAND_STEP : 0
  const expandTop = top < 0 ? Math.ceil(-top / PAINT_EXPAND_STEP) * PAINT_EXPAND_STEP : 0
  const expandRight = right > cw ? Math.ceil((right - cw) / PAINT_EXPAND_STEP) * PAINT_EXPAND_STEP : 0
  const expandBottom = bottom > ch ? Math.ceil((bottom - ch) / PAINT_EXPAND_STEP) * PAINT_EXPAND_STEP : 0

  if (expandLeft === 0 && expandTop === 0 && expandRight === 0 && expandBottom === 0) return null

  const newW = cw + expandLeft + expandRight
  const newH = ch + expandTop + expandBottom

  // 上限保护
  if (newW > MAX_PAINT_CANVAS_SIDE || newH > MAX_PAINT_CANVAS_SIDE) {
    mapEditorStore.showHint('画布已达最大尺寸，无法继续向外扩展')
    return null
  }
  if (newW * newH > MAX_PAINT_CANVAS_AREA) {
    mapEditorStore.showHint('画布面积已达上限，无法继续向外扩展')
    return null
  }

  // 新画布：旧内容平移到 (expandLeft, expandTop)，保持世界坐标不变
  const newCanvas = document.createElement('canvas')
  newCanvas.width = newW
  newCanvas.height = newH
  newCanvas.getContext('2d')!.drawImage(s.canvas, expandLeft, expandTop)

  // 替换纹理
  const newTexture = PIXI_.Texture.from(newCanvas)
  newTexture.source.scaleMode = currentScaleMode
  const oldTexture = s.texture
  s.canvas = newCanvas
  s.texture = newTexture
  if (s.sprite) s.sprite.texture = newTexture
  oldTexture.destroy()

  // 更新图层几何：原点向左上扩展时 position 相应减小，向右下扩展时不变
  img.width = newW
  img.height = newH
  if (expandLeft !== 0 || expandTop !== 0) {
    img.position = [posX - expandLeft, posY - expandTop]
  }
  mapStore.markMapDataDirty()
  s.dirty = true
  schedulePaintSave()
  // 返回画布像素坐标需整体平移的量（向左/上扩展时，已有像素坐标需加对应偏移）
  return { dx: expandLeft, dy: expandTop }
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
  // startPoint 存世界坐标，画布可能已扩展，每次重算画布像素坐标
  const start = toCanvasPoint(s.startPoint)
  if (!start) return
  restorePaintSnapshot()
  const end = constrainPoint({ x: px, y: py }, start, shift)
  paintShapeInto(ctx, start, end)
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
  if (!s || !ctx) return
  const tool = mapEditorStore.imageTool
  // 落笔前确保画布覆盖落点范围（画笔半径 / 形状描边半径），超出时自动扩展
  if (tool === 'brush' || tool === 'eraser') {
    const r = (paintStore.brushSize || 1) / 2
    ensurePaintCanvasCoversWorld({ x: world.x - r, y: world.y - r, w: r * 2, h: r * 2 })
  } else if (tool !== 'fill') {
    const lw = tool === 'line'
      ? Math.max(1, paintStore.lineWidth)
      : (paintStore.strokeWidth > 0 ? paintStore.strokeWidth : 1)
    const r = lw / 2
    ensurePaintCanvasCoversWorld({ x: world.x - r, y: world.y - r, w: r * 2, h: r * 2 })
  } else {
    ensurePaintCanvasCoversWorld({ x: world.x - 1, y: world.y - 1, w: 2, h: 2 })
  }
  const p = toCanvasPoint(world)
  if (!p) return
  pushPaintUndo()
  if (tool === 'fill') {
    floodFillAt(p.x, p.y)
    s.dirty = true
    s.texture.source.update()
    schedulePaintSave()
    return
  }
  if (tool === 'brush' || tool === 'eraser') {
    paintBrushAt(p.x, p.y, null)
    // lastPoint 存世界坐标：画布自动扩展后像素坐标会变，世界坐标保持不变
    s.lastPoint = { x: world.x, y: world.y }
  } else {
    s.snapshot = ctx.getImageData(0, 0, s.canvas.width, s.canvas.height)
    // startPoint / lastPoint 存世界坐标，避免拖拽扩展画布后形状起点错位
    s.startPoint = { x: world.x, y: world.y }
    s.lastPoint = { x: world.x, y: world.y }
    // 图形工具拖拽创建中的实时宽高（画布像素）
    paintStore.liveShapeSize = { x: p.x, y: p.y, w: 0, h: 0 }
  }
  s.dirty = true
  s.texture.source.update()
}

function paintMove(world: { x: number; y: number }, shift = false) {
  const s = paintSession
  if (!s) return
  const tool = mapEditorStore.imageTool
  // 移动中持续确保画布覆盖当前点（画笔连续绘制 / 形状拖拽），超出时自动扩展
  if (tool === 'brush' || tool === 'eraser') {
    const r = (paintStore.brushSize || 1) / 2
    ensurePaintCanvasCoversWorld({ x: world.x - r, y: world.y - r, w: r * 2, h: r * 2 })
  } else if (s.startPoint) {
    // 形状拖拽：覆盖起点到当前点的外接矩形（含描边外扩）
    const lw = tool === 'line'
      ? Math.max(1, paintStore.lineWidth)
      : (paintStore.strokeWidth > 0 ? paintStore.strokeWidth : 1)
    const r = lw / 2
    const minX = Math.min(s.startPoint.x, world.x) - r
    const minY = Math.min(s.startPoint.y, world.y) - r
    const maxX = Math.max(s.startPoint.x, world.x) + r
    const maxY = Math.max(s.startPoint.y, world.y) + r
    ensurePaintCanvasCoversWorld({ x: minX, y: minY, w: maxX - minX, h: maxY - minY })
  }
  const p = toCanvasPoint(world)
  if (!p) return
  if (tool === 'brush' || tool === 'eraser') {
    // lastPoint 存的是世界坐标，转回画布像素坐标作为 from（画布可能刚扩展过）
    const from = s.lastPoint ? toCanvasPoint(s.lastPoint) : null
    paintBrushAt(p.x, p.y, from)
    s.lastPoint = { x: world.x, y: world.y }
  } else {
    // startPoint 是世界坐标，拖拽中画布可能扩展，每次都重算画布像素坐标
    const start = s.startPoint ? toCanvasPoint(s.startPoint) : null
    if (start) {
      drawShapePreview(p.x, p.y, shift)
      // 实时宽高：按起止点轴对齐外框（每次赋新对象触发响应式）
      const end = constrainPoint(p, start, shift)
      paintStore.liveShapeSize = {
        x: Math.min(start.x, end.x),
        y: Math.min(start.y, end.y),
        w: Math.abs(end.x - start.x),
        h: Math.abs(end.y - start.y),
      }
    }
    s.lastPoint = { x: world.x, y: world.y }
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
    // startPoint / lastPoint 存世界坐标，落定时统一转画布像素坐标
    const start = toCanvasPoint(s.startPoint)
    const origin = s.snapshot
    const p = world
      ? toCanvasPoint(world)
      : (s.lastPoint ? toCanvasPoint(s.lastPoint) : null)
    restorePaintSnapshot()
    if (!start || !p || !origin) {
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
  paintStore.liveShapeSize = null
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
  // 这张地图已被从素材列表删除：绝不能再落盘，否则会把删掉的地图目录（含 images）重新造出来
  if (!resourceStore.maps.some(m => m.name === session.mapName)) return
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
        // 直接改了 mapData，通知自动保存机制“脏了”
        mapStore.markMapDataDirty()
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
  const snapshot = paintUndo.pop()!
  // 画布可能因自动扩展而变大，旧快照尺寸小于当前画布时先清空再贴回，避免残留
  if (snapshot.width !== s.canvas.width || snapshot.height !== s.canvas.height) {
    ctx.clearRect(0, 0, s.canvas.width, s.canvas.height)
  }
  ctx.putImageData(snapshot, 0, 0)
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
  const snapshot = paintRedo.pop()!
  if (snapshot.width !== s.canvas.width || snapshot.height !== s.canvas.height) {
    ctx.clearRect(0, 0, s.canvas.width, s.canvas.height)
  }
  ctx.putImageData(snapshot, 0, 0)
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

const collision = useShapeLayerEditor({
  getApp: () => app,
  getScale: () => viewport.currentScale.value,
  getOverlayCanvas: () => collisionOverlayRef.value ?? null,
  syncOverlay: () => syncCollisionOverlay(),
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

  // 视口裁剪会让屏幕外的上方图块不可见：快照要覆盖整块画板，先临时全部可见，渲染完恢复
  const upperLayerIds = new Set(upperLayers.map(l => l.id))
  const forcedSprites: { sprite: any; visible: boolean }[] = []
  for (const [key, sprite] of tileSprites) {
    const layerId = Number(key.slice(0, key.indexOf(':')))
    if (!upperLayerIds.has(layerId) || !sprite || sprite.destroyed) continue
    forcedSprites.push({ sprite, visible: sprite.visible })
    sprite.visible = true
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
  } finally {
    // 恢复快照前的可见性（图块是否可见由视口裁剪决定）
    for (const item of forcedSprites) {
      if (!item.sprite.destroyed) item.sprite.visible = item.visible
    }
  }
}

// ─── 覆盖层投影（SVG 变换框 / 塑形锚点 / 光标 / 文字框）───
// 选区主题色统一来自 utils/selectionStyle（与角色绘制页 / 形状图层共用）

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

/**
 * 矢量 UI 层（选框/锚点/钢笔）的画板→屏幕矩阵，走 SVG 内部 transform。
 * 不能沿用 CSS transform：WebKit 会把 CSS 变换过的图层按布局尺寸栅格化再放大，
 * 放大画布后选框描边糊成一圈（叠在图形边缘上就是「选中后边缘发虚」）。SVG 内矩阵
 * 在最终设备分辨率下矢量绘制，缩放后始终锐利。
 */
const vectorUiTransform = computed(() => {
  const m = vectorMatrix.value
  if (!m) return null
  return `matrix(${m.a}, ${m.b}, ${m.c}, ${m.d}, ${m.tx}, ${m.ty})`
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
const vectorBoxStroke = computed(() => SELECTION_STROKE_PX / vectorScreenScale.value)
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
  if (mapStore.activeMode === 'tile') {
    mapStore.undoTile()
    return
  }
  if (vectorActive.value && paintStore.mode === 'vector') vectorEngine.undo()
  else undoPaint()
}

function redoActive() {
  if (mapStore.activeMode === 'tile') {
    mapStore.redoTile()
    return
  }
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

/** 图块层的整层变换（位置 / 缩放 / 旋转），渲染与输入反算共用 */
function layerTileTransform(layerId: number): TileLayerTransform {
  const layer = mapStore.mapData.layers.find(l => l.id === layerId)
  return createLayerTransform(
    mapStore.mapData.width,
    mapStore.mapData.height,
    mapStore.mapData.tileSize,
    layer && layer.type === 'drawing' ? layer : null,
  )
}

function activeTileTransform(): TileLayerTransform {
  const layer = mapStore.activeLayer
  return createLayerTransform(
    mapStore.mapData.width,
    mapStore.mapData.height,
    mapStore.mapData.tileSize,
    layer && layer.type === 'drawing' ? layer : null,
  )
}

/** 指针位置 → 图块格子（先反算整层变换，再落到网格） */
function pointerToTile(e: PointerEvent | DragEvent): { x: number; y: number } | null {
  const world = viewport.screenToWorld(e)
  if (!world) return null
  return worldToTile(activeTileTransform(), world.x, world.y, mapStore.mapData.tileSize)
}

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

  // 形状层：指针事件全部交给形状层编辑器
  if (mapStore.activeMode === 'shape') {
    // 清掉可能残留的平移状态，避免普通拖动带动整块画布
    viewport.endPan()
    const worldPos = viewport.screenToWorld(e)
    if (worldPos) {
      // 捕获指针：拖出画布/移出地图范围后仍能继续拖动，不会卡住
      capturePointer(app?.canvas as HTMLCanvasElement | undefined, e.pointerId)
      collision.pointerDown(worldPos, e.button, e.shiftKey || e.metaKey || e.ctrlKey)
      updateCollisionCursor(worldPos)
    }
    return
  }

  // 点击变换手柄时交给变换逻辑，避免与选区框选冲突
  if (transform.isTransformBusy()) return

  // 图片模式：只做整图的选中 / 移动 / 缩放 / 旋转（像素绘制已迁到绘制页）
  if (mapStore.activeMode === 'image') {
    if (e.button !== 0) return
    const layer = mapStore.activeLayer
    if (layer && layer.type === 'image') transform.handleSelectPointerDown(e, layer)
    // 命中图片会创建变换框，手动补一帧
    requestStageRender()
    return
  }

  // 图块模式：左键绘制
  if (e.button === 0 && !e.altKey && !viewport.isSpacePressed()) {
    const pos = pointerToTile(e)
    if (pos) {
      // 捕获指针：拖到画布外也能收到 pointerup，直线/矩形不会因为快速松开而丢笔
      capturePointer(app?.canvas as HTMLCanvasElement | undefined, e.pointerId)
      painter.handlePaintPointerDown(e, pos)
    }
  }

  // 图块模式：直线/矩形支持右键起笔，拖出要擦除的范围
  if (
    e.button === 2
    && mapStore.activeMode === 'tile'
    && (mapEditorStore.currentTool === 'line' || mapEditorStore.currentTool === 'rect')
  ) {
    const pos = pointerToTile(e)
    if (pos) {
      capturePointer(app?.canvas as HTMLCanvasElement | undefined, e.pointerId)
      painter.handlePaintPointerDown(e, pos)
    }
  }
}

function onPointerMove(e: PointerEvent) {
  // 所有模式都实时上报鼠标世界像素坐标（信息栏显示用）；绘制/框选分支提前 return 也不影响
  const cursorWorld = viewport.screenToWorld(e)
  if (cursorWorld) emit('cursor-move', cursorWorld.x, cursorWorld.y)
  if (mapEditorStore.markerPlacing) markerGhost.value = cursorWorld
  // 形状层：未按键时确保平移状态已结束，不会出现"鼠标一动整块画布跟着走"
  if (mapStore.activeMode === 'shape' && e.buttons === 0) viewport.endPan()
  if (viewport.handlePanMove(e.clientX, e.clientY)) {
    syncVectorGeometry()
    // 叠加层在屏幕坐标绘制，平移后需要重绘
    collision.drawOverlay()
    // ticker 已停：平移只改 stage，必须手动补一帧
    requestStageRender()
    return
  }

  // 形状层：拖动顶点 / 整框移动 / 矩形 / 钢笔预览
  if (mapStore.activeMode === 'shape') {
    const worldPos = viewport.screenToWorld(e)
    if (worldPos) {
      collision.pointerMove(worldPos)
      updateCollisionCursor(worldPos)
    }
    return
  }

  // 整图变换框拖动（拖动图片本体 / 缩放 / 旋转）优先于区块逻辑
  if (transform.handleTransformPointerMove(e)) {
    // ticker 已停：变换只改精灵属性，必须手动补一帧
    requestStageRender()
    return
  }

  // 图片模式只处理整图变换，像素绘制已迁到绘制页
  if (mapStore.activeMode === 'image') return

  let gridPos = pointerToTile(e)
  // 指针捕获后可能拖到画布外：按画布边界裁掉，保持和未捕获时一样不会画出画布
  if (gridPos && (e.buttons & 7) !== 0) {
    const el = app?.canvas as HTMLCanvasElement | undefined
    if (el) {
      const r = el.getBoundingClientRect()
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) {
        gridPos = null
      }
    }
  }
  if (gridPos) {
    cursorGridPos.value = gridPos
    emit('cursor-move', gridPos.x, gridPos.y)
  } else {
    cursorGridPos.value = null
  }

  painter.handlePaintPointerMove(e, gridPos)
}

function onPointerUp(e: PointerEvent) {
  // 形状层：收尾矩形/顶点/整框拖拽
  if (mapStore.activeMode === 'shape') {
    // 空格/中键平移的收尾也必须执行，否则平移状态会残留，之后鼠标移动一直拖动画布
    viewport.endPan()
    releasePointer(app?.canvas as HTMLCanvasElement | undefined, e.pointerId)
    collision.pointerUp()
    return
  }

  // 整图变换框拖动结束优先处理
  if (transform.handleTransformPointerUp()) return

  // 图片模式：只收尾平移 / 指针，像素绘制已迁到绘制页
  if (mapStore.activeMode === 'image') {
    releasePointer(app?.canvas as HTMLCanvasElement | undefined, e.pointerId)
    viewport.endPan()
    viewport.setCursor('default')
    return
  }

  // Move tool: drop tile at new position
  painter.handlePointerUp(cursorGridPos.value)
  releasePointer(app?.canvas as HTMLCanvasElement | undefined, e.pointerId)

  viewport.endPan()
  painter.resetPaintKey()
  viewport.setCursor('default')
}

function onPointerLeave(e: PointerEvent) {
  viewport.endPan()
  painter.resetPaintKey()
  // 图块绘制中离开画布：结束当前笔画，避免后续拖动被并进同一步历史
  if (mapStore.activeMode === 'tile' && e.buttons === 0) {
    // 按住按键时只是短暂移出画布（已捕获指针，pointerup 还会回到画布），不要打断当前笔画
    painter.resetShapeStroke()
    mapStore.endTileStroke()
  }
  cursorGridPos.value = null
  markerGhost.value = null
  // 鼠标离开画布时清空信息栏坐标，避免残留上一次的位置
  emit('cursor-leave')
  painter.hidePreview()
  hideBrushCursor()
  // 松手状态下离开画布才取消未完成的碰撞草稿；拖拽中（按钮仍按下）继续由指针捕获接管
  if (mapStore.activeMode === 'shape' && e.buttons === 0) {
    collision.resetOnLeave()
  }
}

/** 系统取消指针（触摸板手势被接管等）：图块绘制按正常松开收尾，避免笔划悬空 */
function onPointerCancel(e: PointerEvent) {
  if (mapStore.activeMode === 'tile') onPointerUp(e)
}

/**
 * 全局 pointerup 兜底：指针捕获失效或事件没送到画布时（快速松开、触摸板手势），
 * 仍然提交当前直线/矩形笔划。画布已处理过时内部状态已清空，这里不会有副作用。
 */
function onWindowPointerUp(e: PointerEvent) {
  if (mapStore.activeMode !== 'tile') return
  // 画布的 pointerup 没收到时才会留下未提交的笔划；正常松手这里不会重复提交
  if (!painter.hasActiveShapeStroke()) return
  // 终点用最后一次有效移动位置，避免在画布外松手时按屏幕坐标算出越界格子
  painter.handlePointerUp(null)
  releasePointer(app?.canvas as HTMLCanvasElement | undefined, e.pointerId)
  viewport.endPan()
  painter.resetPaintKey()
}

function setupInteraction() {
  if (!app || !app.canvas) return
  const canvas = app.canvas as HTMLCanvasElement

  canvas.addEventListener('wheel', onWheel, { passive: false })
  canvas.addEventListener('pointerdown', onPointerDown)
  canvas.addEventListener('pointermove', onPointerMove)
  canvas.addEventListener('pointerup', onPointerUp)
  canvas.addEventListener('pointercancel', onPointerCancel)
  canvas.addEventListener('pointerleave', onPointerLeave)
  canvas.addEventListener('contextmenu', onContextMenu)
  // Scratch 风格拖拽：监听自定义事件
  canvas.addEventListener('scratch-drop', onScratchDrop as EventListener)
}

function onWheel(e: WheelEvent) {
  viewport.onWheel(e)
  // ticker 已停：缩放只改 stage，必须手动补一帧
  requestStageRender()
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

  const pos = pointerToTile(e as any)
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
  // 撤销/重做快捷键：Ctrl/⌘+Z 撤销，Shift+Ctrl/⌘+Z 或 Ctrl/⌘+Y 重做
  // 地图编辑器用 v-show 常驻，切到代码页时必须让出快捷键
  const mapEditing = editorStore.isGameMode && editorStore.activeEditorMode === 'map'
  if (!typing && mapEditing && (e.ctrlKey || e.metaKey)) {
    const key = e.key.toLowerCase()
    if (key === 'z') {
      e.preventDefault()
      if (e.shiftKey) redoActive()
      else undoActive()
      return
    }
    if (key === 'y') {
      e.preventDefault()
      redoActive()
      return
    }
  }
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
  // 图片模式快捷键：Esc 取消整图选框（像素级快捷键已迁到绘制页）
  if (mapStore.activeMode === 'image') {
    if (e.key === 'Escape' && !typing) {
      e.preventDefault()
      transform.removeTransformBox()
      mapStore.clearImageSelection()
      return
    }
    return
  }
  // Tool shortcuts (only when not typing in an input)
  if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'TEXTAREA') return

  // 形状层快捷键：Esc 取消/退出，Enter 闭合多边形，Delete 删除锚点/形状
  if (mapStore.activeMode === 'shape' && collision.handleKeyDown(e)) return

  switch (e.key.toLowerCase()) {
    case 'b': mapEditorStore.setTool('draw'); break
    case 'e': mapEditorStore.toggleEraseMode(); break
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

/** 轻量重绘：只把当前 stage 出一帧（平移/缩放等场景，不重建图层） */
let stageRenderFrame: number | null = null
function requestStageRender() {
  if (stageRenderFrame !== null || thumbnailCaptureDepth > 0) return
  stageRenderFrame = requestAnimationFrame(() => {
    stageRenderFrame = null
    if (app) app.render()
  })
}

function redraw() {
  viewport.redraw()
  requestStageRender()
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
  requestStageRender()
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

// 图片模式工具同步：仅剩「选择/移动」，统一光标即可
watch(
  () => mapEditorStore.imageTool,
  () => {
    if (mapStore.activeMode !== 'image') return
    syncSelectCursor()
  }
)

watch(
  () => mapEditorStore.currentTool,
  (tool) => {
    // 切换工具时丢弃未完成的直线/矩形拖拽
    painter.resetShapeStroke()
    if (tool !== 'draw' && tool !== 'fill' && tool !== 'line' && tool !== 'rect') {
      painter.hidePreview()
    }
  }
)

// 擦除模式切换：之前的画笔幽灵预览要立即收掉
watch(
  () => mapEditorStore.eraseMode,
  () => painter.hidePreview(),
)

// 图块朝向 / 图章变化：鼠标停在画布上时立即刷新幽灵预览，不用再挪一下才看到朝向变化
watch(
  () => [mapStore.selectedTileFlipH, mapStore.selectedTileFlipV, mapStore.tileBrushStamp],
  () => {
    if (cursorGridPos.value) painter.updatePreview(cursorGridPos.value)
  },
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

// 切到非图片图层时清除图片变换框；切到形状层时清理形状会话并刷新叠加层
watch(
  () => mapStore.activeLayerIndex,
  (idx) => {
    const layer = mapStore.mapData.layers[idx]
    if (!layer || layer.type !== 'image') {
      transform.removeTransformBox()
      mapStore.clearImageSelection()
    }
    if (layer?.type === 'shape') {
      setCollisionCursor(mapEditorStore.shapeTool === 'select' ? 'default' : 'crosshair')
    }
    collision.cancelDraft()
    collision.drawOverlay()
    // 变换框可能被移除，需要刷新一帧
    requestStageRender()
  }
)

// 监听图层可见性变化
watch(
  () => mapStore.mapData.layers.map(l => `${l.id}:${l.visible}`),
  () => {
    ensureLayerOrder()
    // 形状层显隐同步叠加层
    collision.drawOverlay()
    // 矢量模式下上方图层集合随可见性变化，快照需同步重拍
    refreshUpperLayerSnapshot()
    // 图层显隐只改容器 visible，需手动刷新一帧
    requestStageRender()
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

// 平移 / 缩放后重新计算视口裁剪（每帧最多一次，避免整张地图的精灵全部提交给 GPU）
watch(
  () => viewport.viewVersion.value,
  () => { scheduleSpriteVisibility() }
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
    resetFloatingSelection()
    paintClipboard = null
    pasteCount = 0
    mapEditorStore.hasPaintClipboard = false
    collision.cancelDraft()
    // 选中图片时直接显示整图变换框（移动 / 缩放 / 旋转）；像素编辑去绘制页
    if (selImg && mapStore.activeMode === 'image') {
      transform.showTransformBox(selImg)
      syncSelectCursor()
    } else {
      transform.removeTransformBox()
    }
    // 变换框是 Pixi 显示对象，创建/移除后必须刷新一帧
    requestStageRender()
  }
)

// 形状层工具切换：清理未完成草稿并重置光标
watch(
  () => mapEditorStore.shapeTool,
  () => {
    if (mapStore.activeMode !== 'shape') return
    collision.cancelDraft()
    setCollisionCursor(mapEditorStore.shapeTool === 'select' ? 'default' : 'crosshair')
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
        // 本画布是手动渲染（ticker 已停）：构建完显示对象后必须真正出一帧，
        // 否则从绘制页返回等场景会出现"图层已存在但画布不显示"，要手动点一下才刷新
        // 缩略图截图期间跳过（此时图层可见性被临时改写，出屏会闪）
        if (app && thumbnailCaptureDepth === 0) app.render()
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

// 地图图像素材被绘制页覆盖保存后：清掉路径缓存并重建图像图层纹理
function reloadImages() {
  resolvedPathCache.clear()
  for (const layer of mapStore.mapData.layers) {
    if (layer.type === 'image') layerRenderKeys.delete(layer.id)
  }
  mapStore.imageRevision++
  scheduleRender()
}

/** 外部（绘制页保存返回）强制刷新一帧：等图层重建完成后再真正渲染 */
async function renderNow() {
  scheduleRender()
  await whenRenderIdle()
  if (app) app.render()
}

onMounted(() => {
  // Pixi 就绪后强制渲染一次（绘制功能已迁往绘制页，这里只做地编渲染）
  nextTick(async () => {
    await initPixi()
    scheduleRender()
  })
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  // 指针松开兜底：即使 pointerup 没送到画布（快速松开/捕获失效）也能提交图块笔划
  window.addEventListener('pointerup', onWindowPointerUp)
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
  window.removeEventListener('pointerup', onWindowPointerUp)
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
  // GID → 图块集 → 素材（同一素材图片只加载一次）；高位镜像标志在这里一并解出
  const imageCache = new Map<string, HTMLImageElement | null>()
  const resolveTile = (rawGid: number) => {
    const gid = tileBaseGid(rawGid)
    let matched: any = null
    for (let i = tilesets.length - 1; i >= 0; i--) {
      if (gid >= tilesets[i].firstgid) { matched = tilesets[i]; break }
    }
    if (!matched) return null
    const resource = mapStore.mapData.resources.find(r => r.resourceType !== 'image' && r.firstgid === matched.firstgid)
      ?? mapStore.mapData.resources.find(r => r.resourceType !== 'image' && r.path === matched.imagePath)
    if (!resource) return null
    return { resource, tileIndex: gid - matched.firstgid, ...tileFlipFlags(rawGid) }
  }

  const canvas = document.createElement('canvas')
  // 缩略图不需要原图尺寸：按比例缩到安全边长，避免大地图创建超大 canvas（WebKit 有面积上限）
  const FULL_THUMB_MAX = 512
  const thumbScale = Math.min(1, FULL_THUMB_MAX / Math.max(mapW, mapH))
  const drawTs = ts * thumbScale
  canvas.width = Math.max(1, Math.round(mapW * thumbScale))
  canvas.height = Math.max(1, Math.round(mapH * thumbScale))
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
    // 图块自身的镜像：把目标矩形翻到对应方向再画
    const flipH = hit.flipH === true
    const flipV = hit.flipV === true
    ctx.save()
    ctx.translate(x * drawTs + (flipH ? drawTs : 0), y * drawTs + (flipV ? drawTs : 0))
    ctx.scale(flipH ? -1 : 1, flipV ? -1 : 1)
    ctx.drawImage(
      img,
      col * hit.resource.tileWidth, row * hit.resource.tileHeight,
      hit.resource.tileWidth, hit.resource.tileHeight,
      0, 0, drawTs, drawTs,
    )
    ctx.restore()
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
  // 截图期间关闭视口裁剪，并把屏幕外的图块临时置为可见，否则缩略图会缺块
  let savedVisibility: Map<any, boolean> | null = null
  thumbnailCaptureDepth++
  try {
    // 渲染时会先清空图层容器再异步重建图片；必须等这次重建结束，
    // 否则保存时拍到的是全透明的空容器，缩略图就会变空白
    await whenRenderIdle()
    reattachUpperContainers()
    const tileSize = mapStore.mapData.tileSize
    const mapW = mapStore.mapData.width * tileSize
    const mapH = mapStore.mapData.height * tileSize
    if (mapW <= 0 || mapH <= 0) return null

    savedVisibility = new Map()
    for (const sprite of tileSprites.values()) {
      if (!sprite || sprite.destroyed || sprite.__toolHidden) continue
      savedVisibility.set(sprite, sprite.visible)
      sprite.visible = true
    }

    // 大地图直接建 map 尺寸的 RenderTexture 会超过 WebKit 的 canvas 面积上限：
    // 超过安全边长时把整层临时放进一个缩放容器里，按缩放后的尺寸出图
    const MAX_THUMB_SIDE = 2048
    const thumbScale = Math.min(1, MAX_THUMB_SIDE / Math.max(mapW, mapH))
    const rt = PIXI.RenderTexture.create({
      width: Math.max(1, Math.ceil(mapW * thumbScale)),
      height: Math.max(1, Math.ceil(mapH * thumbScale)),
    })
    if (thumbScale === 1) {
      app.renderer.render(tileContainer, { renderTexture: rt })
    } else {
      const parent = tileContainer.parent
      const index = parent ? parent.getChildIndex(tileContainer) : -1
      parent?.removeChild(tileContainer)
      const wrapper = new PIXI.Container()
      wrapper.scale.set(thumbScale)
      wrapper.addChild(tileContainer)
      app.renderer.render(wrapper, { renderTexture: rt })
      wrapper.removeChild(tileContainer)
      wrapper.destroy()
      if (parent && index >= 0) parent.addChildAt(tileContainer, index)
    }
    const canvas = app.renderer.extract.canvas(rt)
    const dataUrl = canvas.toDataURL('image/png')
    rt.destroy(true)
    return dataUrl
  } catch {
    return null
  } finally {
    thumbnailCaptureDepth--
    if (savedVisibility) {
      for (const [sprite, visible] of savedVisibility) {
        if (!sprite.destroyed) sprite.visible = visible
      }
    }
    updateSpriteVisibility()
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

/**
 * 把视口居中到某个世界坐标点。
 * 碰撞叠加层、选区、画笔光标、矢量层都按屏幕坐标绘制，视口一动手动重绘它们，
 * 否则会出现「碰撞体停留在旧位置、点一下画布才对齐」的错位。
 */
function centerOnWorld(x: number, y: number) {
  if (!app) return
  const scale = viewport.currentScale.value
  app.stage.x = app.screen.width / 2 - x * scale
  app.stage.y = app.screen.height / 2 - y * scale
  viewport.redraw()
  collision.drawOverlay()
  drawSelectionOverlay()
  redrawBrushCursor()
  syncVectorGeometry()
  scheduleUpperSnapshotRefresh()
  app.render()
}

/** 把视口居中到整张地图（进入绘制测试时用） */
function centerMap() {
  const w = mapStore.mapData.width * mapStore.mapData.tileSize
  const h = mapStore.mapData.height * mapStore.mapData.tileSize
  centerOnWorld(w / 2, h / 2)
}

/** 当前视口中心的世界坐标：绘制测试退出时用来还原原来的视角 */
function getViewCenter(): { x: number; y: number } | null {
  if (!app) return null
  const scale = viewport.currentScale.value
  return {
    x: (app.screen.width / 2 - app.stage.x) / scale,
    y: (app.screen.height / 2 - app.stage.y) / scale,
  }
}

/** 标记管理里双击 / 定位：把视口居中到该标记 */
function centerMarker(id: string) {
  const marker = mapStore.mapData.markers.find(m => m.id === id)
  if (!marker) return
  centerOnWorld(marker.x, marker.y)
}

/** 形状列表里双击定位：把视口居中到该形状的包围盒中心 */
function centerShape(id: string) {
  const layer = mapStore.activeShapeLayer
  const shape = layer?.shapes.find(s => s.id === id)
  if (!shape || shape.points.length === 0) return
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const [x, y] of shape.points) {
    if (x < minX) minX = x
    if (x > maxX) maxX = x
    if (y < minY) minY = y
    if (y > maxY) maxY = y
  }
  centerOnWorld((minX + maxX) / 2, (minY + maxY) / 2)
}

/** 只渲染未隐藏的标记；临时「显示隐藏标记」时把隐藏项也带上（弱化显示，便于重新选中） */
const visibleMarkers = computed(() =>
  mapStore.mapData.markers.filter(
    m => m.visible !== false || mapEditorStore.showHiddenMarkers,
  ),
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

/** 图钉下方坐标文本：(用户坐标) */
function markerCoordText(p: { x: number; y: number } | null) {
  if (!p) return ''
  return `(${Math.round(toUserX(p.x))},${Math.round(toUserY(p.y))})`
}

/** 绘制画布像素 → 屏幕坐标（相对地图画布容器，与标记图钉同一套换算） */
function paintPointToScreen(p: { x: number; y: number }): { x: number; y: number } | null {
  const s = paintSession
  const img = sessionImage()
  if (!s || !img || !app) return null
  const world = imageLocalToWorld(img, { x: p.x / s.canvas.width, y: p.y / s.canvas.height })
  const scale = viewport.currentScale.value
  return { x: app.stage.x + world.x * scale, y: app.stage.y + world.y * scale }
}

/** 图形工具创建中的实时宽高徽标（跟随外框右下角；贴近画布边缘时翻到内侧） */
const LIVE_BADGE_W = 64 // 估算徽标宽度（边缘翻面判断）
const LIVE_BADGE_H = 22
const liveSizeBadge = computed(() => {
  const r = paintStore.liveShapeSize
  if (!r) return null
  void viewport.viewVersion.value // 缩放/平移后重算
  const p0 = paintPointToScreen({ x: r.x, y: r.y })
  const p1 = paintPointToScreen({ x: r.x + r.w, y: r.y + r.h })
  if (!p0 || !p1) return null
  // 图片翻转/旋转时两角可能互换：取屏幕上的右下方向顶点
  const x = Math.max(p0.x, p1.x)
  const y = Math.max(p0.y, p1.y)
  const host = canvasRef.value
  const maxW = host?.clientWidth ?? Infinity
  const maxH = host?.clientHeight ?? Infinity
  const flipX = x + 10 + LIVE_BADGE_W > maxW
  const flipY = y + 10 + LIVE_BADGE_H > maxH
  return {
    text: `${Math.round(r.w)} × ${Math.round(r.h)}`,
    style: {
      left: `${flipX ? x - 8 : x + 10}px`,
      top: `${flipY ? y - 8 : y + 10}px`,
      transform: `translate(${flipX ? '-100%' : '0'}, ${flipY ? '-100%' : '0'})`,
    },
  }
})

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
  // 锁定后只允许选中，不再跟随鼠标拖动
  if (m.locked) return
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
  centerMarker,
  centerShape,
  centerMap,
  centerOnWorld,
  getViewCenter,
  cursorGridPos,
  renderAllLayers,
  showTransformBox: transform.showTransformBox,
  removeTransformBox: transform.removeTransformBox,
  resetCanvasState,
  reloadImages,
  renderNow,
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
  /** 工具栏尺寸输入：按数值修改选中图形尺寸 */
  resizeShapeSize,
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
    <!-- 矢量 UI 层（框选/变换框/手柄/锚点/钢笔）：屏幕坐标 SVG，位移缩放走 <g> 内部矩阵。
         不能放进上面的 CSS transform 层：WebKit 会按布局尺寸栅格化再放大，放大画布后选框描边发虚 -->
    <div
      v-if="vectorActive && paintStore.mode === 'vector' && vectorUiTransform"
      class="map-vector-ui"
    >
      <svg class="map-vector-ui-svg">
        <g :transform="vectorUiTransform">
        <!-- 框选矩形：与角色绘制页 / 形状图层统一的靛蓝实线 + 10% 填充 -->
        <rect
          v-if="paintStore.selection"
          :x="paintStore.selection.x"
          :y="paintStore.selection.y"
          :width="paintStore.selection.w"
          :height="paintStore.selection.h"
          :fill="VEC_SEL"
          :fill-opacity="SELECTION_FILL_ALPHA"
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
        </g>
      </svg>
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
        v-for="m in visibleMarkers"
        :key="m.id"
        class="map-marker"
        :class="{
          'is-selected': m.id === mapEditorStore.selectedMarkerId,
          'is-hidden': m.visible === false,
        }"
        :style="markerScreenStyle(m)"
        @mousedown="onMarkerMouseDown(m, $event)"
        @dblclick.stop="onMarkerActivate(m)"
        @contextmenu.prevent.stop="mapEditorStore.setSelectedMarkerId(m.id)"
      >
        <div class="map-marker-icon" v-html="markerIconSvg"></div>
        <span
          v-if="m.showName !== false || m.showCoord !== false"
          class="map-marker-label"
        >
          <b v-if="m.showName !== false">{{ m.name }}</b><span v-if="m.showCoord !== false">{{ markerCoordText(m) }}</span>
        </span>
      </div>
    </div>
    <!-- 图形工具拖拽创建中的实时宽高徽标 -->
    <div v-if="liveSizeBadge" class="live-size-badge" :style="liveSizeBadge.style">{{ liveSizeBadge.text }}</div>
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

/* Pixi 主画布：绝对定位贴左上角，避免 inline canvas 被模板空白文本产生的行盒挤下去 */
.map-pixi-canvas {
  position: absolute;
  left: 0;
  top: 0;
  display: block;
}

/* 碰撞叠加层：屏幕坐标 canvas，位于矢量画布（z=10）与矢量投影层（z=11）之上
   实际 left/top/width/height 由 syncCollisionOverlay 按 Pixi 画布实时对齐 */
.map-collision-overlay {
  position: absolute;
  left: 0;
  top: 0;
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

/* 矢量 UI 层：屏幕像素坐标（不受画板 CSS 变换影响，缩放后描边保持锐利） */
.map-vector-ui {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 11;
}

.map-vector-ui-svg {
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

/* 图形创建中的实时宽高徽标（与角色绘制页同款胶囊样式） */
.live-size-badge {
  position: absolute;
  padding: 2px 7px;
  border-radius: 5px;
  background: rgba(18, 20, 28, 0.88);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-size: 11px;
  font-variant-numeric: tabular-nums;
  color: #fff;
  white-space: nowrap;
  pointer-events: none;
  z-index: 32;
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

/* 选中态：只让图标变红（标签始终用深色底，保证任何地图上都看得清字），轻微放大 */
.map-marker.is-selected .map-marker-icon {
  color: var(--mk-red);
  transform: scale(1.07);
  transform-origin: 50% 88%;
}

/* 隐藏的标记：仅在「显示隐藏标记」临时打开时弱化呈现，仍可点选后恢复显示 */
.map-marker.is-hidden {
  opacity: 0.3;
}

.map-marker.is-hidden.is-selected {
  opacity: 0.75;
}

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
