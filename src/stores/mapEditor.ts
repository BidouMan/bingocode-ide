import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { MapTool, CollisionTool, ImageCollisionTool } from './map'

/**
 * 地图编辑器会话状态：工具、显示开关、光标、碰撞编辑模式。
 * 与地图文档数据（layers/resources/tiles/images）分离，避免页面状态污染存档模型。
 */
export const useMapEditorStore = defineStore('mapEditor', () => {
  const showGrid = ref(true)
  const snapToGrid = ref(true)
  const currentTool = ref<MapTool>('select')
  const collisionTool = ref<CollisionTool>('move')
  const snapToPixel = ref(true)
  const cursorX = ref<number | null>(null)
  const cursorY = ref<number | null>(null)
  const imageCollisionTool = ref<ImageCollisionTool>('none')
  const showCollision = ref(false)
  // 图片模式画布内绘制工具（select = 地图选取，不绘制）
  const imageTool = ref<'select' | 'reshape' | 'brush' | 'eraser' | 'fill' | 'text' | 'line' | 'rect' | 'ellipse' | 'eyedropper'>('select')
  // 图片绘制模式：位图 / 矢量（矢量内容退出时烘焙为像素）
  const paintMode = ref<'bitmap' | 'vector'>('bitmap')
  // 像素浮动选区是否存在 / 选区剪贴板是否有内容（工具条按钮可用性）
  const hasPixelSelection = ref(false)
  const hasPaintClipboard = ref(false)

  function setTool(tool: MapTool) {
    currentTool.value = tool
  }

  function toggleGrid() {
    showGrid.value = !showGrid.value
  }

  function toggleSnapToGrid() {
    snapToGrid.value = !snapToGrid.value
  }

  function setCollisionTool(tool: CollisionTool) {
    collisionTool.value = tool
  }

  function toggleSnapToPixel() {
    snapToPixel.value = !snapToPixel.value
  }

  function setCursorPos(x: number | null, y: number | null) {
    cursorX.value = x
    cursorY.value = y
  }

  function setImageCollisionTool(tool: ImageCollisionTool) {
    imageCollisionTool.value = tool
  }

  function toggleShowCollision() {
    showCollision.value = !showCollision.value
  }

  function setImageTool(tool: 'select' | 'reshape' | 'brush' | 'eraser' | 'fill' | 'text' | 'line' | 'rect' | 'ellipse' | 'eyedropper') {
    imageTool.value = tool
  }

  function setPaintMode(mode: 'bitmap' | 'vector') {
    paintMode.value = mode
  }

  return {
    showGrid,
    snapToGrid,
    currentTool,
    collisionTool,
    snapToPixel,
    cursorX,
    cursorY,
    imageCollisionTool,
    showCollision,
    imageTool,
    paintMode,
    hasPixelSelection,
    hasPaintClipboard,
    setImageTool,
    setPaintMode,
    setTool,
    toggleGrid,
    toggleSnapToGrid,
    setCollisionTool,
    toggleSnapToPixel,
    setCursorPos,
    setImageCollisionTool,
    toggleShowCollision,
  }
})
