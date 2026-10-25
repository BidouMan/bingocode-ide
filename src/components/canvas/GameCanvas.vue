<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { useRenderStore } from '../../stores/render'
import { useEditorStore } from '../../stores/editor'
import { useEngine } from '../../composables/useEngine'
import { signalGameCanvasReady, resetGameCanvasReady } from '../../utils/gameCanvasReady'
import { effectiveScaleMode } from '../../utils/renderMode'
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

const renderStore = useRenderStore()
const editorStore = useEditorStore()
const engine = useEngine()

const containerRef = ref<HTMLDivElement>()

const emit = defineEmits<{
  'offset-update': [offset: number]
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
    antialias: true,
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
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
    if (vp.clientWidth === 0 || vp.clientHeight === 0) return
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
  emit('offset-update', stageContainer.x)
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
  // 已放置的瓦片/图像图层：直接改纹理源的采样方式，不重建对象
  // （重建要重新加载全部贴图，会闪烁且更耗性能）。auto 模式下 currentScaleMode 是 linear，
  // 与新建瓦片一致，所以这里不需要额外处理
  for (const obj of tileDisplayObjects.values()) {
    const source = obj.texture?.source
    if (source && source.scaleMode !== currentScaleMode) source.scaleMode = currentScaleMode
  }
}

/**
 * 自动渲染模式：按素材自然尺寸给纹理源定采样方式（小图最近邻、大插画平滑）。
 * 每个纹理源只判定一次，之后每帧只是一次 WeakMap 查表，无逐帧计算。
 */
function applyAutoScaleMode(
  texture: any,
  spriteData: { frameW?: number; frameH?: number; imagePath?: string }
) {
  const source = texture?.source
  if (!source || editorStore.renderMode !== 'auto') return
  // 尺寸未知（引擎暂未下发 cw/ch）时不判定，等下一帧有了再说
  if (!spriteData.frameW || !spriteData.frameH) return
  const cached = autoScaleModes.get(source)
  if (cached) return
  // 矢量素材（SVG）恒平滑：它按目标像素重绘，最近邻会把栅格化锯齿固化下来
  const isVector = !!spriteData.imagePath?.toLowerCase().endsWith('.svg')
  const mode = isVector
    ? 'linear'
    : effectiveScaleMode('auto', spriteData.frameW, spriteData.frameH)
  autoScaleModes.set(source, mode)
  if (source.scaleMode !== mode) source.scaleMode = mode
}

function getTexture(imagePath: string): Promise<any> {
  if (textureCache.has(imagePath)) {
    return Promise.resolve(textureCache.get(imagePath))
  }
  // 同帧/并发对同一路径的请求合并为一次加载、一次计数
  const pending = sharedInFlightTextures.get(imagePath)
  if (pending) return pending

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
      const propsKey = `${spriteData.x.toFixed(1)},${spriteData.y.toFixed(1)},${displayAngle.toFixed(4)},${spriteData.visible},${spriteData.layer},${s.toFixed(4)},${sy.toFixed(4)},${pivotX.toFixed(1)},${pivotY.toFixed(1)}`
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
        displayObj.zIndex = spriteData.layer
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
            displayObj.anchor = { x: 0, y: 0 }
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
      // 图块按格子大小判定；图像按贴图实际尺寸判定（大背景图左上角可能在视口外，但仍覆盖视口）
      const cellSize = tileData.tileSize || renderStore.tileGridSize
      const isImageTile = tileData.type === 'image'
      const cullW = isImageTile ? (displayObj.width || 1) : cellSize
      const cullH = isImageTile ? (displayObj.height || 1) : cellSize
      const cam = renderStore.camera
      const viewLeft = cam.x - LOGIC_W / 2 - cellSize
      const viewRight = cam.x + LOGIC_W / 2 + cellSize
      const viewTop = cam.y - LOGIC_H / 2 - cellSize
      const viewBottom = cam.y + LOGIC_H / 2 + cellSize
      displayObj.visible = tileData.x + cullW > viewLeft
        && tileData.x < viewRight
        && tileData.y + cullH > viewTop
        && tileData.y < viewBottom
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

  // 更新帧耗时（仅在性能面板开启时计算，避免不必要的开销）
  if (renderStore.showStats) {
    updateFrameTime(app.ticker.deltaMS)
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
      nextTick(addGameListeners)
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

onBeforeUnmount(() => {
  removeGameListeners()
  resizeObserver?.disconnect()
  resetGameCanvasReady()

  if (app) {
    app.ticker.remove(gameLoop)
    app.destroy(true)
    app = null
  }

  textureCache.clear()
  tilesetFrameCache.clear()
  frameTextureCache.clear()
  spriteDisplayObjects.clear()
  tileDisplayObjects.clear()
  sayDisplayObjects.clear()
  drawTextDisplayObjects.clear()
  hitboxDisplayObjects.clear()
})

// ─── 性能面板 ───
const statsCollapsed = ref<Record<string, boolean>>({})
const frameTime = ref(0)  // 显示用的平均帧耗时
let frameTimeAccum = 0    // 累计帧耗时
let frameTimeCount = 0    // 累计帧数

function updateFrameTime(dt: number) {
  frameTimeAccum += dt
  frameTimeCount++
  if (frameTimeCount >= 30) {
    frameTime.value = Math.round(frameTimeAccum / frameTimeCount * 100) / 100
    frameTimeAccum = 0
    frameTimeCount = 0
  }
}

/** 从图片路径提取精灵名称 */
function extractSpriteName(imagePath: string): string {
  if (!imagePath) return '(无图像)'
  // 匹配 assets/sprites/XXX/ 或 assets/sprites/XXX.
  const match = imagePath.match(/sprites[\\/]([^\\/]+)(?:[\\/]|\.)/)
  if (match) return match[1]
  // 兜底：取文件名（去扩展名）
  const parts = imagePath.replace(/\\/g, '/').split('/')
  const file = parts[parts.length - 1] || '(无图像)'
  return file.replace(/\.[^.]+$/, '') || '(无图像)'
}

const spriteGroups = computed(() => {
  const groups = new Map<string, { count: number; ids: string[] }>()
  for (const [id, sprite] of renderStore.sprites) {
    const name = extractSpriteName(sprite.imagePath)
    const existing = groups.get(name)
    if (existing) {
      existing.count++
      existing.ids.push(id)
    } else {
      groups.set(name, { count: 1, ids: [id] })
    }
  }
  return Array.from(groups.entries()).sort((a, b) => b[1].count - a[1].count)
})

const statsInfo = computed(() => {
  const sprites = renderStore.sprites
  const tiles = renderStore.tiles
  return {
    fps: renderStore.fps,
    spriteCount: sprites.size,
    tileCount: tiles.size,
    hitboxCount: renderStore.hitboxes.size,
    cameraX: Math.round(renderStore.camera.x),
    cameraY: Math.round(renderStore.camera.y),
  }
})

function toggleGroup(name: string) {
  statsCollapsed.value[name] = !statsCollapsed.value[name]
}

function getGroupSprites(name: string) {
  const result: { id: string; x: number; y: number }[] = []
  for (const [id, sprite] of renderStore.sprites) {
    if (extractSpriteName(sprite.imagePath) === name) {
      result.push({ id, x: sprite.x, y: sprite.y })
    }
  }
  return result
}
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
      <div class="stats-header">PERFORMANCE</div>
      <div class="stats-section">
        <div class="stats-row">
          <span class="stats-label">FPS</span>
          <span class="stats-value" :class="statsInfo.fps >= 55 ? 'text-green' : statsInfo.fps >= 30 ? 'text-yellow' : 'text-red'">
            {{ statsInfo.fps || 0 }}
          </span>
        </div>
        <div class="stats-row">
          <span class="stats-label">帧耗时</span>
          <span class="stats-value" :class="frameTime <= 20 ? 'text-green' : frameTime <= 33 ? 'text-yellow' : 'text-red'">
            {{ frameTime }} ms
          </span>
        </div>
        <div class="stats-row">
          <span class="stats-label">Camera</span>
          <span class="stats-value">{{ statsInfo.cameraX }}, {{ statsInfo.cameraY }}</span>
        </div>
      </div>
      <div class="stats-divider"></div>
      <div class="stats-section">
        <div class="stats-row">
          <span class="stats-label">Sprites</span>
          <span class="stats-value">{{ statsInfo.spriteCount }}</span>
        </div>
        <div class="stats-row">
          <span class="stats-label">Tiles</span>
          <span class="stats-value">{{ statsInfo.tileCount }}</span>
        </div>
        <div class="stats-row">
          <span class="stats-label">Hitboxes</span>
          <span class="stats-value">{{ statsInfo.hitboxCount }}</span>
        </div>
      </div>
      <!-- 精灵分组列表 -->
      <template v-if="spriteGroups.length > 0">
        <div class="stats-divider"></div>
        <div class="stats-section">
          <div class="stats-subheader">Sprite List</div>
          <div v-for="([name, group], idx) in spriteGroups" :key="idx">
            <div class="stats-row stats-clickable" @click="toggleGroup(name)">
              <span class="stats-label stats-group-label">
                <span class="stats-arrow" :class="{ 'stats-arrow-open': !statsCollapsed[name] }">&#9656;</span>
                {{ name }}
              </span>
              <span class="stats-value">x{{ group.count }}</span>
            </div>
            <div v-if="!statsCollapsed[name] && group.count <= 20" class="stats-children">
              <div v-for="sprite in getGroupSprites(name)" :key="sprite.id" class="stats-row stats-child">
                <span class="stats-label">#{{ sprite.id.slice(0, 8) }}</span>
                <span class="stats-value">({{ Math.round(sprite.x) }}, {{ Math.round(sprite.y) }})</span>
              </div>
            </div>
            <div v-if="!statsCollapsed[name] && group.count > 20" class="stats-children">
              <div class="stats-row stats-child">
                <span class="stats-label">...共 {{ group.count }} 个，已折叠</span>
              </div>
            </div>
          </div>
        </div>
      </template>
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
  font-size: 10px;
  font-weight: 700;
  color: #50ff78;
  letter-spacing: 1.5px;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(80, 255, 120, 0.15);
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
.stats-value.text-green { color: #50ff78; }
.stats-value.text-yellow { color: #f0c040; }
.stats-value.text-red { color: #ff5050; }
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
.stats-clickable {
  cursor: pointer;
}
.stats-clickable:hover {
  background: rgba(80, 255, 120, 0.06);
  border-radius: 2px;
}
.stats-group-label {
  display: flex;
  align-items: center;
  gap: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 180px;
}
.stats-arrow {
  font-size: 9px;
  transition: transform 0.15s;
  flex-shrink: 0;
}
.stats-arrow-open {
  transform: rotate(90deg);
}
.stats-children {
  padding-left: 16px;
}
.stats-child {
  font-size: 10px;
  color: #5a6270;
}
</style>
