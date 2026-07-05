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

  async function loadBuiltinLibrary() {
    if (items.value.length > 0) return
    loading.value = true

    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')
      const packagesDir = `${engineDir}/maps/packages`
      const files = await invoke<string[]>('list_dir', { path: packagesDir })

      // 过滤出 .bgm 文件，去掉扩展名作为名称
      const mapNames = files
        .filter(f => f.endsWith('.bgm'))
        .map(f => f.replace(/\.bgm$/, ''))

      for (const name of mapNames) {
        items.value.push({
          name,
          bgmUrl: `${packagesDir}/${name}.bgm`,
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
    } catch (e) {
      console.error('[MapLib] 加载内置地图库失败:', e)
    }

    loading.value = false
  }

  return { items, loading, loadBuiltinLibrary }
})
