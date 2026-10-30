<script setup lang="ts">
import { ref, watch, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { useMapStore, type MapResource, type ShapeKind } from '../../stores/map'
import { SHAPE_KIND_COLORS_HEX } from '../../utils/shapeStyle'
import { useMapEditorStore } from '../../stores/mapEditor'
import { useProjectStore } from '../../stores/project'
import { useEditorStore } from '../../stores/editor'
import { snapAxisValue } from '../../utils/smartSnap'

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()
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

const canvasRef = ref<HTMLCanvasElement>()
const editorRef = ref<HTMLDivElement>()
/** 画布在界面上的显示边长：随下方工作区拖拽自适应，内部坐标仍是 tileSize */
const canvasSize = ref(256)
let resizeObserver: ResizeObserver | null = null
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

  // 棋盘格由外层容器 CSS 铺满，画布保持透明；图形和碰撞网格画在透明画布上

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

  // Collision polygon — 仅在碰撞启用时绘制（颜色按作用类型，和碰撞图层一致）
  if (currentCollisionEnabled.value && collisionPoints.value.length >= 2) {
    ctx.beginPath()
    ctx.moveTo(collisionPoints.value[0].x, collisionPoints.value[0].y)
    for (let i = 1; i < collisionPoints.value.length; i++) {
      ctx.lineTo(collisionPoints.value[i].x, collisionPoints.value[i].y)
    }
    ctx.closePath()
    ctx.fillStyle = `rgba(${previewColorRgb.value}, 0.2)`
    ctx.fill()
    ctx.strokeStyle = `rgba(${previewColorRgb.value}, 0.8)`
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

/**
 * 保存碰撞到指定图块 / 图片。
 * 必须显式传 tileIndex：切换图块时 store 里已经是"新图块"，
 * 若沿用 store 的值会把上一块的结果写到新块上（碰撞时有时无的元凶）。
 */
function saveCollision(
  resource = mapStore.selectedResource,
  tileIndex = mapStore.selectedTileIndex,
) {
  if (!resource) return
  const isImageLayer = mapStore.activeLayer?.type === 'image'

  if (isImageLayer) {
    resource.collisionShape = {
      points: collisionPoints.value.map(p => [p.x / tileSize, p.y / tileSize])
    }
    resource.collisionEnabled = collisionPoints.value.length > 0
    return
  }

  if (tileIndex < 0) return
  const tileSet = mapStore.getTileSetForResource(resource)
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

function loadCollision() {
  const resource = mapStore.selectedResource
  if (!resource) { collisionPoints.value = []; return }

  const isImageLayer = mapStore.activeLayer?.type === 'image'
  if (isImageLayer) {
    // 图片图层：碰撞类型为「图像」等于没开碰撞
    if (resource.collisionType === '图像') { collisionPoints.value = []; return }
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
    return
  }

  // 图块：只看这一块图块自己的碰撞数据，不受图块集整体 collisionType 影响
  const tileIndex = mapStore.selectedTileIndex
  if (tileIndex < 0) { collisionPoints.value = []; return }
  const tileSet = mapStore.getTileSetForResource(resource)
  const points = tileSet?.tiles[tileIndex]?.collisionShape?.points
  if (points?.length) {
    collisionPoints.value = points.map(
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

const snapGrid = 8
/** 智能吸附：像素 / 8px 网格 / 编辑区边界与中心；关闭后完全自由 */
function snapValue(val: number): number {
  if (!mapEditorStore.smartSnap) return val
  const lines = [
    0,
    tileSize,
    contentOffset,
    contentOffset + contentSize / 2,
    contentOffset + contentSize,
  ]
  return snapAxisValue(val, lines, snapGrid, 6)
}

function getCanvasPos(e: MouseEvent): { x: number; y: number } {
  if (!canvasRef.value) return { x: 0, y: 0 }
  const rect = canvasRef.value.getBoundingClientRect()
  // 画布内部坐标固定为 tileSize，界面尺寸会随工作区高度缩放，这里换算回内部坐标
  const scaleX = rect.width > 0 ? canvasRef.value.width / rect.width : 1
  const scaleY = rect.height > 0 ? canvasRef.value.height / rect.height : 1
  return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY }
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
  if (mapEditorStore.collisionTool === 'add') {
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
        collisionPoints.value.splice(closestEdgeIdx, 0, { x: snapValue(pos.x), y: snapValue(pos.y) })
        saveCollision(); render(); return
      }
    }
    collisionPoints.value.push({ x: snapValue(pos.x), y: snapValue(pos.y) })
    dirty = true
    saveCollision(); render()
  } else if (mapEditorStore.collisionTool === 'delete') {
    const idx = findAnchor(pos)
    if (idx >= 0) { collisionPoints.value.splice(idx, 1); dirty = true; saveCollision(); render() }
  } else if (mapEditorStore.collisionTool === 'move') {
    const idx = findAnchor(pos)
    if (idx >= 0) draggingIndex.value = idx
  }
}

function onMouseMove(e: MouseEvent) {
  if (draggingIndex.value >= 0) {
    const pos = getCanvasPos(e)
    collisionPoints.value[draggingIndex.value] = { x: snapValue(pos.x), y: snapValue(pos.y) }
    dirty = true
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
  dirty = false
  render()
}

/** 上一次正在编辑的目标：切走时把改动写回"这一块"，而不是新选中的那一块 */
let lastTarget: { resource: MapResource; tileIndex: number } | null = null
/** 当前这块是否被改动过：只有改过才在切换时回写，避免把默认整格误存成碰撞 */
let dirty = false

function currentTarget() {
  const resource = mapStore.selectedResource
  if (!resource) return null
  const tileIndex = mapStore.activeLayer?.type === 'image' ? -1 : mapStore.selectedTileIndex
  return { resource, tileIndex }
}

/** 切换选中前，把上一块的编辑结果写回上一块 */
function flushPendingSave() {
  if (!dirty || !lastTarget) return
  saveCollision(lastTarget.resource, lastTarget.tileIndex)
  dirty = false
}

// 当前碰撞是否启用（响应式，用于触发重绘）
const currentCollisionEnabled = computed(() => {
  const resource = mapStore.selectedResource
  const isImageLayer = mapStore.activeLayer?.type === 'image'
  if (isImageLayer) return resource?.collisionEnabled ?? false
  const tileIndex = mapStore.selectedTileIndex
  if (tileIndex >= 0) {
    const ts = mapStore.getTileSetForResource(resource)
    return ts?.tiles[tileIndex]?.collision ?? false
  }
  const ts = mapStore.getTileSetForResource(resource)
  return ts?.collisionEnabled ?? false
})

/** 当前预览对象的作用（图片层没有作用，统一按碰撞色处理） */
const previewKind = computed<ShapeKind>(() => {
  if (mapStore.activeLayer?.type === 'image') return 'solid'
  const tileIndex = mapStore.selectedTileIndex
  if (tileIndex < 0) return 'solid'
  const ts = mapStore.getTileSetForResource(mapStore.selectedResource)
  return (ts?.tiles[tileIndex]?.kind as ShapeKind) || 'solid'
})

/** 碰撞预览颜色（与碰撞图层共用一套） */
const previewColorRgb = computed(() => {
  const hex = SHAPE_KIND_COLORS_HEX[previewKind.value] ?? SHAPE_KIND_COLORS_HEX.solid
  return `${(hex >> 16) & 0xff}, ${(hex >> 8) & 0xff}, ${hex & 0xff}`
})

watch(
  () => [
    mapStore.selectedResourceIndex,
    mapStore.selectedTileIndex,
    mapStore.activeLayerIndex,
    mapStore.mapLoadCount,
  ],
  async () => {
    // 先把上一块的改动写回上一块，再加载新的一块
    flushPendingSave()
    await preloadImage()
    lastTarget = currentTarget()
    loadCollision()
    nextTick(render)
  }
)

// 实时监听碰撞启用状态变化，重绘画布
watch(currentCollisionEnabled, () => {
  if (ctx) nextTick(render)
})

// 作用类型变了（碰撞 / 感应 / 碰撞 + 感应）：换颜色重绘
watch(previewKind, () => {
  if (ctx) nextTick(render)
})

onMounted(async () => {
  if (canvasRef.value) {
    ctx = canvasRef.value.getContext('2d')
    await preloadImage()
    lastTarget = currentTarget()
    loadCollision()
    render()
  }
  // 工作区可以拖拽改高度：画布取“可用宽高较小值”作为显示边长
  if (editorRef.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver((entries) => {
      const box = entries[0]?.contentRect
      if (!box) return
      const size = Math.max(80, Math.floor(Math.min(box.width, box.height)))
      if (size !== canvasSize.value) canvasSize.value = size
    })
    resizeObserver.observe(editorRef.value)
  }
})

onBeforeUnmount(() => {
  flushPendingSave()
  resizeObserver?.disconnect()
  resizeObserver = null
})

defineExpose({ resetCollision })
</script>

<template>
  <div ref="editorRef" class="col-editor">
    <canvas
      ref="canvasRef"
      :width="tileSize"
      :height="tileSize"
      class="col-canvas"
      :style="{ width: `${canvasSize}px`, height: `${canvasSize}px`, imageRendering: imageRenderingStyle }"
      @mousedown="onMouseDown"
      @mousemove="onMouseMove"
      @mouseup="onMouseUp"
      @mouseleave="onMouseUp"
    />
  </div>
</template>

<style scoped>
.col-editor {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  /* 棋盘格铺满整个碰撞预览区，画布只负责画图形与碰撞点 */
  background: repeating-conic-gradient(#2a2a2a 0% 25%, #3a3a3a 0% 50%) 0 0 / 32px 32px;
}

.col-canvas {
  display: block;
  background: transparent;
  border: none;
  border-radius: 0;
  cursor: crosshair;
}
</style>
