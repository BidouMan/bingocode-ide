import { invoke } from '@tauri-apps/api/core'
import { useMapStore } from '../stores/map'
import { useProjectStore } from '../stores/project'
import {
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
  /**
   * 图集在素材库里预先设定的每格边长（像素）；没设定时素材库会传默认值 16。
   * 只有本地直接上传的图集缺省，此时退回「按当前地图格子切」。
   */
  tileSize?: number
}

export interface ImportedTileAsset {
  /** 实际使用的图片（单图块可能是缩放后的派生图；图集永远是原图） */
  path: string
  tileWidth: number
  tileHeight: number
  /** 原始图片：改格子尺寸时从这里重新处理 */
  originPath: string
  /** 原始每格尺寸：单图块按图片边长识别；图集仅在素材库设定了尺寸时才有值 */
  nativeTileSize?: number
  assetKind: 'tile' | 'tileset'
}

/**
 * 图块素材导入：所有素材最终都换算成地图唯一的格子尺寸。
 *
 * 规则（对使用者透明，不需要理解尺寸）：
 * 1. 第一次导入图块素材时，用素材自己的尺寸决定地图格子并锁定，之后不再自动改变；
 * 2. 之后导入的素材不管原始尺寸多大，都自动归一化到当前格子（整数倍整图缩放，
 *    非整数倍逐块缩放），保证永远对齐、不会出现跨格/重叠；
 * 3. 用户手动改过地图格子后，以手动值为准，已有素材跟着重新换算。
 *
 * - 单图块：图片边长就是原始尺寸；
 * - 图集：素材库设定值（未设定按默认 16），本地直接上传的未知尺寸按当前格子切。
 */
export function useTileAssetImport() {
  const mapStore = useMapStore()
  const projectStore = useProjectStore()

  /**
   * 是否「第一次导入图块素材」：还没画过图块、没有任何图块素材，且用户没手动指定过格子。
   * 只有这种情况才允许自动决定地图格子。
   */
  function isFirstTileImport(): boolean {
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

    // 原始每格尺寸：图集取素材库设定值（0 = 未知）；单图块取图片边长
    const native = kind === 'tileset'
      ? (options.tileSize && Number.isFinite(options.tileSize) ? Math.round(options.tileSize) : 0)
      : (img.width === img.height
        ? img.width
        : (detectSingleTileSize(img.width, img.height) ?? mapStore.mapData.tileSize))

    // 第一次导入图块素材：用素材尺寸决定地图格子并锁定，之后导入不再改格子
    if (native > 0 && isFirstTileImport()) {
      mapStore.updateTileSize(native, true)
    }
    const grid = mapStore.mapData.tileSize

    // 未知尺寸（本地直接上传的图集）只能按当前地图格子切，改格子时再从原图重切
    const cut = native > 0 ? native : grid

    // 尺寸一致：原图直接切
    if (cut === grid) {
      return {
        path: originPath,
        tileWidth: grid,
        tileHeight: grid,
        originPath,
        ...(native > 0 ? { nativeTileSize: native } : {}),
        assetKind: kind,
      }
    }

    // 尺寸不同：整张图归一化到当前格子（整数倍整图缩放，非整数倍逐块缩放）
    const fitted = await fitOrNull(dataUrl, cut, grid)
    if (fitted) {
      const derivedPath = derivedTilePath(originPath, grid)
      try {
        await invoke('write_binary', {
          path: `${projectStore.root}/${derivedPath}`,
          data: dataUrlToBytes(fitted.dataUrl),
        })
        return {
          path: derivedPath,
          tileWidth: grid,
          tileHeight: grid,
          originPath,
          nativeTileSize: cut,
          assetKind: kind,
        }
      } catch (e) {
        console.error('[TileImport] 写入尺寸适配图失败:', e)
      }
    }

    // 归一化失败（写入失败 / 画布超限）：保留原始像素按素材尺寸切，至少内容完整
    console.warn('[TileImport] 图块尺寸归一化失败，按原始尺寸导入:', absSrcPath, cut, grid)
    return {
      path: originPath,
      tileWidth: cut,
      tileHeight: cut,
      originPath,
      ...(native > 0 ? { nativeTileSize: native } : {}),
      assetKind: kind,
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
   * - 已知原始尺寸的素材（单图块 / 有图块尺寸的图集）：从原图按最近邻归一化，
   *   整数倍整图缩放，非整数倍逐块缩放，保证每块都正好落在新格子内；
   * - 没有原始尺寸的旧素材：无法精确换算，从原图按新格子切/画，至少保证对齐。
   */
  async function refitTilesetsToGrid(targetGrid: number): Promise<void> {
    const projectRoot = projectStore.root
    if (!projectRoot || !Number.isFinite(targetGrid) || targetGrid <= 0) return

    const resources = mapStore.mapData.resources.filter(
      r => r.resourceType !== 'image' && r.path.startsWith('assets/'),
    )

    let changed = false
    for (const resource of resources) {
      const native = resource.nativeTileSize
      const originPath = resource.originPath ?? resource.path

      // 旧数据没有原始尺寸：无法精确换算，直接按新格子切/画原图，至少保证对齐
      if (!native) {
        if (
          resource.tileWidth === targetGrid
          && resource.tileHeight === targetGrid
          && resource.path === originPath
        ) continue

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

      // 已知原始每格尺寸（单图块 / 设定了图块尺寸的图集）：按最近邻归一化到新格子
      if (!resource.originPath) continue

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

  return { importTileImage, refitTilesetsToGrid }
}
