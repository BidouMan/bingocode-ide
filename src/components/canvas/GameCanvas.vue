<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
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
let textureCache: Map<string, any> = new Map()
let gameContainer: any = null
let stageContainer: any = null

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

async function getTexture(imagePath: string): Promise<any> {
  if (textureCache.has(imagePath)) {
    return textureCache.get(imagePath)
  }

  try {
    const texture = await PIXI.Assets.load(imagePath)
    textureCache.set(imagePath, texture)
    return texture
  } catch {
    const g = new PIXI.Graphics()
    g.rect(0, 0, 32, 32)
    g.fill({ color: 0xff00ff })
    const placeholder = app.renderer.generateTexture(g)
    textureCache.set(imagePath, placeholder)
    return placeholder
  }
}

async function syncSprites() {
  if (!app || !gameContainer) return

  const currentIds = new Set(renderStore.sprites.keys())

  for (const [id, displayObj] of spriteDisplayObjects) {
    if (!currentIds.has(id)) {
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
      const texture = await getTexture(spriteData.imagePath)
      displayObj = new PIXI.Sprite(texture)
      displayObj.anchor = { x: 0.5, y: 0.5 }
      gameContainer.addChild(displayObj)
      spriteDisplayObjects.set(spriteData.id, displayObj)
    }

    if (spriteData.imagePath && displayObj.texture?.label !== spriteData.imagePath) {
      const texture = await getTexture(spriteData.imagePath)
      displayObj.texture = texture
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
}

function gameLoop() {
  if (!app) return

  const shake = renderStore.getShakeOffset()
  gameContainer.x = -renderStore.camera.x + LOGIC_W / 2 + shake.x
  gameContainer.y = -renderStore.camera.y + LOGIC_H / 2 + shake.y

  syncSprites()
}

function onKeyDown(e: KeyboardEvent) {
  if (editorStore.isRunning) {
    e.stopPropagation()
    const key = mapKey(e.key)
    engine.sendKey(key, true)
  }
}

function onKeyUp(e: KeyboardEvent) {
  if (editorStore.isRunning) {
    e.stopPropagation()
    const key = mapKey(e.key)
    engine.sendKey(key, false)
  }
}

function onCanvasMouseMove(e: MouseEvent) {
  if (!app || !containerRef.value || !editorStore.isRunning) return
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
  if (editorStore.isRunning) {
    e.stopPropagation()
    engine.sendMouseDown()
  }
}

function onCanvasMouseUp(e: MouseEvent) {
  if (editorStore.isRunning) {
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
  spriteDisplayObjects.clear()
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
