# Map Editor & Map Resource Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the full map editor and map resource manager from the original PySide6 project to the Vue/Tauri BingoCodeIDE.

**Architecture:** 3-column layout (resource panel | canvas | property/layer panel) using PixiJS 8 for infinite canvas with pan/zoom/grid/tile-painting. Pinia stores manage map state with auto-save. Library pages provide card-grid browsing of built-in maps and resources.

**Tech Stack:** Vue 3 Composition API, Pinia, PixiJS 8, TypeScript, TailwindCSS

## Global Constraints

- Use PixiJS 8 (already in `package.json`) for canvas rendering
- Follow existing conventions: Composition API, `<script setup>`, Pinia stores, scoped styles
- All icons already exist in `src/assets/icons/` — do not create new ones
- Match original QSS colors exactly (see AGENTS.md color reference)
- No new dependencies — use only what's in `package.json`
- Browser file I/O for now (Tauri native later)
- Auto-save pattern: every change triggers save
- No formal test framework — verify via manual `pnpm dev` testing
- Chinese variable names and comments are intentional — follow the convention

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `src/stores/map.ts` | Modify | Extend with tools, selections, layers, resources, file I/O |
| `src/components/map-editor/MapEditorView.vue` | Rewrite | 3-column layout shell |
| `src/components/map-editor/MapCanvas.vue` | Create | PixiJS infinite canvas |
| `src/components/map-editor/MapToolbar.vue` | Create | Center toolbar |
| `src/components/map-editor/ResourceListPanel.vue` | Create | Left panel resource list |
| `src/components/map-editor/CollisionEditor.vue` | Create | Left panel collision editor |
| `src/components/map-editor/PropertyPanel.vue` | Create | Right panel map properties |
| `src/components/map-editor/LayerPanel.vue` | Create | Right panel layer management |
| `src/components/resource-panel/MapLibraryPage.vue` | Create | Full-screen map library |
| `src/components/resource-panel/MapResourceLibPage.vue` | Create | Full-screen resource library |
| `src/components/resource-panel/MapResourceImportDialog.vue` | Create | Import dialog modal |
| `src/components/resource-panel/MapUploadDrawer.vue` | Create | Slide-up map upload menu |
| `src/components/layout/MainLayout.vue` | Modify | Wire up map pages |

---

### Task 1: Extend Map Store

**Covers:** [S12], [S4]

**Files:**
- Modify: `src/stores/map.ts`

**Interfaces:**
- Produces: `useMapStore` with full state: `currentTool`, `selectedResourceIndex`, `selectedTileIndex`, `mapData`, `layers`, `activeLayerIndex`, `showGrid`, `layerResources`
- Produces: Actions: `newMap()`, `loadMapFromPath(path)`, `saveMap()`, `setTool(tool)`, `setTile()`, `getTile()`, `addLayer()`, `removeLayer()`, `moveLayerUp()`, `moveLayerDown()`, `toggleLayerVisibility()`, `renameLayer()`, `addResource()`, `removeResource()`, `selectTile()`, `updateMapProperty()`

- [ ] **Step 1: Rewrite `src/stores/map.ts` with full state and actions**

Replace the entire file with the following:

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface TileData {
  collision: boolean
  tag: string
  collisionType: string
  collisionShape?: { points: number[][] }
}

export interface TileSet {
  name: string
  imagePath: string
  resourceType: string
  tileWidth: number
  tileHeight: number
  collisionType: string
  collisionEnabled: boolean
  tiles: TileData[]
}

export interface MapLayer {
  id: number
  name: string
  type: 'drawing' | 'image'
  visible: boolean
  tiles: Record<string, number>
  images?: any[]
}

export interface MapResource {
  name: string
  path: string
  resourceType: string
  tileWidth: number
  tileHeight: number
  collisionType: string
  collisionEnabled: boolean
  tileSetIndex: number
}

export interface MapData {
  name: string
  width: number
  height: number
  tileSize: number
  offsetX: number
  offsetY: number
  gravity: boolean
  layers: MapLayer[]
  tileSets: TileSet[]
  layerResourcesMap?: Record<number, number[]>
}

export type MapTool = 'move' | 'select' | 'draw' | 'erase'

export const useMapStore = defineStore('map', () => {
  const currentMapPath = ref('')
  const mapData = ref<MapData>({
    name: '未命名地图',
    width: 40,
    height: 30,
    tileSize: 16,
    offsetX: 0,
    offsetY: 0,
    gravity: false,
    layers: [
      {
        id: 0,
        name: '图层',
        type: 'drawing',
        visible: true,
        tiles: {},
      },
    ],
    tileSets: [],
  })

  const activeLayerIndex = ref(0)
  const showGrid = ref(true)
  const currentTool = ref<MapTool>('move')
  const selectedResourceIndex = ref(-1)
  const selectedTileIndex = ref(-1)
  const mapResources = ref<MapResource[]>([])
  const layerResources = ref<Record<number, MapResource[]>>({})

  const activeLayer = computed(() => mapData.value.layers[activeLayerIndex.value] ?? null)

  function setMapPath(path: string) {
    currentMapPath.value = path
  }

  function loadMap(data: MapData) {
    mapData.value = data
    activeLayerIndex.value = 0
    selectedResourceIndex.value = -1
    selectedTileIndex.value = -1
  }

  function newMap() {
    mapData.value = {
      name: '未命名地图',
      width: 40,
      height: 30,
      tileSize: 16,
      offsetX: 0,
      offsetY: 0,
      gravity: false,
      layers: [
        {
          id: 0,
          name: '图层',
          type: 'drawing',
          visible: true,
          tiles: {},
        },
      ],
      tileSets: [],
    }
    activeLayerIndex.value = 0
    selectedResourceIndex.value = -1
    selectedTileIndex.value = -1
    mapResources.value = []
    layerResources.value = {}
    currentMapPath.value = ''
  }

  function setTool(tool: MapTool) {
    currentTool.value = tool
  }

  function setTile(x: number, y: number, tileId: number) {
    const layer = activeLayer.value
    if (!layer || layer.type !== 'drawing') return
    const key = `${x},${y}`
    if (tileId === 0) {
      delete layer.tiles[key]
    } else {
      layer.tiles[key] = tileId
    }
  }

  function getTile(x: number, y: number): number {
    const layer = activeLayer.value
    if (!layer || layer.type !== 'drawing') return 0
    return layer.tiles[`${x},${y}`] ?? 0
  }

  function addLayer(name: string, type: 'drawing' | 'image' = 'drawing') {
    const id = mapData.value.layers.length
    mapData.value.layers.push({
      id,
      name,
      type,
      visible: true,
      tiles: {},
    })
    activeLayerIndex.value = mapData.value.layers.length - 1
    return id
  }

  function removeLayer(index: number) {
    if (index >= 0 && index < mapData.value.layers.length && mapData.value.layers.length > 1) {
      mapData.value.layers.splice(index, 1)
      if (activeLayerIndex.value >= mapData.value.layers.length) {
        activeLayerIndex.value = mapData.value.layers.length - 1
      }
    }
  }

  function moveLayerUp(index: number) {
    if (index < mapData.value.layers.length - 1) {
      const temp = mapData.value.layers[index]
      mapData.value.layers[index] = mapData.value.layers[index + 1]
      mapData.value.layers[index + 1] = temp
      activeLayerIndex.value = index + 1
    }
  }

  function moveLayerDown(index: number) {
    if (index > 0) {
      const temp = mapData.value.layers[index]
      mapData.value.layers[index] = mapData.value.layers[index - 1]
      mapData.value.layers[index - 1] = temp
      activeLayerIndex.value = index - 1
    }
  }

  function toggleLayerVisibility(index: number) {
    const layer = mapData.value.layers[index]
    if (layer) layer.visible = !layer.visible
  }

  function renameLayer(index: number, name: string) {
    const layer = mapData.value.layers[index]
    if (layer) layer.name = name
  }

  function setActiveLayer(index: number) {
    activeLayerIndex.value = index
    selectedResourceIndex.value = -1
    selectedTileIndex.value = -1
  }

  function toggleGrid() {
    showGrid.value = !showGrid.value
  }

  function selectTile(resourceIndex: number, tileIndex: number) {
    selectedResourceIndex.value = resourceIndex
    selectedTileIndex.value = tileIndex
  }

  function addResource(resource: MapResource) {
    mapResources.value.push(resource)
  }

  function removeResource(index: number) {
    if (index >= 0 && index < mapResources.value.length) {
      mapResources.value.splice(index, 1)
    }
  }

  function clearResources() {
    mapResources.value = []
  }

  function updateMapProperty(key: keyof MapData, value: any) {
    ;(mapData.value as any)[key] = value
  }

  function setTileCollision(tileSetIndex: number, tileIndex: number, collision: boolean) {
    const tileSet = mapData.value.tileSets[tileSetIndex]
    if (!tileSet) return
    while (tileSet.tiles.length <= tileIndex) {
      tileSet.tiles.push({
        collision: true,
        tag: '',
        collisionType: '图像',
      })
    }
    tileSet.tiles[tileIndex].collision = collision
  }

  return {
    currentMapPath,
    mapData,
    activeLayerIndex,
    showGrid,
    currentTool,
    selectedResourceIndex,
    selectedTileIndex,
    mapResources,
    layerResources,
    activeLayer,
    setMapPath,
    loadMap,
    newMap,
    setTool,
    setTile,
    getTile,
    addLayer,
    removeLayer,
    moveLayerUp,
    moveLayerDown,
    toggleLayerVisibility,
    renameLayer,
    setActiveLayer,
    toggleGrid,
    selectTile,
    addResource,
    removeResource,
    clearResources,
    updateMapProperty,
    setTileCollision,
  }
})
```

- [ ] **Step 2: Verify store compiles**

Run: `pnpm dev` — no TypeScript errors in console.

- [ ] **Step 3: Commit**

```bash
git add src/stores/map.ts
git commit -m "feat(map-editor): extend map store with full state and actions"
```

---

### Task 2: Map Canvas (PixiJS)

**Covers:** [S5]

**Files:**
- Create: `src/components/map-editor/MapCanvas.vue`

**Interfaces:**
- Consumes: `useMapStore` (mapData, showGrid, currentTool, selectedResourceIndex, selectedTileIndex)
- Produces: Emits `tile-painted(x, y, tileId)`, `tile-erased(x, y)`, exposes `redraw()` method

- [ ] **Step 1: Create `src/components/map-editor/MapCanvas.vue`**

```vue
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useMapStore } from '../../stores/map'

const emit = defineEmits<{
  'tile-painted': [x: number, y: number, tileId: number]
  'tile-erased': [x: number, y: number]
}>()

const canvasRef = ref<HTMLDivElement>()
let app: any = null
let gridGraphics: any = null
let axisX: any = null
let axisY: any = null
let gameWindowRect: any = null
let tileContainer: any = null
let previewTile: any = null
let isPanning = false
let lastPointer = { x: 0, y: 0 }
let currentScale = 1.6

const mapStore = useMapStore()

async function initPixi() {
  if (!canvasRef.value) return

  const PIXI = await import('pixi.js')
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
  redraw()
}

function drawGrid() {
  if (!app) return
  const PIXI = require('pixi.js')
  if (gridGraphics) app.stage.removeChild(gridGraphics)
  gridGraphics = new PIXI.Graphics()

  const { width, height, tileSize } = mapStore.mapData
  const gridW = width * tileSize
  const gridH = height * tileSize

  gridGraphics.rect(0, 0, gridW, gridH)
  gridGraphics.stroke({ width: 1, color: 0x444444 })

  for (let x = 0; x <= width; x++) {
    gridGraphics.moveTo(x * tileSize, 0)
    gridGraphics.lineTo(x * tileSize, gridH)
  }
  for (let y = 0; y <= height; y++) {
    gridGraphics.moveTo(0, y * tileSize)
    gridGraphics.lineTo(gridW, y * tileSize)
  }
  gridGraphics.stroke({ width: 0.5, color: 0x333333 })

  gridGraphics.visible = mapStore.showGrid
  app.stage.addChildAt(gridGraphics, 0)
}

function drawAxes() {
  if (!app) return
  const PIXI = require('pixi.js')
  if (axisX) app.stage.removeChild(axisX)
  if (axisY) app.stage.removeChild(axisY)

  axisX = new PIXI.Graphics()
  axisX.moveTo(-10000, 0)
  axisX.lineTo(10000, 0)
  axisX.stroke({ width: 1, color: 0xC83232 })
  app.stage.addChild(axisX)

  axisY = new PIXI.Graphics()
  axisY.moveTo(0, -10000)
  axisY.lineTo(0, 10000)
  axisY.stroke({ width: 1, color: 0x32C832 })
  app.stage.addChild(axisY)
}

function drawGameWindow() {
  if (!app) return
  const PIXI = require('pixi.js')
  if (gameWindowRect) app.stage.removeChild(gameWindowRect)

  gameWindowRect = new PIXI.Graphics()
  gameWindowRect.rect(0, 0, 640, 480)
  gameWindowRect.stroke({ width: 1, color: 0xB4B4FF, style: 'dashed' })
  app.stage.addChild(gameWindowRect)
}

function setupInteraction() {
  if (!app || !app.canvas) return
  const canvas = app.canvas as HTMLCanvasElement

  canvas.addEventListener('wheel', (e: WheelEvent) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? 0.9 : 1.1
    currentScale = Math.max(0.5, Math.min(4, currentScale * delta))
    app.stage.scale.set(currentScale, currentScale)
  }, { passive: false })

  canvas.addEventListener('pointerdown', (e: PointerEvent) => {
    if (e.button === 1 || (e.button === 0 && e.altKey)) {
      isPanning = true
      lastPointer = { x: e.clientX, y: e.clientY }
      canvas.style.cursor = 'grabbing'
      e.preventDefault()
      return
    }

    if (e.button === 0 && mapStore.currentTool !== 'move' && mapStore.currentTool !== 'select') {
      const pos = screenToGrid(e)
      if (pos) {
        if (mapStore.currentTool === 'draw' && mapStore.selectedTileIndex >= 0) {
          const tileId = (mapStore.selectedResourceIndex + 1) * 1000 + mapStore.selectedTileIndex
          mapStore.setTile(pos.x, pos.y, tileId)
          emit('tile-painted', pos.x, pos.y, tileId)
        } else if (mapStore.currentTool === 'erase') {
          mapStore.setTile(pos.x, pos.y, 0)
          emit('tile-erased', pos.x, pos.y)
        }
      }
    }
  })

  canvas.addEventListener('pointermove', (e: PointerEvent) => {
    if (isPanning) {
      const dx = e.clientX - lastPointer.x
      const dy = e.clientY - lastPointer.y
      app.stage.x += dx
      app.stage.y += dy
      lastPointer = { x: e.clientX, y: e.clientY }
      return
    }

    if (mapStore.currentTool === 'draw' || mapStore.currentTool === 'erase') {
      const pos = screenToGrid(e)
      updatePreview(pos)
    }
  })

  canvas.addEventListener('pointerup', () => {
    isPanning = false
    if (canvasRef.value) canvasRef.value.style.cursor = 'default'
  })
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
  if (!app) return
  const PIXI = require('pixi.js')

  if (previewTile) {
    app.stage.removeChild(previewTile)
    previewTile = null
  }

  if (!pos) return
  const tileSize = mapStore.mapData.tileSize

  previewTile = new PIXI.Graphics()
  previewTile.rect(pos.x * tileSize, pos.y * tileSize, tileSize, tileSize)
  previewTile.stroke({ width: 1, color: 0x5BFB84 })
  app.stage.addChild(previewTile)
}

function redraw() {
  drawGrid()
  if (gridGraphics) gridGraphics.visible = mapStore.showGrid
}

watch(() => mapStore.showGrid, redraw)
watch(() => [mapStore.mapData.width, mapStore.mapData.height, mapStore.mapData.tileSize], redraw)

onMounted(() => {
  nextTick(initPixi)
})

onBeforeUnmount(() => {
  if (app) {
    app.destroy(true)
    app = null
  }
})

defineExpose({ redraw })
</script>

<template>
  <div ref="canvasRef" class="map-canvas" />
</template>

<style scoped>
.map-canvas {
  width: 100%;
  height: 100%;
  background: rgb(30, 30, 30);
  overflow: hidden;
}
</style>
```

- [ ] **Step 2: Verify canvas renders**

Run: `pnpm dev` → switch to map editor mode. Canvas should show grid, axes, and game window rect.

- [ ] **Step 3: Commit**

```bash
git add src/components/map-editor/MapCanvas.vue
git commit -m "feat(map-editor): add PixiJS canvas with pan/zoom/grid"
```

---

### Task 3: Map Toolbar

**Covers:** [S4], [S5]

**Files:**
- Create: `src/components/map-editor/MapToolbar.vue`

**Interfaces:**
- Consumes: `useMapStore` (currentTool, showGrid)
- Produces: Emits `new-map`, `import-map`, `export-map`, `tool-change(tool)`

- [ ] **Step 1: Create `src/components/map-editor/MapToolbar.vue`**

```vue
<script setup lang="ts">
import { useMapStore } from '../../stores/map'
import type { MapTool } from '../../stores/map'

const emit = defineEmits<{
  'new-map': []
  'import-map': []
  'export-map': []
}>()

const mapStore = useMapStore()

const tools: { id: MapTool; icon: string; label: string }[] = [
  { id: 'move', icon: '移动工具.svg', label: '移动' },
  { id: 'select', icon: '选取工具.svg', label: '选取' },
  { id: 'draw', icon: 'icon--paint.svg', label: '绘制' },
  { id: 'erase', icon: '清空.svg', label: '擦除' },
]
</script>

<template>
  <div class="map-toolbar">
    <button class="toolbar-btn" title="新建地图" @click="emit('new-map')">
      <img src="../../assets/icons/新建地图.svg" class="toolbar-icon" />
    </button>
    <button class="toolbar-btn" title="导入 .bgm" @click="emit('import-map')">
      <img src="../../assets/icons/导入地图.svg" class="toolbar-icon" />
    </button>
    <button class="toolbar-btn" title="导出 .bgm" @click="emit('export-map')">
      <img src="../../assets/icons/导出地图.svg" class="toolbar-icon" />
    </button>

    <div class="toolbar-separator" />

    <button
      v-for="tool in tools"
      :key="tool.id"
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapStore.currentTool === tool.id }"
      :title="tool.label"
      @click="mapStore.setTool(tool.id)"
    >
      <img :src="`../../assets/icons/${tool.icon}`" class="toolbar-icon" />
    </button>

    <div class="toolbar-separator" />

    <button
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapStore.showGrid }"
      title="显示网格"
      @click="mapStore.toggleGrid()"
    >
      <img src="../../assets/icons/显示网格.svg" class="toolbar-icon" />
    </button>

    <div class="toolbar-spacer" />

    <select class="map-selector">
      <option>未命名地图</option>
    </select>
  </div>
</template>

<style scoped>
.map-toolbar {
  display: flex;
  align-items: center;
  height: 30px;
  padding: 0 4px;
  gap: 2px;
  background: rgb(34, 37, 43);
  border-bottom: 1px solid rgb(12, 12, 12);
  flex-shrink: 0;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  padding: 4px;
  transition: background 0.15s;
}

.toolbar-btn:hover {
  background: rgb(61, 64, 72);
}

.toolbar-btn:active {
  background: rgb(72, 75, 82);
}

.toolbar-btn-active {
  background: rgb(46, 49, 58);
  border: 1px solid rgb(55, 59, 68);
}

.toolbar-btn-active:hover {
  background: rgb(55, 59, 68);
}

.toolbar-icon {
  width: 20px;
  height: 20px;
}

.toolbar-separator {
  width: 1px;
  height: 20px;
  background: rgb(55, 59, 68);
  margin: 0 2px;
}

.toolbar-spacer {
  flex: 1;
}

.map-selector {
  border: 1px solid rgb(55, 59, 68);
  border-radius: 4px;
  background: rgb(40, 43, 52);
  color: white;
  padding: 3px 8px;
  font-size: 12px;
  min-width: 100px;
  outline: none;
}

.map-selector:hover {
  border: 1px solid rgb(65, 69, 82);
  background: rgb(50, 53, 62);
}
</style>
```

- [ ] **Step 2: Verify toolbar renders**

Run: `pnpm dev` → map editor should show toolbar with icons. Click tools to verify toggle.

- [ ] **Step 3: Commit**

```bash
git add src/components/map-editor/MapToolbar.vue
git commit -m "feat(map-editor): add map toolbar with tools and grid toggle"
```

---

### Task 4: Resource List Panel

**Covers:** [S6]

**Files:**
- Create: `src/components/map-editor/ResourceListPanel.vue`

**Interfaces:**
- Consumes: `useMapStore` (mapResources, selectedResourceIndex, selectedTileIndex)
- Produces: Emits `open-library`, `upload-resource`, `delete-resource`, `clear-resources`, `select-tile(resourceIndex, tileIndex)`

- [ ] **Step 1: Create `src/components/map-editor/ResourceListPanel.vue`**

```vue
<script setup lang="ts">
import { useMapStore } from '../../stores/map'

const emit = defineEmits<{
  'open-library': []
  'upload-resource': []
  'delete-resource': [index: number]
  'clear-resources': []
  'select-tile': [resourceIndex: number, tileIndex: number]
}>()

const mapStore = useMapStore()

function getTileCount(resource: any) {
  if (!resource.tileWidth || !resource.tileHeight) return 0
  return 32
}
</script>

<template>
  <div class="resource-list-panel">
    <div class="resource-toolbar">
      <button class="res-tool-btn" title="打开资源库" @click="emit('open-library')">
        <img src="../../assets/icons/图片库.svg" class="res-tool-icon" />
      </button>
      <button class="res-tool-btn" title="上传本地资源" @click="emit('upload-resource')">
        <img src="../../assets/icons/上传本地图片资源.svg" class="res-tool-icon" />
      </button>
      <button class="res-tool-btn" title="选中删除" @click="emit('delete-resource', mapStore.selectedResourceIndex)">
        <img src="../../assets/icons/选中删除.svg" class="res-tool-icon" />
      </button>
      <button class="res-tool-btn" title="重置" @click="emit('clear-resources')">
        <img src="../../assets/icons/重置.svg" class="res-tool-icon" />
      </button>
    </div>

    <div class="resource-list">
      <div
        v-for="(resource, rIdx) in mapStore.mapResources"
        :key="rIdx"
        class="resource-group"
      >
        <div class="resource-name">{{ resource.name }}</div>
        <div class="tile-grid">
          <div
            v-for="tIdx in getTileCount(resource)"
            :key="tIdx"
            class="tile-cell"
            :class="{
              'tile-selected': mapStore.selectedResourceIndex === rIdx && mapStore.selectedTileIndex === tIdx
            }"
            @click="emit('select-tile', rIdx, tIdx)"
          />
        </div>
      </div>
      <div v-if="mapStore.mapResources.length === 0" class="resource-empty">
        暂无资源
      </div>
    </div>

    <div class="res-info-bar">
      <span v-if="mapStore.selectedResourceIndex >= 0">
        {{ mapStore.mapResources[mapStore.selectedResourceIndex]?.name || '' }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.resource-list-panel {
  display: flex;
  flex-direction: column;
  width: 256px;
  min-width: 256px;
  background: rgb(34, 37, 43);
  border-right: 1px solid rgb(12, 12, 12);
}

.resource-toolbar {
  display: flex;
  align-items: center;
  height: 30px;
  padding: 0 4px;
  gap: 2px;
}

.res-tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  padding: 4px;
  transition: background 0.15s;
}

.res-tool-btn:hover {
  background: rgb(61, 64, 72);
}

.res-tool-icon {
  width: 20px;
  height: 20px;
}

.resource-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px;
}

.resource-group {
  margin-bottom: 8px;
}

.resource-name {
  font-size: 11px;
  color: rgb(156, 160, 164);
  padding: 4px 4px 2px;
}

.tile-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 1px;
  padding: 2px;
}

.tile-cell {
  aspect-ratio: 1;
  background: rgb(50, 53, 62);
  border: 1px solid transparent;
  border-radius: 2px;
  cursor: pointer;
  transition: border-color 0.1s;
}

.tile-cell:hover {
  border-color: rgb(91, 199, 114);
}

.tile-selected {
  border-color: rgb(91, 199, 114) !important;
  background: rgb(60, 65, 75);
}

.resource-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100px;
  color: rgb(80, 80, 80);
  font-size: 12px;
}

.res-info-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  font-size: 12px;
  color: rgb(156, 160, 164);
}
</style>
```

- [ ] **Step 2: Verify panel renders**

Run: `pnpm dev` → left panel should show toolbar and "暂无资源" placeholder.

- [ ] **Step 3: Commit**

```bash
git add src/components/map-editor/ResourceListPanel.vue
git commit -m "feat(map-editor): add resource list panel with toolbar"
```

---

### Task 5: Property Panel

**Covers:** [S7]

**Files:**
- Create: `src/components/map-editor/PropertyPanel.vue`

**Interfaces:**
- Consumes: `useMapStore` (mapData)
- Produces: Updates mapData properties via store actions

- [ ] **Step 1: Create `src/components/map-editor/PropertyPanel.vue`**

```vue
<script setup lang="ts">
import { useMapStore } from '../../stores/map'

const mapStore = useMapStore()

const tileSizes = [16, 32, 64]
const collisionTypes = ['图像', '墙体', '跳板', '自定义']
</script>

<template>
  <div class="property-panel">
    <div class="prop-header">地图属性</div>

    <div class="prop-grid">
      <label class="prop-label">名称</label>
      <input
        class="prop-input"
        :value="mapStore.mapData.name"
        @input="mapStore.updateMapProperty('name', ($event.target as HTMLInputElement).value)"
      />

      <label class="prop-label">尺寸 X</label>
      <input
        class="prop-input"
        type="number"
        :value="mapStore.mapData.width"
        @input="mapStore.updateMapProperty('width', Number(($event.target as HTMLInputElement).value))"
      />

      <label class="prop-label">尺寸 Y</label>
      <input
        class="prop-input"
        type="number"
        :value="mapStore.mapData.height"
        @input="mapStore.updateMapProperty('height', Number(($event.target as HTMLInputElement).value))"
      />

      <label class="prop-label">重力</label>
      <label class="prop-checkbox">
        <input
          type="checkbox"
          :checked="mapStore.mapData.gravity"
          @change="mapStore.updateMapProperty('gravity', ($event.target as HTMLInputElement).checked)"
        />
      </label>

      <label class="prop-label">瓦片大小</label>
      <select
        class="prop-select"
        :value="mapStore.mapData.tileSize"
        @change="mapStore.updateMapProperty('tileSize', Number(($event.target as HTMLSelectElement).value))"
      >
        <option v-for="size in tileSizes" :key="size" :value="size">{{ size }}x{{ size }}</option>
      </select>

      <label class="prop-label">碰撞类型</label>
      <select class="prop-select" value="图像">
        <option v-for="ct in collisionTypes" :key="ct" :value="ct">{{ ct }}</option>
      </select>

      <label class="prop-label">标签</label>
      <input class="prop-input" placeholder="" />

      <label class="prop-label">碰撞启用</label>
      <label class="prop-checkbox">
        <input type="checkbox" />
      </label>
    </div>
  </div>
</template>

<style scoped>
.property-panel {
  width: 256px;
  min-width: 256px;
  background: rgb(34, 37, 43);
  border-left: 1px solid rgb(12, 12, 12);
}

.prop-header {
  text-align: center;
  color: rgb(156, 160, 164);
  font-size: 12px;
  padding: 8px 0;
  border-bottom: 1px solid rgb(45, 45, 45);
}

.prop-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px 8px;
  padding: 10px 8px;
  align-items: center;
}

.prop-label {
  color: rgb(156, 160, 164);
  font-size: 12px;
}

.prop-input {
  background: rgb(40, 43, 52);
  border: 1px solid rgb(55, 59, 68);
  border-radius: 4px;
  color: white;
  padding: 3px 6px;
  font-size: 12px;
  outline: none;
  width: 100%;
}

.prop-input:hover {
  background: rgb(50, 53, 62);
  border: 1px solid rgb(65, 69, 82);
}

.prop-input:focus {
  background: rgb(55, 59, 68);
  border: 1px solid #528bff;
  color: white;
}

.prop-select {
  border: 1px solid rgb(55, 59, 68);
  border-radius: 4px;
  background: rgb(40, 43, 52);
  color: white;
  padding: 3px 6px;
  font-size: 12px;
  outline: none;
  width: 100%;
}

.prop-select:hover {
  border: 1px solid rgb(65, 69, 82);
  background: rgb(50, 53, 62);
}

.prop-checkbox {
  display: flex;
  align-items: center;
}

.prop-checkbox input[type="checkbox"] {
  width: 14px;
  height: 14px;
  accent-color: #528bff;
}
</style>
```

- [ ] **Step 2: Verify panel renders**

Run: `pnpm dev` → right panel should show map properties with inputs.

- [ ] **Step 3: Commit**

```bash
git add src/components/map-editor/PropertyPanel.vue
git commit -m "feat(map-editor): add property panel with map settings"
```

---

### Task 6: Layer Panel

**Covers:** [S8]

**Files:**
- Create: `src/components/map-editor/LayerPanel.vue`

**Interfaces:**
- Consumes: `useMapStore` (mapData.layers, activeLayerIndex)
- Produces: Updates layers via store actions

- [ ] **Step 1: Create `src/components/map-editor/LayerPanel.vue`**

```vue
<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { useMapStore } from '../../stores/map'

const mapStore = useMapStore()
const editingLayerIndex = ref<number | null>(null)
const editingName = ref('')

function startRename(index: number) {
  editingLayerIndex.value = index
  editingName.value = mapStore.mapData.layers[index].name
  nextTick(() => {
    const input = document.querySelector('.layer-rename-input') as HTMLInputElement
    if (input) { input.focus(); input.select() }
  })
}

function confirmRename() {
  if (editingLayerIndex.value !== null && editingName.value.trim()) {
    mapStore.renameLayer(editingLayerIndex.value, editingName.value.trim())
  }
  editingLayerIndex.value = null
}

function cancelRename() {
  editingLayerIndex.value = null
}
</script>

<template>
  <div class="layer-panel">
    <div class="layer-header">图层</div>

    <div class="layer-toolbar">
      <button class="layer-tool-btn" title="新建图像图层" @click="mapStore.addLayer('图像图层', 'image')">
        <img src="../../assets/icons/图片库.svg" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" title="新建绘制图层" @click="mapStore.addLayer('绘制图层', 'drawing')">
        <img src="../../assets/icons/btn_preview_add.svg" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" title="删除图层" @click="mapStore.removeLayer(mapStore.activeLayerIndex)">
        <img src="../../assets/icons/选中删除.svg" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" title="上移图层" @click="mapStore.moveLayerUp(mapStore.activeLayerIndex)">
        <img src="../../assets/icons/上移图层.svg" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" title="下移图层" @click="mapStore.moveLayerDown(mapStore.activeLayerIndex)">
        <img src="../../assets/icons/下移图层.svg" class="layer-tool-icon" />
      </button>
    </div>

    <div class="layer-list">
      <div
        v-for="(layer, index) in [...mapStore.mapData.layers].reverse()"
        :key="layer.id"
        class="layer-item"
        :class="{ 'layer-item-active': mapStore.activeLayerIndex === mapStore.mapData.layers.length - 1 - index }"
        @click="mapStore.setActiveLayer(mapStore.mapData.layers.length - 1 - index)"
      >
        <button
          class="layer-vis-btn"
          :title="layer.visible ? '隐藏' : '显示'"
          @click.stop="mapStore.toggleLayerVisibility(mapStore.mapData.layers.length - 1 - index)"
        >
          <img :src="`../../assets/icons/${layer.visible ? 'icon_show.svg' : 'icon_hide.svg'}`" class="vis-icon" />
        </button>
        <template v-if="editingLayerIndex === mapStore.mapData.layers.length - 1 - index">
          <input
            class="layer-rename-input"
            v-model="editingName"
            @blur="confirmRename"
            @keydown.enter.prevent="confirmRename"
            @keydown.escape="cancelRename"
            @click.stop
          />
        </template>
        <template v-else>
          <span class="layer-name" @dblclick.stop="startRename(mapStore.mapData.layers.length - 1 - index)">
            {{ layer.name }}
          </span>
        </template>
      </div>
    </div>

    <div class="layer-mode-bar">
      <span class="layer-mode-text">
        {{ mapStore.activeLayer?.type === 'image' ? '图像' : '绘制' }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.layer-panel {
  display: flex;
  flex-direction: column;
}

.layer-header {
  text-align: center;
  color: rgb(156, 160, 164);
  font-size: 12px;
  padding: 8px 0;
  border-top: 1px solid rgb(45, 45, 45);
}

.layer-toolbar {
  display: flex;
  align-items: center;
  height: 30px;
  padding: 0 4px;
  gap: 2px;
}

.layer-tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  padding: 4px;
  transition: background 0.15s;
}

.layer-tool-btn:hover {
  background: rgb(61, 64, 72);
}

.layer-tool-icon {
  width: 20px;
  height: 20px;
}

.layer-list {
  flex: 1;
  overflow-y: auto;
}

.layer-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  cursor: pointer;
  transition: background 0.1s;
}

.layer-item:hover {
  background: #2c313a;
}

.layer-item-active {
  background: #3D6BE5;
  color: white;
}

.layer-vis-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  background: transparent;
  border: none;
  cursor: pointer;
  border-radius: 2px;
  flex-shrink: 0;
}

.layer-vis-btn:hover {
  background: rgb(61, 64, 72);
}

.vis-icon {
  width: 14px;
  height: 14px;
}

.layer-name {
  font-size: 12px;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.layer-rename-input {
  flex: 1;
  height: 18px;
  background: rgb(61, 61, 61);
  border: 1px solid rgb(91, 199, 114);
  border-radius: 2px;
  color: white;
  font-size: 12px;
  padding: 0 4px;
  outline: none;
}

.layer-mode-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 30px;
}

.layer-mode-text {
  font-size: 12px;
  color: rgb(156, 160, 164);
}
</style>
```

- [ ] **Step 2: Verify layer panel renders**

Run: `pnpm dev` → right panel should show layer list with visibility toggles.

- [ ] **Step 3: Commit**

```bash
git add src/components/map-editor/LayerPanel.vue
git commit -m "feat(map-editor): add layer panel with visibility and rename"
```

---

### Task 7: MapEditorView Assembly

**Covers:** [S4], [S13]

**Files:**
- Rewrite: `src/components/map-editor/MapEditorView.vue`

**Interfaces:**
- Consumes: All sub-components (MapToolbar, MapCanvas, ResourceListPanel, PropertyPanel, LayerPanel)
- Produces: Complete 3-column map editor layout

- [ ] **Step 1: Rewrite `src/components/map-editor/MapEditorView.vue`**

```vue
<script setup lang="ts">
import MapToolbar from './MapToolbar.vue'
import MapCanvas from './MapCanvas.vue'
import ResourceListPanel from './ResourceListPanel.vue'
import PropertyPanel from './PropertyPanel.vue'
import LayerPanel from './LayerPanel.vue'

function onNewMap() {
  // TODO: Task 10 - map file operations
}

function onImportMap() {
  // TODO: Task 10 - map file operations
}

function onExportMap() {
  // TODO: Task 10 - map file operations
}

function onOpenLibrary() {
  // TODO: Task 8 - map library page
}

function onUploadResource() {
  // TODO: Task 9 - resource import dialog
}
</script>

<template>
  <div class="map-editor-view">
    <MapToolbar
      @new-map="onNewMap"
      @import-map="onImportMap"
      @export-map="onExportMap"
    />
    <div class="map-editor-body">
      <ResourceListPanel
        @open-library="onOpenLibrary"
        @upload-resource="onUploadResource"
      />
      <div class="map-editor-center">
        <MapCanvas class="map-canvas-area" />
        <div class="map-info-bar">
          <span class="info-label">名称: {{ $store.map?.mapData.name }}</span>
          <span class="info-label">尺寸: {{ $store.map?.mapData.width }} × {{ $store.map?.mapData.height }}</span>
          <span class="info-label">瓦片: {{ $store.map?.mapData.tileSize }}px</span>
        </div>
      </div>
      <div class="map-editor-right">
        <PropertyPanel />
        <LayerPanel />
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
}

.map-editor-body {
  flex: 1;
  min-height: 0;
  display: flex;
}

.map-editor-center {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.map-canvas-area {
  flex: 1;
  min-height: 0;
}

.map-info-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  gap: 20px;
  background: rgb(34, 37, 43);
}

.info-label {
  font-size: 12px;
  color: rgb(156, 160, 164);
  padding: 0 6px;
}

.map-editor-right {
  display: flex;
  flex-direction: column;
  width: 256px;
  min-width: 256px;
}
</style>
```

- [ ] **Step 2: Fix the store reference in template**

The template uses `$store.map` which is wrong. Fix to use `useMapStore()`:

```vue
<script setup lang="ts">
import MapToolbar from './MapToolbar.vue'
import MapCanvas from './MapCanvas.vue'
import ResourceListPanel from './ResourceListPanel.vue'
import PropertyPanel from './PropertyPanel.vue'
import LayerPanel from './LayerPanel.vue'
import { useMapStore } from '../../stores/map'

const mapStore = useMapStore()

// ... rest of script stays same
</script>

<template>
  <div class="map-editor-view">
    <MapToolbar
      @new-map="onNewMap"
      @import-map="onImportMap"
      @export-map="onExportMap"
    />
    <div class="map-editor-body">
      <ResourceListPanel
        @open-library="onOpenLibrary"
        @upload-resource="onUploadResource"
      />
      <div class="map-editor-center">
        <MapCanvas class="map-canvas-area" />
        <div class="map-info-bar">
          <span class="info-label">名称: {{ mapStore.mapData.name }}</span>
          <span class="info-label">尺寸: {{ mapStore.mapData.width }} × {{ mapStore.mapData.height }}</span>
          <span class="info-label">瓦片: {{ mapStore.mapData.tileSize }}px</span>
        </div>
      </div>
      <div class="map-editor-right">
        <PropertyPanel />
        <LayerPanel />
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 3: Verify full layout renders**

Run: `pnpm dev` → switch to map editor mode. Should show 3-column layout with toolbar, canvas, and panels.

- [ ] **Step 4: Commit**

```bash
git add src/components/map-editor/MapEditorView.vue
git commit -m "feat(map-editor): assemble 3-column map editor layout"
```

---

### Task 8: Map Library Page

**Covers:** [S9]

**Files:**
- Create: `src/components/resource-panel/MapLibraryPage.vue`

**Interfaces:**
- Consumes: `useResourceStore` (maps)
- Produces: Emits `close`, `imported(mapPath)`

- [ ] **Step 1: Create `src/components/resource-panel/MapLibraryPage.vue`**

```vue
<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  'close': []
  'imported': [path: string]
}>()

const searchQuery = ref('')

// Placeholder for built-in map library
const maps = ref<{ name: string; path: string; thumbnail?: string }[]>([])
</script>

<template>
  <div class="map-lib-page">
    <div class="lib-toolbar">
      <input v-model="searchQuery" class="lib-search" placeholder="搜索..." />
      <div class="lib-spacer" />
      <span class="lib-hint">请选择地图</span>
      <div class="lib-spacer" />
      <div style="width:120px" />
      <button class="lib-return-btn" @click="emit('close')">返回</button>
    </div>
    <div class="lib-grid">
      <div v-for="map in maps" :key="map.path" class="lib-card" @click="emit('imported', map.path)">
        <div class="lib-card-thumb">
          <img v-if="map.thumbnail" :src="map.thumbnail" />
          <span v-else class="lib-card-placeholder">{{ map.name.charAt(0) }}</span>
        </div>
        <div class="lib-card-name">{{ map.name }}</div>
      </div>
      <div v-if="maps.length === 0" class="lib-empty">暂无地图</div>
    </div>
  </div>
</template>

<style scoped>
.map-lib-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: rgb(34, 37, 43);
}

.lib-toolbar {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 5px;
  gap: 0;
  flex-shrink: 0;
  border-bottom: 1px solid rgb(12, 12, 12);
}

.lib-search {
  width: 200px;
  height: 28px;
  padding: 0 8px;
  background: rgb(52, 55, 62);
  border: 1px solid rgb(73, 76, 86);
  border-radius: 6px;
  color: rgb(150, 150, 150);
  font-size: 12px;
  outline: none;
}

.lib-search:focus {
  border-color: rgb(91, 251, 132);
}

.lib-spacer { flex: 1; }

.lib-hint {
  font-size: 12px;
  color: rgb(128, 128, 128);
}

.lib-return-btn {
  width: 80px;
  height: 28px;
  background: rgb(52, 55, 62);
  border: 1px solid rgb(73, 76, 86);
  border-radius: 4px;
  color: rgb(150, 150, 150);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.lib-return-btn:hover {
  background: rgb(62, 65, 72);
  color: white;
}

.lib-grid {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 8px;
}

.lib-card {
  background: rgb(45, 45, 45);
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.lib-card:hover {
  background: rgb(60, 60, 60);
}

.lib-card-thumb {
  width: 150px;
  height: 110px;
  margin: 0 auto 8px;
  background: rgb(61, 61, 61);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.lib-card-thumb img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.lib-card-placeholder {
  font-size: 16px;
  color: rgb(230, 230, 230);
}

.lib-card-name {
  text-align: center;
  font-size: 10px;
  color: rgb(230, 230, 230);
}

.lib-empty {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: rgb(80, 80, 80);
  font-size: 12px;
}
</style>
```

- [ ] **Step 2: Verify page renders**

Run: `pnpm dev` → navigate to map library (page 2). Should show toolbar with search and empty grid.

- [ ] **Step 3: Commit**

```bash
git add src/components/resource-panel/MapLibraryPage.vue
git commit -m "feat(map-editor): add map library page with card grid"
```

---

### Task 9: Map Resource Library Page

**Covers:** [S10]

**Files:**
- Create: `src/components/resource-panel/MapResourceLibPage.vue`

**Interfaces:**
- Produces: Emits `close`, `imported(path)`

- [ ] **Step 1: Create `src/components/resource-panel/MapResourceLibPage.vue`**

```vue
<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  'close': []
  'imported': [path: string]
}>()

const searchQuery = ref('')
const activeCategory = ref<'images' | 'tiles' | 'tilesets'>('images')

const categories = [
  { id: 'images' as const, label: '图像' },
  { id: 'tiles' as const, label: '图块' },
  { id: 'tilesets' as const, label: '集合' },
]

const resources = ref<{ name: string; path: string; thumbnail?: string }[]>([])
</script>

<template>
  <div class="map-res-lib-page">
    <div class="lib-toolbar">
      <input v-model="searchQuery" class="lib-search" placeholder="搜索..." />
      <div style="width:10px" />
      <button
        v-for="cat in categories"
        :key="cat.id"
        class="lib-tab-btn"
        :class="{ 'lib-tab-active': activeCategory === cat.id }"
        @click="activeCategory = cat.id"
      >
        {{ cat.label }}
      </button>
      <div class="lib-spacer" />
      <div style="width:120px" />
      <button class="lib-return-btn" @click="emit('close')">返回</button>
    </div>
    <div class="lib-grid">
      <div v-for="res in resources" :key="res.path" class="lib-card" @click="emit('imported', res.path)">
        <div class="lib-card-thumb">
          <img v-if="res.thumbnail" :src="res.thumbnail" />
          <span v-else class="lib-card-placeholder">{{ res.name.charAt(0) }}</span>
        </div>
        <div class="lib-card-name">{{ res.name }}</div>
      </div>
      <div v-if="resources.length === 0" class="lib-empty">暂无素材</div>
    </div>
  </div>
</template>

<style scoped>
.map-res-lib-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: rgb(34, 37, 43);
}

.lib-toolbar {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 5px;
  gap: 0;
  flex-shrink: 0;
  border-bottom: 1px solid rgb(12, 12, 12);
}

.lib-search {
  width: 200px;
  height: 28px;
  padding: 0 8px;
  background: rgb(52, 55, 62);
  border: 1px solid rgb(73, 76, 86);
  border-radius: 6px;
  color: rgb(150, 150, 150);
  font-size: 12px;
  outline: none;
}

.lib-search:focus {
  border-color: rgb(91, 251, 132);
}

.lib-spacer { flex: 1; }

.lib-tab-btn {
  padding: 4px 16px;
  background: transparent;
  border: 1px solid rgb(73, 76, 86);
  border-radius: 4px;
  color: rgb(128, 128, 128);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.lib-tab-btn:hover {
  color: white;
}

.lib-tab-active {
  background: rgb(55, 120, 200);
  color: white;
  border-color: rgb(55, 120, 200);
}

.lib-return-btn {
  width: 80px;
  height: 28px;
  background: rgb(52, 55, 62);
  border: 1px solid rgb(73, 76, 86);
  border-radius: 4px;
  color: rgb(150, 150, 150);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.lib-return-btn:hover {
  background: rgb(62, 65, 72);
  color: white;
}

.lib-grid {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 8px;
}

.lib-card {
  background: rgb(45, 45, 45);
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.lib-card:hover {
  background: rgb(60, 60, 60);
}

.lib-card-thumb {
  width: 150px;
  height: 110px;
  margin: 0 auto 8px;
  background: rgb(61, 61, 61);
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.lib-card-thumb img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.lib-card-placeholder {
  font-size: 16px;
  color: rgb(230, 230, 230);
}

.lib-card-name {
  text-align: center;
  font-size: 10px;
  color: rgb(230, 230, 230);
}

.lib-empty {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: rgb(80, 80, 80);
  font-size: 12px;
}
</style>
```

- [ ] **Step 2: Verify page renders**

Run: `pnpm dev` → navigate to resource library (page 4). Should show category tabs and empty grid.

- [ ] **Step 3: Commit**

```bash
git add src/components/resource-panel/MapResourceLibPage.vue
git commit -m "feat(map-editor): add map resource library page with categories"
```

---

### Task 10: Map Resource Import Dialog

**Covers:** [S11]

**Files:**
- Create: `src/components/resource-panel/MapResourceImportDialog.vue`

**Interfaces:**
- Consumes: None
- Produces: Emits `close`, `imported({ path, mode, size })`

- [ ] **Step 1: Create `src/components/resource-panel/MapResourceImportDialog.vue`**

```vue
<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  'close': []
  'imported': [options: { path: string; mode: 'image' | 'tileset'; size: string }]
}>()

const resourcePath = ref('')
const mode = ref<'image' | 'tileset'>('image')
const tileSize = ref('16x16')

const sizes = ['16x16', '32x32', '64x64']

function onBrowse() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.png,.jpg,.jpeg,.bmp,.gif'
  input.onchange = (e: Event) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (file) resourcePath.value = file.name
  }
  input.click()
}

function onConfirm() {
  emit('imported', {
    path: resourcePath.value,
    mode: mode.value,
    size: tileSize.value,
  })
}
</script>

<template>
  <div class="dialog-overlay" @click.self="emit('close')">
    <div class="dialog-box">
      <div class="dialog-row">
        <label class="dialog-label">资源路径:</label>
        <input v-model="resourcePath" class="dialog-input" />
        <button class="dialog-btn" @click="onBrowse">浏览</button>
      </div>

      <div class="dialog-row">
        <label class="dialog-radio-group">
          <input type="radio" v-model="mode" value="image" />
          <span>图像模式</span>
        </label>
        <label class="dialog-radio-group">
          <input type="radio" v-model="mode" value="tileset" />
          <span>图块集合</span>
        </label>

        <div class="dialog-spacer" />

        <label class="dialog-label">尺寸:</label>
        <select v-model="tileSize" class="dialog-select">
          <option v-for="s in sizes" :key="s" :value="s">{{ s }}</option>
        </select>
      </div>

      <div class="dialog-row dialog-actions">
        <div class="dialog-spacer" />
        <button class="dialog-btn" @click="emit('close')">取消</button>
        <button class="dialog-btn dialog-btn-primary" @click="onConfirm">确定</button>
        <div class="dialog-spacer" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.dialog-box {
  background: rgb(34, 37, 43);
  border: 1px solid rgb(55, 59, 68);
  border-radius: 8px;
  padding: 20px;
  min-width: 380px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dialog-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dialog-label {
  font-size: 12px;
  color: rgb(156, 160, 164);
  white-space: nowrap;
}

.dialog-input {
  flex: 1;
  height: 28px;
  background: rgb(40, 43, 52);
  border: 1px solid rgb(55, 59, 68);
  border-radius: 4px;
  color: white;
  padding: 0 8px;
  font-size: 12px;
  outline: none;
}

.dialog-input:focus {
  border: 1px solid #528bff;
}

.dialog-select {
  height: 28px;
  background: rgb(40, 43, 52);
  border: 1px solid rgb(55, 59, 68);
  border-radius: 4px;
  color: white;
  padding: 0 8px;
  font-size: 12px;
  outline: none;
}

.dialog-btn {
  height: 28px;
  padding: 0 12px;
  background: rgb(52, 55, 62);
  border: 1px solid rgb(73, 76, 86);
  border-radius: 4px;
  color: rgb(150, 150, 150);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.dialog-btn:hover {
  background: rgb(62, 65, 72);
  color: white;
}

.dialog-btn-primary {
  background: rgb(55, 120, 200);
  border-color: rgb(55, 120, 200);
  color: white;
}

.dialog-btn-primary:hover {
  background: rgb(65, 140, 220);
}

.dialog-radio-group {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: rgb(156, 160, 164);
  cursor: pointer;
}

.dialog-spacer { flex: 1; }

.dialog-actions {
  padding-top: 8px;
  border-top: 1px solid rgb(55, 59, 68);
}
</style>
```

- [ ] **Step 2: Verify dialog renders**

Run: `pnpm dev` → trigger import dialog. Should show modal with path input, mode radio, size dropdown.

- [ ] **Step 3: Commit**

```bash
git add src/components/resource-panel/MapResourceImportDialog.vue
git commit -m "feat(map-editor): add map resource import dialog"
```

---

### Task 11: Map Upload Drawer

**Covers:** [S11]

**Files:**
- Create: `src/components/resource-panel/MapUploadDrawer.vue`

**Interfaces:**
- Produces: Emits `import-file`, `create-map`, `open-library`

- [ ] **Step 1: Create `src/components/resource-panel/MapUploadDrawer.vue`**

```vue
<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  'import-file': []
  'create-map': []
  'open-library': []
}>()

const menuVisible = ref(false)
let hideTimeout: ReturnType<typeof setTimeout> | null = null

function onMouseEnter() {
  if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null }
  menuVisible.value = true
}

function onMouseLeave() {
  hideTimeout = setTimeout(() => { menuVisible.value = false }, 200)
}

function onAction(action: string) {
  menuVisible.value = false
  if (action === 'import') emit('import-file')
  else if (action === 'create') emit('create-map')
  else if (action === 'library') emit('open-library')
}
</script>

<template>
  <div class="upload-drawer" @mouseenter="onMouseEnter" @mouseleave="onMouseLeave">
    <transition name="slide-up">
      <div v-show="menuVisible" class="drawer-menu">
        <button class="drawer-btn" @click="onAction('import')" title="从文件导入">
          <img src="../../assets/icons/icon--file-upload.svg" class="drawer-icon" />
        </button>
        <button class="drawer-btn" @click="onAction('create')" title="创建地图">
          <img src="../../assets/icons/编辑.svg" class="drawer-icon" />
        </button>
        <button class="drawer-btn" @click="onAction('library')" title="选择库文件">
          <img src="../../assets/icons/icon--select--sprite.svg" class="drawer-icon" />
        </button>
      </div>
    </transition>
    <button class="drawer-main-btn" @mouseenter="onMouseEnter">
      <img src="../../assets/icons/map_upload.svg" class="drawer-main-icon" />
    </button>
  </div>
</template>

<style scoped>
.upload-drawer {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 70px;
  height: 226px;
  z-index: 100;
}

.drawer-menu {
  position: absolute;
  bottom: 50px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px;
}

.drawer-btn {
  width: 30px;
  height: 30px;
  background: #4B9B5C;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.drawer-btn:hover {
  background: #5bc772;
}

.drawer-icon {
  width: 20px;
  height: 20px;
}

.drawer-main-btn {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 50px;
  height: 50px;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.drawer-main-icon {
  width: 40px;
  height: 40px;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(20px);
}
</style>
```

- [ ] **Step 2: Verify drawer renders**

Run: `pnpm dev` → bottom-right corner should show upload button. Hover to expand menu.

- [ ] **Step 3: Commit**

```bash
git add src/components/resource-panel/MapUploadDrawer.vue
git commit -m "feat(map-editor): add map upload drawer with slide-up animation"
```

---

### Task 12: Wire Up MainLayout Integration

**Covers:** [S4], [S9], [S10], [S11]

**Files:**
- Modify: `src/components/layout/MainLayout.vue`

**Interfaces:**
- Consumes: MapLibraryPage, MapResourceLibPage, MapUploadDrawer
- Produces: Page navigation (currentPage) for map pages

- [ ] **Step 1: Add imports and page navigation to MainLayout.vue**

Add these imports near the top of `<script setup>`:

```typescript
import MapLibraryPage from '../resource-panel/MapLibraryPage.vue'
import MapResourceLibPage from '../resource-panel/MapResourceLibPage.vue'
import MapUploadDrawer from '../resource-panel/MapUploadDrawer.vue'
```

- [ ] **Step 2: Add page 2 (map library) content**

Replace the empty map library placeholder (around line 687-698):

```vue
<!-- ─── page 2: 地图库 ─── -->
<div v-show="currentPage === 2" class="lib-page">
  <MapLibraryPage @close="switchPage(0)" @imported="onMapLibImported" />
</div>
```

Add the handler:

```typescript
function onMapLibImported(path: string) {
  currentPage.value = 0
  editorStore.setActiveEditorMode('map')
}
```

- [ ] **Step 3: Add page 4 (resource library) content**

Replace the empty resource library placeholder (around line 706-718):

```vue
<!-- ─── page 4: 素材库 ─── -->
<div v-show="currentPage === 4" class="lib-page">
  <MapResourceLibPage @close="switchPage(0)" @imported="onResLibImported" />
</div>
```

Add the handler:

```typescript
function onResLibImported(path: string) {
  currentPage.value = 0
  editorStore.setActiveEditorMode('map')
}
```

- [ ] **Step 4: Update `onOpenLibrary` to handle map pages**

Replace the existing `onOpenLibrary` function:

```typescript
function onOpenLibrary(type: string) {
  if (type === 'sprite') {
    currentPage.value = 3  // sprite_lib page
  } else if (type === 'map') {
    currentPage.value = 2  // map_lib page
  }
}
```

- [ ] **Step 5: Update map tab in sidebar to open map library**

In the sidebar map tab section, add a button to open the map library:

```vue
<div v-else-if="editorStore.resourceTab === 'map'" class="resource-grid" @click="closeSpriteContextMenus">
  <div
    v-for="item in resourceStore.maps"
    :key="item.id"
    class="resource-grid-item"
    :class="{ 'resource-grid-item-active': selectedResource === item.id }"
    @click="selectedResource = item.id"
    @dblclick="openResource(item)"
  >
    <div class="resource-thumb resource-thumb-map"><span>{{ item.name.charAt(0) }}</span></div>
    <span class="resource-grid-name">{{ item.name }}</span>
  </div>
  <div v-if="resourceStore.maps.length === 0" class="resource-empty"></div>
</div>
```

- [ ] **Step 6: Verify integration**

Run: `pnpm dev`:
1. Switch to game mode → click 地图 tab → should show map editor
2. Click "场景" tab in sidebar → upload drawer should work
3. Navigate to map library (page 2) → should show MapLibraryPage
4. Navigate to resource library (page 4) → should show MapResourceLibPage with tabs

- [ ] **Step 7: Commit**

```bash
git add src/components/layout/MainLayout.vue
git commit -m "feat(map-editor): wire up map pages and upload drawer in MainLayout"
```

---

### Task 13: Collision Editor (Left Panel Bottom)

**Covers:** [S6]

**Files:**
- Create: `src/components/map-editor/CollisionEditor.vue`

**Interfaces:**
- Consumes: `useMapStore` (selectedResourceIndex, selectedTileIndex)
- Produces: Collision shape editing capabilities

- [ ] **Step 1: Create `src/components/map-editor/CollisionEditor.vue`**

```vue
<script setup lang="ts">
import { useMapStore } from '../../stores/map'

const mapStore = useMapStore()

type CollisionTool = 'move' | 'add' | 'delete' | 'reset'
const currentCollisionTool = ref<CollisionTool>('move')
const snapToPixel = ref(true)

function setCollisionTool(tool: CollisionTool) {
  currentCollisionTool.value = tool
}
</script>

<template>
  <div class="collision-editor">
    <div class="col-toolbar">
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': currentCollisionTool === 'move' }"
        title="移动锚点"
        @click="setCollisionTool('move')"
      >
        <img src="../../assets/icons/移动锚点.svg" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': currentCollisionTool === 'add' }"
        title="添加锚点"
        @click="setCollisionTool('add')"
      >
        <img src="../../assets/icons/添加锚点.svg" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': currentCollisionTool === 'delete' }"
        title="删除锚点"
        @click="setCollisionTool('delete')"
      >
        <img src="../../assets/icons/删除锚点.svg" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        title="重置锚点"
        @click="setCollisionTool('reset')"
      >
        <img src="../../assets/icons/重置锚点.svg" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': snapToPixel }"
        title="吸附锚点"
        @click="snapToPixel = !snapToPixel"
      >
        <img src="../../assets/icons/吸附锚点.svg" class="col-tool-icon" />
      </button>
    </div>

    <div class="col-canvas">
      <div v-if="mapStore.selectedTileIndex >= 0" class="col-placeholder">
        选择瓦片编辑碰撞
      </div>
      <div v-else class="col-placeholder">
        选择瓦片编辑碰撞
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
</script>

<style scoped>
.collision-editor {
  display: flex;
  flex-direction: column;
}

.col-toolbar {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 4px;
  gap: 2px;
}

.col-tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 24px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  padding: 2px;
  transition: background 0.15s;
}

.col-tool-btn:hover {
  background: rgb(61, 64, 72);
}

.col-tool-active {
  background: rgb(46, 49, 58);
  border: 1px solid rgb(55, 59, 68);
}

.col-tool-icon {
  width: 20px;
  height: 20px;
}

.col-canvas {
  width: 256px;
  height: 256px;
  background: rgb(30, 30, 30);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}

.col-placeholder {
  font-size: 12px;
  color: rgb(80, 80, 80);
}
</style>
```

- [ ] **Step 2: Integrate CollisionEditor into ResourceListPanel**

In `src/components/map-editor/ResourceListPanel.vue`, add the collision editor below the resource list:

```vue
<script setup lang="ts">
import { useMapStore } from '../../stores/map'
import CollisionEditor from './CollisionEditor.vue'

// ... existing code
</script>

<template>
  <div class="resource-list-panel">
    <!-- ... existing toolbar and list ... -->

    <CollisionEditor />

    <div class="res-info-bar">
      <!-- ... existing info bar ... -->
    </div>
  </div>
</template>
```

- [ ] **Step 3: Verify collision editor renders**

Run: `pnpm dev` → left panel should show collision toolbar and 256×256 canvas area below resource list.

- [ ] **Step 4: Commit**

```bash
git add src/components/map-editor/CollisionEditor.vue src/components/map-editor/ResourceListPanel.vue
git commit -m "feat(map-editor): add collision editor with tool buttons"
```

---

### Task 14: Final Polish & Styling Consistency

**Covers:** [S13], [S14]

**Files:**
- Modify: `src/components/map-editor/MapEditorView.vue`
- Modify: `src/components/map-editor/MapCanvas.vue`
- Modify: `src/components/map-editor/ResourceListPanel.vue`

**Interfaces:**
- Ensures all colors match original QSS exactly
- Ensures all panels have correct borders and backgrounds

- [ ] **Step 1: Verify all color values match AGENTS.md reference**

Check each component uses:
- Background: `rgb(34, 37, 43)` / `#22252B`
- Editor area: `rgb(41, 44, 52)` / `#292C34`
- Canvas: `rgb(30, 30, 30)` / `#1e1e1e`
- Border: `rgb(12, 12, 12)` / `#0C0C0C`
- Hover: `rgb(61, 64, 72)` / `#3D4048`
- Active: `rgb(91, 199, 114)` / `#5BC772`
- Input bg: `rgb(40, 43, 52)`
- Input border: `rgb(55, 59, 68)`
- Focus: `#528bff`
- Label: `rgb(156, 160, 164)` / `#9ca0a4`

- [ ] **Step 2: Verify all panels have correct dimensions**

- Left panel: 256px wide
- Right panel: 256px wide
- Canvas: flex fill
- Toolbar: 30px height
- Info bars: 30px height

- [ ] **Step 3: Run final visual check**

Run: `pnpm dev` → complete visual inspection of all map editor components.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(map-editor): final styling polish and dimension fixes"
```

---

## Summary

| Task | Description | Covers |
|------|-------------|--------|
| 1 | Extend Map Store | S12, S4 |
| 2 | Map Canvas (PixiJS) | S5 |
| 3 | Map Toolbar | S4, S5 |
| 4 | Resource List Panel | S6 |
| 5 | Property Panel | S7 |
| 6 | Layer Panel | S8 |
| 7 | MapEditorView Assembly | S4, S13 |
| 8 | Map Library Page | S9 |
| 9 | Map Resource Library Page | S10 |
| 10 | Map Resource Import Dialog | S11 |
| 11 | Map Upload Drawer | S11 |
| 12 | MainLayout Integration | S4, S9, S10, S11 |
| 13 | Collision Editor | S6 |
| 14 | Final Polish | S13, S14 |

**Total: 14 tasks**
