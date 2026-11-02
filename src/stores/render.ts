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
  /** 内容重心相对图片中心的偏移（像素），用于修正翻转/旋转锚点 */
  vox: number
  voy: number
  /** .bsf 精灵：帧在 sheet 贴图中的 UV 区域 [x, y, w, h]；null = 整张贴图 */
  frameRect: number[] | null
  /** 当前帧内容的自然尺寸（引擎 raw_cw/raw_ch）：自动渲染模式据此判定最近邻还是平滑 */
  frameW?: number
  frameH?: number
  /** 需要一并预载的贴图路径（.bgs 目录角色的全部帧文件），用于真实、一次性的加载进度 */
  preloadPaths?: string[]
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

/** 启动加载页最短显示时间：快电脑上避免一闪而过（慢电脑实际耗时更长，不受影响） */
const MIN_STARTUP_MS = 500

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
  const prevCamera = ref<CameraData>({ ...camera.value })
  const targetCamera = ref<CameraData>({ ...camera.value })
  const cameraUpdateTime = ref(0)
  const fps = ref(0)
  const isPaused = ref(false)
  // 场景代次：每次清场（clearAll）自增，GameCanvas 据此在下一帧先销毁全部显示对象再同步新数据。
  // 必须有这一层：新一次运行创建的角色 id 会与上一轮残留的显示对象撞号
  // （引擎按 1、2、3 递增编号），直接复用旧对象会连旧纹理一起保留 → 渲染出错图。
  const sceneEpoch = ref(0)

  // 调试工具状态
  const showFps = ref(false)
  const showCollision = ref(false)
  const showStats = ref(false)

  const shakeIntensity = ref(0)
  const shakeDuration = ref(0)
  const shakeStartTime = ref(0)

  // 资源加载跟踪
  const textureTotal = ref(0)
  const textureLoaded = ref(0)
  const isLoadingTextures = ref(false)
  // 启动加载：点击运行就立即显示加载页，避免先露出默认背景色再闪一下加载页；
  // 结束条件 = 引擎初始化完成（GAME_READY）+ 贴图全部就绪 + 帧循环已同步场景，
  // 且加载页至少显示 MIN_STARTUP_MS，避免快电脑上一闪而过被看成故障闪烁
  const startupPending = ref(false)
  const engineReady = ref(false)
  let startupStartedAt = 0

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
      vox: data.vox ?? 0,
      voy: data.voy ?? 0,
      frameRect: data.frameRect ?? null,
      frameW: data.frameW,
      frameH: data.frameH,
      preloadPaths: data.preloadPaths,
    })
  }

  function updateSprite(id: string, data: Partial<SpriteData>) {
    const sprite = sprites.value.get(id)
    if (sprite) {
      // 只合并有值的字段：局部更新（比如只改 layer）不会把 x/y/角度等清成 undefined
      for (const [key, value] of Object.entries(data)) {
        if (value !== undefined) {
          (sprite as Record<string, any>)[key] = value
        }
      }
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
    prevCamera.value = { ...camera.value }
    targetCamera.value = { ...camera.value }
    cameraUpdateTime.value = 0
    fps.value = 0
    isPaused.value = false
    showFps.value = false
    showCollision.value = false
    showStats.value = false
    shakeIntensity.value = 0
    resetTextureLoading()
    // 通知画布：下一帧先销毁全部显示对象再重建，避免跨运行复用旧对象/旧纹理
    sceneEpoch.value++
  }

  function resetTextureLoading() {
    textureTotal.value = 0
    textureLoaded.value = 0
    isLoadingTextures.value = false
    startupPending.value = false
    engineReady.value = false
  }

  /** 点击运行立刻进入加载页（游戏模式），覆盖 Python 启动期间的默认背景色空档 */
  function beginStartupLoading() {
    textureTotal.value = 0
    textureLoaded.value = 0
    engineReady.value = false
    startupPending.value = true
    startupStartedAt = performance.now()
    isLoadingTextures.value = true
  }

  /** 引擎初始化完成（GAME_READY） */
  function noteEngineReady() {
    engineReady.value = true
  }

  /**
   * 启动加载收尾：由 GameCanvas 在每帧同步完场景后调用。
   * 条件都满足才隐藏覆盖层：引擎就绪、贴图全部加载完、本帧已完成场景同步，
   * 并且加载页已显示满 MIN_STARTUP_MS（快电脑也别一闪而过；慢电脑本来就超过，不受影响）。
   * 放在帧末而不是贴图计数回调里，避免「最后一张贴图刚解码完、还没贴到显示对象上」
   * 就提前撤销覆盖层，露出占位画面。
   */
  function tryFinishStartup() {
    if (!startupPending.value || !engineReady.value) return
    if (textureTotal.value > 0 && textureLoaded.value < textureTotal.value) return
    if (performance.now() - startupStartedAt < MIN_STARTUP_MS) return
    startupPending.value = false
    isLoadingTextures.value = false
  }

  function setTextureTotal(total: number) {
    textureTotal.value = total
    isLoadingTextures.value = total > 0
  }

  function incrementTextureLoaded() {
    textureLoaded.value++
    // 启动阶段不在计数回调里收尾，交给帧循环的 tryFinishStartup
    if (startupPending.value) return
    if (textureLoaded.value >= textureTotal.value && textureTotal.value > 0) {
      isLoadingTextures.value = false
    }
  }

  function setLoadingState(loading: boolean) {
    isLoadingTextures.value = loading
  }

  function updateCamera(data: Partial<CameraData>) {
    prevCamera.value = { ...camera.value }
    Object.assign(camera.value, data)
    targetCamera.value = { ...camera.value }
    cameraUpdateTime.value = performance.now()
  }

  function getInterpolatedCamera(): CameraData {
    const dt = performance.now() - cameraUpdateTime.value
    const t = Math.min(dt / 16.67, 1) // 归一化到 [0, 1]，16.67ms = 60fps 周期
    return {
      x: prevCamera.value.x + (targetCamera.value.x - prevCamera.value.x) * t,
      y: prevCamera.value.y + (targetCamera.value.y - prevCamera.value.y) * t,
      zoom: prevCamera.value.zoom + (targetCamera.value.zoom - prevCamera.value.zoom) * t,
      limitLeft: targetCamera.value.limitLeft,
      limitRight: targetCamera.value.limitRight,
      limitTop: targetCamera.value.limitTop,
      limitBottom: targetCamera.value.limitBottom,
    }
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
        // 存精灵原始 y，气泡上浮偏移由 GameCanvas 按字号动态计算
        y: sprite.y,
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
    sceneEpoch,
    showFps,
    showCollision,
    showStats,
    textureTotal,
    textureLoaded,
    isLoadingTextures,
    startupPending,
    createSprite,
    updateSprite,
    deleteSprite,
    createBatch,
    clearAll,
    updateCamera,
    getInterpolatedCamera,
    setFps,
    triggerShake,
    getShakeOffset,
    setSayText,
    setDrawText,
    setHitbox,
    removeHitbox,
    resetTextureLoading,
    beginStartupLoading,
    noteEngineReady,
    tryFinishStartup,
    setTextureTotal,
    incrementTextureLoaded,
    setLoadingState,
  }
})
