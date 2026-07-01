<script setup lang="ts">
import { ref, watch, onMounted, nextTick } from 'vue'
import { useMapStore } from '../../stores/map'

const mapStore = useMapStore()

const canvasRef = ref<HTMLCanvasElement>()
let ctx: CanvasRenderingContext2D | null = null

// Collision state
const collisionPoints = ref<{ x: number; y: number }[]>([])
const draggingIndex = ref(-1)
const tileSize = 256 // display size

// Get the selected tile's image
async function loadTileImage(): Promise<HTMLImageElement | null> {
  const resource = mapStore.selectedResource
  if (!resource || mapStore.selectedTileIndex < 0) return null

  return new Promise((resolve) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = resource.path
  })
}

function getTileSourceRect(resource: any, tileIndex: number, imgWidth: number): { sx: number; sy: number; sw: number; sh: number } | null {
  if (!resource) return null
  const cols = Math.floor(imgWidth / resource.tileWidth)
  const row = Math.floor(tileIndex / cols)
  const col = tileIndex % cols
  return {
    sx: col * resource.tileWidth,
    sy: row * resource.tileHeight,
    sw: resource.tileWidth,
    sh: resource.tileHeight,
  }
}

async function render() {
  if (!canvasRef.value || !ctx) return
  const canvas = canvasRef.value
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // Draw checkerboard background
  const checkSize = 16
  for (let y = 0; y < tileSize; y += checkSize) {
    for (let x = 0; x < tileSize; x += checkSize) {
      ctx.fillStyle = ((x / checkSize + y / checkSize) % 2 === 0) ? '#2a2a2a' : '#3a3a3a'
      ctx.fillRect(x, y, checkSize, checkSize)
    }
  }

  // Draw tile image
  const resource = mapStore.selectedResource
  const tileIndex = mapStore.selectedTileIndex
  if (resource && tileIndex >= 0) {
    const img = await loadTileImage()
    if (img) {
      const srcRect = getTileSourceRect(resource, tileIndex, img.width)
      if (srcRect) {
        ctx.imageSmoothingEnabled = false
        ctx.drawImage(
          img,
          srcRect.sx, srcRect.sy, srcRect.sw, srcRect.sh,
          0, 0, tileSize, tileSize
        )
      }
    }
  }

  // Draw collision polygon
  if (collisionPoints.value.length >= 2) {
    ctx.beginPath()
    ctx.moveTo(collisionPoints.value[0].x, collisionPoints.value[0].y)
    for (let i = 1; i < collisionPoints.value.length; i++) {
      ctx.lineTo(collisionPoints.value[i].x, collisionPoints.value[i].y)
    }
    ctx.closePath()
    ctx.fillStyle = 'rgba(255, 80, 80, 0.2)'
    ctx.fill()
    ctx.strokeStyle = 'rgba(255, 80, 80, 0.8)'
    ctx.lineWidth = 1
    ctx.stroke()
  }

  // Draw anchor points
  for (let i = 0; i < collisionPoints.value.length; i++) {
    const p = collisionPoints.value[i]
    const size = 6
    ctx.fillStyle = i === 0 ? '#5BFB84' : '#FF5050'
    ctx.fillRect(p.x - size / 2, p.y - size / 2, size, size)
    ctx.strokeStyle = '#fff'
    ctx.lineWidth = 1
    ctx.strokeRect(p.x - size / 2, p.y - size / 2, size, size)
  }

  // Draw grid overlay
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)'
  ctx.lineWidth = 0.5
  const gridStep = tileSize / 8
  for (let i = 1; i < 8; i++) {
    ctx.beginPath()
    ctx.moveTo(i * gridStep, 0)
    ctx.lineTo(i * gridStep, tileSize)
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(0, i * gridStep)
    ctx.lineTo(tileSize, i * gridStep)
    ctx.stroke()
  }
}

function getCanvasPos(e: MouseEvent): { x: number; y: number } {
  if (!canvasRef.value) return { x: 0, y: 0 }
  const rect = canvasRef.value.getBoundingClientRect()
  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top,
  }
}

function findAnchor(pos: { x: number; y: number }): number {
  for (let i = 0; i < collisionPoints.value.length; i++) {
    const p = collisionPoints.value[i]
    if (Math.abs(p.x - pos.x) < 8 && Math.abs(p.y - pos.y) < 8) {
      return i
    }
  }
  return -1
}

function snapToPixel(val: number): number {
  return mapStore.snapToPixel ? Math.round(val) : val
}

function pointToSegmentDistance(p: { x: number; y: number }, a: { x: number; y: number }, b: { x: number; y: number }): number {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const lenSq = dx * dx + dy * dy
  if (lenSq === 0) return Math.hypot(p.x - a.x, p.y - a.y)
  let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / lenSq
  t = Math.max(0, Math.min(1, t))
  const projX = a.x + t * dx
  const projY = a.y + t * dy
  return Math.hypot(p.x - projX, p.y - projY)
}

function onMouseDown(e: MouseEvent) {
  const pos = getCanvasPos(e)

  if (mapStore.collisionTool === 'reset') {
    resetCollision()
    return
  }

  if (mapStore.collisionTool === 'add') {
    // Check if clicking on first anchor to close polygon
    if (collisionPoints.value.length >= 3) {
      const first = collisionPoints.value[0]
      if (Math.abs(first.x - pos.x) < 8 && Math.abs(first.y - pos.y) < 8) {
        // Close polygon (already closed by default, just confirm)
        render()
        saveCollision()
        return
      }
    }

    // Check if clicking on an edge to insert point
    if (collisionPoints.value.length >= 2) {
      let closestEdgeIdx = -1
      let closestDist = Infinity
      for (let i = 0; i < collisionPoints.value.length; i++) {
        const a = collisionPoints.value[i]
        const b = collisionPoints.value[(i + 1) % collisionPoints.value.length]
        const dist = pointToSegmentDistance(pos, a, b)
        if (dist < closestDist && dist < 20) {
          closestDist = dist
          closestEdgeIdx = i + 1
        }
      }
      if (closestEdgeIdx >= 0) {
        collisionPoints.value.splice(closestEdgeIdx, 0, { x: snapToPixel(pos.x), y: snapToPixel(pos.y) })
        render()
        saveCollision()
        return
      }
    }

    // Otherwise add new point at end
    collisionPoints.value.push({ x: snapToPixel(pos.x), y: snapToPixel(pos.y) })
    render()
    saveCollision()
  } else if (mapStore.collisionTool === 'delete') {
    const idx = findAnchor(pos)
    if (idx >= 0) {
      collisionPoints.value.splice(idx, 1)
      render()
      saveCollision()
    }
  } else if (mapStore.collisionTool === 'move') {
    const idx = findAnchor(pos)
    if (idx >= 0) {
      draggingIndex.value = idx
    }
  }
}

function onMouseMove(e: MouseEvent) {
  if (draggingIndex.value >= 0) {
    const pos = getCanvasPos(e)
    collisionPoints.value[draggingIndex.value] = {
      x: snapToPixel(pos.x),
      y: snapToPixel(pos.y),
    }
    render()
  }
}

function onMouseUp() {
  if (draggingIndex.value >= 0) {
    draggingIndex.value = -1
    saveCollision()
  }
}

function saveCollision() {
  const resource = mapStore.selectedResource
  const tileIndex = mapStore.selectedTileIndex
  if (!resource || tileIndex < 0) return

  // 使用全局索引（当前图层偏移 + 本地索引）
  const globalIdx = mapStore.globalResourceOffset + mapStore.selectedResourceIndex
  const tileSet = mapStore.mapData.tileSets[globalIdx]
  if (!tileSet) return

  while (tileSet.tiles.length <= tileIndex) {
    tileSet.tiles.push({ collision: false, tag: '', collisionType: '图像' })
  }
  tileSet.tiles[tileIndex].collision = collisionPoints.value.length > 0
  tileSet.tiles[tileIndex].collisionShape = {
    points: collisionPoints.value.map(p => [p.x / tileSize, p.y / tileSize])
  }
}

function loadCollision() {
  const resource = mapStore.selectedResource
  const tileIndex = mapStore.selectedTileIndex
  if (!resource || tileIndex < 0) {
    collisionPoints.value = []
    return
  }

  const globalIdx = mapStore.globalResourceOffset + mapStore.selectedResourceIndex
  const tileSet = mapStore.mapData.tileSets[globalIdx]
  if (tileSet && tileSet.tiles[tileIndex]) {
    tileSet.tiles[tileIndex].collisionShape = {
      points: collisionPoints.value.map(p => [p.x / tileSize, p.y / tileSize])
    }
  }
}

function resetCollision() {
  collisionPoints.value = [
    { x: 0, y: 0 },
    { x: tileSize, y: 0 },
    { x: tileSize, y: tileSize },
    { x: 0, y: tileSize },
  ]
  saveCollision()
  render()
}

watch(
  () => [mapStore.selectedResourceIndex, mapStore.selectedTileIndex],
  () => {
    loadCollision()
    nextTick(render)
  }
)

onMounted(() => {
  if (canvasRef.value) {
    ctx = canvasRef.value.getContext('2d')
    render()
  }
})
</script>

<template>
  <div class="col-editor">
    <canvas
      ref="canvasRef"
      :width="tileSize"
      :height="tileSize"
      class="col-canvas"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @mouseleave="onMouseUp"
    />
    <div class="col-actions">
      <button class="col-reset-btn" @click="resetCollision">重置碰撞</button>
    </div>
  </div>
</template>

<style scoped>
.col-editor {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
}

.col-canvas {
  width: 256px;
  height: 256px;
  min-width: 256px;
  min-height: 256px;
  background: rgb(30, 30, 30);
  border: 1px solid rgb(55, 59, 68);
  border-radius: 4px;
  cursor: crosshair;
  image-rendering: pixelated;
}

.col-actions {
  display: flex;
  gap: 4px;
}

.col-reset-btn {
  height: 22px;
  padding: 0 8px;
  background: rgb(52, 55, 62);
  border: 1px solid rgb(73, 76, 86);
  border-radius: 4px;
  color: rgb(150, 150, 150);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}

.col-reset-btn:hover {
  background: rgb(62, 65, 72);
  color: white;
}
</style>
