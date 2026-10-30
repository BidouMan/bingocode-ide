<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { useMapStore, type MapResource } from '../../stores/map'
import { useProjectStore } from '../../stores/project'
import iconLibrary from '../../assets/icons/图片库.svg'
import iconUpload from '../../assets/icons/上传本地图片资源.svg'
import iconDelete from '../../assets/icons/icon--delete.svg'
import iconReset from '../../assets/icons/重置.svg'
import iconChevron from '../../assets/icons/right_arrow.svg'
import iconClickSelect from '../../assets/icons/选择箭头.svg'
import iconMove from '../../assets/icons/移动工具.svg'
import iconRandom from '../../assets/icons/随机.svg'
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
  'select-tile': [resourceIndex: number, tileIndex: number]
}>()

const mapStore = useMapStore()
const projectStore = useProjectStore()
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

/** 网格背景铺在视口上：尺寸/位置跟随缩放和平移，形成无限延伸的格子 */
const paletteViewportStyle = computed(() => {
  const size = PALETTE_CELL * zoom.value
  return {
    backgroundSize: `${size}px ${size}px, ${size}px ${size}px`,
    backgroundPosition: `${panX.value}px ${panY.value}px, ${panX.value}px ${panY.value}px`,
  }
})

const palettePlaneStyle = computed(() => ({
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`,
}))

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

function tileKey(resourceId: string, tileIndex: number) {
  return `${resourceId}:${tileIndex}`
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
  return Math.floor((entry.left - 1) / PALETTE_CELL)
}
function tileGlobalRow(entry: PaletteLayoutItem) {
  return Math.floor((entry.top - 1) / PALETTE_CELL)
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
      const key = tileKey(boxAnchorEntry.item.resource.id, boxAnchorEntry.item.tileIndex)
      // Shift 点已选中的格子：取消它（加选的常规手感）
      if (boxAdditive && paletteSelection.has(key)) {
        paletteSelection.delete(key)
        // 取消后画笔交给剩下最后一块，没有剩余就保持不动
        const fallback = [...paletteLayout.value.items].reverse().find(entry =>
          paletteSelection.has(tileKey(entry.item.resource.id, entry.item.tileIndex))
        )
        if (fallback) emit('select-tile', fallback.item.resourceIndex, fallback.item.tileIndex)
      } else {
        paletteSelection.add(key)
        emit('select-tile', boxAnchorEntry.item.resourceIndex, boxAnchorEntry.item.tileIndex)
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
      paletteSelection.add(tileKey(entry.item.resource.id, entry.item.tileIndex))
      lastHit = entry
    }
  }

  // 多选后当前画笔始终取最后一个：碰撞预览显示的就是它
  if (lastHit) emit('select-tile', lastHit.item.resourceIndex, lastHit.item.tileIndex)
  boxAnchorEntry = null
}

function paletteCellBackground(item: PaletteItem) {
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

/** 屏幕坐标命中的图块（考虑平移 / 缩放） */
function paletteHitAt(clientX: number, clientY: number): PaletteLayoutItem | null {
  const vp = viewportRef.value
  if (!vp) return null
  const rect = vp.getBoundingClientRect()
  const local = viewportPointToLocal(clientX - rect.left, clientY - rect.top)
  return paletteLayout.value.items.find(entry =>
    local.x >= entry.left && local.x <= entry.left + 38
    && local.y >= entry.top && local.y <= entry.top + 38
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
  const cell = PALETTE_CELL * zoom.value
  const size = 38 * zoom.value
  return drag.items.map(({ entry, relCol, relRow }) => ({
    key: tileKey(entry.item.resource.id, entry.item.tileIndex),
    item: entry.item,
    size,
    left: drag.pointerX - drag.grabOffsetX + relCol * cell,
    top: drag.pointerY - drag.grabOffsetY + relRow * cell,
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
      resourceId: entry.item.resource.id,
      tileIndex: entry.item.tileIndex,
      col: Math.floor((entry.left - 1) / PALETTE_CELL),
      row: Math.floor((entry.top - 1) / PALETTE_CELL),
    }))
  if (cells.length) mapStore.setPaletteCells(cells)
}

function beginPaletteMove(hit: PaletteLayoutItem, e: PointerEvent) {
  const vp = viewportRef.value
  if (!vp) return
  materializePaletteCells()

  // 拖的是已选中的图块 → 整组一起移动；否则只拖这一块
  const anchorKey = tileKey(hit.item.resource.id, hit.item.tileIndex)
  let group: PaletteLayoutItem[]
  if (paletteSelection.has(anchorKey) && paletteSelection.size > 1) {
    group = paletteLayout.value.items.filter(entry =>
      paletteSelection.has(tileKey(entry.item.resource.id, entry.item.tileIndex)),
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
  const anchorLeft = anchorCell.col * PALETTE_CELL + 1
  const anchorTop = anchorCell.row * PALETTE_CELL + 1
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
  const keyOf = (entry: PaletteLayoutItem) =>
    tileKey(entry.item.resource.id, entry.item.tileIndex)
  const cellOf = (entry: PaletteLayoutItem) => ({
    col: Math.floor((entry.left - 1) / PALETTE_CELL),
    row: Math.floor((entry.top - 1) / PALETTE_CELL),
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
  occupants.forEach((o, i) => {
    mapStore.setPaletteEntryCell(
      o.entry.item.resource.id,
      o.entry.item.tileIndex,
      vacated[i].col,
      vacated[i].row,
    )
  })
  items.forEach((entry, i) => {
    mapStore.setPaletteEntryCell(
      entry.item.resource.id,
      entry.item.tileIndex,
      targetCells[i].col,
      targetCells[i].row,
    )
  })
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
    .filter(entry => paletteSelection.has(tileKey(entry.item.resource.id, entry.item.tileIndex)))
    .map(entry => ({ resourceId: entry.item.resource.id, tileIndex: entry.item.tileIndex }))
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
  const targets: { resourceId: string; tileIndex: number }[] = []
  for (const key of paletteSelection) {
    const sep = key.lastIndexOf(':')
    if (sep < 0) continue
    targets.push({ resourceId: key.slice(0, sep), tileIndex: Number(key.slice(sep + 1)) })
  }
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

// 选择变化 / 切换图层后，随机池跟着更新
watch(
  () => [randomBrushOn.value, [...paletteSelection].sort().join('|')],
  () => syncRandomBrushPool(),
)

/** 把调色板的选择同步给 store，右侧面板据此批量改类型 / 作用 / 单向碰撞 */
watch(
  () => [...paletteSelection].sort().join('|'),
  () => {
    const list: { resourceId: string; tileIndex: number }[] = []
    for (const key of paletteSelection) {
      const sep = key.lastIndexOf(':')
      if (sep <= 0) continue
      list.push({ resourceId: key.slice(0, sep), tileIndex: Number(key.slice(sep + 1)) })
    }
    mapStore.setTileBrushSelection(list)
  },
  { immediate: true },
)

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

/** 鼠标在调色板上时按 F 才响应，避免影响代码编辑器里的输入 */
function onPaletteWindowKeydown(e: KeyboardEvent) {
  if (!paletteHovered.value) return
  if (e.key !== 'f' && e.key !== 'F') return
  if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return
  const target = e.target as HTMLElement | null
  if (target && (
    target.tagName === 'INPUT'
    || target.tagName === 'TEXTAREA'
    || target.tagName === 'SELECT'
    || target.isContentEditable
  )) return
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
})

/** 打开系统窗口多选图片，全部按当前图块尺寸切块导入调色板 */
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

  const tw = Math.max(1, mapStore.mapData.tileSize)
  for (const src of paths) {
    let relativePath: string
    try {
      relativePath = await copyResourceToMapDir(src)
    } catch (e) {
      console.error('复制资源到项目目录失败:', e)
      continue
    }
    const resourceId = mapStore.addResource({
      name: src.split('/').pop()?.split('.')[0] || '图块',
      path: relativePath,
      resourceType: 'tileset',
      tileWidth: tw,
      tileHeight: tw,
      collisionType: '图像',
      collisionEnabled: false,
    })
    expandedResources.add(resourceId)
    // 按图块尺寸切块并全部加入调色板（全透明块会在刷新时自动剔除）
    try {
      const img = await loadImage(await getResourceUrl(relativePath))
      const cols = Math.floor(img.width / tw)
      const rows = Math.floor(img.height / tw)
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
  }
  await refreshAll()
}

defineExpose({
  uploadLocalTiles,
  deleteSelectedTile: () => onDeleteSelected(),
  clearTiles: () => onClearResources(),
})

const currentResources = computed(() => mapStore.activeLayerResources)
const tileResources = computed(() => currentResources.value.filter(r => r.resourceType !== 'image'))

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
// 已经展开进调色板的素材（避免刷新时重复追加/复活已删除的图块）
let expandedResources = new Set<string>()

const paletteEntries = computed(() => mapStore.mapData.tilePalette ?? [])

interface PaletteItem {
  paletteIndex: number
  resource: MapResource
  resourceIndex: number
  tileIndex: number
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
      resource,
      resourceIndex,
      tileIndex: entry.tileIndex,
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
      left: entry.col * PALETTE_CELL + 1,
      top: entry.row * PALETTE_CELL + 1,
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
        left: blockX + (col - minCol) * PALETTE_CELL + 1,
        top: (row - minRow) * PALETTE_CELL + 1,
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

const selectedPaletteIndex = computed(() => {
  if (mapStore.selectedResourceIndex < 0) return -1
  const item = paletteItems.value.find(it =>
    it.resourceIndex === mapStore.selectedResourceIndex
    && it.tileIndex === mapStore.selectedTileIndex
  )
  return item ? item.paletteIndex : -1
})

async function getResourceUrl(path: string): Promise<string> {
  const cached = globalUrlCache.get(path)
  if (cached) return cached

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

  tileCounts.value = batchCounts
  tileCols.value = batchCols
  tileThumbs.value = batchThumbs
  tileEmpty.value = batchEmpty
  syncPaletteWithResources(batchCounts, batchEmpty)
}

/** 把新素材的非空图块按顺序展开进调色板；已存在的素材不重复追加 */
function syncPaletteWithResources(
  counts: Map<string, number>,
  empty: Map<string, boolean>
) {
  const resources = tileResources.value
  if (mapStore.mapData.tilePalette === undefined) {
    const entries: { resourceId: string; tileIndex: number }[] = []
    for (const res of resources) {
      const count = counts.get(res.id) ?? 0
      for (let t = 0; t < count; t++) {
        if (empty.get(`${res.id}:${t}`)) continue
        entries.push({ resourceId: res.id, tileIndex: t })
      }
    }
    mapStore.setTilePalette(entries)
    expandedResources = new Set(
      resources.filter(r => (counts.get(r.id) ?? 0) > 0).map(r => r.id)
    )
    return
  }

  // 旧存档里可能已经包含空图块：顺手清掉
  const existing = mapStore.mapData.tilePalette ?? []
  const cleaned = existing.filter(e => !empty.get(`${e.resourceId}:${e.tileIndex}`))
  if (cleaned.length !== existing.length) mapStore.setTilePalette(cleaned)

  const newEntries: { resourceId: string; tileIndex: number }[] = []
  for (const res of resources) {
    if (expandedResources.has(res.id)) continue
    const count = counts.get(res.id) ?? 0
    if (count <= 0) continue // 加载失败时保留，下次刷新重试
    for (let t = 0; t < count; t++) {
      if (empty.get(`${res.id}:${t}`)) continue
      newEntries.push({ resourceId: res.id, tileIndex: t })
    }
    expandedResources.add(res.id)
  }
  if (newEntries.length > 0) mapStore.addPaletteEntries(newEntries)
}

async function refreshAll() {
  await generateTileThumbnails()
}

watch(() => mapStore.activeLayerIndex, () => {
  paletteSelection.clear()
  refreshAll()
})
watch(() => currentResources.value.length, refreshAll)
// 改「图块尺寸」只影响地图网格，图块集仍按自己的原始尺寸切片，调色板不需要重建
watch(() => mapStore.mapLoadCount, () => {
  // 载入地图后以当前素材为基线，避免把已删除的图块重新展开
  paletteSelection.clear()
  expandedResources = new Set(tileResources.value.map(r => r.id))
  refreshAll()
})

onMounted(() => {
  expandedResources = new Set(tileResources.value.map(r => r.id))
  refreshAll()
  window.addEventListener('keydown', onPaletteWindowKeydown)
})

function onDeleteSelected() {
  // 有框选/多选时，一次删掉所有被选图块
  if (paletteSelection.size > 0) {
    const indices: number[] = []
    for (const item of paletteItems.value) {
      if (paletteSelection.has(tileKey(item.resource.id, item.tileIndex))) {
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

// 将资源文件复制到当前地图目录，返回相对路径
async function copyResourceToMapDir(srcPath: string): Promise<string> {
  const projectRoot = projectStore.root
  const mapName = mapStore.mapData.name
  if (!projectRoot || !mapName) throw new Error('地图未就绪')
  // 同名文件重复导入时不能覆盖已有素材（否则图层/图块会串图）
  const rawName = srcPath.split('/').pop() || 'resource.png'
  const dot = rawName.lastIndexOf('.')
  const base = dot > 0 ? rawName.slice(0, dot) : rawName
  const ext = dot > 0 ? rawName.slice(dot) : ''
  const used = new Set(
    mapStore.mapData.resources.map(r => r.path.split('/').pop() || ''),
  )
  let fileName = rawName
  let seq = 2
  while (used.has(fileName)) fileName = `${base}-${seq++}${ext}`
  const relativePath = `assets/maps/${mapName}/images/${fileName}`
  await invoke<string>('copy_file_to_project', {
    src: srcPath,
    projectRoot,
    relativePath,
  })
  return relativePath
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
      :style="paletteViewportStyle"
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
          :key="`${entry.item.resource.id}:${entry.item.tileIndex}`"
          class="tile-cell"
          :class="{
            'tile-selected': entry.item.resourceIndex === mapStore.selectedResourceIndex
              && entry.item.tileIndex === mapStore.selectedTileIndex,
            'tile-box-selected': paletteSelection.has(tileKey(entry.item.resource.id, entry.item.tileIndex)),
            'tile-dragging': draggingKeys.has(tileKey(entry.item.resource.id, entry.item.tileIndex))
          }"
          :title="`${entry.item.resource.name} · #${entry.item.tileIndex}`"
          :style="[{ left: `${entry.left}px`, top: `${entry.top}px` }, paletteCellBackground(entry.item)]"
        />
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
          }, paletteCellBackground(ghost.item)]"
        />
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

.collapse-btn img {
  transition: transform 0.15s;
}

/* 展开时箭头朝下，收起时朝右 */
.collapse-rotated img {
  transform: rotate(90deg);
}

/* Unity 风格调色板：视口负责无限网格背景与裁剪，平面负责平移/缩放 */
.palette-viewport {
  position: relative;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  cursor: grab;
  background-color: rgb(30, 30, 30);
  background-image:
    linear-gradient(to right, rgba(255, 255, 255, 0.045) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255, 255, 255, 0.045) 1px, transparent 1px);
  background-repeat: repeat;
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

/* 框选矩形 */
.palette-box-select {
  position: absolute;
  border: 1px solid rgb(91, 251, 132);
  background: rgba(91, 251, 132, 0.12);
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
  background-color: rgb(52, 56, 66);
  box-shadow:
    0 8px 16px rgba(0, 0, 0, 0.55),
    inset 0 0 0 1px rgb(91, 251, 132);
  transform: scale(1.06);
  transform-origin: center;
  pointer-events: none;
  image-rendering: pixelated;
  opacity: 0.95;
}

.palette-plane {
  position: absolute;
  left: 0;
  top: 0;
  width: 0;
  height: 0;
  transform-origin: 0 0;
}

.tile-cell {
  position: absolute;
  width: 38px;
  height: 38px;
  box-sizing: border-box;
  background-color: transparent;
  border: none;
  cursor: default;
  transition: box-shadow 0.1s;
}

/* 悬停：细绿线。已选中的图块不参与悬停，避免点击后看起来还停在 hover 状态 */
.tile-cell:not(.tile-selected):not(.tile-box-selected):hover {
  box-shadow: inset 0 0 0 1px rgb(91, 199, 114);
}

.tile-selected {
  background-color: rgb(60, 65, 75);
  box-shadow: inset 0 0 0 1px rgb(91, 199, 114);
}

/* 选择工具选中的图块：2px 亮绿色内描边；优先级高于 hover，点下去立刻变粗线 */
.tile-cell.tile-box-selected {
  box-shadow: inset 0 0 0 2px rgb(91, 251, 132);
}

.resource-empty {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgb(80, 80, 80);
  font-size: 12px;
  pointer-events: none;
}
</style>
