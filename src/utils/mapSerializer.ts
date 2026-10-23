import * as pako from 'pako'
import { imageLocalToWorld } from './mapImageGeometry'

export interface MapSaveData {
  name: string
  width: number
  height: number
  tileSize: number
  gravity: boolean
  collisionType: string
  collisionEnabled: boolean
  renderMode?: 'smooth' | 'pixelated'
  // 地图级素材库（新增）；旧存档没有该字段时从各图层收集
  resources?: ResourceSaveData[]
  layers: LayerSaveData[]
  tilesets: TilesetSaveData[]
  // 图块笔刷调色板（顺序=界面显示顺序）
  tilePalette?: { resourceId: string; tileIndex: number }[]
}

export interface LayerSaveData {
  id: number
  name: string
  type: 'tilelayer' | 'imagelayer' | 'collisionlayer'
  visible: boolean
  locked: boolean
  data?: string
  images?: ImageSaveData[]
  resources?: ResourceSaveData[]
  // 碰撞层：世界坐标碰撞多边形
  polygons?: CollisionPolygonSaveData[]
}

export interface CollisionPolygonSaveData {
  id: string
  shape: 'rect' | 'circle' | 'capsule' | 'polygon'
  points: number[][]
  collisionType: string
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
  tiles?: { id: number; collision: string; tag?: string; collisionType?: string; collisionShape?: { points: number[][] } }[]
}

export interface MapLoadData {
  name: string
  version: number
  width: number
  height: number
  tileSize: number
  gravity: boolean
  collisionType: string
  collisionEnabled: boolean
  renderMode?: 'smooth' | 'pixelated'
  resources: any[]
  layers: any[]
  tileSets: any[]
  tilePalette?: { resourceId: string; tileIndex: number }[]
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
      type: layer.type === 'image' ? 'imagelayer' : layer.type === 'collision' ? 'collisionlayer' : 'tilelayer',
      visible: layer.visible,
      locked: layer.locked,
    }

    if (layer.type === 'collision') {
      base.polygons = (layer.polygons || []).map((poly: any) => ({
        id: poly.id,
        shape: poly.shape,
        points: poly.points,
        collisionType: poly.collisionType || '墙体',
        disabled: poly.disabled === true,
      }))
      return base
    }

    if (layer.type === 'drawing') {
      base.data = compressTileData(layer.tiles, mapData.width, mapData.height)
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
    collisionType: mapData.collisionType || '图像',
    collisionEnabled: mapData.collisionEnabled || false,
    resources: mapResources,
    layers,
    tilesets,
    tilePalette: mapData.tilePalette,
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
          image: img,
        })
      })
      continue
    }

    if (layer.type === 'collisionlayer') {
      layers.push({
        id: layer.id,
        name: layer.name || '碰撞',
        type: 'collision',
        visible: layer.visible,
        locked: layer.locked,
        polygons: (layer.polygons || [])
          .filter(p => Array.isArray(p.points) && p.points.length >= 3)
          .map(p => ({
            id: p.id || `col_${Math.random().toString(36).slice(2, 8)}`,
            shape: p.shape === 'rect' || p.shape === 'circle' || p.shape === 'capsule' ? p.shape : 'polygon',
            points: p.points.map(pt => [Number(pt[0]) || 0, Number(pt[1]) || 0]),
            collisionType: p.collisionType || '墙体',
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
      tiles: layer.data ? decompressTileData(layer.data, data.width, data.height) : {},
    })
  }

  // ====== 旧存档迁移：图片实例碰撞 → 碰撞层（世界坐标） ======
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
          id: `col_mig_${migratedSeq++}`,
          shape: raw.shape === 'rect' ? 'rect' : 'polygon',
          points: world.map((w: any) => [w.x, w.y]),
          collisionType: img.collisionType && img.collisionType !== '图像' ? img.collisionType : '墙体',
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
      type: 'collision',
      visible: true,
      locked: false,
      polygons: migratedPolygons,
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
    collisionType: data.collisionType || '图像',
    collisionEnabled: data.collisionEnabled || false,
    resources,
    layers,
    tileSets,
    tilePalette: data.tilePalette,
  }
}
