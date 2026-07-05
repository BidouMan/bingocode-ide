import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

export interface SpriteLibItem {
  name: string
  bgsUrl: string
  thumbUrl: string
  loaded: boolean
}

export const useSpriteLibStore = defineStore('spriteLib', () => {
  const items = ref<SpriteLibItem[]>([])
  const loading = ref(false)

  async function loadBuiltinLibrary() {
    if (items.value.length > 0) return
    loading.value = true

    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')
      const packagesDir = `${engineDir}/sprites/packages`
      const files = await invoke<string[]>('list_dir', { path: packagesDir })

      // 过滤出 .bgs 文件，去掉扩展名作为名称
      const spriteNames = files
        .filter(f => f.endsWith('.bgs'))
        .map(f => f.replace(/\.bgs$/, ''))

      for (const name of spriteNames) {
        items.value.push({
          name,
          bgsUrl: `${packagesDir}/${name}.bgs`,
          thumbUrl: '',
          loaded: false,
        })
      }

      for (const item of items.value) {
        try {
          const dataUrl = await invoke<string>('get_sprite_thumbnail', {
            path: item.bgsUrl,
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
