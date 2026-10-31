import * as pako from 'pako'
import { imageLocalToWorld } from './mapImageGeometry'

export interface MapSaveData {
  name: string
  width: number
  height: number
  tileSize: number
  gravity: boolean
  /** 边界碰撞：勾选后角色被地图矩形挡住；旧存档缺省时沿用 gravity */
  boundaryCollision?: boolean
  /** 禁止下滑：勾选后角色站在斜坡上不会下滑；旧存档缺省视为开启 */
  stopOnSlope?: boolean
  collisionType: string
  collisionEnabled: boolean
  renderMode?: 'smooth' | 'pixelated'
  // 地图级素材库（新增）；旧存档没有该字段时从各图层收集
  resources?: ResourceSaveData[]
  layers: LayerSaveData[]
  tilesets: TilesetSaveData[]
  // 图块集分组：界面上的图块集列表（缺省视为只有一个）
  tilesetGroups?: TilesetGroupSaveData[]
  // 图块笔刷调色板（顺序=界面显示顺序；col/row 为移动工具摆好的格子坐标）
  tilePalette?: { resourceId: string; tileIndex: number; col?: number; row?: number }[]
  // 相机设置（引擎运行时读取）
  camera?: {
    enabled: boolean
    target?: string
    offsetX: number
    offsetY: number
    smoothing: number
    limitBounds: boolean
  }
  // 场景标记：世界坐标；引擎 load_map 后可通过 get_marker / get_markers 读取
  markers?: {
    id: string
    name: string
    x: number
    y: number
    type?: string
    visible?: boolean
    locked?: boolean
    showName?: boolean
    showCoord?: boolean
  }[]
}

export interface LayerSaveData {
  id: number
  name: string
  /** shapelayer 为新格式；collisionlayer 仅用于兼容读取旧存档 */
  type: 'tilelayer' | 'imagelayer' | 'shapelayer' | 'collisionlayer'
  visible: boolean
  locked: boolean
  /** 游戏运行时是否渲染该图层（缺省视为 true） */
  render?: boolean
  /** 整层位移（世界像素，仅图块层） */
  offsetX?: number
  offsetY?: number
  /** 整层缩放（以地图中心为基准，缺省 1）与旋转（世界角度，顺时针为正，单位度） */
  scaleX?: number
  scaleY?: number
  rotation?: number
  /** 该图块层当前使用的图块集（集合是独立资源仓库，只影响左侧资源列表） */
  groupId?: string
  /** 过渡期存档字段：上一版按图层记录的多个图块集，读取时取第一个 */
  groupIds?: string[]
  data?: string
  images?: ImageSaveData[]
  resources?: ResourceSaveData[]
  // 形状层：世界坐标判定形状
  shapes?: ShapeSaveData[]
  // 旧存档字段名，仅用于兼容读取
  polygons?: ShapeSaveData[]
}

/** 图块集分组：名称 + 锁定 / 禁用状态 */
export interface TilesetGroupSaveData {
  id: string
  name: string
  locked?: boolean
  disabled?: boolean
}

export interface ShapeSaveData {
  id: string
  shape: 'rect' | 'circle' | 'capsule' | 'polygon'
  points: number[][]
  /** 能力类型：solid / sensor / both（旧存档缺省视为 solid） */
  kind?: 'solid' | 'sensor' | 'both'
  /** 自由标签：代码里按 tag 查询 */
  tag?: string
  /** 单向碰撞（参考 Godot One Way Collision） */
  oneWay?: boolean
  /** 触发碰撞的运动方向（世界坐标，y 向下）：(0,1) 下落 = 从上方踩住 */
  oneWayDirX?: number
  oneWayDirY?: number
  /** 单向碰撞厚度容差（像素） */
  oneWayMargin?: number
  /** 碰撞类型：由 oneWay 推导（引擎用它填 raycast 等 API 的 collision_type）
      旧存档的「跳板」表示单向碰撞，读取时会迁移成 oneWay */
  collisionType?: string
  disabled?: boolean
}

export interface ResourceSaveData {
  // 稳定标识与 GID 起点：新存档写入，旧存档缺失时由读取方迁移补全
  id?: string
  firstgid?: number
  name: string
  path: string
  resourceType: string
  tileWidth: number
  tileHeight: number
  collisionType: string
  collisionEnabled: boolean
  collisionShape?: { points: number[][] }
  /** 所属图块集分组 */
  groupId?: string
}

export interface ImageSaveData {
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
  // 多个碰撞体；旧字段 collisionShape 仅用于兼容读取
  collisions?: { id: string; shape: 'rect' | 'polygon'; points: number[][] }[]
  collisionShape?: { points: number[][] }
  background?: boolean
  vectorData?: string
  vectorBasePath?: string
  paintMode?: 'bitmap' | 'vector'
}

export interface TilesetSaveData {
  id?: string
  name: string
  image: string
  firstgid: number
  tileWidth: number
  tileHeight: number
  collisionType: string
  collisionEnabled: boolean
  tiles?: {
    id: number
    collision: string
    tag?: string
    collisionType?: string
    collisionShape?: { points: number[][] }
    /** 作用：solid / sensor / both（缺省视为 solid） */
    kind?: 'solid' | 'sensor' | 'both'
    /** 单向碰撞（参考 Godot One Way Collision） */
    oneWay?: boolean
    oneWayDirX?: number
    oneWayDirY?: number
    oneWayMargin?: number
  }[]
}

export interface MapLoadData {
  name: string
  version: number
  width: number
  height: number
  tileSize: number
  gravity: boolean
  boundaryCollision: boolean
  stopOnSlope: boolean
  collisionType: string
  collisionEnabled: boolean
  renderMode?: 'smooth' | 'pixelated'
  resources: any[]
  layers: any[]
  tileSets: any[]
  tilesetGroups?: TilesetGroupSaveData[]
  tilePalette?: { resourceId: string; tileIndex: number; col?: number; row?: number }[]
  camera?: {
    enabled: boolean
    target?: string
    offsetX: number
    offsetY: number
    smoothing: number
    limitBounds: boolean
  }
  markers: {
    id: string
    name: string
    x: number
    y: number
    type: string
    visible?: boolean
    locked?: boolean
    showName?: boolean
    showCoord?: boolean
  }[]
}

/**
 * 将稀疏瓦片字典压缩为 base64+zlib 字符串
 * 瓦片值已经是GID格式（firstgid + localTileIndex）
 */
export function compressTileData(
  tiles: Record<string, number>,
  width: number,
  height: number,
): string {
  const flatArray = new Uint32Array(width * height)

  for (const [key, gid] of Object.entries(tiles)) {
    const [x, y] = key.split(',').map(Number)
    if (x >= 0 && x < width && y >= 0 && y < height) {
      flatArray[y * width + x] = gid
    }
  }

  const compressed = pako.deflate(flatArray.buffer)
  return btoa(String.fromCharCode(...compressed))
}

/**
 * 解压 base64+zlib 瓦片数据为稀疏字典
 * 返回GID格式（firstgid + localTileIndex），由调用方负责解码
 */
export function decompressTileData(
  base64: string,
  width: number,
  height: number,
): Record<string, number> {
  const compressed = Uint8Array.from(atob(base64), c => c.charCodeAt(0))
  const decompressed = pako.inflate(compressed)
  const flatArray = new Uint32Array(decompressed.buffer)

  const tiles: Record<string, number> = {}
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const gid = flatArray[y * width + x]
      if (gid > 0) {
        tiles[`${x},${y}`] = gid
      }
    }
  }

  return tiles
}

/**
 * 从编辑器内部格式转换为保存格式
 */
export function serializeMap(mapData: any): MapSaveData {
  const serializeResource = (r: any): ResourceSaveData => ({
    id: r.id || undefined,
    firstgid: r.firstgid || undefined,
    name: r.name,
    path: r.path,
    resourceType: r.resourceType,
    tileWidth: r.tileWidth,
    tileHeight: r.tileHeight,
    collisionType: r.collisionType || '图像',
    collisionEnabled: r.collisionEnabled || false,
    collisionShape: r.collisionShape,
    groupId: r.groupId || undefined,
  })

  const mapResources = (mapData.resources || []).map(serializeResource)
  const imageResources = (mapData.resources || []).filter((r: any) => r.resourceType === 'image')
  const tileResources = (mapData.resources || []).filter((r: any) => r.resourceType !== 'image')

  const tilesets: TilesetSaveData[] = mapData.tileSets.map((ts: any) => {
    return {
      id: ts.id || undefined,
      name: ts.name,
      image: ts.imagePath,
      firstgid: ts.firstgid || 1,
      tileWidth: ts.tileWidth,
      tileHeight: ts.tileHeight,
      collisionType: ts.collisionType || '图像',
      collisionEnabled: ts.collisionEnabled || false,
      tiles: ts.tiles?.map((t: any, i: number) => ({
        id: i,
        collision: t.collision ? 'solid' : 'none',
        collisionType: t.collisionType || '图像',
        tag: t.tag || undefined,
        collisionShape: t.collisionShape,
        kind: t.kind || undefined,
        oneWay: t.oneWay === true,
        oneWayDirX: t.oneWayDirX ?? 0,
        oneWayDirY: t.oneWayDirY ?? 1,
        oneWayMargin: t.oneWayMargin ?? 0,
      })),
    }
  })

  const serializeImage = (img: any): ImageSaveData => ({
    imagePath: img.imagePath,
    position: img.position,
    rotation: img.rotation,
    scale: img.scale,
    scaleX: img.scaleX,
    scaleY: img.scaleY,
    opacity: img.opacity,
    width: img.width,
    height: img.height,
    collisionType: img.collisionType || 'none',
    collisionEnabled: false,
    background: img.background || false,
    vectorData: img.vectorData,
    vectorBasePath: img.vectorBasePath,
    paintMode: img.paintMode,
  })

  const layers: LayerSaveData[] = mapData.layers.map((layer: any) => {
    const base: LayerSaveData = {
      id: layer.id,
      name: layer.name,
      type: layer.type === 'image' ? 'imagelayer' : layer.type === 'shape' ? 'shapelayer' : 'tilelayer',
      visible: layer.visible,
      locked: layer.locked,
      render: layer.render !== false,
    }

    if (layer.type === 'shape') {
      base.shapes = (layer.shapes || []).map((shape: any): ShapeSaveData => ({
        id: shape.id,
        shape: shape.shape,
        points: shape.points,
        kind: shape.kind || 'solid',
        tag: shape.tag || '',
        oneWay: shape.oneWay === true,
        oneWayDirX: shape.oneWayDirX ?? 0,
        oneWayDirY: shape.oneWayDirY ?? 1,
        oneWayMargin: shape.oneWayMargin ?? 0,
        // 单向形状在引擎/代码里仍报告为「跳板」，普通形状为「墙体」
        collisionType: shape.oneWay === true ? '跳板' : '墙体',
        disabled: shape.disabled === true,
      }))
      return base
    }

    if (layer.type === 'drawing') {
      base.data = compressTileData(layer.tiles, mapData.width, mapData.height)
      base.offsetX = layer.offsetX || 0
      base.offsetY = layer.offsetY || 0
      base.scaleX = layer.scaleX ?? 1
      base.scaleY = layer.scaleY ?? 1
      base.rotation = layer.rotation || 0
      base.groupId = layer.groupId || undefined
    }

    // 扁平模型：一个图片图层只对应一张图片，仍然写成标准 imagelayer
    if (layer.image) {
      base.images = [serializeImage(layer.image)]
    }

    // 层内镜像只用于兼容旧版本与引擎的 tileset 碰撞回填；
    // 编辑器真正读取的是顶层地图级 resources
    const layerResources = layer.type === 'image' ? imageResources : tileResources
    if (layerResources.length > 0) {
      base.resources = layerResources.map(serializeResource)
    }

    return base
  })

  return {
    name: mapData.name,
    width: mapData.width,
    height: mapData.height,
    tileSize: mapData.tileSize,
    gravity: mapData.gravity,
    boundaryCollision: mapData.boundaryCollision,
    stopOnSlope: mapData.stopOnSlope,
    collisionType: mapData.collisionType || '图像',
    collisionEnabled: mapData.collisionEnabled || false,
    resources: mapResources,
    layers,
    tilesets,
    tilesetGroups: mapData.tilesetGroups?.map((g: any) => ({
      id: g.id,
      name: g.name,
      ...(g.locked ? { locked: true } : {}),
      ...(g.disabled ? { disabled: true } : {}),
    })),
    tilePalette: mapData.tilePalette,
    camera: mapData.camera,
    markers: (mapData.markers || []).map((m: any) => ({
      id: m.id,
      name: m.name,
      x: Number(m.x) || 0,
      y: Number(m.y) || 0,
      type: typeof m.type === 'string' && m.type.trim() ? m.type : '出生点',
      visible: m.visible !== false,
      locked: m.locked === true,
      showName: m.showName !== false,
      showCoord: m.showCoord !== false,
    })),
  }
}

/**
 * 从保存格式转换为编辑器内部格式
 */
export function deserializeMap(data: MapSaveData): MapLoadData {
  const tileSets = data.tilesets.map(ts => ({
    id: ts.id || '',
    name: ts.name,
    imagePath: ts.image,
    resourceType: 'tileset',
    tileWidth: ts.tileWidth,
    tileHeight: ts.tileHeight,
    firstgid: ts.firstgid || 1,
    collisionType: ts.collisionType || '图像',
    collisionEnabled: ts.collisionEnabled || false,
    tiles: ts.tiles?.map(t => ({
      collision: t.collision === 'solid',
      tag: t.tag || '',
      collisionType: t.collisionType || '图像',
      collisionShape: t.collisionShape,
      kind: t.kind === 'sensor' || t.kind === 'both' ? t.kind : 'solid',
      oneWay: t.oneWay === true,
      oneWayDirX: Number(t.oneWayDirX) || 0,
      oneWayDirY: t.oneWayDirY === undefined || t.oneWayDirY === null ? 1 : Number(t.oneWayDirY) || 0,
      oneWayMargin: Number(t.oneWayMargin) || 0,
    })) || [],
  }))

  // 旧存档没有 id/firstgid：按 path/name 把资源与 tileset 一一配对并补全
  const createResourceId = () =>
    `res_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
  const claimedTileSets = new Set<any>()
  let nextFirstgid = tileSets.length > 0
    ? Math.max(...tileSets.map(ts => ts.firstgid || 1))
    : 0

  // 统一解析素材：补全 id/firstgid，并与 tileset 一一配对
  const resolveResource = (r: any): any => {
    let matched: any = null
    if (r.id) matched = tileSets.find(ts => ts.id === r.id) ?? null
    if (!matched && r.firstgid != null) {
      matched = tileSets.find(ts => ts.firstgid === r.firstgid) ?? null
    }
    if (!matched) {
      matched = tileSets.find(
        ts => !claimedTileSets.has(ts) && ts.imagePath === r.path && ts.name === r.name,
      ) ?? tileSets.find(
        ts => !claimedTileSets.has(ts) && ts.imagePath === r.path,
      ) ?? null
    }
    if (matched) claimedTileSets.add(matched)

    const resourceType = r.resourceType === 'image' ? 'image' : 'tileset'
    const id = r.id || matched?.id || createResourceId()
    let firstgid = r.firstgid ?? matched?.firstgid
    if (!firstgid || firstgid <= 0) {
      firstgid = nextFirstgid > 0 ? nextFirstgid + 10000 : 1
      nextFirstgid = firstgid
    } else if (firstgid > nextFirstgid) {
      nextFirstgid = firstgid
    }

    if (matched) {
      if (!matched.id) matched.id = id
      // 资源声明的 firstgid 优先，保证已有瓦片 GID 不变
      matched.firstgid = firstgid
    } else {
      matched = {
        id,
        name: r.name,
        imagePath: r.path,
        resourceType,
        tileWidth: r.tileWidth,
        tileHeight: r.tileHeight,
        firstgid,
        collisionType: r.collisionType || '图像',
        collisionEnabled: r.collisionEnabled || false,
        tiles: [],
      }
      tileSets.push(matched)
      claimedTileSets.add(matched)
    }

    return {
      id,
      firstgid,
      name: r.name,
      path: r.path,
      resourceType,
      tileWidth: r.tileWidth,
      tileHeight: r.tileHeight,
      collisionType: r.collisionType || '图像',
      collisionEnabled: r.collisionEnabled || false,
      collisionShape: r.collisionShape,
      groupId: r.groupId,
    }
  }

  let resources: any[]
  if (Array.isArray(data.resources)) {
    // 新存档：直接读地图级素材库
    resources = data.resources.map(resolveResource)
  } else {
    // 旧存档：从各图层收集，并按来源图层归一化素材类型
    const legacy: any[] = []
    for (const layer of data.layers) {
      for (const r of layer.resources || []) {
        legacy.push({
          ...r,
          resourceType: layer.type === 'imagelayer' ? 'image' : 'tileset',
        })
      }
    }
    resources = legacy.map(resolveResource)
  }

  // 图像素材只按路径被实例引用，重复条目直接合并
  const seenImagePaths = new Set<string>()
  resources = resources.filter(r => {
    if (r.resourceType !== 'image') return true
    if (seenImagePaths.has(r.path)) return false
    seenImagePaths.add(r.path)
    return true
  })

  // 扁平模型：旧存档一个 imagelayer 里的多张图片，拆成多个独立图片图层
  const layers: any[] = []
  for (const layer of data.layers) {
    if (layer.type === 'imagelayer') {
      const images: any[] = layer.images || []
      images.forEach((img, i) => {
        layers.push({
          id: layer.id,
          name: images.length > 1 ? `${layer.name || '图片'}${i > 0 ? ` ${i + 1}` : ''}` : (layer.name || '图片'),
          type: 'image',
          visible: layer.visible,
          locked: layer.locked,
          render: layer.render !== false,
          image: img,
        })
      })
      continue
    }

    if (layer.type === 'shapelayer' || layer.type === 'collisionlayer') {
      // 新格式写 shapes；旧存档只有 polygons，读取时统一成形状
      const rawShapes: any[] = Array.isArray(layer.shapes)
        ? layer.shapes
        : (Array.isArray(layer.polygons) ? layer.polygons : [])
      layers.push({
        id: layer.id,
        name: layer.name || '碰撞',
        type: 'shape',
        visible: layer.visible,
        locked: layer.locked,
        render: layer.render !== false,
        shapes: rawShapes
          .filter(p => Array.isArray(p.points) && p.points.length >= 3)
          .map(p => ({
            id: p.id || `shp_${Math.random().toString(36).slice(2, 8)}`,
            shape: p.shape === 'rect' || p.shape === 'circle' || p.shape === 'capsule' ? p.shape : 'polygon',
            points: p.points.map((pt: any[]) => [Number(pt[0]) || 0, Number(pt[1]) || 0]),
            kind: p.kind === 'sensor' || p.kind === 'both' ? p.kind : 'solid',
            tag: typeof p.tag === 'string' ? p.tag : '',
            // 单向碰撞：新存档读 oneWay 字段；旧存档的「跳板」类型迁移成方向向下
            oneWay: p.oneWay === true || p.collisionType === '跳板',
            oneWayDirX: p.oneWayDirX === undefined || p.oneWayDirX === null
              ? 0
              : Number(p.oneWayDirX) || 0,
            oneWayDirY: p.oneWayDirY === undefined || p.oneWayDirY === null
              ? 1
              : Number(p.oneWayDirY) || 0,
            oneWayMargin: Number(p.oneWayMargin) || 0,
            disabled: p.disabled === true,
          })),
      })
      continue
    }

    layers.push({
      id: layer.id,
      name: layer.name,
      type: 'drawing',
      visible: layer.visible,
      locked: layer.locked,
      render: layer.render !== false,
      tiles: layer.data ? decompressTileData(layer.data, data.width, data.height) : {},
      offsetX: Number(layer.offsetX) || 0,
      offsetY: Number(layer.offsetY) || 0,
      scaleX: layer.scaleX == null ? 1 : Number(layer.scaleX),
      scaleY: layer.scaleY == null ? 1 : Number(layer.scaleY),
      rotation: Number(layer.rotation) || 0,
      // 新存档写单个 groupId；过渡期存档的 groupIds 数组读取时取第一个
      groupId: typeof layer.groupId === 'string'
        ? layer.groupId
        : (Array.isArray(layer.groupIds) && layer.groupIds.length > 0
          ? String(layer.groupIds[0])
          : undefined),
    })
  }

  // ====== 旧存档迁移：图片实例碰撞 → 形状层（世界坐标） ======
  const migratedPolygons: any[] = []
  let migratedSeq = 0
  for (const l of layers) {
    if (l.type !== 'image') continue
    const img = l.image
    if (!img) continue
    const rawList: any[] = Array.isArray(img.collisions) && img.collisions.length > 0
      ? img.collisions
      : (img.collisionShape?.points ? [{ shape: 'polygon', points: img.collisionShape.points }] : [])
    if (img.collisionEnabled && rawList.length > 0) {
      const iw = Math.max(1, Number(img.width) || 1)
      const ih = Math.max(1, Number(img.height) || 1)
      for (const raw of rawList) {
        const pts = (raw.points || []).filter((p: any) => Array.isArray(p) && p.length >= 2)
        if (pts.length < 3) continue
        // 兼容历史像素坐标
        const pixelLegacy = pts.some((p: number[]) => Math.abs(p[0]) > 1.5 || Math.abs(p[1]) > 1.5)
        const normalized = pixelLegacy
          ? pts.map((p: number[]) => [p[0] / iw, p[1] / ih])
          : pts
        const world = normalized.map((p: number[]) =>
          imageLocalToWorld(img, { x: p[0], y: p[1] })
        )
        migratedPolygons.push({
          id: `shp_mig_${migratedSeq++}`,
          shape: raw.shape === 'rect' ? 'rect' : 'polygon',
          points: world.map((w: any) => [w.x, w.y]),
          kind: 'solid',
          tag: '',
          oneWay: img.collisionType === '跳板',
          oneWayDirX: 0,
          oneWayDirY: 1,
          oneWayMargin: 0,
        })
      }
    }
    // 迁移后清除旧字段，避免重复迁移与引擎重复判定
    delete img.collisions
    delete img.collisionShape
    img.collisionEnabled = false
  }
  if (migratedPolygons.length > 0) {
    layers.push({
      id: layers.length,
      name: '碰撞',
      type: 'shape',
      visible: true,
      locked: false,
      shapes: migratedPolygons,
    })
  }

  // 拆分后 id 可能重复，按最终顺序统一重排
  layers.forEach((l, i) => { l.id = i })

  return {
    name: data.name,
    version: 5,
    width: data.width,
    height: data.height,
    tileSize: data.tileSize,
    gravity: data.gravity,
    // 旧存档没有该字段：沿用重力地图原来的钳制行为
    boundaryCollision: data.boundaryCollision ?? data.gravity ?? false,
    // 旧存档没有该字段：缺省视为开启（站在斜坡上不下滑）
    stopOnSlope: data.stopOnSlope ?? true,
    collisionType: data.collisionType || '图像',
    collisionEnabled: data.collisionEnabled || false,
    resources,
    layers,
    tileSets,
    tilesetGroups: Array.isArray(data.tilesetGroups)
      ? data.tilesetGroups.map(g => ({
          id: String(g.id),
          name: String(g.name || '图块集合'),
          locked: g.locked === true,
          disabled: g.disabled === true,
        }))
      : undefined,
    tilePalette: data.tilePalette,
    camera: data.camera
      ? {
          enabled: data.camera.enabled === true,
          target: typeof data.camera.target === 'string' ? data.camera.target : '',
          offsetX: Number(data.camera.offsetX) || 0,
          offsetY: Number(data.camera.offsetY) || 0,
          smoothing: Math.max(0, Math.min(1, Number(data.camera.smoothing) || 0)),
          limitBounds: data.camera.limitBounds !== false,
        }
      : undefined,
    markers: (Array.isArray(data.markers) ? data.markers : []).map((m, i) => ({
      id: m.id || `mk_legacy_${i}`,
      name: typeof m.name === 'string' && m.name.trim() ? m.name : `标记${i > 0 ? i : ''}`,
      x: Math.round(Number(m.x) || 0),
      y: Math.round(Number(m.y) || 0),
      type: typeof m.type === 'string' && m.type.trim() ? m.type : '出生点',
      visible: m.visible !== false,
      locked: m.locked === true,
      showName: m.showName !== false,
      showCoord: m.showCoord !== false,
    })),
  }
}
