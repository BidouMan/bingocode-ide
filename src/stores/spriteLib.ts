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

  const BUILTIN_SPRITES = [
    '皮卡丘', '林克', '男剑士', '女忍者', '弓箭手',
    '魔女', '魔术师', '达奥斯', '喷火龙', '太鼓达人',
    '女武神', '男换装术士', '男孩-迷你', '女孩-迷你',
  ]

  async function loadBuiltinLibrary() {
    if (items.value.length > 0) return
    loading.value = true

    // 获取引擎资源目录
    const engineDir = await invoke<string>('get_engine_assets_dir')

    // 创建所有条目
    for (const name of BUILTIN_SPRITES) {
      items.value.push({
        name,
        bgsUrl: `${engineDir}/sprites/packages/${name}.bgs`,
        thumbUrl: '',
        loaded: false,
      })
    }

    // 通过 Tauri 命令加载缩略图（从 .bgs zip 读取）
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
