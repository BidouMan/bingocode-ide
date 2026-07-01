import { defineStore } from 'pinia'
import { ref } from 'vue'
import JSZip from 'jszip'

export interface MapLibItem {
  name: string
  bgmUrl: string
  thumbUrl: string
  loaded: boolean
}

export const useMapLibStore = defineStore('mapLib', () => {
  const items = ref<MapLibItem[]>([])
  const loading = ref(false)

  const BUILTIN_MAPS = ['草地', '森林01']

  async function loadBuiltinLibrary() {
    if (items.value.length > 0) return
    loading.value = true

    for (const name of BUILTIN_MAPS) {
      const bgmUrl = `/map_lib/${name}.bgm`
      items.value.push({
        name,
        bgmUrl,
        thumbUrl: '',
        loaded: false,
      })
    }

    for (const item of items.value) {
      try {
        const resp = await fetch(item.bgmUrl)
        const blob = await resp.blob()
        const zip = await JSZip.loadAsync(blob)

        const thumbEntry = zip.file('thumbnail.png')
        if (thumbEntry) {
          const thumbBlob = await thumbEntry.async('blob')
          item.thumbUrl = URL.createObjectURL(thumbBlob)
        }

        const infoFile = zip.file(/.*\.info$/)
        if (infoFile.length > 0) {
          const infoName = infoFile[0].name.replace('.info', '')
          item.name = infoName
        }

        item.loaded = true
      } catch {
        // thumbnail load failed
      }
    }

    loading.value = false
  }

  return { items, loading, loadBuiltinLibrary }
})
