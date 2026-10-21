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
  firstgid: number
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
  collisionShape?: { points: number[][] }
  tileSetIndex: number
}

export interface MapData {
  name: string
  version: number
  width: number
  height: number
  tileSize: number
  gravity: boolean
  collisionType: string
  collisionEnabled: boolean
  layers: MapLayer[]
  tileSets: TileSet[]
  layerResourcesMap?: Record<number, number[]>
}

export type MapTool = 'move' | 'select' | 'draw' | 'erase' | 'fill'
export type CollisionTool = 'move' | 'add' | 'delete' | 'reset'
// 图像模式碰撞编辑工具（none = 未进入碰撞编辑）
export type ImageCollisionTool = 'none' | 'rect' | 'polygon' | 'vertex'

export const useMapStore = defineStore('map', () => {
  const currentMapPath = ref('')
  const mapData = ref<MapData>({
    name: '未命名地图',
    version: 5,
    width: 40,
    height: 30,
    tileSize: 16,
    gravity: false,
    collisionType: '图像',
    collisionEnabled: false,
    layers: [
      {
        id: 0,
        name: '图像图层',
        type: 'image',
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
  const snapToGrid = ref(true)
  const currentTool = ref<MapTool>('select')
  const selectedResourceIndex = ref(-1)
  const selectedTileIndex = ref(-1)
  const mapResources = ref<MapResource[]>([])
  const layerResources = ref<Record<number, MapResource[]>>({})
  const collisionTool = ref<CollisionTool>('move')
  const snapToPixel = ref(true)
  const cursorX = ref<number | null>(null)
  const cursorY = ref<number | null>(null)

  // 图像实例选中状态（画布选中图像后，属性面板/工具栏共用）
  const selectedImageLayerId = ref(-1)
  const selectedImageIndex = ref(-1)
  const imageCollisionTool = ref<ImageCollisionTool>('none')
  // 全局显示所有图像碰撞形状（调试用）
  const showCollision = ref(false)

  // Revision counters for cheap watcher dependency tracking (avoid expensive JSON.stringify in watcher getters)
  const tileRevision = ref(0)
  const imageRevision = ref(0)
  // 碰撞数据变更计数器（只触发叠加层重绘，不触发整图重渲染）
  const collisionRevision = ref(0)
  // 完整地图加载计数器（loadMap 时递增，用于 ResourceListPanel 刷新缩略图）
  const mapLoadCount = ref(0)

  const activeLayer = computed(() => {
    const layer = mapData.value.layers[activeLayerIndex.value] ?? null
    return layer
  })
  const selectedResource = computed(() => activeLayer.value?.resources[selectedResourceIndex.value] ?? null)
  // 画布上选中的图像实例
  const selectedImage = computed<ImageData | null>(() => {
    if (selectedImageLayerId.value < 0 || selectedImageIndex.value < 0) return null
    const layer = mapData.value.layers.find(l => l.id === selectedImageLayerId.value)
    return layer?.images[selectedImageIndex.value] ?? null
  })

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
    // 默认选中最上方的图层（数组最后一个）
    activeLayerIndex.value = Math.max(0, data.layers.length - 1)
    selectedResourceIndex.value = -1
    selectedTileIndex.value = -1
    clearImageSelection()
    syncToolWithLayer()
    // 强制触发 canvas 重新渲染（mapData 完全替换后所有瓦片和图像都变了）
    tileRevision.value++
    imageRevision.value++
    mapLoadCount.value++
  }

  function newMap() {
    mapData.value = {
      name: '未命名地图',
      version: 5,
      width: 40,
      height: 30,
      tileSize: 16,
      gravity: false,
      collisionType: '图像',
      collisionEnabled: false,
      layers: [
        {
          id: 0,
          name: '图像图层',
          type: 'image',
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
    clearImageSelection()
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
      // 自动扩展地图尺寸以容纳超出边界的砖块
      if (x + 1 > mapData.value.width) {
        mapData.value.width = x + 1
      }
      if (y + 1 > mapData.value.height) {
        mapData.value.height = y + 1
      }
    }
    tileRevision.value++
  }

  function getTile(x: number, y: number): number {
    const layer = activeLayer.value
    if (!layer || layer.type !== 'drawing') return 0
    return layer.tiles[`${x},${y}`] ?? 0
  }

  function addLayer(name: string, type: 'drawing' | 'image' = 'image') {
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
    syncToolWithLayer()
    return id
  }

  function removeLayer(index: number) {
    if (index >= 0 && index < mapData.value.layers.length && mapData.value.layers.length > 1) {
      const removed = mapData.value.layers[index]
      if (removed && removed.id === selectedImageLayerId.value) clearImageSelection()
      mapData.value.layers.splice(index, 1)
      if (activeLayerIndex.value >= mapData.value.layers.length) {
        activeLayerIndex.value = mapData.value.layers.length - 1
      }
      syncToolWithLayer()
    }
  }

  function moveLayerUp(index: number) {
    if (index < mapData.value.layers.length - 1) {
      const layers = mapData.value.layers
      const temp = layers[index]
      layers[index] = layers[index + 1]
      layers[index + 1] = temp
      activeLayerIndex.value = index + 1
      mapData.value.layers = [...layers]
      syncToolWithLayer()
    }
  }

  function moveLayerDown(index: number) {
    if (index > 0) {
      const layers = mapData.value.layers
      const temp = layers[index]
      layers[index] = layers[index - 1]
      layers[index - 1] = temp
      activeLayerIndex.value = index - 1
      mapData.value.layers = [...layers]
      syncToolWithLayer()
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

  // 根据当前选中图层类型设置默认工具和选中状态
  function syncToolWithLayer() {
    const idx = activeLayerIndex.value
    const layer = mapData.value.layers[idx]
    if (!layer) return
    if (layer.type === 'image') {
      currentTool.value = 'select'
    } else {
      currentTool.value = 'draw'
      if (layer.resources.length > 0) {
        selectedResourceIndex.value = 0
        selectedTileIndex.value = 0
      }
    }
  }

  function setActiveLayer(index: number) {
    activeLayerIndex.value = index
    selectedResourceIndex.value = -1
    selectedTileIndex.value = -1
    clearImageSelection()
    syncToolWithLayer()
  }

  function toggleGrid() {
    showGrid.value = !showGrid.value
  }

  function toggleSnapToGrid() {
    snapToGrid.value = !snapToGrid.value
  }

  function selectTile(resourceIndex: number, tileIndex: number) {
    selectedResourceIndex.value = resourceIndex
    selectedTileIndex.value = tileIndex
  }

  function addResource(resource: MapResource) {
    const layer = activeLayer.value
    if (!layer) return
    layer.resources.push(resource)
    // 分配firstgid（Tiled标准：每个瓦片集递增10000，避免冲突）
    const nextFirstgid = mapData.value.tileSets.length > 0
      ? Math.max(...mapData.value.tileSets.map(ts => ts.firstgid)) + 10000
      : 1
    mapData.value.tileSets.push({
      name: resource.name,
      imagePath: resource.path,
      resourceType: resource.resourceType,
      tileWidth: resource.tileWidth,
      tileHeight: resource.tileHeight,
      firstgid: nextFirstgid,
      collisionType: resource.collisionType,
      collisionEnabled: resource.collisionEnabled,
      tiles: [],
    })
  }

  function removeResource(index: number) {
    const layer = activeLayer.value
    if (!layer || index < 0 || index >= layer.resources.length) return

    // 先记录被删 tileset 的索引与 GID 范围，再移除；
    // 否则 splice 后同一索引已经指向下一个 tileset，清理范围会算错
    let globalIdx = 0
    for (const l of mapData.value.layers) {
      if (l.id === layer.id) break
      globalIdx += l.resources.length
    }
    globalIdx += index

    const removedTileSet = mapData.value.tileSets[globalIdx]
    const nextFirstgid = mapData.value.tileSets[globalIdx + 1]?.firstgid ?? Infinity

    layer.resources.splice(index, 1)
    if (globalIdx < mapData.value.tileSets.length) {
      mapData.value.tileSets.splice(globalIdx, 1)
    }

    // 清理所有图层中属于该 tileset 的瓦片（GID 编码）
    let tilesChanged = false
    if (removedTileSet) {
      for (const l of mapData.value.layers) {
        for (const key of Object.keys(l.tiles)) {
          const gid = l.tiles[key]
          if (gid >= removedTileSet.firstgid && gid < nextFirstgid) {
            delete l.tiles[key]
            tilesChanged = true
          }
        }
      }
    }
    // 瓦片被移除后必须通知画布重绘，否则残留的 sprite 不会消失
    if (tilesChanged) tileRevision.value++
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
      tileRevision.value++
    }
  }

  function updateMapProperty(key: keyof MapData, value: any) {
    ;(mapData.value as any)[key] = value
  }

  function updateTileSize(newSize: number) {
    mapData.value.tileSize = newSize
    for (const layer of mapData.value.layers) {
      for (const resource of layer.resources) {
        resource.tileWidth = newSize
        resource.tileHeight = newSize
      }
    }
    for (const ts of mapData.value.tileSets) {
      ts.tileWidth = newSize
      ts.tileHeight = newSize
    }
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

  // ====== 图像实例碰撞（图像模式） ======

  function selectImage(layerId: number, index: number) {
    selectedImageLayerId.value = layerId
    selectedImageIndex.value = index
  }

  function clearImageSelection() {
    selectedImageLayerId.value = -1
    selectedImageIndex.value = -1
    imageCollisionTool.value = 'none'
  }

  function setImageCollisionTool(tool: ImageCollisionTool) {
    imageCollisionTool.value = tool
  }

  function toggleShowCollision() {
    showCollision.value = !showCollision.value
  }

  // 默认碰撞形状：整张图片
  function defaultImageCollisionPoints(): number[][] {
    return [[0, 0], [1, 0], [1, 1], [0, 1]]
  }

  /** 设置选中图像实例的碰撞多边形（归一化 0~1 图片本地坐标）；传 null 清除 */
  function setImageCollisionPoints(points: number[][] | null) {
    const img = selectedImage.value
    if (!img) return
    if (!points || points.length < 3) {
      delete img.collisionShape
      img.collisionEnabled = false
    } else {
      img.collisionShape = { points }
      img.collisionEnabled = true
      if (!img.collisionType || img.collisionType === '图像') img.collisionType = '墙体'
    }
    collisionRevision.value++
  }

  function setImageCollisionType(type: string) {
    const img = selectedImage.value
    if (!img) return
    img.collisionType = type
    if (type === '图像') {
      img.collisionEnabled = false
    } else {
      img.collisionEnabled = true
      if (!img.collisionShape?.points?.length) {
        img.collisionShape = { points: defaultImageCollisionPoints() }
      }
    }
    collisionRevision.value++
  }

  function setImageCollisionEnabled(enabled: boolean) {
    const img = selectedImage.value
    if (!img) return
    img.collisionEnabled = enabled
    if (enabled) {
      if (!img.collisionType || img.collisionType === '图像') img.collisionType = '墙体'
      if (!img.collisionShape?.points?.length) {
        img.collisionShape = { points: defaultImageCollisionPoints() }
      }
    }
    collisionRevision.value++
  }

  function clearImageCollision() {
    const img = selectedImage.value
    if (!img) return
    delete img.collisionShape
    img.collisionEnabled = false
    collisionRevision.value++
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

  function setTileCollisionType(tileSetIndex: number, tileIndex: number, collisionType: string) {
    const tileSet = mapData.value.tileSets[tileSetIndex]
    if (!tileSet) return
    while (tileSet.tiles.length <= tileIndex) {
      tileSet.tiles.push({
        collision: false,
        tag: '',
        collisionType: '图像',
      })
    }
    tileSet.tiles[tileIndex].collisionType = collisionType
    tileSet.tiles[tileIndex].collision = collisionType !== '图像'
  }

  return {
    currentMapPath,
    mapData,
    activeLayerIndex,
    showGrid,
    snapToGrid,
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
    toggleSnapToGrid,
    selectTile,
    addResource,
    removeResource,
    clearResources,
    updateMapProperty,
    updateTileSize,
    setTileCollision,
    setTileCollisionType,
    setCollisionTool,
    toggleSnapToPixel,
    setCursorPos,
    selectedImageLayerId,
    selectedImageIndex,
    selectedImage,
    imageCollisionTool,
    showCollision,
    selectImage,
    clearImageSelection,
    setImageCollisionTool,
    toggleShowCollision,
    setImageCollisionPoints,
    setImageCollisionType,
    setImageCollisionEnabled,
    clearImageCollision,
    tileRevision,
    imageRevision,
    collisionRevision,
    mapLoadCount,
  }
})
