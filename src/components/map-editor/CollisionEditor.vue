<script setup lang="ts">
import { ref, watch, computed, onMounted, nextTick } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { useMapStore, type MapResource } from '../../stores/map'
import { useProjectStore } from '../../stores/project'
import { useEditorStore } from '../../stores/editor'

const mapStore = useMapStore()
const projectStore = useProjectStore()
const editorStore = useEditorStore()

const imageRenderingStyle = computed(() => {
  return editorStore.renderMode === 'pixelated' ? 'pixelated' : 'auto'
})

const resolvedPathCache = new Map<string, string>()
async function resolveImagePath(path: string): Promise<string> {
  const cached = resolvedPathCache.get(path)
  if (cached) return cached
  let url: string
  if (path.startsWith('/maps/')) {
    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')
      url = await invoke<string>('read_image_as_data_url', { path: `${engineDir}${path}` })
    } catch { url = '' }
  } else if (path.startsWith('assets/')) {
    url = convertFileSrc(`${projectStore.root}/${path}`)
  } else {
    url = convertFileSrc(path)
  }
  resolvedPathCache.set(path, url)
  return url
}

const canvasRef = ref<HTMLCanvasElement>()
let ctx: CanvasRenderingContext2D | null = null
const collisionPoints = ref<{ x: number; y: number }[]>([])
const draggingIndex = ref(-1)
const tileSize = 256
const contentMargin = 0.1
const contentSize = tileSize * (1 - contentMargin * 2)
const contentOffset = tileSize * contentMargin

let cachedImage: HTMLImageElement | null = null
let cachedImagePath = ''

async function loadTileImage(): Promise<HTMLImageElement | null> {
  const resource = mapStore.selectedResource
  if (!resource) return null
  const isImageLayer = mapStore.activeLayer?.type === 'image'
  if (isImageLayer && mapStore.selectedTileIndex < 0) {
    const url = await resolveImagePath(resource.path)
    if (!url) return null
    return new Promise((resolve) => {
      const img = new Image()
      img.crossOrigin = 'anonymous'
      img.onload = () => resolve(img)
      img.onerror = () => resolve(null)
      img.src = url
    })
  }
  if (mapStore.selectedTileIndex < 0) return null
  const url = await resolveImagePath(resource.path)
  if (!url) return null
  return new Promise((resolve) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = url
  })
}

function getTileSourceRect(resource: any, tileIndex: number, imgWidth: number) {
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

async function preloadImage() {
  const img = await loadTileImage()
  const resource = mapStore.selectedResource
  const path = resource?.path || ''
  if (img && path !== cachedImagePath) {
    cachedImage = img
    cachedImagePath = path
  } else if (!img) {
    cachedImage = null
    cachedImagePath = ''
  }
}

function render() {
  if (!canvasRef.value || !ctx) return
  const canvas = canvasRef.value
  ctx.clearRect(0, 0, canvas.width, canvas.height)

  // Checkerboard background
  const checkSize = 16
  for (let y = 0; y < tileSize; y += checkSize) {
    for (let x = 0; x < tileSize; x += checkSize) {
      ctx.fillStyle = ((x / checkSize + y / checkSize) % 2 === 0) ? '#2a2a2a' : '#3a3a3a'
      ctx.fillRect(x, y, checkSize, checkSize)
    }
  }

  // Draw tile/image
  const resource = mapStore.selectedResource
  const tileIndex = mapStore.selectedTileIndex
  const isImageLayer = mapStore.activeLayer?.type === 'image'
  if (resource && cachedImage) {
    ctx.imageSmoothingEnabled = false
    if (isImageLayer && tileIndex < 0) {
      const scale = Math.min(contentSize / cachedImage.width, contentSize / cachedImage.height)
      const w = cachedImage.width * scale
      const h = cachedImage.height * scale
      ctx.drawImage(cachedImage, contentOffset + (contentSize - w) / 2, contentOffset + (contentSize - h) / 2, w, h)
    } else if (tileIndex >= 0) {
      const srcRect = getTileSourceRect(resource, tileIndex, cachedImage.width)
      if (srcRect) {
        const scale = Math.min(contentSize / srcRect.sw, contentSize / srcRect.sh)
        const dw = srcRect.sw * scale
        const dh = srcRect.sh * scale
        ctx.drawImage(cachedImage, srcRect.sx, srcRect.sy, srcRect.sw, srcRect.sh,
          contentOffset + (contentSize - dw) / 2, contentOffset + (contentSize - dh) / 2, dw, dh)
      }
    }
  }

  // Collision polygon — 仅在碰撞启用时绘制
  if (currentCollisionEnabled.value && collisionPoints.value.length >= 2) {
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

  // Anchor points — 仅在碰撞启用时绘制
  if (currentCollisionEnabled.value) {
    for (let i = 0; i < collisionPoints.value.length; i++) {
      const p = collisionPoints.value[i]
      const size = 6
      ctx.fillStyle = i === 0 ? '#5BFB84' : '#FF5050'
      ctx.fillRect(p.x - size / 2, p.y - size / 2, size, size)
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 1
      ctx.strokeRect(p.x - size / 2, p.y - size / 2, size, size)
    }
  }

  // Grid overlay
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)'
  ctx.lineWidth = 0.5
  const gridStep = contentSize / 8
  for (let i = 1; i < 8; i++) {
    ctx.beginPath()
    ctx.moveTo(contentOffset + i * gridStep, contentOffset)
    ctx.lineTo(contentOffset + i * gridStep, contentOffset + contentSize)
    ctx.stroke()
    ctx.beginPath()
    ctx.moveTo(contentOffset, contentOffset + i * gridStep)
    ctx.lineTo(contentOffset + contentSize, contentOffset + i * gridStep)
    ctx.stroke()
  }
}

function getImageRenderRect(): { x: number; y: number; w: number; h: number } | null {
  if (!cachedImage) return null
  const scale = Math.min(contentSize / cachedImage.width, contentSize / cachedImage.height)
  const w = cachedImage.width * scale
  const h = cachedImage.height * scale
  return { x: contentOffset + (contentSize - w) / 2, y: contentOffset + (contentSize - h) / 2, w, h }
}

function defaultCollisionFromRect(rect: { x: number; y: number; w: number; h: number }) {
  return [
    { x: rect.x, y: rect.y },
    { x: rect.x + rect.w, y: rect.y },
    { x: rect.x + rect.w, y: rect.y + rect.h },
    { x: rect.x, y: rect.y + rect.h },
  ]
}

function saveCollision(target?: MapResource | null) {
  const resource = target ?? mapStore.selectedResource
  if (!resource) return
  const isImageLayer = mapStore.activeLayer?.type === 'image'

  if (isImageLayer) {
    resource.collisionShape = {
      points: collisionPoints.value.map(p => [p.x / tileSize, p.y / tileSize])
    }
    resource.collisionEnabled = collisionPoints.value.length > 0
  } else {
    const tileIndex = mapStore.selectedTileIndex
    if (tileIndex < 0) return
    const globalIdx = mapStore.globalResourceOffset + mapStore.selectedResourceIndex
    const tileSet = mapStore.mapData.tileSets[globalIdx]
    if (!tileSet) return
    while (tileSet.tiles.length <= tileIndex) {
      tileSet.tiles.push({ collision: false, tag: '', collisionType: '图像' })
    }
    tileSet.tiles[tileIndex].collision = collisionPoints.value.length > 0
    tileSet.tiles[tileIndex].collisionShape = {
      points: collisionPoints.value.map(p => [
        (p.x - contentOffset) / contentSize,
        (p.y - contentOffset) / contentSize,
      ])
    }
  }
}

function loadCollision() {
  const resource = mapStore.selectedResource
  if (!resource) { collisionPoints.value = []; return }
  if (resource.collisionType === '图像') { collisionPoints.value = []; return }

  const isImageLayer = mapStore.activeLayer?.type === 'image'
  if (isImageLayer) {
    if (resource.collisionShape?.points?.length) {
      collisionPoints.value = resource.collisionShape.points.map(
        (p: number[]) => ({ x: p[0] * tileSize, y: p[1] * tileSize })
      )
    } else {
      const rect = getImageRenderRect()
      collisionPoints.value = rect ? defaultCollisionFromRect(rect) : [
        { x: contentOffset, y: contentOffset },
        { x: contentOffset + contentSize, y: contentOffset },
        { x: contentOffset + contentSize, y: contentOffset + contentSize },
        { x: contentOffset, y: contentOffset + contentSize },
      ]
    }
  } else {
    const tileIndex = mapStore.selectedTileIndex
    if (tileIndex < 0) { collisionPoints.value = []; return }
    const globalIdx = mapStore.globalResourceOffset + mapStore.selectedResourceIndex
    const tileSet = mapStore.mapData.tileSets[globalIdx]
    if (tileSet && tileSet.tiles[tileIndex]?.collisionShape?.points) {
      collisionPoints.value = tileSet.tiles[tileIndex].collisionShape!.points.map(
        (p: number[]) => ({ x: p[0] * contentSize + contentOffset, y: p[1] * contentSize + contentOffset })
      )
    } else {
      collisionPoints.value = [
        { x: contentOffset, y: contentOffset },
        { x: contentOffset + contentSize, y: contentOffset },
        { x: contentOffset + contentSize, y: contentOffset + contentSize },
        { x: contentOffset, y: contentOffset + contentSize },
      ]
    }
  }
}

const snapGrid = 8
function snapToGrid(val: number): number {
  return mapStore.snapToPixel ? Math.round(val / snapGrid) * snapGrid : val
}

function getCanvasPos(e: MouseEvent): { x: number; y: number } {
  if (!canvasRef.value) return { x: 0, y: 0 }
  const rect = canvasRef.value.getBoundingClientRect()
  return { x: e.clientX - rect.left, y: e.clientY - rect.top }
}

function findAnchor(pos: { x: number; y: number }): number {
  for (let i = 0; i < collisionPoints.value.length; i++) {
    const p = collisionPoints.value[i]
    if (Math.abs(p.x - pos.x) < 8 && Math.abs(p.y - pos.y) < 8) return i
  }
  return -1
}

function pointToSegmentDistance(p: { x: number; y: number }, a: { x: number; y: number }, b: { x: number; y: number }): number {
  const dx = b.x - a.x, dy = b.y - a.y
  const lenSq = dx * dx + dy * dy
  if (lenSq === 0) return Math.hypot(p.x - a.x, p.y - a.y)
  let t = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / lenSq))
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy))
}

function onMouseDown(e: MouseEvent) {
  const pos = getCanvasPos(e)
  if (mapStore.collisionTool === 'add') {
    if (collisionPoints.value.length >= 3) {
      const first = collisionPoints.value[0]
      if (Math.abs(first.x - pos.x) < 8 && Math.abs(first.y - pos.y) < 8) {
        saveCollision(); render(); return
      }
    }
    if (collisionPoints.value.length >= 2) {
      let closestEdgeIdx = -1, closestDist = Infinity
      for (let i = 0; i < collisionPoints.value.length; i++) {
        const a = collisionPoints.value[i]
        const b = collisionPoints.value[(i + 1) % collisionPoints.value.length]
        const dist = pointToSegmentDistance(pos, a, b)
        if (dist < closestDist && dist < 20) { closestDist = dist; closestEdgeIdx = i + 1 }
      }
      if (closestEdgeIdx >= 0) {
        collisionPoints.value.splice(closestEdgeIdx, 0, { x: snapToGrid(pos.x), y: snapToGrid(pos.y) })
        saveCollision(); render(); return
      }
    }
    collisionPoints.value.push({ x: snapToGrid(pos.x), y: snapToGrid(pos.y) })
    saveCollision(); render()
  } else if (mapStore.collisionTool === 'delete') {
    const idx = findAnchor(pos)
    if (idx >= 0) { collisionPoints.value.splice(idx, 1); saveCollision(); render() }
  } else if (mapStore.collisionTool === 'move') {
    const idx = findAnchor(pos)
    if (idx >= 0) draggingIndex.value = idx
  }
}

function onMouseMove(e: MouseEvent) {
  if (draggingIndex.value >= 0) {
    const pos = getCanvasPos(e)
    collisionPoints.value[draggingIndex.value] = { x: snapToGrid(pos.x), y: snapToGrid(pos.y) }
    render()
  }
}

function onMouseUp() {
  if (draggingIndex.value >= 0) { draggingIndex.value = -1; saveCollision() }
}

async function resetCollision() {
  const isImageLayer = mapStore.activeLayer?.type === 'image'
  if (isImageLayer) {
    const rect = getImageRenderRect()
    collisionPoints.value = rect ? defaultCollisionFromRect(rect) : [
      { x: contentOffset, y: contentOffset },
      { x: contentOffset + contentSize, y: contentOffset },
      { x: contentOffset + contentSize, y: contentOffset + contentSize },
      { x: contentOffset, y: contentOffset + contentSize },
    ]
  } else {
    collisionPoints.value = [
      { x: contentOffset, y: contentOffset },
      { x: contentOffset + contentSize, y: contentOffset },
      { x: contentOffset + contentSize, y: contentOffset + contentSize },
      { x: contentOffset, y: contentOffset + contentSize },
    ]
  }
  saveCollision()
  render()
}

let lastResource: MapResource | null = null

// 当前碰撞是否启用（响应式，用于触发重绘）
const currentCollisionEnabled = computed(() => {
  const resource = mapStore.selectedResource
  const isImageLayer = mapStore.activeLayer?.type === 'image'
  if (isImageLayer) return resource?.collisionEnabled ?? false
  const tileIndex = mapStore.selectedTileIndex
  if (tileIndex >= 0) {
    const ts = mapStore.mapData.tileSets[mapStore.globalResourceOffset + mapStore.selectedResourceIndex]
    return ts?.tiles[tileIndex]?.collision ?? false
  }
  const ts = mapStore.mapData.tileSets.find(t => t.name === resource?.name)
  return ts?.collisionEnabled ?? false
})

watch(
  () => [
    mapStore.selectedResourceIndex,
    mapStore.selectedTileIndex,
    mapStore.activeLayerIndex,
    mapStore.selectedResource?.collisionType,
    mapStore.selectedResource?.collisionEnabled,
  ],
  async () => {
    if (lastResource && collisionPoints.value.length > 0) saveCollision(lastResource)
    lastResource = mapStore.selectedResource ?? null
    await preloadImage()
    loadCollision()
    nextTick(render)
  }
)

// 实时监听碰撞启用状态变化，重绘画布
watch(currentCollisionEnabled, () => {
  if (ctx) nextTick(render)
})

onMounted(async () => {
  if (canvasRef.value) {
    ctx = canvasRef.value.getContext('2d')
    lastResource = mapStore.selectedResource ?? null
    await preloadImage()
    render()
  }
})

defineExpose({ resetCollision })
</script>

<template>
  <div class="col-editor">
    <canvas
      ref="canvasRef"
      :width="tileSize"
      :height="tileSize"
      class="col-canvas"
      :style="{ imageRendering: imageRenderingStyle }"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @mouseleave="onMouseUp"
    />
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
  border: 1px solid var(--border-light);
  border-radius: 4px;
  cursor: crosshair;
}
</style>
