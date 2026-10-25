<script setup lang="ts">
/**
 * 碰撞形状叠加层：画布逻辑坐标系内渲染 SVG 形状 + 屏幕恒定尺寸手柄。
 * 手柄尺寸与描边都按 1/zoom 换算成画布单位（缩放后正好是固定的屏幕像素），
 * 放大画布时锚点框不会跟着变粗、也不会因反向缩放的栅格化而发虚；
 * 命中判定参考地图编辑器碰撞锚点：锚点 > 边（插点）> 形状内部整体移动，
 * 保证"点在已存在的锚点上"永远优先于"插新锚点"。
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { pointInPolygon } from '../../utils/mapImageGeometry'
import type { SpriteCollisionShape } from '../../composables/useSpriteData'

const props = defineProps<{
  canvasW: number
  canvasH: number
  shape: SpriteCollisionShape
  zoom: number
  /** 禁用碰撞：形状仍显示但整体置灰（与地图编辑器禁用碰撞体同观感） */
  disabled?: boolean
}>()
const emit = defineEmits<{ update: [shape: SpriteCollisionShape] }>()

// Godot 编辑器钢蓝（边框/形状描边）；禁用时转为灰色
const COL = computed(() => (props.disabled ? '#8a8f98' : '#478CBF'))
// Scratch 风格半透明蓝填充；禁用时转为低透明度灰
const FILL = computed(() => (props.disabled ? 'rgba(160,160,170,0.14)' : 'rgba(76,151,255,0.28)'))
const snap = (v: number) => Math.round(v * 2) / 2

const rootRef = ref<HTMLDivElement | null>(null)
const hoverCursor = ref('default')

// ── 屏幕像素常量（与地图编辑器碰撞编辑一致） ──
/** 锚点视觉半径（屏幕像素）：直径 8px，缩放时保持恒定 */
const HANDLE_SIZE_PX = 8
/** 锚点命中半径（屏幕像素）：多边形顶点与地图编辑器一致取 12px */
const VERTEX_HIT_PX = 12
/** 矩形/胶囊手柄命中半径（屏幕像素）：略小一些，保证形状很小的时候仍能拖动整体 */
const SHAPE_HANDLE_HIT_PX = 10
/** 多边形边命中距离（屏幕像素） */
const EDGE_HIT_PX = 5

const viewZoom = computed(() => Math.max(0.001, props.zoom))
/** 手柄半边长 / 顶点圆半径（画布逻辑单位）：屏幕 8px 见方的锚点 */
const halfSize = computed(() => HANDLE_SIZE_PX / 2 / viewZoom.value)

// ── 各形状统一归一化为包围盒（矩形/胶囊手柄定位共用） ──
const box = computed(() => {
  const s = props.shape
  if (s.type === 'rect') {
    return { cx: s.cx, cy: s.cy, w: Math.max(0.5, s.w), h: Math.max(0.5, s.h) }
  }
  if (s.type === 'capsule') {
    const r = Math.max(0.5, s.radius)
    const h = Math.max(2 * r, s.height)
    return { cx: s.cx, cy: s.cy, w: 2 * r, h }
  }
  const xs = s.points.map(p => p[0])
  const ys = s.points.map(p => p[1])
  const x0 = Math.min(...xs)
  const x1 = Math.max(...xs)
  const y0 = Math.min(...ys)
  const y1 = Math.max(...ys)
  return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, w: Math.max(0.5, x1 - x0), h: Math.max(0.5, y1 - y0) }
})

const svgRect = computed(() => {
  const b = box.value
  return { x: b.cx - b.w / 2, y: b.cy - b.h / 2, width: b.w, height: b.h }
})

const svgCapsule = computed(() => {
  const b = box.value
  const s = props.shape
  const r = s.type === 'capsule' ? Math.max(0.5, s.radius) : Math.min(b.w, b.h) / 2
  return { x: b.cx - b.w / 2, y: b.cy - b.h / 2, width: b.w, height: b.h, rx: Math.min(r, b.w / 2, b.h / 2) }
})

const polyPointsStr = computed(() =>
  props.shape.type === 'polygon' ? props.shape.points.map(p => `${p[0]},${p[1]}`).join(' ') : '',
)

// ── 屏幕坐标 → 画布逻辑坐标（根元素被 zoom 变换，用自身 rect 反推） ──
/** 返回画布坐标 + 实际屏幕缩放倍率（命中容差按屏幕像素换算要用） */
function clientToCanvas(e: MouseEvent): { x: number; y: number; scale: number } | null {
  const el = rootRef.value
  if (!el) return null
  const r = el.getBoundingClientRect()
  if (r.width === 0) return null
  const scale = r.width / props.canvasW
  return { x: (e.clientX - r.left) / scale, y: (e.clientY - r.top) / scale, scale }
}

// ── 手柄定义 ──
type RectHandle = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w'
type CapsuleHandle = 'cap-top' | 'cap-bottom' | 'cap-side'
type DragKind = 'move' | RectHandle | CapsuleHandle | `vtx:${number}`

interface Handle {
  kind: DragKind
  x: number
  y: number
  /** 悬停/拖拽光标：方向缩放光标让抓取意图一目了然 */
  cursor: string
}

const RECT_HANDLE_ORDER: RectHandle[] = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']
const RECT_HANDLE_CURSOR: Record<RectHandle, string> = {
  nw: 'nwse-resize', se: 'nwse-resize',
  ne: 'nesw-resize', sw: 'nesw-resize',
  n: 'ns-resize', s: 'ns-resize',
  e: 'ew-resize', w: 'ew-resize',
}

const handles = computed<Handle[]>(() => {
  const s = props.shape
  const b = box.value
  const x0 = b.cx - b.w / 2
  const x1 = b.cx + b.w / 2
  const y0 = b.cy - b.h / 2
  const y1 = b.cy + b.h / 2
  if (s.type === 'rect') {
    const pos: Record<RectHandle, [number, number]> = {
      nw: [x0, y0], n: [b.cx, y0], ne: [x1, y0], e: [x1, b.cy],
      se: [x1, y1], s: [b.cx, y1], sw: [x0, y1], w: [x0, b.cy],
    }
    return RECT_HANDLE_ORDER.map(k => ({ kind: k, x: pos[k][0], y: pos[k][1], cursor: RECT_HANDLE_CURSOR[k] }))
  }
  if (s.type === 'capsule') {
    return [
      { kind: 'cap-top', x: b.cx, y: y0, cursor: 'ns-resize' },
      { kind: 'cap-bottom', x: b.cx, y: y1, cursor: 'ns-resize' },
      { kind: 'cap-side', x: x1, y: b.cy, cursor: 'ew-resize' },
    ]
  }
  // 多边形顶点：正常指针（对齐地图编辑器锚点，不用小手指）
  return s.points.map((p, i) => ({
    kind: `vtx:${i}` as DragKind,
    x: p[0],
    y: p[1],
    cursor: 'default',
  }))
})

// ── 命中判定（优先级：锚点 > 边 > 形状内部） ──
type Hit =
  | { kind: 'handle'; index: number }
  | { kind: 'edge'; index: number }
  | { kind: 'inside'; index: number }
  | { kind: 'none'; index: number }

function nearestHandle(p: { x: number; y: number }, scale: number): number {
  const tol = (props.shape.type === 'polygon' ? VERTEX_HIT_PX : SHAPE_HANDLE_HIT_PX) / scale
  let best = -1
  let bestDist = tol
  handles.value.forEach((h, i) => {
    const d = Math.hypot(h.x - p.x, h.y - p.y)
    if (d <= bestDist) {
      bestDist = d
      best = i
    }
  })
  return best
}

function pointToSegmentDistance(
  p: { x: number; y: number },
  a: { x: number; y: number },
  b: { x: number; y: number },
): number {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const lenSq = dx * dx + dy * dy
  if (lenSq === 0) return Math.hypot(p.x - a.x, p.y - a.y)
  const t = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / lenSq))
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy))
}

/** 最近的多边形边（边下标 = 起点顶点下标；最后一条边闭合回 points[0]） */
function nearestEdge(p: { x: number; y: number }, scale: number): number {
  const s = props.shape
  if (s.type !== 'polygon' || s.points.length < 2) return -1
  const tol = EDGE_HIT_PX / scale
  let best = -1
  let bestDist = tol
  for (let i = 0; i < s.points.length; i++) {
    const a = { x: s.points[i][0], y: s.points[i][1] }
    const b = s.points[(i + 1) % s.points.length]
    const d = pointToSegmentDistance(p, a, { x: b[0], y: b[1] })
    if (d < bestDist) {
      bestDist = d
      best = i
    }
  }
  return best
}

function isInside(p: { x: number; y: number }): boolean {
  const s = props.shape
  if (s.type === 'rect') {
    const b = box.value
    return Math.abs(p.x - b.cx) <= b.w / 2 && Math.abs(p.y - b.cy) <= b.h / 2
  }
  if (s.type === 'capsule') {
    const r = Math.max(0.5, s.radius)
    const h = Math.max(2 * r, s.height)
    const top = s.cy - h / 2 + r
    const bottom = s.cy + h / 2 - r
    const nearestY = Math.max(top, Math.min(bottom, p.y))
    return Math.hypot(p.x - s.cx, p.y - nearestY) <= r
  }
  return pointInPolygon({ x: p.x, y: p.y }, s.points.map(([x, y]) => ({ x, y })))
}

function hitTest(p: { x: number; y: number }, scale: number): Hit {
  const hi = nearestHandle(p, scale)
  if (hi >= 0) return { kind: 'handle', index: hi }
  const ei = nearestEdge(p, scale)
  if (ei >= 0) return { kind: 'edge', index: ei }
  if (isInside(p)) return { kind: 'inside', index: -1 }
  return { kind: 'none', index: -1 }
}

function cursorForHit(hit: Hit): string {
  if (hit.kind === 'handle') return handles.value[hit.index]?.cursor ?? 'default'
  if (hit.kind === 'edge') return 'copy'
  if (hit.kind === 'inside') return 'move'
  return 'default'
}

// ── 拖拽状态 ──
const dragKind = ref<DragKind | null>(null)
let dragStart: SpriteCollisionShape | null = null
/** 拖拽起点（画布逻辑坐标）：整体移动按总位移计算，避免逐帧累积误差 */
let dragOrigin: { x: number; y: number } | null = null
const selectedVtx = ref<number | null>(null)

function dragRect(s: Extract<SpriteCollisionShape, { type: 'rect' }>, kind: DragKind, m: { x: number; y: number }): SpriteCollisionShape {
  let x0 = s.cx - s.w / 2
  let x1 = s.cx + s.w / 2
  let y0 = s.cy - s.h / 2
  let y1 = s.cy + s.h / 2
  const mx = snap(m.x)
  const my = snap(m.y)
  switch (kind) {
    case 'nw': x0 = mx; y0 = my; break
    case 'n': y0 = my; break
    case 'ne': x1 = mx; y0 = my; break
    case 'e': x1 = mx; break
    case 'se': x1 = mx; y1 = my; break
    case 's': y1 = my; break
    case 'sw': x0 = mx; y1 = my; break
    case 'w': x0 = mx; break
  }
  const nx0 = Math.min(x0, x1)
  const nx1 = Math.max(x0, x1)
  const ny0 = Math.min(y0, y1)
  const ny1 = Math.max(y0, y1)
  return { type: 'rect', cx: (nx0 + nx1) / 2, cy: (ny0 + ny1) / 2, w: Math.max(0.5, nx1 - nx0), h: Math.max(0.5, ny1 - ny0) }
}

function dragCapsule(s: Extract<SpriteCollisionShape, { type: 'capsule' }>, kind: DragKind, m: { x: number; y: number }): SpriteCollisionShape {
  const r = Math.max(0.5, s.radius)
  const h = Math.max(2 * r, s.height)
  const top = s.cy - h / 2
  const bottom = s.cy + h / 2
  if (kind === 'cap-top') {
    const nt = snap(m.y)
    const nh = Math.max(2 * r, bottom - nt)
    return { ...s, cy: bottom - nh / 2, height: nh }
  }
  if (kind === 'cap-bottom') {
    const nb = snap(m.y)
    const nh = Math.max(2 * r, nb - top)
    return { ...s, cy: top + nh / 2, height: nh }
  }
  // cap-side：拖动改半径（以中心对称），高度不足 2r 时同步撑高
  const nr = Math.max(0.5, Math.abs(snap(m.x) - s.cx))
  return { ...s, radius: nr, height: Math.max(2 * nr, h) }
}

/** 开始拖拽：快照起点形状，后续按总位移计算 */
function beginDrag(kind: DragKind, startShape: SpriteCollisionShape, m: { x: number; y: number }) {
  dragKind.value = kind
  dragStart = JSON.parse(JSON.stringify(startShape))
  dragOrigin = m
  selectedVtx.value = kind.startsWith('vtx:') ? Number(kind.slice(4)) : null
}

/** 统一入口：按命中优先级决定 拖锚点 / 边插点 / 整体移动，空白处清除选中 */
function onRootDown(e: MouseEvent) {
  if (e.button !== 0) return // 中键放行给画布平移
  const m = clientToCanvas(e)
  if (!m) return
  const hit = hitTest(m, m.scale)
  if (hit.kind === 'none') {
    selectedVtx.value = null
    return
  }
  e.stopPropagation()
  e.preventDefault()
  if (hit.kind === 'inside') {
    hoverCursor.value = 'move'
    beginDrag('move', props.shape, m)
    return
  }
  if (hit.kind === 'handle') {
    const h = handles.value[hit.index]
    hoverCursor.value = h.cursor
    beginDrag(h.kind, props.shape, m)
    return
  }
  // 命中边：插入锚点并直接拖动它（与地图编辑器一致，插点即编辑）
  if (props.shape.type !== 'polygon') return
  const points = props.shape.points.map(p => [...p] as [number, number])
  points.splice(hit.index + 1, 0, [snap(m.x), snap(m.y)])
  const next: SpriteCollisionShape = { type: 'polygon', points }
  emit('update', next)
  hoverCursor.value = 'copy'
  beginDrag(`vtx:${hit.index + 1}`, next, m)
}

function onRootMove(e: MouseEvent) {
  if (dragKind.value) return // 拖拽中保持当前光标，避免抖动
  // 中键平移时保持画布 grabbing 光标（根元素覆盖整个画布，会盖住父级光标）
  if (e.buttons & 4) {
    hoverCursor.value = 'grabbing'
    return
  }
  const m = clientToCanvas(e)
  if (!m) return
  hoverCursor.value = cursorForHit(hitTest(m, m.scale))
}

function onRootLeave() {
  if (!dragKind.value) hoverCursor.value = 'default'
}

/** 整体平移形状（0.5px 吸附绝对坐标） */
function translateShape(s: SpriteCollisionShape, dx: number, dy: number): SpriteCollisionShape {
  if (s.type === 'polygon') {
    return {
      type: 'polygon',
      points: s.points.map(([x, y]) => [snap(x + dx), snap(y + dy)] as [number, number]),
    }
  }
  return { ...s, cx: snap(s.cx + dx), cy: snap(s.cy + dy) }
}

function onDragMove(e: MouseEvent) {
  if (!dragKind.value || !dragStart || !dragOrigin) return
  const m = clientToCanvas(e)
  if (!m) return
  const kind = dragKind.value
  const start = dragStart
  if (kind === 'move') {
    emit('update', translateShape(start, m.x - dragOrigin.x, m.y - dragOrigin.y))
    return
  }
  if (kind.startsWith('vtx:')) {
    if (start.type !== 'polygon') return
    const i = Number(kind.slice(4))
    const points = start.points.map(p => [...p] as [number, number])
    points[i] = [snap(m.x), snap(m.y)]
    emit('update', { type: 'polygon', points })
    return
  }
  if (start.type === 'rect') emit('update', dragRect(start, kind, m))
  else if (start.type === 'capsule') emit('update', dragCapsule(start, kind, m))
}

function onDragUp() {
  dragKind.value = null
  dragStart = null
  dragOrigin = null
  hoverCursor.value = 'default'
}

function onKeyDown(e: KeyboardEvent) {
  if (props.shape.type !== 'polygon') return
  const t = e.target as HTMLElement | null
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return
  if (e.key === 'Escape') {
    selectedVtx.value = null
    return
  }
  if (selectedVtx.value == null) return
  if (e.key !== 'Delete' && e.key !== 'Backspace') return
  if (props.shape.points.length <= 3) return
  const points = props.shape.points.filter((_, i) => i !== selectedVtx.value)
  selectedVtx.value = null
  emit('update', { type: 'polygon', points })
}

onMounted(() => window.addEventListener('mousemove', onDragMove))
onMounted(() => window.addEventListener('mouseup', onDragUp))
onMounted(() => window.addEventListener('keydown', onKeyDown))
onBeforeUnmount(() => window.removeEventListener('mousemove', onDragMove))
onBeforeUnmount(() => window.removeEventListener('mouseup', onDragUp))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeyDown))
</script>

<template>
  <div
    ref="rootRef"
    class="cso-root"
    :class="{ 'cso-disabled': disabled }"
    :style="{ width: `${canvasW}px`, height: `${canvasH}px`, cursor: hoverCursor }"
    @mousedown="onRootDown"
    @mousemove="onRootMove"
    @mouseleave="onRootLeave"
  >
    <svg
      class="cso-svg"
      :width="canvasW"
      :height="canvasH"
      :viewBox="`0 0 ${canvasW} ${canvasH}`"
    >
      <!-- 形状本体：只负责绘制，交互统一由根元素命中判定（避免细小手柄抢不到事件） -->
      <template v-if="shape.type === 'rect'">
        <rect
          v-bind="svgRect"
          :fill="FILL"
          :stroke="COL"
          :stroke-width="1.5 / viewZoom"
        />
      </template>
      <!-- 胶囊（rx=半径 → 竖直胶囊外形） -->
      <template v-else-if="shape.type === 'capsule'">
        <rect
          v-bind="svgCapsule"
          :fill="FILL"
          :stroke="COL"
          :stroke-width="1.5 / viewZoom"
        />
      </template>
      <!-- 多边形 -->
      <template v-else>
        <polygon
          :points="polyPointsStr"
          :fill="FILL"
          :stroke="COL"
          :stroke-width="1.5 / viewZoom"
        />
      </template>

      <!-- 手柄：尺寸与描边都按 1/zoom 换算成画布单位，屏幕尺寸恒定、缩放不增粗 -->
      <g class="cso-handle-group">
        <!-- 矩形 8 手柄 -->
        <template v-if="shape.type === 'rect'">
          <rect
            v-for="(h, i) in handles"
            :key="`h-${i}`"
            class="cso-handle"
            :x="h.x - halfSize"
            :y="h.y - halfSize"
            :width="halfSize * 2"
            :height="halfSize * 2"
            :rx="halfSize * 0.3"
            :stroke-width="1 / viewZoom"
          />
        </template>

        <!-- 胶囊手柄：顶/底改总高，侧边改半径 -->
        <template v-else-if="shape.type === 'capsule'">
          <template v-for="(h, i) in handles" :key="`c-${i}`">
            <circle
              v-if="h.kind === 'cap-side'"
              class="cso-handle"
              :cx="h.x"
              :cy="h.y"
              :r="halfSize"
              :stroke-width="1 / viewZoom"
            />
            <rect
              v-else
              class="cso-handle"
              :x="h.x - halfSize"
              :y="h.y - halfSize"
              :width="halfSize * 2"
              :height="halfSize * 2"
              :rx="halfSize * 0.3"
              :stroke-width="1 / viewZoom"
            />
          </template>
        </template>

        <!-- 多边形顶点 -->
        <template v-else>
          <template v-for="(p, i) in shape.points" :key="`v-${i}`">
            <circle
              v-if="selectedVtx === i"
              :cx="p[0]"
              :cy="p[1]"
              :r="halfSize * 1.8"
              fill="rgba(71,140,191,0.55)"
            />
            <circle
              class="cso-handle"
              :class="{ 'cso-vtx-sel': selectedVtx === i }"
              :cx="p[0]"
              :cy="p[1]"
              :r="halfSize"
              :stroke-width="1 / viewZoom"
            />
          </template>
        </template>
      </g>
    </svg>
  </div>
</template>

<style scoped>
.cso-root {
  position: absolute;
  left: 0;
  top: 0;
  z-index: 3;
  pointer-events: auto;
  user-select: none;
}
.cso-svg {
  position: absolute;
  left: 0;
  top: 0;
  overflow: visible;
  pointer-events: none;
}
/* 手柄：白底深描边（描边宽度由模板按 1/zoom 换算，屏幕恒定 1px） */
.cso-handle {
  fill: #ffffff;
  stroke: #23272e;
}
.cso-vtx-sel {
  fill: #478cbf;
  stroke: #ffffff;
}
/* 禁用碰撞：形状整体置灰（手柄半透明，仍可编辑） */
.cso-disabled .cso-handle-group { opacity: 0.5; }
</style>
