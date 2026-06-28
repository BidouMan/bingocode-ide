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

  function getList(type: ResourceItem['type']) {
    switch (type) {
      case 'sprite': return sprites
      case 'map': return maps
      case 'sound': return sounds
      case 'code': return codes
    }
  }

  function addItem(item: Omit<ResourceItem, 'id'>) {
    const list = getList(item.type)
    let name = item.name
    const existingNames = list.value.map(i => i.name)
    if (existingNames.includes(name)) {
      let counter = 1
      while (existingNames.includes(`${name}-${counter}`)) counter++
      name = `${name}-${counter}`
    }

    const id = `res-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    list.value.push({ ...item, name, id })
    return id
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

  function clearAll(type: ResourceItem['type']) {
    const list = getList(type)
    list.value = []
  }

  function getItem(id: string, type: ResourceItem['type']) {
    return getList(type).value.find(i => i.id === id)
  }

  return { sprites, maps, sounds, codes, selectedSpriteId, addItem, removeItem, renameItem, clearAll, getItem }
})
