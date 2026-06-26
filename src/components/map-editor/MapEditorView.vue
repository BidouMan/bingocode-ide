<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const canvasRef = ref<HTMLDivElement>()

let app: any = null

async function initPixi() {
  if (!canvasRef.value) return

  try {
    const PIXI = await import('pixi.js')

    app = new PIXI.Application()

    await app.init({
      background: '#1e1e1e',
      resizeTo: canvasRef.value,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
    })

    canvasRef.value.appendChild(app.canvas)

    const grid = new PIXI.Graphics()
    grid.rect(0, 0, 640, 480)
    grid.stroke({ width: 1, color: 0x444444 })
    app.stage.addChild(grid)

    const border = new PIXI.Graphics()
    border.rect(0, 0, 640, 480)
    border.stroke({ width: 2, color: 0x3778c8 })
    app.stage.addChild(border)
  } catch (e) {
    console.error('Failed to init PixiJS:', e)
  }
}

onMounted(() => {
  initPixi()
})

onBeforeUnmount(() => {
  if (app) {
    app.destroy(true)
    app = null
  }
})
</script>

<template>
  <div class="h-full flex bg-[#1a1a1a]">
    <div class="flex-1 flex items-center justify-center overflow-auto p-4">
      <div ref="canvasRef" class="relative" />
    </div>

    <div class="w-56 border-l border-[#2d2d2d] bg-[#252526] p-3 flex flex-col gap-3 text-xs">
      <div>
        <h3 class="text-gray-400 mb-2 font-medium">图层</h3>
        <div class="space-y-1">
          <div class="flex items-center gap-2 px-2 py-1 rounded bg-[#2d2d2d]">
            <input type="checkbox" checked class="accent-[#3778c8]" />
            <span class="text-white">背景层</span>
          </div>
        </div>
      </div>

      <div>
        <h3 class="text-gray-400 mb-2 font-medium">瓦片集</h3>
        <p class="text-gray-600">暂无瓦片集</p>
      </div>

      <div>
        <h3 class="text-gray-400 mb-2 font-medium">碰撞</h3>
        <p class="text-gray-600">选择瓦片编辑碰撞</p>
      </div>

      <div class="mt-auto">
        <button class="w-full px-3 py-1.5 bg-[#3778c8] text-white rounded hover:bg-[#2d6ab8] transition-colors">
          导出地图
        </button>
      </div>
    </div>
  </div>
</template>
