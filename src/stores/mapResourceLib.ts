import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

export interface MapResourceItem {
  name: string
  path: string
  category: 'images' | 'tiles' | 'tilesets'
  thumbnail: string
}

const BUILTIN_RESOURCES: { name: string; path: string; category: MapResourceItem['category'] }[] = [
  { name: 'bg', path: '/maps/images/bg.png', category: 'images' },
  { name: 'Fence 01', path: '/maps/images/Fence 01.png', category: 'images' },
  { name: 'Grass 03', path: '/maps/images/Grass 03.png', category: 'images' },
  { name: 'Tree 03', path: '/maps/images/Tree 03.png', category: 'images' },
  { name: 'brick', path: '/maps/tiles/brick.png', category: 'tiles' },
  { name: 'grass', path: '/maps/tiles/grass.png', category: 'tiles' },
  { name: 'tileset', path: '/maps/tilesets/tileset.png', category: 'tilesets' },
  { name: 'fruit', path: '/maps/tilesets/fruit.png', category: 'tilesets' },
  { name: 'coin', path: '/maps/tilesets/coin.png', category: 'tilesets' },
]

export const useMapResourceLibStore = defineStore('mapResourceLib', () => {
  const items = ref<MapResourceItem[]>([])
  const loaded = ref(false)

  async function loadBuiltinResources() {
    if (loaded.value) return

    // 获取引擎资源目录
    const engineDir = await invoke<string>('get_engine_assets_dir')

    // 先设置空缩略图
    items.value = BUILTIN_RESOURCES.map(r => ({
      ...r,
      thumbnail: '',
    }))
    loaded.value = true

    // 通过 Rust 命令逐个加载缩略图
    for (const item of items.value) {
      try {
        const fullPath = `${engineDir}${item.path}`
        const dataUrl = await invoke<string>('read_image_as_data_url', { path: fullPath })
        item.thumbnail = dataUrl
      } catch (e) {
        console.warn(`[MapResourceLib] ${item.name}: 加载缩略图失败`, e)
      }
    }
  }

  return { items, loaded, loadBuiltinResources }
})
