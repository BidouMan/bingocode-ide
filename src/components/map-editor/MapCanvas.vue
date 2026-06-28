<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useMapStore } from '../../stores/map'

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
let tileContainer: any = null
let previewTile: any = null
let isPanning = false
let isSpaceHeld = false
let lastPointer = { x: 0, y: 0 }
let currentScale = 1.6
let lastPaintedKey = ''

const mapStore = useMapStore()

const LOGIC_W = 640
const LOGIC_H = 480

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
}

function drawGrid() {
  if (!app || !PIXI) return
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

function onWheel(e: WheelEvent) {
  e.preventDefault()
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

  if (e.button === 0 && !e.altKey && !isSpaceHeld) {
    if (mapStore.currentTool === 'draw' || mapStore.currentTool === 'erase') {
      const pos = screenToGrid(e)
      if (pos) {
        if (mapStore.currentTool === 'draw' && mapStore.selectedTileIndex >= 0) {
          const tileId = (mapStore.selectedResourceIndex + 1) * 1000 + mapStore.selectedTileIndex
          mapStore.setTile(pos.x, pos.y, tileId)
          lastPaintedKey = `${pos.x},${pos.y}`
          emit('tile-painted', pos.x, pos.y, tileId)
        } else if (mapStore.currentTool === 'erase') {
          mapStore.setTile(pos.x, pos.y, 0)
          lastPaintedKey = `${pos.x},${pos.y}`
          emit('tile-erased', pos.x, pos.y)
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

  const gridPos = screenToGrid(e)
  if (gridPos) {
    cursorGridPos.value = gridPos
    emit('cursor-move', gridPos.x, gridPos.y)
  } else {
    cursorGridPos.value = null
  }

  if (mapStore.currentTool === 'draw' || mapStore.currentTool === 'erase') {
    const pos = screenToGrid(e)
    updatePreview(pos)

    if (pos && (mapStore.currentTool === 'draw' || mapStore.currentTool === 'erase') && e.buttons === 1) {
      const key = `${pos.x},${pos.y}`
      if (key !== lastPaintedKey) {
        if (mapStore.currentTool === 'draw' && mapStore.selectedTileIndex >= 0) {
          const tileId = (mapStore.selectedResourceIndex + 1) * 1000 + mapStore.selectedTileIndex
          mapStore.setTile(pos.x, pos.y, tileId)
          emit('tile-painted', pos.x, pos.y, tileId)
        } else if (mapStore.currentTool === 'erase') {
          mapStore.setTile(pos.x, pos.y, 0)
          emit('tile-erased', pos.x, pos.y)
        }
        lastPaintedKey = key
      }
    }
  }
}

function onPointerUp() {
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
}

function onKeyDown(e: KeyboardEvent) {
  if (e.code === 'Space' && !e.repeat) {
    isSpaceHeld = true
    if (app?.canvas) (app.canvas as HTMLCanvasElement).style.cursor = 'grab'
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
}

watch(() => mapStore.showGrid, () => {
  if (gridGraphics) gridGraphics.visible = mapStore.showGrid
})

watch(
  () => [mapStore.mapData.width, mapStore.mapData.height, mapStore.mapData.tileSize],
  () => {
    redraw()
  }
)

watch(
  () => mapStore.currentTool,
  (tool) => {
    if (tool !== 'draw' && tool !== 'erase') {
      if (previewTile) previewTile.visible = false
    }
  }
)

onMounted(() => {
  nextTick(initPixi)
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
  if (app?.canvas) {
    const canvas = app.canvas as HTMLCanvasElement
    canvas.removeEventListener('wheel', onWheel)
    canvas.removeEventListener('pointerdown', onPointerDown)
    canvas.removeEventListener('pointermove', onPointerMove)
    canvas.removeEventListener('pointerup', onPointerUp)
    canvas.removeEventListener('pointerleave', onPointerLeave)
  }
  if (app) {
    app.destroy(true)
    app = null
  }
  PIXI = null
})

defineExpose({ redraw, cursorGridPos })
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
