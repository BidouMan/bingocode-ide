<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { useMapStore, type MapResource } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import { useProjectStore } from '../../stores/project'
import { useEditorStore } from '../../stores/editor'
import { isSvgSource, rasterizeSvgImage, SVG_RASTER_SCALE } from '../../utils/svgRasterize'
import { imageWorldToLocal, imageLocalToWorld } from '../../utils/mapImageGeometry'
import { usePaintStore } from '../../stores/paint'
import { rgbaCss, hexToRgba } from '../paint-editor/utils/artboardExport'
import { useMapViewport } from '../../composables/useMapViewport'
import { useImageTransform } from '../../composables/useImageTransform'
import { useImageCollisionEditor } from '../../composables/useImageCollisionEditor'
import { useTilePainter } from '../../composables/useTilePainter'

const emit = defineEmits<{
  'tile-painted': [x: number, y: number, tileId: number]
  'tile-erased': [x: number, y: number]
  'cursor-move': [x: number, y: number]
}>()

const cursorGridPos = ref<{ x: number; y: number } | null>(null)

const canvasRef = ref<HTMLDivElement>()
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
  })
  resizeObserver.observe(canvasRef.value)

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

function applyRenderMode() {
  if (!PIXI) return
  const mode = editorStore.renderMode
  currentScaleMode = mode === 'pixelated' ? 'nearest' : 'linear'
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

  // 移除不再存在的图层容器
  const activeIds = new Set(layers.map(l => l.id))
  for (const [id, container] of layerContainers) {
    if (!activeIds.has(id)) {
      tileContainer.removeChild(container)
      container.destroy({ children: true })
      layerContainers.delete(id)
    }
  }

  // 确保每个图层都有容器，设置 zIndex 和可见性（但不 addChild）
  for (let i = 0; i < layers.length; i++) {
    const layer = layers[i]
    const container = getOrCreateLayerContainer(layer.id)
    container.zIndex = i
    container.visible = layer.visible
  }

  // 先清空所有图层容器的内容
  for (const layer of layers) {
    clearLayerContainer(layer.id)
  }

  // 逐图层重建内容
  for (const layer of layers) {
    if (layer.type === 'drawing') {
      for (const [posKey, tileId] of Object.entries(layer.tiles)) {
        const [x, y] = posKey.split(',').map(Number)
        await renderTile(layer.id, x, y, tileId)
      }
    } else if (layer.type === 'image') {
      const container = getOrCreateLayerContainer(layer.id)
      await renderImageLayer(container, layer.image, layer.id)
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
  collision.drawCollisionOverlay()
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
    }
  }
  // 扁平模型：放置一张图片就新建一个图片图层（在最上层）
  const layerId = mapStore.addImageLayer(resource.name || '图片', imgData)

  // 放置后选中该图片并显示变换框，切换到选取工具
  transform.setSelection(layerId, imgData)
  transform.showTransformBox(imgData)
  mapEditorStore.setTool('select')
}

// 供外部（图层工具栏/内置资源库）直接按路径放置一张图片并建层
async function placeImageFromPath(path: string, x = 0, y = 0) {
  const name = path.split('/').pop()?.split('.')[0] || '图片'
  await placeImage({ name, path }, x, y)
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
  pixelSelection = null
  floatCanvas = null
  floatBaseCanvas = null
  floatOrigin = null
  floatOp = 'none'
  floatStartXf = null
  selectionGraphics?.clear()
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
  const img = mapStore.selectedImage
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
  const img = mapStore.selectedImage
  if (!s || !img) return

  const scale = Math.max(0.1, viewport.currentScale.value)
  const hs = 8 / scale

  if (floatCanvas) {
    const box = floatBoxWorld()
    if (!box) return
    const pts = [box.tl, box.tr, box.br, box.bl].flatMap(p => [p.x, p.y])
    g.poly(pts)
    g.fill({ color: 0x5bfb84, alpha: 0.06 })
    g.poly(pts)
    g.stroke({ width: 1, color: 0x5bfb84 })
    // 旋转锚点连线
    g.moveTo(box.top.x, box.top.y)
    g.lineTo(box.rot.x, box.rot.y)
    g.stroke({ width: 1, color: 0x5bfb84 })
    // 缩放锚点（白底绿边）
    for (const h of box.handles) {
      g.rect(h.x - hs / 2, h.y - hs / 2, hs, hs)
      g.fill({ color: 0xffffff })
      g.stroke({ width: 1, color: 0x5bfb84 })
    }
    // 旋转锚点
    g.circle(box.rot.x, box.rot.y, hs * 0.6)
    g.fill({ color: 0xffffff })
    g.stroke({ width: 1, color: 0x5bfb84 })
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
    g.fill({ color: 0x5bfb84, alpha: 0.08 })
    g.poly(pts)
    g.stroke({ width: 1, color: 0x5bfb84 })
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
  if (!s || !ctx || !r || r.w < 2 || r.h < 2) {
    clearPixelSelection()
    return
  }
  pushPaintUndo()
  floatOrigin = ctx.getImageData(0, 0, s.canvas.width, s.canvas.height)
  const base = makeOffscreenCanvas(s.canvas.width, s.canvas.height)
  const bctx = base.getContext('2d')!
  bctx.drawImage(s.canvas, 0, 0)
  bctx.clearRect(r.x, r.y, r.w, r.h)
  const fc = makeOffscreenCanvas(r.w, r.h)
  fc.getContext('2d')!.drawImage(s.canvas, r.x, r.y, r.w, r.h, 0, 0, r.w, r.h)
  floatBaseCanvas = base
  floatCanvas = fc
  floatXf = { cx: r.x + r.w / 2, cy: r.y + r.h / 2, sx: 1, sy: 1, angle: 0 }
  pixelSelection = null
  floatOp = 'none'
  floatStartXf = null
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
  floatCanvas = null
  floatBaseCanvas = null
  floatOrigin = null
  floatOp = 'none'
  floatStartXf = null
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
  s.texture.source.update()
  selectionGraphics?.clear()
  s.dirty = true
  schedulePaintSave()
}

function clipToSelection(ctx: CanvasRenderingContext2D) {
  if (!pixelSelection || !paintSession) return
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

function pickPaintSavePath(path: string): string {
  const base = (path.split('/').pop() || '图像').replace(/\.[^.]+$/, '')
  return `assets/maps/${mapStore.mapData.name}/images/${base}-draw-${Date.now().toString(36)}.png`
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
  const img = mapStore.selectedImage
  if (!s || !img) return
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

function handleSelectPointerMove(world: { x: number; y: number }, shift: boolean): boolean {
  const s = paintSession
  const img = mapStore.selectedImage
  if (!s || !img) return false

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

  const PIXI_ = PIXI
  if (!PIXI_) return false
  try {
    const source = await loadImage(img.imagePath)
    const srcW = source.naturalWidth || source.width
    const srcH = source.naturalHeight || source.height
    // 背景图层的绘制范围跟随当前地图尺寸（地图改大后可继续在新区域绘制）
    const isBackground = !!img.background
    const mapW = Math.max(1, mapStore.mapData.width * mapStore.mapData.tileSize)
    const mapH = Math.max(1, mapStore.mapData.height * mapStore.mapData.tileSize)
    const canvasW = isBackground ? Math.max(srcW, mapW) : srcW
    const canvasH = isBackground ? Math.max(srcH, mapH) : srcH
    const canvas = document.createElement('canvas')
    canvas.width = canvasW
    canvas.height = canvasH
    if (canvas.width <= 0 || canvas.height <= 0) return false
    canvas.getContext('2d')!.drawImage(source, 0, 0)
    if (isBackground && (canvasW !== srcW || canvasH !== srcH)) {
      img.width = canvasW
      img.height = canvasH
      img.position = [0, 0]
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
    paintSession = {
      layerId,
      mapName: mapStore.mapData.name,
      canvas,
      texture,
      sprite,
      lastPoint: null,
      startPoint: null,
      snapshot: null,
      dirty: false,
      savePath: pickPaintSavePath(img.imagePath),
    }
    if (sprite) bindPaintTexture(sprite, img)
    paintUndo = []
    paintRedo = []
    // 精灵已存在则已直接绑定纹理；不存在时触发一次渲染补建
    if (!sprite) scheduleRender()
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
  const start = s.startPoint
  const tool = mapEditorStore.imageTool
  // 位图形状：实心 / 轮廓 二选一（直线始终是描边）
  const fillOn = tool !== 'line' && paintStore.shapeStyle === 'fill'
  const strokeOn = tool === 'line' || paintStore.shapeStyle === 'outline'
  ctx.save()
  clipToSelection(ctx)
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
}

function toCanvasPoint(world: { x: number; y: number }): { x: number; y: number } | null {
  const s = paintSession
  const img = mapStore.selectedImage
  if (!s || !img) return null
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

function paintEnd(world?: { x: number; y: number }, shift = false) {
  const s = paintSession
  if (!s) return
  if (s.startPoint) {
    const start = s.startPoint
    const p = world ? toCanvasPoint(world) : s.lastPoint
    restorePaintSnapshot()
    if (!p) {
      paintUndo.pop()
    } else {
      const end = constrainPoint(p, start, shift)
      const isClick = Math.abs(end.x - start.x) < 0.5 && Math.abs(end.y - start.y) < 0.5
      if (isClick) {
        // 零尺寸空点击：丢弃本次撤销记录，不产生可见变更
        paintUndo.pop()
      } else {
        drawShapePreview(p.x, p.y, shift)
        s.dirty = true
        s.texture.source.update()
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
      if (layer && layer.type === 'image') layer.image.imagePath = session.savePath
    }
    resolvedPathCache.delete(session.savePath)
    if (finalize) mapStore.imageRevision++
  } catch (e) {
    session.dirty = true
    console.error('[MapCanvas] 保存绘制结果失败:', e)
  }
}

async function commitPaintSession(finalize = true) {
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
  paintUndo = []
  paintRedo = []
  resetFloatingSelection()
}

function undoPaint() {
  const s = paintSession
  const ctx = paintCtx()
  if (!s || !ctx || paintUndo.length === 0) return
  resetFloatingSelection()
  paintRedo.push(ctx.getImageData(0, 0, s.canvas.width, s.canvas.height))
  ctx.putImageData(paintUndo.pop()!, 0, 0)
  s.texture.source.update()
  s.dirty = true
  schedulePaintSave()
}

function redoPaint() {
  const s = paintSession
  const ctx = paintCtx()
  if (!s || !ctx || paintRedo.length === 0) return
  resetFloatingSelection()
  paintUndo.push(ctx.getImageData(0, 0, s.canvas.width, s.canvas.height))
  ctx.putImageData(paintRedo.pop()!, 0, 0)
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
    collision.drawCollisionOverlay()
    // 选区手柄按屏幕尺寸恒定，缩放后重绘
    drawSelectionOverlay()
  },
})

const transform = useImageTransform({
  getApp: () => app,
  getPIXI: () => PIXI,
  getLayerContainers: () => layerContainers,
  screenToWorld: viewport.screenToWorld,
  onCollisionRedraw: () => collision.drawCollisionOverlay(),
  onRenderRequest: () => scheduleRender(),
})

const collision = useImageCollisionEditor({
  getApp: () => app,
  getPIXI: () => PIXI,
  getScale: () => viewport.currentScale.value,
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

// --- Interaction ---

function onPointerDown(e: PointerEvent) {
  if (e.button === 1 || (e.button === 0 && viewport.isSpacePressed()) || (e.button === 0 && e.altKey)) {
    viewport.startPan(e.clientX, e.clientY)
    viewport.setCursor('grabbing')
    e.preventDefault()
    return
  }

  // 碰撞编辑模式下，指针事件全部交给碰撞工具，避免拖动/缩放图像
  if (mapStore.activeLayer?.type === 'image' && mapEditorStore.imageCollisionTool !== 'none' && mapStore.selectedImage) {
    const worldPos = viewport.screenToWorld(e)
    if (worldPos) collision.handleCollisionPointerDown(mapStore.selectedImage, worldPos, e.button)
    return
  }

  // 图片模式的选择工具：框选像素 → 浮动选区（整层选择走左侧图层列表）
  if (mapStore.activeMode === 'image' && mapEditorStore.imageTool === 'select' && mapStore.selectedImage) {
    if (e.button !== 0) return
    const worldPos = viewport.screenToWorld(e)
    if (worldPos) {
      if (paintSession) {
        handleSelectPointerDown(worldPos)
      } else {
        void startPaintSession().then(ok => {
          if (ok) handleSelectPointerDown(worldPos)
        })
      }
    }
    return
  }

  // If transform handle or rotation handle was clicked, don't process further
  if (transform.isTransformBusy()) return

  if (e.button === 0 && !e.altKey && !viewport.isSpacePressed()) {
    // 图片模式：直接在画布上绘制
    if (isImagePaintTool()) {
      const worldPos = viewport.screenToWorld(e)
      if (worldPos) {
        if (paintSession) {
          paintBegin(worldPos)
        } else {
          void startPaintSession().then(ok => {
            if (ok) paintBegin(worldPos)
          })
        }
        return
      }
    }

    const layer = mapStore.activeLayer

    if (transform.handleSelectPointerDown(e, layer)) return

    const pos = viewport.screenToGrid(e)
    if (pos) painter.handlePaintPointerDown(e, pos)
  }
}

function onPointerMove(e: PointerEvent) {
  if (viewport.handlePanMove(e.clientX, e.clientY)) return

  // 碰撞编辑：拖动顶点 / 拉矩形 / 钢笔预览
  if (mapEditorStore.imageCollisionTool !== 'none' && mapStore.selectedImage) {
    const worldPos = viewport.screenToWorld(e)
    if (worldPos) collision.handleCollisionPointerMove(mapStore.selectedImage, worldPos)
    return
  }

  // 图片模式选取工具：更新框选矩形 / 拖动浮动选区（移动、缩放、旋转）
  if (mapStore.activeMode === 'image' && mapEditorStore.imageTool === 'select' && mapStore.selectedImage) {
    if (floatOp !== 'none') {
      const worldPos = viewport.screenToWorld(e)
      if (worldPos) handleSelectPointerMove(worldPos, e.shiftKey)
    }
    return
  }

  if (isImagePaintTool()) {
    if (e.buttons === 1 && paintSession) {
      const worldPos = viewport.screenToWorld(e)
      if (worldPos) paintMove(worldPos, e.shiftKey)
    }
    return
  }

  if (transform.handleTransformPointerMove(e)) return

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
  // 图片模式选取工具：结束框选 / 结束移动缩放旋转
  if (mapStore.activeMode === 'image' && mapEditorStore.imageTool === 'select' && mapStore.selectedImage) {
    if (e.button === 0) handleSelectPointerUp()
    viewport.endPan()
    return
  }

  if (collision.handlePointerUp()) return

  if (isImagePaintTool() && paintSession) {
    paintEnd(viewport.screenToWorld(e) ?? undefined, e.shiftKey)
    viewport.endPan()
    return
  }

  if (transform.handleTransformPointerUp()) return

  // Move tool: drop tile at new position
  painter.handlePointerUp(cursorGridPos.value)

  viewport.endPan()
  painter.resetPaintKey()
  viewport.setCursor('default')
}

function onPointerLeave() {
  viewport.endPan()
  painter.resetPaintKey()
  cursorGridPos.value = null
  painter.hidePreview()
  // 绘制中离开画布：结束当前笔画
  if (isImagePaintTool() && paintSession) paintEnd()
  // 框选中离开画布：按当前尺寸收口，避免选框悬空
  if (mapStore.activeMode === 'image' && mapEditorStore.imageTool === 'select' && floatOp === 'create') {
    handleSelectPointerUp()
  }
  // 离开画布时取消未完成的碰撞草稿，避免残留预览
  if (mapEditorStore.imageCollisionTool !== 'none') {
    collision.resetDraftOnLeave()
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
  if (e.code === 'Space' && !e.repeat) {
    viewport.onSpaceDown()
    return
  }
  // 图片模式选取工具：Esc 取消浮动选区，Delete 删除选区内容
  if (mapStore.activeMode === 'image' && mapEditorStore.imageTool === 'select') {
    if (e.key === 'Escape' && floatCanvas) {
      e.preventDefault()
      cancelFloatingSelection()
      return
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && floatCanvas) {
      e.preventDefault()
      deleteFloatingPixels()
      return
    }
  }
  // 绘制模式下不响应地图快捷键（避免误删图层/切工具）
  if (isImagePaintTool()) return
  // Tool shortcuts (only when not typing in an input)
  if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'TEXTAREA') return

  // 碰撞编辑快捷键：Esc 取消/退出，Enter 闭合多边形，Delete 删除顶点
  if (collision.handleKeyDown(e)) return

  // Delete/Backspace 删除选中图像（图像图层时）
  if ((e.key === 'Delete' || e.key === 'Backspace') && mapStore.activeLayer?.type === 'image') {
    e.preventDefault()
    deleteSelectedImage()
    return
  }

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

// 监听渲染模式变化
watch(
  () => editorStore.renderMode,
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
      void commitPaintSession(false).then(() => startPaintSession())
    }
  }
)

watch(
  () => mapEditorStore.imageTool,
  (tool) => {
    if (mapStore.activeMode !== 'image') return
    if (tool === 'select') {
      viewport.setCursor('default')
      // 选取工具需要绘制会话才能读写图片像素
      void startPaintSession()
    } else {
      // 切换绘制工具前先落定浮动选区
      bakeFloatingSelection()
      clearPixelSelection()
      transform.removeTransformBox()
      viewport.setCursor('crosshair')
      void startPaintSession()
    }
  }
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
    })
  }
)

// 切到图块图层时清除图片变换框；切到图片图层由选中逻辑负责建立变换框
watch(
  () => mapStore.activeLayerIndex,
  (idx) => {
    const layer = mapStore.mapData.layers[idx]
    if (!layer || layer.type !== 'image') {
      transform.removeTransformBox()
      mapStore.clearImageSelection()
    }
  }
)

// 监听图层可见性变化
watch(
  () => mapStore.mapData.layers.map(l => `${l.id}:${l.visible}`),
  () => { ensureLayerOrder() }
)

// Watch for layer add/remove -> re-render all
watch(
  () => mapStore.mapData.layers.length,
  () => { scheduleRender() }
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

// 选中实例变化 → 同步本地变换框 + 重绘叠加层
watch(
  () => mapStore.selectedImageLayerId,
  () => {
    collision.cancelCollisionDraft()
    collision.clearVertexSelection()
    resetFloatingSelection()
    // 外部设置的选中实例（例如绘制页保存返回）需要同步本地变换框
    const img = mapStore.selectedImage
    if (img && mapEditorStore.imageCollisionTool === 'none' && mapEditorStore.imageTool === 'select' && !transform.isSelectedImage(img)) {
      transform.setSelection(mapStore.selectedImageLayerId, img)
      transform.showTransformBox(img)
      transform.cacheSelectedImageSprite()
    }
    collision.drawCollisionOverlay()
    // 切换图片图层：先落盘旧图层，再为新图层建会话
    if (paintSession && paintSession.layerId !== mapStore.selectedImageLayerId) {
      void commitPaintSession(false).then(() => startPaintSession())
    } else if (mapStore.activeMode === 'image' && !paintSession && mapStore.selectedImage) {
      // 图片模式下选中图层即预建会话，保证首次框选/绘制立即可用
      void startPaintSession()
    }
  }
)

// 进入碰撞编辑时隐藏变换框（避免手柄抢事件），退出时恢复
watch(
  () => mapEditorStore.imageCollisionTool,
  (tool, prev) => {
    collision.cancelCollisionDraft()
    collision.clearVertexSelection()
    if (tool !== 'none') {
      transform.removeTransformBox()
      viewport.setCursor('crosshair')
    } else if (prev !== 'none') {
      transform.restoreSelectedImageUI()
      viewport.setCursor('default')
    }
    collision.drawCollisionOverlay()
  }
)

// 统一的渲染调度：合并多次变更，用锁防止并发渲染
function scheduleRender() {
  pendingRender = true
  if (!renderQueued) {
    renderQueued = true
    nextTick(async () => {
      renderQueued = false
      while (pendingRender) {
        pendingRender = false
        // app 未就绪时轮询等待（initPixi 是异步的）
        while (!app) {
          await new Promise(r => requestAnimationFrame(r))
        }
        await renderAllLayers()
      }
    })
  }
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
          renderAllLayers()
        } else {
          requestAnimationFrame(checkReady)
        }
      }
      requestAnimationFrame(checkReady)
    }
  }
)

// 切换地图时清理所有选中状态、变换框、拖拽状态
function resetCanvasState() {
  void commitPaintSession()
  resetFloatingSelection()
  transform.resetTransformState()
  mapStore.clearImageSelection()
  collision.cancelCollisionDraft()
  painter.resetMoveState()
}

onMounted(() => {
  nextTick(initPixi)
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  // 在 document 上注册 drop 事件，确保能接收拖放
  document.addEventListener('dragover', onDragOver)
  document.addEventListener('drop', onDrop)
})

onBeforeUnmount(() => {
  void commitPaintSession()
  resizeObserver?.disconnect()
  resizeObserver = null
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
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

function getThumbnailDataUrl(): string | null {
  if (!app || !PIXI || !app.renderer) return null
  try {
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
  }
}

function deleteSelectedImage() {
  // 碰撞编辑时变换框已被移除，优先用 store 里的选中状态
  const layerId = mapStore.selectedImageLayerId >= 0 ? mapStore.selectedImageLayerId : transform.getSelectedImageLayerId()
  if (layerId < 0) return
  const index = mapStore.mapData.layers.findIndex(l => l.id === layerId)
  if (index < 0) return
  transform.removeTransformBox()
  collision.cancelCollisionDraft()
  mapStore.removeLayer(index)
  collision.drawCollisionOverlay()
  scheduleRender()
}

defineExpose({ redraw, cursorGridPos, renderAllLayers, showTransformBox: transform.showTransformBox, removeTransformBox: transform.removeTransformBox, resetCanvasState, getThumbnailDataUrl, deleteSelectedImage, placeImageFromPath, undoPaint, redoPaint })
</script>

<template>
  <div
    ref="canvasRef"
    class="map-canvas"
    @mousedown="onMouseDown"
  />
</template>

<style scoped>
.map-canvas {
  width: 100%;
  height: 100%;
  background: rgb(30, 30, 30);
  overflow: hidden;
  outline: none;
}
</style>
