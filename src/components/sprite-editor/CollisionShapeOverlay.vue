<script setup lang="ts">
/**
 * 碰撞形状叠加层：画布逻辑坐标系内渲染 SVG 形状 + 屏幕恒定尺寸手柄。
 * 交互参考 Godot CollisionShape2D 编辑（矩形 8 手柄 / 胶囊顶底改高侧边改半径），
 * 多边形顶点编辑复用地图 CollisionEditor 惯例（拖点 / 点边插点 / Delete 删点）。
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
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
function clientToCanvas(e: MouseEvent): { x: number; y: number } | null {
  const el = rootRef.value
  if (!el) return null
  const r = el.getBoundingClientRect()
  if (r.width === 0) return null
  const scale = r.width / props.canvasW
  return { x: (e.clientX - r.left) / scale, y: (e.clientY - r.top) / scale }
}

// ── 拖拽状态 ──
type RectHandle = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w'
type CapsuleHandle = 'cap-top' | 'cap-bottom' | 'cap-side'
type DragKind = 'move' | RectHandle | CapsuleHandle | `vtx:${number}`
const dragKind = ref<DragKind | null>(null)
let dragStart: SpriteCollisionShape | null = null
/** 拖拽起点（画布逻辑坐标）：整体移动按总位移计算，避免逐帧累积误差 */
let dragOrigin: { x: number; y: number } | null = null
const selectedVtx = ref<number | null>(null)

const rectHandles = computed<{ kind: RectHandle; x: number; y: number }[]>(() => {
  if (props.shape.type !== 'rect') return []
  const b = box.value
  const x0 = b.cx - b.w / 2
  const x1 = b.cx + b.w / 2
  const y0 = b.cy - b.h / 2
  const y1 = b.cy + b.h / 2
  return [
    { kind: 'nw', x: x0, y: y0 }, { kind: 'n', x: b.cx, y: y0 }, { kind: 'ne', x: x1, y: y0 },
    { kind: 'e', x: x1, y: b.cy }, { kind: 'se', x: x1, y: y1 }, { kind: 's', x: b.cx, y: y1 },
    { kind: 'sw', x: x0, y: y1 }, { kind: 'w', x: x0, y: b.cy },
  ]
})

const capsuleHandles = computed<{ kind: CapsuleHandle; x: number; y: number }[]>(() => {
  const b = box.value
  const y0 = b.cy - b.h / 2
  const y1 = b.cy + b.h / 2
  return [
    { kind: 'cap-top', x: b.cx, y: y0 },
    { kind: 'cap-bottom', x: b.cx, y: y1 },
    { kind: 'cap-side', x: b.cx + b.w / 2, y: b.cy },
  ]
})

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

/** 点击形状内部：整体移动（并清除顶点选中） */
function onShapeDown(e: MouseEvent) {
  if (e.button !== 0) return
  e.stopPropagation()
  e.preventDefault()
  const m = clientToCanvas(e)
  if (!m) return
  dragKind.value = 'move'
  dragStart = JSON.parse(JSON.stringify(props.shape))
  dragOrigin = m
  selectedVtx.value = null
}

function onHandleDown(kind: DragKind, e: MouseEvent) {
  if (e.button !== 0) return
  e.stopPropagation()
  e.preventDefault()
  dragKind.value = kind
  dragStart = JSON.parse(JSON.stringify(props.shape))
  dragOrigin = clientToCanvas(e)
  if (kind.startsWith('vtx:')) selectedVtx.value = Number(kind.slice(4))
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
}

/** 点边插入顶点（edgeIdx = 边起点顶点下标；最后一条边 = points[n-1]→points[0]） */
function insertVertex(edgeIdx: number, e: MouseEvent) {
  if (props.shape.type !== 'polygon') return
  e.stopPropagation()
  e.preventDefault()
  const m = clientToCanvas(e)
  if (!m) return
  const points = props.shape.points.map(p => [...p] as [number, number])
  points.splice(edgeIdx + 1, 0, [snap(m.x), snap(m.y)])
  selectedVtx.value = edgeIdx + 1
  emit('update', { type: 'polygon', points })
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

/** 手柄体自身只做反向缩放（定位由外层 anchor 负责，居中偏移在 CSS） */
function handleStyle() {
  return { transform: `scale(${1 / props.zoom})` }
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
    :style="{ width: `${canvasW}px`, height: `${canvasH}px` }"
  >
    <svg
      class="cso-svg"
      :width="canvasW"
      :height="canvasH"
      :viewBox="`0 0 ${canvasW} ${canvasH}`"
    >
      <!-- 矩形 -->
      <template v-if="shape.type === 'rect'">
        <rect
          v-bind="svgRect"
          :fill="FILL"
          :stroke="COL"
          stroke-width="1.5"
          vector-effect="non-scaling-stroke"
          style="pointer-events: auto; cursor: move" @mousedown="onShapeDown"
        />
      </template>
      <!-- 胶囊（rx=半径 → 竖直胶囊外形） -->
      <template v-else-if="shape.type === 'capsule'">
        <rect
          v-bind="svgCapsule"
          :fill="FILL"
          :stroke="COL"
          stroke-width="1.5"
          vector-effect="non-scaling-stroke"
          style="pointer-events: auto; cursor: move" @mousedown="onShapeDown"
        />
      </template>
      <!-- 多边形：可见细线 + 透明加粗命中线（点边插点） -->
      <template v-else>
        <polygon
          :points="polyPointsStr"
          :fill="FILL"
          :stroke="COL"
          stroke-width="1.5"
          vector-effect="non-scaling-stroke"
          style="pointer-events: auto; cursor: move" @mousedown="onShapeDown"
        />
        <polyline
          v-for="i in shape.points.length"
          :key="`hit-${i}`"
          :points="`${shape.points[i - 1].join(',')} ${shape.points[i % shape.points.length].join(',')}`"
          fill="none"
          stroke="transparent"
          stroke-width="12"
          vector-effect="non-scaling-stroke"
          style="pointer-events: stroke; cursor: copy"
          @click="insertVertex(i - 1, $event)"
        />
      </template>
    </svg>

    <!-- 矩形 8 手柄 -->
    <template v-if="shape.type === 'rect'">
      <div
        v-for="h in rectHandles"
        :key="h.kind"
        class="cso-anchor"
        :style="{ left: `${h.x}px`, top: `${h.y}px` }"
      >
        <div
          class="cso-handle"
          :style="handleStyle()"
          @mousedown="onHandleDown(h.kind, $event)"
        ></div>
      </div>
    </template>

    <!-- 胶囊手柄：顶/底改总高，侧边改半径 -->
    <template v-else-if="shape.type === 'capsule'">
      <div
        v-for="h in capsuleHandles"
        :key="h.kind"
        class="cso-anchor"
        :style="{ left: `${h.x}px`, top: `${h.y}px` }"
      >
        <div
          class="cso-handle"
          :class="{ 'cso-handle-round': h.kind === 'cap-side' }"
          :style="handleStyle()"
          @mousedown="onHandleDown(h.kind, $event)"
        ></div>
      </div>
    </template>

    <!-- 多边形顶点 -->
    <template v-else>
      <div
        v-for="(p, i) in shape.points"
        :key="`vtx-${i}`"
        class="cso-anchor"
        :style="{ left: `${p[0]}px`, top: `${p[1]}px` }"
      >
        <div
          class="cso-handle cso-vtx"
          :class="{ 'cso-vtx-sel': selectedVtx === i }"
          :style="handleStyle()"
          @mousedown="onHandleDown(`vtx:${i}`, $event)"
        ></div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.cso-root {
  position: absolute;
  left: 0;
  top: 0;
  pointer-events: none;
  z-index: 3;
}
.cso-svg {
  position: absolute;
  left: 0;
  top: 0;
  overflow: visible;
  pointer-events: none;
}
/* 手柄锚点：位置=画布逻辑坐标，手柄体反向缩放保持屏幕尺寸恒定 */
.cso-anchor {
  position: absolute;
  width: 0;
  height: 0;
  z-index: 4;
}
.cso-handle {
  position: absolute;
  left: -4.5px;
  top: -4.5px;
  width: 9px;
  height: 9px;
  border-radius: 2px;
  background: #ffffff;
  border: 1px solid #23272e;
  transform-origin: center center;
  pointer-events: auto;
  cursor: default;
  box-sizing: border-box;
}
.cso-handle-round {
  border-radius: 50%;
}
.cso-vtx {
  border-radius: 50%;
  width: 8px;
  height: 8px;
  left: -4px;
  top: -4px;
}
.cso-vtx-sel {
  background: #478cbf;
  border-color: #ffffff;
  box-shadow: 0 0 0 2px rgba(71, 140, 191, 0.55);
}
/* 禁用碰撞：形状整体置灰（手柄半透明，仍可编辑） */
.cso-disabled .cso-handle { opacity: 0.5; }
</style>
