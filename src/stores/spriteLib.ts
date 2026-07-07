import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

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

export const useSpriteLibStore = defineStore('spriteLib', () => {
  const items = ref<SpriteLibItem[]>([])
  const loading = ref(false)

  async function loadBuiltinLibrary() {
    if (items.value.length > 0) return
    loading.value = true

    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')

      // 加载 .bgs 包文件
      const packagesDir = `${engineDir}/sprites/packages`
      try {
        const files = await invoke<string[]>('list_dir', { path: packagesDir })
        const bgsNames = files
          .filter(f => f.endsWith('.bgs'))
          .map(f => f.replace(/\.bgs$/, ''))

        for (const name of bgsNames) {
          items.value.push({
            name,
            filePath: `${packagesDir}/${name}.bgs`,
            type: 'bgs',
            thumbUrl: '',
            loaded: false,
          })
        }
      } catch (e) {
        console.error('[SpriteLib] 加载 .bgs 列表失败:', e)
      }

      // 加载 images/ 目录下的常规图片文件
      const imagesDir = `${engineDir}/sprites/images`
      try {
        const files = await invoke<string[]>('list_dir', { path: imagesDir })
        const imageFiles = files.filter(f => {
          const lower = f.toLowerCase()
          return IMAGE_EXTS.some(ext => lower.endsWith(ext))
        })

        for (const filename of imageFiles) {
          const name = filename.replace(/\.[^.]+$/, '')
          items.value.push({
            name,
            filePath: `${imagesDir}/${filename}`,
            type: 'image',
            thumbUrl: '',
            loaded: false,
          })
        }
      } catch (e) {
        // images 目录可能为空或不存在，静默处理
        console.warn('[SpriteLib] 加载图片列表:', e)
      }

      // 批量加载缩略图
      for (const item of items.value) {
        try {
          const dataUrl = await invoke<string>('get_sprite_thumbnail', {
            path: item.filePath,
          })
          item.thumbUrl = dataUrl
          item.loaded = true
        } catch (e) {
          console.error(`[SpriteLib] ${item.name}: 加载缩略图失败`, e)
        }
      }
    } catch (e) {
      console.error('[SpriteLib] 加载内置角色库失败:', e)
    }

    loading.value = false
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

  return { items, loading, loadBuiltinLibrary, loadSpriteData }
})
