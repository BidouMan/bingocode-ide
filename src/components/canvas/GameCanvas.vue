<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { convertFileSrc } from '@tauri-apps/api/core'
import { useRenderStore } from '../../stores/render'
import { useEditorStore } from '../../stores/editor'
import { useEngine } from '../../composables/useEngine'
import { signalGameCanvasReady, registerGameCanvasMount, unregisterGameCanvasMount } from '../../utils/gameCanvasReady'

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

/** resize 后立即同步渲染，避免 WebGL buffer 重置导致的空帧闪烁 */
function handleResize() {
  if (!app || !containerRef.value) return
  const vp = containerRef.value
  app.renderer.resize(vp.clientWidth, vp.clientHeight)
  fitStage()
  // 同步渲染一帧，填满新 buffer，等下一帧不会闪烁
  app.renderer.render(app.stage)
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

    displayObj.x = spriteData.x
    displayObj.y = spriteData.y
    displayObj.rotation = (spriteData.angle * Math.PI) / 180
    displayObj.scale.x = spriteData.scale * spriteData.scaleX
    displayObj.scale.y = spriteData.scale * spriteData.scaleY
    displayObj.visible = spriteData.visible
    // 精灵在独立 spriteContainer 中，zIndex 用于容器内排序
    displayObj.zIndex = spriteData.layer
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
      displayObj.x = tileData.x
      displayObj.y = tileData.y
      displayObj.rotation = ((tileData.angle ?? 0) * Math.PI) / 180
      const s = tileData.scale ?? 1
      displayObj.scale.x = s * (tileData.scaleX ?? 1)
      displayObj.scale.y = s * (tileData.scaleY ?? 1)
      displayObj.alpha = tileData.opacity ?? 1
      displayObj.zIndex = tileData.layer

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
      textObj.text = sayData.text
    }

    // 重绘背景
    const bg = container.children[0]
    if (bg && textObj) {
      bg.clear()
      const padding = 6
      const w = textObj.width + padding * 2
      const h = textObj.height + padding * 2
      bg.roundRect(-w / 2, -h, w, h, 6)
      bg.fill({ color: 0xffffff, alpha: 0.9 })
      bg.stroke({ width: 1, color: 0x333333 })
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
    textObj.text = data.text
    textObj.x = data.x
    textObj.y = data.y
  }
}

function syncHitboxes() {
  if (!app || !uiContainer) return

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
    }
    graphics.clear()
    if (data.rect) {
      const [left, top, right, bottom] = data.rect
      graphics.rect(left, top, right - left, bottom - top)
      graphics.stroke({ width: 1, color: 0x00ff00 })
    }
  }
}

function gameLoop() {
  if (!app) return

  const shake = renderStore.getShakeOffset()
  gameContainer.x = -renderStore.camera.x + LOGIC_W / 2 + shake.x
  gameContainer.y = -renderStore.camera.y + LOGIC_H / 2 + shake.y

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

function usesEngine(): boolean {
  const code = editorStore.currentTab?.content || ''
  if (code.includes('bingo_engine')) return true
  // 检测游戏关键词（与 useEngine.ts 的自动注入逻辑一致）
  const gameKeywords = ['run()', 'Sprite(', 'load_map(', 'key_down(', 'key_pressed(', 'Timer(', 'mouse', 'wait(']
  return gameKeywords.some(kw => code.includes(kw))
}

function onCanvasMouseMove(e: MouseEvent) {
  if (!app || !containerRef.value || !editorStore.isRunning || !usesEngine()) return
  const rect = containerRef.value.getBoundingClientRect()
  const scaleX = rect.width / LOGIC_W
  const scaleY = rect.height / LOGIC_H
  const scale = Math.min(scaleX, scaleY)
  const offsetX = (rect.width - LOGIC_W * scale) / 2
  const offsetY = (rect.height - LOGIC_H * scale) / 2
  const x = (e.clientX - rect.left - offsetX) / scale
  const y = (e.clientY - rect.top - offsetY) / scale
  engine.sendMouseMove(x, y)
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

onMounted(async () => {
  registerGameCanvasMount()
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
  unregisterGameCanvasMount()

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
</script>

<template>
  <div ref="containerRef" class="game-canvas-container" tabindex="-1">
    <div
      v-if="renderStore.fps > 0"
      class="absolute top-2 left-2 px-2 py-0.5 bg-black/60 text-green-400 text-xs font-mono rounded z-10"
    >
      FPS: {{ renderStore.fps }}
    </div>
  </div>
</template>

<style scoped>
.game-canvas-container {
  width: 100%;
  height: 100%;
  background: rgb(26, 28, 33);
  outline: none;
}
</style>
