import { ref, watch, type Ref } from 'vue'
import { useMapStore } from '../stores/map'
import { useMapEditorStore } from '../stores/mapEditor'

interface MapViewportOptions {
  canvasRef: Ref<HTMLDivElement | undefined>
  getApp: () => any
  getPIXI: () => any
  // 缩放后需要重绘的叠加层（碰撞框），避免循环依赖
  onZoom?: () => void
}

/**
 * 地图画布视口：缩放、平移、网格/坐标轴/地图边框、屏幕坐标换算。
 */
export function useMapViewport(options: MapViewportOptions) {
  const mapStore = useMapStore()
  const mapEditorStore = useMapEditorStore()
  const { canvasRef, getApp, getPIXI } = options

  const currentScale = ref(1.6)

  let isPanning = false
  let isSpaceHeld = false
  let lastPointer = { x: 0, y: 0 }
  let gridGraphics: any = null
  let axisX: any = null
  let axisY: any = null
  let mapBorderRect: any = null

  function setCursor(style: string) {
    const app = getApp()
    if (app?.canvas) (app.canvas as HTMLCanvasElement).style.cursor = style
  }

  // --- Grid / Axes ---

  function drawGrid() {
    const app = getApp()
    const PIXI = getPIXI()
    if (!app || !PIXI) {
      return
    }
    if (gridGraphics) {
      app.stage.removeChild(gridGraphics)
      gridGraphics.destroy()
    }
    gridGraphics = new PIXI.Graphics()

    const { tileSize } = mapStore.mapData
    const extent = 200
    const totalW = extent * 2 * tileSize
    const totalH = extent * 2 * tileSize
    const offsetX = -extent * tileSize
    const offsetY = -extent * tileSize

    for (let x = -extent; x <= extent; x++) {
      gridGraphics.moveTo(x * tileSize, offsetY)
      gridGraphics.lineTo(x * tileSize, offsetY + totalH)
    }
    for (let y = -extent; y <= extent; y++) {
      gridGraphics.moveTo(offsetX, y * tileSize)
      gridGraphics.lineTo(offsetX + totalW, y * tileSize)
    }
    gridGraphics.stroke({ width: 0.5, color: 0x333333 })

    gridGraphics.visible = mapEditorStore.showGrid
    app.stage.addChildAt(gridGraphics, 0)
  }

  function drawAxes() {
    const app = getApp()
    const PIXI = getPIXI()
    if (!app || !PIXI) return
    if (axisX) { app.stage.removeChild(axisX); axisX.destroy() }
    if (axisY) { app.stage.removeChild(axisY); axisY.destroy() }

    axisX = new PIXI.Graphics()
    axisX.moveTo(-100000, 0)
    axisX.lineTo(100000, 0)
    axisX.stroke({ width: 1, color: 0xC83232 })
    app.stage.addChild(axisX)

    axisY = new PIXI.Graphics()
    axisY.moveTo(0, -100000)
    axisY.lineTo(0, 100000)
    axisY.stroke({ width: 1, color: 0x32C832 })
    app.stage.addChild(axisY)
  }

  function drawGameWindow() {
    const app = getApp()
    const PIXI = getPIXI()
    if (!app || !PIXI) return
    if (mapBorderRect) { app.stage.removeChild(mapBorderRect); mapBorderRect.destroy() }

    const mapW = mapStore.mapData.width * mapStore.mapData.tileSize
    const mapH = mapStore.mapData.height * mapStore.mapData.tileSize
    if (mapW <= 0 || mapH <= 0) return

    mapBorderRect = new PIXI.Graphics()
    mapBorderRect.rect(0, 0, mapW, mapH)
    mapBorderRect.stroke({ width: 1, color: 0x4A90D9, alpha: 0.6 })
    app.stage.addChild(mapBorderRect)
  }

  function applyScale() {
    const app = getApp()
    if (!app) return
    app.stage.scale.set(currentScale.value, currentScale.value)
  }

  function centerView() {
    const app = getApp()
    if (!app || !canvasRef.value) return
    // 重置为 1.0 缩放，让用户看到坐标原点 (0,0) 和游戏窗口 (640x480)
    currentScale.value = 1.0
    applyScale()
    // 留 30px 边距，原点在左上，游戏窗口完整可见
    app.stage.x = 30
    app.stage.y = 30
  }

  function redraw() {
    drawGrid()
    drawAxes()
    drawGameWindow()
  }

  // --- Interaction ---

  function onWheel(e: WheelEvent) {
    e.preventDefault()

    const app = getApp()
    if (!app) return
    // Zoom canvas
    const rect = canvasRef.value?.getBoundingClientRect()
    if (!rect) return
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top
    const worldX = (mouseX - app.stage.x) / currentScale.value
    const worldY = (mouseY - app.stage.y) / currentScale.value
    const delta = e.deltaY > 0 ? 0.9 : 1.1
    currentScale.value = Math.max(0.5, Math.min(4, currentScale.value * delta))
    app.stage.x = mouseX - worldX * currentScale.value
    app.stage.y = mouseY - worldY * currentScale.value
    applyScale()
    // 手柄尺寸随缩放变化，重绘碰撞叠加层
    options.onZoom?.()
  }

  function startPan(clientX: number, clientY: number) {
    isPanning = true
    lastPointer = { x: clientX, y: clientY }
  }

  // 返回 true 表示事件已被平移消费
  function handlePanMove(clientX: number, clientY: number): boolean {
    if (!isPanning) return false
    const app = getApp()
    if (app) {
      const dx = clientX - lastPointer.x
      const dy = clientY - lastPointer.y
      app.stage.x += dx
      app.stage.y += dy
    }
    lastPointer = { x: clientX, y: clientY }
    return true
  }

  function endPan() {
    isPanning = false
  }

  function isPanningNow(): boolean {
    return isPanning
  }

  function isSpacePressed(): boolean {
    return isSpaceHeld
  }

  function onSpaceDown() {
    isSpaceHeld = true
    setCursor('grab')
  }

  function onSpaceUp() {
    isSpaceHeld = false
    if (!isPanning) setCursor('default')
  }

  function screenToGrid(e: PointerEvent): { x: number; y: number } | null {
    const app = getApp()
    if (!canvasRef.value || !app) return null
    const rect = canvasRef.value.getBoundingClientRect()
    const sx = (e.clientX - rect.left - app.stage.x) / currentScale.value
    const sy = (e.clientY - rect.top - app.stage.y) / currentScale.value
    const tileSize = mapStore.mapData.tileSize
    return {
      x: Math.floor(sx / tileSize),
      y: Math.floor(sy / tileSize),
    }
  }

  function screenToWorld(e: PointerEvent | DragEvent): { x: number; y: number } | null {
    const app = getApp()
    if (!canvasRef.value || !app) return null
    const rect = canvasRef.value.getBoundingClientRect()
    const clientX = 'clientX' in e ? e.clientX : 0
    const clientY = 'clientY' in e ? e.clientY : 0
    return {
      x: (clientX - rect.left - app.stage.x) / currentScale.value,
      y: (clientY - rect.top - app.stage.y) / currentScale.value,
    }
  }

  watch(() => mapEditorStore.showGrid, () => {
    if (gridGraphics) gridGraphics.visible = mapEditorStore.showGrid
  })

  return {
    currentScale,
    drawGrid,
    drawAxes,
    drawGameWindow,
    applyScale,
    centerView,
    redraw,
    onWheel,
    startPan,
    handlePanMove,
    endPan,
    isPanningNow,
    isSpacePressed,
    onSpaceDown,
    onSpaceUp,
    setCursor,
    screenToGrid,
    screenToWorld,
  }
}
