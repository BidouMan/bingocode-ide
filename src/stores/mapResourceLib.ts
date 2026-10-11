import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'

export interface MapResourceItem {
  name: string
  path: string
  category: 'images' | 'tiles' | 'tilesets'
  thumbnail: string
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
    // list_dir 对子目录返回 "name/" 后缀，需要过滤掉
    const categories: MapResourceItem['category'][] = ['images', 'tiles', 'tilesets']
    const results: MapResourceItem[] = []

    for (const category of categories) {
      try {
        const dirPath = joinPath(engineDir, 'maps', category)
        const files = await invoke<string[]>('list_dir', { path: dirPath })
        for (const file of files) {
          if (file.endsWith('/')) continue
          if (!IMAGE_EXTS.test(file)) continue
          const fullPath = joinPath(dirPath, file)
          results.push({
            name: file.replace(IMAGE_EXTS, ''),
            path: `/maps/${category}/${file}`,
            category,
            // 缩略图直接用文件 URL 交给 <img>：WebView 按需异步解码并自带缓存，
            // 不做 base64 全量读取，图片再多也不卡主线程
            thumbnail: convertFileSrc(fullPath),
          })
        }
      } catch (e) {
        console.warn(`[MapResourceLib] 扫描 ${category} 目录失败:`, e)
      }
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
