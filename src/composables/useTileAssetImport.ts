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
  /** 已知的原始图块尺寸（内置资源库按目录约定给出）；缺省时按图片自动判断 */
  nativeTileSize?: number
}

export interface ImportedTileAsset {
  /** 实际使用的图片（可能是适配后的派生图） */
  path: string
  tileWidth: number
  tileHeight: number
  /** 原始图片：改格子尺寸时从这里重新换算，避免反复缩放 */
  originPath: string
  nativeTileSize: number
}

/**
 * 图块素材导入：把任意来源的图块统一换算成当前地图的格子尺寸。
 *
 * 规则：
 * - 空地图（还没有任何图块素材、也没画过图块）→ 直接把格子尺寸改成素材自带的尺寸；
 * - 已有网格且是整数倍关系 → 按当前网格重新缩放出一份派生图，原图保留；
 * - 无法换算（非整数倍）→ 按原尺寸导入，至少不把图切成碎片。
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

    const gridBefore = mapStore.mapData.tileSize
    const declared = options.nativeTileSize && options.nativeTileSize > 0
      ? Math.round(options.nativeTileSize)
      : null
    // 未知尺寸时：小正方形图按「单图块」处理；其余视为已按当前网格切好
    const native = declared ?? detectSingleTileSize(img.width, img.height) ?? gridBefore

    if (native !== gridBefore && canAutoSwitchGrid()) {
      mapStore.updateTileSize(native)
    }
    const grid = mapStore.mapData.tileSize

    const rawName = options.fileName?.split(/[\\/]/).pop() || 'tile.png'
    let originPath: string
    try {
      originPath = await copyToMapDir(absSrcPath, rawName)
    } catch (e) {
      console.error('[TileImport] 复制图块到项目失败:', e)
      return null
    }

    if (grid === native) {
      return { path: originPath, tileWidth: grid, tileHeight: grid, originPath, nativeTileSize: native }
    }

    const fitted = await fitTileSheet(dataUrl, native, grid)
    if (!fitted) {
      // 非整数倍：按原尺寸导入，避免被切成碎片
      console.warn('[TileImport] 图块尺寸无法整数倍换算，按原尺寸导入:', absSrcPath, native, grid)
      return { path: originPath, tileWidth: native, tileHeight: native, originPath, nativeTileSize: native }
    }

    const derivedPath = derivedTilePath(originPath, grid)
    try {
      await invoke('write_binary', {
        path: `${projectStore.root}/${derivedPath}`,
        data: dataUrlToBytes(fitted.dataUrl),
      })
    } catch (e) {
      console.error('[TileImport] 写入适配图块失败:', e)
      return { path: originPath, tileWidth: native, tileHeight: native, originPath, nativeTileSize: native }
    }

    return {
      path: derivedPath,
      tileWidth: grid,
      tileHeight: grid,
      originPath,
      nativeTileSize: native,
    }
  }

  /**
   * 改格子尺寸后，把已有素材按新的网格重新换算（始终从原图出发，反复切换也不会变糊）。
   * @param previousGrid 改动前的格子尺寸：老素材没有登记原始尺寸时，用它作为原始尺寸补登记
   */
  async function refitTilesetsToGrid(targetGrid: number, previousGrid?: number): Promise<void> {
    const projectRoot = projectStore.root
    if (!projectRoot || !Number.isFinite(targetGrid) || targetGrid <= 0) return

    const resources = mapStore.mapData.resources.filter(r => r.resourceType !== 'image')

    let changed = false
    for (const resource of resources) {
      let native = resource.nativeTileSize
      let originPath = resource.originPath

      // 老素材（本次改动前导入）没有登记原图与尺寸：把当前图当作原图，按旧格子尺寸补登记
      if ((!native || !originPath) && previousGrid && resource.tileWidth === previousGrid) {
        native = previousGrid
        originPath = resource.path
      }
      if (!native || !originPath) continue
      if (!canFitTileSize(native, targetGrid)) continue

      // 回到原始尺寸：直接指回原图，不需要派生文件
      if (targetGrid === native) {
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

      const fitted = await fitTileSheet(dataUrl, native, targetGrid)
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

  return { importTileImage, refitTilesetsToGrid }
}
