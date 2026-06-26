import { defineStore } from 'pinia'
import { ref } from 'vue'
import { readBgsFromUrl, type SpriteData } from '../composables/useSpriteData'

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

    for (const name of BUILTIN_SPRITES) {
      const bgsUrl = `/sprite_lib/${name}.bgs`
      items.value.push({
        name,
        bgsUrl,
        thumbUrl: '',
        loaded: false,
      })
    }

    // 异步加载缩略图
    for (const item of items.value) {
      try {
        const data = await readBgsFromUrl(item.bgsUrl)
        if (data.frames.length > 0) {
          item.thumbUrl = data.frames[0].url
          item.loaded = true
        }
      } catch {
        // 缩略图加载失败，跳过
      }
    }

    loading.value = false
  }

  async function loadSpriteData(bgsUrl: string): Promise<SpriteData> {
    return readBgsFromUrl(bgsUrl)
  }

  return { items, loading, loadBuiltinLibrary, loadSpriteData }
})
