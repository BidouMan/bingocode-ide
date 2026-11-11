<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { useRenderStore } from '../../stores/render'
import { useEditorStore } from '../../stores/editor'
import { useSettingsStore } from '../../stores/settings'
import { useEngine } from '../../composables/useEngine'
import { signalGameCanvasReady, resetGameCanvasReady } from '../../utils/gameCanvasReady'
import { detectPixelArt, effectiveScaleMode } from '../../utils/renderMode'
// 模块级共享缓存：MainLayout 同时挂着两个 GameCanvas 实例（预览窗 + 全屏 v-show 窗），
// 若各实例自持缓存，同一文件会重复走 IPC 加载且渲染 store 的贴图计数器被翻倍登记，
// 「加载资源中」覆盖层的进度与完成判定随之失真（表现为覆盖层随动画节奏闪烁）。
// 运行开始由 useEngine.run() 调用 invalidateGameTextures() 统一清空。
// frameTextureCache 的 key = sheet路径#x,y,w,h（.bsf UV 取帧，复用同一张 BaseTexture）
import {
  sharedTextureCache as textureCache,
  sharedTilesetFrameCache as tilesetFrameCache,
  sharedFrameTextureCache as frameTextureCache,
  sharedInFlightTextures,
} from '../../utils/gameTextures'
import {
  processStats,
  startProcessStatsPolling,
  stopProcessStatsPolling,
} from '../../utils/processStats'

const renderStore = useRenderStore()
const editorStore = useEditorStore()
const settingsStore = useSettingsStore()
const engine = useEngine()

const containerRef = ref<HTMLDivElement>()

const emit = defineEmits<{
  /** 实际游戏画面区域（640×480 等比缩放后在容器内的矩形），用于工具栏对齐与加载遮罩定位 */
  'offset-update': [rect: { left: number; top: number; width: number; height: number }]
}>()

// 当前画布是否处于可见/激活状态。MainLayout 同时挂两个 GameCanvas（预览窗 + 全屏窗），
// 不可见的那个应停止 PixiJS ticker，避免双倍 60fps 渲染占满 CPU。
const props = defineProps<{
  active?: boolean
}>()

let app: any = null
let PIXI: any = null
let spriteDisplayObjects: Map<string, any> = new Map()
let tileDisplayObjects: Map<string, any> = new Map()
let sayDisplayObjects: Map<string, any> = new Map()
let drawTextDisplayObjects: Map<string, any> = new Map()
let hitboxDisplayObjects: Map<string, any> = new Map()
let gameContainer: any = null
let tileLayerContainer: any = null
let spriteContainer: any = null
let uiContainer: any = null
let stageContainer: any = null
let currentScaleMode: 'nearest' | 'linear' = 'linear'
/**
 * 自动模式下每个纹理源的采样方式：只判定一次（WeakMap，按纹理源缓存）。
 * 判定依据是素材自然尺寸（引擎 raw_cw/raw_ch），是静态属性——
 * 不随缩放/帧变化，所以每帧零成本，也不会在阈值附近来回翻。
 */
let autoScaleModes = new WeakMap<object, 'nearest' | 'linear'>()
let resizeObserver: ResizeObserver | null = null
let tilesSyncing = false
let spritesSyncing = false
// 已应用到的场景代次：与 renderStore.sceneEpoch 不一致时先整体清场（见 gameLoop）
let appliedSceneEpoch = -1

const LOGIC_W = 640
const LOGIC_H = 480

// 游戏画面在容器内的偏移（用于统计面板定位）
const stageOffsetX = ref(0)
const stageOffsetY = ref(0)

async function initPixi() {
  if (!containerRef.value) return

  PIXI = await import('pixi.js')

  // 根据当前渲染模式设置初始 scaleMode
  currentScaleMode = editorStore.renderMode === 'pixelated' ? 'nearest' : 'linear'

  app = new PIXI.Application()
  await app.init({
    background: '#1a1c21',
    backgroundAlpha: 1,
    // 性能模式关闭抗锯齿：MSAA 对老集显（如 HD Graphics 3000）开销很可观
    antialias: !settingsStore.perfMode,
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
    // 优先使用高性能 GPU：低端集显机器走集显，双显卡机器走独显，避免用软件渲染
    powerPreference: 'high-performance',
  })

  containerRef.value.appendChild(app.canvas)
  // 挡住 WebGL resize 时 canvas 属性重设导致的黑闪
  app.canvas.style.background = '#1a1c21'

  stageContainer = new PIXI.Container()
  gameContainer = new PIXI.Container()

  // 分层容器：瓦片层 / 精灵层 / UI层
  tileLayerContainer = new PIXI.Container()
  tileLayerContainer.sortableChildren = true
  spriteContainer = new PIXI.Container()
  spriteContainer.sortableChildren = true
  uiContainer = new PIXI.Container()
  gameContainer.addChild(tileLayerContainer)
  gameContainer.addChild(spriteContainer)
  gameContainer.addChild(uiContainer)

  const gameBg = new PIXI.Graphics()
  gameBg.rect(0, 0, LOGIC_W, LOGIC_H)
  gameBg.fill({ color: 0x363a45 })
  stageContainer.addChild(gameBg)

  stageContainer.addChild(gameContainer)
  app.stage.addChild(stageContainer)

  const mask = new PIXI.Graphics()
  mask.rect(0, 0, LOGIC_W, LOGIC_H)
  mask.fill({ color: 0x000000 })
  stageContainer.mask = mask
  stageContainer.addChild(mask)

  handleResize()

  const ro = new ResizeObserver(() => handleResize())
  ro.observe(containerRef.value)
  resizeObserver = ro
}

let resizeTicking = false
// 启动阶段 MainLayout 还是加载屏（display:none），容器尺寸为 0；
// 此时不能 resize 到 0×0，改为按帧重试，等界面真正显示后自动完成首次尺寸校准。
// 否则画布会一直停留在 Pixi 的默认尺寸，运行后画面像是「没反应」，
// 必须重新挂载（切模式）才会正常。
let resizeRetryFrames = 0
const MAX_RESIZE_RETRY_FRAMES = 240

/** resize 后立即同步渲染，避免 WebGL buffer 重置导致的空帧闪烁，使用 RAF 防抖 */
function handleResize() {
  if (!app || !containerRef.value) return
  if (resizeTicking) return
  resizeTicking = true
  requestAnimationFrame(() => {
    resizeTicking = false
    if (!app || !containerRef.value) return
    const vp = containerRef.value
    // 全屏页/预览页用 v-show 隐藏时容器尺寸为 0：此时绝不能 resize 到 0×0，
    // 否则 WebGL 帧缓冲变成 0 尺寸，重新显示时旧画面会残留在画布上（表现为
    // 「最大化后窗口还是很久以前那个程序」）。等重新显示时 ResizeObserver 再触发。
    if (vp.clientWidth === 0 || vp.clientHeight === 0) {
      // 窗口隐藏时 rAF 会暂停，恢复后这条重试链继续执行，不需要额外监听 show 事件
      if (resizeRetryFrames < MAX_RESIZE_RETRY_FRAMES) {
        resizeRetryFrames++
        handleResize()
      }
      return
    }
    resizeRetryFrames = 0
    app.renderer.resize(vp.clientWidth, vp.clientHeight)
    fitStage()
    app.renderer.render(app.stage)
  })
}

function fitStage() {
  if (!app || !containerRef.value) return
  const vp = containerRef.value
  if (vp.clientWidth === 0 || vp.clientHeight === 0) return
  const scaleX = vp.clientWidth / LOGIC_W
  const scaleY = vp.clientHeight / LOGIC_H
  const scale = Math.min(scaleX, scaleY)
  stageContainer.x = (vp.clientWidth - LOGIC_W * scale) / 2
  stageContainer.y = (vp.clientHeight - LOGIC_H * scale) / 2
  stageContainer.scale.set(scale)
  stageOffsetX.value = stageContainer.x
  stageOffsetY.value = stageContainer.y
  emit('offset-update', {
    left: stageContainer.x,
    top: stageContainer.y,
    width: LOGIC_W * scale,
    height: LOGIC_H * scale,
  })
}

function applyRenderMode() {
  if (!PIXI) return
  const mode = editorStore.renderMode
  currentScaleMode = mode === 'pixelated' ? 'nearest' : 'linear'
  // 清空纹理缓存，强制使用新的 scaleMode 重新创建
  textureCache.clear()
  tilesetFrameCache.clear()
  frameTextureCache.clear()
  autoScaleModes = new WeakMap()
  // 已创建的精灵仍持有旧 scaleMode 的纹理：清掉 texKey 让下一帧重新取纹理
  for (const obj of spriteDisplayObjects.values()) obj._texKey = null
  // 已放置的瓦片/图像图层：显式模式直接改纹理源的采样方式，不重建对象
  // （重建要重新加载全部贴图，会闪烁且更耗性能）。
  // auto 模式不再强制：autoScaleModes 已清空，下一帧 syncTiles 会按内容尺寸重新判定
  if (mode !== 'auto') {
    for (const obj of tileDisplayObjects.values()) {
      const source = obj.texture?.source
      if (source && source.scaleMode !== currentScaleMode) source.scaleMode = currentScaleMode
    }
  }
}

/**
 * 自动渲染模式：与角色编辑器共用同一套判定——先看画风（像素画/插画），
 * 画风分析不出时再按素材自然尺寸兜底（小图最近邻、大插画平滑）。
 * 每个纹理源只判定一次，之后每帧只是一次 WeakMap 查表，无逐帧计算。
 */
function applyAutoScaleMode(
  texture: any,
  spriteData: { frameW?: number; frameH?: number; imagePath?: string }
) {
  const source = texture?.source
  if (!source || editorStore.renderMode !== 'auto') return
  const cached = autoScaleModes.get(source)
  if (cached) return
  // 矢量素材（SVG）恒平滑：它按目标像素重绘，最近邻会把栅格化锯齿固化下来
  const isVector = !!spriteData.imagePath?.toLowerCase().endsWith('.svg')
  // 纹理源就是解码后的图片/图集，就地分析画风（.bsf 源是整张 sheet，同一包画风一致）
  let pixelArt: boolean | null = null
  if (!isVector) {
    const res: any = source.resource
    const w = res?.naturalWidth || res?.videoWidth || res?.width
    const h = res?.naturalHeight || res?.videoHeight || res?.height
    if (w && h) pixelArt = detectPixelArt(res as CanvasImageSource, w, h)
  }
  const mode = isVector
    ? 'linear'
    : effectiveScaleMode('auto', spriteData.frameW, spriteData.frameH, pixelArt)
  autoScaleModes.set(source, mode)
  if (source.scaleMode !== mode) source.scaleMode = mode
}

function getTexture(imagePath: string): Promise<any> {
  if (textureCache.has(imagePath)) {
    return Promise.resolve(textureCache.get(imagePath))
  }
  // 同帧/并发对同一路径的请求合并为一次加载、一次计数
  const pending = sharedInFlightTextures.get(imagePath)
  if (pending) {
    return pending
  }

  const promise = loadTexture(imagePath).finally(() => {
    sharedInFlightTextures.delete(imagePath)
  })
  sharedInFlightTextures.set(imagePath, promise)
  return promise
}

/** 从 dataURL 手动解码创建纹理：绕过 PixiJS Assets 缓存，确保 scaleMode 在 GPU 上传前设好 */
async function createTextureFromDataUrl(url: string): Promise<any> {
  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const el = new Image()
    el.crossOrigin = 'anonymous'
    el.onload = () => resolve(el)
    el.onerror = () => reject(new Error(`Image load failed: ${url.substring(0, 80)}...`))
    el.src = url
  })
  const source = new PIXI.BufferImageSource({
    resource: img,
    scaleMode: currentScaleMode,
  })
  return new PIXI.Texture(source)
}

function placeholderTexture(): any {
  if (!app) return PIXI.Texture.EMPTY
  const g = new PIXI.Graphics()
  g.rect(0, 0, 32, 32)
  g.fill({ color: 0xff00ff })
  return app.renderer.generateTexture(g)
}

async function loadTexture(imagePath: string): Promise<any> {
  // 增加总数计数
  renderStore.setTextureTotal(renderStore.textureTotal + 1)

  try {
    const isLocal = imagePath.startsWith('/') || imagePath.match(/^[A-Z]:\\/i)
    let url: string
    if (isLocal) {
      // 本地文件用 Tauri invoke 读取 data URL（避免 convertFileSrc 对中文路径编码问题）
      url = await invoke<string>('read_image_as_data_url', { path: imagePath })
    } else {
      url = imagePath
    }
    const texture = await createTextureFromDataUrl(url)
    textureCache.set(imagePath, texture)
    // 增加已加载计数
    renderStore.incrementTextureLoaded()
    return texture
  } catch (e) {
    console.warn(`[GameCanvas] 加载纹理失败: ${imagePath}`, e)
    const placeholder = placeholderTexture()
    if (!placeholder) return null
    textureCache.set(imagePath, placeholder)
    // 增加已加载计数（失败也算加载完成）
    renderStore.incrementTextureLoaded()
    return placeholder
  }
}

/**
 * 批量预载（.bgs 逐帧清单）：一次 IPC 读回全部文件，再并发解码。
 * 之前每帧一次 IPC 往返 + base64，固定开销 × N，机械盘/老机器上进度条明显偏慢；
 * 现在往返次数 N→1，总数一次性登记为真实文件数，每解码完一张推进一格真实进度。
 */
async function preloadTextures(paths: string[]): Promise<void> {
  const missing = [...new Set(paths)].filter(
    p => !textureCache.has(p) && !sharedInFlightTextures.has(p),
  )
  if (missing.length === 0) return

  // 整批登记真实总量（在任何解码完成前），覆盖层从 0% 开始
  renderStore.setTextureTotal(renderStore.textureTotal + missing.length)

  const batch = (async () => {
    let results: (string | null)[] = missing.map(() => null)
    try {
      results = await invoke<(string | null)[]>('read_images_as_data_urls', { paths: missing })
    } catch (e) {
      console.warn('[GameCanvas] 批量读取贴图失败:', e)
    }
    await Promise.all(
      missing.map(async (p, i) => {
        try {
          const dataUrl = results[i]
          if (!dataUrl) throw new Error('文件读取失败')
          const texture = await createTextureFromDataUrl(dataUrl)
          textureCache.set(p, texture)
        } catch (e) {
          console.warn(`[GameCanvas] 预载失败: ${p}`, e)
          textureCache.set(p, placeholderTexture())
        }
        renderStore.incrementTextureLoaded()
      }),
    )
  })()

  for (const p of missing) sharedInFlightTextures.set(p, batch)
  try {
    await batch
  } finally {
    for (const p of missing) sharedInFlightTextures.delete(p)
  }
}

async function getTileFrame(tileSetIndex: number, tileId: number): Promise<any> {
  const tileSet = renderStore.tileSets[tileSetIndex]
  if (!tileSet) return null

  const cacheKey = `${tileSet.imagePath}_${tileSet.tileWidth}_${tileSet.tileHeight}`
  if (!tilesetFrameCache.has(cacheKey)) {
    tilesetFrameCache.set(cacheKey, new Map())
  }
  const frameCache = tilesetFrameCache.get(cacheKey)!

  if (frameCache.has(tileId)) {
    return frameCache.get(tileId)
  }

  const baseTexture = await getTexture(tileSet.imagePath)
  if (!baseTexture || !baseTexture.source) return null

  const cols = Math.floor(baseTexture.width / tileSet.tileWidth)
  const row = Math.floor((tileId - 1) / cols)
  const col = (tileId - 1) % cols

  const frame = new PIXI.Rectangle(
    col * tileSet.tileWidth,
    row * tileSet.tileHeight,
    tileSet.tileWidth,
    tileSet.tileHeight,
  )

  const texture = new PIXI.Texture({ source: baseTexture.source, frame })
  frameCache.set(tileId, texture)
  return texture
}

/** 精灵纹理：普通角色用整张贴图；.bsf 角色按 frameRect 从 sheet 裁子纹理（一次解码，多帧复用） */
async function getSpriteTexture(imagePath: string, frameRect?: number[] | null): Promise<any> {
  const base = await getTexture(imagePath)
  if (!base || !base.source || !frameRect || frameRect.length !== 4) return base

  const key = `${imagePath}#${frameRect.join(',')}`
  if (frameTextureCache.has(key)) return frameTextureCache.get(key)

  const texture = new PIXI.Texture({
    source: base.source,
    frame: new PIXI.Rectangle(frameRect[0], frameRect[1], frameRect[2], frameRect[3]),
  })
  frameTextureCache.set(key, texture)
  return texture
}

/**
 * 同步取缓存里的精灵纹理：预览窗从角色编辑器切回代码页重新挂载时，
 * 共享缓存里已有上一轮的贴图，直接同步命中可避免一帧的透明占位闪烁。
 * 未命中返回 null，由调用方走异步 getSpriteTexture 加载。
 */
function getCachedSpriteTextureSync(imagePath: string, frameRect?: number[] | null): any | null {
  const base = textureCache.get(imagePath)
  if (!base) return null
  if (!frameRect || frameRect.length !== 4) return base
  const key = `${imagePath}#${frameRect.join(',')}`
  return frameTextureCache.get(key) ?? null
}

async function syncSprites() {
  if (!app || !spriteContainer || spritesSyncing) return
  spritesSyncing = true

  const currentSpriteIds = new Set(renderStore.sprites.keys())

  for (const [id, displayObj] of spriteDisplayObjects) {
    if (!currentSpriteIds.has(id)) {
      spriteContainer.removeChild(displayObj)
      displayObj.destroy()
      spriteDisplayObjects.delete(id)
    }
  }

  const sortedSprites = Array.from(renderStore.sprites.values())
    .sort((a, b) => a.layer - b.layer)

  for (const spriteData of sortedSprites) {
    let displayObj = spriteDisplayObjects.get(spriteData.id)

    if (!displayObj) {
      // 同步创建：先用 1x1 透明占位，避免 await 导致并发重复创建
      displayObj = new PIXI.Sprite(PIXI.Texture.EMPTY)
      displayObj.anchor = { x: 0.5, y: 0.5 }
      spriteContainer.addChild(displayObj)
      spriteDisplayObjects.set(spriteData.id, displayObj)

      // .bgs 目录角色：批量预载全部帧文件（清单由 CREATE 指令的 config.frames 生成）。
      // 总数一次性登记为真实总量，覆盖层只做一次显隐——
      // 而不是动画播放时逐帧追着加载、闪个不停
      if (spriteData.preloadPaths?.length) {
        preloadTextures(spriteData.preloadPaths)
      }
    }

    // 纹理脏检查：路径或 sheet 帧区域变化才重新取纹理（.bsf 动画 = 路径不变、rect 变）
    if (spriteData.imagePath) {
      const texKey = spriteData.frameRect
        ? `${spriteData.imagePath}#${spriteData.frameRect.join(',')}`
        : spriteData.imagePath
      if (displayObj._texKey !== texKey) {
        displayObj._texKey = texKey
        // 先同步命中缓存：预览窗重挂载时共享缓存已有上一轮贴图，直接贴上可零闪烁恢复最后一帧；
        // 未命中再走异步加载（首帧用 Texture.EMPTY 透明占位，加载完成后替换）。
        const cached = getCachedSpriteTextureSync(spriteData.imagePath, spriteData.frameRect)
        if (cached) {
          displayObj.texture = cached
          applyAutoScaleMode(cached, spriteData)
        }
        getSpriteTexture(spriteData.imagePath, spriteData.frameRect).then(texture => {
          if (displayObj && !displayObj.destroyed && displayObj._texKey === texKey) {
            displayObj.texture = texture
            applyAutoScaleMode(texture, spriteData)
          }
        })
      }
    }

    if (displayObj) {
      // 自动渲染判定（已判定过的纹理源直接命中缓存返回，逐帧开销≈一次 WeakMap 查表）
      applyAutoScaleMode(displayObj.texture, spriteData)
      // 脏检查：只在实际数据变化时更新属性
      const displayAngle = spriteData.angle * Math.PI / 180
      // scale_x/scale_y 已含最终缩放（base×flip），直接使用，不能再乘 scale（会平方）
      const s = spriteData.scaleX ?? spriteData.scale ?? 1
      const sy = spriteData.scaleY ?? spriteData.scale ?? 1
      // pivot 控制旋转/翻转中心：用内容重心偏移（vox/voy）替代图片几何中心，
      // 使 fish_2 等非居中素材翻转时不产生视觉跳动
      const pivotX = spriteData.vox ?? 0
      const pivotY = spriteData.voy ?? 0
      const propsKey = `${spriteData.x.toFixed(1)},${spriteData.y.toFixed(1)},${displayAngle.toFixed(4)},${spriteData.visible},${spriteData.layer},${spriteData.ySort},${s.toFixed(4)},${sy.toFixed(4)},${pivotX.toFixed(1)},${pivotY.toFixed(1)}`
      if (displayObj._lastPropsKey !== propsKey) {
        displayObj._lastPropsKey = propsKey
        displayObj.x = Math.round(spriteData.x)
        displayObj.y = Math.round(spriteData.y)
        displayObj.rotation = (spriteData.angle * Math.PI) / 180
        displayObj.scale.x = s
        displayObj.scale.y = sy
        displayObj.pivot.x = pivotX
        displayObj.pivot.y = pivotY
        displayObj.visible = spriteData.visible
        // 排序键：图层为主序（每层预留 10000 的偏移空间）；
        // 勾选「Y轴排序」的角色，同层内按脚底高度排——越靠下（游戏 y 越小）越靠前
        const ySortOffset = spriteData.ySort
          ? Math.max(-4000, Math.min(4000, Math.round(-spriteData.y)))
          : 0
        displayObj.zIndex = spriteData.layer * 10000 + ySortOffset
      }
    }
  }

  spriteContainer.sortChildren()
  spritesSyncing = false
}

async function syncTiles() {
  if (!app || !tileLayerContainer || tilesSyncing) return
  tilesSyncing = true
  // 记录本轮同步开始时的场景代次：等待贴图期间可能已开始新一轮运行（清场）
  const syncEpoch = renderStore.sceneEpoch

  const currentTileIds = new Set(renderStore.tiles.keys())

  for (const [id, displayObj] of tileDisplayObjects) {
    if (!currentTileIds.has(id)) {
      tileLayerContainer.removeChild(displayObj)
      displayObj.destroy()
      tileDisplayObjects.delete(id)
    }
  }

  const sortedTiles = Array.from(renderStore.tiles.values())
    .sort((a, b) => a.layer - b.layer)

  for (const tileData of sortedTiles) {
    let displayObj = tileDisplayObjects.get(tileData.id)

    if (!displayObj) {
      try {
        if (tileData.type === 'image' && tileData.imagePath) {
          const texture = await getTexture(tileData.imagePath)
          if (texture) {
            displayObj = new PIXI.Sprite(texture)
            displayObj.anchor = { x: 0, y: 0 }
          }
        } else if (tileData.type === 'tile' && tileData.tileSetIndex !== undefined && tileData.tileId !== undefined) {
          const texture = await getTileFrame(tileData.tileSetIndex, tileData.tileId)
          if (texture) {
            displayObj = new PIXI.Sprite(texture)
            // 图块锚点居中：引擎发送的是变换后的图块中心（缩放/旋转都以中心为基准）
            displayObj.anchor = { x: 0.5, y: 0.5 }
          }
        }
      } catch (e) {
        console.warn('[GameCanvas] tile create error:', e)
      }

      if (displayObj) {
        // 等待贴图期间场景已被清场（新一轮运行）：丢弃这个过期对象，避免撞号复用旧纹理
        if (syncEpoch !== renderStore.sceneEpoch) {
          displayObj.destroy()
          continue
        }
        tileLayerContainer.addChild(displayObj)
        tileDisplayObjects.set(tileData.id, displayObj)
      }
    }

    if (displayObj) {
      // auto 模式：瓦片按「内容尺寸」判定采样。瓦片贴图是图集子纹理，内容尺寸是图集
      // 格子尺寸（tileWidth/Height）而不是图集整图尺寸（16px 格的图集轻松超过 128px）；
      // 图像层用图片自然尺寸，SVG 恒平滑。判定结果按纹理源缓存一次（同一图集的全部
      // 瓦片共用一个 source，只判一次），之后每帧只是一次 WeakMap 查表。
      if (editorStore.renderMode === 'auto') {
        const source = displayObj.texture?.source
        if (source) {
          let mode = autoScaleModes.get(source)
          if (!mode) {
            if (tileData.type === 'tile') {
              const tileSet = tileData.tileSetIndex !== undefined
                ? renderStore.tileSets[tileData.tileSetIndex]
                : undefined
              mode = tileSet
                ? effectiveScaleMode('auto', tileSet.tileWidth, tileSet.tileHeight)
                : effectiveScaleMode('auto', displayObj.texture.width, displayObj.texture.height)
            } else {
              // SVG 矢量图按目标像素重绘，最近邻会把栅格化锯齿固化下来，恒平滑
              mode = tileData.imagePath?.toLowerCase().endsWith('.svg')
                ? 'linear'
                : effectiveScaleMode('auto', displayObj.texture.width, displayObj.texture.height)
            }
            autoScaleModes.set(source, mode)
          }
          if (source.scaleMode !== mode) source.scaleMode = mode
        }
      }
      // 脏检查：只在实际数据变化时更新属性
      // scale_x/scale_y 已含最终缩放，直接使用，不能再乘 scale（会平方）
      const tileScaleX = tileData.scaleX ?? tileData.scale ?? 1
      const tileScaleY = tileData.scaleY ?? tileData.scale ?? 1
      const propsKey = `${tileData.x},${tileData.y},${tileData.angle ?? 0},${tileScaleX},${tileScaleY},${tileData.opacity ?? 1},${tileData.layer}`
      if (displayObj._lastPropsKey !== propsKey) {
        displayObj._lastPropsKey = propsKey
        displayObj.x = tileData.x
        displayObj.y = tileData.y
        displayObj.rotation = ((tileData.angle ?? 0) * Math.PI) / 180
        displayObj.scale.x = tileScaleX
        displayObj.scale.y = tileScaleY
        displayObj.alpha = tileData.opacity ?? 1
        displayObj.zIndex = tileData.layer
      }
      // 视口裁剪：只渲染相机视口内的瓦片，减少 GPU 负担
      // 尺寸取精灵当前显示尺寸（已包含整层缩放），图块锚点在中心，裁剪框从中心向两侧展开
      const cellSize = tileData.type === 'tile'
        ? (tileData.tileSize || renderStore.tileGridSize)
        : (renderStore.tileGridSize || 16)
      const isImageTile = tileData.type === 'image'
      const cullW = displayObj.width || cellSize
      const cullH = displayObj.height || cellSize
      const halfW = isImageTile ? 0 : cullW / 2
      const halfH = isImageTile ? 0 : cullH / 2
      const cam = renderStore.camera
      const viewLeft = cam.x - LOGIC_W / 2 - cellSize
      const viewRight = cam.x + LOGIC_W / 2 + cellSize
      const viewTop = cam.y - LOGIC_H / 2 - cellSize
      const viewBottom = cam.y + LOGIC_H / 2 + cellSize
      displayObj.visible = tileData.x + halfW + cullW > viewLeft
        && tileData.x - halfW < viewRight
        && tileData.y + halfH + cullH > viewTop
        && tileData.y - halfH < viewBottom
    }
  }

  tileLayerContainer.sortChildren()
  tilesSyncing = false
}

// 气泡字号：舞台坐标系内随窗口等比缩小，小窗下屏幕上只剩几个像素看不清。
// 按显示比例放大字号，保证屏幕上约 14px 可读（下限=原字号，上限防爆）
function getSayFontSize(): number {
  const displayScale = stageContainer?.scale?.x || 1
  return Math.round(Math.min(34, Math.max(14, 14 / displayScale)))
}

function syncSayTexts() {
  if (!app || !uiContainer) return

  const fontSize = getSayFontSize()

  // 回收不再需要的气泡对象（隐藏而非销毁，供后续复用）
  for (const [id, container] of sayDisplayObjects) {
    if (!renderStore.sayTexts.has(id)) {
      container.visible = false
    }
  }

  for (const [id, sayData] of renderStore.sayTexts) {
    let container = sayDisplayObjects.get(id)
    if (!container) {
      // 优先复用被隐藏的气泡对象（注意删除旧 id 的映射）
      for (const [pooledId, pooled] of sayDisplayObjects) {
        if (!pooled.visible) {
          container = pooled
          sayDisplayObjects.delete(pooledId)
          container._sayStyleKey = ''
          break
        }
      }
      if (!container) {
        container = new PIXI.Container()
        const bg = new PIXI.Graphics()
        container.addChild(bg)
        const text = new PIXI.Text({
          text: '',
          style: { fill: 0x000000, fontSize: 14, fontFamily: 'Arial' },
        })
        // 锚点居中：文字垂直居中显示在气泡内（原先锚点在底部导致偏下）
        text.anchor = { x: 0.5, y: 0.5 }
        container.addChild(text)
        uiContainer.addChild(container)
      }
      sayDisplayObjects.set(id, container)
    }

    container.visible = true
    container.x = sayData.x
    // 气泡底边悬浮在角色上方，偏移随字号缩放（fontSize=14 时为 40，与原行为一致）
    container.y = sayData.y - (fontSize + 26)
    container.zIndex = 1

    const textObj = container.children[1]
    if (textObj && textObj.text !== undefined) {
      // 文本或字号变化（窗口缩放）时才重设样式与重绘背景
      const styleKey = `${sayData.text}|${fontSize}`
      if (container._sayStyleKey !== styleKey) {
        container._sayStyleKey = styleKey
        if (textObj.style) textObj.style.fontSize = fontSize
        textObj.text = sayData.text
        const bg = container.children[0]
        if (bg) {
          const padX = Math.round(fontSize * 0.5)
          const padY = Math.round(fontSize * 0.35)
          const w = textObj.width + padX * 2
          const h = textObj.height + padY * 2
          bg.clear()
          bg.roundRect(-w / 2, -h, w, h, Math.round(fontSize * 0.45))
          bg.fill({ color: 0xffffff, alpha: 0.9 })
          bg.stroke({ width: 1, color: 0x333333 })
          // 文字垂直居中于气泡
          textObj.x = 0
          textObj.y = -h / 2
        }
      }
    }
  }
}

function syncDrawTexts() {
  if (!app || !uiContainer) return

  const currentIds = new Set(renderStore.drawTexts.keys())

  for (const [id, obj] of drawTextDisplayObjects) {
    if (!currentIds.has(id)) {
      uiContainer.removeChild(obj)
      obj.destroy()
      drawTextDisplayObjects.delete(id)
    }
  }

  for (const [id, data] of renderStore.drawTexts) {
    let textObj = drawTextDisplayObjects.get(id)
    if (!textObj) {
      textObj = new PIXI.Text({
        text: data.text,
        style: { fill: 0xffffff, fontSize: 16, fontFamily: 'Arial', stroke: { color: 0x000000, width: 2 } },
      })
      textObj.zIndex = 2
      uiContainer.addChild(textObj)
      drawTextDisplayObjects.set(id, textObj)
    }
    // 脏检查：只在文本变化时设置
    if (textObj.text !== data.text) textObj.text = data.text
    textObj.x = data.x
    textObj.y = data.y
  }
}

function syncHitboxes() {
  if (!app || !uiContainer) return

  // 如果调试开关关闭，清除所有碰撞盒显示
  if (!renderStore.showCollision) {
    for (const [, obj] of hitboxDisplayObjects) {
      uiContainer.removeChild(obj)
      obj.destroy()
    }
    hitboxDisplayObjects.clear()
    return
  }

  const currentIds = new Set(renderStore.hitboxes.keys())

  for (const [id, obj] of hitboxDisplayObjects) {
    if (!currentIds.has(id)) {
      uiContainer.removeChild(obj)
      obj.destroy()
      hitboxDisplayObjects.delete(id)
    }
  }

  for (const [id, data] of renderStore.hitboxes) {
    let graphics = hitboxDisplayObjects.get(id)
    if (!graphics) {
      graphics = new PIXI.Graphics()
      graphics.zIndex = 0
      uiContainer.addChild(graphics)
      hitboxDisplayObjects.set(id, graphics)
      graphics._lastRect = null
    }
    // 脏检查：仅碰撞盒数据变化时重绘
    const rectStr = data.rect ? data.rect.join(',') : ''
    if (graphics._lastRect !== rectStr) {
      graphics.clear()
      if (data.rect) {
        const [left, top, right, bottom] = data.rect
        graphics.rect(left, top, right - left, bottom - top)
        graphics.stroke({ width: 1, color: 0x00ff00 })
      }
      graphics._lastRect = rectStr
    }
  }
}

/**
 * 销毁全部显示对象（清场专用）。
 * 停止运行不清场（画布保留最后一帧），所以下一次运行时上一轮的显示对象还在；
 * 引擎角色 id 是每进程从 1 递增，新角色可能与旧对象撞号，一旦复用就会沿用旧纹理。
 * 因此清场时必须整体销毁，让下一帧全部重建。
 */
function resetDisplayObjects() {
  const destroyAll = (objs: Map<string, any>, container: any) => {
    for (const obj of objs.values()) {
      if (container) container.removeChild(obj)
      obj.destroy()
    }
    objs.clear()
  }
  destroyAll(spriteDisplayObjects, spriteContainer)
  destroyAll(tileDisplayObjects, tileLayerContainer)
  destroyAll(sayDisplayObjects, uiContainer)
  destroyAll(drawTextDisplayObjects, uiContainer)
  destroyAll(hitboxDisplayObjects, uiContainer)
}

function gameLoop() {
  if (!app) return

  // 场景代次变化（新一轮运行 / 切换项目 / 应用启动）：
  // 必须在同步精灵和瓦片之前销毁残留对象，否则撞号的旧对象会被直接复用
  if (appliedSceneEpoch !== renderStore.sceneEpoch) {
    appliedSceneEpoch = renderStore.sceneEpoch
    resetDisplayObjects()
  }

  // 游戏未运行时跳过高开销的同步操作：sprites/tiles 不会变化，
  // PixiJS 会自动保留最后一帧画面。避免空转占满 CPU（低端机器尤其明显）。
  if (!editorStore.isRunning) {
    // 仍需收尾启动加载页（贴图加载完成时隐藏）
    renderStore.tryFinishStartup()
    return
  }

  // 更新帧耗时（仅在性能面板开启时计算，避免不必要的开销）
  if (renderStore.showStats) {
    updateFrameTime(app.ticker.deltaMS)
    updatePerfPanel()
  }

  const cam = renderStore.getInterpolatedCamera()
  const shake = renderStore.getShakeOffset()
  // 整数像素对齐：消除子像素渲染导致的模糊/撕裂
  gameContainer.x = Math.round(-cam.x + LOGIC_W / 2) + shake.x
  gameContainer.y = Math.round(-cam.y + LOGIC_H / 2) + shake.y

  syncSprites()
  syncTiles()
  syncSayTexts()
  syncDrawTexts()
  syncHitboxes()
  // 启动加载页收尾：引擎就绪 + 贴图全部就绪 + 本帧场景已同步，才撤掉覆盖层
  // （进度条本身由 MainLayout 自己的帧循环推进，不依赖画布 ticker 是否在跑）
  renderStore.tryFinishStartup()
}

function onKeyDown(e: KeyboardEvent) {
  if (editorStore.isRunning && usesEngine()) {
    e.stopPropagation()
    const key = mapKey(e.key)
    engine.sendKey(key, true)
  }
}

function onKeyUp(e: KeyboardEvent) {
  if (editorStore.isRunning && usesEngine()) {
    e.stopPropagation()
    const key = mapKey(e.key)
    engine.sendKey(key, false)
  }
}

let usesEngineCache = { valid: false, value: false }

function invalidateUsesEngineCache() {
  usesEngineCache.valid = false
}

function usesEngine(): boolean {
  if (usesEngineCache.valid) return usesEngineCache.value
  const gameKeywords = ['run()', 'Sprite(', 'load_map(', 'key_down(', 'key_pressed(', 'key_up(', 'Timer(', 'mouse', 'time_passed(']
  // 游戏模式下检查所有 tabs，不只是当前 tab
  // 用户可能切换了 tab，但游戏引擎仍在运行
  const tabs = editorStore.isGameMode ? editorStore.currentTabs : [editorStore.currentTab]
  for (const tab of tabs) {
    const code = tab?.content || ''
    if (code.includes('bingo_engine') || gameKeywords.some(kw => code.includes(kw))) {
      usesEngineCache.value = true
      usesEngineCache.valid = true
      return true
    }
  }
  usesEngineCache.value = false
  usesEngineCache.valid = true
  return false
}

let pendingMouseMove: MouseEvent | null = null
let rafId: number | null = null

function onCanvasMouseMove(e: MouseEvent) {
  if (!app || !containerRef.value || !editorStore.isRunning || !usesEngine()) return
  pendingMouseMove = e
  if (rafId === null) {
    rafId = requestAnimationFrame(() => {
      rafId = null
      const evt = pendingMouseMove
      pendingMouseMove = null
      if (!evt || !containerRef.value) return
      const rect = containerRef.value.getBoundingClientRect()
      const scaleX = rect.width / LOGIC_W
      const scaleY = rect.height / LOGIC_H
      const scale = Math.min(scaleX, scaleY)
      const offsetX = (rect.width - LOGIC_W * scale) / 2
      const offsetY = (rect.height - LOGIC_H * scale) / 2
      const x = (evt.clientX - rect.left - offsetX) / scale
      const y = (evt.clientY - rect.top - offsetY) / scale
      engine.sendMouseMove(x, y)
    })
  }
}

function onCanvasMouseDown(e: MouseEvent) {
  containerRef.value?.focus()
  if (editorStore.isRunning && usesEngine()) {
    e.stopPropagation()
    engine.sendMouseDown()
  }
}

function onCanvasMouseUp(e: MouseEvent) {
  if (editorStore.isRunning && usesEngine()) {
    e.stopPropagation()
    engine.sendMouseUp()
  }
}

function mapKey(key: string): string {
  const map: Record<string, string> = {
    ArrowUp: 'up',
    ArrowDown: 'down',
    ArrowLeft: 'left',
    ArrowRight: 'right',
    ' ': 'space',
    Enter: 'enter',
    Escape: 'escape',
    Shift: 'shift',
    Control: 'ctrl',
  }
  return map[key] ?? key.toLowerCase()
}

function addGameListeners() {
  const el = containerRef.value
  if (!el) return
  el.addEventListener('keydown', onKeyDown)
  el.addEventListener('keyup', onKeyUp)
  el.addEventListener('mousemove', onCanvasMouseMove)
  el.addEventListener('mousedown', onCanvasMouseDown)
  el.addEventListener('mouseup', onCanvasMouseUp)
  el.focus()
}

function removeGameListeners() {
  const el = containerRef.value
  if (!el) return
  el.removeEventListener('keydown', onKeyDown)
  el.removeEventListener('keyup', onKeyUp)
  el.removeEventListener('mousemove', onCanvasMouseMove)
  el.removeEventListener('mousedown', onCanvasMouseDown)
  el.removeEventListener('mouseup', onCanvasMouseUp)
}

watch(
  () => editorStore.isRunning,
  (running) => {
    if (running) {
      nextTick(() => {
        // 运行时再校准一次尺寸：画布可能是在启动加载屏（隐藏）期间初始化的，
        // 这里补上尺寸和缩放，画面立即正常，不需要切模式重新挂载
        handleResize()
        addGameListeners()
      })
    } else {
      removeGameListeners()
    }
  }
)

watch(
  () => editorStore.renderMode,
  () => {
    if (app && PIXI) {
      applyRenderMode()
      // 重新渲染所有精灵和瓦片
      syncSprites()
      syncTiles()
    }
  }
)

// 监听标签切换、模式切换、tabs 变化，使 usesEngine 缓存失效
watch(
  () => [editorStore.currentTab?.content, editorStore.currentTab?.id, editorStore.isGameMode, editorStore.currentTabs.length],
  () => invalidateUsesEngineCache()
)

onMounted(async () => {
  try {
    await initPixi()
    if (app) {
      app.ticker.add(gameLoop)
      // 性能模式把画面刷新压到 30 帧（0 = 不限制）。
      // 只影响显示频率，引擎逻辑仍按 60Hz 步进，游戏速度不变。
      app.ticker.maxFPS = settingsStore.perfMode ? 30 : 0
      // ticker 只在「画布可见 + 游戏运行中」时启动：
      // 不可见或未运行时停止，避免 PixiJS 空转占满 CPU（低端机器尤其明显）。
      // 停止后 canvas 保留最后一帧画面，视觉上无变化。
      if (!(props.active !== false && editorStore.isRunning)) {
        app.ticker.stop()
      }
    }
    if (editorStore.isRunning) {
      nextTick(addGameListeners)
    }
  } catch (e) {
    console.error('[GameCanvas] PixiJS 初始化失败:', e)
  } finally {
    signalGameCanvasReady()
  }
})

// 画布可见性或游戏运行状态变化时启停 ticker
// 运行条件：画布可见（active !== false）且游戏正在运行
const shouldRunTicker = () => props.active !== false && editorStore.isRunning

watch(
  () => [props.active, editorStore.isRunning],
  () => {
    if (!app) return
    if (shouldRunTicker()) {
      app.ticker.start()
    } else {
      app.ticker.stop()
    }
  }
)

// 未运行时的清场（新建 / 打开项目）：此时 ticker 已停止，gameLoop 不会处理场景代次，
// 画布会一直保留上一个项目的最后一帧。这里主动销毁残留显示对象并重绘一帧。
watch(
  () => renderStore.sceneEpoch,
  () => {
    if (editorStore.isRunning || !app) return
    appliedSceneEpoch = renderStore.sceneEpoch
    resetDisplayObjects()
    app.renderer.render(app.stage)
  }
)

// 性能模式开关即时生效：渲染帧率随之切换（抗锯齿只能在下次挂载时调整）
watch(
  () => settingsStore.perfMode,
  (on) => {
    if (!app) return
    app.ticker.maxFPS = on ? 30 : 0
  }
)

// 性能面板开关：只在面板打开时轮询进程树资源（避免常驻后台采样）
// 模块级单例保证两个 GameCanvas 实例只发起一份轮询
watch(
  () => renderStore.showStats,
  (on) => {
    if (on) startProcessStatsPolling()
    else stopProcessStatsPolling()
  }
)

onBeforeUnmount(() => {
  removeGameListeners()
  resizeObserver?.disconnect()
  resetGameCanvasReady()

  if (app) {
    app.ticker.remove(gameLoop)
    // 用 false 而非 true：app.destroy(true) 会递归销毁舞台上所有 sprite 的纹理及其 source，
    // 而两个 GameCanvas 实例（预览窗 + 全屏 v-show 窗）共享 gameTextures.ts 中的纹理缓存，
    // 一旦此处销毁 source，另一个仍在运行的实例持有的同源纹理就变成了「缺失纹理」，
    // WebGL 会渲染出粉紫色方块（0xFF00FF）。
    // renderer.destroy(false) 只释放本渲染器的 GPU 资源，source 对象本身保留，
    // 新实例挂载时由新渲染器按需重新上传，零闪烁。
    app.destroy(false)
    app = null
  }

  // 不清空共享纹理缓存：缓存由 useEngine.run() 里的 invalidateGameTextures() 在每次运行开始时统一清空，
  // 此处清空会导致预览窗从角色编辑器切回代码页时重新走 IPC 加载全部贴图，
  // 一瞬间画面里的角色变成粉紫色占位块。保留缓存可让最后一帧瞬间恢复。
  // 只清空本实例的显示对象映射（显示对象已随 stage 销毁/脱离）。
  spriteDisplayObjects.clear()
  tileDisplayObjects.clear()
  sayDisplayObjects.clear()
  drawTextDisplayObjects.clear()
  hitboxDisplayObjects.clear()
})

// ─── 性能面板 ───
// 只保留能指导优化的信号：画面是否流畅、卡在逻辑还是渲染、真正提交给 GPU 的对象数、
// 纹理显存与整机占用。角色 id / 坐标、相机位置这类「看着专业但没法指导改动」的数值不显示。
const frameTime = ref(0)  // 显示用的平均帧耗时
let frameTimeAccum = 0    // 累计帧耗时
let frameTimeCount = 0    // 累计帧数

// 最近 120 帧耗时（ms）：用于平均帧率、1% Low、最慢帧和帧耗时曲线
const FRAME_HISTORY = 120
const frameHistory: number[] = []
const fpsAvg = ref(0)
const fpsLow1 = ref(0)
const framePeak = ref(0)
/**
 * 判定基准帧率：不写死 60，避免把「本来就该是 30/50」的情况误判成卡。
 * - 性能模式主动锁 30 帧 → 以 30 为基准
 * - 老笔记本/外接屏是 50Hz → 最快也只有 50 帧，以 50 为基准
 * - 其余按 60
 */
const targetFps = ref(60)
const targetFrameMs = computed(() => 1000 / targetFps.value)
const frameGraphRef = ref<HTMLCanvasElement | null>(null)
let frameGraphDrawnAt = 0

// 纹理显存 / 绘制对象数：低频采样（遍历缓存和显示对象不能每帧做）
const vramMB = ref(0)
const textureCount = ref(0)
const drawnSprites = ref(0)
const drawnTiles = ref(0)
let statsSampledAt = 0

/** 采样纹理显存估算（width × height × 4 字节，RGBA8）与实际参与绘制的对象数 */
function sampleScene() {
  let bytes = 0
  let count = 0
  // 只统计基础纹理：tileset 分帧与 .bsf UV 帧都是这些 BaseTexture 的子纹理，
  // 重复计入会把显存估算翻好几倍
  for (const tex of textureCache.values()) {
    if (!tex) continue
    bytes += (tex.width || 0) * (tex.height || 0) * 4
    count++
  }
  vramMB.value = bytes / 1048576
  textureCount.value = count

  // 视口外的瓦片已被裁剪（visible=false），不会提交给 GPU；
  // 「绘制」才是真实的渲染负载，总数只说明地图有多大
  let sprites = 0
  for (const obj of spriteDisplayObjects.values()) if (obj.visible) sprites++
  let tiles = 0
  for (const obj of tileDisplayObjects.values()) if (obj.visible) tiles++
  drawnSprites.value = sprites
  drawnTiles.value = tiles
}

function updateFrameTime(dt: number) {
  frameTimeAccum += dt
  frameTimeCount++
  frameHistory.push(dt)
  if (frameHistory.length > FRAME_HISTORY) frameHistory.shift()

  if (frameTimeCount >= 30) {
    frameTime.value = Math.round(frameTimeAccum / frameTimeCount * 100) / 100
    frameTimeAccum = 0
    frameTimeCount = 0

    const sum = frameHistory.reduce((a, b) => a + b, 0)
    fpsAvg.value = sum > 0 ? Math.round(frameHistory.length / (sum / 1000)) : 0
    const sorted = [...frameHistory].sort((a, b) => a - b)
    // 1% Low：最慢的 1% 帧对应的瞬时帧率，比平均帧率更能暴露卡顿
    const worst = sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * 0.99))] || 0
    fpsLow1.value = worst > 0 ? Math.round(1000 / worst) : 0
    framePeak.value = Math.round((sorted[sorted.length - 1] || 0) * 10) / 10
    // 基准帧率：性能模式 30；屏幕最快只能到 ~50 帧（50Hz 屏/老显卡）时按 50，其余按 60。
    // 用「最顺的那批帧」（约最快 5%）估算，屏幕刷新率是硬上限，最顺的帧最接近它
    const fastest = sorted[Math.floor(sorted.length * 0.05)] || 16.7
    const fastestFps = 1000 / fastest
    targetFps.value = settingsStore.perfMode ? 30 : (fastestFps <= 54 ? 50 : 60)
  }
}

/** 绘制帧耗时曲线（纵轴按基准帧耗时自适应，绿/黄/红 = 达标/偏高/明显掉帧） */
function drawFrameGraph() {
  const el = frameGraphRef.value
  if (!el) return
  const now = performance.now()
  if (now - frameGraphDrawnAt < 100) return
  frameGraphDrawnAt = now

  const ctx = el.getContext('2d')
  if (!ctx) return
  const w = el.width
  const h = el.height
  ctx.clearRect(0, 0, w, h)

  const refMs = targetFrameMs.value
  const scaleMax = Math.max(50, refMs * 1.8)
  // 基准帧耗时参考线（60fps 时是 16.7ms，性能模式下是 33.3ms）
  const refY = h - (Math.min(refMs, scaleMax) / scaleMax) * h
  ctx.strokeStyle = 'rgba(80, 255, 120, 0.18)'
  ctx.beginPath()
  ctx.moveTo(0, refY)
  ctx.lineTo(w, refY)
  ctx.stroke()

  const barW = w / FRAME_HISTORY
  for (let i = 0; i < frameHistory.length; i++) {
    const ms = frameHistory[i]
    const barH = Math.max(1, Math.min(ms / scaleMax, 1) * h)
    ctx.fillStyle = ms <= refMs * 1.2 ? '#50ff78' : ms <= refMs * 1.8 ? '#f0c040' : '#ff5050'
    ctx.fillRect(i * barW, h - barH, Math.max(1, barW - 0.4), barH)
  }
}

/** 性能面板的低频刷新（曲线 10Hz、显存与对象数 2Hz） */
function updatePerfPanel() {
  drawFrameGraph()
  const now = performance.now()
  if (now - statsSampledAt >= 500) {
    statsSampledAt = now
    sampleScene()
  }
}

/** 进程树资源（主进程 + WebView2 + Python 引擎）：只汇总合计，分组明细对优化没有帮助 */
const procView = computed(() => {
  const s = processStats.value
  if (!s) return null
  return {
    totalMemMB: s.total_memory / 1048576,
    totalCpu: s.total_cpu,
  }
})

const statsInfo = computed(() => ({
  spriteCount: renderStore.sprites.size,
  tileCount: renderStore.tiles.size,
}))

const fpsClass = computed(() => {
  if (fpsAvg.value >= targetFps.value * 0.92) return 'text-green'
  if (fpsAvg.value >= targetFps.value * 0.6) return 'text-yellow'
  return 'text-red'
})

const fpsLowClass = computed(() => {
  if (fpsLow1.value >= targetFps.value * 0.7) return 'text-green'
  if (fpsLow1.value >= targetFps.value * 0.5) return 'text-yellow'
  return 'text-red'
})

const frameTimeClass = computed(() => {
  if (frameTime.value <= targetFrameMs.value * 1.2) return 'text-green'
  if (frameTime.value <= targetFrameMs.value * 1.8) return 'text-yellow'
  return 'text-red'
})

/** 画面流畅度：以这台机器/屏幕能达到的帧率为基准；低于 30 帧在任何机器上都是卡 */
const perfStatus = computed(() => {
  if (fpsAvg.value <= 0) return null
  const target = targetFps.value
  if (fpsAvg.value < 30) return { label: '卡顿', cls: 'text-red' }
  if (fpsAvg.value >= target * 0.92 && fpsLow1.value >= target * 0.7) return { label: '流畅', cls: 'text-green' }
  return { label: '一般', cls: 'text-yellow' }
})

/**
 * 瓶颈判断：游戏开发的排查顺序是「先看逻辑有没有超一帧预算，再看渲染」。
 * 引擎一帧逻辑超过 16.7ms 就赶不上 60Hz，角色会一顿一顿；
 * 逻辑没问题而画面帧耗时超过 20ms，说明是渲染（对象太多 / 贴图太大）撑不住。
 */
const bottleneck = computed(() => {
  if (!renderStore.enginePerf && frameTime.value <= 0) return { label: '—', cls: '' }
  const logic = renderStore.enginePerf?.avgMs ?? 0
  if (logic >= 16.7) return { label: '逻辑', cls: 'text-red' }
  if (logic >= 10) return { label: '逻辑偏重', cls: 'text-yellow' }
  if (frameTime.value >= 20) return { label: '渲染', cls: 'text-yellow' }
  return { label: '无', cls: 'text-green' }
})
</script>

<template>
  <div ref="containerRef" class="game-canvas-container" tabindex="-1">
    <!-- FPS 叠加层 -->
    <div
      v-if="renderStore.showFps && renderStore.fps > 0"
      class="fps-overlay"
      :style="{ top: stageOffsetY + 8 + 'px', left: stageOffsetX + 8 + 'px' }"
    >
      FPS: {{ renderStore.fps }}
    </div>
    <!-- 性能面板 -->
    <div v-if="renderStore.showStats" class="stats-panel" :style="{ top: stageOffsetY + 8 + 'px', right: stageOffsetX + 8 + 'px' }">
      <div class="stats-header">
        <span>PERFORMANCE</span>
        <span v-if="perfStatus" class="stats-badge" :class="perfStatus.cls">{{ perfStatus.label }}</span>
      </div>
      <div class="stats-section">
        <div class="stats-row">
          <span class="stats-label">FPS</span>
          <span class="stats-value" :class="fpsClass">
            {{ fpsAvg }}
            <span class="stats-sub">目标 {{ targetFps }}</span>
          </span>
        </div>
        <div class="stats-row">
          <span class="stats-label">1% Low</span>
          <span class="stats-value" :class="fpsLowClass">
            {{ fpsLow1 }}
          </span>
        </div>
        <div class="stats-row">
          <span class="stats-label">帧耗时</span>
          <span class="stats-value" :class="frameTimeClass">
            {{ frameTime }} ms
            <span class="stats-sub">最慢 {{ framePeak }}ms</span>
          </span>
        </div>
        <canvas ref="frameGraphRef" class="stats-graph" width="240" height="40"></canvas>
      </div>
      <div class="stats-divider"></div>
      <div class="stats-section">
        <div class="stats-subheader">耗时</div>
        <div class="stats-row">
          <span class="stats-label">逻辑（引擎）</span>
          <span class="stats-value"
                :class="!renderStore.enginePerf ? '' : renderStore.enginePerf.avgMs <= 8 ? 'text-green' : renderStore.enginePerf.avgMs <= 16.7 ? 'text-yellow' : 'text-red'">
            {{ renderStore.enginePerf ? renderStore.enginePerf.avgMs.toFixed(2) + ' ms' : '—' }}
            <span class="stats-sub">峰值 {{ renderStore.enginePerf ? renderStore.enginePerf.maxMs.toFixed(1) + 'ms' : '—' }}</span>
          </span>
        </div>
        <div class="stats-row">
          <span class="stats-label">瓶颈</span>
          <span class="stats-value" :class="bottleneck.cls">{{ bottleneck.label }}</span>
        </div>
      </div>
      <div class="stats-divider"></div>
      <div class="stats-section">
        <div class="stats-subheader">场景</div>
        <div class="stats-row">
          <span class="stats-label">角色</span>
          <span class="stats-value">{{ statsInfo.spriteCount }} <span class="stats-sub">绘制 {{ drawnSprites }}</span></span>
        </div>
        <div class="stats-row">
          <span class="stats-label">瓦片</span>
          <span class="stats-value">{{ statsInfo.tileCount }} <span class="stats-sub">绘制 {{ drawnTiles }}</span></span>
        </div>
        <div class="stats-row">
          <span class="stats-label">纹理显存</span>
          <span class="stats-value">{{ vramMB.toFixed(1) }} MB <span class="stats-sub">{{ textureCount }} 张</span></span>
        </div>
      </div>
      <div class="stats-divider"></div>
      <div class="stats-section">
        <div class="stats-subheader">系统</div>
        <template v-if="procView">
          <div class="stats-row">
            <span class="stats-label">内存</span>
            <span class="stats-value">{{ procView.totalMemMB.toFixed(0) }} MB</span>
          </div>
          <div class="stats-row">
            <span class="stats-label">CPU</span>
            <span class="stats-value" :class="procView.totalCpu <= 40 ? 'text-green' : procView.totalCpu <= 70 ? 'text-yellow' : 'text-red'">
              {{ procView.totalCpu.toFixed(0) }}%
            </span>
          </div>
        </template>
        <div v-else class="stats-row">
          <span class="stats-label">系统采样中…</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.game-canvas-container {
  position: relative;
  width: 100%;
  height: 100%;
  background: rgb(26, 28, 33);
  outline: none;
}
.fps-overlay {
  position: absolute;
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  color: #50ff78;
  z-index: 10;
  user-select: none;
  text-shadow: 0 0 2px rgba(0, 0, 0, 0.6);
}
.stats-panel {
  position: absolute;
  background: rgba(10, 10, 14, 0.88);
  border: 1px solid rgba(80, 255, 120, 0.2);
  border-radius: 4px;
  padding: 8px 10px;
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
  font-size: 11px;
  color: #b0b8c4;
  min-width: 180px;
  max-width: 280px;
  max-height: 70%;
  overflow-y: auto;
  z-index: 20;
  user-select: none;
}
.stats-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 10px;
  font-weight: 700;
  color: #50ff78;
  letter-spacing: 1.5px;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(80, 255, 120, 0.15);
}
.stats-badge {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0;
  line-height: 13px;
  padding: 0 5px;
  border: 1px solid currentColor;
  border-radius: 3px;
}
.stats-section {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.stats-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1px 0;
  line-height: 1.5;
}
.stats-label {
  color: #7a8290;
}
.stats-value {
  color: #d0d6e0;
  font-variant-numeric: tabular-nums;
}
.text-green { color: #50ff78; }
.text-yellow { color: #f0c040; }
.text-red { color: #ff5050; }
.stats-divider {
  height: 1px;
  background: rgba(80, 255, 120, 0.1);
  margin: 5px 0;
}
.stats-subheader {
  font-size: 10px;
  font-weight: 600;
  color: #7a8290;
  letter-spacing: 0.5px;
  margin-bottom: 2px;
}
.stats-sub {
  color: #5a6270;
  font-size: 10px;
}
.stats-graph {
  display: block;
  width: 100%;
  height: 40px;
  margin: 3px 0;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 2px;
}
</style>
