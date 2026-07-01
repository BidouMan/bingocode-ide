import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface MapResourceItem {
  name: string
  path: string
  category: 'images' | 'tiles' | 'tilesets'
  thumbnail: string
}

const BUILTIN_RESOURCES: { name: string; path: string; category: MapResourceItem['category'] }[] = [
  { name: 'bg', path: '/map_assets/images/bg.png', category: 'images' },
  { name: 'Fence 01', path: '/map_assets/images/Fence 01.png', category: 'images' },
  { name: 'Grass 03', path: '/map_assets/images/Grass 03.png', category: 'images' },
  { name: 'Tree 03', path: '/map_assets/images/Tree 03.png', category: 'images' },
  { name: 'brick', path: '/map_assets/tiles/brick.png', category: 'tiles' },
  { name: 'grass', path: '/map_assets/tiles/grass.png', category: 'tiles' },
  { name: 'tileset', path: '/map_assets/tilesets/tileset.png', category: 'tilesets' },
  { name: 'fruit', path: '/map_assets/tilesets/fruit.png', category: 'tilesets' },
  { name: 'coin', path: '/map_assets/tilesets/coin.png', category: 'tilesets' },
]

export const useMapResourceLibStore = defineStore('mapResourceLib', () => {
  const items = ref<MapResourceItem[]>([])
  const loaded = ref(false)

  function loadBuiltinResources() {
    if (loaded.value) return
    items.value = BUILTIN_RESOURCES.map(r => ({
      ...r,
      thumbnail: r.path,
    }))
    loaded.value = true
  }

  return { items, loaded, loadBuiltinResources }
})
