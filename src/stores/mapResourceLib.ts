import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { loadBuiltinAssetManifest, isBuiltinAsset } from '../utils/builtinAssets'

export type ResourceCategory = 'images' | 'tiles' | 'tilesets' | 'characters' | 'items'

export interface MapResourceItem {
  /** 显示名：索引里的中文名，未登记时回退为文件名 */
  name: string
  /** 导入用路径：/maps/<category>/<相对路径> */
  path: string
  category: ResourceCategory
  thumbnail: string
  /** 分类：由子目录名自动推导；根目录下的文件为「未分类」 */
  group: string
  tags: string[]
  /** 预计算拼音（全拼 / 首字母），由整理工具写入索引，运行时无需拼音库 */
  py: string
  pyi: string
  /** 文件名（含扩展名） */
  file: string
  /** 分类目录内的相对路径，也是索引条目的 key */
  rel: string
  /** 角色素材专用：包文件（.bgs/.bsf）或普通图片 */
  spriteKind?: 'package' | 'image'
}

/** 索引条目的字段（可选，缺省时回退文件名） */
export interface IndexEntry {
  name?: string
  tags?: string[]
  py?: string
  pyi?: string
}

/** 每个分类一份 index.json：分类目录名即分类标签，索引存名字/标签/拼音 + 分类的显示顺序 */
export interface CategoryIndex {
  version: number
  tagPool: string[]
  entries: Record<string, IndexEntry>
  /** 分类的显示顺序（dev 整理工具可手动排序）；未列出的分类按名称排 */
  groups: string[]
}

export const UNGROUPED = '未分类'
export const INDEX_FILE = 'index.json'
export const RESOURCE_CATEGORIES: ResourceCategory[] = ['images', 'tiles', 'tilesets']

// 支持的图片扩展名（自动扫描时过滤）
export const IMAGE_EXTS = /\.(png|jpe?g|gif|webp|bmp|svg)$/i

// 路径拼接：兼容 Windows（反斜杠）和 Unix（正斜杠）
export function joinPath(base: string, ...parts: string[]): string {
  const sep = base.includes('\\') && !base.includes('/') ? '\\' : '/'
  const cleanBase = base.replace(/[\\/]+$/, '')
  const cleanParts = parts.map(p => p.replace(/^[\\/]+/, '').replace(/[\\/]+$/, ''))
  return [cleanBase, ...cleanParts].join(sep)
}

export const useMapResourceLibStore = defineStore('mapResourceLib', () => {
  const items = ref<MapResourceItem[]>([])
  /** 引擎素材根目录（绝对路径），整理工具复用 */
  const engineDir = ref('')

  function categoryDir(category: ResourceCategory): string {
    return joinPath(engineDir.value, 'maps', category)
  }

  function indexFilePath(category: ResourceCategory): string {
    return joinPath(categoryDir(category), INDEX_FILE)
  }

  /** 读索引：缺失或损坏时静默退化为纯文件名检索，绝不影响资源列表 */
  async function readCategoryIndex(category: ResourceCategory): Promise<CategoryIndex> {
    try {
      const raw = await invoke<string>('read_file', { path: indexFilePath(category) })
      const data = JSON.parse(raw)
      return {
        version: typeof data.version === 'number' ? data.version : 1,
        tagPool: Array.isArray(data.tagPool) ? data.tagPool : [],
        entries: data.entries && typeof data.entries === 'object' ? data.entries : {},
        groups: Array.isArray(data.groups) ? data.groups.filter((g: unknown) => typeof g === 'string') : [],
      }
    } catch {
      return { version: 1, tagPool: [], entries: {}, groups: [] }
    }
  }

  /** 扫描分类目录：根目录文件 + 一级子目录（子目录名即分类标签） */
  async function scanCategory(category: ResourceCategory): Promise<Array<{ rel: string; file: string; group: string }>> {
    const dirPath = categoryDir(category)
    const found: Array<{ rel: string; file: string; group: string }> = []
    let top: string[]
    try {
      top = await invoke<string[]>('list_dir', { path: dirPath })
    } catch (e) {
      console.warn(`[MapResourceLib] 扫描 ${category} 目录失败:`, e)
      return found
    }
    for (const entry of top) {
      if (entry.endsWith('/')) {
        const group = entry.replace(/\/+$/, '')
        let sub: string[]
        try {
          sub = await invoke<string[]>('list_dir', { path: joinPath(dirPath, group) })
        } catch {
          continue
        }
        for (const f of sub) {
          if (f.endsWith('/') || !IMAGE_EXTS.test(f)) continue
          found.push({ rel: `${group}/${f}`, file: f, group })
        }
      } else if (IMAGE_EXTS.test(entry)) {
        found.push({ rel: entry, file: entry, group: '' })
      }
    }
    return found
  }

  /** 只列一级子目录名（含空目录），供整理工具管理分类 */
  async function listGroups(category: ResourceCategory): Promise<string[]> {
    try {
      const top = await invoke<string[]>('list_dir', { path: categoryDir(category) })
      return top.filter(e => e.endsWith('/')).map(e => e.replace(/\/+$/, ''))
    } catch {
      return []
    }
  }

  async function loadBuiltinResources() {
    // 每次打开面板都重新扫描：read_dir 为微秒级操作，缩略图走 WebView 缓存的文件 URL，
    // 重扫零负担；这样才能让用户新放入的图片无需重启即被看到
    engineDir.value = await invoke<string>('get_engine_assets_dir')
    // 正式包按清单过滤：覆盖安装残留的旧素材（发布包里已删除的）不再显示
    const manifest = await loadBuiltinAssetManifest()

    const results: MapResourceItem[] = []
    const stamp = Date.now()
    /** 每个分类的手动排序权重表 */
    const groupOrders: Record<string, Map<string, number>> = {}

    for (const category of RESOURCE_CATEGORIES) {
      const dirPath = categoryDir(category)
      const index = await readCategoryIndex(category)
      groupOrders[category] = new Map(index.groups.map((g, i) => [g, i]))

      for (const entry of await scanCategory(category)) {
        if (!isBuiltinAsset(manifest, `maps/${category}/${entry.rel}`)) continue
        const meta = index.entries[entry.rel] ?? {}
        results.push({
          name: meta.name || entry.file.replace(IMAGE_EXTS, ''),
          path: `/maps/${category}/${entry.rel}`,
          category,
          // 缩略图直接用文件 URL 交给 <img>：WebView 按需异步解码并自带缓存，
          // 不做 base64 全量读取，图片再多也不卡主线程。
          // URL 带时间戳破坏缓存：替换同名图片后重扫能立即看到新图
          thumbnail: `${convertFileSrc(joinPath(dirPath, entry.rel))}?t=${stamp}`,
          group: entry.group || UNGROUPED,
          tags: Array.isArray(meta.tags) ? meta.tags : [],
          py: meta.py ?? '',
          pyi: meta.pyi ?? '',
          file: entry.file,
          rel: entry.rel,
        })
      }
    }

    // 分类间保持 images -> tiles -> tilesets；分类内「未分类」垫底，
    // 其余按 index.json 里的手动顺序排，未登记的按名称排
    results.sort((a, b) => {
      if (a.category !== b.category) {
        return RESOURCE_CATEGORIES.indexOf(a.category) - RESOURCE_CATEGORIES.indexOf(b.category)
      }
      if (a.group !== b.group) {
        if (a.group === UNGROUPED) return 1
        if (b.group === UNGROUPED) return -1
        const order = groupOrders[a.category]
        const ia = order.get(a.group) ?? Number.MAX_SAFE_INTEGER
        const ib = order.get(b.group) ?? Number.MAX_SAFE_INTEGER
        if (ia !== ib) return ia - ib
        return a.group.localeCompare(b.group, 'zh-CN')
      }
      return a.name.localeCompare(b.name, 'zh-CN', { numeric: true })
    })

    items.value = results
  }

  return {
    items,
    engineDir,
    categoryDir,
    indexFilePath,
    readCategoryIndex,
    listGroups,
    loadBuiltinResources,
  }
})
