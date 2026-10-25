import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ResourceItem {
  id: string
  name: string
  type: 'sprite' | 'map' | 'sound' | 'code'
  path: string
  content?: string
  extra?: Record<string, any>
}

export const useResourceStore = defineStore('resource', () => {
  const sprites = ref<ResourceItem[]>([])
  const maps = ref<ResourceItem[]>([])
  const sounds = ref<ResourceItem[]>([])
  const codes = ref<ResourceItem[]>([])
  const selectedSpriteId = ref<string | null>(null)

  // 角色缩略图版本号：编辑器改了默认渲染帧后 bump，MainLayout 监听并重载对应缩略图
  const spriteThumbVersions = ref<Record<string, number>>({})
  function bumpSpriteThumb(id: string) {
    if (!id) return
    spriteThumbVersions.value = {
      ...spriteThumbVersions.value,
      [id]: (spriteThumbVersions.value[id] ?? 0) + 1,
    }
  }

  // 地图数据预解析缓存：mapId → deserialized MapData
  const mapDataCache = ref<Map<string, any>>(new Map())

  function getList(type: ResourceItem['type']) {
    switch (type) {
      case 'sprite': return sprites
      case 'map': return maps
      case 'sound': return sounds
      case 'code': return codes
    }
  }

  // 生成下一个顺序名：扫描现有的「前缀+数字」名字，返回 最大序号+1（如 角色1、角色2…/地图1、地图2…）
  function nextSequentialName(type: ResourceItem['type'], prefix: string) {
    const existingNames = getList(type).value.map(i => i.name)
    let max = 0
    for (const n of existingNames) {
      const m = n.match(new RegExp(`^${prefix}(\\d+)$`))
      if (m) max = Math.max(max, parseInt(m[1], 10))
    }
    let name = `${prefix}${max + 1}`
    while (existingNames.includes(name)) name = `${prefix}${++max + 1}`
    return name
  }

  // id 可选：代码资源的 id 必须与标签页 id 保持一致，重命名/删除才能正确联动
  function addItem(item: Omit<ResourceItem, 'id'>, id?: string) {
    const list = getList(item.type)
    let name = item.name
    const existingNames = list.value.map(i => i.name)
    if (existingNames.includes(name)) {
      let counter = 1
      while (existingNames.includes(`${name}-${counter}`)) counter++
      name = `${name}-${counter}`
    }

    const newId = id || `res-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    list.value.push({ ...item, name, id: newId })
    return newId
  }

  function removeItem(id: string, type: ResourceItem['type']) {
    const list = getList(type)
    const idx = list.value.findIndex(i => i.id === id)
    if (idx >= 0) list.value.splice(idx, 1)
  }

  function renameItem(id: string, newName: string) {
    for (const list of [sprites, maps, sounds, codes]) {
      const item = list.value.find(i => i.id === id)
      if (item) {
        // 代码文件自动补 .py 后缀
        if (item.type === 'code') {
          item.name = newName.endsWith('.py') ? newName : newName + '.py'
        } else {
          item.name = newName
        }
        break
      }
    }
  }

  /** 更新资源磁盘路径（如图片角色首次追加帧后转正为目录角色） */
  function updateItemPath(id: string, path: string) {
    for (const list of [sprites, maps, sounds, codes]) {
      const item = list.value.find(i => i.id === id)
      if (item) {
        item.path = path
        return
      }
    }
  }

  function clearAll(type: ResourceItem['type']) {
    const list = getList(type)
    list.value = []
  }

  function getItem(id: string, type: ResourceItem['type']) {
    return getList(type).value.find(i => i.id === id)
  }

  function clearAllResources() {
    sprites.value = []
    maps.value = []
    sounds.value = []
    codes.value = []
    selectedSpriteId.value = null
    mapDataCache.value.clear()
  }

  function setCachedMapData(mapId: string, data: any) {
    mapDataCache.value.set(mapId, data)
  }

  function getCachedMapData(mapId: string): any | undefined {
    return mapDataCache.value.get(mapId)
  }

  function clearMapDataCache() {
    mapDataCache.value.clear()
  }

  return { sprites, maps, sounds, codes, selectedSpriteId, spriteThumbVersions, bumpSpriteThumb, addItem, removeItem, renameItem, updateItemPath, clearAll, getItem, clearAllResources, setCachedMapData, getCachedMapData, clearMapDataCache, nextSequentialName }
})
