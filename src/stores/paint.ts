import { ref } from 'vue'
import { defineStore } from 'pinia'

export type PaintTool = 'select' | 'reshape' | 'brush' | 'eraser' | 'fill' | 'line' | 'rect' | 'ellipse' | 'text' | 'eyedropper'
export type PaintMode = 'vector' | 'bitmap'

/** 绘制帧的 UI 元数据（像素数据在引擎闭包的离屏画布中，不进 store） */
export interface PaintFrameMeta {
  id: string
  /** 帧缩略图 dataURL，由引擎在切换/落盘时更新 */
  thumb?: string
}

/** 画板尺寸上限（手动输入约束） */
export const ARTBOARD_MAX = 2048
/** 默认画板尺寸：与游戏窗口一致 640×480 */
export const DEFAULT_ARTBOARD = { w: 640, h: 480 }

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
  /** 追加模式（为现有角色画新帧）：画板尺寸锁定为目标角色帧尺寸，禁止修改 */
  const sizeForced = ref(false)

  /** 序列帧元数据（像素在绘制引擎闭包；下标与引擎离屏画布数组对齐） */
  const frames = ref<PaintFrameMeta[]>([{ id: makeFrameId() }])
  const activeFrameIndex = ref(0)

  function makeFrameId(): string {
    return `f${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
  }

  function selectFrame(index: number) {
    if (index >= 0 && index < frames.value.length) {
      activeFrameIndex.value = index
    }
  }

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
    sizeForced.value = false
    frames.value = [{ id: makeFrameId() }]
    activeFrameIndex.value = 0
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
    sizeForced,
    frames,
    activeFrameIndex,
    selectFrame,
    makeFrameId,
    setTool,
    setMode,
    setZoom,
    resetView,
    reset,
  }
})
