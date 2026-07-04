<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { convertFileSrc } from '@tauri-apps/api/core'
import { useRenderStore } from '../../stores/render'
import { useEditorStore } from '../../stores/editor'
import { useEngine } from '../../composables/useEngine'

const props = defineProps<{
  previewMode?: boolean
}>()

const renderStore = useRenderStore()
const editorStore = useEditorStore()
const engine = useEngine()
const containerRef = ref<HTMLDivElement>()

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
let stageContainer: any = null
let currentScaleMode: 'nearest' | 'linear' = 'linear'
let tilesSyncing = false
let spritesSyncing = false

const LOGIC_W = 640
const LOGIC_H = 480

async function initPixi() {
  if (!containerRef.value) return

  PIXI = await import('pixi.js')

  app = new PIXI.Application()
  await app.init({
    background: '#1e1e1e',
    resizeTo: containerRef.value,
    antialias: true,
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
  })

  containerRef.value.appendChild(app.canvas)

  stageContainer = new PIXI.Container()
  gameContainer = new PIXI.Container()
  stageContainer.addChild(gameContainer)
  app.stage.addChild(stageContainer)

  const border = new PIXI.Graphics()
  border.rect(0, 0, LOGIC_W, LOGIC_H)
  border.stroke({ width: 2, color: 0x3778c8 })
  stageContainer.addChild(border)

  const mask = new PIXI.Graphics()
  mask.rect(0, 0, LOGIC_W, LOGIC_H)
  mask.fill({ color: 0x000000 })
  stageContainer.mask = mask
  stageContainer.addChild(mask)

  fitStage()
  window.addEventListener('resize', fitStage)
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

  try {
    const isLocal = imagePath.startsWith('/') || imagePath.match(/^[A-Z]:\\/i)
    const url = isLocal ? convertFileSrc(imagePath) : imagePath
    const texture = await PIXI.Assets.load(url)
    texture.source.scaleMode = currentScaleMode
    textureCache.set(imagePath, texture)
    return texture
  } catch (e) {
    const g = new PIXI.Graphics()
    g.rect(0, 0, 32, 32)
    g.fill({ color: 0xff00ff })
    const placeholder = app.renderer.generateTexture(g)
    textureCache.set(imagePath, placeholder)
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
  if (!app || !gameContainer || spritesSyncing) return
  spritesSyncing = true

  const currentSpriteIds = new Set(renderStore.sprites.keys())

  for (const [id, displayObj] of spriteDisplayObjects) {
    if (!currentSpriteIds.has(id)) {
      gameContainer.removeChild(displayObj)
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
      gameContainer.addChild(displayObj)
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
    displayObj.zIndex = spriteData.layer
  }

  gameContainer.sortChildren()
  spritesSyncing = false
}

async function syncTiles() {
  if (!app || !gameContainer || tilesSyncing) return
  tilesSyncing = true

  const currentTileIds = new Set(renderStore.tiles.keys())

  for (const [id, displayObj] of tileDisplayObjects) {
    if (!currentTileIds.has(id)) {
      gameContainer.removeChild(displayObj)
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
        gameContainer.addChild(displayObj)
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
      displayObj.zIndex = tileData.layer * 1000 - 1
    }
  }

  gameContainer.sortChildren()
  tilesSyncing = false
}

function syncSayTexts() {
  if (!app || !gameContainer) return

  const currentIds = new Set(renderStore.sayTexts.keys())

  for (const [id, obj] of sayDisplayObjects) {
    if (!currentIds.has(id)) {
      gameContainer.removeChild(obj)
      obj.destroy()
      sayDisplayObjects.delete(id)
    }
  }

  for (const [id, sayData] of renderStore.sayTexts) {
    let container = sayDisplayObjects.get(id)
    if (!container) {
      container = new PIXI.Container()
      // 气泡背景
      const bg = new PIXI.Graphics()
      container.addChild(bg)
      // 文字
      const text = new PIXI.Text({
        text: sayData.text,
        style: { fill: 0x000000, fontSize: 14, fontFamily: 'Arial' },
      })
      text.anchor = { x: 0.5, y: 1 }
      container.addChild(text)
      gameContainer.addChild(container)
      sayDisplayObjects.set(id, container)
    }

    // 更新位置和文字
    container.x = sayData.x
    container.y = sayData.y
    container.zIndex = 99999

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
  if (!app || !gameContainer) return

  const currentIds = new Set(renderStore.drawTexts.keys())

  for (const [id, obj] of drawTextDisplayObjects) {
    if (!currentIds.has(id)) {
      gameContainer.removeChild(obj)
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
      textObj.zIndex = 100000
      gameContainer.addChild(textObj)
      drawTextDisplayObjects.set(id, textObj)
    }
    textObj.text = data.text
    textObj.x = data.x
    textObj.y = data.y
  }
}

function syncHitboxes() {
  if (!app || !gameContainer) return

  const currentIds = new Set(renderStore.hitboxes.keys())

  for (const [id, obj] of hitboxDisplayObjects) {
    if (!currentIds.has(id)) {
      gameContainer.removeChild(obj)
      obj.destroy()
      hitboxDisplayObjects.delete(id)
    }
  }

  for (const [id, data] of renderStore.hitboxes) {
    let graphics = hitboxDisplayObjects.get(id)
    if (!graphics) {
      graphics = new PIXI.Graphics()
      graphics.zIndex = 99998
      gameContainer.addChild(graphics)
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
  await initPixi()
  if (app) {
    app.ticker.add(gameLoop)
  }
  if (editorStore.isRunning) {
    nextTick(addGameListeners)
  }
})

onBeforeUnmount(() => {
  removeGameListeners()
  window.removeEventListener('resize', fitStage)

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
  background: #1a1a1a;
  outline: none;
}
</style>
