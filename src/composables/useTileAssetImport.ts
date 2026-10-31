import { invoke } from '@tauri-apps/api/core'
import { useMapStore } from '../stores/map'
import { useProjectStore } from '../stores/project'
import {
  canFitTileSize,
  dataUrlToBytes,
  derivedTilePath,
  detectSingleTileSize,
  fitTileSheet,
  loadImageElement,
} from '../utils/tileAssetFit'

export interface TileImportOptions {
  /** 资源库里的文件名（含扩展名），用于项目内命名 */
  fileName?: string
  /**
   * 素材类型：内置库按目录区分（tiles=单图块 / tilesets=图集）。
   * 缺省时按图片自动判断：小正方形图视为单图块，其余视为图集。
   */
  kind?: 'tile' | 'tileset'
}

export interface ImportedTileAsset {
  /** 实际使用的图片（单图块可能是缩放后的派生图；图集永远是原图） */
  path: string
  tileWidth: number
  tileHeight: number
  /** 原始图片：改格子尺寸时从这里重新处理 */
  originPath: string
  /** 只有单图块才有原始尺寸；图集不推断尺寸 */
  nativeTileSize?: number
  assetKind: 'tile' | 'tileset'
}

/**
 * 图块素材导入：单图块与图集分开处理。
 *
 * 单图块（tile）：
 * - 图片边长就是图块尺寸，可以判断；
 * - 和地图格子不一致时按整数倍缩放适配；空地图可以直接跟随素材尺寸。
 *
 * 图集（tileset）：
 * - 图片里看不出每格多大，**绝不推断、绝不缩放**；
 * - 只按当前地图格子切；切错了就改地图的图块尺寸，会从原图重新切一遍。
 */
export function useTileAssetImport() {
  const mapStore = useMapStore()
  const projectStore = useProjectStore()

  /** 空地图才允许自动改网格：用户手动指定过格子尺寸、已有图块素材或画过图块时都必须保持网格不变 */
  function canAutoSwitchGrid(): boolean {
    const data = mapStore.mapData
    if (data.tileSizeExplicit) return false
    if (data.resources.some(r => r.resourceType !== 'image')) return false
    return !data.layers.some(l => l.type === 'drawing' && Object.keys(l.tiles ?? {}).length > 0)
  }

  /** 复制到当前地图目录；同名不覆盖，自动加 -2 / -3 后缀 */
  async function copyToMapDir(absSrcPath: string, rawName: string): Promise<string> {
    const projectRoot = projectStore.root
    const mapName = mapStore.mapData.name
    if (!projectRoot || !mapName) throw new Error('地图未就绪')

    const dot = rawName.lastIndexOf('.')
    const base = dot > 0 ? rawName.slice(0, dot) : rawName
    const ext = dot > 0 ? rawName.slice(dot) : '.png'
    const used = new Set(mapStore.mapData.resources.map(r => r.path.split('/').pop() || ''))
    let fileName = `${base}${ext}`
    let seq = 2
    while (used.has(fileName)) fileName = `${base}-${seq++}${ext}`

    const relativePath = `assets/maps/${mapName}/images/${fileName}`
    await invoke<string>('copy_file_to_project', {
      src: absSrcPath,
      projectRoot,
      relativePath,
    })
    return relativePath
  }

  async function importTileImage(
    absSrcPath: string,
    options: TileImportOptions = {},
  ): Promise<ImportedTileAsset | null> {
    let dataUrl: string
    try {
      dataUrl = await invoke<string>('read_image_as_data_url', { path: absSrcPath })
    } catch (e) {
      console.error('[TileImport] 读取图块失败:', absSrcPath, e)
      return null
    }

    let img: HTMLImageElement
    try {
      img = await loadImageElement(dataUrl)
    } catch {
      return null
    }

    const rawName = options.fileName?.split(/[\\/]/).pop() || 'tile.png'
    const kind = options.kind ?? (detectSingleTileSize(img.width, img.height) ? 'tile' : 'tileset')

    let originPath: string
    try {
      originPath = await copyToMapDir(absSrcPath, rawName)
    } catch (e) {
      console.error('[TileImport] 复制图块到项目失败:', e)
      return null
    }

    // 图集：不推断尺寸、不缩放，直接按当前地图格子切
    if (kind === 'tileset') {
      const grid = mapStore.mapData.tileSize
      return {
        path: originPath,
        tileWidth: grid,
        tileHeight: grid,
        originPath,
        assetKind: 'tileset',
      }
    }

    // 单图块：图片边长就是原始尺寸
    const gridBefore = mapStore.mapData.tileSize
    const native = detectSingleTileSize(img.width, img.height) ?? gridBefore
    if (native !== gridBefore && canAutoSwitchGrid()) {
      mapStore.updateTileSize(native)
    }
    const grid = mapStore.mapData.tileSize

    if (grid === native) {
      return {
        path: originPath,
        tileWidth: native,
        tileHeight: native,
        originPath,
        nativeTileSize: native,
        assetKind: 'tile',
      }
    }

    const fitted = await fitOrNull(dataUrl, native, grid)
    if (!fitted) {
      console.warn('[TileImport] 单图块尺寸无法整数倍换算，按原尺寸导入:', absSrcPath, native, grid)
      return {
        path: originPath,
        tileWidth: native,
        tileHeight: native,
        originPath,
        nativeTileSize: native,
        assetKind: 'tile',
      }
    }

    const derivedPath = derivedTilePath(originPath, grid)
    try {
      await invoke('write_binary', {
        path: `${projectStore.root}/${derivedPath}`,
        data: dataUrlToBytes(fitted.dataUrl),
      })
    } catch (e) {
      console.error('[TileImport] 写入适配图块失败:', e)
      return {
        path: originPath,
        tileWidth: native,
        tileHeight: native,
        originPath,
        nativeTileSize: native,
        assetKind: 'tile',
      }
    }

    return {
      path: derivedPath,
      tileWidth: grid,
      tileHeight: grid,
      originPath,
      nativeTileSize: native,
      assetKind: 'tile',
    }
  }

  async function fitOrNull(dataUrl: string, native: number, grid: number) {
    try {
      return await fitTileSheet(dataUrl, native, grid)
    } catch {
      return null
    }
  }

  /**
   * 改格子尺寸后，把已有素材按新的网格重新处理：
   * - 图集：从原图按新格子重新切（不缩放，切错了再改尺寸即可）；
   * - 单图块：从原图按整数倍缩放。
   */
  async function refitTilesetsToGrid(targetGrid: number): Promise<void> {
    const projectRoot = projectStore.root
    if (!projectRoot || !Number.isFinite(targetGrid) || targetGrid <= 0) return

    const resources = mapStore.mapData.resources.filter(
      r => r.resourceType !== 'image' && r.path.startsWith('assets/'),
    )

    let changed = false
    for (const resource of resources) {
      const kind = await resolveAssetKind(resource)
      if (kind === 'tileset') {
        const originPath = resource.originPath ?? resource.path
        if (
          resource.tileWidth === targetGrid
          && resource.tileHeight === targetGrid
          && resource.path === originPath
        ) continue

        // 只换切片尺寸与图片路径，不动像素：相当于用新格子把原图重新切一遍
        mapStore.setResourceAsset(resource.id, {
          path: originPath,
          tileWidth: targetGrid,
          tileHeight: targetGrid,
          originPath,
          nativeTileSize: null,
        })
        changed = true
        continue
      }

      const native = resource.nativeTileSize
      const originPath = resource.originPath
      if (!native || !originPath || !canFitTileSize(native, targetGrid)) continue

      if (targetGrid === native) {
        if (resource.path === originPath && resource.tileWidth === native) continue
        mapStore.setResourceAsset(resource.id, {
          path: originPath,
          tileWidth: native,
          tileHeight: native,
          originPath,
          nativeTileSize: native,
        })
        changed = true
        continue
      }

      let dataUrl: string
      try {
        dataUrl = await invoke<string>('read_image_as_data_url', { path: `${projectRoot}/${originPath}` })
      } catch {
        continue
      }

      const fitted = await fitOrNull(dataUrl, native, targetGrid)
      if (!fitted) continue

      const derivedPath = derivedTilePath(originPath, targetGrid)
      try {
        await invoke('write_binary', {
          path: `${projectRoot}/${derivedPath}`,
          data: dataUrlToBytes(fitted.dataUrl),
        })
      } catch {
        continue
      }

      mapStore.setResourceAsset(resource.id, {
        path: derivedPath,
        tileWidth: targetGrid,
        tileHeight: targetGrid,
        originPath,
        nativeTileSize: native,
      })
      changed = true
    }

    // 全部换完再通知一次，避免每换一个素材就触发一次画布全量重建
    if (changed) mapStore.notifyTileAssetsChanged()
  }

  /**
   * 判断素材类型。旧数据没有 assetKind：
   * 原图正好是「原始尺寸 × 原始尺寸」的正方形 → 单图块，否则按图集处理。
   */
  async function resolveAssetKind(resource: {
    assetKind?: 'tile' | 'tileset'
    nativeTileSize?: number
    originPath?: string
    path: string
  }): Promise<'tile' | 'tileset'> {
    if (resource.assetKind) return resource.assetKind
    const native = resource.nativeTileSize
    const originPath = resource.originPath
    if (!native || !originPath) return 'tileset'
    try {
      const dataUrl = await invoke<string>('read_image_as_data_url', {
        path: `${projectStore.root}/${originPath}`,
      })
      const img = await loadImageElement(dataUrl)
      if (img.width === native && img.height === native) return 'tile'
    } catch {
      // 读不到原图就按图集处理（不会缩放，最安全）
    }
    return 'tileset'
  }

  return { importTileImage, refitTilesetsToGrid }
}
