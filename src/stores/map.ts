import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface TileData {
  collision: boolean
  tag: string
  collisionType: string
  collisionShape?: { points: number[][] }
}

export interface TileSet {
  name: string
  imagePath: string
  resourceType: string
  tileWidth: number
  tileHeight: number
  collisionType: string
  collisionEnabled: boolean
  tiles: TileData[]
}

export interface MapLayer {
  id: number
  name: string
  type: 'drawing' | 'image'
  visible: boolean
  tiles: Record<string, number>
  images?: any[]
}

export interface MapData {
  name: string
  width: number
  height: number
  tileSize: number
  offsetX: number
  offsetY: number
  gravity: boolean
  layers: MapLayer[]
  tileSets: TileSet[]
}

export const useMapStore = defineStore('map', () => {
  const currentMapPath = ref('')
  const mapData = ref<MapData>({
    name: '未命名地图',
    width: 40,
    height: 30,
    tileSize: 16,
    offsetX: 0,
    offsetY: 0,
    gravity: false,
    layers: [
      {
        id: 0,
        name: '图层',
        type: 'drawing',
        visible: true,
        tiles: {},
      },
    ],
    tileSets: [],
  })

  const activeLayerIndex = ref(0)
  const showGrid = ref(true)

  function setMapPath(path: string) {
    currentMapPath.value = path
  }

  function loadMap(data: MapData) {
    mapData.value = data
  }

  function setTile(layerIndex: number, x: number, y: number, tileId: number) {
    const layer = mapData.value.layers[layerIndex]
    if (!layer) return

    const key = `${x},${y}`
    if (tileId === 0) {
      delete layer.tiles[key]
    } else {
      layer.tiles[key] = tileId
    }
  }

  function getTile(layerIndex: number, x: number, y: number): number {
    const layer = mapData.value.layers[layerIndex]
    if (!layer) return 0
    return layer.tiles[`${x},${y}`] ?? 0
  }

  function addLayer(name: string) {
    const newLayer: MapLayer = {
      id: mapData.value.layers.length,
      name,
      type: 'drawing',
      visible: true,
      tiles: {},
    }
    mapData.value.layers.push(newLayer)
    return mapData.value.layers.length - 1
  }

  function removeLayer(index: number) {
    if (index >= 0 && index < mapData.value.layers.length) {
      mapData.value.layers.splice(index, 1)
    }
  }

  function setActiveLayer(index: number) {
    activeLayerIndex.value = index
  }

  function toggleGrid() {
    showGrid.value = !showGrid.value
  }

  function addTileSet(tileSet: TileSet) {
    mapData.value.tileSets.push(tileSet)
  }

  function removeTileSet(index: number) {
    if (index >= 0 && index < mapData.value.tileSets.length) {
      mapData.value.tileSets.splice(index, 1)
    }
  }

  function setTileCollision(
    tileSetIndex: number,
    tileIndex: number,
    collision: boolean
  ) {
    const tileSet = mapData.value.tileSets[tileSetIndex]
    if (!tileSet) return

    while (tileSet.tiles.length <= tileIndex) {
      tileSet.tiles.push({
        collision: true,
        tag: '',
        collisionType: '图像',
      })
    }
    tileSet.tiles[tileIndex].collision = collision
  }

  return {
    currentMapPath,
    mapData,
    activeLayerIndex,
    showGrid,
    setMapPath,
    loadMap,
    setTile,
    getTile,
    addLayer,
    removeLayer,
    setActiveLayer,
    toggleGrid,
    addTileSet,
    removeTileSet,
    setTileCollision,
  }
})
