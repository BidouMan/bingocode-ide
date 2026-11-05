<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import {
  useMapStore,
  tilePaletteEntryKey,
  type MapResource,
  type TilePaletteEntry,
} from '../../stores/map'
import { useProjectStore } from '../../stores/project'
import { useEditorStore } from '../../stores/editor'
import { useTileAssetImport } from '../../composables/useTileAssetImport'
import CustomSelect from '../common/CustomSelect.vue'
import iconLibrary from '../../assets/icons/图片库.svg'
import iconUpload from '../../assets/icons/上传本地图片资源.svg'
import iconDelete from '../../assets/icons/icon--delete.svg'
import iconCopy from '../../assets/icons/copy.svg'
import iconReset from '../../assets/icons/重置.svg'
import iconChevron from '../../assets/icons/right_arrow.svg'
import iconClickSelect from '../../assets/icons/选择箭头.svg'
import iconMove from '../../assets/icons/移动工具.svg'
import iconRandom from '../../assets/icons/随机.svg'
import iconZoomIn from '../../assets/icons/add-one.svg'
import iconZoomOut from '../../assets/icons/reduce-one.svg'
import iconFocus from '../../assets/icons/聚焦.svg'
import iconFlipH from '../../assets/icons/水平翻转.svg'
import iconFlipV from '../../assets/icons/垂直翻转.svg'
import iconCollisionOn from '../../assets/icons/重置锚点.svg'
import iconCollisionOff from '../../assets/icons/hitbox.svg'

/**
 * 图块模式专用：画布下方的图块笔刷面板。
 * 每个图块都是独立“笔刷”，按调色板顺序从左到右、从上到下排列；
 * 支持拖拽重排、单独移除；本地上传的文件全部按图块素材（图块集）处理。
 */
const props = defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  'open-library': []
  'select-tile': [
    resourceIndex: number,
    tileIndex: number,
    entry?: { key: string; flipH: boolean; flipV: boolean },
  ]
}>()

const mapStore = useMapStore()
const projectStore = useProjectStore()
const editorStore = useEditorStore()
const { importTileImage, refitTilesetsToGrid } = useTileAssetImport()
const collapsed = ref(false)

// ====== Unity 风格无限网格画布：图块按 16 列排布，可自由平移 / 缩放 ======
const PALETTE_CELL = 40
const PALETTE_COLS = 16
const PALETTE_MIN_ZOOM = 0.5
const PALETTE_MAX_ZOOM = 2.5
const viewportRef = ref<HTMLDivElement>()
const panX = ref(0)
const panY = ref(0)
const zoom = ref(1)
let panning = false
let panStartX = 0
let panStartY = 0
let panStartPanX = 0
let panStartPanY = 0

const palettePlaneStyle = computed(() => ({
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`,
}))

/** 网格层：独立画布，按设备像素对齐描 1px 线，不参与图块的缩放/渲染 */
const gridCanvasRef = ref<HTMLCanvasElement>()
let gridFrame = 0
let gridObserver: ResizeObserver | null = null

function drawPaletteGrid() {
  const canvas = gridCanvasRef.value
  const vp = viewportRef.value
  if (!canvas || !vp) return
  const w = vp.clientWidth
  const h = vp.clientHeight
  if (w <= 0 || h <= 0) return

  const dpr = window.devicePixelRatio || 1
  const bw = Math.round(w * dpr)
  const bh = Math.round(h * dpr)
  if (canvas.width !== bw || canvas.height !== bh) {
    canvas.width = bw
    canvas.height = bh
  }

  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.setTransform(1, 0, 0, 1, 0, 0)
  ctx.clearRect(0, 0, bw, bh)

  const size = PALETTE_CELL * zoom.value
  if (size <= 0.5) return

  // 线宽固定 1 个 CSS 像素（按设备像素取整），任何缩放下都不会变粗或发虚
  const lineWidth = Math.max(1, Math.round(dpr))
  ctx.fillStyle = 'rgba(255, 255, 255, 0.07)'

  let startX = panX.value % size
  if (startX < 0) startX += size
  for (let x = startX; x < w; x += size) {
    ctx.fillRect(Math.round(x * dpr), 0, lineWidth, bh)
  }
  let startY = panY.value % size
  if (startY < 0) startY += size
  for (let y = startY; y < h; y += size) {
    ctx.fillRect(0, Math.round(y * dpr), bw, lineWidth)
  }
}

function scheduleGridDraw() {
  if (gridFrame) return
  gridFrame = requestAnimationFrame(() => {
    gridFrame = 0
    drawPaletteGrid()
  })
}

watch([panX, panY, zoom], scheduleGridDraw)

const paletteHovered = ref(false)

// ====== 工具栏工具：选择 / 移动（单选组，始终有一个处于激活状态） ======
/** 默认激活选择工具：打开图块层先能选，不用额外点一下 */
type PaletteTool = 'select' | 'move'
const paletteTool = ref<PaletteTool>('select')
const paletteSelectMode = computed(() => paletteTool.value === 'select')
const paletteMoveMode = computed(() => paletteTool.value === 'move')

// ====== 选择工具：普通点选 + 从选中块拖动框选（Godot 风格） ======
const paletteSelection = reactive(new Set<string>())
const paletteBoxRect = ref<{ x: number; y: number; w: number; h: number } | null>(null)
let boxAnchorCol = 0
let boxAnchorRow = 0
let boxDragged = false
/** 本次框选是否按住 Shift 追加（不清空原选择） */
let boxAdditive = false
let boxRange = { minCol: 0, maxCol: 0, minRow: 0, maxRow: 0 }
let boxAnchorEntry: PaletteLayoutItem | null = null

/** 调色板条目唯一键：复制出来的同图块副本靠它区分 */
function paletteEntryKeyOf(item: PaletteItem) {
  const entry = paletteEntries.value[item.paletteIndex]
  return entry ? tilePaletteEntryKey(entry) : `${item.resource.id}:${item.tileIndex}`
}

/** 切换工具：两个工具互斥，点哪个就一直是哪个 */
function setPaletteTool(tool: PaletteTool) {
  paletteTool.value = tool
}

/** 视口内的屏幕坐标 → 图块平面坐标（平移 / 缩放逆变换） */
function viewportPointToLocal(x: number, y: number) {
  return {
    x: (x - panX.value) / zoom.value,
    y: (y - panY.value) / zoom.value,
  }
}

/** 平面坐标 → 视口内的屏幕坐标 */
function localPointToViewport(x: number, y: number) {
  return {
    x: x * zoom.value + panX.value,
    y: y * zoom.value + panY.value,
  }
}

/** 图块左上角换算成整张网格的列 / 行 */
function tileGlobalCol(entry: PaletteLayoutItem) {
  return Math.floor(entry.left / PALETTE_CELL)
}
function tileGlobalRow(entry: PaletteLayoutItem) {
  return Math.floor(entry.top / PALETTE_CELL)
}

/** 框选矩形按整格吸附：只覆盖被选中的格子，不会碰巧带上边上的图块 */
function updateBoxOverlayFromRange() {
  const x = boxRange.minCol * PALETTE_CELL
  const y = boxRange.minRow * PALETTE_CELL
  const w = (boxRange.maxCol - boxRange.minCol + 1) * PALETTE_CELL
  const h = (boxRange.maxRow - boxRange.minRow + 1) * PALETTE_CELL
  const p = localPointToViewport(x, y)
  paletteBoxRect.value = {
    x: p.x,
    y: p.y,
    w: w * zoom.value,
    h: h * zoom.value,
  }
}

function onPaletteBoxMove(e: PointerEvent) {
  const vp = viewportRef.value
  if (!vp) return
  const rect = vp.getBoundingClientRect()
  const local = viewportPointToLocal(e.clientX - rect.left, e.clientY - rect.top)
  const endCol = Math.floor(local.x / PALETTE_CELL)
  const endRow = Math.floor(local.y / PALETTE_CELL)
  boxRange = {
    minCol: Math.min(boxAnchorCol, endCol),
    maxCol: Math.max(boxAnchorCol, endCol),
    minRow: Math.min(boxAnchorRow, endRow),
    maxRow: Math.max(boxAnchorRow, endRow),
  }
  boxDragged = endCol !== boxAnchorCol || endRow !== boxAnchorRow
  // 只有真的拖到别的格子才显示框选矩形
  if (boxDragged) updateBoxOverlayFromRange()
  else paletteBoxRect.value = null
}

function onPaletteBoxEnd() {
  window.removeEventListener('pointermove', onPaletteBoxMove)
  window.removeEventListener('pointerup', onPaletteBoxEnd)
  paletteBoxRect.value = null

  // Shift 加选：保留原有选择；否则本次重新选择
  if (!boxAdditive) paletteSelection.clear()

  if (!boxDragged) {
    // 没有跨格：只处理起点那一块，并把它设为当前画笔
    if (boxAnchorEntry) {
      const key = paletteEntryKeyOf(boxAnchorEntry.item)
      // Shift 点已选中的格子：取消它（加选的常规手感）
      if (boxAdditive && paletteSelection.has(key)) {
        paletteSelection.delete(key)
        // 取消后画笔交给剩下最后一块，没有剩余就保持不动
        const fallback = [...paletteLayout.value.items].reverse().find(entry =>
          paletteSelection.has(paletteEntryKeyOf(entry.item))
        )
        if (fallback) emitSelectItem(fallback.item)
      } else {
        paletteSelection.add(key)
        emitSelectItem(boxAnchorEntry.item)
      }
    }
    boxAnchorEntry = null
    return
  }

  // 严格按格子范围选择：只把落在框内格子里的图块算进来
  let lastHit: PaletteLayoutItem | null = null
  for (const entry of paletteLayout.value.items) {
    const col = tileGlobalCol(entry)
    const row = tileGlobalRow(entry)
    if (
      col >= boxRange.minCol && col <= boxRange.maxCol
      && row >= boxRange.minRow && row <= boxRange.maxRow
    ) {
      paletteSelection.add(paletteEntryKeyOf(entry.item))
      lastHit = entry
    }
  }

  // 多选后当前画笔始终取最后一个：碰撞预览显示的就是它
  if (lastHit) emitSelectItem(lastHit.item)
  boxAnchorEntry = null
}

function paletteCellBackground(item: PaletteItem): Record<string, string> {
  return item.thumb
    ? {
        backgroundImage: `url(${item.thumb})`,
        backgroundSize: 'contain',
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'center',
        imageRendering: 'pixelated',
      }
    : {}
}

/** 图块自身朝向：调色板里直接按翻转后的样子显示（所见即所得） */
function paletteCellTransform(item: PaletteItem): Record<string, string> {
  if (!item.flipH && !item.flipV) return {}
  return { transform: `scale(${item.flipH ? -1 : 1}, ${item.flipV ? -1 : 1})` }
}

/** 图块图像的完整样式：缩略图 + 朝向 */
function paletteCellStyle(item: PaletteItem): Record<string, string> {
  return { ...paletteCellBackground(item), ...paletteCellTransform(item) }
}

/** 把某块图块设为当前画笔（带上它自己的朝向与条目键） */
function emitSelectItem(item: PaletteItem) {
  emit('select-tile', item.resourceIndex, item.tileIndex, {
    key: paletteEntryKeyOf(item),
    flipH: item.flipH,
    flipV: item.flipV,
  })
}

/** 这块图块是不是当前画笔（同图块有副本时按条目键精确匹配） */
function isCurrentBrush(item: PaletteItem) {
  if (item.resourceIndex !== mapStore.selectedResourceIndex) return false
  if (item.tileIndex !== mapStore.selectedTileIndex) return false
  const key = mapStore.selectedTileEntryKey
  return key ? key === paletteEntryKeyOf(item) : true
}

/** 屏幕坐标命中的图块（考虑平移 / 缩放） */
function paletteHitAt(clientX: number, clientY: number): PaletteLayoutItem | null {
  const vp = viewportRef.value
  if (!vp) return null
  const rect = vp.getBoundingClientRect()
  const local = viewportPointToLocal(clientX - rect.left, clientY - rect.top)
  return paletteLayout.value.items.find(entry =>
    local.x >= entry.left && local.x <= entry.left + PALETTE_CELL
    && local.y >= entry.top && local.y <= entry.top + PALETTE_CELL
  ) ?? null
}

function onPalettePointerDown(e: PointerEvent) {
  const isMiddle = e.button === 1
  if (!isMiddle && e.button !== 0) return
  if (isMiddle) e.preventDefault()

  const target = e.target as HTMLElement | null

  // 选择工具：点在图块上就以这块为起点，拖动框选；中键仍然平移画布
  if (!isMiddle && paletteSelectMode.value) {
    if (target?.closest('.tile-cell')) {
      e.preventDefault()
      const hit = paletteHitAt(e.clientX, e.clientY)
      if (!hit) return
      boxAnchorEntry = hit
      boxAnchorCol = tileGlobalCol(hit)
      boxAnchorRow = tileGlobalRow(hit)
      boxDragged = false
      // 按住 Shift 表示在现有选择上追加
      boxAdditive = e.shiftKey
      boxRange = {
        minCol: boxAnchorCol,
        maxCol: boxAnchorCol,
        minRow: boxAnchorRow,
        maxRow: boxAnchorRow,
      }
      // 还没跨格时不画框：否则点一下会闪出一个绿色框，和 hover 叠在一起
      paletteBoxRect.value = null
      window.addEventListener('pointermove', onPaletteBoxMove)
      window.addEventListener('pointerup', onPaletteBoxEnd)
      return
    }
    // 点空白处只当作平移画布，保留现有选择（选中高亮不会被点没）
  }

  // 移动工具：按住图块拖到别的格子（空格移动，有图块则交换）
  if (!isMiddle && paletteMoveMode.value && target?.closest('.tile-cell')) {
    e.preventDefault()
    const hit = paletteHitAt(e.clientX, e.clientY)
    if (!hit) return
    beginPaletteMove(hit, e)
    window.addEventListener('pointermove', onPaletteMoveMove)
    window.addEventListener('pointerup', onPaletteMoveEnd)
    return
  }

  // 左键在空白网格上平移；中键在图块上也能直接平移画布
  if (!isMiddle && target?.closest('.tile-cell')) return
  panning = true
  panStartX = e.clientX
  panStartY = e.clientY
  panStartPanX = panX.value
  panStartPanY = panY.value
  window.addEventListener('pointermove', onPalettePointerMove)
  window.addEventListener('pointerup', onPalettePointerUp)
}

// ====== 移动工具：拖动图块（支持整组多选）到别的格子 ======
/** 拖动中的整组图块：本体淡出，影子固定在窗口层自由跟随鼠标（不会被面板裁掉） */
const moveDrag = ref<{
  items: { entry: PaletteLayoutItem; relCol: number; relRow: number }[]
  /** 被按住那块所在格子（限制整组不能拖到负坐标用） */
  anchorCol: number
  anchorRow: number
  startLocalX: number
  startLocalY: number
  pointerX: number
  pointerY: number
  /** 鼠标相对被按住图块左上角的偏移（屏幕像素） */
  grabOffsetX: number
  grabOffsetY: number
  /** 松手后落到的格子偏移 */
  dCol: number
  dRow: number
  moved: boolean
} | null>(null)

/** 拖动的图块影子：连续跟随鼠标，松手才吸附到格子 */
const moveGhost = computed(() => {
  const drag = moveDrag.value
  if (!drag || !drag.moved) return []
  const size = PALETTE_CELL * zoom.value
  return drag.items.map(({ entry, relCol, relRow }) => ({
    key: paletteEntryKeyOf(entry.item),
    item: entry.item,
    size,
    left: drag.pointerX - drag.grabOffsetX + relCol * size,
    top: drag.pointerY - drag.grabOffsetY + relRow * size,
  }))
})

/** 正在被拖走的图块：原位置淡出，视觉上就像被拿起来了 */
const draggingKeys = computed(() => new Set(moveGhost.value.map(g => g.key)))

/** 图块已记录的格子坐标（自动排列的图块还没有） */
function cellOfItem(item: PaletteItem) {
  const entry = paletteEntries.value[item.paletteIndex]
  return entry && entry.col != null && entry.row != null
    ? { col: entry.col, row: entry.row }
    : null
}

/** 拖动前先把当前自动排列固化成坐标，避免松手后其余图块重新排布 */
function materializePaletteCells() {
  const cells = paletteLayout.value.items
    .filter(entry => !cellOfItem(entry.item))
    .map(entry => ({
      key: paletteEntryKeyOf(entry.item),
      col: Math.floor(entry.left / PALETTE_CELL),
      row: Math.floor(entry.top / PALETTE_CELL),
    }))
  if (cells.length) mapStore.setPaletteCellsByKey(cells)
}

function beginPaletteMove(hit: PaletteLayoutItem, e: PointerEvent) {
  const vp = viewportRef.value
  if (!vp) return
  materializePaletteCells()

  // 拖的是已选中的图块 → 整组一起移动；否则只拖这一块
  const anchorKey = paletteEntryKeyOf(hit.item)
  let group: PaletteLayoutItem[]
  if (paletteSelection.has(anchorKey) && paletteSelection.size > 1) {
    group = paletteLayout.value.items.filter(entry =>
      paletteSelection.has(paletteEntryKeyOf(entry.item)),
    )
  } else {
    paletteSelection.clear()
    paletteSelection.add(anchorKey)
    group = [hit]
  }

  // 记录每块相对“被按住那块”的偏移，整组才能保持原有排布一起走
  const anchorCell = cellOfItem(hit.item) ?? { col: 0, row: 0 }
  const items = group.map(entry => {
    const cell = cellOfItem(entry.item) ?? anchorCell
    return {
      entry,
      relCol: cell.col - anchorCell.col,
      relRow: cell.row - anchorCell.row,
    }
  })

  const rect = vp.getBoundingClientRect()
  const local = viewportPointToLocal(e.clientX - rect.left, e.clientY - rect.top)
  const anchorLeft = anchorCell.col * PALETTE_CELL
  const anchorTop = anchorCell.row * PALETTE_CELL
  moveDrag.value = {
    items,
    anchorCol: anchorCell.col,
    anchorRow: anchorCell.row,
    startLocalX: local.x,
    startLocalY: local.y,
    pointerX: e.clientX,
    pointerY: e.clientY,
    // 抓取点：鼠标落在图块内的相对位置，拖起来不会“跳”
    grabOffsetX: e.clientX - (rect.left + panX.value + anchorLeft * zoom.value),
    grabOffsetY: e.clientY - (rect.top + panY.value + anchorTop * zoom.value),
    dCol: 0,
    dRow: 0,
    moved: false,
  }
}

function onPaletteMoveMove(e: PointerEvent) {
  const drag = moveDrag.value
  const vp = viewportRef.value
  if (!drag || !vp) return
  const rect = vp.getBoundingClientRect()
  const local = viewportPointToLocal(e.clientX - rect.left, e.clientY - rect.top)
  const dx = local.x - drag.startLocalX
  const dy = local.y - drag.startLocalY

  drag.pointerX = e.clientX
  drag.pointerY = e.clientY
  // 松手时吸附：四舍五入到最近的格子（横向纵向都算）
  drag.dCol = Math.round(dx / PALETTE_CELL)
  drag.dRow = Math.round(dy / PALETTE_CELL)
  // 超过 3px 才算真的拖动，单纯点击不会闪出影子
  if (!drag.moved && Math.hypot(dx, dy) > 3) drag.moved = true
}

function onPaletteMoveEnd() {
  window.removeEventListener('pointermove', onPaletteMoveMove)
  window.removeEventListener('pointerup', onPaletteMoveEnd)
  const drag = moveDrag.value
  moveDrag.value = null
  if (!drag || !drag.moved) return
  // 整组不允许跑到左上角之外：按绝对格子算（anchor + 组内最小相对偏移 + 位移）
  let minRelCol = Infinity
  let minRelRow = Infinity
  for (const it of drag.items) {
    minRelCol = Math.min(minRelCol, it.relCol)
    minRelRow = Math.min(minRelRow, it.relRow)
  }
  const dCol = Math.max(drag.dCol, -(drag.anchorCol + minRelCol))
  const dRow = Math.max(drag.dRow, -(drag.anchorRow + minRelRow))
  if (dCol === 0 && dRow === 0) return
  applyGroupMove(drag.items.map(it => it.entry), dCol, dRow)
}

/**
 * 整组图块整体平移 dCol/dRow 格。
 * 目标格被别的图块占着时，被占的图块挪进腾出来的原格子（即交换）；
 * 占位的比要移动的还多就放弃这次移动。
 */
function applyGroupMove(items: PaletteLayoutItem[], dCol: number, dRow: number) {
  const keyOf = (entry: PaletteLayoutItem) => paletteEntryKeyOf(entry.item)
  const cellOf = (entry: PaletteLayoutItem) => ({
    col: Math.floor(entry.left / PALETTE_CELL),
    row: Math.floor(entry.top / PALETTE_CELL),
  })

  const movingKeys = new Set(items.map(keyOf))
  const sourceCells = items.map(cellOf)
  const targetCells = sourceCells.map(c => ({ col: c.col + dCol, row: c.row + dRow }))

  const occupants = paletteLayout.value.items
    .filter(entry => !movingKeys.has(keyOf(entry)))
    .map(entry => ({ entry, cell: cellOf(entry) }))
    .filter(o => targetCells.some(t => t.col === o.cell.col && t.row === o.cell.row))
    .sort((a, b) => a.cell.row - b.cell.row || a.cell.col - b.cell.col)
  if (occupants.length > sourceCells.length) return

  const vacated = [...sourceCells].sort((a, b) => a.row - b.row || a.col - b.col)
  const cells: { key: string; col: number; row: number }[] = []
  occupants.forEach((o, i) => {
    cells.push({
      key: keyOf(o.entry),
      col: vacated[i].col,
      row: vacated[i].row,
    })
  })
  items.forEach((entry, i) => {
    cells.push({
      key: keyOf(entry),
      col: targetCells[i].col,
      row: targetCells[i].row,
    })
  })
  mapStore.setPaletteCellsByKey(cells)
}

// ====== 随机绘制：在选中的多个图块里随机挑一个来画（同 Godot） ======
const randomBrushOn = ref(false)

/** 把当前选中的图块同步给 store，画布绘制时从中随机取值 */
function syncRandomBrushPool() {
  if (!randomBrushOn.value) {
    mapStore.setRandomBrush(false)
    return
  }
  const pool = paletteLayout.value.items
    .filter(entry => paletteSelection.has(paletteEntryKeyOf(entry.item)))
    .map(entry => ({
      resourceId: entry.item.resource.id,
      tileIndex: entry.item.tileIndex,
      flipH: entry.item.flipH,
      flipV: entry.item.flipV,
    }))
  mapStore.setRandomBrush(true, pool)
}

function toggleRandomBrush() {
  randomBrushOn.value = !randomBrushOn.value
  syncRandomBrushPool()
}

/** 散布参数：0~100，越大越容易留空 */
function onScatterChange(e: Event) {
  const el = e.target as HTMLInputElement
  const value = Math.round(Number(el.value))
  mapStore.setRandomBrushScatter(Number.isFinite(value) ? value : 0)
  el.value = String(mapStore.randomBrushScatter)
}

// ====== 批量给选中的图块加 / 去碰撞 ======
/** 选中的图块；没有多选时退回当前画笔 */
function selectedTileTargets(): { resourceId: string; tileIndex: number }[] {
  const targets = paletteItems.value
    .filter(item => paletteSelection.has(paletteEntryKeyOf(item)))
    .map(item => ({ resourceId: item.resource.id, tileIndex: item.tileIndex }))
  const brush = mapStore.selectedResource
  if (targets.length === 0 && brush && mapStore.selectedTileIndex >= 0) {
    targets.push({ resourceId: brush.id, tileIndex: mapStore.selectedTileIndex })
  }
  return targets
}

/** 批量设置碰撞：开启时补一个铺满整块的默认矩形 */
function setSelectedTilesCollision(enabled: boolean) {
  for (const target of selectedTileTargets()) {
    const resource = mapStore.activeLayerResources.find(r => r.id === target.resourceId)
    if (!resource) continue
    const tileSetIndex = mapStore.tileSetIndexOfResource(resource)
    if (tileSetIndex < 0) continue
    const shape = enabled ? { points: [[0, 0], [1, 0], [1, 1], [0, 1]] } : undefined
    mapStore.setTileCollision(tileSetIndex, target.tileIndex, enabled, shape)
  }
}

/** 选中图块朝向的签名：翻转后要重新同步给画笔 / 图章 / 随机池 */
function paletteFlipSignature() {
  return paletteItems.value
    .map(item => `${paletteEntryKeyOf(item)}:${item.flipH ? 1 : 0}${item.flipV ? 1 : 0}`)
    .join('|')
}

// 注意：这个 watcher 必须放在 paletteItems / paletteLayout 定义之后。
// watch 的 getter 在组件 setup 阶段就会执行一次（用于记录旧值），
// 若在 paletteItems 声明之前调用 paletteFlipSignature 会触发 TDZ 报错，
// 导致 TileResourceBar setup 失败、Vue 更新队列卡死（新建图块图层时整页卡顿）。

/** 把调色板的选择同步给 store：右侧面板批量改属性 + 画布多图块图章 */
function syncPaletteSelection() {
  const selectedItems = paletteItems.value.filter(item => paletteSelection.has(paletteEntryKeyOf(item)))
  mapStore.setTileBrushSelection(
    selectedItems.map(item => ({ resourceId: item.resource.id, tileIndex: item.tileIndex })),
  )

  // 多选时按调色板里的相对位置生成图章：选中一个则退回普通单块画笔
  const selectedLayout = paletteLayout.value.items.filter(entry =>
    paletteSelection.has(paletteEntryKeyOf(entry.item))
  )
  if (selectedLayout.length <= 1) {
    mapStore.setTileBrushStamp([])
    return
  }
  let minCol = Infinity
  let minRow = Infinity
  for (const entry of selectedLayout) {
    minCol = Math.min(minCol, tileGlobalCol(entry))
    minRow = Math.min(minRow, tileGlobalRow(entry))
  }
  mapStore.setTileBrushStamp(selectedLayout.map(entry => ({
    resourceId: entry.item.resource.id,
    tileIndex: entry.item.tileIndex,
    flipH: entry.item.flipH,
    flipV: entry.item.flipV,
    dx: tileGlobalCol(entry) - minCol,
    dy: tileGlobalRow(entry) - minRow,
  })))
}

// ====== 图块翻转 / 复制：每块图块的朝向独立，复制后可各自翻转 ======
/** 当前要翻转的图块：优先用框选/多选，否则作用于当前画笔 */
function flipTargets(): PaletteItem[] {
  const selected = paletteItems.value.filter(item => paletteSelection.has(paletteEntryKeyOf(item)))
  if (selected.length) return selected
  const current = paletteItems.value.find(item => isCurrentBrush(item))
  return current ? [current] : []
}

const flipTargetCount = computed(() => flipTargets().length)
const flipHOn = computed(() => {
  const targets = flipTargets()
  return targets.length > 0 && targets.every(item => item.flipH)
})
const flipVOn = computed(() => {
  const targets = flipTargets()
  return targets.length > 0 && targets.every(item => item.flipV)
})

/** 多选翻转时把整组图块的排列也镜像（大物件镜像后不会碎成散块） */
function mirrorSelectionCells(targets: PaletteItem[], axis: 'h' | 'v') {
  if (targets.length <= 1) return
  materializePaletteCells()
  const layout = paletteLayout.value.items.filter(entry =>
    targets.some(item => item.key === paletteEntryKeyOf(entry.item))
  )
  if (layout.length <= 1) return

  let minCol = Infinity
  let maxCol = -1
  let minRow = Infinity
  let maxRow = -1
  const cells = layout.map(entry => {
    const col = tileGlobalCol(entry)
    const row = tileGlobalRow(entry)
    if (col < minCol) minCol = col
    if (col > maxCol) maxCol = col
    if (row < minRow) minRow = row
    if (row > maxRow) maxRow = row
    return { key: paletteEntryKeyOf(entry.item), col, row }
  })
  const targetCells = cells.map(cell => ({
    key: cell.key,
    col: axis === 'h' ? minCol + maxCol - cell.col : cell.col,
    row: axis === 'v' ? minRow + maxRow - cell.row : cell.row,
  }))

  // 目标格被未选中的图块占着时，把占用者换到腾出来的格子，避免重叠
  const occupancy = new Map<string, string>()
  for (const entry of paletteLayout.value.items) {
    occupancy.set(`${tileGlobalCol(entry)},${tileGlobalRow(entry)}`, paletteEntryKeyOf(entry.item))
  }
  const movingKeys = new Set(cells.map(cell => cell.key))
  const vacated = [...cells].sort((a, b) => a.row - b.row || a.col - b.col)
  const displaced: { key: string; col: number; row: number }[] = []
  let vacateIndex = 0
  for (const target of targetCells) {
    const occupant = occupancy.get(`${target.col},${target.row}`)
    if (!occupant || movingKeys.has(occupant)) continue
    const slot = vacated[vacateIndex++]
    if (!slot) return
    displaced.push({ key: occupant, col: slot.col, row: slot.row })
  }
  mapStore.setPaletteCellsByKey([...targetCells, ...displaced])
}

/** X / Y：翻转选中的图块（多选时整组排列一起镜像） */
function toggleFlip(axis: 'h' | 'v') {
  const targets = flipTargets()
  if (!targets.length) return
  const next = axis === 'h' ? !flipHOn.value : !flipVOn.value
  mirrorSelectionCells(targets, axis)
  for (const item of targets) {
    mapStore.setPaletteEntryFlip(
      paletteEntryKeyOf(item),
      axis === 'h' ? next : item.flipH,
      axis === 'v' ? next : item.flipV,
    )
  }
}

/** 复制选中的图块到右侧空位：新条目和原条目完全独立，可以各自翻转 */
function copySelectedTiles() {
  if (props.disabled) return
  const targets = flipTargets()
  if (!targets.length) return
  // 先把整张调色板的格子坐标固化，避免复制后其余图块自动重排
  materializePaletteCells()

  const layoutByKey = new Map<string, PaletteLayoutItem>()
  for (const entry of paletteLayout.value.items) {
    layoutByKey.set(paletteEntryKeyOf(entry.item), entry)
  }
  const sourceLayout = targets
    .map(item => layoutByKey.get(item.key))
    .filter((entry): entry is PaletteLayoutItem => !!entry)
  if (!sourceLayout.length) return

  let minCol = Infinity
  let maxCol = -1
  let minRow = Infinity
  let maxRow = -1
  for (const entry of sourceLayout) {
    const col = tileGlobalCol(entry)
    const row = tileGlobalRow(entry)
    if (col < minCol) minCol = col
    if (col > maxCol) maxCol = col
    if (row < minRow) minRow = row
    if (row > maxRow) maxRow = row
  }
  const width = maxCol - minCol + 1
  const height = maxRow - minRow + 1

  // 从选区右侧开始，找一块不会压到已有图块的空位
  const occupied = new Set<string>()
  for (const entry of paletteLayout.value.items) {
    occupied.add(`${tileGlobalCol(entry)},${tileGlobalRow(entry)}`)
  }
  let startCol = maxCol + 1
  while (true) {
    let free = true
    for (let dc = 0; dc < width && free; dc++) {
      for (let dr = 0; dr < height; dr++) {
        if (occupied.has(`${startCol + dc},${minRow + dr}`)) {
          free = false
          break
        }
      }
    }
    if (free) break
    startCol++
  }

  const copies = sourceLayout.map(entry => ({
    resourceId: entry.item.resource.id,
    tileIndex: entry.item.tileIndex,
    flipH: entry.item.flipH,
    flipV: entry.item.flipV,
    col: startCol + (tileGlobalCol(entry) - minCol),
    row: tileGlobalRow(entry),
  }))
  const newKeys = mapStore.addPaletteEntryCopies(copies)
  if (!newKeys.length) return

  // 复制完直接选中新副本，方便马上翻转出另一个朝向
  paletteSelection.clear()
  for (const key of newKeys) paletteSelection.add(key)
  const first = paletteItems.value.find(item => item.key === newKeys[0])
  if (first) emitSelectItem(first)
}

function onPalettePointerMove(e: PointerEvent) {
  if (!panning) return
  panX.value = panStartPanX + (e.clientX - panStartX)
  panY.value = panStartPanY + (e.clientY - panStartY)
}

function onPalettePointerUp() {
  panning = false
  window.removeEventListener('pointermove', onPalettePointerMove)
  window.removeEventListener('pointerup', onPalettePointerUp)
}

/** 滚轮以鼠标位置为中心缩放 */
function onPaletteWheel(e: WheelEvent) {
  if (!viewportRef.value) return
  const rect = viewportRef.value.getBoundingClientRect()
  const mx = e.clientX - rect.left
  const my = e.clientY - rect.top
  const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12
  const next = Math.min(PALETTE_MAX_ZOOM, Math.max(PALETTE_MIN_ZOOM, zoom.value * factor))
  const ratio = next / zoom.value
  panX.value = mx - (mx - panX.value) * ratio
  panY.value = my - (my - panY.value) * ratio
  zoom.value = next
}

/** 双击空白网格：视角回到原点 */
function onPaletteDblClick(e: MouseEvent) {
  const target = e.target as HTMLElement | null
  if (target?.closest('.tile-cell')) return
  panX.value = 0
  panY.value = 0
  zoom.value = 1
}

/** F：把全部图块缩放到视口内并居中 */
function fitPaletteView() {
  const vp = viewportRef.value
  if (!vp || !paletteLayout.value.items.length) {
    panX.value = 0
    panY.value = 0
    zoom.value = 1
    return
  }
  const rect = vp.getBoundingClientRect()
  const pad = 12
  const availW = Math.max(1, rect.width - pad * 2)
  const availH = Math.max(1, rect.height - pad * 2)
  const fit = Math.min(availW / paletteLayout.value.width, availH / paletteLayout.value.height)
  zoom.value = Math.max(PALETTE_MIN_ZOOM, Math.min(PALETTE_MAX_ZOOM, fit))
  panX.value = (rect.width - paletteLayout.value.width * zoom.value) / 2
  panY.value = (rect.height - paletteLayout.value.height * zoom.value) / 2
}

/** 悬浮缩放条显示的百分比 */
const paletteZoomText = computed(() => `${Math.round(zoom.value * 100)}%`)

/** 按钮缩放：以视口中心为锚点，避免缩放时视野跑偏 */
function zoomPaletteBy(factor: number) {
  const vp = viewportRef.value
  if (!vp) return
  const next = Math.min(PALETTE_MAX_ZOOM, Math.max(PALETTE_MIN_ZOOM, zoom.value * factor))
  if (next === zoom.value) return
  const rect = vp.getBoundingClientRect()
  const cx = rect.width / 2
  const cy = rect.height / 2
  const ratio = next / zoom.value
  panX.value = cx - (cx - panX.value) * ratio
  panY.value = cy - (cy - panY.value) * ratio
  zoom.value = next
}

/** 实际尺寸（100%）居中显示整张调色板 */
function resetPaletteView() {
  const vp = viewportRef.value
  if (!vp) return
  const rect = vp.getBoundingClientRect()
  zoom.value = 1
  panX.value = (rect.width - paletteLayout.value.width) / 2
  panY.value = (rect.height - paletteLayout.value.height) / 2
}

// 进入绘制测试时请求一次「居中显示」：图块尺寸/切图是异步算出来的，
// 所以等布局就绪（或稍后）再居中，避免按空布局算错位置
let pendingCenterPalette = false

function tryCenterPaletteView() {
  if (!pendingCenterPalette) return
  const vp = viewportRef.value
  if (!vp || vp.clientWidth === 0 || !paletteLayout.value.items.length) return
  pendingCenterPalette = false
  resetPaletteView()
}

/** 外部（绘制测试）请求：把调色板按 100% 居中显示一次 */
function requestCenterPaletteView() {
  pendingCenterPalette = true
  tryCenterPaletteView()
  // 布局异步生成时，上面这次可能还没就绪，补两次
  window.setTimeout(tryCenterPaletteView, 120)
  window.setTimeout(tryCenterPaletteView, 400)
}

/**
 * 放大并居中选中的图块（多选时按整组包围盒居中）。
 * 放大到单格约 60px（zoom=1.5）就够看清，不继续放大以免素材过大。
 */
function focusSelectedTileView() {
  const vp = viewportRef.value
  if (!vp) return
  const selectedLayout = paletteLayout.value.items.filter(entry =>
    paletteSelection.has(paletteEntryKeyOf(entry.item))
  )
  const targets = selectedLayout.length
    ? selectedLayout
    : paletteLayout.value.items.filter(entry => isCurrentBrush(entry.item))
  if (!targets.length) return

  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const entry of targets) {
    if (entry.left < minX) minX = entry.left
    if (entry.top < minY) minY = entry.top
    if (entry.left + PALETTE_CELL > maxX) maxX = entry.left + PALETTE_CELL
    if (entry.top + PALETTE_CELL > maxY) maxY = entry.top + PALETTE_CELL
  }

  const rect = vp.getBoundingClientRect()
  // 已经放得更大时保持当前比例，不要因为点一下反而缩小
  const next = Math.min(PALETTE_MAX_ZOOM, Math.max(1.5, zoom.value))
  zoom.value = next
  panX.value = rect.width / 2 - ((minX + maxX) / 2) * next
  panY.value = rect.height / 2 - ((minY + maxY) / 2) * next
}

/** 鼠标在调色板上时按 F 才响应，避免影响代码编辑器里的输入 */
function onPaletteWindowKeydown(e: KeyboardEvent) {
  const target = e.target as HTMLElement | null
  if (target && (
    target.tagName === 'INPUT'
    || target.tagName === 'TEXTAREA'
    || target.tagName === 'SELECT'
    || target.isContentEditable
  )) return

  // X / Y：翻转选中的图块（同 Tiled），只在地图编辑页的图块模式下生效
  const key = e.key.toLowerCase()
  if ((key === 'x' || key === 'y') && !e.ctrlKey && !e.metaKey && !e.altKey) {
    if (
      editorStore.isGameMode
      && editorStore.activeEditorMode === 'map'
      && mapStore.activeMode === 'tile'
    ) {
      e.preventDefault()
      toggleFlip(key === 'x' ? 'h' : 'v')
    }
    return
  }

  // F：鼠标在调色板上时把全部图块缩放到视口内并居中
  if (!paletteHovered.value) return
  if (e.key !== 'f' && e.key !== 'F') return
  if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return
  e.preventDefault()
  fitPaletteView()
}

onBeforeUnmount(() => {
  onPalettePointerUp()
  window.removeEventListener('pointermove', onPaletteBoxMove)
  window.removeEventListener('pointerup', onPaletteBoxEnd)
  window.removeEventListener('pointermove', onPaletteMoveMove)
  window.removeEventListener('pointerup', onPaletteMoveEnd)
  window.removeEventListener('keydown', onPaletteWindowKeydown)
  gridObserver?.disconnect()
  gridObserver = null
  if (gridFrame) cancelAnimationFrame(gridFrame)
  gridFrame = 0
})

/** 打开系统窗口多选图片：统一换算成当前图块尺寸后导入调色板 */
async function uploadLocalTiles() {
  if (props.disabled) return
  let paths: string[] = []
  try {
    paths = await invoke<string[]>('pick_image_files')
  } catch {
    return // 用户取消
  }
  if (!paths.length) return

  // 旧地图没有调色板时，先把已有素材展开，避免只导入新素材的图块
  if (mapStore.mapData.tilePalette === undefined) {
    await generateTileThumbnails()
  }

  let lastResourceId = ''
  for (const src of paths) {
    // 单图块按整数倍缩放适配；多格图集只按当前格子切（切错了改尺寸重切）
    const imported = await importTileImage(src, { fileName: src.split(/[\\/]/).pop() })
    if (!imported) continue
    const resourceId = mapStore.addResource({
      name: (src.split(/[\\/]/).pop() || '图块').split('.')[0] || '图块',
      path: imported.path,
      resourceType: 'tileset',
      tileWidth: imported.tileWidth,
      tileHeight: imported.tileHeight,
      collisionType: '图像',
      collisionEnabled: false,
      originPath: imported.originPath,
      nativeTileSize: imported.nativeTileSize,
      assetKind: imported.assetKind,
    })
    expandedSlices.set(resourceId, `${imported.path}:${imported.tileWidth}x${imported.tileHeight}`)
    // 按图块尺寸切块并全部加入调色板（全透明块会在刷新时自动剔除）
    try {
      const img = await loadImage(await getResourceUrl(imported.path))
      const cols = Math.floor(img.width / imported.tileWidth)
      const rows = Math.floor(img.height / imported.tileHeight)
      const entries: { resourceId: string; tileIndex: number }[] = []
      for (let r = 0; r < rows; r++) {
        for (let c = 0; c < cols; c++) {
          entries.push({ resourceId, tileIndex: r * cols + c })
        }
      }
      mapStore.addPaletteEntries(entries)
    } catch {
      // 加载失败时由 refreshAll 重试
    }
    lastResourceId = resourceId
  }
  // 导入完默认选中最后上传的图块，不用再手动点一次（切片异步生成，刷新完成后落实）
  if (lastResourceId) mapStore.pendingTileSelectResourceId = lastResourceId
  await refreshAll()
}

defineExpose({
  uploadLocalTiles,
  requestCenterPaletteView,
})

const currentResources = computed(() => mapStore.activeLayerResources)
const tileResources = computed(() => currentResources.value.filter(r => r.resourceType !== 'image'))

// ====== 图块尺寸（整张地图统一） ======
const tileSizeOptions = [
  { label: '16x16', value: '16x16' },
  { label: '32x32', value: '32x32' },
  { label: '64x64', value: '64x64' },
]
const tileSizeValue = computed(() => `${mapStore.mapData.tileSize}x${mapStore.mapData.tileSize}`)
function onTileSizeChange(val: string) {
  const newSize = Number(val.split('x')[0])
  if (!Number.isFinite(newSize) || newSize <= 0) return
  if (newSize === mapStore.mapData.tileSize) return
  mapStore.updateTileSize(newSize, true)
  // 所有素材都从原图按新格子重新归一化（整数倍整图缩放，非整数倍逐块缩放）
  void refitTilesetsToGrid(newSize)
}

// ====== 全局缓存 ======
const globalUrlCache = new Map<string, string>()
const globalTileCache = new Map<string, { count: number; cols: number; thumbnails: string[]; empty: boolean[] }>()
const imageLoadCache = new Map<string, HTMLImageElement>()

const tileCounts = ref<Map<string, number>>(new Map())
/** 每套图块集的原始列数：按原图排列，保留空位 */
const tileCols = ref<Map<string, number>>(new Map())
const tileThumbs = ref<Map<string, string>>(new Map())
// 空格子（整块全透明）标记：不进入笔刷调色板
const tileEmpty = ref<Map<string, boolean>>(new Map())
// 已经展开进调色板的素材：记录切片签名（图片 + 图块尺寸）。
// 尺寸一变说明图块要重新切，必须重建成员，否则只会显示旧切片剩下的那几个。
let expandedSlices = new Map<string, string>()

/** 切片签名：图片路径或图块尺寸变化时，这套素材需要重新展开进调色板 */
function slicingKey(res: MapResource): string {
  return `${res.path}:${res.tileWidth}x${res.tileHeight}`
}

const paletteEntries = computed(() => mapStore.mapData.tilePalette ?? [])

interface PaletteItem {
  paletteIndex: number
  /** 条目唯一键（同一图块的多个副本各有一个） */
  key: string
  resource: MapResource
  resourceIndex: number
  tileIndex: number
  /** 图块自身朝向：调色板显示与落笔都用它 */
  flipH: boolean
  flipV: boolean
  thumb: string
}

/** 调色板按保存顺序展开为界面条目（无效条目自动跳过） */
const paletteItems = computed<PaletteItem[]>(() => {
  const items: PaletteItem[] = []
  const resources = currentResources.value
  for (let i = 0; i < paletteEntries.value.length; i++) {
    const entry = paletteEntries.value[i]
    const resourceIndex = resources.findIndex(r => r.id === entry.resourceId)
    if (resourceIndex < 0) continue
    const resource = resources[resourceIndex]
    const count = tileCounts.value.get(resource.id) ?? 0
    if (entry.tileIndex < 0 || entry.tileIndex >= count) continue
    if (tileEmpty.value.get(`${resource.id}:${entry.tileIndex}`)) continue
    items.push({
      paletteIndex: i,
      key: tilePaletteEntryKey(entry),
      resource,
      resourceIndex,
      tileIndex: entry.tileIndex,
      flipH: entry.flipH === true,
      flipV: entry.flipV === true,
      thumb: tileThumbs.value.get(`${resource.id}:${entry.tileIndex}`) || '',
    })
  }
  return items
})

/** 按原图排布：每套图块集独立成块，保留原始列数与空格子 */
/** 块与块之间不留空隙：新上传的图块集紧挨着排在右边 */
const PALETTE_BLOCK_GAP = 0
interface PaletteLayoutItem {
  item: PaletteItem
  left: number
  top: number
}
const paletteLayout = computed<{
  items: PaletteLayoutItem[]
  width: number
  height: number
}>(() => {
  const entries = paletteEntries.value
  const placed: PaletteLayoutItem[] = []
  const natural: PaletteItem[] = []

  // 1) 移动工具摆放过的图块：直接用它记录下来的格子坐标
  let maxPlacedCol = -1
  for (const item of paletteItems.value) {
    const entry = entries[item.paletteIndex]
    if (!entry || entry.col == null || entry.row == null) {
      natural.push(item)
      continue
    }
    placed.push({
      item,
      left: entry.col * PALETTE_CELL,
      top: entry.row * PALETTE_CELL,
    })
    if (entry.col > maxPlacedCol) maxPlacedCol = entry.col
  }

  // 2) 其余图块按原图排布，从已摆放图块的右侧开始
  const blockOrder: string[] = []
  const byResource = new Map<string, PaletteItem[]>()
  for (const item of natural) {
    const id = item.resource.id
    if (!byResource.has(id)) {
      byResource.set(id, [])
      blockOrder.push(id)
    }
    byResource.get(id)!.push(item)
  }

  let blockX = (maxPlacedCol + 1) * PALETTE_CELL
  for (const id of blockOrder) {
    const list = byResource.get(id)!
    const cols = tileCols.value.get(id) || PALETTE_COLS

    // 只裁掉外边缘整行整列空白：取非空图块的包围盒，内部空位保留
    let minCol = Infinity
    let maxCol = -1
    let minRow = Infinity
    let maxRow = -1
    for (const item of list) {
      const col = item.tileIndex % cols
      const row = Math.floor(item.tileIndex / cols)
      if (col < minCol) minCol = col
      if (col > maxCol) maxCol = col
      if (row < minRow) minRow = row
      if (row > maxRow) maxRow = row
    }
    if (maxCol < 0) continue

    for (const item of list) {
      const col = item.tileIndex % cols
      const row = Math.floor(item.tileIndex / cols)
      placed.push({
        item,
        left: blockX + (col - minCol) * PALETTE_CELL,
        top: (row - minRow) * PALETTE_CELL,
      })
    }

    const blockWidth = (maxCol - minCol + 1) * PALETTE_CELL
    blockX += blockWidth + PALETTE_BLOCK_GAP
  }

  // 宽度 / 高度按实际占用的格子算（F 键居中、框选都用它）
  let width = 0
  let height = 0
  for (const entry of placed) {
    width = Math.max(width, entry.left + PALETTE_CELL - 1)
    height = Math.max(height, entry.top + PALETTE_CELL - 1)
  }
  return { items: placed, width, height }
})

// 选择变化 / 切换图层后，随机池跟着更新（放在 paletteItems / paletteLayout 初始化之后）
watch(
  () => [randomBrushOn.value, [...paletteSelection].sort().join('|'), paletteFlipSignature()],
  () => syncRandomBrushPool(),
)

// 选择变化、图块移动/重排后都要重算图章位置（放在 paletteLayout 定义之后，immediate 才能安全取值）
watch(
  () => [
    [...paletteSelection].sort().join('|'),
    paletteLayout.value.items
      .map(entry => `${paletteEntryKeyOf(entry.item)}@${tileGlobalCol(entry)},${tileGlobalRow(entry)}`)
      .join('|'),
    // 朝向变化（翻转）后，图章 / 画笔也要跟着换成新朝向
    paletteFlipSignature(),
  ],
  () => syncPaletteSelection(),
  { immediate: true },
)

const selectedPaletteIndex = computed(() => {
  const item = paletteItems.value.find(it => isCurrentBrush(it))
  return item ? item.paletteIndex : -1
})

async function getResourceUrl(path: string): Promise<string> {
  const cached = globalUrlCache.get(path)
  if (cached) return cached

  // 绘制测试里的内存缩放图是 data URL，直接可加载
  if (path.startsWith('data:')) {
    globalUrlCache.set(path, path)
    return path
  }

  let url: string
  if (path.startsWith('/maps/')) {
    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')
      url = await invoke<string>('read_image_as_data_url', { path: `${engineDir}${path}` })
    } catch (e) {
      console.warn('加载内置资源失败:', path, e)
      url = ''
    }
  } else if (path.startsWith('assets/')) {
    const fullPath = `${projectStore.root}/${path}`
    try {
      url = await invoke<string>('read_image_as_data_url', { path: fullPath })
    } catch {
      url = convertFileSrc(fullPath)
    }
  } else {
    try {
      url = await invoke<string>('read_image_as_data_url', { path })
    } catch {
      url = convertFileSrc(path)
    }
  }

  globalUrlCache.set(path, url)
  return url
}

async function loadImage(src: string): Promise<HTMLImageElement> {
  const cached = imageLoadCache.get(src)
  if (cached) return cached
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      imageLoadCache.set(src, img)
      resolve(img)
    }
    img.onerror = reject
    img.src = src
  })
}

function cacheKey(res: MapResource) {
  return `${res.id}:${res.tileWidth}x${res.tileHeight}`
}

/** 整块全透明 = 空图块（不进入笔刷列表） */
function isCanvasEmpty(canvas: HTMLCanvasElement): boolean {
  const ctx = canvas.getContext('2d')
  if (!ctx) return true
  const d = ctx.getImageData(0, 0, canvas.width, canvas.height).data
  for (let i = 3; i < d.length; i += 4) {
    if (d[i] > 8) return false
  }
  return true
}

async function generateTileThumbnails() {
  const batchCounts = new Map<string, number>()
  const batchCols = new Map<string, number>()
  const batchThumbs = new Map<string, string>()
  const batchEmpty = new Map<string, boolean>()
  // 所有素材都命中缓存时结果和上次完全相同：不要替换 Map（否则会触发整个调色板重绘）
  let cacheMissed = false

  for (const res of tileResources.value) {
    const key = cacheKey(res)
    const cached = globalTileCache.get(key)
    if (cached) {
      batchCounts.set(res.id, cached.count)
      batchCols.set(res.id, cached.cols)
      for (let t = 0; t < cached.count; t++) {
        batchThumbs.set(`${res.id}:${t}`, cached.thumbnails[t] || '')
        batchEmpty.set(`${res.id}:${t}`, cached.empty?.[t] ?? false)
      }
      continue
    }
    cacheMissed = true

    try {
      const url = await getResourceUrl(res.path)
      if (!url) { batchCounts.set(res.id, 0); continue }
      const img = await loadImage(url)
      const cols = Math.floor(img.width / res.tileWidth)
      const count = cols * Math.floor(img.height / res.tileHeight)
      batchCounts.set(res.id, count)
      batchCols.set(res.id, cols)

      const thumbs: string[] = []
      const emptyFlags: boolean[] = []
      for (let tIdx = 0; tIdx < count; tIdx++) {
        const row = Math.floor(tIdx / cols)
        const col = tIdx % cols
        const canvas = document.createElement('canvas')
        canvas.width = res.tileWidth
        canvas.height = res.tileHeight
        const ctx = canvas.getContext('2d', { willReadFrequently: true })!
        ctx.drawImage(
          img,
          col * res.tileWidth, row * res.tileHeight,
          res.tileWidth, res.tileHeight,
          0, 0,
          res.tileWidth, res.tileHeight
        )
        const empty = isCanvasEmpty(canvas)
        emptyFlags.push(empty)
        thumbs.push(canvas.toDataURL())
        batchThumbs.set(`${res.id}:${tIdx}`, thumbs[tIdx])
        batchEmpty.set(`${res.id}:${tIdx}`, empty)
      }
      globalTileCache.set(key, { count, cols, thumbnails: thumbs, empty: emptyFlags })
    } catch {
      batchCounts.set(res.id, 0)
    }
  }

  // 内容有变化才替换响应式 Map：切图层时全部命中缓存，跳过赋值可避免整块调色板重绘
  const changed =
    cacheMissed ||
    batchCounts.size !== tileCounts.value.size ||
    batchCols.size !== tileCols.value.size ||
    batchThumbs.size !== tileThumbs.value.size ||
    batchEmpty.size !== tileEmpty.value.size
  if (changed) {
    tileCounts.value = batchCounts
    tileCols.value = batchCols
    tileThumbs.value = batchThumbs
    tileEmpty.value = batchEmpty
  }
  syncPaletteWithResources(batchCounts, batchEmpty)
}

/** 把新素材的非空图块按顺序展开进调色板；切片尺寸变化时重建该素材的成员 */
function syncPaletteWithResources(
  counts: Map<string, number>,
  empty: Map<string, boolean>
) {
  const resources = tileResources.value

  // 首次生成调色板
  if (mapStore.mapData.tilePalette === undefined) {
    const entries: TilePaletteEntry[] = []
    for (const res of resources) {
      const count = counts.get(res.id) ?? 0
      for (let t = 0; t < count; t++) {
        if (empty.get(`${res.id}:${t}`)) continue
        entries.push({ resourceId: res.id, tileIndex: t })
      }
    }
    mapStore.setTilePalette(entries)
    expandedSlices = new Map(
      resources
        .filter(r => (counts.get(r.id) ?? 0) > 0)
        .map(r => [r.id, slicingKey(r)]),
    )
    return
  }

  // 清理空图块 / 超出当前切片数量的旧条目（只处理当前可见的图块集，别误删其它集合的条目）
  const visibleIds = new Set(resources.map(r => r.id))
  const existing = mapStore.mapData.tilePalette ?? []
  const cleaned = existing.filter(e => {
    if (!visibleIds.has(e.resourceId)) return true
    const count = counts.get(e.resourceId) ?? 0
    if (e.tileIndex < 0 || e.tileIndex >= count) return false
    return !empty.get(`${e.resourceId}:${e.tileIndex}`)
  })
  if (cleaned.length !== existing.length) mapStore.setTilePalette(cleaned)

  // 新素材，或者切片尺寸变了（重新切图）→ 重建这套素材在调色板里的成员
  let palette = mapStore.mapData.tilePalette ?? []
  let paletteChanged = false
  for (const res of resources) {
    const key = slicingKey(res)
    if (expandedSlices.get(res.id) === key) continue
    const count = counts.get(res.id) ?? 0
    if (count <= 0) continue // 加载失败时保留，下次刷新重试

    const added: TilePaletteEntry[] = []
    for (let t = 0; t < count; t++) {
      if (empty.get(`${res.id}:${t}`)) continue
      added.push({ resourceId: res.id, tileIndex: t })
    }
    // 保留这套素材已有的副本（带 id 的条目）：改图块尺寸重新切图后，用户复制/翻转出来的图块不会丢
    const keptCopies = palette.filter(e => e.resourceId === res.id && e.id)
    // 在原位置替换，避免整套素材被挪到调色板末尾
    const insertAt = palette.findIndex(e => e.resourceId === res.id)
    const others = palette.filter(e => e.resourceId !== res.id)
    palette = insertAt >= 0
      ? [...others.slice(0, insertAt), ...added, ...keptCopies, ...others.slice(insertAt)]
      : [...others, ...added, ...keptCopies]
    expandedSlices.set(res.id, key)
    paletteChanged = true
  }
  if (paletteChanged) mapStore.setTilePalette(palette)
}

async function refreshAll() {
  await generateTileThumbnails()
  applyPendingTileSelect()
}

/** 保持当前缩放，把调色板里的某块图块平移到视口内（刚好可见即可，不居中） */
function ensurePaletteItemVisible(entry: PaletteLayoutItem) {
  const vp = viewportRef.value
  if (!vp) return
  const rect = vp.getBoundingClientRect()
  const size = PALETTE_CELL * zoom.value
  const topLeft = localPointToViewport(entry.left, entry.top)
  const margin = 8
  if (topLeft.x < margin) panX.value += margin - topLeft.x
  else if (topLeft.x + size > rect.width - margin) panX.value += rect.width - margin - (topLeft.x + size)
  if (topLeft.y < margin) panY.value += margin - topLeft.y
  else if (topLeft.y + size > rect.height - margin) panY.value += rect.height - margin - (topLeft.y + size)
}

/** 导入图块素材后落实待选中：默认高亮新素材的最后一块图块（同手动点选，框选同步收拢到它） */
function applyPendingTileSelect() {
  const resourceId = mapStore.pendingTileSelectResourceId
  if (!resourceId) return
  // 素材已不在当前图块集（被删掉 / 换了地图）就放弃这次选中
  if (!tileResources.value.some(r => r.id === resourceId)) {
    mapStore.pendingTileSelectResourceId = ''
    return
  }
  const items = paletteItems.value.filter(item => item.resource.id === resourceId)
  const last = items[items.length - 1]
  if (!last) return // 切片还没算出来，等下一轮刷新再试
  mapStore.pendingTileSelectResourceId = ''
  paletteSelection.clear()
  paletteSelection.add(paletteEntryKeyOf(last))
  emitSelectItem(last)
  // 新素材排在调色板末尾，可能不在视口里：保持缩放，刚好把它挪到可见
  const key = paletteEntryKeyOf(last)
  const layout = paletteLayout.value.items.find(entry => paletteEntryKeyOf(entry.item) === key)
  if (layout) ensurePaletteItemVisible(layout)
}

watch(() => mapStore.activeLayerIndex, () => {
  paletteSelection.clear()
  refreshAll()
})
// 切换图块集（资源仓库）时素材整批变化，需要重新生成缩略图与调色板
// 路径 / 切片尺寸也纳入 key：改地图格子尺寸后素材会被换成新的适配图
watch(
  () => currentResources.value.map(r => `${r.id}:${r.path}:${r.tileWidth}x${r.tileHeight}`).join(','),
  refreshAll,
)
// 载入地图后以当前素材为基线，避免把已删除的图块重新展开
watch(() => mapStore.mapLoadCount, () => {
  paletteSelection.clear()
  mapStore.pendingTileSelectResourceId = ''
  expandedSlices = new Map(tileResources.value.map(r => [r.id, slicingKey(r)]))
  refreshAll()
})
// 布局就绪（尺寸/切图算好）后补一次居中
watch(paletteLayout, () => tryCenterPaletteView())

onMounted(() => {
  expandedSlices = new Map(tileResources.value.map(r => [r.id, slicingKey(r)]))
  refreshAll()
  window.addEventListener('keydown', onPaletteWindowKeydown)
  // 视口尺寸变化（收起/展开、窗口缩放）时重画网格
  if (viewportRef.value) {
    gridObserver = new ResizeObserver(() => scheduleGridDraw())
    gridObserver.observe(viewportRef.value)
  }
  scheduleGridDraw()
})

function onDeleteSelected() {
  // 有框选/多选时，一次删掉所有被选图块
  if (paletteSelection.size > 0) {
    const indices: number[] = []
    for (const item of paletteItems.value) {
      if (paletteSelection.has(paletteEntryKeyOf(item))) {
        indices.push(item.paletteIndex)
      }
    }
    indices.sort((a, b) => b - a)
    for (const idx of indices) mapStore.removePaletteEntry(idx)
    paletteSelection.clear()
    return
  }
  const idx = selectedPaletteIndex.value
  if (idx >= 0) mapStore.removePaletteEntry(idx)
}

function onClearResources() {
  mapStore.clearResources()
  refreshAll()
}
</script>

<template>
  <div class="tile-resource-bar" :class="{ collapsed }">
    <div class="bar-toolbar">
      <button class="bar-tool-btn" v-tooltip="'打开资源库'" @click="emit('open-library')">
        <img :src="iconLibrary" class="bar-tool-icon" />
      </button>
      <button class="bar-tool-btn" v-tooltip="'上传本地图块'" :disabled="disabled" @click="uploadLocalTiles">
        <img :src="iconUpload" class="bar-tool-icon" />
      </button>
      <button
        class="bar-tool-btn"
        v-tooltip="'复制选中的图块（复制出来的和原图块各自独立，可以分别翻转）'"
        :disabled="disabled || (paletteSelection.size === 0 && selectedPaletteIndex < 0)"
        @click="copySelectedTiles"
      >
        <img :src="iconCopy" class="bar-tool-icon" />
      </button>
      <button
        class="bar-tool-btn"
        v-tooltip="'删除图块'"
        :disabled="disabled || (paletteSelection.size === 0 && selectedPaletteIndex < 0)"
        @click="onDeleteSelected"
      >
        <img :src="iconDelete" class="bar-tool-icon" />
      </button>
      <button class="bar-tool-btn" v-tooltip="'清空图块'" @click="onClearResources">
        <img :src="iconReset" class="bar-tool-icon bar-tool-icon-clear" />
      </button>
      <div class="bar-tool-sep" />
      <button
        class="bar-tool-btn"
        :class="{ 'bar-tool-active': paletteSelectMode }"
        v-tooltip="'选择图块（点选 / 拖动框选）'"
        @click="setPaletteTool('select')"
      >
        <img :src="iconClickSelect" class="bar-tool-icon" />
      </button>
      <button
        class="bar-tool-btn"
        :class="{ 'bar-tool-active': paletteMoveMode }"
        v-tooltip="'移动图块（拖动到其他格子）'"
        @click="setPaletteTool('move')"
      >
        <img :src="iconMove" class="bar-tool-icon" />
      </button>
      <button
        class="bar-tool-btn"
        v-tooltip="'给选中的图块添加碰撞'"
        :disabled="disabled || (paletteSelection.size === 0 && selectedPaletteIndex < 0)"
        @click="setSelectedTilesCollision(true)"
      >
        <img :src="iconCollisionOn" class="bar-tool-icon" />
      </button>
      <button
        class="bar-tool-btn"
        v-tooltip="'移除选中图块的碰撞'"
        :disabled="disabled || (paletteSelection.size === 0 && selectedPaletteIndex < 0)"
        @click="setSelectedTilesCollision(false)"
      >
        <img :src="iconCollisionOff" class="bar-tool-icon" />
      </button>
      <div class="bar-tool-sep" />
      <!-- 图块朝向：翻转选中的图块；调色板里直接显示翻转后的样子 -->
      <button
        class="bar-tool-btn"
        :class="{ 'bar-tool-on': flipHOn }"
        v-tooltip="'左右翻转选中的图块（快捷键 X）'"
        :disabled="disabled || flipTargetCount === 0"
        @click="toggleFlip('h')"
      >
        <img :src="iconFlipH" class="bar-tool-icon" />
      </button>
      <button
        class="bar-tool-btn"
        :class="{ 'bar-tool-on': flipVOn }"
        v-tooltip="'上下翻转选中的图块（快捷键 Y）'"
        :disabled="disabled || flipTargetCount === 0"
        @click="toggleFlip('v')"
      >
        <img :src="iconFlipV" class="bar-tool-icon" />
      </button>
      <button
        class="bar-tool-btn"
        :class="{ 'bar-tool-on': randomBrushOn }"
        v-tooltip="'随机绘制（在选中的多个图块里随机挑一个来画）'"
        @click="toggleRandomBrush"
      >
        <img :src="iconRandom" class="bar-tool-icon bar-tool-icon-random" />
      </button>
      <!-- 散布：随机模式下这一格有多大比例什么都不画（同 Godot 的 Scattering） -->
      <div v-if="randomBrushOn" class="bar-scatter">
        <span class="bar-scatter-label">散布</span>
        <input
          class="bar-scatter-input"
          type="number"
          min="0"
          max="100"
          step="5"
          :value="mapStore.randomBrushScatter"
          v-tooltip="'散布：这一格有百分之多少的概率什么都不画'"
          @change="onScatterChange"
        />
        <span class="bar-scatter-unit">%</span>
      </div>
      <div class="bar-spacer" />
      <div
        class="bar-tile-size"
        v-tooltip="'地图的图块格子尺寸（整张地图统一，修改后图块集按新格子重新切）'"
      >
        <span class="bar-tile-size-label">图块尺寸</span>
        <CustomSelect
          class="bar-tile-size-select"
          placement="up"
          :model-value="tileSizeValue"
          :options="tileSizeOptions"
          :disabled="disabled"
          @update:model-value="onTileSizeChange"
        />
      </div>
      <div class="bar-tool-sep" />
      <button
        class="bar-tool-btn collapse-btn"
        :class="{ 'collapse-rotated': !collapsed }"
        v-tooltip="collapsed ? '展开素材' : '收起素材'"
        @click="collapsed = !collapsed"
      >
        <img :src="iconChevron" class="bar-tool-icon" />
      </button>
    </div>

    <div
      ref="viewportRef"
      class="palette-viewport"
      :class="{ 'select-mode': paletteSelectMode, 'move-mode': paletteMoveMode, 'move-dragging': moveGhost.length > 0 }"
      @pointerdown="onPalettePointerDown"
      @mousedown.middle.prevent
      @dblclick="onPaletteDblClick"
      @mouseenter="paletteHovered = true"
      @mouseleave="paletteHovered = false"
      @wheel.prevent="onPaletteWheel"
    >
      <div class="palette-plane" :style="palettePlaneStyle">
        <div
          v-for="entry in paletteLayout.items"
          :key="paletteEntryKeyOf(entry.item)"
          class="tile-cell"
          :class="{
            'tile-selected': isCurrentBrush(entry.item),
            'tile-box-selected': paletteSelection.has(paletteEntryKeyOf(entry.item)),
            'tile-dragging': draggingKeys.has(paletteEntryKeyOf(entry.item))
          }"
          :title="`${entry.item.resource.name} · #${entry.item.tileIndex}`"
          :style="{ left: `${entry.left}px`, top: `${entry.top}px` }"
        >
          <!-- 图块图像单独一层：镜像只翻图片，不影响选中描边和网格 -->
          <div class="tile-cell-img" :style="paletteCellStyle(entry.item)" />
        </div>
      </div>
      <!-- 网格独立成层：画在图块之上，永远按屏幕像素清晰渲染 -->
      <canvas ref="gridCanvasRef" class="palette-grid" />

      <!-- 悬浮缩放条：固定在调色板右下角，不随图块平移/缩放 -->
      <div class="palette-float-bar" @pointerdown.stop @mousedown.stop @dblclick.stop>
        <button
          class="float-btn"
          v-tooltip="'缩小'"
          :disabled="zoom <= PALETTE_MIN_ZOOM"
          @click="zoomPaletteBy(1 / 1.25)"
        >
          <img :src="iconZoomOut" class="float-icon" />
        </button>
        <button
          class="float-zoom-text"
          v-tooltip="'点击恢复 100% 并居中显示'"
          @click="resetPaletteView"
        >{{ paletteZoomText }}</button>
        <button
          class="float-btn"
          v-tooltip="'放大'"
          :disabled="zoom >= PALETTE_MAX_ZOOM"
          @click="zoomPaletteBy(1.25)"
        >
          <img :src="iconZoomIn" class="float-icon" />
        </button>
        <span class="float-sep" />
        <button
          class="float-btn"
          v-tooltip="'放大并居中选中的图块'"
          :disabled="!paletteLayout.items.length"
          @click="focusSelectedTileView"
        >
          <img :src="iconFocus" class="float-icon" />
        </button>
      </div>
      <div
        v-if="paletteBoxRect"
        class="palette-box-select"
        :style="{
          left: `${paletteBoxRect.x}px`,
          top: `${paletteBoxRect.y}px`,
          width: `${paletteBoxRect.w}px`,
          height: `${paletteBoxRect.h}px`
        }"
      />
      <div v-if="!paletteLayout.items.length" class="resource-empty">
        暂无可用的图块笔刷
      </div>
    </div>

    <!-- 拖动中的图块影子：挂在窗口层，不会被调色板面板裁掉 -->
    <Teleport to="body">
      <div v-if="moveGhost.length" class="tile-ghost-layer">
        <div
          v-for="ghost in moveGhost"
          :key="`ghost-${ghost.key}`"
          class="tile-ghost"
          :style="[{
            left: `${ghost.left}px`,
            top: `${ghost.top}px`,
            width: `${ghost.size}px`,
            height: `${ghost.size}px`
          }]"
        >
          <div class="tile-ghost-img" :style="paletteCellStyle(ghost.item)" />
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.tile-resource-bar {
  display: flex;
  flex-direction: column;
  height: 156px;
  flex-shrink: 0;
  background: var(--bg-root);
  border-top: 1px solid var(--border);
}

.tile-resource-bar.collapsed {
  height: 44px;
}

.tile-resource-bar.collapsed .bar-body {
  display: none;
}

.bar-toolbar {
  display: flex;
  align-items: center;
  /* 与顶部工具栏同高（44px） */
  height: 44px;
  padding: 0 8px;
  gap: 4px;
  flex-shrink: 0;
  /* 绿色选中条画在按钮外侧下沿，需要盖过下方的图块区 */
  position: relative;
  z-index: 2;
}

.bar-tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: default;
  padding: 4px;
  flex-shrink: 0;
  transition: background 0.15s;
}

.bar-tool-btn:hover {
  background: rgba(255, 255, 255, 0.07);
}

/* 当前激活的工具：与绘制图层工具栏一致（深色底 + 下方绿色小条） */
.bar-tool-active {
  position: relative;
  background: rgb(46, 49, 58);
  box-shadow: inset 0 0 0 1px var(--border-light);
}

.bar-tool-active:hover {
  background: var(--border-light);
}

.bar-tool-active::before {
  content: '';
  position: absolute;
  left: 1px;
  right: 1px;
  bottom: -5px;
  height: 2.5px;
  border-radius: 1.25px;
  background: var(--accent);
}

/* 常驻开关（随机绘制）：按下只给深色底，不画绿色小条 */
.bar-tool-on {
  background: rgb(46, 49, 58);
  box-shadow: inset 0 0 0 1px var(--border-light);
}

.bar-tool-on:hover {
  background: var(--border-light);
}

/* 模式工具与资源操作之间的细分隔线 */
.bar-tool-sep {
  width: 1px;
  height: 18px;
  margin: 0 2px;
  background: rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
}

/* 随机绘制的「散布」参数 */
.bar-scatter {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  padding-left: 2px;
  color: #9ca0a4;
  font-size: 11px;
}

.bar-scatter-input {
  width: 42px;
  height: 22px;
  padding: 0 4px;
  box-sizing: border-box;
  background: rgb(30, 30, 30);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: #d5d8dc;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  text-align: right;
  outline: none;
}

.bar-scatter-input:focus {
  border-color: var(--accent);
}

/* 去掉数字输入框的上下箭头 */
.bar-scatter-input::-webkit-inner-spin-button,
.bar-scatter-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.bar-scatter-unit {
  color: #7a7f85;
}

.bar-tool-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.bar-tool-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

/* 随机图标本身在画布里留白多，放大一点才能和其他图标视觉等大 */
.bar-tool-icon-random {
  transform: scale(1.25);
}

/* 清空用的图标几乎占满画布，缩一点才和旁边图标齐平 */
.bar-tool-icon-clear {
  transform: scale(0.85);
}

.bar-spacer {
  flex: 1;
}

/* 右侧：整张地图统一的图块尺寸 */
.bar-tile-size {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  color: #9ca0a4;
  font-size: 11px;
}

.bar-tile-size-label {
  white-space: nowrap;
}

.bar-tile-size-select {
  width: 68px;
  height: 22px;
  flex-shrink: 0;
  font-size: 11px;
}

.collapse-btn img {
  transition: transform 0.15s;
}

/* 展开时箭头朝下，收起时朝右 */
.collapse-rotated img {
  transform: rotate(90deg);
}

/* Unity 风格调色板：视口负责裁剪，平面负责平移/缩放，网格单独一层 */
.palette-viewport {
  position: relative;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  cursor: grab;
  background-color: rgb(30, 30, 30);
}

/* 网格层：铺在视口上、盖在图块上，按屏幕像素独立绘制，不随图块缩放 */
.palette-grid {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 4;
}

/* 悬浮缩放条：固定在调色板右下角，深色圆角浮窗（参考 Unity 图块调色板底部工具条） */
.palette-float-bar {
  position: absolute;
  right: 12px;
  bottom: 12px;
  z-index: 6;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 8px;
  border-radius: 8px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(34, 37, 43, 0.92);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.45);
  cursor: default;
  user-select: none;
}

.float-btn {
  width: 26px;
  height: 26px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 5px;
  background: transparent;
  cursor: pointer;
  transition: background-color 0.1s;
}

.float-btn:hover:not(:disabled) {
  background: rgb(61, 64, 72);
}

.float-btn:disabled {
  opacity: 0.35;
  cursor: default;
}

.float-icon {
  width: 18px;
  height: 18px;
  pointer-events: none;
}

/* 百分比本身也是按钮：点一下恢复 100% 并居中 */
.float-zoom-text {
  min-width: 42px;
  height: 26px;
  padding: 0 4px;
  border: none;
  border-radius: 5px;
  background: transparent;
  color: #cfd3d8;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  text-align: center;
  cursor: pointer;
  transition: background-color 0.1s;
}

.float-zoom-text:hover {
  background: rgb(61, 64, 72);
}

.float-sep {
  width: 1px;
  height: 16px;
  margin: 0 4px;
  background: rgba(255, 255, 255, 0.16);
}

.palette-viewport:active {
  cursor: grabbing;
}

/* 选择模式：左键框选，光标用十字 */
.palette-viewport.select-mode,
.palette-viewport.select-mode:active {
  cursor: crosshair;
}

.palette-viewport.move-mode,
.palette-viewport.move-mode:active {
  cursor: move;
}

/* 正在拖动：手型变抓取态 */
.palette-viewport.move-dragging,
.palette-viewport.move-dragging:active {
  cursor: grabbing;
}

/* 框选矩形：蓝色，和绿色素材区分开 */
.palette-box-select {
  position: absolute;
  border: 1px solid rgb(10, 132, 255);
  background: rgba(10, 132, 255, 0.16);
  pointer-events: none;
  z-index: 5;
}

/* 被拖走的图块：原位置淡出，视觉上就是被拿起来了 */
.tile-dragging {
  opacity: 0.15;
}

/* 拖动中的影子层：铺满窗口，不挡鼠标 */
.tile-ghost-layer {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 9000;
}

/* 跟着鼠标走的图块影子：略微放大 + 投影，看起来像被拿起来了 */
.tile-ghost {
  position: absolute;
  border-radius: 3px;
  overflow: hidden;
  background-color: rgb(52, 56, 66);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.55);
  transform: scale(1.06);
  transform-origin: center;
  pointer-events: none;
  image-rendering: pixelated;
  opacity: 0.95;
}

/* 拖影描边也放到覆盖层：图片是子元素，inset 阴影会被盖住 */
.tile-ghost::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 2;
  box-sizing: border-box;
  border: 2px solid rgb(64, 158, 255);
  pointer-events: none;
}

.palette-plane {
  position: absolute;
  left: 0;
  top: 0;
  width: 0;
  height: 0;
  transform-origin: 0 0;
}

/* 图块占满整格（与网格线严丝合缝，不再留 1px 缝隙） */
.tile-cell {
  position: absolute;
  width: 40px;
  height: 40px;
  box-sizing: border-box;
  background-color: transparent;
  border: none;
  cursor: default;
}

/* 图块图像层：镜像通过 transform 翻这一层，选中描边 / 网格不受影响 */
.tile-cell-img,
.tile-ghost-img {
  position: absolute;
  inset: 0;
  pointer-events: none;
  transform-origin: center;
}

/* 选中 / 悬停高亮：放覆盖层，画在图片之上（参考 Unity 图块调色板：干净的实心描边，不加辉光） */
.tile-cell::after {
  content: '';
  position: absolute;
  inset: 0;
  z-index: 2;
  box-sizing: border-box;
  border: 1px solid transparent;
  pointer-events: none;
  transition: border-color 0.1s;
}

/* 悬停：细白线。已选中的图块不参与悬停，避免点击后看起来还停在 hover 状态 */
.tile-cell:not(.tile-selected):not(.tile-box-selected):hover::after {
  border-color: rgba(255, 255, 255, 0.85);
}

/* 选择工具里一起选中的图块：亮蓝描边 */
.tile-cell.tile-box-selected::after {
  border: 2px solid rgb(110, 196, 255);
}

/* 当前画笔：更深的蓝，且放在后面覆盖 box-selected，保证「正在画的」最醒目 */
.tile-cell.tile-selected::after {
  border: 2px solid rgb(64, 158, 255);
}

.resource-empty {
  position: absolute;
  inset: 0;
  z-index: 6;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgb(80, 80, 80);
  font-size: 12px;
  pointer-events: none;
}
</style>
