import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useMapEditorStore } from './mapEditor'
import { setUserOriginY } from '../utils/coords'

export interface TileData {
  collision: boolean
  tag: string
  collisionType: string
  collisionShape?: { points: number[][] }
  /** 作用：碰撞 / 感应 / 碰撞 + 感应（缺省视为碰撞） */
  kind?: ShapeKind
  /** 单向碰撞（参考 Godot One Way Collision） */
  oneWay?: boolean
  oneWayDirX?: number
  oneWayDirY?: number
  oneWayMargin?: number
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

/**
 * 图块集分组：界面上的一张「图块集」。
 * 同一画布上传的图块默认都归入第一个分组，只有用户手动新建才会产生新分组。
 */
export interface TilesetGroup {
  id: string
  name: string
}

interface MapLayerBase {
  id: number
  name: string
  visible: boolean
  locked: boolean
  /** 游戏运行时是否绘制该图层（默认 true；关闭后编辑器仍可见，打包运行时不渲染） */
  render?: boolean
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

/** 形状的绘制方式（仅影响生成顶点的算法，运行时统一按多边形处理） */
export type ShapeDrawType = 'rect' | 'circle' | 'capsule' | 'polygon'
/** 判定形状的能力：solid=阻挡，sensor=感应，both=两者 */
export type ShapeKind = 'solid' | 'sensor' | 'both'

/** 形状层里的一个世界坐标判定形状（几何只有一份，能力可叠加） */
export interface ShapeItem {
  id: string
  shape: ShapeDrawType
  // 地图世界坐标（像素）
  points: number[][]
  // 能力类型：阻挡 / 感应 / 两者（旧存档缺省视为 solid）
  kind: ShapeKind
  // 自由标签：代码里按 tag 查询（is_touch("tag")）
  tag: string
  // 单向碰撞（参考 Godot 的 One Way Collision）：勾选后只在「朝实心面推进」时挡住
  oneWay?: boolean
  // 触发碰撞的运动方向（世界坐标，y 向下）：(0,1) 下落 = 从上方踩住（默认）
  oneWayDirX?: number
  oneWayDirY?: number
  // 单向碰撞的厚度容差（像素）
  oneWayMargin?: number
  // 禁用：勾选后该形状不参与物理与感应判定
  disabled?: boolean
}

/** 形状层：整层共享一组世界坐标判定形状，与图像/图块解耦 */
export interface ShapeLayer extends MapLayerBase {
  type: 'shape'
  shapes: ShapeItem[]
}

export type MapLayer = DrawingLayer | ImageLayer | ShapeLayer

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
  // 旧存档兼容：图片实例碰撞，加载时会自动迁移为形状层
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
  /** 所属图块集分组（缺省视为第一个分组，兼容旧地图） */
  groupId?: string
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

/**
 * 场景标记：地图上给用户看的坐标图钉。
 * 坐标为世界坐标（地图左上角原点、y 向下），界面显示时换算为用户坐标。
 */
export interface SceneMarker {
  id: string
  name: string
  x: number
  y: number
  /** 类型：代码里可按类型批量查找（get_markers("敌人")），默认「出生点」 */
  type: string
  /** 是否在地图上显示（缺省视为显示，兼容旧地图） */
  visible?: boolean
  /** 是否锁定位置（锁定后不能拖动，仍可选中） */
  locked?: boolean
  /** 图钉下方是否显示名称（缺省显示） */
  showName?: boolean
  /** 图钉下方是否显示坐标（缺省显示） */
  showCoord?: boolean
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
  // 图块集分组：界面上的图块集列表；缺省时视为只有一个分组
  tilesetGroups?: TilesetGroup[]
  // 图块笔刷调色板：每个图块一个独立条目（顺序=界面显示顺序），缺省时由资源自动生成
  tilePalette?: TilePaletteEntry[]
  // 相机设置（缺省视为未启用）
  camera?: CameraSettings
  // 场景标记（地图级，不属于任何图层）
  markers: SceneMarker[]
}

export interface TilePaletteEntry {
  resourceId: string
  tileIndex: number
  /** 移动工具固化后的格子坐标（列 / 行）；缺省时按原图自动排列 */
  col?: number
  row?: number
}

export type MapTool = 'move' | 'select' | 'draw' | 'erase' | 'fill'
export type CollisionTool = 'move' | 'add' | 'delete' | 'reset'
// 形状层编辑工具：select=选择/拖动，rect/circle/capsule/polygon=形状，addPoint/deletePoint=锚点增删
export type ShapeTool = 'select' | 'rect' | 'circle' | 'capsule' | 'polygon' | 'addPoint' | 'deletePoint'

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
    markers: [],
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
  // 形状数据变更计数器（只触发叠加层重绘，不触发整图重渲染）
  const shapeRevision = ref(0)
  // 完整地图加载计数器（loadMap 时递增，用于素材面板/图层缩略图刷新）
  const mapLoadCount = ref(0)

  const activeLayer = computed(() => {
    const layer = mapData.value.layers[activeLayerIndex.value] ?? null
    return layer
  })
  // 当前工作模式：由选中图层类型决定；空地图默认图像模式
  const activeMode = computed<'image' | 'tile' | 'shape'>(() => {
    const type = activeLayer.value?.type
    return type === 'drawing' ? 'tile' : type === 'shape' ? 'shape' : 'image'
  })
  // 当前模式可用的素材：图像模式只看图像素材，图块模式看瓦片素材，形状层不需要素材
  const activeLayerResources = computed(() => {
    if (activeMode.value === 'shape') return []
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

  // 当前激活的形状层及其形状
  const activeShapeLayer = computed<ShapeLayer | null>(() =>
    activeLayer.value?.type === 'shape' ? activeLayer.value : null
  )
  const activeShapes = computed<ShapeItem[]>(() =>
    activeShapeLayer.value?.shapes ?? []
  )
  const activeShape = computed<ShapeItem | null>(() => {
    const list = activeShapes.value
    const id = mapEditor.activeShapeId
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

  // ====== 图块集分组 ======
  /** 保证至少有第一个图块集：旧地图与新建地图都从「图块集 1」开始 */
  function ensureTilesetGroups(): TilesetGroup[] {
    if (!mapData.value.tilesetGroups || mapData.value.tilesetGroups.length === 0) {
      mapData.value.tilesetGroups = [{ id: createResourceId(), name: '图块集 1' }]
    }
    return mapData.value.tilesetGroups
  }

  /** 用户手动新建图块集：之后的图块上传都会进入这个新分组 */
  function addTilesetGroup(name?: string): string {
    const groups = mapData.value.tilesetGroups ?? []
    const group: TilesetGroup = {
      id: createResourceId(),
      name: (name ?? '').trim() || `图块集 ${groups.length + 1}`,
    }
    mapData.value.tilesetGroups = [...groups, group]
    return group.id
  }

  function renameTilesetGroup(id: string, name: string) {
    const group = mapData.value.tilesetGroups?.find(g => g.id === id)
    if (group && name.trim()) group.name = name.trim()
  }

  /** 素材所属图块集：旧地图没有 groupId 时视为第一个分组 */
  function tilesetGroupIdOf(resource: MapResource | null): string {
    if (!resource) return ''
    if (resource.groupId) return resource.groupId
    return mapData.value.tilesetGroups?.[0]?.id ?? ''
  }

  function setMapPath(path: string) {
    currentMapPath.value = path
  }

  function loadMap(data: MapData) {
    // 兼容缺 markers 字段的数据源
    if (!Array.isArray(data.markers)) data.markers = []
    mapData.value = data
    // 默认选中最上方的图层（数组最后一个）
    activeLayerIndex.value = data.layers.length > 0 ? data.layers.length - 1 : -1
    selectedResourceIndex.value = -1
    selectedTileIndex.value = -1
    syncToolWithLayer()
    // 图片图层保留选中实例：打开地图后属性/碰撞可直接生效（变换框仍需用户主动点选才出现）；
    // 图块/形状图层则清空图片选中态
    if (data.layers[activeLayerIndex.value]?.type !== 'image') {
      clearImageSelection()
    }
    mapEditor.setActiveShapeId(null)
    mapEditor.setSelectedMarkerId(null)
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
      markers: [],
    }
    activeLayerIndex.value = -1
    selectedResourceIndex.value = -1
    selectedTileIndex.value = -1
    clearImageSelection()
    mapEditor.setSelectedMarkerId(null)
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
      mapEditor.setActiveShapeId(null)
      return
    }
    if (layer.type === 'shape') {
      // 形状层：默认激活选择移动（形状按钮独立记忆，默认矩形常亮）
      mapEditor.setTool('select')
      mapEditor.setShapeTool('select')
      mapEditor.setActiveShapeId(null)
      selectedImageLayerId.value = -1
      selectedResourceIndex.value = -1
      selectedTileIndex.value = -1
      return
    }
    mapEditor.setActiveShapeId(null)
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
    // 图块素材默认并入最后一个图块集（同一画布上传的图块都算同一集）
    if (resource.resourceType !== 'image' && !resource.groupId) {
      const groups = ensureTilesetGroups()
      resource.groupId = groups[groups.length - 1].id
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
    // 重建调色板时保留已有的格子坐标，否则用户摆好的位置会被打回自动排列
    const prev = new Map(
      (mapData.value.tilePalette ?? []).map(e => [`${e.resourceId}:${e.tileIndex}`, e]),
    )
    mapData.value.tilePalette = entries.map(e => {
      const old = prev.get(`${e.resourceId}:${e.tileIndex}`)
      return {
        resourceId: e.resourceId,
        tileIndex: e.tileIndex,
        col: e.col ?? old?.col,
        row: e.row ?? old?.row,
      }
    })
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

  /** 把当前自动排列固化成格子坐标（移动工具第一次拖动时调用，避免其余图块重新排列） */
  function setPaletteCells(cells: { resourceId: string; tileIndex: number; col: number; row: number }[]) {
    const list = mapData.value.tilePalette
    if (!list?.length) return
    const byKey = new Map(cells.map(c => [`${c.resourceId}:${c.tileIndex}`, c]))
    for (const entry of list) {
      const cell = byKey.get(`${entry.resourceId}:${entry.tileIndex}`)
      if (!cell) continue
      entry.col = cell.col
      entry.row = cell.row
    }
  }

  /** 单个图块挪到指定格子（移动 / 交换时由界面调用） */
  function setPaletteEntryCell(resourceId: string, tileIndex: number, col: number, row: number) {
    const entry = mapData.value.tilePalette?.find(
      e => e.resourceId === resourceId && e.tileIndex === tileIndex,
    )
    if (!entry) return
    entry.col = col
    entry.row = row
  }

  // ====== 调色板里选中的图块（供右侧面板批量设置） ======
  /** 图块面板点选 / 框选的结果，右侧面板按它批量改类型、作用、单向碰撞 */
  const tileBrushSelection = ref<{ resourceId: string; tileIndex: number }[]>([])

  function setTileBrushSelection(list: { resourceId: string; tileIndex: number }[]) {
    tileBrushSelection.value = list
  }

  // ====== 随机绘制（参照 Godot 的随机绘制） ======
  /** 开启后画布上每一格都从随机池里挑一块画 */
  const randomBrushEnabled = ref(false)
  const randomBrushPool = ref<{ resourceId: string; tileIndex: number }[]>([])
  /** 散布（同 Godot 的 Scattering）：0~100，越大越可能这一格干脆不画 */
  const randomBrushScatter = ref(0)

  function setRandomBrush(enabled: boolean, pool: { resourceId: string; tileIndex: number }[] = []) {
    randomBrushEnabled.value = enabled
    randomBrushPool.value = enabled ? pool : []
  }

  function setRandomBrushScatter(percent: number) {
    randomBrushScatter.value = Math.max(0, Math.min(100, Math.round(percent)))
  }

  /** 当前该画的图块：随机模式下从池子里随机取一块，否则用当前画笔；散布命中时这一格不画 */
  function pickBrush(): { resourceIndex: number; tileIndex: number } {
    const pool = randomBrushPool.value
    if (randomBrushEnabled.value) {
      // 散布：按概率整格留空，形成自然的稀疏效果
      if (randomBrushScatter.value > 0 && Math.random() * 100 < randomBrushScatter.value) {
        return { resourceIndex: -1, tileIndex: -1 }
      }
      if (pool.length > 1) {
        const pick = pool[Math.floor(Math.random() * pool.length)]
        const index = activeLayerResources.value.findIndex(r => r.id === pick.resourceId)
        if (index >= 0) return { resourceIndex: index, tileIndex: pick.tileIndex }
      }
    }
    return {
      resourceIndex: selectedResourceIndex.value,
      tileIndex: selectedTileIndex.value,
    }
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

  /**
   * 修改图块尺寸：保持地图的「世界像素尺寸」不变。
   * 例：40×30 @16px（640×480）改成 32px → 变成 20×15，仍然 640×480，
   * 游戏窗口能看到的范围不变；瓦片坐标按比例同步换算。
   */
  function updateTileSize(newSize: number) {
    const oldSize = mapData.value.tileSize
    if (!Number.isFinite(newSize) || newSize <= 0 || newSize === oldSize) return
    const k = newSize / oldSize
    const mapCoord = (v: number) => Math.max(0, Math.round(v / k))
    const newWidth = Math.max(1, Math.round(mapData.value.width / k))
    const newHeight = Math.max(1, Math.round(mapData.value.height / k))

    // 瓦片按格子坐标存储：换算到新的格子空间（缩小时同一格的后写入者胜出）
    for (const layer of mapData.value.layers) {
      if (layer.type !== 'drawing') continue
      const next: Record<string, number> = {}
      for (const [key, gid] of Object.entries(layer.tiles)) {
        const [x, y] = key.split(',').map(Number)
        const nx = mapCoord(x)
        const ny = mapCoord(y)
        if (nx >= newWidth || ny >= newHeight) continue
        next[`${nx},${ny}`] = gid
      }
      layer.tiles = next
    }

    mapData.value.width = newWidth
    mapData.value.height = newHeight
    mapData.value.tileSize = newSize

    // 图块集保留自己的切片尺寸：换网格不会重新切图，已画的图块外观不丢，
    // 渲染时按「原图尺寸 → 当前格子」等比缩放（编辑器与游戏窗口一致）
    tileRevision.value++
  }

  // ====== 场景标记 ======
  const selectedMarker = computed<SceneMarker | null>(() => {
    const id = mapEditor.selectedMarkerId
    return id ? mapData.value.markers.find(m => m.id === id) ?? null : null
  })

  function createMarkerId(): string {
    return `mk_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
  }

  /** 新增标记：唯一命名 标记 / 标记1 / 标记2 ...，坐标取世界像素 */
  function addMarker(xWorld: number, yWorld: number): string {
    const used = new Set(mapData.value.markers.map(m => m.name))
    let name = '标记'
    let n = 1
    while (used.has(name)) { name = `标记${n}`; n++ }
    const marker: SceneMarker = {
      id: createMarkerId(),
      name,
      x: Math.round(xWorld),
      y: Math.round(yWorld),
      type: '出生点',
    }
    mapData.value.markers.push(marker)
    mapEditor.setSelectedMarkerId(marker.id)
    return marker.id
  }

  /** 重命名标记：空名或重名不生效，返回是否成功 */
  function renameMarker(id: string, name: string): boolean {
    const marker = mapData.value.markers.find(m => m.id === id)
    const trimmed = name.trim()
    if (!marker || !trimmed) return false
    if (trimmed !== marker.name && mapData.value.markers.some(m => m.name === trimmed)) return false
    marker.name = trimmed
    return true
  }

  /** 设置标记类型（代码里 get_markers(类型) 按此分组） */
  function setMarkerType(id: string, type: string) {
    const marker = mapData.value.markers.find(m => m.id === id)
    if (!marker) return
    marker.type = type.trim() || '出生点'
  }

  /** 显示 / 隐藏标记（只影响编辑器画面，代码里仍可读） */
  function setMarkerVisible(id: string, visible: boolean) {
    const marker = mapData.value.markers.find(m => m.id === id)
    if (!marker) return
    marker.visible = visible
  }

  /** 锁定 / 解锁标记（锁定后不能拖动，仍可选中） */
  function setMarkerLocked(id: string, locked: boolean) {
    const marker = mapData.value.markers.find(m => m.id === id)
    if (!marker) return
    marker.locked = locked
  }

  /** 图钉标签的显示项：名称 / 坐标 */
  function setMarkerLabelVisible(id: string, part: 'name' | 'coord', visible: boolean) {
    const marker = mapData.value.markers.find(m => m.id === id)
    if (!marker) return
    if (part === 'name') marker.showName = visible
    else marker.showCoord = visible
  }

  /** 移动标记（世界像素坐标） */
  function updateMarkerPosition(id: string, xWorld: number, yWorld: number) {
    const marker = mapData.value.markers.find(m => m.id === id)
    if (!marker) return
    marker.x = Math.round(xWorld)
    marker.y = Math.round(yWorld)
  }

  /** 复制标记：紧邻原标记偏移一点，命名「原名副本 / 原名副本2 ...」 */
  function duplicateMarker(id: string): string | null {
    const src = mapData.value.markers.find(m => m.id === id)
    if (!src) return null
    const used = new Set(mapData.value.markers.map(m => m.name))
    const base = `${src.name}副本`
    let name = base
    let n = 2
    while (used.has(name)) { name = `${base}${n}`; n++ }
    const marker: SceneMarker = {
      id: createMarkerId(),
      name,
      x: src.x + 16,
      y: src.y + 16,
      type: src.type,
      visible: src.visible,
      locked: src.locked,
      showName: src.showName,
      showCoord: src.showCoord,
    }
    mapData.value.markers.push(marker)
    mapEditor.setSelectedMarkerId(marker.id)
    return marker.id
  }

  function removeMarker(id: string) {
    const idx = mapData.value.markers.findIndex(m => m.id === id)
    if (idx < 0) return
    mapData.value.markers.splice(idx, 1)
    if (mapEditor.selectedMarkerId === id) mapEditor.setSelectedMarkerId(null)
  }

  // ====== 图层 / 图像选中 ======

  function selectImage(layerId: number) {
    selectedImageLayerId.value = layerId
  }

  function clearImageSelection() {
    selectedImageLayerId.value = -1
  }

  // ====== 形状层（世界坐标判定形状） ======

  function createShapeId(): string {
    return `shp_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
  }

  /** 新建形状层并选中 */
  function addShapeLayer(name = '碰撞'): number {
    const layers = mapData.value.layers
    const id = layers.length > 0 ? Math.max(...layers.map(l => l.id)) + 1 : 0
    const used = new Set(layers.map(l => l.name))
    let finalName = name
    let seq = 2
    while (used.has(finalName)) finalName = `${name} ${seq++}`
    const layer: ShapeLayer = {
      id, name: finalName, type: 'shape', visible: true, locked: false, shapes: [],
    }
    layers.push(layer)
    activeLayerIndex.value = layers.length - 1
    selectedResourceIndex.value = -1
    selectedTileIndex.value = -1
    syncToolWithLayer()
    imageRevision.value++
    return id
  }

  /** 在当前形状层新增一个形状并选中 */
  function addShape(
    shape: ShapeDrawType,
    points: number[][],
    options: Partial<Pick<ShapeItem,
      'kind' | 'tag' | 'oneWay' | 'oneWayDirX' | 'oneWayDirY' | 'oneWayMargin'>> = {},
  ): string | null {
    const layer = activeShapeLayer.value
    if (!layer) return null
    const item: ShapeItem = {
      id: createShapeId(),
      shape,
      points: points.map(p => [p[0], p[1]]),
      kind: options.kind ?? 'solid',
      // 标签默认「墙体」：新建形状开箱即用，代码里直接 is_touch("墙体") 就能查
      tag: options.tag ?? '墙体',
      // 默认普通碰撞（不勾单向）；勾选后默认方向为「下落时挡住」，厚度 0
      oneWay: options.oneWay ?? false,
      oneWayDirX: options.oneWayDirX ?? 0,
      oneWayDirY: options.oneWayDirY ?? 1,
      oneWayMargin: options.oneWayMargin ?? 0,
    }
    layer.shapes.push(item)
    mapEditor.setActiveShapeId(item.id)
    shapeRevision.value++
    return item.id
  }

  function removeShape(id: string) {
    const layer = activeShapeLayer.value
    if (!layer) return
    const idx = layer.shapes.findIndex(p => p.id === id)
    if (idx < 0) return
    layer.shapes.splice(idx, 1)
    if (mapEditor.activeShapeId === id) {
      const next = layer.shapes[Math.min(idx, layer.shapes.length - 1)] ?? null
      mapEditor.setActiveShapeId(next?.id ?? null)
    } else if (mapEditor.activeShapeIds.includes(id)) {
      mapEditor.setActiveShapeIds(mapEditor.activeShapeIds.filter(x => x !== id))
    }
    shapeRevision.value++
  }

  /** 更新形状顶点；不足 3 点视为删除 */
  function updateShapePoints(id: string, points: number[][] | null) {
    const layer = activeShapeLayer.value
    if (!layer) return
    const item = layer.shapes.find(p => p.id === id)
    if (!item) return
    if (!points || points.length < 3) {
      removeShape(id)
      return
    }
    item.points = points.map(p => [p[0], p[1]])
    shapeRevision.value++
  }

  /** 批量修改形状属性：只写入传入的字段，其余保持原值（单选也是走这里，ids 传一个即可） */
  function updateShapes(
    ids: string[],
    patch: Partial<Pick<ShapeItem,
      'kind' | 'tag' | 'oneWay' | 'oneWayDirX' | 'oneWayDirY' | 'oneWayMargin' | 'disabled'>>,
  ) {
    const layer = activeShapeLayer.value
    if (!layer || ids.length === 0) return
    const wanted = new Set(ids)
    let changed = false
    for (const item of layer.shapes) {
      if (!wanted.has(item.id)) continue
      if (patch.kind !== undefined) item.kind = patch.kind
      if (patch.tag !== undefined) item.tag = patch.tag
      if (patch.oneWay !== undefined) item.oneWay = patch.oneWay
      if (patch.oneWayDirX !== undefined) item.oneWayDirX = patch.oneWayDirX
      if (patch.oneWayDirY !== undefined) item.oneWayDirY = patch.oneWayDirY
      if (patch.oneWayMargin !== undefined) item.oneWayMargin = patch.oneWayMargin
      if (patch.disabled !== undefined) item.disabled = patch.disabled
      changed = true
    }
    if (changed) shapeRevision.value++
  }

  /** 批量删除形状；当前选中的形状被删掉时清空选中 */
  function removeShapes(ids: string[]) {
    const layer = activeShapeLayer.value
    if (!layer || ids.length === 0) return
    const wanted = new Set(ids)
    const before = layer.shapes.length
    layer.shapes = layer.shapes.filter(item => !wanted.has(item.id))
    if (layer.shapes.length === before) return
    // 从多选里剔除已删除的形状；主选中被删掉时清空
    const alive = new Set(layer.shapes.map(item => item.id))
    if (mapEditor.activeShapeId && !alive.has(mapEditor.activeShapeId)) {
      mapEditor.setActiveShapeIds(mapEditor.activeShapeIds.filter(x => alive.has(x)))
    } else if (mapEditor.activeShapeIds.some(x => !alive.has(x))) {
      mapEditor.setActiveShapeIds(mapEditor.activeShapeIds.filter(x => alive.has(x)))
    }
    shapeRevision.value++
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

  function setTileCollision(
    tileSetIndex: number,
    tileIndex: number,
    collision: boolean,
    defaultShape?: { points: number[][] },
  ) {
    const tileSet = mapData.value.tileSets[tileSetIndex]
    if (!tileSet) return
    while (tileSet.tiles.length <= tileIndex) {
      tileSet.tiles.push({
        collision: false,
        tag: '',
        collisionType: '图像',
      })
    }
    const tile = tileSet.tiles[tileIndex]
    tile.collision = collision
    // 开启碰撞时没有形状就补一个默认的整块矩形，碰撞编辑器里可以直接微调
    if (collision && !tile.collisionShape && defaultShape) {
      tile.collisionShape = defaultShape
    }
    // 类型默认是「墙体」（和碰撞图层新建时一致）
    if (collision && !(tile.tag || '').trim()) {
      tile.tag = '墙体'
    }
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

  /** 图块分类（= 图块 tag，代码里 is_touch("分类名") 用） */
  function setTileTag(tileSetIndex: number, tileIndex: number, tag: string) {
    const tileSet = mapData.value.tileSets[tileSetIndex]
    if (!tileSet) return
    while (tileSet.tiles.length <= tileIndex) {
      tileSet.tiles.push({
        collision: false,
        tag: '',
        collisionType: '图像',
      })
    }
    tileSet.tiles[tileIndex].tag = tag
  }

  /** 修改某个图块的属性（作用 / 单向碰撞等） */
  function updateTile(
    tileSetIndex: number,
    tileIndex: number,
    patch: Partial<Pick<TileData,
      'kind' | 'tag' | 'oneWay' | 'oneWayDirX' | 'oneWayDirY' | 'oneWayMargin'>>,
  ) {
    const tileSet = mapData.value.tileSets[tileSetIndex]
    if (!tileSet) return
    while (tileSet.tiles.length <= tileIndex) {
      tileSet.tiles.push({
        collision: false,
        tag: '',
        collisionType: '图像',
      })
    }
    const tile = tileSet.tiles[tileIndex]
    if (patch.kind !== undefined) tile.kind = patch.kind
    if (patch.tag !== undefined) tile.tag = patch.tag
    if (patch.oneWay !== undefined) tile.oneWay = patch.oneWay
    if (patch.oneWayDirX !== undefined) tile.oneWayDirX = patch.oneWayDirX
    if (patch.oneWayDirY !== undefined) tile.oneWayDirY = patch.oneWayDirY
    if (patch.oneWayMargin !== undefined) tile.oneWayMargin = patch.oneWayMargin
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
    ensureTilesetGroups,
    addTilesetGroup,
    renameTilesetGroup,
    tilesetGroupIdOf,
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
    setPaletteCells,
    setPaletteEntryCell,
    randomBrushEnabled,
    randomBrushPool,
    randomBrushScatter,
    tileBrushSelection,
    setTileBrushSelection,
    setRandomBrush,
    setRandomBrushScatter,
    pickBrush,
    movePaletteEntry,
    removePaletteEntry,
    removeResource,
    clearResources,
    updateMapProperty,
    updateCameraSettings,
    updateTileSize,
    selectedMarker,
    addMarker,
    renameMarker,
    setMarkerType,
    setMarkerVisible,
    setMarkerLocked,
    setMarkerLabelVisible,
    updateMarkerPosition,
    duplicateMarker,
    removeMarker,
    setTileCollision,
    setTileCollisionType,
    setTileTag,
    updateTile,
    selectedImageLayerId,
    selectedImage,
    activeShapeLayer,
    activeShapes,
    activeShape,
    sceneRenderMode,
    selectImage,
    clearImageSelection,
    addShapeLayer,
    addShape,
    removeShape,
    updateShapePoints,
    updateShapes,
    removeShapes,
    tileRevision,
    imageRevision,
    shapeRevision,
    mapLoadCount,
  }
})
