import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'

export type SpriteLibType = 'bgs' | 'image'

export interface SpriteLibItem {
  name: string
  /** .bgs 文件路径 或 图片文件路径 */
  filePath: string
  /** 资源类型 */
  type: SpriteLibType
  thumbUrl: string
  loaded: boolean
}

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

  async function loadBuiltinLibrary() {
    if (loading.value) return
    loading.value = true

    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')
      const found = new Map<string, SpriteLibItem>()

      // 扫描 .bgs 包文件
      const packagesDir = joinPath(engineDir, 'sprites', 'packages')
      try {
        const files = await invoke<string[]>('list_dir', { path: packagesDir })
        for (const f of files.filter(f => f.endsWith('.bgs'))) {
          const name = f.replace(/\.bgs$/, '')
          const filePath = joinPath(packagesDir, f)
          found.set(filePath, { name, filePath, type: 'bgs', thumbUrl: '', loaded: false })
        }
      } catch (e) {
        console.error('[SpriteLib] 加载 .bgs 列表失败:', e)
      }

      // 扫描 images/ 目录下的常规图片文件
      const imagesDir = joinPath(engineDir, 'sprites', 'images')
      try {
        const files = await invoke<string[]>('list_dir', { path: imagesDir })
        for (const filename of files.filter(f => {
          const lower = f.toLowerCase()
          return IMAGE_EXTS.some(ext => lower.endsWith(ext))
        })) {
          const name = filename.replace(/\.[^.]+$/, '')
          const filePath = joinPath(imagesDir, filename)
          found.set(filePath, { name, filePath, type: 'image', thumbUrl: '', loaded: false })
        }
      } catch (_e) {
        // images 目录可能为空或不存在，静默处理
      }

      // 增量合并：已有项复用缩略图缓存，只为新增文件加载缩略图
      // （.bgs 缩略图需要解包取帧，重复打开库页面时不能重付这份成本）
      const oldByPath = new Map(items.value.map(i => [i.filePath, i]))
      const needThumbs: SpriteLibItem[] = []
      const merged: SpriteLibItem[] = []
      for (const item of found.values()) {
        const old = oldByPath.get(item.filePath)
        if (old && old.loaded) { merged.push(old); continue }
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

  // 动画预览缓存：.bgs 悬停预览用，路径 → 帧图 ObjectURL 列表 + fps（null = 无动画）
  const previewCache = new Map<string, { urls: string[]; fps: number } | null>()

  // 悬停动画预览：解析 .bgs 的帧与动画段（每个包只解析一次）
  async function getSpritePreview(filePath: string): Promise<{ urls: string[]; fps: number } | null> {
    if (previewCache.has(filePath)) return previewCache.get(filePath)!
    try {
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

  return { items, loading, loadBuiltinLibrary, loadSpriteData, getSpritePreview }
})
