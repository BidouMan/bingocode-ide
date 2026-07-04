import * as pako from 'pako'

export interface MapSaveData {
  name: string
  width: number
  height: number
  tileSize: number
  offsetX: number
  offsetY: number
  gravity: boolean
  collisionType: string
  collisionEnabled: boolean
  renderMode?: 'smooth' | 'pixelated'
  layers: LayerSaveData[]
  tilesets: TilesetSaveData[]
}

export interface LayerSaveData {
  id: number
  name: string
  type: 'tilelayer' | 'imagelayer'
  visible: boolean
  locked: boolean
  data?: string
  images?: ImageSaveData[]
  resources?: ResourceSaveData[]
}

export interface ResourceSaveData {
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
  collisionShape?: { points: number[][] }
}

export interface TilesetSaveData {
  name: string
  image: string
  firstgid: number
  tileWidth: number
  tileHeight: number
  collisionType: string
  collisionEnabled: boolean
  tiles?: { id: number; collision: string; tag?: string }[]
}

export interface MapLoadData {
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
  renderMode?: 'smooth' | 'pixelated'
  layers: any[]
  tileSets: any[]
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
  const tilesets: TilesetSaveData[] = mapData.tileSets.map((ts: any) => {
    return {
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
        tag: t.tag || undefined,
      })),
    }
  })

  const layers: LayerSaveData[] = mapData.layers.map((layer: any) => {
    const base: LayerSaveData = {
      id: layer.id,
      name: layer.name,
      type: layer.type === 'image' ? 'imagelayer' : 'tilelayer',
      visible: layer.visible,
      locked: layer.locked,
    }

    if (layer.type !== 'image') {
      base.data = compressTileData(layer.tiles, mapData.width, mapData.height)
    }

    if (layer.images?.length) {
      base.images = layer.images.map((img: any) => ({
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
        collisionEnabled: img.collisionEnabled || false,
        collisionShape: img.collisionShape,
      }))
    }

    if (layer.resources?.length) {
      base.resources = layer.resources.map((r: any) => ({
        name: r.name,
        path: r.path,
        resourceType: r.resourceType,
        tileWidth: r.tileWidth,
        tileHeight: r.tileHeight,
        collisionType: r.collisionType || '图像',
        collisionEnabled: r.collisionEnabled || false,
        collisionShape: r.collisionShape,
      }))
    }

    return base
  })

  return {
    name: mapData.name,
    width: mapData.width,
    height: mapData.height,
    tileSize: mapData.tileSize,
    offsetX: mapData.offsetX,
    offsetY: mapData.offsetY,
    gravity: mapData.gravity,
    collisionType: mapData.collisionType || '图像',
    collisionEnabled: mapData.collisionEnabled || false,
    layers,
    tilesets,
  }
}

/**
 * 从保存格式转换为编辑器内部格式
 */
export function deserializeMap(data: MapSaveData): MapLoadData {
  const tileSets = data.tilesets.map(ts => ({
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
      collisionType: t.collision,
    })) || [],
  }))

  const layers = data.layers.map(layer => {
    const base: any = {
      id: layer.id,
      name: layer.name,
      type: layer.type === 'imagelayer' ? 'image' : 'drawing',
      visible: layer.visible,
      locked: layer.locked,
      resources: (layer.resources || []).map((r: any) => ({
        name: r.name,
        path: r.path,
        resourceType: r.resourceType,
        tileWidth: r.tileWidth,
        tileHeight: r.tileHeight,
        collisionType: r.collisionType || '图像',
        collisionEnabled: r.collisionEnabled || false,
        collisionShape: r.collisionShape,
        tileSetIndex: 0,
      })),
      images: layer.images || [],
    }

    if (layer.type !== 'imagelayer' && layer.data) {
      base.tiles = decompressTileData(layer.data, data.width, data.height)
    } else {
      base.tiles = {}
    }

    return base
  })

  return {
    name: data.name,
    version: 5,
    width: data.width,
    height: data.height,
    tileSize: data.tileSize,
    offsetX: data.offsetX,
    offsetY: data.offsetY,
    gravity: data.gravity,
    collisionType: data.collisionType || '图像',
    collisionEnabled: data.collisionEnabled || false,
    layers,
    tileSets,
  }
}
