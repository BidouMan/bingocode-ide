<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { useMapStore, type MapResource } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import { useProjectStore } from '../../stores/project'
import { useEditorStore } from '../../stores/editor'
import { isSvgSource, rasterizeSvgImage, SVG_RASTER_SCALE } from '../../utils/svgRasterize'
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
      for (const imgData of layer.images) {
        await renderImageLayer(container, imgData)
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
  collision.drawCollisionOverlay()
}

async function renderImageLayer(container: any, imgData: any) {
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
    transform.noteRenderedImage(imgData, sprite)
  } catch (err) {
    console.error('[MapCanvas] renderImageLayer error:', err)
  }
}

async function placeImage(layer: any, resource: any, x: number, y: number) {
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
  layer.images.push(imgData)
  mapStore.imageRevision++
  // 不要在这里调用 renderAllLayers，让 watcher 处理
  // renderAllLayers() 会导致竞态条件

  // 放置后选中该图像并显示变换框，切换到移动模式
  const index = layer.images.length - 1
  transform.setSelection(layer.id, index, imgData)
  mapStore.selectImage(layer.id, index)
  transform.showTransformBox(imgData)
  mapEditorStore.setTool('select')
}

// --- 交互 composables ---
const viewport = useMapViewport({
  canvasRef,
  getApp: () => app,
  getPIXI: () => PIXI,
  onZoom: () => collision.drawCollisionOverlay(),
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

  // If transform handle or rotation handle was clicked, don't process further
  if (transform.isTransformBusy()) return

  if (e.button === 0 && !e.altKey && !viewport.isSpacePressed()) {
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

function onPointerUp() {
  if (collision.handlePointerUp()) return

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
  const layer = mapStore.activeLayer

  if (!layer || layer.type !== 'image') return
  const resource = mapStore.activeLayerResources[resourceIndex]
  if (!resource) return

  // 拖入的图片左上角自动对齐到坐标原点
  placeImage(layer, resource, 0, 0)
}

function onDragOver(e: DragEvent) {
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
}

function onDrop(e: DragEvent) {
  e.preventDefault()
  e.stopPropagation()

  const layer = mapStore.activeLayer

  const imageData = e.dataTransfer?.getData('application/x-bingo-image')

  if (imageData && layer && layer.type === 'image') {
    try {
      const { resourceIndex } = JSON.parse(imageData)
      const resource = mapStore.activeLayerResources[resourceIndex]
      const worldPos = viewport.screenToWorld(e)
      if (resource && worldPos) {
        placeImage(layer, resource, worldPos.x, worldPos.y)
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

// 切换图层时清除图像变换框（防止绘制图层上残留图像的选择框）
watch(
  () => mapStore.activeLayerIndex,
  () => {
    transform.removeTransformBox()
    mapStore.clearImageSelection()
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
  () => [mapStore.selectedImageLayerId, mapStore.selectedImageIndex],
  () => {
    collision.cancelCollisionDraft()
    collision.clearVertexSelection()
    // 外部设置的选中实例（例如绘制页保存返回）需要同步本地变换框
    const img = mapStore.selectedImage
    if (img && mapEditorStore.imageCollisionTool === 'none' && !transform.isSelectedImage(img)) {
      transform.setSelection(mapStore.selectedImageLayerId, mapStore.selectedImageIndex, img)
      transform.showTransformBox(img)
      transform.cacheSelectedImageSprite()
    }
    collision.drawCollisionOverlay()
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
  const index = mapStore.selectedImageIndex >= 0 ? mapStore.selectedImageIndex : transform.getSelectedImageIndex()
  if (index < 0) return
  const layer = mapStore.mapData.layers.find(l => l.id === layerId)
  if (!layer || layer.type !== 'image') return
  layer.images.splice(index, 1)
  transform.removeTransformBox()
  mapStore.clearImageSelection()
  collision.cancelCollisionDraft()
  collision.drawCollisionOverlay()
  mapStore.imageRevision++
  scheduleRender()
}

defineExpose({ redraw, cursorGridPos, renderAllLayers, showTransformBox: transform.showTransformBox, removeTransformBox: transform.removeTransformBox, resetCanvasState, getThumbnailDataUrl, deleteSelectedImage })
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
