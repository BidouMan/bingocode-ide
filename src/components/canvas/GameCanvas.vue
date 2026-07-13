<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { convertFileSrc } from '@tauri-apps/api/core'
import { useRenderStore } from '../../stores/render'
import { useEditorStore } from '../../stores/editor'
import { useEngine } from '../../composables/useEngine'
import { signalGameCanvasReady, resetGameCanvasReady } from '../../utils/gameCanvasReady'

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
let textureCache: Map<string, any> = new Map()
let tilesetFrameCache: Map<string, Map<number, any>> = new Map()
let gameContainer: any = null
let tileLayerContainer: any = null
let spriteContainer: any = null
let uiContainer: any = null
let stageContainer: any = null
let currentScaleMode: 'nearest' | 'linear' = 'linear'
let resizeObserver: ResizeObserver | null = null
let tilesSyncing = false
let spritesSyncing = false

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
    app.renderer.resize(vp.clientWidth, vp.clientHeight)
    fitStage()
    app.renderer.render(app.stage)
  })
}

function fitStage() {
  if (!app || !containerRef.value) return
  const vp = containerRef.value
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
}

async function getTexture(imagePath: string): Promise<any> {
  if (textureCache.has(imagePath)) {
    return textureCache.get(imagePath)
  }

  // 增加总数计数
  renderStore.setTextureTotal(renderStore.textureTotal + 1)

  try {
    const isLocal = imagePath.startsWith('/') || imagePath.match(/^[A-Z]:\\/i)
    const url = isLocal ? convertFileSrc(imagePath) : imagePath
    // 手动加载图片，绕过 PixiJS Assets 全局缓存，
    // 确保每次清缓存后能用新的 scaleMode 重建纹理
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const el = new Image()
      el.crossOrigin = 'anonymous'
      el.onload = () => resolve(el)
      el.onerror = reject
      el.src = url
    })
    // 手动创建 BaseTexture，绕过 PixiJS Texture.from 的内部 URL 缓存，
    // 确保 scaleMode 在 GPU 上传前就设置好
    const source = new PIXI.BufferImageSource({
      resource: img,
      scaleMode: currentScaleMode,
    })
    const texture = new PIXI.Texture(source)
    textureCache.set(imagePath, texture)
    // 增加已加载计数
    renderStore.incrementTextureLoaded()
    return texture
  } catch (e) {
    const g = new PIXI.Graphics()
    g.rect(0, 0, 32, 32)
    g.fill({ color: 0xff00ff })
    const placeholder = app.renderer.generateTexture(g)
    textureCache.set(imagePath, placeholder)
    // 增加已加载计数（失败也算加载完成）
    renderStore.incrementTextureLoaded()
    return placeholder
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

      // 异步加载真实纹理后替换
      if (spriteData.imagePath) {
        getTexture(spriteData.imagePath).then(texture => {
          if (displayObj && !displayObj.destroyed) {
            displayObj.texture = texture
          }
        })
      }
    }

    if (spriteData.imagePath && displayObj.texture?.label !== spriteData.imagePath) {
      getTexture(spriteData.imagePath).then(texture => {
        if (displayObj && !displayObj.destroyed) {
          displayObj.texture = texture
        }
      })
    }

    if (displayObj) {
      // 脏检查：只在实际数据变化时更新属性
      const displayAngle = spriteData.angle * Math.PI / 180
      const s = spriteData.scale * spriteData.scaleX
      const sy = spriteData.scale * spriteData.scaleY
      const propsKey = `${spriteData.x.toFixed(1)},${spriteData.y.toFixed(1)},${displayAngle.toFixed(4)},${spriteData.visible},${spriteData.layer},${s.toFixed(4)},${sy.toFixed(4)}`
      if (displayObj._lastPropsKey !== propsKey) {
        displayObj._lastPropsKey = propsKey
        displayObj.x = Math.round(spriteData.x)
        displayObj.y = Math.round(spriteData.y)
        displayObj.rotation = (spriteData.angle * Math.PI) / 180
        displayObj.scale.x = spriteData.scale * spriteData.scaleX
        displayObj.scale.y = spriteData.scale * spriteData.scaleY
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
      if (tileData.type === 'image' && tileData.imagePath) {
        const texture = await getTexture(tileData.imagePath)
        displayObj = new PIXI.Sprite(texture)
        displayObj.anchor = { x: 0, y: 0 }
      } else if (tileData.type === 'tile' && tileData.tileSetIndex !== undefined && tileData.tileId !== undefined) {
        const texture = await getTileFrame(tileData.tileSetIndex, tileData.tileId)
        if (texture) {
          displayObj = new PIXI.Sprite(texture)
          displayObj.anchor = { x: 0, y: 0 }
        }
      }

      if (displayObj) {
        tileLayerContainer.addChild(displayObj)
        tileDisplayObjects.set(tileData.id, displayObj)
      }
    }

    if (displayObj) {
      // 脏检查：只在实际数据变化时更新属性
      const tileScale = tileData.scale ?? 1
      const propsKey = `${tileData.x},${tileData.y},${tileData.angle ?? 0},${tileScale},${tileData.scaleX ?? 1},${tileData.scaleY ?? 1},${tileData.opacity ?? 1},${tileData.layer}`
      if (displayObj._lastPropsKey !== propsKey) {
        displayObj._lastPropsKey = propsKey
        displayObj.x = tileData.x
        displayObj.y = tileData.y
        displayObj.rotation = ((tileData.angle ?? 0) * Math.PI) / 180
        displayObj.scale.x = tileScale * (tileData.scaleX ?? 1)
        displayObj.scale.y = tileScale * (tileData.scaleY ?? 1)
        displayObj.alpha = tileData.opacity ?? 1
        displayObj.zIndex = tileData.layer
      }
      // 视口裁剪：只渲染相机视口内的瓦片，减少 GPU 负担
      const tileSize = tileData.tileSize || renderStore.tileGridSize
      const cam = renderStore.camera
      const viewLeft = cam.x - LOGIC_W / 2 - tileSize
      const viewRight = cam.x + LOGIC_W / 2 + tileSize
      const viewTop = cam.y - LOGIC_H / 2 - tileSize
      const viewBottom = cam.y + LOGIC_H / 2 + tileSize
      displayObj.visible = tileData.x + tileSize > viewLeft
        && tileData.x < viewRight
        && tileData.y + tileSize > viewTop
        && tileData.y < viewBottom
    }
  }

  tileLayerContainer.sortChildren()
  tilesSyncing = false
}

function syncSayTexts() {
  if (!app || !uiContainer) return

  // 回收不再需要的气泡对象（隐藏而非销毁，供后续复用）
  for (const [id, container] of sayDisplayObjects) {
    if (!renderStore.sayTexts.has(id)) {
      container.visible = false
    }
  }

  for (const [id, sayData] of renderStore.sayTexts) {
    let container = sayDisplayObjects.get(id)
    if (!container) {
      // 优先复用被隐藏的气泡对象
      for (const [, pooled] of sayDisplayObjects) {
        if (!pooled.visible) {
          container = pooled
          sayDisplayObjects.delete(id)
          // 重新绑定到新 id
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
        text.anchor = { x: 0.5, y: 1 }
        container.addChild(text)
        uiContainer.addChild(container)
      }
      sayDisplayObjects.set(id, container)
    }

    container.visible = true
    container.x = sayData.x
    container.y = sayData.y
    container.zIndex = 1

    const textObj = container.children[1]
    if (textObj && textObj.text !== undefined) {
      if (textObj.text !== sayData.text) {
        textObj.text = sayData.text
        // 仅当文本变化时重绘背景
        const bg = container.children[0]
        if (bg) {
          const padding = 6
          const w = textObj.width + padding * 2
          const h = textObj.height + padding * 2
          bg.clear()
          bg.roundRect(-w / 2, -h, w, h, 6)
          bg.fill({ color: 0xffffff, alpha: 0.9 })
          bg.stroke({ width: 1, color: 0x333333 })
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

function gameLoop() {
  if (!app) return

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
  const gameKeywords = ['run()', 'Sprite(', 'load_map(', 'key_down(', 'key_pressed(', 'Timer(', 'mouse', 'wait(']
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
