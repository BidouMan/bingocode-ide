import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'

export interface MapResourceItem {
  name: string
  path: string
  category: 'images' | 'tiles' | 'tilesets'
  thumbnail: string
  /**
   * 素材自带的图块尺寸（格子边长的像素值）。
   * - tiles/ 下的单张图块：缺省，导入时按图片边长自动判断
   * - tilesets/<尺寸>/ 下的图集：目录名即尺寸
   * - tilesets/ 根目录下的图集：按 16 处理（兼容旧素材）
   */
  nativeTileSize?: number
}

// 支持的图片扩展名（自动扫描时过滤）
const IMAGE_EXTS = /\.(png|jpe?g|gif|webp|bmp|svg)$/i

// 路径拼接：兼容 Windows（反斜杠）和 Unix（正斜杠）
function joinPath(base: string, ...parts: string[]): string {
  const sep = base.includes('\\') && !base.includes('/') ? '\\' : '/'
  const cleanBase = base.replace(/[\\/]+$/, '')
  const cleanParts = parts.map(p => p.replace(/^[\\/]+/, '').replace(/[\\/]+$/, ''))
  return [cleanBase, ...cleanParts].join(sep)
}

export const useMapResourceLibStore = defineStore('mapResourceLib', () => {
  const items = ref<MapResourceItem[]>([])

  async function loadBuiltinResources() {
    // 每次打开面板都重新扫描：read_dir 为微秒级操作，缩略图走 WebView 缓存的文件 URL，
    // 重扫零负担；这样才能让用户新放入的图片无需重启即被看到
    const engineDir = await invoke<string>('get_engine_assets_dir')

    // 自动扫描 maps/images、maps/tiles、maps/tilesets 三个目录
    // list_dir 对子目录返回 "name/" 后缀
    const categories: MapResourceItem['category'][] = ['images', 'tiles', 'tilesets']
    const results: MapResourceItem[] = []

    /**
     * 扫描一个分类目录。tilesets 允许一层子目录，目录名即图块尺寸：
     * tilesets/16/*.png、tilesets/32/*.png。根目录下的旧图集按 16 处理。
     */
    async function scanCategory(
      category: MapResourceItem['category'],
      dirPath: string,
      urlPrefix: string,
      nativeTileSize?: number,
      allowSubDir = true,
    ) {
      let files: string[]
      try {
        files = await invoke<string[]>('list_dir', { path: dirPath })
      } catch (e) {
        console.warn(`[MapResourceLib] 扫描 ${dirPath} 失败:`, e)
        return
      }
      for (const file of files) {
        if (file.endsWith('/')) {
          if (!allowSubDir || category !== 'tilesets') continue
          const dirName = file.slice(0, -1)
          const declared = Number(dirName)
          await scanCategory(
            category,
            joinPath(dirPath, dirName),
            `${urlPrefix}/${dirName}`,
            Number.isFinite(declared) && declared > 0 ? declared : nativeTileSize,
            false,
          )
          continue
        }
        if (!IMAGE_EXTS.test(file)) continue
        results.push({
          name: file.replace(IMAGE_EXTS, ''),
          path: `${urlPrefix}/${file}`,
          category,
          // 缩略图直接用文件 URL 交给 <img>：WebView 按需异步解码并自带缓存，
          // 不做 base64 全量读取，图片再多也不卡主线程。
          // URL 追加时间戳破坏缓存：用户替换同名图片后重扫能立即看到新图
          thumbnail: `${convertFileSrc(joinPath(dirPath, file))}?t=${Date.now()}`,
          nativeTileSize,
        })
      }
    }

    for (const category of categories) {
      // 根目录下的图集是历史素材，按 16 处理；新素材放 tilesets/<尺寸>/ 即可自动识别
      const defaultSize = category === 'tilesets' ? 16 : undefined
      await scanCategory(category, joinPath(engineDir, 'maps', category), `/maps/${category}`, defaultSize)
    }

    // 按名称排序，分类间保持 images -> tiles -> tilesets
    results.sort((a, b) =>
      a.category === b.category
        ? a.name.localeCompare(b.name)
        : categories.indexOf(a.category) - categories.indexOf(b.category)
    )

    items.value = results
  }

  return { items, loadBuiltinResources }
})
