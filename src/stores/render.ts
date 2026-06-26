import { defineStore } from 'pinia'
import { ref } from 'vue'

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

export interface CameraData {
  x: number
  y: number
  zoom: number
  limitLeft: number
  limitRight: number
  limitTop: number
  limitBottom: number
}

export const useRenderStore = defineStore('render', () => {
  const sprites = ref<Map<string, SpriteData>>(new Map())
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

  function clearAll() {
    sprites.value.clear()
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

  return {
    sprites,
    camera,
    fps,
    isPaused,
    createSprite,
    updateSprite,
    deleteSprite,
    clearAll,
    updateCamera,
    setFps,
    triggerShake,
    getShakeOffset,
  }
})
