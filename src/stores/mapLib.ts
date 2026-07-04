import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

export interface MapLibItem {
  name: string
  bgmUrl: string
  thumbUrl: string
  loaded: boolean
}

export const useMapLibStore = defineStore('mapLib', () => {
  const items = ref<MapLibItem[]>([])
  const loading = ref(false)

  // 内置地图列表
  const BUILTIN_MAPS = ['草地']

  async function loadBuiltinLibrary() {
    if (items.value.length > 0) return
    loading.value = true

    const engineDir = await invoke<string>('get_engine_assets_dir')

    for (const name of BUILTIN_MAPS) {
      items.value.push({
        name,
        bgmUrl: `${engineDir}/maps/packages/${name}.bgm`,
        thumbUrl: '',
        loaded: false,
      })
    }

    for (const item of items.value) {
      try {
        const dataUrl = await invoke<string>('get_sprite_thumbnail', {
          path: item.bgmUrl,
        })
        item.thumbUrl = dataUrl
        item.loaded = true
      } catch (e) {
        console.error(`[MapLib] ${item.name}: 加载缩略图失败`, e)
      }
    }

    loading.value = false
  }

  return { items, loading, loadBuiltinLibrary }
})
