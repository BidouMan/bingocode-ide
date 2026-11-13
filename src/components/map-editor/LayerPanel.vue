<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { useMapStore } from '../../stores/map'
import { useProjectStore } from '../../stores/project'
import iconShow from '../../assets/icons/icon_show.svg'
import iconHide from '../../assets/icons/icon_hide.svg'
import iconAdd from '../../assets/icons/新建图块图层.svg'
import iconDelete from '../../assets/icons/icon--delete.svg'
import iconPaint from '../../assets/icons/创建绘制图层.svg'
import iconImageLayer from '../../assets/icons/图像图层.svg'
import iconLibrary from '../../assets/icons/图片库.svg'
import iconUpload from '../../assets/icons/上传本地图片资源.svg'
import iconCollisionType from '../../assets/icons/重置锚点.svg'

const props = defineProps<{
  disabled?: boolean
  /** 图块图层缩略图提供者（只渲染该图层自身，避免串层） */
  getLayerThumbnail?: (layerId: number) => string | null | Promise<string | null>
}>()

const emit = defineEmits<{
  paint: []
  /** 双击图像图层：进入绘制页再次编辑 */
  'edit-image': [layerId: number]
  'open-library': []
  'upload-image': []
}>()

const mapStore = useMapStore()
const projectStore = useProjectStore()

const editingLayerIndex = ref<number | null>(null)
const editingName = ref('')
const listRef = ref<HTMLDivElement>()

// 缩略图渲染：跟随场景渲染模式（图块/位图场景像素渲染，全矢量场景平滑）
const imageRenderingStyle = computed(() => {
  return mapStore.sceneRenderMode === 'pixelated' ? 'pixelated' : 'auto'
})

// 显示顺序：数组末尾是最上层，列表顶部也应是最上层
const displayLayers = computed(() => {
  return mapStore.mapData.layers
    .map((layer, index) => ({ layer, index }))
    .reverse()
})

// ====== 图片图层缩略图 ======
const thumbUrls = ref<Map<number, string>>(new Map())
const urlCache = new Map<string, string>()
/** 纯 ASCII 路径：这种路径下 asset 协议还能用；含中文的路径回退一定加载失败 */
const ASCII_PATH = /^[\x20-\x7E]*$/

async function resolveThumbUrl(path: string): Promise<string> {
  const cached = urlCache.get(path)
  if (cached !== undefined) return cached
  let url: string
  let cacheable = true
  if (path.startsWith('/maps/')) {
    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')
      url = await invoke<string>('read_image_as_data_url', { path: `${engineDir}${path}` })
    } catch {
      url = ''
    }
  } else if (path.startsWith('assets/')) {
    const fullPath = `${projectStore.root}/${path}`
    try {
      url = await invoke<string>('read_image_as_data_url', { path: fullPath })
    } catch {
      // 读盘失败：中文路径下 convertFileSrc 必然加载失败，只会显示成“？”
      // 失败结果不进缓存，下次刷新重新读盘——文件恢复后缩略图自己会回来
      url = ASCII_PATH.test(fullPath) ? convertFileSrc(fullPath) : ''
      cacheable = false
    }
  } else {
    try {
      url = await invoke<string>('read_image_as_data_url', { path })
    } catch {
      url = ASCII_PATH.test(path) ? convertFileSrc(path) : ''
      cacheable = false
    }
  }
  if (cacheable) urlCache.set(path, url)
  return url
}

async function refreshThumbs(onlyMissing = false, imagesOnly = false) {
  // 图片可能被内联绘制原地覆盖，清空 URL 缓存以拿到最新内容
  urlCache.clear()
  const next = new Map<number, string>()
  const prevThumbs = thumbUrls.value
  for (const layer of mapStore.mapData.layers) {
    const cached = prevThumbs.get(layer.id)
    // 仅补齐新增图层 / 只刷新图片图层时，已有图块缩略图继续复用，避免整张地图反复重绘
    if (cached && (onlyMissing || (imagesOnly && layer.type === 'drawing'))) {
      next.set(layer.id, cached)
      continue
    }
    if (layer.type === 'image' && layer.image?.imagePath) {
      next.set(layer.id, await resolveThumbUrl(layer.image.imagePath))
    } else if (!imagesOnly && layer.type === 'drawing' && props.getLayerThumbnail) {
      // 图块图层：只取该图层自身渲染结果；未绘制图块时为空（不显示占位图）
      const url = await props.getLayerThumbnail(layer.id)
      if (url) next.set(layer.id, url)
    }
  }
  thumbUrls.value = next
}

/** 只刷新当前图块图层的缩略图（绘制时高频调用，其他图层内容没变无需重算） */
async function refreshTileThumbs() {
  if (!props.getLayerThumbnail) return
  const active = mapStore.activeLayer
  if (!active || active.type !== 'drawing') return
  const url = await props.getLayerThumbnail(active.id)
  const next = new Map(thumbUrls.value)
  if (url) next.set(active.id, url)
  else next.delete(active.id)
  thumbUrls.value = next
}

/** 批量清理（删素材 / 清空集合 / 删分组）会同时改动多个图层：所有图块图层的缩略图都要重算 */
async function refreshAllTileThumbs() {
  if (!props.getLayerThumbnail) return
  const next = new Map(thumbUrls.value)
  for (const layer of mapStore.mapData.layers) {
    if (layer.type !== 'drawing') continue
    const url = await props.getLayerThumbnail(layer.id)
    if (url) next.set(layer.id, url)
    else next.delete(layer.id)
  }
  thumbUrls.value = next
}

/** 图片绘制中由 MapCanvas 推送当前图层缩略图：只更新这一条，避免全量读盘 */
function setLayerThumb(layerId: number, dataUrl: string) {
  if (!mapStore.mapData.layers.some(l => l.id === layerId)) return
  const next = new Map(thumbUrls.value)
  next.set(layerId, dataUrl)
  thumbUrls.value = next
}

// 图片内容变化只刷新图片图层缩略图：图块图层没变，不必按整张地图尺寸重画
watch(() => mapStore.imageRevision, () => refreshThumbs(false, true))
// 地图载入后 Pixi 渲染有延迟，稍后再补一次图块缩略图
let loadThumbTimer: ReturnType<typeof setTimeout> | null = null
watch(() => mapStore.mapLoadCount, () => {
  refreshThumbs()
  if (loadThumbTimer) clearTimeout(loadThumbTimer)
  loadThumbTimer = setTimeout(() => {
    loadThumbTimer = null
    refreshThumbs()
  }, 300)
})
// 图层增删后补齐缩略图：只算新增图层的，已有图层不用重画整张地图
watch(() => mapStore.mapData.layers.length, () => refreshThumbs(true))
// 图块绘制后等 Pixi 渲染完成再取该图层缩略图
let tileThumbTimer: ReturnType<typeof setTimeout> | null = null
watch(() => mapStore.tileRevision, () => {
  if (tileThumbTimer) clearTimeout(tileThumbTimer)
  tileThumbTimer = setTimeout(() => {
    tileThumbTimer = null
    refreshTileThumbs()
  }, 120)
})
// 删素材 / 清空集合 / 删分组会一次改动多个图层，刷新全部图块图层缩略图
let bulkThumbTimer: ReturnType<typeof setTimeout> | null = null
watch(() => mapStore.tileBulkRevision, () => {
  if (bulkThumbTimer) clearTimeout(bulkThumbTimer)
  bulkThumbTimer = setTimeout(() => {
    bulkThumbTimer = null
    refreshAllTileThumbs()
  }, 120)
})
onMounted(refreshThumbs)
onBeforeUnmount(() => {
  if (tileThumbTimer) clearTimeout(tileThumbTimer)
  if (loadThumbTimer) clearTimeout(loadThumbTimer)
  if (bulkThumbTimer) clearTimeout(bulkThumbTimer)
})

// ====== 选中 / 重命名 ======
function selectLayer(index: number) {
  if (mapStore.activeLayerIndex !== index) mapStore.setActiveLayer(index)
}

/** 双击图像图层行：进入绘制页编辑该图片（双击名称仍是重命名） */
function onRowDblClick(index: number) {
  const layer = mapStore.mapData.layers[index]
  if (!layer || layer.type !== 'image' || layer.locked) return
  selectLayer(index)
  emit('edit-image', layer.id)
}

function startRename(index: number) {
  editingLayerIndex.value = index
  editingName.value = mapStore.mapData.layers[index].name
  nextTick(() => {
    const input = document.querySelector('.layer-rename-input') as HTMLInputElement
    if (input) { input.focus(); input.select() }
  })
}

function confirmRename() {
  if (editingLayerIndex.value !== null && editingName.value.trim()) {
    mapStore.renameLayer(editingLayerIndex.value, editingName.value.trim())
  }
  editingLayerIndex.value = null
}

function cancelRename() {
  editingLayerIndex.value = null
}

// ====== 拖拽排序（Pointer Events + 浮动幽灵 + 空隙让位） ======
/** 拖拽中的显示层索引（-1 = 未拖拽），模板用它隐藏原行占位 */
const dragging = ref(false)
const dragFromDisplay = ref(-1)
const dragTargetDisplay = ref(-1)

interface DragRow { el: HTMLElement; top: number; height: number }

let dragStartY = 0
let dragStartX = 0
let grabOffsetY = 0
let dragModelIndex = -1
let draggingStarted = false
let lastPointerY = 0
/** 拖动开始时的行几何（内容坐标系，滚动后依旧有效） */
let baseRows: DragRow[] = []
/** 每行当前的让位位移（非响应式：拖拽中直接改行内联 transform，绕开 Vue 的样式 patch） */
let currentShifts: number[] = []
/** 拖拽期间列表可视区（拖拽中不会变，缓存后避免每帧读布局） */
let listViewTop = 0
let listViewBottom = 0
let ghostEl: HTMLElement | null = null
let ghostBaseTop = 0
/** 幽灵当前位移，用于判断落位是否需要动画 */
let ghostCurrentDy = 0
let autoScrollRaf = 0
let settleTimer: ReturnType<typeof setTimeout> | null = null
/** 松手后的落位收尾（等幽灵滑进空位再提交），下一次按下要立即冲刷掉，避免漏提交或幽灵残留 */
let pendingSettle: (() => void) | null = null
let dragPointerId: number | null = null

/** 直接给行写位移：不走响应式渲染，避免每次换位触发整列表重渲染 */
function setRowShift(dIdx: number, shift: number) {
  if (currentShifts[dIdx] === shift) return
  currentShifts[dIdx] = shift
  baseRows[dIdx].el.style.transform = shift ? `translateY(${shift}px)` : ''
}

function onRowPointerDown(e: PointerEvent, modelIndex: number) {
  if (e.button !== 0) return
  const target = e.target as HTMLElement
  if (target.closest('button,input,textarea')) return
  // 按下即选中（与主流图层/资源列表一致），拖拽过程中不会出现"选中了别的层"的错位感
  selectLayer(modelIndex)
  if (props.disabled || mapStore.mapData.layers.length < 2) return
  // 上一轮落位动画还没走完就再次按下：立即完成上一轮的提交
  flushSettle()
  dragModelIndex = modelIndex
  dragPointerId = e.pointerId
  dragStartY = e.clientY
  dragStartX = e.clientX
  lastPointerY = e.clientY
  draggingStarted = false
  window.addEventListener('pointermove', onWindowPointerMove, { passive: false })
  window.addEventListener('pointerup', onWindowPointerUp)
  window.addEventListener('pointercancel', onWindowPointerCancel)
  window.addEventListener('blur', onWindowBlur)
}

function onWindowPointerMove(e: PointerEvent) {
  if (dragModelIndex < 0) return
  // 拖动阶段统一阻止默认行为：避免拖到文本上变成选中文字、拖到图片上触发原生拖拽
  if (draggingStarted) e.preventDefault()
  if (!draggingStarted) {
    if (Math.abs(e.clientY - dragStartY) < 4 && Math.abs(e.clientX - dragStartX) < 4) return
    if (!startDrag()) return
  }
  lastPointerY = e.clientY
  updateGhost(e.clientY)
  updateDragTarget(e.clientY)
}

/** 开始拖拽：缓存行几何、创建跟随指针的幽灵行、给原行留空位 */
function startDrag(): boolean {
  const list = listRef.value
  if (!list) return false
  // 防御：清掉任何历史遗留的幽灵行，确保屏幕上永远只有一个拖拽浮层
  document.querySelectorAll('.layer-drag-ghost').forEach(el => el.remove())
  const rowEls = Array.from(list.querySelectorAll<HTMLElement>('.layer-item'))
  if (rowEls.length !== displayLayers.value.length) return false
  const fromDisplay = displayLayers.value.findIndex(it => it.index === dragModelIndex)
  if (fromDisplay < 0) return false

  const listRect = list.getBoundingClientRect()
  listViewTop = listRect.top
  listViewBottom = listRect.bottom
  baseRows = rowEls.map(el => {
    const rect = el.getBoundingClientRect()
    return { el, top: rect.top - listRect.top + list.scrollTop, height: rect.height }
  })
  // 清掉上一轮可能残留的位移，位移状态从 0 重新开始
  currentShifts = new Array(baseRows.length).fill(0)
  baseRows.forEach(row => { row.el.style.transform = '' })

  const rowRect = rowEls[fromDisplay].getBoundingClientRect()
  grabOffsetY = dragStartY - rowRect.top
  ghostBaseTop = rowRect.top

  const ghost = rowEls[fromDisplay].cloneNode(true) as HTMLElement
  ghost.classList.remove('layer-item-active')
  ghost.classList.add('layer-drag-ghost')
  // 原生 title 提示会跟着克隆体在拖拽中反复弹出，去掉
  ghost.removeAttribute('title')
  ghost.style.left = `${rowRect.left}px`
  ghost.style.top = `${rowRect.top}px`
  ghost.style.width = `${rowRect.width}px`
  ghost.style.height = `${rowRect.height}px`
  document.body.appendChild(ghost)
  ghostEl = ghost
  ghostCurrentDy = 0

  // 指针捕获：拖到窗口外松手也能收到 pointerup，不会卡在拖拽状态
  if (dragPointerId !== null) {
    try { rowEls[fromDisplay].setPointerCapture(dragPointerId) } catch { /* 忽略不支持捕获的环境 */ }
  }

  draggingStarted = true
  dragging.value = true
  dragFromDisplay.value = fromDisplay
  dragTargetDisplay.value = fromDisplay
  document.body.classList.add('layer-dragging-cursor')
  startAutoScroll()
  return true
}

/** 幽灵行跟随指针（竖直方向 1:1 跟手，无延迟无惯性） */
function updateGhost(pointerY: number) {
  if (!ghostEl) return
  ghostCurrentDy = pointerY - grabOffsetY - ghostBaseTop
  ghostEl.style.transform = `translate3d(0, ${ghostCurrentDy}px, 0)`
}

/** 用指针在"内容坐标系"里的位置算最终插入位置（滚动时也能正确落位） */
function updateDragTarget(pointerY: number) {
  const list = listRef.value
  if (!list || baseRows.length === 0) return
  const contentY = pointerY - listViewTop + list.scrollTop
  let target = 0
  for (let i = 0; i < baseRows.length; i++) {
    if (i === dragFromDisplay.value) continue
    const row = baseRows[i]
    if (contentY > row.top + row.height / 2) target++
  }
  if (target === dragTargetDisplay.value) return
  dragTargetDisplay.value = target
  // 被让位的行整体平移一格，形成平滑滑动的空位（位移由 CSS transition 补间）
  const h = baseRows[dragFromDisplay.value]?.height ?? 54
  for (let i = 0; i < baseRows.length; i++) {
    let shift = 0
    if (dragFromDisplay.value < target && i > dragFromDisplay.value && i <= target) shift = -h
    else if (dragFromDisplay.value > target && i >= target && i < dragFromDisplay.value) shift = h
    setRowShift(i, shift)
  }
}

// ====== 拖到列表上下边缘时自动滚动 ======
function startAutoScroll() {
  stopAutoScroll()
  const step = () => {
    autoScrollRaf = requestAnimationFrame(step)
    const list = listRef.value
    if (!list) return
    const scrollBefore = list.scrollTop
    const edge = 28
    let dy = 0
    if (lastPointerY < listViewTop + edge) {
      dy = -Math.min(14, (listViewTop + edge - lastPointerY) * 0.6)
    } else if (lastPointerY > listViewBottom - edge) {
      dy = Math.min(14, (lastPointerY - (listViewBottom - edge)) * 0.6)
    }
    if (dy) list.scrollTop += dy
    // 滚轮 / 自动滚动都会改 scrollTop：内容坐标变了，落位要跟着重算
    if (list.scrollTop !== scrollBefore) updateDragTarget(lastPointerY)
  }
  autoScrollRaf = requestAnimationFrame(step)
}

function stopAutoScroll() {
  if (autoScrollRaf) cancelAnimationFrame(autoScrollRaf)
  autoScrollRaf = 0
}

function removeWindowListeners() {
  window.removeEventListener('pointermove', onWindowPointerMove)
  window.removeEventListener('pointerup', onWindowPointerUp)
  window.removeEventListener('pointercancel', onWindowPointerCancel)
  window.removeEventListener('blur', onWindowBlur)
}

function onWindowPointerUp() {
  removeWindowListeners()
  if (!draggingStarted) {
    resetDragState()
    return
  }
  settleDrag()
}

function onWindowPointerCancel() {
  removeWindowListeners()
  if (!draggingStarted) {
    resetDragState()
    return
  }
  cancelDrag()
}

function onWindowBlur() {
  removeWindowListeners()
  if (draggingStarted) cancelDrag()
  else resetDragState()
}

/** 松手：幽灵滑到空位后提交顺序（视觉上原行正好出现在幽灵落点，无跳动） */
function settleDrag() {
  stopAutoScroll()
  releasePointerCapture()
  const list = listRef.value
  const target = dragTargetDisplay.value
  const ghost = ghostEl
  const canCommit = !!list && target >= 0 && ghost
  let hasMotion = false
  if (ghost && canCommit) {
    const listRect = list!.getBoundingClientRect()
    const gapTop = listRect.top - list!.scrollTop + (baseRows[target]?.top ?? 0)
    const targetDy = gapTop - ghostBaseTop
    hasMotion = Math.abs(targetDy - ghostCurrentDy) > 0.5
    if (hasMotion) {
      ghost.style.transition = 'transform 0.14s cubic-bezier(0.2, 0, 0, 1)'
      ghost.style.transform = `translate3d(0, ${targetDy}px, 0)`
      ghostCurrentDy = targetDy
    }
  }
  const modelFrom = dragModelIndex
  const count = mapStore.mapData.layers.length
  discardSettle()
  pendingSettle = () => {
    if (ghost) ghost.remove()
    ghostEl = null
    if (canCommit && modelFrom >= 0) commitReorder(modelFrom, count - 1 - target)
    finishDragState()
  }
  if (ghost && hasMotion) {
    // 幽灵滑到空位（transform 补间结束）再提交，避免提前移除造成落点前一小段跳动
    ghost.addEventListener('transitionend', (ev) => {
      if ((ev as TransitionEvent).propertyName === 'transform') flushSettle()
    }, { once: true })
  }
  settleTimer = setTimeout(flushSettle, ghost && hasMotion ? 320 : 0)
}

function commitReorder(fromModel: number, toModel: number) {
  const list = listRef.value
  if (!list) return
  const rows = baseRows
  // 位移完全走行内联样式（模板不再绑定 :style），Vue 的 class/style patch 碰不到它：
  // 1) 给每行内联关过渡，2) 同步清掉让位位移，3) 强制一次样式计算。
  // 这样"清位移"确定发生在无过渡状态，不会留下任何补间，落点零动画。
  for (const row of rows) {
    row.el.style.transition = 'none'
    row.el.style.transform = ''
  }
  currentShifts = new Array(rows.length).fill(0)
  void list.offsetHeight
  // 提交真实顺序：Vue 只移动 DOM 节点，不再改 transform
  if (fromModel !== toModel) mapStore.moveLayerTo(fromModel, toModel)
  nextTick(() => {
    // 换位后的布局已在"无过渡"下完成一次样式计算，此时恢复过渡不会触发补间
    const el = listRef.value
    if (el) void el.offsetHeight
    for (const row of rows) row.el.style.transition = ''
  })
}

/** 取消（Esc / 窗口失焦 / 触摸被打断）：幽灵归位，行动画复原 */
function cancelDrag() {
  stopAutoScroll()
  releasePointerCapture()
  // 让位行恢复原位：CSS 过渡会把它们平滑滑回去
  for (let i = 0; i < baseRows.length; i++) setRowShift(i, 0)
  const list = listRef.value
  const ghost = ghostEl
  let hasMotion = false
  if (ghost && list) {
    const listRect = list.getBoundingClientRect()
    const originTop = listRect.top - list.scrollTop + (baseRows[dragFromDisplay.value]?.top ?? 0)
    const originDy = originTop - ghostBaseTop
    hasMotion = Math.abs(originDy - ghostCurrentDy) > 0.5
    if (hasMotion) {
      ghost.style.transition = 'transform 0.14s cubic-bezier(0.2, 0, 0, 1), opacity 0.14s ease'
      ghost.style.transform = `translate3d(0, ${originDy}px, 0)`
      ghost.style.opacity = '0'
    }
  }
  discardSettle()
  pendingSettle = () => {
    ghost?.remove()
    ghostEl = null
    finishDragState()
  }
  settleTimer = setTimeout(flushSettle, ghost && hasMotion ? 320 : 0)
}

function finishDragState() {
  draggingStarted = false
  dragging.value = false
  dragFromDisplay.value = -1
  dragTargetDisplay.value = -1
  currentShifts = []
  dragModelIndex = -1
  dragPointerId = null
  baseRows = []
  document.body.classList.remove('layer-dragging-cursor')
}

function resetDragState() {
  discardSettle()
  stopAutoScroll()
  ghostEl?.remove()
  ghostEl = null
  finishDragState()
}

/** 立即执行待提交的落位收尾（不丢上一次排序结果） */
function flushSettle() {
  if (settleTimer) {
    clearTimeout(settleTimer)
    settleTimer = null
  }
  const fn = pendingSettle
  pendingSettle = null
  fn?.()
}

/** 丢弃落位收尾（组件卸载等场景，不再提交） */
function discardSettle() {
  if (settleTimer) {
    clearTimeout(settleTimer)
    settleTimer = null
  }
  pendingSettle = null
}

function releasePointerCapture() {
  const list = listRef.value
  if (dragPointerId === null || !list) return
  const rowEls = list.querySelectorAll<HTMLElement>('.layer-item')
  rowEls.forEach(el => {
    try {
      if (el.hasPointerCapture?.(dragPointerId!)) el.releasePointerCapture(dragPointerId!)
    } catch { /* 忽略 */ }
  })
}

/** Esc 取消拖拽 */
function onDragKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape' && draggingStarted) {
    e.preventDefault()
    removeWindowListeners()
    cancelDrag()
  }
}

onMounted(() => window.addEventListener('keydown', onDragKeyDown))
onBeforeUnmount(() => {
  removeWindowListeners()
  window.removeEventListener('keydown', onDragKeyDown)
  discardSettle()
  stopAutoScroll()
  ghostEl?.remove()
  ghostEl = null
  document.body.classList.remove('layer-dragging-cursor')
})

defineExpose({ setLayerThumb })
</script>

<template>
  <div class="layer-panel">
    <div class="layer-toolbar">
      <!-- 工具栏固定不变：图像相关入口在图块模式下仍保留，点击后新建图片图层 -->
      <button class="layer-tool-btn" v-tooltip="'绘制图像'" :disabled="disabled" @click="emit('paint')">
        <img :src="iconPaint" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" v-tooltip="'打开内置资源'" :disabled="disabled" @click="emit('open-library')">
        <img :src="iconLibrary" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" v-tooltip="'新建图块图层'" :disabled="disabled" @click="mapStore.addLayer('图块图层')">
        <img :src="iconAdd" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" v-tooltip="'新建形状图层'" :disabled="disabled" @click="mapStore.addShapeLayer()">
        <img :src="iconCollisionType" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" v-tooltip="'本地上传'" :disabled="disabled" @click="emit('upload-image')">
        <img :src="iconUpload" class="layer-tool-icon" />
      </button>
      <button class="layer-tool-btn" v-tooltip="'删除图层'" :disabled="disabled || mapStore.activeLayerIndex < 0" @click="mapStore.removeLayer(mapStore.activeLayerIndex)">
        <img :src="iconDelete" class="layer-tool-icon" />
      </button>
    </div>

    <div ref="listRef" class="layer-list" :class="{ 'is-dragging': dragging }">
      <div
        v-for="(item, dIdx) in displayLayers"
        :key="item.layer.id"
        class="layer-item"
        :class="{
          'layer-item-active': mapStore.activeLayerIndex === item.index,
          'layer-item-placeholder': dragging && dragFromDisplay === dIdx,
        }"
        @pointerdown="onRowPointerDown($event, item.index)"
        @dblclick="onRowDblClick(item.index)"
        :title="item.layer.type === 'image' ? '双击进入绘制页编辑这张图片（双击名称可重命名）' : ''"
      >
        <div class="layer-thumb">
          <img
            v-if="thumbUrls.get(item.layer.id)"
            :src="thumbUrls.get(item.layer.id)"
            class="layer-thumb-img"
            :style="{ imageRendering: imageRenderingStyle }"
            draggable="false"
          />
        </div>

        <!-- 图层类型图标：绘制层=绘制图像按钮图标；上传/内置图片=图像图层图标；图块/形状=对应按钮图标 -->
        <img
          :src="item.layer.type === 'image'
            ? (item.layer.image?.background ? iconPaint : iconImageLayer)
            : item.layer.type === 'shape' ? iconCollisionType : iconAdd"
          class="layer-type-icon"
          draggable="false"
        />

        <template v-if="editingLayerIndex === item.index">
          <input
            class="layer-rename-input"
            v-model="editingName"
            @blur="confirmRename"
            @keydown.enter.prevent="confirmRename"
            @keydown.escape="cancelRename"
            @click.stop
            @mousedown.stop
          />
        </template>
        <template v-else>
          <span class="layer-name" @dblclick.stop="startRename(item.index)">
            {{ item.layer.name }}
          </span>
        </template>

        <button
          class="layer-vis-btn"
          v-tooltip="item.layer.visible ? '隐藏' : '显示'"
          @click.stop="mapStore.toggleLayerVisibility(item.index)"
        >
          <img :src="item.layer.visible ? iconShow : iconHide" class="vis-icon" />
        </button>
      </div>

      <div v-if="displayLayers.length === 0" class="layer-empty">暂无图层</div>
    </div>

    <div class="layer-info-bar">
      <span class="layer-info-text">图层管理</span>
    </div>
  </div>
</template>

<style scoped>
.layer-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: var(--bg-root);
}

.layer-toolbar {
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 8px;
  gap: 4px;
  flex-shrink: 0;
  border-bottom: 1px solid rgb(45, 45, 45);
}

.layer-tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  height: 28px;
  background: rgb(40, 43, 52);
  border: none;
  border-radius: 4px;
  cursor: default;
  padding: 2px;
  transition: background 0.15s;
}

.layer-tool-btn:hover {
  background: var(--bg-hover);
}

.layer-tool-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.layer-tool-icon {
  height: 20px;
}

.layer-list {
  flex: 1;
  overflow-y: auto;
  margin: 0 8px;
  padding: 2px 0;
  background: rgb(30, 30, 30);
}

.layer-item {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 54px;
  padding: 0 6px;
  border-radius: 4px;
  cursor: default;
  /* 让位位移的补间：短、阻尼感强，接近原生列表的手感 */
  transition: background 0.12s, transform 0.15s cubic-bezier(0.2, 0, 0, 1);
  position: relative;
}

/* 悬停只作用于未选中的行；选中行本身就是高亮态，不再叠加第二层底色 */
.layer-item:hover {
  background: rgb(40, 43, 52);
}

.layer-item-active,
.layer-item-active:hover {
  background: rgb(60, 65, 75);
}

/* 拖拽中：原行隐形留位，其他行不响应悬停高亮 */
.layer-item-placeholder {
  opacity: 0;
  pointer-events: none;
}

.layer-list.is-dragging .layer-item {
  will-change: transform;
}

.layer-list.is-dragging .layer-item:hover {
  background: transparent;
}

.layer-list.is-dragging .layer-item-active,
.layer-list.is-dragging .layer-item-active:hover {
  background: rgb(60, 65, 75);
}

/* 跟随指针的幽灵行（克隆自行本身，保留缩略图与图标） */
.layer-drag-ghost {
  position: fixed;
  margin: 0;
  border: none;
  z-index: 9999;
  box-sizing: border-box;
  background: rgb(52, 56, 66);
  border-radius: 4px;
  pointer-events: none;
  opacity: 0.97;
  /* 关键：跟手阶段绝不能有过渡，否则幽灵会拖尾 */
  transition: none;
  /* 阴影用负扩散 + 内描边：卡片视觉尺寸严格等于行本身，不会溢出左右面板边框 */
  box-shadow: 0 6px 12px -6px rgba(0, 0, 0, 0.65), inset 0 0 0 1px rgba(255, 255, 255, 0.06);
}

:global(body.layer-dragging-cursor) {
  cursor: grabbing !important;
  user-select: none;
}

:global(body.layer-dragging-cursor *) {
  cursor: grabbing !important;
}

.layer-thumb {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  background: rgb(50, 53, 62);
  border-radius: 5px;
  overflow: hidden;
}

.layer-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}

/* 图层类型图标（与对应创建按钮图标一致） */
.layer-type-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  opacity: 0.85;
  pointer-events: none;
}

.layer-name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: rgb(196, 200, 206);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  user-select: none;
}

.layer-rename-input {
  flex: 1;
  min-width: 0;
  height: 22px;
  background: rgb(40, 43, 52);
  border: 1px solid var(--border-light);
  border-radius: 3px;
  color: #fff;
  font-size: 12px;
  padding: 0 4px;
  outline: none;
}

.layer-vis-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 3px;
  cursor: default;
  font-size: 12px;
  line-height: 1;
}

.layer-vis-btn:hover {
  background: rgb(70, 74, 84);
}

.vis-icon {
  width: 16px;
  height: 16px;
  opacity: 0.85;
}

.layer-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 80px;
  color: rgb(80, 80, 80);
  font-size: 12px;
}

.layer-info-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 30px;
  /* 比面板更深一档 + 一条细分隔线，保证是独立的一条信息栏 */
  background: rgb(26, 28, 33);
  border-top: 1px solid rgba(255, 255, 255, 0.07);
  flex-shrink: 0;
}

.layer-info-text {
  font-size: 12px;
  color: rgb(156, 160, 164);
}
</style>
