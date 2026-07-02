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
  locked: boolean
  tiles: Record<string, number>
  resources: MapResource[]
  images: ImageData[]
}

export interface ImageData {
  imagePath: string
  position: [number, number]
  rotation: number
  scale: number
  scaleX: number
  scaleY: number
  opacity: number
  width: number
  height: number
  collisionType: string
  collisionEnabled: boolean
  collisionShape?: { points: number[][] }
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
  version: number
  width: number
  height: number
  tileSize: number
  offsetX: number
  offsetY: number
  gravity: boolean
  collisionType: string
  collisionEnabled: boolean
  layers: MapLayer[]
  tileSets: TileSet[]
  layerResourcesMap?: Record<number, number[]>
}

export type MapTool = 'move' | 'select' | 'draw' | 'erase' | 'fill'
export type CollisionTool = 'move' | 'add' | 'delete' | 'reset'

export const useMapStore = defineStore('map', () => {
  const currentMapPath = ref('')
  const mapData = ref<MapData>({
    name: '未命名地图',
    version: 5,
    width: 40,
    height: 30,
    tileSize: 16,
    offsetX: 0,
    offsetY: 0,
    gravity: false,
    collisionType: '图像',
    collisionEnabled: false,
    layers: [
      {
        id: 0,
        name: '图层',
        type: 'drawing',
        visible: true,
        locked: false,
        tiles: {},
        resources: [],
        images: [],
      },
    ],
    tileSets: [],
  })

  const activeLayerIndex = ref(0)
  const showGrid = ref(true)
  const currentTool = ref<MapTool>('select')
  const selectedResourceIndex = ref(-1)
  const selectedTileIndex = ref(-1)
  const mapResources = ref<MapResource[]>([])
  const layerResources = ref<Record<number, MapResource[]>>({})
  const collisionTool = ref<CollisionTool>('move')
  const snapToPixel = ref(true)
  const cursorX = ref<number | null>(null)
  const cursorY = ref<number | null>(null)

  // Revision counters for cheap watcher dependency tracking (avoid expensive JSON.stringify in watcher getters)
  const tileRevision = ref(0)
  const imageRevision = ref(0)

  const activeLayer = computed(() => {
    const layer = mapData.value.layers[activeLayerIndex.value] ?? null
    return layer
  })
  const selectedResource = computed(() => activeLayer.value?.resources[selectedResourceIndex.value] ?? null)

  // 计算当前图层资源在全局 tileSets 中的起始索引
  const globalResourceOffset = computed(() => {
    let offset = 0
    for (const l of mapData.value.layers) {
      if (l.id === activeLayer.value?.id) break
      offset += l.resources.length
    }
    return offset
  })

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
      version: 5,
      width: 40,
      height: 30,
      tileSize: 16,
      offsetX: 0,
      offsetY: 0,
      gravity: false,
      collisionType: '图像',
      collisionEnabled: false,
      layers: [
        {
          id: 0,
          name: '图层',
          type: 'drawing',
          visible: true,
        locked: false,
          tiles: {},
          resources: [],
          images: [],
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
    if (!layer || layer.type !== 'drawing' || layer.locked) return
    const key = `${x},${y}`
    if (tileId === 0) {
      delete layer.tiles[key]
    } else {
      layer.tiles[key] = tileId
    }
    tileRevision.value++
  }

  function getTile(x: number, y: number): number {
    const layer = activeLayer.value
    if (!layer || layer.type !== 'drawing') return 0
    return layer.tiles[`${x},${y}`] ?? 0
  }

  function addLayer(name: string, type: 'drawing' | 'image' = 'drawing') {
    const id = mapData.value.layers.length > 0
      ? Math.max(...mapData.value.layers.map(l => l.id)) + 1
      : 0
    const newLayer = {
      id,
      name,
      type,
      visible: true,
      locked: false,
      tiles: {},
      resources: [],
      images: [],
    }
    mapData.value.layers.push(newLayer)
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
      const layers = mapData.value.layers
      const temp = layers[index]
      layers[index] = layers[index + 1]
      layers[index + 1] = temp
      activeLayerIndex.value = index + 1
      // 触发响应式更新
      mapData.value.layers = [...layers]
    }
  }

  function moveLayerDown(index: number) {
    if (index > 0) {
      const layers = mapData.value.layers
      const temp = layers[index]
      layers[index] = layers[index - 1]
      layers[index - 1] = temp
      activeLayerIndex.value = index - 1
      // 触发响应式更新
      mapData.value.layers = [...layers]
    }
  }

  function toggleLayerVisibility(index: number) {
    const layer = mapData.value.layers[index]
    if (layer) layer.visible = !layer.visible
  }

  function toggleLayerLock(index: number) {
    const layer = mapData.value.layers[index]
    if (layer) layer.locked = !layer.locked
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
    const layer = activeLayer.value
    if (!layer) return
    layer.resources.push(resource)
    // 同时创建对应的 TileSet 以支持碰撞数据
    mapData.value.tileSets.push({
      name: resource.name,
      imagePath: resource.path,
      resourceType: resource.resourceType,
      tileWidth: resource.tileWidth,
      tileHeight: resource.tileHeight,
      collisionType: resource.collisionType,
      collisionEnabled: resource.collisionEnabled,
      tiles: [],
    })
  }

  function removeResource(index: number) {
    const layer = activeLayer.value
    if (!layer || index < 0 || index >= layer.resources.length) return
    const removedResource = layer.resources[index]
    layer.resources.splice(index, 1)
    // 移除对应的 TileSet
    let globalIdx = 0
    for (const l of mapData.value.layers) {
      if (l.id === layer.id) break
      globalIdx += l.resources.length
    }
    globalIdx += index
    if (globalIdx < mapData.value.tileSets.length) {
      mapData.value.tileSets.splice(globalIdx, 1)
    }
    // 清理画布上的相关瓦片
    if (removedResource) {
      for (const l of mapData.value.layers) {
        for (const key of Object.keys(l.tiles)) {
          const tileId = l.tiles[key]
          const resIdx = Math.floor(tileId / 1000) - 1
          if (resIdx === globalIdx) {
            delete l.tiles[key]
          }
        }
      }
    }
  }

  function clearResources() {
    const layer = activeLayer.value
    if (!layer) return
    let startIdx = 0
    for (const l of mapData.value.layers) {
      if (l.id === layer.id) break
      startIdx += l.resources.length
    }
    const count = layer.resources.length
    mapData.value.tileSets.splice(startIdx, count)
    layer.resources = []
    // 清空该图层的所有瓦片
    if (layer.type === 'drawing') {
      layer.tiles = {}
    }
  }

  function updateMapProperty(key: keyof MapData, value: any) {
    ;(mapData.value as any)[key] = value
  }

  function setCollisionTool(tool: CollisionTool) {
    collisionTool.value = tool
  }

  function toggleSnapToPixel() {
    snapToPixel.value = !snapToPixel.value
  }

  function setCursorPos(x: number | null, y: number | null) {
    cursorX.value = x
    cursorY.value = y
  }

  function setTileCollision(tileSetIndex: number, tileIndex: number, collision: boolean) {
    const tileSet = mapData.value.tileSets[tileSetIndex]
    if (!tileSet) return
    while (tileSet.tiles.length <= tileIndex) {
      tileSet.tiles.push({
        collision: false,
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
    collisionTool,
    snapToPixel,
    cursorX,
    cursorY,
    activeLayer,
    selectedResource,
    globalResourceOffset,
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
    toggleLayerLock,
    renameLayer,
    setActiveLayer,
    toggleGrid,
    selectTile,
    addResource,
    removeResource,
    clearResources,
    updateMapProperty,
    setTileCollision,
    setCollisionTool,
    toggleSnapToPixel,
    setCursorPos,
    tileRevision,
    imageRevision,
  }
})
