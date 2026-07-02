<script setup lang="ts">
import { ref, watch } from 'vue'
import MapToolbar from './MapToolbar.vue'
import MapCanvas from './MapCanvas.vue'
import ResourceListPanel from './ResourceListPanel.vue'
import PropertyPanel from './PropertyPanel.vue'
import LayerPanel from './LayerPanel.vue'
import { useMapStore } from '../../stores/map'
import { useResourceStore } from '../../stores/resource'
import JSZip from 'jszip'

const mapStore = useMapStore()
const resourceStore = useResourceStore()

const mapCanvasRef = ref<InstanceType<typeof MapCanvas>>()

const emit = defineEmits<{
  'open-resource-lib': []
}>()

// 自动保存到 localStorage + 资源列表（防抖 500ms）
let autoSaveTimer: ReturnType<typeof setTimeout> | null = null
watch(() => JSON.stringify(mapStore.mapData), () => {
  if (autoSaveTimer) clearTimeout(autoSaveTimer)
  autoSaveTimer = setTimeout(() => {
    if (mapStore.currentMapPath) {
      try {
        localStorage.setItem(`map_autosave_${mapStore.currentMapPath}`, JSON.stringify(mapStore.mapData))
      } catch {}
      saveMapToResource()
    }
  }, 500)
})

async function saveMapToResource() {
  const path = mapStore.currentMapPath
  if (!path) return
  const item = resourceStore.maps.find(m => m.id === path || m.name === path || m.path === path)
  if (!item) return

  try {
    const zip = new JSZip()
    zip.file('map.json', JSON.stringify(mapStore.mapData))

    // Get thumbnail from canvas
    const thumbDataUrl = mapCanvasRef.value?.getThumbnailDataUrl()
    if (thumbDataUrl) {
      const blob = await (await fetch(thumbDataUrl)).blob()
      zip.file('thumbnail.png', blob)
    }

    const blob = await zip.generateAsync({ type: 'blob' })
    const url = URL.createObjectURL(blob)
    // Revoke old URL to avoid memory leak
    if (item.path && item.path.startsWith('blob:')) URL.revokeObjectURL(item.path)
    item.path = url
  } catch {}
}

function onNewMap() {
  const mapCount = resourceStore.maps.length
  const name = `地图${mapCount + 1}`
  const id = resourceStore.addItem({ name, type: 'map', path: '' })
  mapStore.setMapPath(id)
  mapStore.loadMap({
    name,
    version: 5,
    width: 40,
    height: 30,
    tileSize: 16,
    offsetX: 0,
    offsetY: 0,
    gravity: false,
    collisionType: '图像',
    collisionEnabled: false,
    layers: [
      {
        id: 0,
        name: '图层',
        type: 'drawing',
        visible: true,
        tiles: {},
        resources: [],
        images: [],
      },
    ],
    tileSets: [],
  })
}

async function onImportMap() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.bgm,.zip'
  input.onchange = async (e: Event) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (!file) return

    try {
      const zip = await JSZip.loadAsync(file)

      // Try to read map.json (our format)
      const mapJsonEntry = zip.file('map.json')
      if (mapJsonEntry) {
        const data = JSON.parse(await mapJsonEntry.async('text'))
        mapStore.loadMap(data)
        mapStore.setMapPath(file.name)
        return
      }

      // Try to read legacy binary format (.info file)
      const infoFile = zip.file(/.*\.info$/)
      if (infoFile.length > 0) {
        const infoData = await infoFile[0].async('arraybuffer')
        const view = new DataView(infoData)
        let offset = 0

        // Read magic number
        const magic = view.getUint32(offset, false)
        offset += 4
        if (magic !== 0x4D415050) { // "MAP_"
          alert('无效的地图文件格式')
          return
        }

        // Read version
        const version = view.getUint32(offset, true)
        offset += 4

        // Read name
        const nameLen = view.getUint32(offset, true)
        offset += 4
        const nameBytes = new Uint8Array(infoData, offset, nameLen)
        const name = new TextDecoder().decode(nameBytes)
        offset += nameLen

        // Read dimensions
        const width = view.getUint32(offset, true)
        offset += 4
        const height = view.getUint32(offset, true)
        offset += 4
        const tileSize = view.getUint32(offset, true)
        offset += 4
        const offsetX = view.getInt32(offset, true)
        offset += 4
        const offsetY = view.getInt32(offset, true)
        offset += 4

        // Skip layer count (read from tiles file)
        offset += 4

        // Read gravity (v5+)
        let gravity = false
        if (version >= 5 && offset + 1 <= infoData.byteLength) {
          gravity = view.getUint8(offset) !== 0
          offset += 1
        }

        // Read tiles file for layer data
        const layers: any[] = []
        const tilesFile = zip.file(/.*\.tiles$/)
        if (tilesFile.length > 0) {
          const tilesData = await tilesFile[0].async('arraybuffer')
          const tView = new DataView(tilesData)
          let tOffset = 0

          // Tiles magic
          const tMagic = tView.getUint32(tOffset, false)
          tOffset += 4
          if (tMagic !== 0x54494C45) { // "TILE"
            alert('无效的瓦片文件格式')
            return
          }

          const tLayerCount = tView.getUint32(tOffset, true)
          tOffset += 4

          for (let i = 0; i < tLayerCount; i++) {
            // Layer name
            const lNameLen = tView.getUint32(tOffset, true)
            tOffset += 4
            const lNameBytes = new Uint8Array(tilesData, tOffset, lNameLen)
            const lName = new TextDecoder().decode(lNameBytes)
            tOffset += lNameLen

            // Visible
            const visible = tView.getUint8(tOffset) !== 0
            tOffset += 1

            // Type
            const typeCode = tView.getUint8(tOffset)
            tOffset += 1
            const type = typeCode === 1 ? 'image' : 'drawing'

            // Layer ID
            const layerId = tView.getUint32(tOffset, true)
            tOffset += 4

            // Read tile data (width * height * uint16)
            const tiles: Record<string, number> = {}
            for (let y = 0; y < height; y++) {
              for (let x = 0; x < width; x++) {
                const tileId = tView.getUint16(tOffset, true)
                tOffset += 2
                if (tileId !== 0) {
                  tiles[`${x},${y}`] = tileId
                }
              }
            }

            layers.push({ id: layerId, name: lName, type, visible, tiles, resources: [], images: [] })
          }
        }

        if (layers.length === 0) {
          layers.push({ id: 0, name: '图层', type: 'drawing', visible: true, locked: false, tiles: {}, resources: [], images: [] })
        }

        mapStore.loadMap({
          name,
          version,
          width,
          height,
          tileSize,
          offsetX,
          offsetY,
          gravity,
          collisionType: '图像',
          collisionEnabled: false,
          layers,
          tileSets: [],
        })
        mapStore.setMapPath(file.name)
      } else {
        alert('无法识别的地图文件格式')
      }
    } catch (err) {
      console.error('导入地图失败:', err)
      alert('导入地图失败: ' + (err as Error).message)
    }
  }
  input.click()
}

async function onExportMap() {
  const zip = new JSZip()
  const data = mapStore.mapData

  // Save as JSON (compact format)
  zip.file('map.json', JSON.stringify(data))

  // Also create legacy binary format
  // .info file
  const nameBytes = new TextEncoder().encode(data.name)
  const infoSize = 4 + 4 + 4 + nameBytes.length + 4 + 4 + 4 + 4 + 4 + 4 + 1
  const infoBuilder = new ArrayBuffer(infoSize)
  const infoView = new DataView(infoBuilder)
  let offset = 0

  // Magic
  infoView.setUint32(offset, 0x4D415050, false)
  offset += 4
  // Version
  infoView.setUint32(offset, data.version, true)
  offset += 4
  // Name
  infoView.setUint32(offset, nameBytes.length, true)
  offset += 4
  new Uint8Array(infoBuilder, offset, nameBytes.length).set(nameBytes)
  offset += nameBytes.length
  // Dimensions
  infoView.setUint32(offset, data.width, true)
  offset += 4
  infoView.setUint32(offset, data.height, true)
  offset += 4
  infoView.setUint32(offset, data.tileSize, true)
  offset += 4
  infoView.setInt32(offset, data.offsetX, true)
  offset += 4
  infoView.setInt32(offset, data.offsetY, true)
  offset += 4
  // Layer count
  infoView.setUint32(offset, data.layers.length, true)
  offset += 4
  // Gravity
  infoView.setUint8(offset, data.gravity ? 1 : 0)
  offset += 1

  zip.file(`${data.name}.info`, infoBuilder.slice(0, offset))

  // .tiles file
  const tilesSize = 8 + data.layers.reduce((sum, layer) => {
    return sum + 4 + layer.name.length + 1 + 1 + 4 + data.width * data.height * 2
  }, 0)
  const tilesBuilder = new ArrayBuffer(tilesSize)
  const tilesView = new DataView(tilesBuilder)
  let tOffset = 0

  // Magic
  tilesView.setUint32(tOffset, 0x54494C45, false)
  tOffset += 4
  // Layer count
  tilesView.setUint32(tOffset, data.layers.length, true)
  tOffset += 4

  for (const layer of data.layers) {
    // Name
    const lNameBytes = new TextEncoder().encode(layer.name)
    tilesView.setUint32(tOffset, lNameBytes.length, true)
    tOffset += 4
    new Uint8Array(tilesBuilder, tOffset, lNameBytes.length).set(lNameBytes)
    tOffset += lNameBytes.length
    // Visible
    tilesView.setUint8(tOffset, layer.visible ? 1 : 0)
    tOffset += 1
    // Type
    tilesView.setUint8(tOffset, layer.type === 'image' ? 1 : 0)
    tOffset += 1
    // Layer ID
    tilesView.setUint32(tOffset, layer.id, true)
    tOffset += 4
    // Tile data
    for (let y = 0; y < data.height; y++) {
      for (let x = 0; x < data.width; x++) {
        const tileId = layer.tiles[`${x},${y}`] ?? 0
        tilesView.setUint16(tOffset, tileId, true)
        tOffset += 2
      }
    }
  }

  zip.file(`${data.name}.tiles`, tilesBuilder.slice(0, tOffset))

  // Generate zip and download
  const blob = await zip.generateAsync({ type: 'blob' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${data.name}.bgm`
  a.click()
  URL.revokeObjectURL(url)

  // Also save to resource store
  const item = resourceStore.maps.find(m => m.id === mapStore.currentMapPath || m.name === data.name)
  if (item) {
    if (item.path && item.path.startsWith('blob:')) URL.revokeObjectURL(item.path)
    item.path = url
  }
}

function onOpenLibrary() {
  emit('open-resource-lib')
}

function onCursorMove(x: number, y: number) {
  mapStore.setCursorPos(x, y)
}
</script>

<template>
  <div class="map-editor-view">
    <div class="map-editor-body">
      <ResourceListPanel
        @open-library="onOpenLibrary"
        @select-tile="(rIdx, tIdx) => mapStore.selectTile(rIdx, tIdx)"
      />
      <div class="map-editor-center">
        <MapToolbar
          @new-map="onNewMap"
          @import-map="onImportMap"
          @export-map="onExportMap"
        />
        <MapCanvas ref="mapCanvasRef" class="map-canvas-area" @cursor-move="onCursorMove" />
        <div class="map-info-bar">
          <span class="info-spacer" />
          <span class="info-label">ID:{{ mapStore.currentMapPath ? mapStore.currentMapPath.split('/').pop()?.split('.')[0] ?? '--' : '--' }}</span>
          <span class="info-label">场景大小:{{ mapStore.mapData.width * mapStore.mapData.tileSize }}×{{ mapStore.mapData.height * mapStore.mapData.tileSize }}</span>
          <span class="info-label">坐标:{{ mapStore.cursorX ?? '--' }},{{ mapStore.cursorY ?? '--' }}</span>
          <span class="info-label">资源尺寸:{{ mapStore.selectedResource?.tileWidth ?? '--' }}×{{ mapStore.selectedResource?.tileHeight ?? '--' }}</span>
          <span class="info-spacer" />
        </div>
      </div>
      <div class="map-editor-right">
        <PropertyPanel />
        <LayerPanel />
      </div>
    </div>
  </div>
</template>

<style scoped>
.map-editor-view {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: rgb(30, 30, 30);
}

.map-editor-body {
  flex: 1;
  min-height: 0;
  display: flex;
}

.map-editor-center {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.map-canvas-area {
  flex: 1;
  min-height: 0;
}

.map-info-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  gap: 20px;
  background: rgb(34, 37, 43);
  flex-shrink: 0;
}

.info-spacer {
  flex: 1;
}

.info-label {
  font-size: 12px;
  color: rgb(156, 160, 164);
  white-space: nowrap;
}

.map-editor-right {
  display: flex;
  flex-direction: column;
  width: 272px;
  min-width: 272px;
  border-left: 1px solid rgb(12, 12, 12);
  background: rgb(34, 37, 43);
}
</style>
