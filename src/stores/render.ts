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

/**
 * 启动超过该时长才把纯色遮罩升级为加载页。
 * 更快的启动完全不显示加载页，避免给高性能电脑凭空增加等待。
 */
const PAGE_REVEAL_MS = 200
/** 加载页一旦出现，最短停留时间：避免「刚出现就被撤掉」的割裂感 */
const PAGE_MIN_DWELL_MS = 150
/** 进度平滑时间常数（ms）：只朝目标值缓动、绝不后退，避免数值跳变 */
const PROGRESS_EASE_MS = 180

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
  // 启动遮罩：点击运行立刻盖住画布（纯色，无文字），防止露出旧画面/空画布；
  // 超过 PAGE_REVEAL_MS 仍未就绪才升级为带进度条的加载页；
  // 结束条件 = 引擎初始化完成（GAME_READY）+ 贴图全部就绪 + 本帧场景已同步
  const startupPending = ref(false)
  const engineReady = ref(false)
  const startupProgress = ref(0)
  /** 加载页（文字 + 进度条）是否已经出现；前 200ms 只有纯色遮罩 */
  const startupPageVisible = ref(false)
  let startupStartedAt = 0
  /** 加载页首次出现的时间点，用于保证最短停留 */
  let startupPageShownAt = 0
  /** 引擎进程真正拉起的时间点（前置准备阶段到此结束） */
  let engineLaunchedAt = 0
  /** 上一次进度推进的时间，用于按真实帧间隔做指数缓动 */
  let lastProgressTick = 0
  /** 内部浮点进度：只在整数变化时写回 ref，避免每帧触发整个布局重渲染 */
  let startupProgressRaw = 0

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

  /**
   * 清空场景。
   * preserveStartup = true：这是「新一轮运行」在加载页内部清场，只重置贴图计数，
   * 保留启动进度与计时（否则重启时进度条会先涨到十几再归零，看起来像卡了一下）。
   */
  function clearAll(options: { preserveStartup?: boolean } = {}) {
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
    if (options.preserveStartup) {
      textureTotal.value = 0
      textureLoaded.value = 0
      engineReady.value = false
    } else {
      resetTextureLoading()
    }
    // 通知画布：下一帧先销毁全部显示对象再重建，避免跨运行复用旧对象/旧纹理
    sceneEpoch.value++
  }

  function resetTextureLoading() {
    textureTotal.value = 0
    textureLoaded.value = 0
    isLoadingTextures.value = false
    startupPending.value = false
    engineReady.value = false
    startupPageVisible.value = false
    startupProgress.value = 0
    startupProgressRaw = 0
    engineLaunchedAt = 0
    startupPageShownAt = 0
  }

  /** 点击运行立刻盖上纯色遮罩（游戏模式），防止露出上一次运行的最后画面 */
  function beginStartupLoading() {
    textureTotal.value = 0
    textureLoaded.value = 0
    engineReady.value = false
    startupPending.value = true
    startupPageVisible.value = false
    startupProgress.value = 0
    startupProgressRaw = 0
    startupStartedAt = performance.now()
    lastProgressTick = startupStartedAt
    engineLaunchedAt = 0
    startupPageShownAt = 0
    isLoadingTextures.value = true
  }

  /** 前置准备（初始化项目 / 保存 / 写代码文件）完成，Python 进程即将拉起 */
  function markEngineLaunched() {
    if (!startupPending.value) return
    engineLaunchedAt = performance.now()
  }

  /** 引擎初始化完成（GAME_READY） */
  function noteEngineReady() {
    engineReady.value = true
  }

  function texturesReady(): boolean {
    return textureTotal.value === 0 || textureLoaded.value >= textureTotal.value
  }

  /**
   * 帧循环驱动进度推进（由 MainLayout 的 rAF 循环每帧调用）。
   * 同时负责「遮罩 → 加载页」的升级：启动超过 PAGE_REVEAL_MS 才出现文字和进度条。
   *
   * 各阶段目标值：
   * - 准备阶段 0→22%（时间缓动）
   * - 引擎启动 22→60%（Python 启动没有可观测总量，用时间缓动逼近，绝不静止）
   * - 资源加载 60→85%（真实贴图比例 + 缓慢爬升）
   * - 就绪收尾 99%
   * 进度只增不减，且按帧间隔做指数缓动，任何阶段切换都不会出现数值跳变。
   */
  function tickStartupProgress(now: number = performance.now()) {
    if (!startupPending.value) return

    // 200ms 还没启动完，才把纯色遮罩升级成真正的加载页
    if (!startupPageVisible.value && now - startupStartedAt >= PAGE_REVEAL_MS) {
      startupPageVisible.value = true
      startupPageShownAt = now
    }

    const dt = Math.min(Math.max(now - lastProgressTick, 0), 200)
    lastProgressTick = now

    let target: number
    if (engineReady.value && texturesReady()) {
      target = 99
    } else if (textureTotal.value > 0) {
      const ratio = Math.min(1, textureLoaded.value / textureTotal.value)
      // 最后 15% 留给引擎就绪与首帧，避免「资源加载完却还要干等」
      target = 60 + 25 * ratio
      // 贴图是逐张登记的（图像层更是一张张解码），比例可能早已接近 1 但还有后续资源，
      // 加一条不超过 85% 的缓慢爬升，保证这一阶段进度条不会长时间静止不动
      const creep = 60 + 20 * (1 - Math.exp(-(now - startupStartedAt) / 3000))
      target = Math.max(target, Math.min(85, creep))
    } else if (engineLaunchedAt > 0) {
      const elapsed = now - engineLaunchedAt
      target = 20 + 40 * (1 - Math.exp(-elapsed / 1500))
    } else {
      // 项目初始化 / 保存文件 / 等画布初始化：没有总量可统计，同样用缓动推进，
      // 老机器上某个环节慢一点也不会让进度条一动不动
      target = 22 * (1 - Math.exp(-(now - startupStartedAt) / 2500))
    }

    if (target <= startupProgressRaw) return
    const k = 1 - Math.exp(-dt / PROGRESS_EASE_MS)
    startupProgressRaw = Math.min(target, startupProgressRaw + (target - startupProgressRaw) * k)
    const rounded = Math.floor(startupProgressRaw)
    if (rounded > startupProgress.value) startupProgress.value = rounded
  }

  /**
   * 启动加载收尾：由 GameCanvas 在每帧同步完场景后调用。
   * 条件：引擎就绪 + 贴图全部加载完 + 本帧场景已同步。
   * 放在帧末而不是贴图计数回调里，避免「最后一张贴图刚解码完、还没贴到显示对象上」
   * 就提前撤销遮罩，露出占位画面。
   *
   * 时长的处理：
   * - 200ms 内就绪：加载页从未出现，直接撤掉遮罩，不补显示
   * - 加载页已出现：至少显示 PAGE_MIN_DWELL_MS，避免刚出现就被撤掉
   * 不再有额外的强制停留时间，就绪即走。
   */
  function tryFinishStartup(now: number = performance.now()) {
    if (!startupPending.value || !engineReady.value) return
    if (!texturesReady()) return
    if (startupPageVisible.value && now - startupPageShownAt < PAGE_MIN_DWELL_MS) return
    startupProgressRaw = 100
    startupProgress.value = 100
    startupPending.value = false
    isLoadingTextures.value = false
  }

  // 贴图计数只服务于进度，不再自行控制加载页显隐：
  // 运行中新建角色/加载新图片时若弹一次全屏「加载资源中」，就是肉眼可见的闪屏。
  // 覆盖层只在本轮启动（startupPending）期间显示。
  function setTextureTotal(total: number) {
    textureTotal.value = total
  }

  function incrementTextureLoaded() {
    textureLoaded.value++
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
    startupPageVisible,
    startupProgress,
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
    markEngineLaunched,
    noteEngineReady,
    tickStartupProgress,
    tryFinishStartup,
    setTextureTotal,
    incrementTextureLoaded,
    setLoadingState,
  }
})
