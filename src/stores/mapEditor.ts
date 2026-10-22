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
