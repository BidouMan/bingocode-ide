import { ref, watch, type Ref } from 'vue'
import { useMapStore } from '../stores/map'
import { useMapEditorStore } from '../stores/mapEditor'
import { USER_ORIGIN_Y } from '../utils/coords'

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
  // 视口版本号：平移/缩放/尺寸变化时递增，供 DOM 叠加层（标记图钉）重新计算屏幕坐标
  const viewVersion = ref(0)

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
    // 复用同一个 Graphics，平移/缩放时只重建路径，避免每帧销毁重建
    if (!gridGraphics) {
      gridGraphics = new PIXI.Graphics()
      app.stage.addChildAt(gridGraphics, 0)
    }
    const g = gridGraphics
    g.clear()

    const tileSize = mapStore.mapData.tileSize
    const scale = currentScale.value
    // 按当前视口计算可见世界范围，保证网格始终铺满整个画布区域
    const left = -app.stage.x / scale
    const top = -app.stage.y / scale
    const right = left + app.screen.width / scale
    const bottom = top + app.screen.height / scale
    // 对齐到瓦片网格并多画一圈，避免边缘出现空白
    const startX = Math.floor(left / tileSize) * tileSize
    const startY = Math.floor(top / tileSize) * tileSize
    const endX = Math.ceil(right / tileSize) * tileSize
    const endY = Math.ceil(bottom / tileSize) * tileSize

    for (let x = startX; x <= endX; x += tileSize) {
      g.moveTo(x, startY)
      g.lineTo(x, endY)
    }
    for (let y = startY; y <= endY; y += tileSize) {
      g.moveTo(startX, y)
      g.lineTo(endX, y)
    }
    g.stroke({ width: 0.5, color: 0x333333 })

    g.visible = mapEditorStore.showGrid
    // 网格随视口重绘，说明视口刚刚变化；通知 DOM 叠加层同步
    viewVersion.value++
  }

  function drawAxes() {
    const app = getApp()
    const PIXI = getPIXI()
    if (!app || !PIXI) return
    if (axisX) { app.stage.removeChild(axisX); axisX.destroy() }
    if (axisY) { app.stage.removeChild(axisY); axisY.destroy() }

    // 坐标轴按用户坐标画：x 轴在用户 y=0 处（世界 y=地图底部），y 轴在 x=0 处
    axisX = new PIXI.Graphics()
    axisX.moveTo(-100000, USER_ORIGIN_Y)
    axisX.lineTo(100000, USER_ORIGIN_Y)
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
    // 重置为 1.0 缩放，让用户看到地图左上角与完整游戏窗口 (640x480)
    currentScale.value = 1.0
    applyScale()
    // 留边距，地图左上角在画布左上方，游戏窗口完整可见；
    // 偏移对齐到瓦片尺寸，网格线从画布左/上边缘开始，不出现半格空白
    const tileSize = mapStore.mapData.tileSize
    const offset = Math.max(tileSize, Math.ceil(30 / tileSize) * tileSize)
    app.stage.x = offset
    app.stage.y = offset
    drawGrid()
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
    // 视口变化后重绘网格，保证始终铺满整块画布
    drawGrid()
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
      // 平移后按新视口重绘网格，避免画布边缘出现空白
      drawGrid()
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
    const clientX = 'clientX' in e ? e.clientX : 0
    const clientY = 'clientY' in e ? e.clientY : 0
    return clientToWorld(clientX, clientY)
  }

  /** 客户端屏幕坐标 → 地图世界坐标（标记拖拽等非 PointerEvent 场景使用） */
  function clientToWorld(clientX: number, clientY: number): { x: number; y: number } | null {
    const app = getApp()
    if (!canvasRef.value || !app) return null
    const rect = canvasRef.value.getBoundingClientRect()
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
    viewVersion,
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
    clientToWorld,
  }
}
