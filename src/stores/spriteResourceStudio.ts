import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { UNGROUPED, INDEX_FILE, IMAGE_EXTS, joinPath } from './mapResourceLib'
import type { CategoryIndex, MapResourceItem } from './mapResourceLib'
import { loadBuiltinAssetManifest, isBuiltinAsset } from '../utils/builtinAssets'

/**
 * 开发模式专用：内置角色素材（sprites/characters、sprites/items）的扫描与索引读写。
 * 只被素材整理页动态 import，正式包不会包含。
 */

export type SpriteCategory = 'characters' | 'items'

/** 角色素材分类（目录名 = sprites/ 下的一级子目录） */
export const SPRITE_STUDIO_CATEGORIES: Array<{ id: SpriteCategory; label: string }> = [
  { id: 'characters', label: '角色' },
  { id: 'items', label: '道具' },
]

/** 精灵包扩展名（.bgs 逐帧 / .bsf sheet 图集） */
export const SPRITE_PACKAGE_EXTS = /\.(bgs|bsf)$/i

export function isSpriteCategory(category: string): category is SpriteCategory {
  return category === 'characters' || category === 'items'
}

export const useSpriteResourceStudioStore = defineStore('spriteResourceStudio', () => {
  const items = ref<MapResourceItem[]>([])
  /** 引擎素材根目录（绝对路径） */
  const engineDir = ref('')

  // 缩略图解码成本高，缓存整份列表；切分类页签时直接复用
  let cache: MapResourceItem[] | null = null
  let loading = false

  function categoryDir(category: SpriteCategory): string {
    return joinPath(engineDir.value, 'sprites', category)
  }

  function indexFilePath(category: SpriteCategory): string {
    return joinPath(categoryDir(category), INDEX_FILE)
  }

  /** 读索引：缺失或损坏时静默退化为纯文件名检索 */
  async function readCategoryIndex(category: SpriteCategory): Promise<CategoryIndex> {
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

  /** 角色素材不分子文件夹：整理页不需要分类管理 */
  async function listGroups(_category: SpriteCategory): Promise<string[]> {
    return []
  }

  /**
   * 扫描 packages/ 与 images/：
   * 与角色库一致，同名时包文件优先（图片跳过），避免同一角色显示两遍
   */
  async function scanCategory(
    category: SpriteCategory,
  ): Promise<Array<{ kind: 'package' | 'image'; rel: string; file: string }>> {
    const dirPath = categoryDir(category)
    const found: Array<{ kind: 'package' | 'image'; rel: string; file: string }> = []
    const packageStems = new Set<string>()

    try {
      const files = await invoke<string[]>('list_dir', { path: joinPath(dirPath, 'packages') })
      for (const f of files) {
        if (f.endsWith('/') || !SPRITE_PACKAGE_EXTS.test(f)) continue
        packageStems.add(f.replace(/[.][^.]+$/, '').toLowerCase())
        found.push({ kind: 'package', rel: `packages/${f}`, file: f })
      }
    } catch (_e) {
      // packages 目录可能不存在，静默处理
    }

    try {
      const files = await invoke<string[]>('list_dir', { path: joinPath(dirPath, 'images') })
      for (const f of files) {
        if (f.endsWith('/') || !IMAGE_EXTS.test(f)) continue
        if (packageStems.has(f.replace(/[.][^.]+$/, '').toLowerCase())) continue
        found.push({ kind: 'image', rel: `images/${f}`, file: f })
      }
    } catch (_e) {
      // images 目录可能不存在，静默处理
    }

    return found
  }

  /** 包文件缩略图需要解包：放在列表展示后再异步补齐，避免整页等待 */
  async function fillThumbnail(item: MapResourceItem) {
    try {
      const abs = joinPath(categoryDir(item.category as SpriteCategory), item.rel)
      if (abs.toLowerCase().endsWith('.bsf')) {
        const { getBsfThumbnail } = await import('../composables/useSpriteData')
        item.thumbnail = await getBsfThumbnail(abs)
      } else {
        item.thumbnail = await invoke<string>('get_sprite_thumbnail', { path: abs })
      }
    } catch (e) {
      console.warn('[SpriteResourceStudio] 缩略图加载失败:', item.rel, e)
    }
  }

  async function loadSpriteResources(force = false) {
    if (loading) return
    if (!force && cache) {
      items.value = cache
      return
    }

    loading = true
    try {
      if (!engineDir.value) engineDir.value = await invoke<string>('get_engine_assets_dir')
      // 正式包按清单过滤：覆盖安装残留的旧素材不再显示
      const manifest = await loadBuiltinAssetManifest()
      const result: MapResourceItem[] = []

      for (const { id: category } of SPRITE_STUDIO_CATEGORIES) {
        const index = await readCategoryIndex(category)
        const dirPath = categoryDir(category)
        for (const entry of await scanCategory(category)) {
          if (!isBuiltinAsset(manifest, `sprites/${category}/${entry.rel}`)) continue
          const meta = index.entries[entry.rel] ?? {}
          const absPath = joinPath(dirPath, entry.rel)
          result.push({
            name: meta.name || entry.file.replace(/[.][^.]+$/, ''),
            path: `/sprites/${category}/${entry.rel}`,
            category,
            // 图片直接用文件 URL 交给 <img>；包文件先留空，稍后解包出缩略图
            thumbnail: entry.kind === 'image' ? convertFileSrc(absPath) : '',
            group: UNGROUPED,
            tags: Array.isArray(meta.tags) ? meta.tags : [],
            py: meta.py ?? '',
            pyi: meta.pyi ?? '',
            file: entry.file,
            rel: entry.rel,
            spriteKind: entry.kind,
          })
        }
      }

      result.sort((a, b) => {
        if (a.category !== b.category) {
          return (
            SPRITE_STUDIO_CATEGORIES.findIndex(c => c.id === a.category) -
            SPRITE_STUDIO_CATEGORIES.findIndex(c => c.id === b.category)
          )
        }
        return a.name.localeCompare(b.name, 'zh-CN', { numeric: true })
      })

      items.value = result
      cache = result
      // 包文件缩略图逐个解包，避免几十个 zip 同时解码占满内存
      void (async () => {
        for (const item of result) {
          if (item.spriteKind === 'package') await fillThumbnail(item)
        }
      })()
    } catch (e) {
      console.error('[SpriteResourceStudio] 加载角色素材失败:', e)
    } finally {
      loading = false
    }
  }

  return {
    items,
    engineDir,
    categoryDir,
    indexFilePath,
    readCategoryIndex,
    listGroups,
    loadSpriteResources,
  }
})
