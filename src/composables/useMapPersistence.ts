import { invoke } from '@tauri-apps/api/core'
import JSZip from 'jszip'
import type { MapData } from '../stores/map'
import { useMapStore } from '../stores/map'
import { useResourceStore } from '../stores/resource'
import { useProjectStore } from '../stores/project'
import { serializeMap, deserializeMap } from '../utils/mapSerializer'

interface MapPersistenceOptions {
  /** 画布缩略图（保存 map.json 时一并写入 thumbnail.png） */
  getThumbnailDataUrl: () => string | null
  /** 缩略图写回资源列表缓存 */
  onThumbnailUpdated?: (itemId: string, dataUrl: string) => void
}

/**
 * 地图持久化：map.json 读写、.bgm 修复、相对路径解析、空地图结构。
 * 页面组件只负责编排，不再直接处理文件 IO。
 */
export function useMapPersistence(options: MapPersistenceOptions) {
  const mapStore = useMapStore()
  const resourceStore = useResourceStore()
  const projectStore = useProjectStore()

  function mapDirPath(mapName: string): string {
    return `${projectStore.root}/assets/maps/${mapName}`
  }

  function mapJsonPath(mapName: string): string {
    return `${mapDirPath(mapName)}/map.json`
  }

  async function saveMapToProject(mapName?: string): Promise<void> {
    const name = mapName ?? mapStore.mapData.name
    if (!name) {
      console.warn('[MapEditor] saveMapToProject: 地图名为空，跳过保存')
      return
    }
    if (!projectStore.root) {
      await projectStore.initProject()
    }
    if (!projectStore.root) {
      console.warn('[MapEditor] saveMapToProject: 项目目录未就绪，无法保存')
      return
    }

    const dirPath = mapDirPath(name)
    const savePath = mapJsonPath(name)
    try {
      const saveData = serializeMap(mapStore.mapData)
      await invoke('write_file', { path: savePath, content: JSON.stringify(saveData) })

      // 同时生成 thumbnail.png 快照
      const thumbDataUrl = options.getThumbnailDataUrl()
      if (thumbDataUrl && thumbDataUrl.startsWith('data:image/')) {
        const base64 = thumbDataUrl.split(',')[1]
        const raw = Uint8Array.from(atob(base64), c => c.charCodeAt(0))
        await invoke('write_binary', { path: `${dirPath}/thumbnail.png`, data: Array.from(raw) })

        // 直接把刚生成的快照写进资源列表缩略图缓存（经 MainLayout）
        const savedItem = resourceStore.maps.find(m => m.name === name)
        if (savedItem) options.onThumbnailUpdated?.(savedItem.id, thumbDataUrl)
      }

      // 更新 resource store 中该 map 的 path，供左侧缩略图加载
      const item = resourceStore.maps.find(m => m.name === name)
      if (item) item.path = dirPath
    } catch (e) {
      console.error('[MapEditor] 保存地图到项目目录失败:', e)
    }
  }

  async function loadMapFromProject(itemId: string): Promise<boolean> {
    if (!projectStore.root) {
      await projectStore.initProject()
    }
    if (!projectStore.root) return false

    // 优先从预解析缓存读取
    const cached = resourceStore.getCachedMapData(itemId)
    if (cached) {
      // 资源名为准：缓存内 name 可能是改名前的残留，避免保存写回旧目录
      const cachedItem = resourceStore.maps.find(m => m.id === itemId)
      if (cachedItem && cached.name !== cachedItem.name) cached.name = cachedItem.name
      mapStore.loadMap(cached)
      return true
    }

    const item = resourceStore.maps.find(m => m.id === itemId)
    const mapName = item?.name ?? mapStore.mapData.name
    if (!mapName) return false
    const filePath = mapJsonPath(mapName)
    try {
      const exists = await invoke<boolean>('path_exists', { path: filePath })
      if (!exists) return false
      const json = await invoke<string>('read_file', { path: filePath })
      const saveData = JSON.parse(json)

      // Rust zip 0.6 解压 .bgm 时 map.json 可能丢失数据（tilesets/layers 被清空）
      // 必须 tilesets 和 layers 双双为空才判定为解压损坏
      if ((!saveData.tilesets || saveData.tilesets.length === 0)
        && (!saveData.layers || saveData.layers.length === 0)) {
        const fixed = await tryReadMapFromBgm(mapName)
        if (fixed) {
          await invoke('write_file', { path: filePath, content: JSON.stringify(fixed, null, 2) })
          Object.assign(saveData, fixed)
        }
      }

      const mapData = deserializeMap(saveData)
      // 资源名为准：存档内 name 可能是改名前的残留，避免保存写回旧目录
      mapData.name = mapName
      resolveRelativePaths(mapData, mapDirPath(mapName))
      mapStore.loadMap(mapData)
      return true
    } catch (e) {
      console.error(`[MapEditor] loadMapFromProject: 失败 path=${filePath}`, e)
      return false
    }
  }

  // 尝试从原始 .bgm zip 文件读取 map.json（修复 Rust zip 解压 bug）
  async function tryReadMapFromBgm(mapName: string): Promise<any | null> {
    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')
      const bgmPath = `${engineDir}/maps/packages/${mapName}.bgm`
      const bgmExists = await invoke<boolean>('path_exists', { path: bgmPath })
      if (!bgmExists) return null
      const data = await invoke<number[]>('read_binary', { path: bgmPath })
      const zip = await JSZip.loadAsync(new Uint8Array(data))
      const entry = zip.file('map.json')
      if (!entry) return null
      return JSON.parse(await entry.async('text'))
    } catch {
      return null
    }
  }

  // 将相对路径解析为绝对路径
  function resolveRelativePaths(mapData: any, dir: string) {
    for (const ts of mapData.tileSets) {
      if (ts.imagePath && !ts.imagePath.startsWith('/') && !ts.imagePath.startsWith('assets/') && !ts.imagePath.startsWith('/maps/')) {
        ts.imagePath = `${dir}/${ts.imagePath}`
      }
    }
    for (const res of mapData.resources || []) {
      if (res.path && !res.path.startsWith('/') && !res.path.startsWith('assets/') && !res.path.startsWith('/maps/')) {
        res.path = `${dir}/${res.path}`
      }
    }
    for (const layer of mapData.layers) {
      if (layer.type === 'image' && layer.image?.imagePath
        && !layer.image.imagePath.startsWith('/') && !layer.image.imagePath.startsWith('assets/') && !layer.image.imagePath.startsWith('/maps/')) {
        layer.image.imagePath = `${dir}/${layer.image.imagePath}`
      }
    }
  }

  function createEmptyMapData(name: string): MapData {
    return {
      name,
      version: 5,
      width: 40,
      height: 30,
      tileSize: 16,
      gravity: false,
      boundaryCollision: true,
      collisionType: '图像',
      collisionEnabled: false,
      resources: [],
      // 空地图不带图层，进入编辑页后由编辑器自动创建默认图像图层
      layers: [],
      tileSets: [],
    }
  }

  return {
    mapDirPath,
    mapJsonPath,
    saveMapToProject,
    loadMapFromProject,
    resolveRelativePaths,
    createEmptyMapData,
  }
}
