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
  /** 矢量模式启用开关（Stage 2 起开放） */
  const vectorEnabled = ref(true)
  /** 追加模式（为现有角色画新帧）：画板尺寸锁定为目标角色帧尺寸，禁止修改 */
  const sizeForced = ref(false)

  // ─── 矢量模式状态（usePaperScope 写入，顶栏按钮读取）───
  /** 矢量撤销/重做可用（与位图 canUndo/canRedo 分开，顶栏按模式取值） */
  const vectorCanUndo = ref(false)
  const vectorCanRedo = ref(false)
  /** 矢量选中对象数（>0 时顶栏复制/删除/图层按钮可用） */
  const vectorSelectedCount = ref(0)
  /** 矢量剪贴板有内容 */
  const hasVectorClipboard = ref(false)
  /** 任意帧存在矢量内容（禁用裁切：裁位图会与矢量层错位） */
  const vectorContent = ref(false)
  /**
   * 矢量选中变换框几何（画板逻辑坐标，含旋转定向）：由 usePaperScope 写入，
   * PaintArtboard 用 SVG overlay 渲染（与位图 transformBox 同构）——
   * 不走 paper.item.selected（那会渲染进 canvas、随保存烙印）。
   */
  const vectorSelBox = ref<{
    corners: { x: number; y: number }[]
    handles: { x: number; y: number }[]
    rotateTop: { x: number; y: number }
    rotateAt: { x: number; y: number }
  } | null>(null)

  // ─── 位图选区状态（引擎写入，顶栏按钮/蚂蚁线 overlay 读取）───
  /** 当前选区矩形（画板逻辑坐标整数）：框选中=拖动矩形；有浮动选区=其 AABB */
  const selection = ref<{ x: number; y: number; w: number; h: number } | null>(null)
  /** 存在浮动选区（带变换框+手柄，蚂蚁线 div 隐藏改由画布绘制） */
  const floatActive = ref(false)
  /**
   * 变换框几何（画板逻辑坐标）：由引擎在浮动选区每次变化时计算，
   * PaintArtboard 用独立 SVG 图层渲染——矢量平滑且绝不污染图像像素。
   */
  const transformBox = ref<{
    corners: { x: number; y: number }[]
    handles: { x: number; y: number }[]
    rotateTop: { x: number; y: number }
    rotateAt: { x: number; y: number }
  } | null>(null)
  /** 剪贴板有内容（供粘贴按钮启用） */
  const hasClipboard = ref(false)

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
    // 模式切换工具回退（对齐 Scratch switchModeForFormat）：
    // reshape 仅矢量存在 → 切位图回退 select；其余工具两模式共有保持不变
    if (m === 'bitmap' && activeTool.value === 'reshape') {
      activeTool.value = 'select'
    }
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
    vectorCanUndo.value = false
    vectorCanRedo.value = false
    vectorSelectedCount.value = 0
    hasVectorClipboard.value = false
    vectorContent.value = false
    vectorSelBox.value = null
    selection.value = null
    floatActive.value = false
    transformBox.value = null
    hasClipboard.value = false
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
    vectorCanUndo,
    vectorCanRedo,
    vectorSelectedCount,
    hasVectorClipboard,
    vectorContent,
    vectorSelBox,
    selection,
    floatActive,
    transformBox,
    hasClipboard,
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
