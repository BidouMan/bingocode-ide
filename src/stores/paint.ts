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
  /** 默认矢量模式（对齐 Scratch：新内容默认矢量；vector→bitmap 转换为单向烘焙） */
  const mode = ref<PaintMode>('vector')

  /** 唯一绘制色：所有绘制工具共用（默认 Scratch 紫 #9A66FF = rgb(154,102,255)） */
  const fillColor = ref('#9A66FF')
  /** 矢量模式的描边色（默认柔和深灰——接近黑但不刺眼，便于一眼识别描边；位图工具不使用） */
  const strokeColor = ref('#2d2d2d')
  /**
   * 选中矢量图形是否有可见描边（引擎在选中变化时同步）——
   * 面板「描边」勾选框的选中态来源（无选中时用 strokeEnabled 预设）。
   */
  const selectionHasStroke = ref(false)
  /**
   * 选中图形中存在"本体描边"对象（无可见填充，描边即本体——直线/描边轮廓形）：
   * 粗细滑条下限抬到 1（拖到 0 会删本体致线条消失）。
   */
  const selectionHasBodyStroke = ref(false)
  /** 选中图形全部为本体描边对象：勾选框禁用（本体不可"去描边"） */
  const selectionBodyOnly = ref(false)
  /**
   * 勾选强制信号：strokeEnabled 新旧值可能相同（预设残留时勾选/取消写入值不变），
   * Vue watch 不触发导致勾选无效——每次勾选动作递增 tick 保证信号必达。
   */
  const strokeToggleTick = ref(0)
  /**
   * 拾色模式：面板吸管按钮开启后，下一次画板点击取该点像素色写入目标通道
   * （fill=绘制色 / stroke=描边色），随即退出。Esc 或再点按钮取消。
   */
  const eyedropperActive = ref(false)
  const eyedropperTarget = ref<'fill' | 'stroke'>('fill')
  const fillEnabled = ref(true)
  const strokeEnabled = ref(false)
  // 位图形状样式：实心 / 轮廓（互斥，Scratch 风格）
  const shapeStyle = ref<'fill' | 'outline'>('fill')
  /** 形状/直线工具的描边线宽（默认 0=无描边；画线时引擎保底 1 保证可见） */
  const strokeWidth = ref(0)
  /**
   * 直线工具的本体粗细（独立于描边机制：直线=纯描边对象，本体宽与"给图形加描边"的
   * 粗细是两回事——共用一个值会互相污染）。默认 8。
   */
  const lineWidth = ref(8)
  /** 画笔/橡皮的笔刷直径 */
  const brushSize = ref(12)
  /** 0-100 */
  const opacity = ref(100)
  /**
   * 颜色面板编辑手势进行中（SV 方块/色相条/滑条 pointerdown ~ window pointerup）。
   * 引擎用它区分「一次拖动改色」与「多次独立改色」——撤销只在手势首次压一步、
   * 缩略图只在手势结束统一刷新。
   */
  const colorEditing = ref(false)

  const artboardWidth = ref(DEFAULT_ARTBOARD.w)
  const artboardHeight = ref(DEFAULT_ARTBOARD.h)

  /** 视图缩放（1 = 100%）与平移（px），仅 UI 视图状态 */
  const zoom = ref(1)
  const panX = ref(0)
  const panY = ref(0)
  /**
   * 矢量模式画笔/橡皮的自绘光标位置（画板逻辑坐标，hover 跟随）。
   * dataURL 圆圈光标在大 zoom 下尺寸超浏览器上限会失效，改为 overlay 自绘圈
   *（Scratch 同款：画布内光标圈，随视图正确缩放）。
   */
  const cursorPos = ref<{ x: number; y: number } | null>(null)

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
  /** 选中项中含 Group（顶栏「取消组合」仅此情况可点，防误触普通对象） */
  const vectorCanUngroup = ref(false)
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

  // ─── 塑形工具锚点状态（usePaperScope 写入，PaintArtboard SVG overlay 渲染）───
  /**
   * 塑形工具选中对象的全部锚点（画板逻辑坐标）。手柄为绝对坐标（锚点+偏移经
   * localToGlobal），null=该侧无柄；选中锚点所属项被全选时手柄不下发
   *（对齐 Scratch fullySelected 隐藏手柄语义）。
   */
  const reshapePts = ref<
    {
      x: number
      y: number
      handleIn: { x: number; y: number } | null
      handleOut: { x: number; y: number } | null
      selected: boolean
    }[] | null
  >(null)
  /** 选中对象的轮廓 path data（项目坐标，与 reshapePts 同生同灭，SVG overlay 描边高亮） */
  const reshapeOutline = ref<string[] | null>(null)
  /** 选中锚点中存在未曲线化的点（顶栏「曲线」按钮可用性） */
  const reshapeHasUncurved = ref(false)
  /** 选中锚点中存在带手柄的点（顶栏「折线」按钮可用性） */
  const reshapeHasPointed = ref(false)

  // ─── 文字编辑 overlay（引擎写入，PaintArtboard 定位 textarea）───
  /**
   * 活跃文字编辑会话（textarea 覆盖层状态）；null=未在编辑。
   * 矢量模式对应 paper.PointText 编辑；位图模式为一次性输入（结束即栅格化）。
   * 定位：vector 用 matrix（对齐 PointText 变换，含旋转/缩放）；
   * bitmap 用 x/y 绝对定位（画板逻辑坐标，无旋转）。
   */
  const textEdit = ref<{
    /** 矢量：完整 CSS matrix（画板坐标系，含 PointText 自身变换）；位图 null */
    matrix: string | null
    /** matrix 模式下 transform-origin（相对 textarea 左上，px） */
    transformOrigin: string
    /** 位图：画板逻辑坐标（文字框左上） */
    x: number
    y: number
    fontSize: number
    /** 行高比（leading/fontSize） */
    lineHeight: number
    color: string
    value: string
    /** 内容框尺寸（画板逻辑坐标，动态贴合文字；空文字≈一个光标位） */
    width: number
    height: number
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

  /** 取色前的工具（取色结束回退；null=非工具栏触发的取色会话） */
  const toolBeforePick = ref<PaintTool | null>(null)

  function setTool(tool: PaintTool) {
    // 取色工具：进入拾色会话（画板放大镜+准心），记录来源工具供结束后回退
    if (tool === 'eyedropper') {
      if (activeTool.value !== 'eyedropper') toolBeforePick.value = activeTool.value
      eyedropperTarget.value = 'fill'
      eyedropperActive.value = true
    } else if (activeTool.value === 'eyedropper') {
      // 切到其它工具 = 手动取消取色
      toolBeforePick.value = null
      eyedropperActive.value = false
    }
    activeTool.value = tool
  }

  /** 取色完成/取消：结束会话；工具栏取色回退到取色前的工具（面板吸管不动工具） */
  function endEyedropper() {
    eyedropperActive.value = false
    if (activeTool.value === 'eyedropper') {
      activeTool.value = toolBeforePick.value ?? 'select'
    }
    toolBeforePick.value = null
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
    mode.value = 'vector'
    fillColor.value = '#9A66FF'
    strokeColor.value = '#2d2d2d'
    fillEnabled.value = true
    strokeEnabled.value = false
    selectionHasStroke.value = false
    selectionHasBodyStroke.value = false
    selectionBodyOnly.value = false
    strokeToggleTick.value = 0
    eyedropperActive.value = false
    eyedropperTarget.value = 'fill'
    toolBeforePick.value = null
    strokeWidth.value = 0
    lineWidth.value = 8
    brushSize.value = 12
    opacity.value = 100
    colorEditing.value = false
    artboardWidth.value = DEFAULT_ARTBOARD.w
    artboardHeight.value = DEFAULT_ARTBOARD.h
    zoom.value = 1
    panX.value = 0
    panY.value = 0
    cursorPos.value = null
    canUndo.value = false
    canRedo.value = false
    dirty.value = false
    sizeForced.value = false
    vectorCanUndo.value = false
    vectorCanRedo.value = false
    vectorSelectedCount.value = 0
    vectorCanUngroup.value = false
    hasVectorClipboard.value = false
    vectorContent.value = false
    vectorSelBox.value = null
    reshapePts.value = null
    reshapeOutline.value = null
    reshapeHasUncurved.value = false
    reshapeHasPointed.value = false
    selection.value = null
    floatActive.value = false
    transformBox.value = null
    hasClipboard.value = false
    textEdit.value = null
    frames.value = [{ id: makeFrameId() }]
    activeFrameIndex.value = 0
  }

  return {
    activeTool,
    mode,
    fillColor,
    strokeColor,
    selectionHasStroke,
    selectionHasBodyStroke,
    selectionBodyOnly,
    strokeToggleTick,
    eyedropperActive,
    eyedropperTarget,
    fillEnabled,
    strokeEnabled,
    shapeStyle,
    strokeWidth,
    lineWidth,
    brushSize,
    opacity,
    colorEditing,
    artboardWidth,
    artboardHeight,
    zoom,
    panX,
    panY,
    cursorPos,
    canUndo,
    canRedo,
    dirty,
    vectorEnabled,
    sizeForced,
    vectorCanUndo,
    vectorCanRedo,
    vectorSelectedCount,
    vectorCanUngroup,
    hasVectorClipboard,
    vectorContent,
    vectorSelBox,
    reshapePts,
    reshapeOutline,
    reshapeHasUncurved,
    reshapeHasPointed,
    selection,
    floatActive,
    transformBox,
    hasClipboard,
    textEdit,
    frames,
    activeFrameIndex,
    selectFrame,
    makeFrameId,
    setTool,
    endEyedropper,
    setMode,
    setZoom,
    resetView,
    reset,
  }
})
