<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useMapStore, type MapResource } from '../../stores/map'

const emit = defineEmits<{
  'tile-painted': [x: number, y: number, tileId: number]
  'tile-erased': [x: number, y: number]
  'cursor-move': [x: number, y: number]
}>()

const cursorGridPos = ref<{ x: number; y: number } | null>(null)

const canvasRef = ref<HTMLDivElement>()
let PIXI: any = null
let app: any = null
let gridGraphics: any = null
let axisX: any = null
let axisY: any = null
let gameWindowRect: any = null
let previewTile: any = null
let isPanning = false
let isSpaceHeld = false
let lastPointer = { x: 0, y: 0 }
let currentScale = 1.6
let lastPaintedKey = ''

// Move tool state
let moveStartPos: { x: number; y: number } | null = null
let moveTileId = 0
let movePreview: any = null

// Image drag state
let isDraggingImage = false
let imageDragStartWorld = { x: 0, y: 0 }
let imageDragStartPos = [0, 0]

const mapStore = useMapStore()

const LOGIC_W = 640
const LOGIC_H = 480

// Tile rendering state
let layerContainers: Map<number, any> = new Map()
let tileSprites: Map<string, any> = new Map() // "layerId:x,y" -> Sprite
let tileTextures: Map<string, any> = new Map() // "resourcePath:tileIndex" -> Texture
let sourceImageCache: Map<string, any> = new Map() // "resourcePath" -> HTMLImageElement
let tileContainer: any = null

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

  tileContainer = new PIXI.Container()
  app.stage.addChild(tileContainer)

  drawGrid()
  drawAxes()
  drawGameWindow()
  setupInteraction()
  applyScale()
  centerView()
  await renderAllLayers()
}

// --- Tile Rendering ---

async function loadImage(src: string): Promise<HTMLImageElement> {
  if (sourceImageCache.has(src)) return sourceImageCache.get(src)
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      sourceImageCache.set(src, img)
      resolve(img)
    }
    img.onerror = reject
    img.src = src
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

    const canvas = document.createElement('canvas')
    canvas.width = resource.tileWidth
    canvas.height = resource.tileHeight
    const ctx = canvas.getContext('2d')!
    ctx.drawImage(
      img,
      col * resource.tileWidth, row * resource.tileHeight,
      resource.tileWidth, resource.tileHeight,
      0, 0,
      resource.tileWidth, resource.tileHeight
    )

    const texture = PIXI.Texture.from(canvas)
    tileTextures.set(key, texture)
    return texture
  } catch {
    return null
  }
}

function decodeTileId(tileId: number): { resourceIndex: number; tileIndex: number } {
  return {
    resourceIndex: Math.floor(tileId / 1000) - 1,
    tileIndex: (tileId % 1000) - 1,
  }
}

function getLayerContainer(layerId: number): any {
  if (layerContainers.has(layerId)) return layerContainers.get(layerId)
  const container = new PIXI.Container()
  container.label = `layer_${layerId}`
  tileContainer.addChild(container)
  layerContainers.set(layerId, container)
  return container
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
  const { resourceIndex, tileIndex } = decodeTileId(tileId)

  // 从所有图层的资源中查找对应的资源
  let globalIdx = 0
  let resource: MapResource | null = null
  for (const layer of mapStore.mapData.layers) {
    for (const res of layer.resources) {
      if (globalIdx === resourceIndex) {
        resource = res
        break
      }
      globalIdx++
    }
    if (resource) break
  }
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
    const container = getLayerContainer(layerId)
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

  // Clear existing
  for (const [, container] of layerContainers) {
    tileContainer.removeChild(container)
    container.destroy({ children: true })
  }
  layerContainers.clear()
  tileSprites.clear()

  const layers = mapStore.mapData.layers
  for (let i = 0; i < layers.length; i++) {
    const layer = layers[i]
    const container = getLayerContainer(layer.id)
    container.zIndex = i
    container.visible = layer.visible

    if (layer.type === 'drawing') {
      for (const [posKey, tileId] of Object.entries(layer.tiles)) {
        const [x, y] = posKey.split(',').map(Number)
        await renderTile(layer.id, x, y, tileId)
      }
    } else if (layer.type === 'image') {
      for (const imgData of layer.images) {
        await renderImageLayer(container, imgData)
      }
    }
  }
  tileContainer.sortChildren()
}

async function renderImageLayer(container: any, imgData: any) {
  if (!imgData?.imagePath) {
    return
  }
  try {
    const img = await loadImage(imgData.imagePath)
    const texture = PIXI.Texture.from(img)
    const sprite = new PIXI.Sprite(texture)

    sprite.x = imgData.position?.[0] ?? 0
    sprite.y = imgData.position?.[1] ?? 0

    const scaleX = (imgData.scaleX ?? imgData.scale ?? 1)
    const scaleY = (imgData.scaleY ?? imgData.scale ?? 1)
    sprite.scale.set(scaleX, scaleY)

    const rotation = (imgData.rotation ?? 0) * Math.PI / 180
    // PixiJS rotation is around the anchor point; we want around center
    // Convert: set anchor to center, rotate, then offset position
    sprite.anchor.set(0.5, 0.5)
    sprite.x += (imgData.width || 64) * scaleX / 2
    sprite.y += (imgData.height || 64) * scaleY / 2
    sprite.rotation = rotation

    sprite.alpha = imgData.opacity ?? 1

    container.addChild(sprite)

    // Cache sprite reference for the currently selected image
    if (selectedImageData && imgData === selectedImageData) {
      selectedImageSprite = sprite
    }
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
  // 不要在这里调用 renderAllLayers，让 watcher 处理
  // renderAllLayers() 会导致竞态条件

  // 放置后选中该图像并显示变换框，切换到移动模式
  selectedImageData = imgData
  selectedImageLayerId = layer.id
  selectedImageIndex = layer.images.length - 1
  showTransformBox(imgData)
  mapStore.setTool('select')
}

async function updateTileAt(layerIndex: number, x: number, y: number) {
  const layer = mapStore.mapData.layers[layerIndex]
  if (!layer) return
  const tileId = layer.tiles[`${x},${y}`] ?? 0
  await renderTile(layer.id, x, y, tileId)
}

// --- Grid / Axes ---

function drawGrid() {
  if (!app || !PIXI) {
    return
  }
  if (gridGraphics) {
    app.stage.removeChild(gridGraphics)
    gridGraphics.destroy()
  }
  gridGraphics = new PIXI.Graphics()

  const { tileSize } = mapStore.mapData
  const extent = 200
  const totalW = extent * 2 * tileSize
  const totalH = extent * 2 * tileSize
  const offsetX = -extent * tileSize
  const offsetY = -extent * tileSize

  for (let x = -extent; x <= extent; x++) {
    gridGraphics.moveTo(x * tileSize, offsetY)
    gridGraphics.lineTo(x * tileSize, offsetY + totalH)
  }
  for (let y = -extent; y <= extent; y++) {
    gridGraphics.moveTo(offsetX, y * tileSize)
    gridGraphics.lineTo(offsetX + totalW, y * tileSize)
  }
  gridGraphics.stroke({ width: 0.5, color: 0x333333 })

  gridGraphics.visible = mapStore.showGrid
  app.stage.addChildAt(gridGraphics, 0)
}

function drawAxes() {
  if (!app || !PIXI) return
  if (axisX) { app.stage.removeChild(axisX); axisX.destroy() }
  if (axisY) { app.stage.removeChild(axisY); axisY.destroy() }

  axisX = new PIXI.Graphics()
  axisX.moveTo(-100000, 0)
  axisX.lineTo(100000, 0)
  axisX.stroke({ width: 1, color: 0xC83232 })
  app.stage.addChild(axisX)

  axisY = new PIXI.Graphics()
  axisY.moveTo(0, -100000)
  axisY.lineTo(0, 100000)
  axisY.stroke({ width: 1, color: 0x32C832 })
  app.stage.addChild(axisY)
}

function drawGameWindow() {
  if (!app || !PIXI) return
  if (gameWindowRect) { app.stage.removeChild(gameWindowRect); gameWindowRect.destroy() }

  gameWindowRect = new PIXI.Graphics()
  gameWindowRect.rect(0, 0, LOGIC_W, LOGIC_H)
  gameWindowRect.stroke({ width: 1, color: 0xB4B4FF, alpha: 0.6, dash: [6, 4] })
  app.stage.addChild(gameWindowRect)
}

function applyScale() {
  if (!app) return
  app.stage.scale.set(currentScale, currentScale)
}

function centerView() {
  if (!app || !canvasRef.value) return
  const { tileSize } = mapStore.mapData
  const mapPixelW = mapStore.mapData.width * tileSize
  const mapPixelH = mapStore.mapData.height * tileSize
  const vpW = canvasRef.value.clientWidth
  const vpH = canvasRef.value.clientHeight
  app.stage.x = (vpW - mapPixelW * currentScale) / 2
  app.stage.y = (vpH - mapPixelH * currentScale) / 2
}

// --- Interaction ---

function onWheel(e: WheelEvent) {
  e.preventDefault()

  // Scroll wheel on selected image: scale it
  if (selectedImageData) {
    const delta = e.deltaY > 0 ? 0.95 : 1.05
    const newScale = Math.max(0.1, Math.min(10, (selectedImageData.scaleX ?? selectedImageData.scale ?? 1) * delta))
    selectedImageData.scaleX = newScale
    selectedImageData.scaleY = newScale
    selectedImageData.scale = newScale
    updateTransformBox()
    renderAllLayers()
    return
  }

  // Default: zoom canvas
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  const mouseX = e.clientX - rect.left
  const mouseY = e.clientY - rect.top
  const worldX = (mouseX - app.stage.x) / currentScale
  const worldY = (mouseY - app.stage.y) / currentScale
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  currentScale = Math.max(0.5, Math.min(4, currentScale * delta))
  app.stage.x = mouseX - worldX * currentScale
  app.stage.y = mouseY - worldY * currentScale
  applyScale()
}

function onPointerDown(e: PointerEvent) {
  if (e.button === 1 || (e.button === 0 && isSpaceHeld) || (e.button === 0 && e.altKey)) {
    isPanning = true
    lastPointer = { x: e.clientX, y: e.clientY }
    ;(app.canvas as HTMLCanvasElement).style.cursor = 'grabbing'
    e.preventDefault()
    return
  }

  // If transform handle or rotation handle was clicked, don't process further
  if (transformDragging || isRotating) return

  if (e.button === 0 && !e.altKey && !isSpaceHeld) {
    const layer = mapStore.activeLayer

    if (mapStore.currentTool === 'select' && layer && layer.type === 'image') {
      const worldPos = screenToWorld(e)
      if (worldPos) {
        const hit = hitTestImage(worldPos.x, worldPos.y)
        if (hit) {
          if (selectedImageData !== hit.imageData) {
            // New image selected — build transform box
            selectedImageData = hit.imageData
            selectedImageLayerId = hit.layerId
            selectedImageIndex = hit.imageIndex
            showTransformBox(hit.imageData)
            cacheSelectedImageSprite()
          }
          imageDragStartWorld = { x: worldPos.x, y: worldPos.y }
          imageDragStartPos = [...hit.imageData.position]
          // Defer drag start so PixiJS handles can set their flags first
          nextTick(() => {
            if (!transformDragging && !isRotating) {
              isDraggingImage = true
              isImageDragging = true
            }
          })
          return
        } else {
          removeTransformBox()
        }
      }
      return
    }

    const pos = screenToGrid(e)
    if (pos) {
      const globalIdx = mapStore.globalResourceOffset + mapStore.selectedResourceIndex
      if (mapStore.currentTool === 'draw' && mapStore.selectedTileIndex >= 0) {
        const tileId = (globalIdx + 1) * 1000 + mapStore.selectedTileIndex
        mapStore.setTile(pos.x, pos.y, tileId)
        lastPaintedKey = `${pos.x},${pos.y}`
        updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
        emit('tile-painted', pos.x, pos.y, tileId)
      } else if (mapStore.currentTool === 'erase') {
        mapStore.setTile(pos.x, pos.y, 0)
        lastPaintedKey = `${pos.x},${pos.y}`
        updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
        emit('tile-erased', pos.x, pos.y)
      } else if (mapStore.currentTool === 'fill' && mapStore.selectedTileIndex >= 0) {
        const tileId = (globalIdx + 1) * 1000 + mapStore.selectedTileIndex
        floodFill(pos.x, pos.y, tileId)
      } else if (mapStore.currentTool === 'move') {
        // Pick up tile for moving
        const layer = mapStore.activeLayer
        if (layer && layer.type === 'drawing') {
          const tileId = layer.tiles[`${pos.x},${pos.y}`] ?? 0
          if (tileId !== 0) {
            moveStartPos = pos
            moveTileId = tileId
            // Show preview
            if (!movePreview) {
              movePreview = new PIXI.Graphics()
              app.stage.addChild(movePreview)
            }
            const tileSize = mapStore.mapData.tileSize
            movePreview.clear()
            movePreview.rect(pos.x * tileSize, pos.y * tileSize, tileSize, tileSize)
            movePreview.stroke({ width: 1, color: 0x528bff, alpha: 0.8 })
            movePreview.fill({ color: 0x528bff, alpha: 0.15 })
            movePreview.visible = true
          }
        }
      }
    }
  }
}

function onPointerMove(e: PointerEvent) {
  if (isPanning) {
    const dx = e.clientX - lastPointer.x
    const dy = e.clientY - lastPointer.y
    app.stage.x += dx
    app.stage.y += dy
    lastPointer = { x: e.clientX, y: e.clientY }
    return
  }

  // Rotation via handle
  if (isRotating && selectedImageData) {
    const pos = selectedImageData.position || [0, 0]
    const w = (selectedImageData.width || 64) * (selectedImageData.scaleX ?? selectedImageData.scale ?? 1)
    const h = (selectedImageData.height || 64) * (selectedImageData.scaleY ?? selectedImageData.scale ?? 1)
    const cx = pos[0] + w / 2
    const cy = pos[1] + h / 2
    const worldPos = screenToWorld(e)
    if (worldPos) {
      const angle = Math.atan2(worldPos.y - cy, worldPos.x - cx)
      selectedImageData.rotation = ((angle - rotationStartAngle) * 180 / Math.PI)
      updateTransformBox()
      updateSelectedImageSprite()
    }
    return
  }

  // Transform handle drag
  if (transformDragging && selectedImageData && transformHandleIndex >= 0) {
    const worldPos = screenToWorld(e)
    if (!worldPos) return
    const idx = transformHandleIndex
    const mx = worldPos.x
    const my = worldPos.y

    // Each handle controls specific edges: [left, top, right, bottom]
    // Uncontrolled edges stay fixed at their initial position
    const handleEdges = [
      [true,  true,  false, false], // 0 top-left
      [false, true,  false, false], // 1 top-center
      [false, true,  true,  false], // 2 top-right
      [false, false, true,  false], // 3 right-center
      [false, false, true,  true ], // 4 bottom-right
      [false, false, false, true ], // 5 bottom-center
      [true,  false, false, true ], // 6 bottom-left
      [true,  false, false, false], // 7 left-center
    ]
    const edges = handleEdges[idx]

    let newLeft   = edges[0] ? mx : transformStartBox.left
    let newTop    = edges[1] ? my : transformStartBox.top
    let newRight  = edges[2] ? mx : transformStartBox.right
    let newBottom = edges[3] ? my : transformStartBox.bottom

    const minPx = 10

    // Corner handles (0,2,4,6): maintain aspect ratio
    const isCorner = idx % 2 === 0
    if (isCorner) {
      const origPW = transformStartBox.right - transformStartBox.left
      const origPH = transformStartBox.bottom - transformStartBox.top
      const ratio = origPW / origPH
      // Anchor is the opposite corner (fixed)
      let rawW: number, rawH: number
      if (idx === 0) { // top-left → anchor is bottom-right
        rawW = transformStartBox.right - mx
        rawH = transformStartBox.bottom - my
      } else if (idx === 2) { // top-right → anchor is bottom-left
        rawW = mx - transformStartBox.left
        rawH = transformStartBox.bottom - my
      } else if (idx === 4) { // bottom-right → anchor is top-left
        rawW = mx - transformStartBox.left
        rawH = my - transformStartBox.top
      } else { // idx === 6, bottom-left → anchor is top-right
        rawW = transformStartBox.right - mx
        rawH = my - transformStartBox.top
      }
      // Constrain to ratio using the dominant axis
      rawW = Math.max(rawW, minPx)
      rawH = Math.max(rawH, minPx)
      if (rawW / rawH > ratio) {
        rawH = rawW / ratio
      } else {
        rawW = rawH * ratio
      }
      // Recompute edges from anchor + constrained size
      if (idx === 0) { newLeft = transformStartBox.right - rawW; newTop = transformStartBox.bottom - rawH }
      else if (idx === 2) { newTop = transformStartBox.bottom - rawH; newRight = transformStartBox.left + rawW }
      else if (idx === 4) { newRight = transformStartBox.left + rawW; newBottom = transformStartBox.top + rawH }
      else { newLeft = transformStartBox.right - rawW; newBottom = transformStartBox.top + rawH }
    }

    let pixelW = Math.abs(newRight - newLeft)
    let pixelH = Math.abs(newBottom - newTop)
    if (pixelW < minPx) pixelW = minPx
    if (pixelH < minPx) pixelH = minPx

    selectedImageData.position = [
      Math.min(newLeft, newRight),
      Math.min(newTop, newBottom),
    ]
    // Update scale to match new pixel size, keeping natural width/height constant
    const origW = selectedImageData.width || 64
    const origH = selectedImageData.height || 64
    selectedImageData.scaleX = pixelW / origW
    selectedImageData.scaleY = pixelH / origH
    selectedImageData.scale = selectedImageData.scaleX
    updateTransformBox()
    updateSelectedImageSprite()
    return
  }

  // Image body drag
  if (isDraggingImage && selectedImageData) {
    const worldPos = screenToWorld(e)
    if (worldPos) {
      const dx = worldPos.x - imageDragStartWorld.x
      const dy = worldPos.y - imageDragStartWorld.y
      selectedImageData.position = [imageDragStartPos[0] + dx, imageDragStartPos[1] + dy]
      updateTransformBox()
      updateSelectedImageSprite()
    }
    return
  }

  const gridPos = screenToGrid(e)
  if (gridPos) {
    cursorGridPos.value = gridPos
    emit('cursor-move', gridPos.x, gridPos.y)
  } else {
    cursorGridPos.value = null
  }

  // Move tool preview
  if (moveStartPos && moveTileId && movePreview) {
    const pos = screenToGrid(e)
    if (pos) {
      const tileSize = mapStore.mapData.tileSize
      movePreview.clear()
      movePreview.rect(pos.x * tileSize, pos.y * tileSize, tileSize, tileSize)
      movePreview.stroke({ width: 1, color: 0x528bff, alpha: 0.8 })
      movePreview.fill({ color: 0x528bff, alpha: 0.15 })
      movePreview.visible = true
    }
  }

  if (mapStore.currentTool === 'draw' || mapStore.currentTool === 'erase' || mapStore.currentTool === 'fill') {
    const pos = screenToGrid(e)
    updatePreview(pos)

    if (pos && e.buttons === 1) {
      const key = `${pos.x},${pos.y}`
      if (key !== lastPaintedKey) {
        const globalIdx = mapStore.globalResourceOffset + mapStore.selectedResourceIndex
        if (mapStore.currentTool === 'draw' && mapStore.selectedTileIndex >= 0) {
          const tileId = (globalIdx + 1) * 1000 + mapStore.selectedTileIndex
          mapStore.setTile(pos.x, pos.y, tileId)
          updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
          emit('tile-painted', pos.x, pos.y, tileId)
        } else if (mapStore.currentTool === 'erase') {
          mapStore.setTile(pos.x, pos.y, 0)
          updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
          emit('tile-erased', pos.x, pos.y)
        }
        lastPaintedKey = key
      }
    }
  }
}

function onPointerUp() {
  if (transformDragging) {
    transformDragging = false
    transformHandleIndex = -1
    isImageDragging = false
    updateSelectedImageSprite()
    renderAllLayers()
    return
  }

  if (isRotating) {
    isRotating = false
    isImageDragging = false
    updateSelectedImageSprite()
    renderAllLayers()
    return
  }

  if (isDraggingImage) {
    isDraggingImage = false
    isImageDragging = false
    updateSelectedImageSprite()
    renderAllLayers()
    return
  }

  // Move tool: drop tile at new position
  if (moveStartPos && moveTileId) {
    const pos = cursorGridPos.value
    if (pos && (pos.x !== moveStartPos.x || pos.y !== moveStartPos.y)) {
      const layer = mapStore.activeLayer
      if (layer && layer.type === 'drawing') {
        // Remove from old position
        mapStore.setTile(moveStartPos.x, moveStartPos.y, 0)
        // Place at new position
        mapStore.setTile(pos.x, pos.y, moveTileId)
        updateTileAt(mapStore.activeLayerIndex, moveStartPos.x, moveStartPos.y)
        updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
      }
    }
    moveStartPos = null
    moveTileId = 0
    if (movePreview) {
      movePreview.visible = false
    }
  }

  isPanning = false
  lastPaintedKey = ''
  if (app?.canvas) (app.canvas as HTMLCanvasElement).style.cursor = 'default'
}

function onPointerLeave() {
  isPanning = false
  lastPaintedKey = ''
  cursorGridPos.value = null
  if (previewTile) {
    previewTile.visible = false
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

function onScratchDrop(e: CustomEvent) {
  const { resourceIndex, clientX, clientY } = e.detail
  const layer = mapStore.activeLayer

  if (!layer || layer.type !== 'image') return
  const resource = layer.resources[resourceIndex]
  if (!resource) return

  // 将屏幕坐标转换为世界坐标
  const rect = (e.target as HTMLElement).getBoundingClientRect()
  const worldX = (clientX - rect.left - app.stage.x) / currentScale
  const worldY = (clientY - rect.top - app.stage.y) / currentScale

  placeImage(layer, resource, worldX, worldY)
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
      const resource = layer.resources[resourceIndex]
      const worldPos = screenToWorld(e)
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

  const pos = screenToGrid(e as any)
  if (!pos) return

  try {
    const { resourceIndex, tileIndex } = JSON.parse(tileData)
    const globalIdx = mapStore.globalResourceOffset + resourceIndex
    const tileId = (globalIdx + 1) * 1000 + tileIndex
    mapStore.setTile(pos.x, pos.y, tileId)
    updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
  } catch {}
}

function onKeyDown(e: KeyboardEvent) {
  if (e.code === 'Space' && !e.repeat) {
    isSpaceHeld = true
    if (app?.canvas) (app.canvas as HTMLCanvasElement).style.cursor = 'grab'
    return
  }
  // Tool shortcuts (only when not typing in an input)
  if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'TEXTAREA') return
  switch (e.key.toLowerCase()) {
    case 'b': mapStore.setTool('draw'); break
    case 'e': mapStore.setTool('erase'); break
    case 'g': mapStore.toggleGrid(); break
    case 'm': mapStore.setTool('move'); break
    case 'v': mapStore.setTool('select'); break
    case 'f': mapStore.setTool('fill'); break
  }
}

function onKeyUp(e: KeyboardEvent) {
  if (e.code === 'Space') {
    isSpaceHeld = false
    if (!isPanning && app?.canvas) (app.canvas as HTMLCanvasElement).style.cursor = 'default'
  }
}

function screenToGrid(e: PointerEvent): { x: number; y: number } | null {
  if (!canvasRef.value || !app) return null
  const rect = canvasRef.value.getBoundingClientRect()
  const sx = (e.clientX - rect.left - app.stage.x) / currentScale
  const sy = (e.clientY - rect.top - app.stage.y) / currentScale
  const tileSize = mapStore.mapData.tileSize
  return {
    x: Math.floor(sx / tileSize),
    y: Math.floor(sy / tileSize),
  }
}

function screenToWorld(e: PointerEvent | DragEvent): { x: number; y: number } | null {
  if (!canvasRef.value || !app) return null
  const rect = canvasRef.value.getBoundingClientRect()
  const clientX = 'clientX' in e ? e.clientX : 0
  const clientY = 'clientY' in e ? e.clientY : 0
  return {
    x: (clientX - rect.left - app.stage.x) / currentScale,
    y: (clientY - rect.top - app.stage.y) / currentScale,
  }
}

function hitTestImage(worldX: number, worldY: number): { layerId: number; imageIndex: number; imageData: any } | null {
  const layer = mapStore.activeLayer
  if (!layer || layer.type !== 'image') return null

  // Check images in reverse order (top-most first)
  for (let i = layer.images.length - 1; i >= 0; i--) {
    const img = layer.images[i]
    const pos = img.position || [0, 0]
    const scaleX = img.scaleX ?? img.scale ?? 1
    const scaleY = img.scaleY ?? img.scale ?? 1
    const w = (img.width || 64) * scaleX
    const h = (img.height || 64) * scaleY

    if (worldX >= pos[0] && worldX <= pos[0] + w &&
        worldY >= pos[1] && worldY <= pos[1] + h) {
      return { layerId: layer.id, imageIndex: i, imageData: img }
    }
  }
  return null
}

function updatePreview(pos: { x: number; y: number } | null) {
  if (!app || !PIXI) return

  if (!pos) {
    if (previewTile) previewTile.visible = false
    return
  }

  const tileSize = mapStore.mapData.tileSize

  if (!previewTile) {
    previewTile = new PIXI.Graphics()
    app.stage.addChild(previewTile)
  }
  previewTile.clear()
  previewTile.rect(pos.x * tileSize, pos.y * tileSize, tileSize, tileSize)
  previewTile.stroke({ width: 1, color: 0x5BFB84, alpha: 0.8 })
  previewTile.fill({ color: 0x5BFB84, alpha: 0.15 })
  previewTile.visible = true
}

function redraw() {
  drawGrid()
  drawAxes()
  drawGameWindow()
}

function onMouseDown(e: MouseEvent) {
  e.stopPropagation()
  if (e.button === 2) e.preventDefault()
}

function onContextMenu(e: MouseEvent) {
  e.preventDefault()
}

// --- Flood Fill ---

function floodFill(startX: number, startY: number, fillTileId: number) {
  const layer = mapStore.activeLayer
  if (!layer || layer.type !== 'drawing') return

  const targetTileId = layer.tiles[`${startX},${startY}`] ?? 0
  if (targetTileId === fillTileId) return

  const { width, height } = mapStore.mapData
  const stack: [number, number][] = [[startX, startY]]
  const visited = new Set<string>()

  while (stack.length > 0) {
    const [x, y] = stack.pop()!
    const key = `${x},${y}`
    if (visited.has(key)) continue
    visited.add(key)

    if (x < 0 || x >= width || y < 0 || y >= height) continue

    const currentId = layer.tiles[key] ?? 0
    if (currentId !== targetTileId) continue

    mapStore.setTile(x, y, fillTileId)

    stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1])
  }

  renderAllLayers()
}

// --- Transform Tool ---

let transformBox: any = null
let transformHandles: any[] = []
let rotationHandle: any = null
let rotationLine: any = null
let selectedImageSprite: any = null
let selectedImageData: any = null
let selectedImageLayerId: number = -1
let selectedImageIndex: number = -1
let transformDragging = false
let transformHandleIndex = -1
let transformStartBox = { left: 0, top: 0, right: 0, bottom: 0 }
let isRotating = false
let rotationStartAngle = 0
let isImageDragging = false

function showTransformBox(imgData: any) {
  removeTransformBox()
  if (!app || !PIXI) return

  selectedImageData = imgData
  const pos = imgData.position || [0, 0]
  const w = (imgData.width || 64) * (imgData.scaleX ?? imgData.scale ?? 1)
  const h = (imgData.height || 64) * (imgData.scaleY ?? imgData.scale ?? 1)
  const cx = pos[0] + w / 2
  const cy = pos[1] + h / 2

  // Bounding box
  transformBox = new PIXI.Graphics()
  transformBox.rect(pos[0], pos[1], w, h)
  transformBox.stroke({ width: 1, color: 0x528bff, alpha: 0.8 })
  transformBox.fill({ color: 0x528bff, alpha: 0.05 })
  app.stage.addChild(transformBox)

  // 8 handles: 4 corners + 4 edge midpoints
  const handlePositions = [
    [pos[0], pos[1]], [pos[0] + w / 2, pos[1]], [pos[0] + w, pos[1]],
    [pos[0] + w, pos[1] + h / 2],
    [pos[0] + w, pos[1] + h], [pos[0] + w / 2, pos[1] + h], [pos[0], pos[1] + h],
    [pos[0], pos[1] + h / 2],
  ]

  transformHandles = handlePositions.map((hp, i) => {
    const handle = new PIXI.Graphics()
    handle.rect(hp[0] - 4, hp[1] - 4, 8, 8)
    handle.fill({ color: 0xffffff })
    handle.stroke({ width: 1, color: 0x528bff })
    handle.cursor = ['nw-resize', 'n-resize', 'ne-resize', 'e-resize', 'se-resize', 's-resize', 'sw-resize', 'w-resize'][i]
    handle.eventMode = 'static'
    handle.on('pointerdown', (e: any) => {
      e.stopPropagation()
      transformDragging = true
      transformHandleIndex = i
      isImageDragging = true
      // Read current data at click time — not closure vars that may be stale
      const p = selectedImageData.position || [0, 0]
      const s = selectedImageData.scaleX ?? selectedImageData.scale ?? 1
      const sy = selectedImageData.scaleY ?? selectedImageData.scale ?? 1
      transformStartBox = {
        left: p[0], top: p[1],
        right: p[0] + (selectedImageData.width || 64) * s,
        bottom: p[1] + (selectedImageData.height || 64) * sy,
      }
    })
    app.stage.addChild(handle)
    return handle
  })

  // Rotation handle: circle above top-center, connected by a line
  const rotX = cx
  const rotY = pos[1] - 30

  rotationLine = new PIXI.Graphics()
  rotationLine.moveTo(cx, pos[1])
  rotationLine.lineTo(rotX, rotY)
  rotationLine.stroke({ width: 1, color: 0x528bff, alpha: 0.8 })
  app.stage.addChild(rotationLine)

  rotationHandle = new PIXI.Graphics()
  rotationHandle.circle(rotX, rotY, 6)
  rotationHandle.fill({ color: 0xffffff })
  rotationHandle.stroke({ width: 1.5, color: 0x528bff })
  rotationHandle.cursor = 'crosshair'
  rotationHandle.eventMode = 'static'
  rotationHandle.on('pointerdown', (e: any) => {
    e.stopPropagation()
    isRotating = true
    isImageDragging = true
    const angle = Math.atan2(e.globalY - cy, e.globalX - cx)
    rotationStartAngle = angle - (selectedImageData.rotation ?? 0) * Math.PI / 180
  })
  app.stage.addChild(rotationHandle)
}

function updateSelectedImageSprite() {
  if (!selectedImageSprite || !selectedImageData) return
  const pos = selectedImageData.position || [0, 0]
  const scaleX = selectedImageData.scaleX ?? selectedImageData.scale ?? 1
  const scaleY = selectedImageData.scaleY ?? selectedImageData.scale ?? 1
  const w = (selectedImageData.width || 64) * scaleX
  const h = (selectedImageData.height || 64) * scaleY
  selectedImageSprite.x = pos[0] + w / 2
  selectedImageSprite.y = pos[1] + h / 2
  selectedImageSprite.rotation = (selectedImageData.rotation ?? 0) * Math.PI / 180
  selectedImageSprite.scale.set(scaleX, scaleY)
  selectedImageSprite.alpha = selectedImageData.opacity ?? 1
  selectedImageSprite.visible = true
}

function cacheSelectedImageSprite() {
  selectedImageSprite = null
  if (selectedImageLayerId < 0) return
  const container = layerContainers.get(selectedImageLayerId)
  if (!container) return
  // Image sprites are added in order as children of the layer container
  const children = container.children
  let imgIdx = 0
  for (const child of children) {
    if (child instanceof PIXI.Sprite) {
      if (imgIdx === selectedImageIndex) {
        selectedImageSprite = child
        return
      }
      imgIdx++
    }
  }
}

function removeTransformBox() {
  if (transformBox) {
    app?.stage.removeChild(transformBox)
    transformBox.destroy()
    transformBox = null
  }
  for (const h of transformHandles) {
    app?.stage.removeChild(h)
    h.destroy()
  }
  transformHandles = []
  if (rotationHandle) {
    app?.stage.removeChild(rotationHandle)
    rotationHandle.destroy()
    rotationHandle = null
  }
  if (rotationLine) {
    app?.stage.removeChild(rotationLine)
    rotationLine.destroy()
    rotationLine = null
  }
  selectedImageData = null
  selectedImageSprite = null
}

function updateTransformBox() {
  if (!selectedImageData || !transformBox) return
  const pos = selectedImageData.position || [0, 0]
  const w = (selectedImageData.width || 64) * (selectedImageData.scaleX ?? selectedImageData.scale ?? 1)
  const h = (selectedImageData.height || 64) * (selectedImageData.scaleY ?? selectedImageData.scale ?? 1)

  transformBox.clear()
  transformBox.rect(pos[0], pos[1], w, h)
  transformBox.stroke({ width: 1, color: 0x528bff, alpha: 0.8 })
  transformBox.fill({ color: 0x528bff, alpha: 0.05 })

  const handlePositions = [
    [pos[0], pos[1]], [pos[0] + w / 2, pos[1]], [pos[0] + w, pos[1]],
    [pos[0] + w, pos[1] + h / 2],
    [pos[0] + w, pos[1] + h], [pos[0] + w / 2, pos[1] + h], [pos[0], pos[1] + h],
    [pos[0], pos[1] + h / 2],
  ]

  transformHandles.forEach((h, i) => {
    h.clear()
    h.rect(handlePositions[i][0] - 4, handlePositions[i][1] - 4, 8, 8)
    h.fill({ color: 0xffffff })
    h.stroke({ width: 1, color: 0x528bff })
  })

  // Update rotation handle position
  const cx = pos[0] + w / 2
  const cy = pos[1] + h / 2
  const rotX = cx
  const rotY = pos[1] - 30

  if (rotationLine) {
    rotationLine.clear()
    rotationLine.moveTo(cx, pos[1])
    rotationLine.lineTo(rotX, rotY)
    rotationLine.stroke({ width: 1, color: 0x528bff, alpha: 0.8 })
  }

  if (rotationHandle) {
    rotationHandle.clear()
    rotationHandle.circle(rotX, rotY, 6)
    rotationHandle.fill({ color: 0xffffff })
    rotationHandle.stroke({ width: 1.5, color: 0x528bff })
  }
}

// --- Keyboard Shortcuts ---

// --- Watchers ---

watch(() => mapStore.showGrid, () => {
  if (gridGraphics) gridGraphics.visible = mapStore.showGrid
})

watch(
  () => [mapStore.mapData.width, mapStore.mapData.height, mapStore.mapData.tileSize],
  () => { redraw() }
)

watch(
  () => mapStore.currentTool,
  (tool) => {
    if (tool !== 'draw' && tool !== 'erase' && tool !== 'fill') {
      if (previewTile) previewTile.visible = false
    }
  }
)

// 监听 mapData 变化，检查图片是否被添加
watch(() => JSON.stringify(mapStore.mapData), (newVal) => {
  const data = JSON.parse(newVal)
  const imageCount = data.layers.reduce((sum: number, l: any) => sum + (l.images?.length || 0), 0)
  if (imageCount > 0) {
  }
})
watch(
  () => mapStore.mapData.layers.map(l => `${l.id}:${l.visible}`),
  () => { ensureLayerOrder() }
)

// Watch for layer add/remove -> re-render all
watch(
  () => mapStore.mapData.layers.length,
  () => { renderAllLayers() }
)

// Watch tile changes on active layer (for external modifications like undo)
let renderQueued = false
watch(
  () => {
    const layer = mapStore.activeLayer
    if (!layer || layer.type !== 'drawing') return ''
    return JSON.stringify(layer.tiles)
  },
  () => {
    if (!renderQueued) {
      renderQueued = true
      nextTick(() => {
        renderAllLayers()
        renderQueued = false
      })
    }
  }
)

// Watch image changes on active layer
let imageRenderQueued = false
watch(
  () => {
    const layer = mapStore.activeLayer
    if (!layer || layer.type !== 'image') return ''
    return JSON.stringify(layer.images)
  },
  () => {
    if (isImageDragging) return
    if (!imageRenderQueued) {
      imageRenderQueued = true
      nextTick(() => {
        renderAllLayers()
        imageRenderQueued = false
      })
    }
  }
)

onMounted(() => {
  nextTick(initPixi)
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
  // 在 document 上注册 drop 事件，确保能接收拖放
  document.addEventListener('dragover', onDragOver)
  document.addEventListener('drop', onDrop)
})

onBeforeUnmount(() => {
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
})

defineExpose({ redraw, cursorGridPos, renderAllLayers, showTransformBox, removeTransformBox })
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
