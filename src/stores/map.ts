import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useMapEditorStore } from './mapEditor'

export interface TileData {
  collision: boolean
  tag: string
  collisionType: string
  collisionShape?: { points: number[][] }
}

export interface TileSet {
  id: string
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

interface MapLayerBase {
  id: number
  name: string
  visible: boolean
  locked: boolean
}

export interface DrawingLayer extends MapLayerBase {
  type: 'drawing'
  tiles: Record<string, number>
}

export interface ImageLayer extends MapLayerBase {
  type: 'image'
  images: ImageData[]
}

export type MapLayer = DrawingLayer | ImageLayer

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
  // 稳定标识：创建时分配，删除/重排图层都不会改变
  id: string
  firstgid: number
  name: string
  path: string
  resourceType: string
  tileWidth: number
  tileHeight: number
  collisionType: string
  collisionEnabled: boolean
  collisionShape?: { points: number[][] }
}

// 新增素材时 id/firstgid 由 store 统一分配
export type MapResourceInput = Omit<MapResource, 'id' | 'firstgid'> &
  Partial<Pick<MapResource, 'id' | 'firstgid'>>

export interface MapData {
  name: string
  version: number
  width: number
  height: number
  tileSize: number
  gravity: boolean
  collisionType: string
  collisionEnabled: boolean
  // 地图级素材库：图层只引用素材，不再各自持有一份
  resources: MapResource[]
  layers: MapLayer[]
  tileSets: TileSet[]
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
    resources: [],
    layers: [
      {
        id: 0,
        name: '图像图层',
        type: 'image',
        visible: true,
        locked: false,
        images: [],
      },
    ],
    tileSets: [],
  })

  const mapEditor = useMapEditorStore()
  const activeLayerIndex = ref(0)
  const selectedResourceIndex = ref(-1)
  const selectedTileIndex = ref(-1)

  // 图像实例选中状态（画布选中图像后，属性面板/工具栏共用）
  const selectedImageLayerId = ref(-1)
  const selectedImageIndex = ref(-1)

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
  // 当前图层可用的素材：图像图层只看图像素材，绘制图层看瓦片素材
  const activeLayerResources = computed(() => {
    const layer = activeLayer.value
    if (!layer) return []
    const wantImage = layer.type === 'image'
    return mapData.value.resources.filter(r => (r.resourceType === 'image') === wantImage)
  })
  const selectedResource = computed(() => activeLayerResources.value[selectedResourceIndex.value] ?? null)
  // 画布上选中的图像实例
  const selectedImage = computed<ImageData | null>(() => {
    if (selectedImageLayerId.value < 0 || selectedImageIndex.value < 0) return null
    const layer = mapData.value.layers.find(l => l.id === selectedImageLayerId.value)
    if (!layer || layer.type !== 'image') return null
    return layer.images[selectedImageIndex.value] ?? null
  })

  // 素材与 tileset 通过稳定 id / firstgid 绑定，不再依赖图层顺序或全局偏移
  function getTileSetForResource(resource: MapResource | null): TileSet | null {
    if (!resource) return null
    const byId = resource.id
      ? mapData.value.tileSets.find(ts => ts.id === resource.id)
      : undefined
    if (byId) return byId
    return mapData.value.tileSets.find(ts => ts.firstgid === resource.firstgid)
      ?? mapData.value.tileSets.find(ts => ts.imagePath === resource.path && ts.name === resource.name)
      ?? mapData.value.tileSets.find(ts => ts.imagePath === resource.path)
      ?? null
  }

  function tileSetIndexOfResource(resource: MapResource | null): number {
    const tileSet = getTileSetForResource(resource)
    return tileSet ? mapData.value.tileSets.indexOf(tileSet) : -1
  }

  function createResourceId(): string {
    return `res_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
  }

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
      resources: [],
      layers: [
        {
          id: 0,
          name: '图像图层',
          type: 'image',
          visible: true,
          locked: false,
          images: [],
        },
      ],
      tileSets: [],
    }
    activeLayerIndex.value = 0
    selectedResourceIndex.value = -1
    selectedTileIndex.value = -1
    clearImageSelection()
    currentMapPath.value = ''
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
    const newLayer: MapLayer = type === 'drawing'
      ? { id, name, type, visible: true, locked: false, tiles: {} }
      : { id, name, type, visible: true, locked: false, images: [] }
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
      mapEditor.setTool('select')
      selectedResourceIndex.value = -1
      selectedTileIndex.value = -1
    } else {
      mapEditor.setTool('draw')
      if (activeLayerResources.value.length > 0) {
        selectedResourceIndex.value = 0
        selectedTileIndex.value = 0
      } else {
        selectedResourceIndex.value = -1
        selectedTileIndex.value = -1
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

  function selectTile(resourceIndex: number, tileIndex: number) {
    selectedResourceIndex.value = resourceIndex
    selectedTileIndex.value = tileIndex
  }

  function addResource(input: MapResourceInput) {
    // firstgid 只在创建时分配一次，之后不再随图层/素材顺序变化
    const nextFirstgid = mapData.value.tileSets.length > 0
      ? Math.max(...mapData.value.tileSets.map(ts => ts.firstgid)) + 10000
      : 1
    const resource: MapResource = {
      ...input,
      id: input.id || createResourceId(),
      firstgid: input.firstgid ?? nextFirstgid,
    }
    mapData.value.resources.push(resource)
    mapData.value.tileSets.push({
      id: resource.id,
      name: resource.name,
      imagePath: resource.path,
      resourceType: resource.resourceType,
      tileWidth: resource.tileWidth,
      tileHeight: resource.tileHeight,
      firstgid: resource.firstgid,
      collisionType: resource.collisionType,
      collisionEnabled: resource.collisionEnabled,
      tiles: [],
    })
  }

  function removeResource(index: number) {
    const removedResource = activeLayerResources.value[index]
    if (!removedResource) return
    const resourceIndex = mapData.value.resources.indexOf(removedResource)
    if (resourceIndex < 0) return

    const removedTileSet = getTileSetForResource(removedResource)
    // 下一个更大的 firstgid 决定该 tileset 的 GID 空间上界
    const higherGids = removedTileSet
      ? mapData.value.tileSets
          .map(ts => ts.firstgid)
          .filter(gid => gid > removedTileSet.firstgid)
      : []
    const nextFirstgid = higherGids.length > 0 ? Math.min(...higherGids) : Infinity

    mapData.value.resources.splice(resourceIndex, 1)
    if (removedTileSet) {
      const tileSetIndex = mapData.value.tileSets.indexOf(removedTileSet)
      if (tileSetIndex >= 0) mapData.value.tileSets.splice(tileSetIndex, 1)
    }

    // 清理所有图层中属于该 tileset 的瓦片（GID 编码）
    let tilesChanged = false
    if (removedTileSet) {
      for (const l of mapData.value.layers) {
        if (l.type !== 'drawing') continue
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

    // 选中的是过滤后的列表下标，删除后需要修正
    if (selectedResourceIndex.value === index) {
      selectedResourceIndex.value = -1
      selectedTileIndex.value = -1
    } else if (selectedResourceIndex.value > index) {
      selectedResourceIndex.value--
    }
  }

  function clearResources() {
    const layer = activeLayer.value
    if (!layer) return
    const removed = activeLayerResources.value
    const removedIds = new Set(removed.map(r => r.id))
    const removedFirstgids = new Set(removed.map(r => r.firstgid))
    // 从地图级素材库移除当前图层可见的素材
    mapData.value.resources = mapData.value.resources.filter(r => !removedIds.has(r.id))
    // 按素材自身的 id/firstgid 精确移除对应 tileset
    mapData.value.tileSets = mapData.value.tileSets.filter(
      ts => !removedIds.has(ts.id) && !removedFirstgids.has(ts.firstgid),
    )
    selectedResourceIndex.value = -1
    selectedTileIndex.value = -1
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
    for (const resource of mapData.value.resources) {
      resource.tileWidth = newSize
      resource.tileHeight = newSize
    }
    for (const ts of mapData.value.tileSets) {
      ts.tileWidth = newSize
      ts.tileHeight = newSize
    }
  }

  // ====== 图像实例碰撞（图像模式） ======

  function selectImage(layerId: number, index: number) {
    selectedImageLayerId.value = layerId
    selectedImageIndex.value = index
  }

  function clearImageSelection() {
    selectedImageLayerId.value = -1
    selectedImageIndex.value = -1
    mapEditor.setImageCollisionTool('none')
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

  /** 在指定图像图层放置图像实例并选中（绘制页保存返回时使用） */
  function addImageInstance(layerId: number, img: ImageData): number {
    const layer = mapData.value.layers.find(l => l.id === layerId)
    if (!layer || layer.type !== 'image') return -1
    layer.images.push(img)
    const index = layer.images.length - 1
    selectedImageLayerId.value = layerId
    selectedImageIndex.value = index
    imageRevision.value++
    return index
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
    selectedResourceIndex,
    selectedTileIndex,
    activeLayerResources,
    activeLayer,
    selectedResource,
    getTileSetForResource,
    tileSetIndexOfResource,
    setMapPath,
    loadMap,
    newMap,
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
    selectTile,
    addResource,
    removeResource,
    clearResources,
    updateMapProperty,
    updateTileSize,
    setTileCollision,
    setTileCollisionType,
    selectedImageLayerId,
    selectedImageIndex,
    selectedImage,
    selectImage,
    clearImageSelection,
    setImageCollisionPoints,
    setImageCollisionType,
    setImageCollisionEnabled,
    clearImageCollision,
    addImageInstance,
    tileRevision,
    imageRevision,
    collisionRevision,
    mapLoadCount,
  }
})
