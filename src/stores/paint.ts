import { ref } from 'vue'
import { defineStore } from 'pinia'

export type PaintTool = 'select' | 'reshape' | 'brush' | 'eraser' | 'fill' | 'line' | 'rect' | 'ellipse' | 'text' | 'eyedropper'
export type PaintMode = 'vector' | 'bitmap'

export const ARTBOARD_PRESETS = [
  { label: '96 × 96', w: 96, h: 96 },
  { label: '240 × 180', w: 240, h: 180 },
  { label: '480 × 360', w: 480, h: 360 },
  { label: '640 × 480', w: 640, h: 480 },
] as const

/** 默认画板尺寸：Scratch 造型区同款 480×360 */
export const DEFAULT_ARTBOARD = { w: 480, h: 360 }

/**
 * 绘制编辑器 UI 状态。
 * 硬约束：PaperScope / paper.Item / CanvasRenderingContext2D 等非原始对象
 * 一律不得放入本 store（Vue 深层响应式 proxy 会破坏 paper 内部对象），
 * 它们只存放在 paint-editor composables 的闭包中。
 *
 * 颜色模型：单一绘制色（fillColor）。画笔/填充/直线/矩形/椭圆全部使用最后一次
 * 选取的颜色，切换工具不会改变颜色。strokeColor 仅留给后续矢量模式的填充+描边组合。
 */
export const usePaintStore = defineStore('paint', () => {
  const activeTool = ref<PaintTool>('brush')
  const mode = ref<PaintMode>('bitmap')

  /** 唯一绘制色：所有位图绘制工具共用 */
  const fillColor = ref('#5BFB84')
  /** 矢量模式的描边色（位图工具不使用） */
  const strokeColor = ref('#ffffff')
  const fillEnabled = ref(true)
  const strokeEnabled = ref(false)
  /** 形状/直线工具的描边线宽 */
  const strokeWidth = ref(4)
  /** 画笔/橡皮的笔刷直径 */
  const brushSize = ref(12)
  /** 0-100 */
  const opacity = ref(100)

  const artboardWidth = ref(DEFAULT_ARTBOARD.w)
  const artboardHeight = ref(DEFAULT_ARTBOARD.h)

  /** 视图缩放（1 = 100%）与平移（px），仅 UI 视图状态 */
  const zoom = ref(1)
  const panX = ref(0)
  const panY = ref(0)

  const canUndo = ref(false)
  const canRedo = ref(false)
  /** 画板有内容（用于锁定画板尺寸、拦截未保存关闭等） */
  const dirty = ref(false)
  /** 矢量模式启用开关：Stage 2 开放前切换按钮禁用 */
  const vectorEnabled = ref(false)

  function setTool(tool: PaintTool) {
    activeTool.value = tool
  }

  function setMode(m: PaintMode) {
    if (m === 'vector' && !vectorEnabled.value) return
    mode.value = m
  }

  function setZoom(z: number) {
    zoom.value = Math.min(32, Math.max(0.1, z))
  }

  function resetView() {
    zoom.value = 1
    panX.value = 0
    panY.value = 0
  }

  /** 打开绘制页时重置全部状态（配合 MainLayout 的 key 递增重建） */
  function reset() {
    activeTool.value = 'brush'
    mode.value = 'bitmap'
    fillColor.value = '#5BFB84'
    strokeColor.value = '#ffffff'
    fillEnabled.value = true
    strokeEnabled.value = false
    strokeWidth.value = 4
    brushSize.value = 12
    opacity.value = 100
    artboardWidth.value = DEFAULT_ARTBOARD.w
    artboardHeight.value = DEFAULT_ARTBOARD.h
    zoom.value = 1
    panX.value = 0
    panY.value = 0
    canUndo.value = false
    canRedo.value = false
    dirty.value = false
  }

  return {
    activeTool,
    mode,
    fillColor,
    strokeColor,
    fillEnabled,
    strokeEnabled,
    strokeWidth,
    brushSize,
    opacity,
    artboardWidth,
    artboardHeight,
    zoom,
    panX,
    panY,
    canUndo,
    canRedo,
    dirty,
    vectorEnabled,
    setTool,
    setMode,
    setZoom,
    resetView,
    reset,
  }
})
