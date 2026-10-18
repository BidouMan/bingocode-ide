import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'

export type SpriteLibType = 'bgs' | 'bsf' | 'image'

export interface SpriteLibItem {
  name: string
  /** .bgs 文件路径 或 图片文件路径 */
  filePath: string
  /** 资源类型 */
  type: SpriteLibType
  thumbUrl: string
  loaded: boolean
  /** 分类目录名（sprites/ 下的子目录：characters / items / ...） */
  category: string
}

/**
 * 精灵库分类配置：显式声明每个分类的标签和对应目录，
 * 不自动扫描目录——新增分类只需在此添加一行 { dir, label }
 */
export const SPRITE_CATEGORIES: Array<{ dir: string; label: string }> = [
  { dir: 'characters', label: '角色' },
  { dir: 'items', label: '道具' },
]

const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']

// 路径拼接：兼容 Windows（反斜杠）和 Unix（正斜杠）
function joinPath(base: string, ...parts: string[]): string {
  const sep = base.includes('\\') && !base.includes('/') ? '\\' : '/'
  const cleanBase = base.replace(/[\\/]+$/, '')
  const cleanParts = parts.map(p => p.replace(/^[\\/]+/, '').replace(/[\\/]+$/, ''))
  return [cleanBase, ...cleanParts].join(sep)
}

export const useSpriteLibStore = defineStore('spriteLib', () => {
  const items = ref<SpriteLibItem[]>([])
  const loading = ref(false)
  /** 发现的分类目录名列表（sprites/ 下的子目录，字母序） */
  const categories = ref<string[]>([])

  async function loadBuiltinLibrary() {
    if (loading.value) return
    loading.value = true

    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')
      const spritesRoot = joinPath(engineDir, 'sprites')
      const found = new Map<string, SpriteLibItem>()

      // 分类来自显式配置，不扫描目录（避免误将内部结构目录当作分类）
      categories.value = SPRITE_CATEGORIES.map(c => c.dir)

      // 逐分类扫描 packages/*（.bgs / .bsf 包文件）与 images/*
      for (const { dir: cat } of SPRITE_CATEGORIES) {
        // 精灵包文件：.bgs（逐帧）与 .bsf（sheet 图集）
        const packagesDir = joinPath(spritesRoot, cat, 'packages')
        try {
          const files = await invoke<string[]>('list_dir', { path: packagesDir })
          for (const f of files) {
            const lower = f.toLowerCase()
            let type: SpriteLibType | null = null
            let name = ''
            if (lower.endsWith('.bgs')) { type = 'bgs'; name = f.slice(0, -4) }
            else if (lower.endsWith('.bsf')) { type = 'bsf'; name = f.slice(0, -4) }
            if (!type) continue
            const filePath = joinPath(packagesDir, f)
            found.set(filePath, { name, filePath, type, thumbUrl: '', loaded: false, category: cat })
          }
        } catch (_e) {
          // packages 目录可能为空或不存在，静默处理
        }

        // 常规图片文件
        const imagesDir = joinPath(spritesRoot, cat, 'images')
        try {
          const files = await invoke<string[]>('list_dir', { path: imagesDir })
          for (const filename of files.filter(f => {
            const lower = f.toLowerCase()
            return IMAGE_EXTS.some(ext => lower.endsWith(ext))
          })) {
            const name = filename.replace(/\.[^.]+$/, '')
            const filePath = joinPath(imagesDir, filename)
            found.set(filePath, { name, filePath, type: 'image', thumbUrl: '', loaded: false, category: cat })
          }
        } catch (_e) {
          // images 目录可能为空或不存在，静默处理
        }
      }

      // 增量合并：已有项复用缩略图缓存，只为新增文件加载缩略图
      // （.bgs 缩略图需要解包取帧，重复打开库页面时不能重付这份成本）
      const oldByPath = new Map(items.value.map(i => [i.filePath, i]))
      const needThumbs: SpriteLibItem[] = []
      const merged: SpriteLibItem[] = []
      for (const item of found.values()) {
        const old = oldByPath.get(item.filePath)
        if (old && old.loaded) {
          old.category = item.category
          merged.push(old)
          continue
        }
        merged.push(item)
        needThumbs.push(item)
      }
      items.value = merged

      // 批量加载缩略图（仅新增项）
      for (const item of needThumbs) {
        try {
          // SVG 无法由 Rust image 库解码缩略图，改用文件 URL 交给 <img> 直接渲染
          if (item.filePath.toLowerCase().endsWith('.svg')) {
            item.thumbUrl = convertFileSrc(item.filePath)
            item.loaded = true
            continue
          }
          // .bsf：前端从 sheet 裁第一帧（Rust 侧不解析 sheet 图集）
          if (item.type === 'bsf') {
            const { getBsfThumbnail } = await import('../composables/useSpriteData')
            item.thumbUrl = await getBsfThumbnail(item.filePath)
            item.loaded = true
            continue
          }
          const dataUrl = await invoke<string>('get_sprite_thumbnail', {
            path: item.filePath,
          })
          item.thumbUrl = dataUrl
          item.loaded = true
        } catch (e) {
          console.error(`[SpriteLib] ${item.name}: 加载缩略图失败 (path=${item.filePath})`, e)
        }
      }
    } catch (e) {
      console.error('[SpriteLib] 加载内置角色库失败:', e)
    }

    loading.value = false
  }

  // 动画预览缓存：.bgs/.bsf 悬停预览用，路径 → 帧图 ObjectURL 列表 + fps（null = 无动画）
  const previewCache = new Map<string, { urls: string[]; fps: number } | null>()

  // 悬停动画预览：解析精灵包的帧与动画段（每个包只解析一次）
  // .bgs：逐帧图片；.bsf：从 sheet 按第一个 clip 的帧序列裁剪
  async function getSpritePreview(filePath: string): Promise<{ urls: string[]; fps: number } | null> {
    if (previewCache.has(filePath)) return previewCache.get(filePath)!
    try {
      const lower = filePath.toLowerCase()
      if (lower.endsWith('.bsf')) {
        const result = await loadBsfPreview(filePath)
        previewCache.set(filePath, result)
        return result
      }

      const bytes = await invoke<number[]>('read_binary', { path: filePath })
      const JSZip = (await import('jszip')).default
      const zip = await JSZip.loadAsync(new Uint8Array(bytes))
      const configEntry = zip.file('config.json')
      if (!configEntry) { previewCache.set(filePath, null); return null }
      const config = JSON.parse(await configEntry.async('text'))
      const frameNames: string[] = config.frames || []
      if (frameNames.length < 2) { previewCache.set(filePath, null); return null }

      const urls: string[] = []
      for (const name of frameNames) {
        const entry = zip.file(name)
        if (!entry) continue
        urls.push(URL.createObjectURL(await entry.async('blob')))
      }
      const seg = (config.segments || config.animations || [])[0]
      const fps = seg?.fps || 10
      const result = urls.length >= 2 ? { urls, fps } : null
      previewCache.set(filePath, result)
      return result
    } catch (e) {
      console.error('[SpriteLib] 动画预览解析失败:', filePath, e)
      previewCache.set(filePath, null)
      return null
    }
  }

  /** .bsf 预览：sheet 只解码一次，用 canvas 按 clip 帧序列裁剪 */
  async function loadBsfPreview(filePath: string): Promise<{ urls: string[]; fps: number } | null> {
    const bytes = await invoke<number[]>('read_binary', { path: filePath })
    const JSZip = (await import('jszip')).default
    const zip = await JSZip.loadAsync(new Uint8Array(bytes))

    const manifestEntry = zip.file('manifest.json')
    const sheetEntry = zip.file('sheet.png')
    if (!manifestEntry || !sheetEntry) return null

    const manifest = JSON.parse(await manifestEntry.async('text'))
    const frames: any[] = manifest.frames || []
    if (frames.length < 2) return null

    const clip = (manifest.clips || [])[0]
    const byName = new Map(frames.map((f: any) => [f.name, f]))
    const order: string[] = clip?.frames?.length
      ? clip.frames.filter((n: string) => byName.has(n))
      : frames.map((f: any) => f.name)
    if (order.length < 2) return null

    const sheetBlob = await sheetEntry.async('blob')
    const { loadImage } = await import('../composables/useSpriteData')
    const sheetImage = await loadImage(sheetBlob)
    const urls: string[] = []
    for (const name of order) {
      const f = byName.get(name)
      const canvas = document.createElement('canvas')
      canvas.width = f.rect.w
      canvas.height = f.rect.h
      const ctx = canvas.getContext('2d')!
      ctx.drawImage(sheetImage, f.rect.x, f.rect.y, f.rect.w, f.rect.h, 0, 0, f.rect.w, f.rect.h)
      const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, 'image/png'))
      if (blob) urls.push(URL.createObjectURL(blob))
    }
    return urls.length >= 2 ? { urls, fps: clip?.fps || 10 } : null
  }

  async function loadSpriteData(bgsUrl: string) {
    const resp = await fetch(bgsUrl)
    const blob = await resp.blob()

    const JSZip = (await import('jszip')).default
    const zip = await JSZip.loadAsync(blob)
    const configEntry = zip.file('config.json')
    if (!configEntry) throw new Error('config.json not found')
    const config = JSON.parse(await configEntry.async('text'))

    const frames = (config.frames || []).map((name: string) => {
      const entry = zip.file(name)
      if (!entry) return null
      return { name, blob: null as any, url: '' }
    }).filter(Boolean)

    const animations = (config.segments || config.animations || []).map((seg: any) => ({
      name: seg.name,
      start: seg.start || 1,
      end: seg.end || seg.start || 1,
      fps: seg.fps || 10,
      loop: seg.loop !== false,
    }))

    return { name: config.name || '未知角色', frames, animations }
  }

  return { items, categories, loading, loadBuiltinLibrary, loadSpriteData, getSpritePreview }
})
