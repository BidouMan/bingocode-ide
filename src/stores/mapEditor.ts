import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { MapTool, CollisionTool, CollisionLayerTool } from './map'

/**
 * 地图编辑器会话状态：工具、显示开关、光标、碰撞编辑模式。
 * 与地图文档数据（layers/resources/tiles/images）分离，避免页面状态污染存档模型。
 */
export const useMapEditorStore = defineStore('mapEditor', () => {
  const showGrid = ref(true)
  // 吸附模式开关：关闭=像素吸附（默认），开启=网格吸附
  const snapToGrid = ref(false)
  const currentTool = ref<MapTool>('select')
  const collisionTool = ref<CollisionTool>('move')
  const snapToPixel = ref(true)
  const cursorX = ref<number | null>(null)
  const cursorY = ref<number | null>(null)
  const imageTool = ref<'select' | 'reshape' | 'brush' | 'eraser' | 'fill' | 'text' | 'line' | 'rect' | 'ellipse' | 'eyedropper'>('select')
  // 图片绘制模式：位图 / 矢量（默认矢量，与角色编辑器一致）
  const paintMode = ref<'bitmap' | 'vector'>('vector')
  // 碰撞层工具：默认选择移动，形状按钮用独立状态记住上次形状
  const collisionLayerTool = ref<CollisionLayerTool>('select')
  // 记住当前形状选择：切换选择/增删锚点工具时，形状按钮保持常亮
  const collisionShapeTool = ref<'rect' | 'circle' | 'capsule' | 'polygon'>('rect')
  // 当前正在编辑的碰撞体 id（属于当前碰撞层）
  const activeCollisionPolygonId = ref<string | null>(null)
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

  function setCollisionLayerTool(tool: CollisionLayerTool) {
    collisionLayerTool.value = tool
    // 形状按钮独立记忆：只有真正选择形状时才更新，选择/增删锚点不影响常亮状态
    if (tool === 'rect' || tool === 'circle' || tool === 'capsule' || tool === 'polygon') {
      collisionShapeTool.value = tool
    }
  }

  function setActiveCollisionPolygonId(id: string | null) {
    activeCollisionPolygonId.value = id
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
    imageTool,
    paintMode,
    collisionLayerTool,
    collisionShapeTool,
    activeCollisionPolygonId,
    hasPixelSelection,
    hasPaintClipboard,
    setImageTool,
    setPaintMode,
    setCollisionLayerTool,
    setActiveCollisionPolygonId,
    setTool,
    toggleGrid,
    toggleSnapToGrid,
    setCollisionTool,
    toggleSnapToPixel,
    setCursorPos,
  }
})
