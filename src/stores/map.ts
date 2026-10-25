import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useMapEditorStore } from './mapEditor'
import { setUserOriginY } from '../utils/coords'

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
  // 扁平模型：一张图片就是一个图层，不再有"图像图层"容器
  image: ImageData
}

/** 碰撞层里的一个世界坐标碰撞体 */
export interface CollisionPolygon {
  id: string
  shape: 'rect' | 'circle' | 'capsule' | 'polygon'
  // 地图世界坐标（像素）
  points: number[][]
  // 物理属性：墙体 / 跳板 / 自定义
  collisionType: string
  // 禁用：勾选后该碰撞体不参与物理判定
  disabled?: boolean
}

/** 碰撞层：整层共享一组世界坐标碰撞多边形，与图像/图块解耦 */
export interface CollisionLayer extends MapLayerBase {
  type: 'collision'
  polygons: CollisionPolygon[]
}

export type MapLayer = DrawingLayer | ImageLayer | CollisionLayer

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
  // 旧存档兼容：图片实例碰撞，加载时会自动迁移为碰撞层
  collisions?: { id?: string; shape?: 'rect' | 'polygon'; points: number[][] }[]
  collisionShape?: { points: number[][] }
  // 整张画布背景图：随地图尺寸变化自动扩展绘制范围
  background?: boolean
  // 矢量图层：Paper.js project JSON（存在时可重新进入矢量编辑）
  vectorData?: string
  // 矢量图层的位图底稿（不含矢量内容，重新编辑时作为 base）
  vectorBasePath?: string
  // 该图层当前的编辑模式：切换图层时按此恢复（缺省时由是否有矢量数据推导）
  paintMode?: 'bitmap' | 'vector'
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

/** 地图相机设置（运行时由引擎读取；参考 Godot/Unity 2D 相机的常用项，保持精简） */
export interface CameraSettings {
  /** 是否启用相机跟随（开启后自动跟随 1 号角色） */
  enabled: boolean
  /** 跟随目标：空=自动（1 号角色），否则为用户代码里的角色变量名 */
  target: string
  /** 相机相对目标的偏移（世界像素） */
  offsetX: number
  offsetY: number
  /** 平滑跟随系数 0~1：0=立即对准，越大越"追不上" */
  smoothing: number
  /** 是否把相机限制在地图世界边界内 */
  limitBounds: boolean
}

export const DEFAULT_CAMERA_SETTINGS: CameraSettings = {
  enabled: false,
  target: '',
  offsetX: 0,
  offsetY: 0,
  smoothing: 0,
  limitBounds: true,
}

export interface MapData {
  name: string
  version: number
  width: number
  height: number
  tileSize: number
  gravity: boolean
  /** 边界碰撞：勾选后角色被地图矩形（地图尺寸）挡住，不能离开可玩区域 */
  boundaryCollision: boolean
  /** 禁止下滑：勾选后角色站在斜坡上不会下滑（默认开启） */
  stopOnSlope: boolean
  collisionType: string
  collisionEnabled: boolean
  // 地图级素材库：图层只引用素材，不再各自持有一份
  resources: MapResource[]
  layers: MapLayer[]
  tileSets: TileSet[]
  // 图块笔刷调色板：每个图块一个独立条目（顺序=界面显示顺序），缺省时由资源自动生成
  tilePalette?: TilePaletteEntry[]
  // 相机设置（缺省视为未启用）
  camera?: CameraSettings
}

export interface TilePaletteEntry {
  resourceId: string
  tileIndex: number
}

export type MapTool = 'move' | 'select' | 'draw' | 'erase' | 'fill'
export type CollisionTool = 'move' | 'add' | 'delete' | 'reset'
// 碰撞层编辑工具：select=选择/拖动，rect/circle/capsule/polygon=形状，addPoint/deletePoint=锚点增删
export type CollisionLayerTool = 'select' | 'rect' | 'circle' | 'capsule' | 'polygon' | 'addPoint' | 'deletePoint'

export const useMapStore = defineStore('map', () => {
  const currentMapPath = ref('')
  const mapData = ref<MapData>({
    name: '未命名地图',
    version: 5,
    width: 40,
    height: 30,
    tileSize: 16,
    gravity: false,
    boundaryCollision: false,
    stopOnSlope: true,
    collisionType: '图像',
    collisionEnabled: false,
    resources: [],
    layers: [],
    tileSets: [],
  })

  // 用户坐标原点 = 地图底部：地图加载 / 改宽高 / 改图块尺寸时同步
  watch(
    () => ({ height: mapData.value.height, tileSize: mapData.value.tileSize }),
    ({ height, tileSize }) => setUserOriginY(Math.max(1, height * tileSize)),
    { immediate: true, flush: 'sync' },
  )

  const mapEditor = useMapEditorStore()
  const activeLayerIndex = ref(-1)
  const selectedResourceIndex = ref(-1)
  const selectedTileIndex = ref(-1)

  // 图像实例选中状态（画布选中图像后，属性面板/工具栏共用）
  const selectedImageLayerId = ref(-1)

  // Revision counters for cheap watcher dependency tracking (avoid expensive JSON.stringify in watcher getters)
  const tileRevision = ref(0)
  const imageRevision = ref(0)
  // 碰撞数据变更计数器（只触发叠加层重绘，不触发整图重渲染）
  const collisionRevision = ref(0)
  // 完整地图加载计数器（loadMap 时递增，用于素材面板/图层缩略图刷新）
  const mapLoadCount = ref(0)

  const activeLayer = computed(() => {
    const layer = mapData.value.layers[activeLayerIndex.value] ?? null
    return layer
  })
  // 当前工作模式：由选中图层类型决定；空地图默认图像模式
  const activeMode = computed<'image' | 'tile' | 'collision'>(() => {
    const type = activeLayer.value?.type
    return type === 'drawing' ? 'tile' : type === 'collision' ? 'collision' : 'image'
  })
  // 当前模式可用的素材：图像模式只看图像素材，图块模式看瓦片素材，碰撞层不需要素材
  const activeLayerResources = computed(() => {
    if (activeMode.value === 'collision') return []
    const wantImage = activeMode.value === 'image'
    return mapData.value.resources.filter(r => (r.resourceType === 'image') === wantImage)
  })
  const selectedResource = computed(() => activeLayerResources.value[selectedResourceIndex.value] ?? null)
  // 画布上选中的图像实例（扁平模型下一层即一张图）
  const selectedImage = computed<ImageData | null>(() => {
    if (selectedImageLayerId.value < 0) return null
    const layer = mapData.value.layers.find(l => l.id === selectedImageLayerId.value)
    if (!layer || layer.type !== 'image') return null
    return layer.image
  })

  // 当前激活的碰撞层及其碰撞体
  const activeCollisionLayer = computed<CollisionLayer | null>(() =>
    activeLayer.value?.type === 'collision' ? activeLayer.value : null
  )
  const activeCollisionPolygons = computed<CollisionPolygon[]>(() =>
    activeCollisionLayer.value?.polygons ?? []
  )
  const activeCollisionPolygon = computed<CollisionPolygon | null>(() => {
    const list = activeCollisionPolygons.value
    const id = mapEditor.activeCollisionPolygonId
    return list.find(p => p.id === id) ?? null
  })

  /**
   * 场景级渲染模式（自动判定，忽略全局渲染设置）：
   * - 存在图块图层 → pixelated：图块是像素素材，整张画布必须最近邻
   * - 存在位图图片图层 → pixelated：整张画布按位图模式渲染
   * - 全部为矢量图层 → smooth：按矢量渲染
   */
  const sceneRenderMode = computed<'smooth' | 'pixelated'>(() => {
    const layers = mapData.value.layers
    if (layers.some(l => l.type === 'drawing')) return 'pixelated'
    const hasBitmapImage = layers.some(l => l.type === 'image' && !l.image.vectorData)
    return hasBitmapImage ? 'pixelated' : 'smooth'
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
    activeLayerIndex.value = data.layers.length > 0 ? data.layers.length - 1 : -1
    selectedResourceIndex.value = -1
    selectedTileIndex.value = -1
    syncToolWithLayer()
    // 图片图层保留选中实例：打开地图后属性/碰撞可直接生效（变换框仍需用户主动点选才出现）；
    // 图块/碰撞图层则清空图片选中态
    if (data.layers[activeLayerIndex.value]?.type !== 'image') {
      clearImageSelection()
    }
    mapEditor.setActiveCollisionPolygonId(null)
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
      boundaryCollision: false,
      stopOnSlope: true,
      collisionType: '图像',
      collisionEnabled: false,
      resources: [],
      layers: [],
      tileSets: [],
    }
    activeLayerIndex.value = -1
    selectedResourceIndex.value = -1
    selectedTileIndex.value = -1
    clearImageSelection()
    syncToolWithLayer()
    currentMapPath.value = ''
    // 强制画布重建：否则清空后 Pixi 仍保留上一张地图的渲染结果
    tileRevision.value++
    imageRevision.value++
    mapLoadCount.value++
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

  function addLayer(name: string): number {
    const id = mapData.value.layers.length > 0
      ? Math.max(...mapData.value.layers.map(l => l.id)) + 1
      : 0
    const newLayer: MapLayer = { id, name, type: 'drawing', visible: true, locked: false, tiles: {} }
    mapData.value.layers.push(newLayer)
    activeLayerIndex.value = mapData.value.layers.length - 1
    syncToolWithLayer()
    return id
  }

  // 新建图片图层（扁平模型：一张图一层），默认放在最上层并选中
  function addImageLayer(name: string, image: ImageData): number {
    const id = mapData.value.layers.length > 0
      ? Math.max(...mapData.value.layers.map(l => l.id)) + 1
      : 0
    const newLayer: ImageLayer = {
      id, name: name || '图像图层', type: 'image', visible: true, locked: false, image,
    }
    mapData.value.layers.push(newLayer)
    activeLayerIndex.value = mapData.value.layers.length - 1
    selectedImageLayerId.value = id
    selectedResourceIndex.value = -1
    selectedTileIndex.value = -1
    imageRevision.value++
    syncToolWithLayer()
    return id
  }

  function removeLayer(index: number) {
    if (index < 0 || index >= mapData.value.layers.length) return
    const removed = mapData.value.layers[index]
    if (removed && removed.id === selectedImageLayerId.value) clearImageSelection()
    mapData.value.layers.splice(index, 1)
    if (mapData.value.layers.length === 0) {
      activeLayerIndex.value = -1
    } else if (activeLayerIndex.value >= mapData.value.layers.length) {
      activeLayerIndex.value = mapData.value.layers.length - 1
    }
    syncToolWithLayer()
    imageRevision.value++
  }

  function moveLayerUp(index: number) {
    if (index < 0) return
    if (index < mapData.value.layers.length - 1) {
      const layers = mapData.value.layers
      const temp = layers[index]
      layers[index] = layers[index + 1]
      layers[index + 1] = temp
      activeLayerIndex.value = index + 1
      mapData.value.layers = [...layers]
      tileRevision.value++
      imageRevision.value++
      syncToolWithLayer()
    }
  }

  function moveLayerDown(index: number) {
    if (index < 0) return
    if (index > 0) {
      const layers = mapData.value.layers
      const temp = layers[index]
      layers[index] = layers[index - 1]
      layers[index - 1] = temp
      activeLayerIndex.value = index - 1
      mapData.value.layers = [...layers]
      tileRevision.value++
      imageRevision.value++
      syncToolWithLayer()
    }
  }

  // 拖拽排序：把 from 位置的图层移动到 to 位置
  function moveLayerTo(from: number, to: number) {
    const layers = [...mapData.value.layers]
    if (from < 0 || from >= layers.length || to < 0 || to >= layers.length || from === to) return
    const activeId = layers[activeLayerIndex.value]?.id
    const [moved] = layers.splice(from, 1)
    layers.splice(to, 0, moved)
    mapData.value.layers = layers
    if (activeId !== undefined) {
      const newIdx = layers.findIndex(l => l.id === activeId)
      if (newIdx >= 0) activeLayerIndex.value = newIdx
    }
    tileRevision.value++
    imageRevision.value++
    syncToolWithLayer()
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
    if (!layer) {
      selectedResourceIndex.value = -1
      selectedTileIndex.value = -1
      selectedImageLayerId.value = -1
      mapEditor.setActiveCollisionPolygonId(null)
      return
    }
    if (layer.type === 'collision') {
      // 碰撞层：默认激活选择移动（形状按钮独立记忆，默认矩形常亮）
      mapEditor.setTool('select')
      mapEditor.setCollisionLayerTool('select')
      mapEditor.setActiveCollisionPolygonId(null)
      selectedImageLayerId.value = -1
      selectedResourceIndex.value = -1
      selectedTileIndex.value = -1
      return
    }
    mapEditor.setActiveCollisionPolygonId(null)
    if (layer.type === 'image') {
      mapEditor.setTool('select')
      // 扁平模型：选中图片图层即选中该张图片
      selectedImageLayerId.value = layer.id
      selectedResourceIndex.value = -1
      selectedTileIndex.value = -1
    } else {
      mapEditor.setTool('draw')
      selectedImageLayerId.value = -1
      const palette = mapData.value.tilePalette
      const first = palette?.find(e =>
        activeLayerResources.value.some(r => r.id === e.resourceId)
      )
      if (first) {
        const rIdx = activeLayerResources.value.findIndex(r => r.id === first.resourceId)
        selectedResourceIndex.value = rIdx
        selectedTileIndex.value = first.tileIndex
      } else if (!palette && activeLayerResources.value.length > 0) {
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

  function addResource(input: MapResourceInput): string {
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
    return resource.id
  }

  // ====== 图块笔刷调色板 ======
  function addPaletteEntries(entries: TilePaletteEntry[]) {
    if (entries.length === 0) return
    const existing = mapData.value.tilePalette ?? []
    const seen = new Set(existing.map(e => `${e.resourceId}:${e.tileIndex}`))
    const merged = [...existing]
    for (const e of entries) {
      const key = `${e.resourceId}:${e.tileIndex}`
      if (seen.has(key)) continue
      seen.add(key)
      merged.push({ resourceId: e.resourceId, tileIndex: e.tileIndex })
    }
    mapData.value.tilePalette = merged
  }

  function setTilePalette(entries: TilePaletteEntry[]) {
    mapData.value.tilePalette = entries.map(e => ({ resourceId: e.resourceId, tileIndex: e.tileIndex }))
  }

  function movePaletteEntry(from: number, to: number) {
    const arr = [...(mapData.value.tilePalette ?? [])]
    if (from < 0 || from >= arr.length) return
    const clamped = Math.max(0, Math.min(to, arr.length - 1))
    if (clamped === from) return
    const [item] = arr.splice(from, 1)
    arr.splice(clamped, 0, item)
    mapData.value.tilePalette = arr
  }

  function removePaletteEntry(index: number) {
    const arr = [...(mapData.value.tilePalette ?? [])]
    if (index < 0 || index >= arr.length) return
    const removed = arr[index]
    arr.splice(index, 1)
    mapData.value.tilePalette = arr
    // 当前选中的笔刷被移除时清空选择
    const rIdx = activeLayerResources.value.findIndex(r => r.id === removed.resourceId)
    if (rIdx === selectedResourceIndex.value && removed.tileIndex === selectedTileIndex.value) {
      selectedResourceIndex.value = -1
      selectedTileIndex.value = -1
    }
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
    // 移除该素材对应的图块笔刷
    mapData.value.tilePalette = (mapData.value.tilePalette ?? [])
      .filter(e => e.resourceId !== removedResource.id)
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
    // 移除对应图块笔刷
    mapData.value.tilePalette = (mapData.value.tilePalette ?? [])
      .filter(e => !removedIds.has(e.resourceId))
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

  /** 更新相机设置（合并默认值，缺省字段补齐） */
  function updateCameraSettings(patch: Partial<CameraSettings>) {
    mapData.value.camera = { ...DEFAULT_CAMERA_SETTINGS, ...(mapData.value.camera ?? {}), ...patch }
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

  // ====== 图层 / 图像选中 ======

  function selectImage(layerId: number) {
    selectedImageLayerId.value = layerId
  }

  function clearImageSelection() {
    selectedImageLayerId.value = -1
  }

  // ====== 碰撞层（世界坐标） ======

  function createCollisionId(): string {
    return `col_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
  }

  /** 新建碰撞层并选中 */
  function addCollisionLayer(name = '碰撞'): number {
    const layers = mapData.value.layers
    const id = layers.length > 0 ? Math.max(...layers.map(l => l.id)) + 1 : 0
    const used = new Set(layers.map(l => l.name))
    let finalName = name
    let seq = 2
    while (used.has(finalName)) finalName = `${name} ${seq++}`
    const layer: CollisionLayer = {
      id, name: finalName, type: 'collision', visible: true, locked: false, polygons: [],
    }
    layers.push(layer)
    activeLayerIndex.value = layers.length - 1
    selectedResourceIndex.value = -1
    selectedTileIndex.value = -1
    syncToolWithLayer()
    imageRevision.value++
    return id
  }

  /** 在当前碰撞层新增一个碰撞体并选中 */
  function addCollisionPolygon(shape: CollisionPolygon['shape'], points: number[][], collisionType = '墙体'): string | null {
    const layer = activeCollisionLayer.value
    if (!layer) return null
    const polygon: CollisionPolygon = {
      id: createCollisionId(),
      shape,
      points: points.map(p => [p[0], p[1]]),
      collisionType: collisionType || '墙体',
    }
    layer.polygons.push(polygon)
    mapEditor.setActiveCollisionPolygonId(polygon.id)
    collisionRevision.value++
    return polygon.id
  }

  function removeCollisionPolygon(id: string) {
    const layer = activeCollisionLayer.value
    if (!layer) return
    const idx = layer.polygons.findIndex(p => p.id === id)
    if (idx < 0) return
    layer.polygons.splice(idx, 1)
    if (mapEditor.activeCollisionPolygonId === id) {
      const next = layer.polygons[Math.min(idx, layer.polygons.length - 1)] ?? null
      mapEditor.setActiveCollisionPolygonId(next?.id ?? null)
    }
    collisionRevision.value++
  }

  /** 更新碰撞体顶点；不足 3 点视为删除 */
  function updateCollisionPolygonPoints(id: string, points: number[][] | null) {
    const layer = activeCollisionLayer.value
    if (!layer) return
    const polygon = layer.polygons.find(p => p.id === id)
    if (!polygon) return
    if (!points || points.length < 3) {
      removeCollisionPolygon(id)
      return
    }
    polygon.points = points.map(p => [p[0], p[1]])
    collisionRevision.value++
  }

  function setCollisionPolygonType(id: string, collisionType: string) {
    const layer = activeCollisionLayer.value
    if (!layer) return
    const polygon = layer.polygons.find(p => p.id === id)
    if (!polygon) return
    polygon.collisionType = collisionType
    collisionRevision.value++
  }

  /** 禁用/启用单个碰撞体（禁用后不参与物理判定） */
  function setCollisionPolygonDisabled(id: string, disabled: boolean) {
    const layer = activeCollisionLayer.value
    if (!layer) return
    const polygon = layer.polygons.find(p => p.id === id)
    if (!polygon) return
    polygon.disabled = disabled
    collisionRevision.value++
  }

  /** 在指定图层位置放置图片（绘制页保存返回时使用）：扁平模型下一张图一层 */
  function addImageAt(layerIndex: number, img: ImageData, name = '图片'): number {
    const layers = [...mapData.value.layers]
    const id = layers.length > 0 ? Math.max(...layers.map(l => l.id)) + 1 : 0
    const newLayer: ImageLayer = {
      id, name, type: 'image', visible: true, locked: false, image: img,
    }
    const insertAt = layerIndex >= 0
      ? Math.min(layerIndex + 1, layers.length)
      : layers.length
    layers.splice(insertAt, 0, newLayer)
    mapData.value.layers = layers
    activeLayerIndex.value = insertAt
    selectedImageLayerId.value = id
    imageRevision.value++
    syncToolWithLayer()
    return id
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
    activeMode,
    selectedResource,
    getTileSetForResource,
    tileSetIndexOfResource,
    setMapPath,
    loadMap,
    newMap,
    setTile,
    getTile,
    addLayer,
    addImageLayer,
    addImageAt,
    removeLayer,
    moveLayerUp,
    moveLayerDown,
    moveLayerTo,
    toggleLayerVisibility,
    toggleLayerLock,
    renameLayer,
    setActiveLayer,
    selectTile,
    addResource,
    addPaletteEntries,
    setTilePalette,
    movePaletteEntry,
    removePaletteEntry,
    removeResource,
    clearResources,
    updateMapProperty,
    updateCameraSettings,
    updateTileSize,
    setTileCollision,
    setTileCollisionType,
    selectedImageLayerId,
    selectedImage,
    activeCollisionLayer,
    activeCollisionPolygons,
    activeCollisionPolygon,
    sceneRenderMode,
    selectImage,
    clearImageSelection,
    addCollisionLayer,
    addCollisionPolygon,
    removeCollisionPolygon,
    updateCollisionPolygonPoints,
    setCollisionPolygonType,
    setCollisionPolygonDisabled,
    tileRevision,
    imageRevision,
    collisionRevision,
    mapLoadCount,
  }
})
