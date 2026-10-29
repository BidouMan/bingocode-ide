import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { MapTool, CollisionTool, ShapeTool } from './map'

/**
 * 地图编辑器会话状态：工具、显示开关、光标、形状编辑模式。
 * 与地图文档数据（layers/resources/tiles/images）分离，避免页面状态污染存档模型。
 */
export const useMapEditorStore = defineStore('mapEditor', () => {
  const showGrid = ref(true)
  // 智能吸附开关：开启时吸附像素/网格/图像边缘与中心；关闭后完全自由（无任何吸附）
  const smartSnap = ref(true)
  const currentTool = ref<MapTool>('select')
  const collisionTool = ref<CollisionTool>('move')
  const cursorX = ref<number | null>(null)
  const cursorY = ref<number | null>(null)
  const imageTool = ref<'select' | 'reshape' | 'brush' | 'eraser' | 'fill' | 'text' | 'line' | 'rect' | 'ellipse' | 'pen' | 'eyedropper'>('select')
  // 图片绘制模式：位图 / 矢量（默认矢量，与角色编辑器一致）
  const paintMode = ref<'bitmap' | 'vector'>('vector')
  // 形状层工具：默认鼠标选择；矩形/圆形/胶囊/自定义为绘制工具
  const shapeTool = ref<ShapeTool>('select')
  // 当前选中的形状创建类型（标签状态）：切换选择/增删锚点工具时保持常亮
  const shapeDrawTool = ref<'rect' | 'circle' | 'capsule' | 'polygon'>('rect')
  // 当前正在编辑的形状 id（属于当前形状层）；多选时它是「主选中」的那个
  const activeShapeId = ref<string | null>(null)
  // 当前选中的形状集合（Shift / Cmd / Ctrl 多选）；始终包含 activeShapeId
  const activeShapeIds = ref<string[]>([])
  // 像素浮动选区是否存在 / 选区剪贴板是否有内容（工具条按钮可用性）
  const hasPixelSelection = ref(false)
  const hasPaintClipboard = ref(false)
  // 场景标记：一次性放置模式 / 当前选中标记 / 临时显示被隐藏的标记
  const markerPlacing = ref(false)
  const selectedMarkerId = ref<string | null>(null)
  const showHiddenMarkers = ref(false)
  // 画布底部临时提示（如「自定义形状不能交叉」），几秒后自动消失
  const hintMessage = ref('')
  let hintTimer: ReturnType<typeof setTimeout> | null = null

  /** 显示一条临时提示：同一时间只保留最新一条 */
  function showHint(text: string, duration = 3000) {
    hintMessage.value = text
    if (hintTimer) clearTimeout(hintTimer)
    hintTimer = setTimeout(() => {
      hintMessage.value = ''
      hintTimer = null
    }, duration)
  }

  function setTool(tool: MapTool) {
    currentTool.value = tool
  }

  function toggleGrid() {
    showGrid.value = !showGrid.value
  }

  function toggleSmartSnap() {
    smartSnap.value = !smartSnap.value
  }

  function setCollisionTool(tool: CollisionTool) {
    collisionTool.value = tool
  }

  function setCursorPos(x: number | null, y: number | null) {
    cursorX.value = x
    cursorY.value = y
  }

  function setShapeTool(tool: ShapeTool) {
    shapeTool.value = tool
    // 形状按钮独立记忆：只有真正选择形状时才更新，选择/增删锚点不影响常亮状态
    if (tool === 'rect' || tool === 'circle' || tool === 'capsule' || tool === 'polygon') {
      shapeDrawTool.value = tool
    }
  }

  function setActiveShapeId(id: string | null) {
    activeShapeId.value = id
    activeShapeIds.value = id ? [id] : []
  }

  /** 点选形状：additive = 按住 Shift / Cmd / Ctrl，加入或移出当前多选 */
  function selectShape(id: string, additive = false) {
    if (!additive) {
      setActiveShapeId(id)
      return
    }
    const current = activeShapeIds.value
    if (current.includes(id)) {
      const next = current.filter(x => x !== id)
      activeShapeIds.value = next
      activeShapeId.value = next.length ? next[next.length - 1] : null
    } else {
      activeShapeIds.value = [...current, id]
      activeShapeId.value = id
    }
  }

  /** 直接设置多选集合（全选 / 清空用）；主选中取最后一个 */
  function setActiveShapeIds(ids: string[]) {
    const next = [...new Set(ids)]
    activeShapeIds.value = next
    activeShapeId.value = next.length ? next[next.length - 1] : null
  }

  /** 只切换「主选中」而不改变多选集合（画布里点中已选中的另一个形状时用，锚点会跟过去） */
  function setPrimaryShape(id: string) {
    if (!activeShapeIds.value.includes(id)) {
      setActiveShapeId(id)
      return
    }
    activeShapeId.value = id
  }

  function setImageTool(tool: 'select' | 'reshape' | 'brush' | 'eraser' | 'fill' | 'text' | 'line' | 'rect' | 'ellipse' | 'pen' | 'eyedropper') {
    imageTool.value = tool
  }

  function setPaintMode(mode: 'bitmap' | 'vector') {
    paintMode.value = mode
  }

  /** 工具栏「标记」：点一下直接进入放置状态（鼠标变为半透明标记），再点一下退出；Esc 也可取消 */
  function toggleMarkerPlacing() {
    markerPlacing.value = !markerPlacing.value
    // 进入放置时收起当前标记的操作胶囊，避免与新标记混淆
    if (markerPlacing.value) selectedMarkerId.value = null
  }
  function cancelMarkerPlacing() {
    markerPlacing.value = false
  }
  /** 选中标记：界面上表现为图钉高亮 + 右侧属性面板切换为标记检视器 */
  function setSelectedMarkerId(id: string | null) {
    selectedMarkerId.value = id
  }
  /** 临时显示被隐藏的标记（弱化显示），方便重新选中并把它们放出来 */
  function toggleShowHiddenMarkers() {
    showHiddenMarkers.value = !showHiddenMarkers.value
  }

  return {
    showGrid,
    smartSnap,
    currentTool,
    collisionTool,
    cursorX,
    cursorY,
    imageTool,
    paintMode,
    shapeTool,
    shapeDrawTool,
    activeShapeId,
    activeShapeIds,
    setActiveShapeIds,
    setPrimaryShape,
    selectShape,
    hasPixelSelection,
    hasPaintClipboard,
    markerPlacing,
    selectedMarkerId,
    showHiddenMarkers,
    hintMessage,
    showHint,
    setImageTool,
    setPaintMode,
    toggleMarkerPlacing,
    cancelMarkerPlacing,
    setSelectedMarkerId,
    toggleShowHiddenMarkers,
    setShapeTool,
    setActiveShapeId,
    setTool,
    toggleGrid,
    toggleSmartSnap,
    setCollisionTool,
    setCursorPos,
  }
})
