import { invoke } from '@tauri-apps/api/core'
import { useMapStore } from '../stores/map'
import { useProjectStore } from '../stores/project'
import {
  dataUrlToBytes,
  derivedTilePath,
  detectSingleTileSize,
  fitTileSheet,
  isValidAssetTileSize,
  isValidMapTileSize,
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
 * 已占用的目标文件名（含并发导入中、还没写进 resources 的），按「项目|地图」分组。
 * 放在模块级：不同页面各自调用 useTileAssetImport() 时也能互相防重名。
 */
const reservedCopyNames = new Set<string>()

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

  /** 路径段是否安全：不允许分隔符、控制字符、`.` 与 `..`（防止写到项目目录之外） */
  function isSafePathSegment(seg: string): boolean {
    return !!seg
      && seg !== '.'
      && seg !== '..'
      && !/[\\/:*?"<>|\x00-\x1f]/.test(seg)
  }

  /** 复制到当前地图目录；同名不覆盖，自动加 -2 / -3 后缀 */
  async function copyToMapDir(absSrcPath: string, rawName: string): Promise<string> {
    const projectRoot = projectStore.root
    const mapName = mapStore.mapData.name
    if (!projectRoot || !mapName) throw new Error('地图未就绪')
    if (!isSafePathSegment(mapName)) {
      throw new Error(`地图名包含非法字符，无法导入图块: ${mapName}`)
    }

    // 文件名里的非法字符统一替换，避免在 Windows / macOS 上写失败或产生奇怪路径
    const safeName = rawName.replace(/[\\/:*?"<>|\x00-\x1f]/g, '_') || 'tile.png'
    const dot = safeName.lastIndexOf('.')
    const base = dot > 0 ? safeName.slice(0, dot) : safeName
    const ext = dot > 0 ? safeName.slice(dot) : '.png'

    const scope = `${projectRoot}|${mapName}`
    const used = new Set(mapStore.mapData.resources.map(r => r.path.split('/').pop() || ''))
    let fileName = `${base}${ext}`
    let seq = 2
    // 同时检查「已经在用的」和「正在并发导入、尚未落进 resources 的」名字
    while (used.has(fileName) || reservedCopyNames.has(`${scope}|${fileName}`)) {
      fileName = `${base}-${seq++}${ext}`
    }
    reservedCopyNames.add(`${scope}|${fileName}`)

    const relativePath = `assets/maps/${mapName}/images/${fileName}`
    try {
      await invoke<string>('copy_file_to_project', {
        src: absSrcPath,
        projectRoot,
        relativePath,
      })
    } catch (e) {
      // 复制失败释放占位，下次重试可以继续使用这个名字
      reservedCopyNames.delete(`${scope}|${fileName}`)
      throw e
    }
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

    if (img.width <= 0 || img.height <= 0) {
      console.error('[TileImport] 图片尺寸无效，已跳过:', absSrcPath, img.width, img.height)
      return null
    }

    const rawName = options.fileName?.split(/[\\/]/).pop() || 'tile.png'
    const kind = options.kind ?? (detectSingleTileSize(img.width, img.height) ? 'tile' : 'tileset')

    // 单图块必须是正方形：否则按一格切片会悄悄裁掉一半内容
    if (kind === 'tile' && img.width !== img.height) {
      console.error('[TileImport] 单图块必须是正方形图片，已跳过:', absSrcPath, `${img.width}×${img.height}`)
      return null
    }

    let originPath: string
    try {
      originPath = await copyToMapDir(absSrcPath, rawName)
    } catch (e) {
      console.error('[TileImport] 复制图块到项目失败:', e)
      return null
    }

    // 原始每格尺寸：图集取素材库设定值（只认常见取值，非法值按「未知」处理）；单图块取图片边长
    const native = kind === 'tileset'
      ? (isValidAssetTileSize(options.tileSize) ? options.tileSize : 0)
      : img.width

    if (kind === 'tileset' && native <= 0) {
      console.warn('[TileImport] 图集未设定图块尺寸，按当前格子 1:1 切割:', absSrcPath)
    }

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
        console.error('[TileImport] 写入尺寸适配图失败，已取消导入:', e)
        return null
      }
    }

    // 归一化失败（画布超限 / 尺寸异常）：拒绝导入，避免图块跨格导致碰撞错位
    console.error('[TileImport] 图块尺寸归一化失败（图片过大或尺寸异常），已取消导入:', absSrcPath, cut, grid)
    return null
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
    if (!projectRoot || !isValidMapTileSize(targetGrid)) return

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
        if (
          resource.path === originPath
          && resource.tileWidth === native
          && resource.tileHeight === native
          && resource.nativeTileSize === native
        ) continue
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

      // 已经是当前目标格子的派生图：跳过，避免重复读图 / 重复写盘
      const derivedPath = derivedTilePath(originPath, targetGrid)
      if (
        resource.path === derivedPath
        && resource.tileWidth === targetGrid
        && resource.tileHeight === targetGrid
        && resource.nativeTileSize === native
      ) continue

      let dataUrl: string
      try {
        dataUrl = await invoke<string>('read_image_as_data_url', { path: `${projectRoot}/${originPath}` })
      } catch {
        continue
      }

      const fitted = await fitOrNull(dataUrl, native, targetGrid)
      if (!fitted) continue

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
