import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { TileData, TileSetData } from '../types/engine'

export interface SpriteData {
  id: string
  x: number
  y: number
  angle: number
  scale: number
  scaleX: number
  scaleY: number
  visible: boolean
  layer: number
  imagePath: string
}

export interface SayData {
  spriteId: string
  text: string
  x: number
  y: number
}

export interface DrawTextData {
  id: string
  text: string
  x: number
  y: number
}

export interface HitboxData {
  spriteId: string
  rect: number[] | null
}

export interface CameraData {
  x: number
  y: number
  zoom: number
  limitLeft: number
  limitRight: number
  limitTop: number
  limitBottom: number
}

export interface RenderTileData {
  id: string
  x: number
  y: number
  layer: number
  type: 'tile' | 'image'
  tileId?: number
  tileSetIndex?: number
  tileSize: number
  imagePath?: string
  angle?: number
  scale?: number
  scaleX?: number
  scaleY?: number
  opacity?: number
}

export interface TileSetInfo {
  name: string
  imagePath: string
  tileWidth: number
  tileHeight: number
}

export const useRenderStore = defineStore('render', () => {
  const sprites = ref<Map<string, SpriteData>>(new Map())
  const tiles = ref<Map<string, RenderTileData>>(new Map())
  const tileSets = ref<TileSetInfo[]>([])
  const tileGridSize = ref(16)
  const sayTexts = ref<Map<string, SayData>>(new Map())
  const drawTexts = ref<Map<string, DrawTextData>>(new Map())
  const hitboxes = ref<Map<string, HitboxData>>(new Map())
  const camera = ref<CameraData>({
    x: 320,
    y: 240,
    zoom: 1.0,
    limitLeft: 0,
    limitRight: 640,
    limitTop: 0,
    limitBottom: 480,
  })
  const fps = ref(0)
  const isPaused = ref(false)

  const shakeIntensity = ref(0)
  const shakeDuration = ref(0)
  const shakeStartTime = ref(0)

  // 资源加载跟踪
  const textureTotal = ref(0)
  const textureLoaded = ref(0)
  const isLoadingTextures = ref(false)

  function createSprite(id: string, data: Partial<SpriteData>) {
    sprites.value.set(id, {
      id,
      x: data.x ?? 320,
      y: data.y ?? 240,
      angle: data.angle ?? 0,
      scale: data.scale ?? 1,
      scaleX: data.scaleX ?? 1,
      scaleY: data.scaleY ?? 1,
      visible: data.visible ?? true,
      layer: data.layer ?? 0,
      imagePath: data.imagePath ?? '',
    })
  }

  function updateSprite(id: string, data: Partial<SpriteData>) {
    const sprite = sprites.value.get(id)
    if (sprite) {
      Object.assign(sprite, data)
    }
  }

  function deleteSprite(id: string) {
    sprites.value.delete(id)
  }

  function createBatch(data: { tiles: TileData[]; tile_sets: TileSetData[]; tile_size: number }) {
    tiles.value.clear()
    tileSets.value = data.tile_sets.map(ts => ({
      name: ts.name,
      imagePath: ts.image || ts.image_path,
      tileWidth: ts.tile_width,
      tileHeight: ts.tile_height,
    }))
    tileGridSize.value = data.tile_size

    for (const tile of data.tiles) {
      tiles.value.set(tile.id, {
        id: tile.id,
        x: tile.x,
        y: tile.y,
        layer: tile.layer,
        type: tile.type,
        tileId: tile.tile_id,
        tileSetIndex: tile.tile_set_index,
        tileSize: tile.tile_size,
        imagePath: tile.image_path,
        angle: tile.angle,
        scale: tile.scale,
        scaleX: tile.scale_x,
        scaleY: tile.scale_y,
        opacity: tile.opacity,
      })
    }
  }

  function clearAll() {
    sprites.value.clear()
    tiles.value.clear()
    tileSets.value = []
    tileGridSize.value = 16
    sayTexts.value.clear()
    drawTexts.value.clear()
    hitboxes.value.clear()
    camera.value = {
      x: 320,
      y: 240,
      zoom: 1.0,
      limitLeft: 0,
      limitRight: 640,
      limitTop: 0,
      limitBottom: 480,
    }
    fps.value = 0
    shakeIntensity.value = 0
    resetTextureLoading()
  }

  function resetTextureLoading() {
    textureTotal.value = 0
    textureLoaded.value = 0
    isLoadingTextures.value = false
  }

  function setTextureTotal(total: number) {
    textureTotal.value = total
    isLoadingTextures.value = total > 0
  }

  function incrementTextureLoaded() {
    textureLoaded.value++
    if (textureLoaded.value >= textureTotal.value && textureTotal.value > 0) {
      isLoadingTextures.value = false
    }
  }

  function setLoadingState(loading: boolean) {
    isLoadingTextures.value = loading
  }

  function updateCamera(data: Partial<CameraData>) {
    Object.assign(camera.value, data)
  }

  function setFps(value: number) {
    fps.value = value
  }

  function triggerShake(intensity: number, duration: number) {
    shakeIntensity.value = intensity
    shakeDuration.value = duration
    shakeStartTime.value = performance.now()
  }

  function getShakeOffset(): { x: number; y: number } {
    if (shakeIntensity.value <= 0) return { x: 0, y: 0 }

    const elapsed = (performance.now() - shakeStartTime.value) / 1000
    if (elapsed >= shakeDuration.value) {
      shakeIntensity.value = 0
      return { x: 0, y: 0 }
    }

    const decay = 1 - elapsed / shakeDuration.value
    const intensity = shakeIntensity.value * decay
    return {
      x: (Math.random() - 0.5) * intensity * 2,
      y: (Math.random() - 0.5) * intensity * 2,
    }
  }

  function setSayText(spriteId: string, text: string) {
    if (!text) {
      sayTexts.value.delete(spriteId)
      return
    }
    const sprite = sprites.value.get(spriteId)
    if (sprite) {
      sayTexts.value.set(spriteId, {
        spriteId,
        text,
        x: sprite.x,
        y: sprite.y - 40,
      })
    }
  }

  function setDrawText(id: string, text: string, x: number, y: number) {
    if (!text) {
      drawTexts.value.delete(id)
      return
    }
    drawTexts.value.set(id, { id, text, x, y })
  }

  function setHitbox(spriteId: string, rect: number[] | null) {
    if (!rect) {
      hitboxes.value.delete(spriteId)
      return
    }
    hitboxes.value.set(spriteId, { spriteId, rect })
  }

  function removeHitbox(spriteId: string) {
    hitboxes.value.delete(spriteId)
  }

  return {
    sprites,
    tiles,
    tileSets,
    tileGridSize,
    sayTexts,
    drawTexts,
    hitboxes,
    camera,
    fps,
    isPaused,
    textureTotal,
    textureLoaded,
    isLoadingTextures,
    createSprite,
    updateSprite,
    deleteSprite,
    createBatch,
    clearAll,
    updateCamera,
    setFps,
    triggerShake,
    getShakeOffset,
    setSayText,
    setDrawText,
    setHitbox,
    removeHitbox,
    resetTextureLoading,
    setTextureTotal,
    incrementTextureLoaded,
    setLoadingState,
  }
})
