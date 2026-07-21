import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

export interface MapLibItem {
  name: string
  bgmUrl: string
  thumbUrl: string
  loaded: boolean
}

// 路径拼接：兼容 Windows（反斜杠）和 Unix（正斜杠）
function joinPath(base: string, ...parts: string[]): string {
  const sep = base.includes('\\') && !base.includes('/') ? '\\' : '/'
  const cleanBase = base.replace(/[\\/]+$/, '')
  const cleanParts = parts.map(p => p.replace(/^[\\/]+/, '').replace(/[\\/]+$/, ''))
  return [cleanBase, ...cleanParts].join(sep)
}

export const useMapLibStore = defineStore('mapLib', () => {
  const items = ref<MapLibItem[]>([])
  const loading = ref(false)

  async function loadBuiltinLibrary() {
    if (items.value.length > 0) return
    loading.value = true

    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')
      const packagesDir = joinPath(engineDir, 'maps', 'packages')
      const files = await invoke<string[]>('list_dir', { path: packagesDir })

      // 过滤出 .bgm 文件，去掉扩展名作为名称
      const mapNames = files
        .filter(f => f.endsWith('.bgm'))
        .map(f => f.replace(/\.bgm$/, ''))

      for (const name of mapNames) {
        items.value.push({
          name,
          bgmUrl: joinPath(packagesDir, `${name}.bgm`),
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
          console.error(`[MapLib] ${item.name}: 加载缩略图失败 (path=${item.bgmUrl})`, e)
        }
      }
    } catch (e) {
      console.error('[MapLib] 加载内置地图库失败:', e)
    }

    loading.value = false
  }

  return { items, loading, loadBuiltinLibrary }
})
