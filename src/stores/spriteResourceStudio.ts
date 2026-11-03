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

/**
 * 素材整理页缩略图的内容占比：默认 0.43 是按普通列表格子的观感定的，
 * 整理页卡片格子更大，用 0.86（正好是默认的两倍）让图像更饱满。
 */
const STUDIO_THUMB_CONTENT_RATIO = 0.86

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

  /**
   * 补齐缩略图，统一到固定 160×160 画布（内容按最长边缩放居中），
   * 保证列表里不同尺寸/留白的素材视觉大小一致。
   *
   * 注意不能对图片用 `convertFileSrc` 的文件 URL：跨域协议会污染 canvas，
   * `normalizeSpriteThumb` 里的 `toDataURL` 会抛异常并静默退回原图，
   * 于是图片缩略图就按各自原始画布撑满卡片、和包文件大小对不上。
   * 一律用 Rust 读成 base64 data URL（同内置角色库 spriteLib 的做法）再归一化。
   */
  async function fillThumbnail(item: MapResourceItem) {
    try {
      const abs = joinPath(categoryDir(item.category as SpriteCategory), item.rel)
      const lower = abs.toLowerCase()
      if (lower.endsWith('.svg')) {
        // SVG 无法由 Rust 图片库解码，直接交给 <img>（矢量图尺寸不受留白影响）
        item.thumbnail = convertFileSrc(abs)
        return
      }
      if (lower.endsWith('.bsf')) {
        // .bsf 缩略图本身就是归一化画布（与悬停动画共用默认帧锚点），无需二次重采样
        const { getBsfThumbnail } = await import('../composables/useSpriteData')
        item.thumbnail = await getBsfThumbnail(abs, STUDIO_THUMB_CONTENT_RATIO)
        return
      }
      // .bgs 取默认帧、单图直接读取，均为 base64 data URL（不污染 canvas）
      const dataUrl = await invoke<string>('get_sprite_thumbnail', { path: abs })
      const { normalizeSpriteThumb } = await import('../utils/spriteThumb')
      item.thumbnail = await normalizeSpriteThumb(dataUrl, STUDIO_THUMB_CONTENT_RATIO)
    } catch (e) {
      console.warn('[SpriteResourceStudio] 缩略图加载失败:', item.rel, e)
    }
  }

  async function loadSpriteResources(force = false) {
    if (loading) return
    if (!force && cache) {
      // 有缓存就直接复用，不重赋值 items.value
      // —— 避免触发 Vue computed 重算导致列表闪烁
      if (!items.value.length) items.value = cache
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
        for (const entry of await scanCategory(category)) {
          if (!isBuiltinAsset(manifest, `sprites/${category}/${entry.rel}`)) continue
          const meta = index.entries[entry.rel] ?? {}
          result.push({
            name: meta.name || entry.file.replace(/[.][^.]+$/, ''),
            path: `/sprites/${category}/${entry.rel}`,
            category,
            // 缩略图统一在 fillThumbnail 里生成为归一化 data URL（含图片），先留空占位
            thumbnail: '',
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
      // 逐个补齐缩略图（包文件需解包、图片需归一化），避免几十个素材同时解码占满内存。
      // 注意：必须从 items.value（reactive 代理）取元素再赋值，
      // 直接改 result 里的原始对象不会触发响应式，缩略图要等下次重渲染才显示。
      const proxyItems = items.value
      void (async () => {
        for (const item of proxyItems) {
          await fillThumbnail(item)
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
