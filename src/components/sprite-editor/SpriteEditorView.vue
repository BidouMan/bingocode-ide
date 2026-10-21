<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useResourceStore } from '../../stores/resource'
import { useEditorStore } from '../../stores/editor'
import type { SpriteData, SpriteAnimation } from '../../composables/useSpriteData'
import { readSpriteFromPath, revokeSpriteUrls, saveSpriteConfig, saveBsfManifest } from '../../composables/useSpriteData'
import type { SpriteCollisionShape } from '../../composables/useSpriteData'
import { appendFramesToSprite } from '../../composables/appendSpriteFrames'
import FrameUploadDrawer from './FrameUploadDrawer.vue'
import CollisionShapeOverlay from './CollisionShapeOverlay.vue'

const emit = defineEmits<{
  /** 造型列表抽屉：打开绘制页为当前角色绘制新帧（编辑模式，自动新建空白帧） */
  openPaintAppend: []
  /** 双击帧卡片：打开绘制页编辑该帧 */
  openPaintEdit: [index: number]
  /** 造型列表抽屉：打开内置素材选帧页 */
  openFramePicker: []
}>()

import iconPrev from '../../assets/icons/btn_preview_prev.svg'
import iconPlay from '../../assets/icons/btn_preview_play.svg'
import iconPause from '../../assets/icons/btn_preview_pause.svg'
import iconNext from '../../assets/icons/btn_preview_next.svg'
import iconScale from '../../assets/icons/btn_preview_scale.svg'
import iconChangeBg from '../../assets/icons/btn_preview_change_bg.svg'
import iconAdd from '../../assets/icons/btn_preview_add.svg'
import iconLoop from '../../assets/icons/anim_loop.svg'
import iconLoopOff from '../../assets/icons/anim_loop_off.svg'
import iconCenterPivot from '../../assets/icons/中心点.svg'
import iconResetAnchor from '../../assets/icons/重置锚点.svg'
import iconMarker from '../../assets/icons/标记.svg'
import iconMarkerRaw from '../../assets/icons/标记.svg?raw'

const resourceStore = useResourceStore()
const editorStore = useEditorStore()

const imageRenderingStyle = computed(() => {
  return editorStore.renderMode === 'pixelated' ? 'pixelated' : 'auto'
})

const currentSprite = ref<SpriteData | null>(null)
const currentSpritePath = ref('')
const selectedFrameIndex = ref(0)
const selectedAnim = ref<SpriteAnimation | null>(null)
const isPlaying = ref(false)
const previewScale = ref(1)
const fpsValue = ref(10)
const costumeHighlightIndex = ref(0)
const canvasDisplayIndex = ref(0)
const previewBgIndex = ref(0)

// 画布缩放和平移
const canvasZoom = ref(1)
const canvasPanX = ref(0)
const canvasPanY = ref(0)
const isPanning = ref(false)
const panStartX = ref(0)
const panStartY = ref(0)
const panStartOffsetX = ref(0)
const panStartOffsetY = ref(0)
const canvasRef = ref<HTMLDivElement | null>(null)

const costumeContextMenu = ref<{ show: boolean; x: number; y: number; index: number }>({ show: false, x: 0, y: 0, index: 0 })
const animContextMenu = ref<{ show: boolean; x: number; y: number; name: string }>({ show: false, x: 0, y: 0, name: '' })
const renamingAnim = ref<string | null>(null)
const renameInputRef = ref<HTMLInputElement | null>(null)
let playTimer: ReturnType<typeof setInterval> | null = null

watch(
  () => resourceStore.selectedSpriteId,
  (id) => {
    if (!id) return
    const item = resourceStore.sprites.find(s => s.id === id)
    if (item && item.path) loadSprite(item)
  },
  { immediate: true }
)

// 自动保存：每次修改后写回 config.json
let saveTimer: ReturnType<typeof setTimeout> | null = null
// 默认渲染帧是否被改过：保存成功后据此刷新资源面板缩略图（其他字段修改不需要）
let defaultFrameDirty = false
function scheduleSave() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(async () => {
    if (!currentSprite.value || !currentSpritePath.value) return
    try {
      // .bsf 角色写回 manifest.json（clips），旧目录角色写回 config.json（segments）
      if (currentSprite.value.bsf) {
        await saveBsfManifest(currentSpritePath.value, currentSprite.value)
      } else {
        await saveSpriteConfig(currentSpritePath.value, currentSprite.value)
      }
      if (defaultFrameDirty) {
        defaultFrameDirty = false
        // 缩略图走磁盘 manifest/config，必须等写盘完成后再生效
        if (resourceStore.selectedSpriteId) {
          resourceStore.bumpSpriteThumb(resourceStore.selectedSpriteId)
        }
      }
    } catch (e) {
      console.error('自动保存角色失败:', e)
    }
  }, 300)
}

async function loadSprite(item: { id: string; name: string; path: string }) {
  // 防重复加载：同一个角色不重新加载
  if (currentSpritePath.value === item.path && currentSprite.value) return
  try {
    // 释放旧的 ObjectURL 防止内存泄漏
    revokeSpriteUrls(currentSprite.value)
    // 图片角色 → 单帧；.bsf 目录 → manifest + sheet 裁帧；.bgs 目录 → config.json
    currentSprite.value = await readSpriteFromPath(item.path)
    currentSpritePath.value = item.path
    // 初始定位到持久化的默认渲染帧（引擎初始渲染与缩略图同源）
    const initialFrame = currentSprite.value.defaultFrameIndex ?? 0
    selectedFrameIndex.value = initialFrame
    canvasDisplayIndex.value = initialFrame
    costumeHighlightIndex.value = initialFrame
    defaultFrameDirty = false
    selectedAnim.value = null
    stopAnimation()
    annoScope.value = 'all'
    activeAnnoLayer.value = 'pivot'
    annoDefaultPivot.value = currentSprite.value.bsf
      ? { ...currentSprite.value.bsf.pivot }
      : null
    canvasZoom.value = 1
    canvasPanX.value = 0
    canvasPanY.value = 0
    if (currentSprite.value.animations.length > 0) {
      const first = currentSprite.value.animations[0]
      selectedAnim.value = first
      fpsValue.value = first.fps || 10
      startAnimation(first)
    }
  } catch (e) {
    console.error('Failed to load sprite:', e)
  }
}

function selectFrame(index: number) {
  stopAnimation()
  selectedFrameIndex.value = index
  costumeHighlightIndex.value = index
  canvasDisplayIndex.value = index
  markDefaultFrame(index)
}

/** 从磁盘强制重载当前角色（追加帧后刷新帧列表；绕过 loadSprite 防重复守卫） */
async function reloadSprite() {
  const id = resourceStore.selectedSpriteId
  if (!id) return
  const item = resourceStore.sprites.find(s => s.id === id)
  if (!item || !item.path) return
  currentSpritePath.value = ''
  await loadSprite(item)
}

/** 抽屉上传的图片帧 → 追加到当前角色并刷新 */
async function onImportFrameBlobs(blobs: Blob[]) {
  if (!currentSpritePath.value || !currentSprite.value || blobs.length === 0) return
  const oldCount = currentSprite.value.frames.length
  try {
    const res = await appendFramesToSprite(currentSpritePath.value, blobs)
    const id = resourceStore.selectedSpriteId
    if (res.newPath && id) {
      resourceStore.updateItemPath(id, res.newPath)
      currentSpritePath.value = res.newPath
    }
    if (id) resourceStore.bumpSpriteThumb(id)
    await reloadSprite()
    if (oldCount < (currentSprite.value?.frames.length ?? 0)) {
      selectFrame(oldCount)
    }
  } catch (e) {
    console.error('[SpriteEditor] 追加帧失败:', e)
  }
}

defineExpose({ reload: reloadSprite })

/** 用户手动选中帧 = 设为默认渲染帧（引擎不播动画时显示它，缩略图同步；对齐 Scratch"当前造型"语义） */
function markDefaultFrame(index: number) {
  if (!currentSprite.value) return
  if (currentSprite.value.defaultFrameIndex === index) return
  currentSprite.value.defaultFrameIndex = index
  defaultFrameDirty = true
  scheduleSave()
}

function selectAnimation(anim: SpriteAnimation) {
  selectedAnim.value = anim
  fpsValue.value = anim.fps || 10
  startAnimation(anim)
}

function startAnimation(anim: SpriteAnimation) {
  stopAnimation()
  isPlaying.value = true
  selectedFrameIndex.value = anim.start - 1
  restartTimer()
}

function restartTimer() {
  if (playTimer) { clearInterval(playTimer); playTimer = null }
  if (!isPlaying.value || !selectedAnim.value) return
  const interval = 1000 / Math.max(fpsValue.value, 1)
  playTimer = setInterval(() => {
    if (!currentSprite.value || !selectedAnim.value) return
    selectedFrameIndex.value++
    if (selectedFrameIndex.value > selectedAnim.value.end - 1) {
      if (selectedAnim.value.loop !== false) {
        selectedFrameIndex.value = selectedAnim.value.start - 1
      } else {
        stopAnimation()
      }
    }
  }, interval)
}

function stopAnimation() {
  isPlaying.value = false
  if (playTimer) { clearInterval(playTimer); playTimer = null }
}

function togglePlay() {
  if (isPlaying.value) stopAnimation()
  else if (selectedAnim.value) startAnimation(selectedAnim.value)
}

function prevFrame() {
  if (!currentSprite.value) return
  stopAnimation()
  selectedFrameIndex.value = Math.max(0, selectedFrameIndex.value - 1)
  canvasDisplayIndex.value = selectedFrameIndex.value
  costumeHighlightIndex.value = selectedFrameIndex.value
  markDefaultFrame(selectedFrameIndex.value)
}

function nextFrame() {
  if (!currentSprite.value) return
  stopAnimation()
  selectedFrameIndex.value = Math.min(currentSprite.value.frames.length - 1, selectedFrameIndex.value + 1)
  canvasDisplayIndex.value = selectedFrameIndex.value
  costumeHighlightIndex.value = selectedFrameIndex.value
  markDefaultFrame(selectedFrameIndex.value)
}

function toggleScale() {
  previewScale.value = previewScale.value === 1 ? 2 : 1
}

function changeBg() {
  previewBgIndex.value = (previewBgIndex.value + 1) % 3
}

// 画布滚轮缩放 (以鼠标位置为中心)
function onCanvasWheel(e: WheelEvent) {
  e.preventDefault()
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  // 鼠标相对于画布中心的偏移
  const mouseX = e.clientX - rect.left - rect.width / 2
  const mouseY = e.clientY - rect.top - rect.height / 2

  const oldZoom = canvasZoom.value
  const delta = e.deltaY > 0 ? 0.9 : 1.1
  const newZoom = Math.min(32, Math.max(0.1, oldZoom * delta))

  // 以鼠标位置为中心缩放: 保持鼠标下的像素点不动
  canvasPanX.value = mouseX - (mouseX - canvasPanX.value) * (newZoom / oldZoom)
  canvasPanY.value = mouseY - (mouseY - canvasPanY.value) * (newZoom / oldZoom)
  canvasZoom.value = newZoom
}

// 中键按下开始平移
function onCanvasMouseDown(e: MouseEvent) {
  if (e.button === 1) {
    e.preventDefault()
    e.stopPropagation()
    isPanning.value = true
    panStartX.value = e.clientX
    panStartY.value = e.clientY
    panStartOffsetX.value = canvasPanX.value
    panStartOffsetY.value = canvasPanY.value
  }
}

function onCanvasMouseMove(e: MouseEvent) {
  if (!isPanning.value) return
  canvasPanX.value = panStartOffsetX.value + (e.clientX - panStartX.value)
  canvasPanY.value = panStartOffsetY.value + (e.clientY - panStartY.value)
}

function onCanvasMouseUp(e: MouseEvent) {
  if (e.button === 1) {
    isPanning.value = false
  }
}

function onGlobalMouseUp(e: MouseEvent) {
  if (e.button === 1) {
    isPanning.value = false
  }
}

// 双击重置画布
function resetCanvas() {
  canvasZoom.value = 1
  canvasPanX.value = 0
  canvasPanY.value = 0
}

// ═══ 中心点标注（仅 .bsf 角色：manifest 带 pivot 元数据） ═══

/** 编辑作用域：all = 改统一值（全部帧生效）；one = 写当前帧覆盖 */
const annoScope = ref<'all' | 'one'>('all')
const isPivotDragging = ref(false)
/** 加载时快照的默认统一 pivot（「重置」按钮的恢复目标） */
const annoDefaultPivot = ref<{ x: number; y: number } | null>(null)

const canAnno = computed(() => !!currentSprite.value?.bsf)

/** 正在标注的帧 = 画布显示帧（动画播放时画布停在选中帧） */
const annoFrameIndex = computed(() => canvasDisplayIndex.value)

/** 第 i 帧的有效中心点：帧级覆盖优先，缺省回退统一值 */
function effPivot(i: number): { x: number; y: number } | null {
  const bsf = currentSprite.value?.bsf
  if (!bsf || i < 0 || i >= bsf.frames.length) return null
  return bsf.frames[i].pivot || bsf.pivot
}

function hasPivotOverride(i: number): boolean {
  return !!currentSprite.value?.bsf?.frames[i]?.pivot
}

const annoPivot = computed(() => effPivot(annoFrameIndex.value))

function setPivot(p: { x: number; y: number }) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  if (annoScope.value === 'all') {
    bsf.pivot = { x: p.x, y: p.y }
  } else {
    const f = bsf.frames[annoFrameIndex.value]
    if (f) f.pivot = { x: p.x, y: p.y }
  }
  scheduleSave()
}

function clearPivotOverride() {
  const f = currentSprite.value?.bsf?.frames[annoFrameIndex.value]
  if (!f) return
  delete f.pivot
  scheduleSave()
}

/** 重置：统一值回到加载时快照，并清除全部帧的单帧覆盖 */
function resetAnno() {
  const bsf = currentSprite.value?.bsf
  if (!bsf || !annoDefaultPivot.value) return
  bsf.pivot = { ...annoDefaultPivot.value }
  for (const f of bsf.frames) delete f.pivot
  scheduleSave()
}

// ═══ 碰撞标注（仅 .bsf；无自定义 = 引擎自动碰撞，学生默认路径） ═══

/** 当前激活的标注图层：中心 / 碰撞 / 标记（单选，同一套画布框架） */
const activeAnnoLayer = ref<'pivot' | 'collision' | 'marker'>('pivot')

/** 第 i 帧的有效碰撞形状：帧覆盖 > 统一值 > null（自动碰撞） */
function effCollision(i: number): SpriteCollisionShape | null {
  const bsf = currentSprite.value?.bsf
  if (!bsf || i < 0 || i >= bsf.frames.length) return null
  return bsf.frames[i].collision ?? bsf.collision ?? null
}

function hasCollisionOverride(i: number): boolean {
  return !!currentSprite.value?.bsf?.frames[i]?.collision
}

const effCol = computed(() => effCollision(annoFrameIndex.value))

/**
 * 画布显示用碰撞形状：自定义优先；自动态显示当前帧内容框
 * （= 引擎自动碰撞实际用的框，所见即所得；拖动手柄会立即转为自定义矩形）
 */
const collisionDisplay = computed<SpriteCollisionShape>(() =>
  effCol.value ?? frameContentCollision(),
)

function setCollision(shape: SpriteCollisionShape) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  if (annoScope.value === 'all') {
    bsf.collision = shape
  } else {
    const f = bsf.frames[annoFrameIndex.value]
    if (f) f.collision = shape
  }
  scheduleSave()
}

function onCollisionUpdate(shape: SpriteCollisionShape) {
  setCollision(shape)
}

function clearCollisionOverride() {
  const f = currentSprite.value?.bsf?.frames[annoFrameIndex.value]
  if (!f) return
  delete f.collision
  scheduleSave()
}

/** 自动：删除自定义碰撞（统一值 + 全部帧覆盖），回引擎内容包围盒默认 */
function resetCollisionToAuto() {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  delete bsf.collision
  for (const f of bsf.frames) delete f.collision
  scheduleSave()
}

/** 当前帧内容框（画布坐标）→ 自定义碰撞初值：与自动碰撞行为一致起步 */
function frameContentCollision(): SpriteCollisionShape {
  const bsf = currentSprite.value!.bsf!
  const f = bsf.frames[annoFrameIndex.value]
  return {
    type: 'rect',
    cx: f.offset.x + f.rect.w / 2,
    cy: f.offset.y + f.rect.h / 2,
    w: f.rect.w,
    h: f.rect.h,
  }
}

function activateAnnoLayer(layer: 'pivot' | 'collision' | 'marker') {
  activeAnnoLayer.value = layer
  if (layer === 'collision') {
    const bsf = currentSprite.value?.bsf
    if (!bsf) return
    // 首次启用：以当前帧内容框初始化统一碰撞（行为与自动一致，用户在此基础上调）
    if (!bsf.collision && !bsf.frames[annoFrameIndex.value]?.collision) {
      bsf.collision = frameContentCollision()
      scheduleSave()
    }
    return
  }
  if (layer === 'marker') {
    const bsf = currentSprite.value?.bsf
    if (!bsf) return
    // 首次启用：默认创建一个标记（内容框中心），选中待编辑
    if (markerNames.value.length === 0) {
      addMarker()
    } else if (!selMarkerName.value || !markerNames.value.includes(selMarkerName.value)) {
      selMarkerName.value = markerNames.value[0]
    }
  }
}

/** 形状类型互转：保持当前包围盒中心/范围（Godot 无此机制，对用户友好）；自动态以当前帧内容框为基准 */
function convertCollisionType(type: 'rect' | 'capsule' | 'polygon') {
  const cur = effCol.value ?? frameContentCollision()
  if (cur.type === type && effCol.value) return
  const b = collisionBBox(cur)
  const cx = Math.round(((b.x0 + b.x1) / 2) * 2) / 2
  const cy = Math.round(((b.y0 + b.y1) / 2) * 2) / 2
  const w = Math.max(0.5, Math.round((b.x1 - b.x0) * 2) / 2)
  const h = Math.max(0.5, Math.round((b.y1 - b.y0) * 2) / 2)
  if (type === 'rect') {
    setCollision({ type: 'rect', cx, cy, w, h })
  } else if (type === 'capsule') {
    const r = Math.max(0.5, Math.min(w, h) / 2)
    setCollision({ type: 'capsule', cx, cy, radius: r, height: Math.max(2 * r, h) })
  } else {
    const x0 = cx - w / 2
    const x1 = cx + w / 2
    const y0 = cy - h / 2
    const y1 = cy + h / 2
    setCollision({
      type: 'polygon',
      points: [[x0, y0], [x1, y0], [x1, y1], [x0, y1]].map(
        ([x, y]) => [Math.round(x * 2) / 2, Math.round(y * 2) / 2] as [number, number],
      ),
    })
  }
}

/** 碰撞形状 → 画布系 AABB（与引擎 _collision_canvas_bbox 同一语义） */
function collisionBBox(shape: SpriteCollisionShape): { x0: number; y0: number; x1: number; y1: number } {
  if (shape.type === 'rect') {
    return {
      x0: shape.cx - shape.w / 2, y0: shape.cy - shape.h / 2,
      x1: shape.cx + shape.w / 2, y1: shape.cy + shape.h / 2,
    }
  }
  if (shape.type === 'capsule') {
    const r = Math.max(0.5, shape.radius)
    const h = Math.max(2 * r, shape.height)
    return { x0: shape.cx - r, y0: shape.cy - h / 2, x1: shape.cx + r, y1: shape.cy + h / 2 }
  }
  const xs = shape.points.map(p => p[0])
  const ys = shape.points.map(p => p[1])
  return { x0: Math.min(...xs), y0: Math.min(...ys), x1: Math.max(...xs), y1: Math.max(...ys) }
}

// ═══ 标记标注（锚点，武器/道具挂载用；统一值 + 帧级覆盖，与中心/碰撞同构） ═══

const selMarkerName = ref<string | null>(null)

/** 全部标记名（统一值 key ∪ 各帧覆盖 key——被删统一值但帧覆盖仍在的名字也要能清除） */
const markerNames = computed(() => {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return [] as string[]
  const names = new Set<string>()
  for (const k of Object.keys(bsf.markers || {})) names.add(k)
  for (const f of bsf.frames) {
    for (const k of Object.keys(f.markers || {})) names.add(k)
  }
  return [...names]
})

/** 第 i 帧某标记的有效位置：帧覆盖 > 统一值 > null */
function effMarker(name: string, i: number): { x: number; y: number } | null {
  const bsf = currentSprite.value?.bsf
  if (!bsf || i < 0 || i >= bsf.frames.length) return null
  return bsf.frames[i].markers?.[name] ?? bsf.markers?.[name] ?? null
}

function hasMarkerOverride(name: string, i: number): boolean {
  return !!currentSprite.value?.bsf?.frames[i]?.markers?.[name]
}

/** 当前帧是否有任意标记覆盖（造型列表角标用） */
function hasAnyMarkerOverride(i: number): boolean {
  const m = currentSprite.value?.bsf?.frames[i]?.markers
  return !!m && Object.keys(m).length > 0
}

const selMarkerPos = computed(() =>
  selMarkerName.value ? effMarker(selMarkerName.value, annoFrameIndex.value) : null,
)

function markerHandleStyle(name: string) {
  const p = effMarker(name, annoFrameIndex.value)
  return p ? { left: `${p.x}px`, top: `${p.y}px` } : { display: 'none' }
}

/**
 * 画布标记图钉：直接把 标记.svg 内联为 DOM（fill 换成 currentColor），
 * 颜色由 CSS color 控制（主题绿 / 帧覆盖蓝），不依赖 mask-image 的跨 WebView 支持差异。
 */
const markerIconSvg = computed(() =>
  iconMarkerRaw
    .replace(/fill="#ffffff"/gi, 'fill="currentColor"')
    .replace(/fill:white/gi, 'fill:currentColor'),
)

function setMarkerPos(name: string, p: { x: number; y: number }) {
  const bsf = currentSprite.value?.bsf
  if (!bsf || !name) return
  if (annoScope.value === 'all') {
    if (!bsf.markers) bsf.markers = {}
    bsf.markers[name] = { x: p.x, y: p.y }
  } else {
    const f = bsf.frames[annoFrameIndex.value]
    if (!f) return
    if (!f.markers) f.markers = {}
    f.markers[name] = { x: p.x, y: p.y }
  }
  scheduleSave()
}

function onMarkerCoordChange(axis: 'x' | 'y', e: Event) {
  const v = Number((e.target as HTMLInputElement).value)
  const cur = selMarkerPos.value
  if (!selMarkerName.value || !cur || !Number.isFinite(v)) return
  setMarkerPos(selMarkerName.value, axis === 'x' ? { x: v, y: cur.y } : { x: cur.x, y: v })
}

/** 新增标记：唯一命名 标记 / 标记1 / 标记2 / ...，初值=当前帧内容框中心 */
function addMarker() {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  if (!bsf.markers) bsf.markers = {}
  const existing = new Set(markerNames.value)
  let name = '标记'
  let n = 1
  while (existing.has(name)) { name = `标记${n}`; n++ }
  const f = bsf.frames[annoFrameIndex.value]
  const cx = f ? Math.round(f.offset.x + f.rect.w / 2) : Math.round(bsf.canvas.w / 2)
  const cy = f ? Math.round(f.offset.y + f.rect.h / 2) : Math.round(bsf.canvas.h / 2)
  bsf.markers[name] = { x: cx, y: cy }
  selMarkerName.value = name
  scheduleSave()
}

/** 重命名标记：统一值与全部帧覆盖同步改 key；空/重名不生效 */
function renameMarker(name: string, newName: string) {
  const bsf = currentSprite.value?.bsf
  const trimmed = newName.trim()
  if (!bsf || !name || !trimmed || trimmed === name) return
  if (markerNames.value.includes(trimmed)) return
  if (bsf.markers && name in bsf.markers) {
    bsf.markers[trimmed] = bsf.markers[name]
    delete bsf.markers[name]
  }
  for (const f of bsf.frames) {
    if (f.markers && name in f.markers) {
      f.markers[trimmed] = f.markers[name]
      delete f.markers[name]
    }
  }
  selMarkerName.value = trimmed
  scheduleSave()
}

/** 删除标记：统一值 + 全部帧覆盖 */
function deleteMarker(name: string) {
  const bsf = currentSprite.value?.bsf
  if (!bsf || !name) return
  if (bsf.markers) delete bsf.markers[name]
  for (const f of bsf.frames) {
    if (f.markers) {
      delete f.markers[name]
      if (Object.keys(f.markers).length === 0) delete f.markers
    }
  }
  if (selMarkerName.value === name) {
    selMarkerName.value = Object.keys(bsf.markers || {})[0] ?? null
  }
  scheduleSave()
}

function clearMarkerOverride() {
  const f = currentSprite.value?.bsf?.frames[annoFrameIndex.value]
  if (!f?.markers || !selMarkerName.value) return
  delete f.markers[selMarkerName.value]
  if (Object.keys(f.markers).length === 0) delete f.markers
  scheduleSave()
}

/** 「脚底」预设：所有帧内容包围盒的底部中心（贴地角色锚点） */
function feetPresetPoint(): { x: number; y: number } {
  const bsf = currentSprite.value?.bsf!
  let maxX = 0
  let maxY = 0
  for (const f of bsf.frames) {
    maxX = Math.max(maxX, f.offset.x + f.rect.w)
    maxY = Math.max(maxY, f.offset.y + f.rect.h)
  }
  return { x: Math.round(maxX / 2), y: maxY }
}

function applyPivotPreset(kind: 'center' | 'feet') {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  const p = kind === 'center'
    ? { x: Math.round(bsf.canvas.w / 2), y: Math.round(bsf.canvas.h / 2) }
    : feetPresetPoint()
  setPivot(p)
}

function onCoordChange(axis: 'x' | 'y', e: Event) {
  const v = Number((e.target as HTMLInputElement).value)
  const cur = annoPivot.value
  if (!cur || !Number.isFinite(v)) return
  setPivot(axis === 'x' ? { x: v, y: cur.y } : { x: cur.x, y: v })
}

/** 洋葱皮幽灵：相邻帧有效中心点与当前帧不同时显示，防碰撞框/重心抖动 */
const pivotGhosts = computed(() => {
  if (!canAnno.value) return []
  const cur = effPivot(annoFrameIndex.value)
  if (!cur) return []
  const out: { i: number; x: number; y: number }[] = []
  for (const ni of [annoFrameIndex.value - 1, annoFrameIndex.value + 1]) {
    const np = effPivot(ni)
    if (!np) continue
    if (Math.abs(np.x - cur.x) < 0.01 && Math.abs(np.y - cur.y) < 0.01) continue
    out.push({ i: ni, x: np.x, y: np.y })
  }
  return out
})

const pivotHandleStyle = computed(() => {
  const p = annoPivot.value
  return p ? { left: `${p.x}px`, top: `${p.y}px` } : {}
})

/** 屏幕坐标 → 逻辑画布坐标（画布中心锚点 + pan + zoom，0.5px 吸附） */
function screenToCanvas(e: MouseEvent): { x: number; y: number } | null {
  const rect = canvasRef.value?.getBoundingClientRect()
  const bsf = currentSprite.value?.bsf
  if (!rect || !bsf) return null
  const offX = e.clientX - rect.left - rect.width / 2
  const offY = e.clientY - rect.top - rect.height / 2
  const lx = (offX - canvasPanX.value + bsf.canvas.w / 2) / canvasZoom.value
  const ly = (offY - canvasPanY.value + bsf.canvas.h / 2) / canvasZoom.value
  return { x: Math.round(lx * 2) / 2, y: Math.round(ly * 2) / 2 }
}

function onPivotMouseDown(e: MouseEvent) {
  if (e.button !== 0) return // 中键放行画布平移，仅左键起拖
  e.stopPropagation()
  e.preventDefault()
  isPivotDragging.value = true
}

function onPivotDragMove(e: MouseEvent) {
  if (!isPivotDragging.value) return
  const p = screenToCanvas(e)
  if (p) setPivot(p)
}

function onPivotDragUp() {
  isPivotDragging.value = false
}

// ── 标记拖拽（选中 + 拖动；复用中心的全局监听模式） ──

const isMarkerDragging = ref(false)

function onMarkerMouseDown(name: string, e: MouseEvent) {
  if (e.button !== 0) return
  e.stopPropagation()
  e.preventDefault()
  selMarkerName.value = name
  isMarkerDragging.value = true
}

function onMarkerDragMove(e: MouseEvent) {
  if (!isMarkerDragging.value || !selMarkerName.value) return
  const p = screenToCanvas(e)
  if (p) setMarkerPos(selMarkerName.value, p)
}

function onMarkerDragUp() {
  isMarkerDragging.value = false
}


function getPreviewBgStyle() {
  const bgs = [
    { background: '#2b2b2b' },
    { background: '#ffffff' },
    { background: 'repeating-conic-gradient(#ccc 0% 25%, #fff 0% 50%) 50% / 16px 16px' },
  ]
  return bgs[previewBgIndex.value]
}

watch(fpsValue, (val) => {
  if (isPlaying.value && selectedAnim.value) {
    restartTimer()
  }
  // 保存 FPS 到当前动画（每个片段独立速度）
  if (selectedAnim.value) {
    selectedAnim.value.fps = val
    scheduleSave()
  }
})

// FPS 手动输入：输入过程中合法值立即生效（预览 + 保存），空/非法值由 blur 恢复
function onFpsNumberInput(e: Event) {
  const el = e.target as HTMLInputElement
  const raw = el.value.trim()
  if (raw === '') return
  const n = Number(raw)
  if (!Number.isFinite(n)) return
  fpsValue.value = Math.min(60, Math.max(1, Math.round(n)))
}

function onFpsNumberBlur(e: Event) {
  const el = e.target as HTMLInputElement
  if (el.value.trim() === '' || !Number.isFinite(Number(el.value))) {
    el.value = String(fpsValue.value)
  }
}

function addAnimation() {
  if (!currentSprite.value) return
  const total = currentSprite.value.frames.length
  let name = '动画'
  const existing = currentSprite.value.animations.map(a => a.name)
  let counter = 1
  while (existing.includes(name)) { name = `动画${counter}`; counter++ }
  const newAnim: SpriteAnimation = { name, start: 1, end: total, fps: 10, loop: true }
  currentSprite.value.animations.push(newAnim)
  // 立即选中新片段：速度滑条/数字框随之切换到它，体现"每片段独立速度"
  selectAnimation(newAnim)
  scheduleSave()
}

function deleteAnimation(name: string) {
  if (!currentSprite.value) return
  if (selectedAnim.value?.name === name) { stopAnimation(); selectedAnim.value = null }
  currentSprite.value.animations = currentSprite.value.animations.filter(a => a.name !== name)
  scheduleSave()
}

function renameAnimation(oldName: string, newName: string) {
  const shouldResume = wasPlayingBeforeRename && renamingAnim.value === oldName
  renamingAnim.value = null
  if (!currentSprite.value || !newName.trim()) return
  const exists = currentSprite.value.animations.some(a => a.name === newName && a.name !== oldName)
  if (exists) return
  const anim = currentSprite.value.animations.find(a => a.name === oldName)
  if (anim) anim.name = newName.trim()
  if (selectedAnim.value?.name === oldName) selectedAnim.value.name = newName.trim()
  if (shouldResume && selectedAnim.value) startAnimation(selectedAnim.value)
  scheduleSave()
}

function toggleLoop(anim: SpriteAnimation) {
  anim.loop = anim.loop === false ? true : false
  scheduleSave()
}

function onCostumeContextMenu(e: MouseEvent, index: number) {
  e.preventDefault()
  costumeContextMenu.value = { show: true, x: e.clientX, y: e.clientY, index }
}

function deleteCostume(index: number) {
  if (!currentSprite.value) return
  currentSprite.value.frames.splice(index, 1)
  for (const anim of currentSprite.value.animations) {
    if (anim.end > currentSprite.value.frames.length) {
      anim.end = currentSprite.value.frames.length
    }
    if (anim.start > anim.end) anim.start = anim.end
  }
  if (selectedFrameIndex.value >= currentSprite.value.frames.length) {
    selectedFrameIndex.value = Math.max(0, currentSprite.value.frames.length - 1)
  }
  costumeContextMenu.value.show = false
  scheduleSave()
}

function onAnimContextMenu(e: MouseEvent, name: string) {
  e.preventDefault()
  animContextMenu.value = { show: true, x: e.clientX, y: e.clientY, name }
}

let wasPlayingBeforeRename = false

function startRename(animName: string) {
  wasPlayingBeforeRename = isPlaying.value
  stopAnimation()
  renamingAnim.value = animName
  nextTick(() => {
    if (renameInputRef.value) {
      renameInputRef.value.focus()
      renameInputRef.value.select()
    }
  })
}

function closeContextMenus() {
  costumeContextMenu.value.show = false
  animContextMenu.value.show = false
}

// 注册全局 mouseup 监听
onMounted(() => {
  document.addEventListener('mouseup', onGlobalMouseUp)
  // 中心/标记拖拽用全局监听：拖出画布也不中断
  document.addEventListener('mousemove', onPivotDragMove)
  document.addEventListener('mouseup', onPivotDragUp)
  document.addEventListener('mousemove', onMarkerDragMove)
  document.addEventListener('mouseup', onMarkerDragUp)
})

onBeforeUnmount(() => {
  stopAnimation()
  revokeSpriteUrls(currentSprite.value)
  if (saveTimer) clearTimeout(saveTimer)
  document.removeEventListener('mouseup', onGlobalMouseUp)
  document.removeEventListener('mousemove', onPivotDragMove)
  document.removeEventListener('mouseup', onPivotDragUp)
  document.removeEventListener('mousemove', onMarkerDragMove)
  document.removeEventListener('mouseup', onMarkerDragUp)
})
</script>

<template>
  <div class="sprite-editor-page" @click="closeContextMenus">
    <!-- 左: 造型列表 (100px) + 追加抽屉 -->
    <div class="costume-list-wrap">
      <div class="costume-list">
        <div
          v-for="(frame, idx) in (currentSprite?.frames || [])"
          :key="idx"
          class="costume-item"
          :class="{ 'costume-item-active': costumeHighlightIndex === idx }"
          title="双击进入绘制编辑"
          @click="selectFrame(idx)"
          @dblclick.stop="emit('openPaintEdit', idx)"
          @contextmenu="onCostumeContextMenu($event, idx)"
        >
          <img :src="frame.url" class="costume-thumb" :style="{ imageRendering: imageRenderingStyle }" />
          <span class="costume-frame-num">帧 {{ idx + 1 }}</span>
          <!-- 中心点单帧覆盖标记 -->
          <span
            v-if="hasPivotOverride(idx)"
            class="pivot-override-badge"
          ></span>
          <!-- 碰撞单帧覆盖标记 -->
          <span
            v-if="hasCollisionOverride(idx)"
            class="collision-override-badge"
          ></span>
          <!-- 标记单帧覆盖标记 -->
          <span
            v-if="hasAnyMarkerOverride(idx)"
            class="marker-override-badge"
          ></span>
        </div>
      </div>
      <FrameUploadDrawer
        @imported="onImportFrameBlobs"
        @paint="emit('openPaintAppend')"
        @library="emit('openFramePicker')"
      />
    </div>

    <!-- 中: 画布列（标注工具条 + 画布） -->
    <div class="canvas-col">
      <!-- 标注图层工具条：图层单选切换，同一画布框架 -->
      <div v-if="canAnno" class="anno-toolbar">
        <button
          class="layer-chip"
          :class="{ active: activeAnnoLayer === 'pivot' }"
          type="button"
          @click="activateAnnoLayer('pivot')"
        >
          <img :src="iconCenterPivot" class="layer-chip-icon" alt="" />中心
        </button>
        <button
          class="layer-chip"
          :class="{ active: activeAnnoLayer === 'collision' }"
          type="button"
          @click="activateAnnoLayer('collision')"
        >
          <img :src="iconResetAnchor" class="layer-chip-icon" alt="" />碰撞
        </button>
        <button
          class="layer-chip"
          :class="{ active: activeAnnoLayer === 'marker' }"
          type="button"
          @click="activateAnnoLayer('marker')"
        >
          <img :src="iconMarker" class="layer-chip-icon" alt="" />标记
        </button>
        <!-- 标注控件随激活图层切换（与底部浮动条同源，共享状态） -->
        <template v-if="activeAnnoLayer === 'pivot'">
          <div class="props-sep"></div>
          <div class="coord-group">
            <label>X</label>
            <input
              class="coord-input"
              type="number"
              step="0.5"
              :value="annoPivot ? annoPivot.x.toFixed(1) : ''"
              @change="onCoordChange('x', $event)"
            />
          </div>
          <div class="coord-group">
            <label>Y</label>
            <input
              class="coord-input"
              type="number"
              step="0.5"
              :value="annoPivot ? annoPivot.y.toFixed(1) : ''"
              @change="onCoordChange('y', $event)"
            />
          </div>
          <div class="props-sep"></div>
          <button class="preset-btn" type="button" @click="applyPivotPreset('center')">中心</button>
          <button class="preset-btn" type="button" @click="applyPivotPreset('feet')">脚底</button>
          <button class="preset-btn" type="button" @click="resetAnno">重置</button>
          <button
            v-if="hasPivotOverride(annoFrameIndex)"
            class="clear-override-btn"
            type="button"
            @click="clearPivotOverride"
          >恢复统一</button>
          <div class="props-sep"></div>
          <div class="scope-seg">
            <button
              type="button"
              :class="{ on: annoScope === 'all' }"
              @click="annoScope = 'all'"
            >全部帧</button>
            <button
              type="button"
              :class="{ on: annoScope === 'one', 'on-blue': annoScope === 'one' }"
              @click="annoScope = 'one'"
            >仅当前帧</button>
          </div>
        </template>
        <template v-else-if="activeAnnoLayer === 'collision'">
          <div class="props-sep"></div>
          <div class="scope-seg">
            <button
              type="button"
              :class="{ on: !effCol }"
              @click="resetCollisionToAuto"
            >自动</button>
            <button
              type="button"
              :class="{ on: effCol?.type === 'rect' }"
              @click="convertCollisionType('rect')"
            >矩形</button>
            <button
              type="button"
              :class="{ on: effCol?.type === 'capsule' }"
              @click="convertCollisionType('capsule')"
            >胶囊</button>
            <button
              type="button"
              :class="{ on: effCol?.type === 'polygon' }"
              @click="convertCollisionType('polygon')"
            >多边形</button>
          </div>
          <div class="props-sep"></div>
          <button
            v-if="hasCollisionOverride(annoFrameIndex)"
            class="clear-override-btn"
            type="button"
            @click="clearCollisionOverride"
          >恢复统一</button>
          <div class="props-sep"></div>
          <div class="scope-seg">
            <button
              type="button"
              :class="{ on: annoScope === 'all' }"
              @click="annoScope = 'all'"
            >全部帧</button>
            <button
              type="button"
              :class="{ on: annoScope === 'one', 'on-blue': annoScope === 'one' }"
              @click="annoScope = 'one'"
            >仅当前帧</button>
          </div>
        </template>
        <template v-else>
          <!-- 标记：画布点选操作 + 添加/改名/删除 + 坐标 + 作用域 -->
          <div class="props-sep"></div>
          <button class="preset-btn" type="button" title="添加标记" @click="addMarker">添加</button>
          <input
            v-if="selMarkerName"
            class="marker-rename-input"
            :value="selMarkerName"
            title="标记名称"
            @change="renameMarker(selMarkerName!, ($event.target as HTMLInputElement).value)"
          />
          <button
            v-if="selMarkerName"
            class="preset-btn"
            type="button"
            title="删除标记"
            @click="deleteMarker(selMarkerName)"
          >删除</button>
          <div class="props-sep"></div>
          <div class="coord-group">
            <label>X</label>
            <input
              class="coord-input"
              type="number"
              step="0.5"
              :value="selMarkerPos ? selMarkerPos.x.toFixed(1) : ''"
              @change="onMarkerCoordChange('x', $event)"
            />
          </div>
          <div class="coord-group">
            <label>Y</label>
            <input
              class="coord-input"
              type="number"
              step="0.5"
              :value="selMarkerPos ? selMarkerPos.y.toFixed(1) : ''"
              @change="onMarkerCoordChange('y', $event)"
            />
          </div>
          <div class="props-sep"></div>
          <button
            v-if="selMarkerName && hasMarkerOverride(selMarkerName, annoFrameIndex)"
            class="clear-override-btn"
            type="button"
            @click="clearMarkerOverride"
          >恢复统一</button>
          <div class="props-sep"></div>
          <div class="scope-seg">
            <button
              type="button"
              :class="{ on: annoScope === 'all' }"
              @click="annoScope = 'all'"
            >全部帧</button>
            <button
              type="button"
              :class="{ on: annoScope === 'one', 'on-blue': annoScope === 'one' }"
              @click="annoScope = 'one'"
            >仅当前帧</button>
          </div>
        </template>
      </div>

      <div
        ref="canvasRef"
        class="sprite-canvas"
        :class="{ 'is-panning': isPanning }"
        @wheel.prevent="onCanvasWheel"
        @mousedown="onCanvasMouseDown"
        @mousemove="onCanvasMouseMove"
        @mouseup="onCanvasMouseUp"
        @mouseleave="onCanvasMouseUp"
        @dblclick="resetCanvas"
      >
        <div class="canvas-center-anchor">
          <div
            class="canvas-sprite-wrapper"
            :style="{
              transform: `translate(${canvasPanX}px, ${canvasPanY}px) scale(${canvasZoom})`
            }"
          >
            <img
              v-if="currentSprite?.frames[canvasDisplayIndex]"
              :src="currentSprite.frames[canvasDisplayIndex].url"
              class="canvas-sprite"
              draggable="false"
              :style="{ imageRendering: imageRenderingStyle }"
            />
            <!-- 洋葱皮幽灵：相邻帧有效中心点不一致时显示（中心点图层） -->
            <div
              v-for="g in (activeAnnoLayer === 'pivot' ? pivotGhosts : [])"
              :key="g.i"
              class="pivot-ghost"
              :style="{ left: `${g.x}px`, top: `${g.y}px` }"
            >
              <div class="ghost-counter" :style="{ transform: `scale(${1 / canvasZoom})` }">
                <span class="ghost-ring"></span>
              </div>
            </div>
            <!-- 中心点手柄（碰撞图层下弱化显示、不响应交互） -->
            <div
              v-if="annoPivot"
              class="pivot-handle"
              :class="{ 'is-override': annoScope === 'one', 'is-inactive': activeAnnoLayer !== 'pivot' }"
              :style="pivotHandleStyle"
              @mousedown="onPivotMouseDown"
            >
              <div class="pivot-visual" :style="{ transform: `scale(${1 / canvasZoom})` }">
                <div class="pivot-ring"></div>
              </div>
            </div>
            <!-- 碰撞形状叠加层（自动态显示引擎内容框；拖动手柄立即转为自定义） -->
            <CollisionShapeOverlay
              v-if="canAnno && activeAnnoLayer === 'collision' && currentSprite?.bsf"
              :canvas-w="currentSprite.bsf.canvas.w"
              :canvas-h="currentSprite.bsf.canvas.h"
              :shape="collisionDisplay"
              :zoom="canvasZoom"
              @update="onCollisionUpdate"
            />
            <!-- 标记手柄：标记.svg 图钉（图标配色独立于 svg 填充，mask 上色），画布点选/拖拽 -->
            <div
              v-for="name in (activeAnnoLayer === 'marker' ? markerNames : [])"
              :key="name"
              class="marker-handle"
              :class="{
                'is-selected': name === selMarkerName,
                'is-override': hasMarkerOverride(name, annoFrameIndex),
              }"
              :style="markerHandleStyle(name)"
              @mousedown="onMarkerMouseDown(name, $event)"
            >
              <div class="marker-visual" :style="{ transform: `scale(${1 / canvasZoom})` }">
                <div class="marker-icon" v-html="markerIconSvg"></div>
                <span class="marker-label">{{ name }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 底部浮动属性条：按激活图层切换控件组 -->
        <div v-if="canAnno" class="anno-props">
          <template v-if="activeAnnoLayer === 'pivot'">
            <span class="props-title">中心</span>
            <div class="coord-group">
              <label>X</label>
              <input
                class="coord-input"
                type="number"
                step="0.5"
                :value="annoPivot ? annoPivot.x.toFixed(1) : ''"
                @change="onCoordChange('x', $event)"
              />
            </div>
            <div class="coord-group">
              <label>Y</label>
              <input
                class="coord-input"
                type="number"
                step="0.5"
                :value="annoPivot ? annoPivot.y.toFixed(1) : ''"
                @change="onCoordChange('y', $event)"
              />
            </div>
            <div class="props-sep"></div>
            <button class="preset-btn" type="button" @click="applyPivotPreset('center')">中心</button>
            <button class="preset-btn" type="button" @click="applyPivotPreset('feet')">脚底</button>
            <button class="preset-btn" type="button" @click="resetAnno">重置</button>
            <button
              v-if="hasPivotOverride(annoFrameIndex)"
              class="clear-override-btn"
              type="button"
              @click="clearPivotOverride"
            >恢复统一</button>
            <div class="props-sep"></div>
            <div class="scope-seg">
              <button
                type="button"
                :class="{ on: annoScope === 'all' }"
                @click="annoScope = 'all'"
              >全部帧</button>
              <button
                type="button"
                :class="{ on: annoScope === 'one', 'on-blue': annoScope === 'one' }"
                @click="annoScope = 'one'"
              >仅当前帧</button>
            </div>
          </template>
          <template v-else-if="activeAnnoLayer === 'collision'">
            <span class="props-title">碰撞</span>
            <!-- 类型 toggle：自动 = 引擎内容包围盒（无 manifest 字段），始终显示在画布 -->
            <div class="scope-seg">
              <button
                type="button"
                :class="{ on: !effCol }"
                @click="resetCollisionToAuto"
              >自动</button>
              <button
                type="button"
                :class="{ on: effCol?.type === 'rect' }"
                @click="convertCollisionType('rect')"
              >矩形</button>
              <button
                type="button"
                :class="{ on: effCol?.type === 'capsule' }"
                @click="convertCollisionType('capsule')"
              >胶囊</button>
              <button
                type="button"
                :class="{ on: effCol?.type === 'polygon' }"
                @click="convertCollisionType('polygon')"
              >多边形</button>
            </div>
            <div class="props-sep"></div>
            <button
              v-if="hasCollisionOverride(annoFrameIndex)"
              class="clear-override-btn"
              type="button"
              @click="clearCollisionOverride"
            >恢复统一</button>
            <div class="props-sep"></div>
            <div class="scope-seg">
              <button
                type="button"
                :class="{ on: annoScope === 'all' }"
                @click="annoScope = 'all'"
              >全部帧</button>
              <button
                type="button"
                :class="{ on: annoScope === 'one', 'on-blue': annoScope === 'one' }"
                @click="annoScope = 'one'"
              >仅当前帧</button>
            </div>
          </template>
          <template v-else>
            <span class="props-title">标记</span>
            <button class="preset-btn" type="button" title="添加标记" @click="addMarker">添加</button>
            <input
              v-if="selMarkerName"
              class="marker-rename-input"
              :value="selMarkerName"
              title="标记名称"
              @change="renameMarker(selMarkerName!, ($event.target as HTMLInputElement).value)"
            />
            <button
              v-if="selMarkerName"
              class="preset-btn"
              type="button"
              title="删除标记"
              @click="deleteMarker(selMarkerName)"
            >删除</button>
            <div class="props-sep"></div>
            <div class="coord-group">
              <label>X</label>
              <input
                class="coord-input"
                type="number"
                step="0.5"
                :value="selMarkerPos ? selMarkerPos.x.toFixed(1) : ''"
                @change="onMarkerCoordChange('x', $event)"
              />
            </div>
            <div class="coord-group">
              <label>Y</label>
              <input
                class="coord-input"
                type="number"
                step="0.5"
                :value="selMarkerPos ? selMarkerPos.y.toFixed(1) : ''"
                @change="onMarkerCoordChange('y', $event)"
              />
            </div>
            <div class="props-sep"></div>
            <button
              v-if="selMarkerName && hasMarkerOverride(selMarkerName, annoFrameIndex)"
              class="clear-override-btn"
              type="button"
              @click="clearMarkerOverride"
            >恢复统一</button>
            <div class="props-sep"></div>
            <div class="scope-seg">
              <button
                type="button"
                :class="{ on: annoScope === 'all' }"
                @click="annoScope = 'all'"
              >全部帧</button>
              <button
                type="button"
                :class="{ on: annoScope === 'one', 'on-blue': annoScope === 'one' }"
                @click="annoScope = 'one'"
              >仅当前帧</button>
            </div>
          </template>
        </div>
      </div>
    </div>

    <!-- 右: 预览面板 (264px) -->
    <div class="preview-panel">
      <div class="preview-label">ANIMATION</div>

      <!-- 预览区域 256×256 -->
      <div class="preview-bg">
        <div class="preview-image-box" :style="getPreviewBgStyle()">
          <div class="preview-image-wrap" :style="{ transform: `scale(${previewScale})` }">
            <img
              v-if="currentSprite?.frames[selectedFrameIndex]"
              :src="currentSprite.frames[selectedFrameIndex].url"
              class="preview-image"
              :style="{ imageRendering: imageRenderingStyle }"
            />
          </div>
          <!-- FPS 控制 (悬浮在预览底部)：左=拖动滑条，右=帧数手动输入；速度按片段独立保存 -->
          <div class="fps-slider-overlay" :class="{ 'fps-overlay-disabled': !selectedAnim }">
            <input
              type="range"
              v-model.number="fpsValue"
              min="1"
              max="60"
              class="fps-slider"
              :disabled="!selectedAnim"
              title="动画播放速度（帧/秒），每个片段独立"
            />
            <input
              type="number"
              class="fps-input"
              :value="fpsValue"
              min="1"
              max="60"
              :disabled="!selectedAnim"
              title="动画播放速度（帧/秒），每个片段独立"
              @input="onFpsNumberInput"
              @blur="onFpsNumberBlur"
              @keyup.enter="($event.target as HTMLInputElement).blur()"
            />
            <span class="fps-unit">帧/秒</span>
          </div>
        </div>
      </div>

      <!-- 按钮栏 -->
      <div class="preview-btns">
        <button class="prev-btn" @click="prevFrame"><img :src="iconPrev" /></button>
        <button class="prev-btn" :class="{ active: isPlaying }" @click="togglePlay">
          <img :src="isPlaying ? iconPause : iconPlay" />
        </button>
        <button class="prev-btn" @click="nextFrame"><img :src="iconNext" /></button>
        <button class="prev-btn" @click="toggleScale"><img :src="iconScale" /></button>
        <button class="prev-btn" @click="changeBg"><img :src="iconChangeBg" /></button>
        <button class="prev-btn" @click="addAnimation"><img :src="iconAdd" /></button>
      </div>

      <!-- 动画列表 -->
      <div class="anim-list">
        <div
          v-for="(anim, animIdx) in (currentSprite?.animations || [])"
          :key="animIdx"
          class="anim-item"
          :class="{ 'anim-item-active': selectedAnim?.name === anim.name }"
          @click="selectAnimation(anim)"
          @contextmenu="onAnimContextMenu($event, anim.name)"
        >
          <div class="anim-item-row">
            <template v-if="renamingAnim === anim.name">
              <input
                ref="renameInputRef"
                class="anim-rename-input"
                :value="anim.name"
                @blur="renameAnimation(anim.name, ($event.target as HTMLInputElement).value)"
                @keydown.enter="renameAnimation(anim.name, ($event.target as HTMLInputElement).value)"
                @keydown.escape="renamingAnim = null"
                @click.stop
              />
            </template>
            <template v-else>
              <span class="anim-name" @dblclick.stop="startRename(anim.name)">{{ anim.name }}</span>
            </template>
            <div class="anim-range">
              <input
                type="number"
                class="anim-spin"
                :value="anim.start"
                min="1"
                :max="currentSprite?.frames.length || 999"
                @change="anim.start = Math.max(1, Math.min(Number(($event.target as HTMLInputElement).value), anim.end)); scheduleSave()"
                @click.stop
              />
              <span class="anim-dash">-</span>
              <input
                type="number"
                class="anim-spin"
                :value="anim.end"
                min="1"
                :max="currentSprite?.frames.length || 999"
                @change="anim.end = Math.max(anim.start, Math.min(Number(($event.target as HTMLInputElement).value), currentSprite?.frames.length || 999)); scheduleSave()"
                @click.stop
              />
              <button class="anim-loop-btn" @click.stop="toggleLoop(anim)">
                <img :src="anim.loop !== false ? iconLoop : iconLoopOff" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 右键菜单: 造型 -->
    <Teleport to="body">
      <div
        v-if="costumeContextMenu.show"
        class="context-menu"
        :style="{ left: costumeContextMenu.x + 'px', top: costumeContextMenu.y + 'px' }"
        @click.stop
      >
        <!-- .bsf 帧是 sheet 图集的一部分，编辑器不支持删除（需回 BingoPacker 重打包） -->
        <div
          v-if="!currentSprite?.bsf"
          class="context-menu-item"
          @click="deleteCostume(costumeContextMenu.index)"
        >
          删除造型: {{ costumeContextMenu.index + 1 }}
        </div>
      </div>
    </Teleport>

    <!-- 右键菜单: 动画 -->
    <Teleport to="body">
      <div
        v-if="animContextMenu.show"
        class="context-menu"
        :style="{ left: animContextMenu.x + 'px', top: animContextMenu.y + 'px' }"
        @click.stop
      >
        <div class="context-menu-item" @click="deleteAnimation(animContextMenu.name)">
          删除动作
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.sprite-editor-page {
  display: flex;
  height: 100%;
  background: var(--bg-root);
  user-select: none;
  -webkit-user-select: none;
}

/* ═══ 左: 造型列表 ═══ */
.costume-list-wrap {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 100px;
  width: 100px;
  border-right: 1px solid var(--border);
  background: var(--bg-root);
}
.costume-list {
  flex: 1;
  min-height: 0;
  padding: 8px 4px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--bg-root);
  /* 底部给追加抽屉留出空间，避免最后一帧被遮住 */
  padding-bottom: 56px;
}
.costume-list::-webkit-scrollbar { width: 0; height: 0; }
.costume-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4px;
  border: 1px solid var(--border);
  border-radius: 4px;
  cursor: pointer;
  background: var(--bg-darker);
}
.costume-item:hover { background: var(--bg-hover); border-color: var(--border-light); }
.costume-item.costume-item-active { border-color: transparent; background: var(--bg-hover); box-shadow: inset 0 0 0 2px var(--accent); }
.costume-item.costume-item-active:hover { box-shadow: inset 0 0 0 2px var(--accent); }
.costume-thumb {
  width: 78px;
  height: 60px;
  object-fit: contain;
}
.costume-frame-num {
  font-size: 10px;
  color: #abb2bf;
  margin-top: 2px;
}

/* ═══ 中: 画布 ═══ */
.sprite-canvas {
  position: relative;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-root);
  min-width: 0;
  overflow: hidden;
  cursor: default;
}
.sprite-canvas.is-panning {
  cursor: grabbing;
}
.canvas-center-anchor {
  display: flex;
  align-items: center;
  justify-content: center;
}
.canvas-sprite-wrapper {
  transform-origin: 0 0;
}
.canvas-sprite {
  display: block;
  background-color: #ffffff;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16'%3E%3Crect width='16' height='16' fill='%23fff'/%3E%3Crect width='8' height='8' fill='%23e0e0e0'/%3E%3Crect x='8' y='8' width='8' height='8' fill='%23e0e0e0'/%3E%3C/svg%3E");
}

/* ═══ 中: 画布列 — 标注图层 ═══ */
.canvas-col {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.anno-toolbar {
  height: 36px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 10px;
  background: var(--bg-root);
  border-bottom: 1px solid var(--border);
}
.layer-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid var(--border-light);
  background: transparent;
  color: #8a8f98;
  cursor: pointer;
  font-size: 12px;
}
.layer-chip:hover:not(:disabled) { background: var(--bg-hover); color: #fff; }
.layer-chip.active { border-color: var(--accent); color: var(--accent); background: rgba(91, 251, 132, 0.08); }
.layer-chip:disabled { opacity: 0.4; cursor: not-allowed; }
.layer-chip .soon { font-size: 9px; opacity: 0.7; margin-left: 2px; }
.layer-chip-icon { width: 14px; height: 14px; }
/* 工具条内的标注控件紧凑排布（36px 行高） */
.anno-toolbar .coord-input { height: 20px; padding: 0 4px; }
.anno-toolbar .scope-seg button { padding: 3px 8px; }
.anno-toolbar .preset-btn,
.anno-toolbar .clear-override-btn { padding: 3px 8px; }

/* 中心点手柄（锚点为逻辑坐标，反向缩放保持屏幕大小恒定） */
/* 中心点手柄：锚点光标用箭头（拖拽区=形状内部才用移动图标） */
.pivot-handle {
  position: absolute;
  width: 0;
  height: 0;
  cursor: default;
  z-index: 5;
}
.pivot-visual {
  position: absolute;
  left: 0;
  top: 0;
  transform-origin: 0 0;
}
.pivot-ring {
  position: absolute;
  left: -11px;
  top: -11px;
  width: 22px;
  height: 22px;
  border: 2px solid var(--accent);
  border-radius: 50%;
  background: rgba(91, 251, 132, 0.12);
  box-shadow: 0 0 6px rgba(91, 251, 132, 0.5);
}
.pivot-ring::before,
.pivot-ring::after {
  content: "";
  position: absolute;
  background: var(--accent);
}
.pivot-ring::before { left: 50%; top: -6px; width: 1.5px; height: 32px; margin-left: -0.75px; }
.pivot-ring::after { top: 50%; left: -6px; height: 1.5px; width: 32px; margin-top: -0.75px; }
/* 单帧覆盖模式：手柄变蓝（区别于统一绿） */
.pivot-handle.is-override .pivot-ring {
  border-color: #61afef;
  background: rgba(97, 175, 239, 0.12);
  box-shadow: 0 0 6px rgba(97, 175, 239, 0.5);
}
.pivot-handle.is-override .pivot-ring::before,
.pivot-handle.is-override .pivot-ring::after { background: #61afef; }
/* 碰撞图层激活时中心点手柄弱化（仅作位置参考，不响应交互） */
.pivot-handle.is-inactive { pointer-events: none; opacity: 0.4; }

/* 洋葱皮幽灵（相邻帧有效中心点） */
.pivot-ghost {
  position: absolute;
  width: 0;
  height: 0;
  pointer-events: none;
  z-index: 4;
}
.ghost-counter {
  position: absolute;
  left: 0;
  top: 0;
  transform-origin: 0 0;
}
.ghost-ring {
  position: absolute;
  left: -7px;
  top: -7px;
  width: 14px;
  height: 14px;
  border: 1.5px dashed #e5c07b;
  border-radius: 50%;
  opacity: 0.55;
}

/* 标记手柄（标记.svg 图钉，mask 上色主题绿；图钉尖对准锚点坐标） */
.marker-handle {
  position: absolute;
  width: 0;
  height: 0;
  cursor: grab;
  z-index: 5;
}
.marker-handle:active { cursor: grabbing; }
.marker-visual {
  position: absolute;
  left: 0;
  top: 0;
  transform-origin: 0 0;
}
/* 图钉：内联 svg（fill=currentColor）；配色走 CSS 变量，图钉尖对准锚点坐标。
   默认=标记红 rgb(234,73,66)；帧覆盖=蓝（与其他标注图层惯例一致） */
.marker-handle {
  --mk-color: #EA4942;
  --mk-glow: rgba(234, 73, 66, 0.6);
}
.marker-handle.is-override {
  --mk-color: #61afef;
  --mk-glow: rgba(97, 175, 239, 0.6);
}
.marker-icon {
  position: absolute;
  left: -10px;
  top: -18.5px;
  width: 20px;
  height: 20px;
  color: var(--mk-color);
  filter: drop-shadow(0 0 4px var(--mk-glow));
  pointer-events: auto;
  transition: transform 0.1s ease;
}
.marker-icon :deep(svg) {
  width: 100%;
  height: 100%;
  display: block;
}
.marker-label {
  position: absolute;
  left: 11px;
  top: -16px;
  font-size: 10px;
  line-height: 14px;
  color: var(--mk-color);
  background: rgba(34, 37, 43, 0.85);
  padding: 0 4px;
  border-radius: 3px;
  white-space: nowrap;
  pointer-events: none;
  user-select: none;
}
/* 选中态：三重区分——白色描边 + 放大 + 标签反色实心（一眼定位当前编辑的标记） */
.marker-handle.is-selected .marker-icon {
  transform: scale(1.2);
  transform-origin: 50% 92.5%; /* 钉尖固定，放大时不脱离锚点 */
  filter:
    drop-shadow(0 0 1px #fff)
    drop-shadow(0 0 2px #fff)
    drop-shadow(0 0 7px var(--mk-glow));
}
.marker-handle.is-selected .marker-label {
  color: #10131a;
  background: var(--mk-color);
  font-weight: 600;
}
/* 标记改名输入框 */
.marker-rename-input {
  width: 76px;
  height: 22px;
  padding: 0 5px;
  border-radius: 4px;
  border: 1px solid var(--border-light);
  background: var(--bg-root);
  color: #fff;
  font-size: 11px;
}
.marker-rename-input:focus {
  outline: none;
  border-color: #EA4942;
}
.anno-toolbar .marker-rename-input { height: 20px; }

/* 底部浮动属性条 */
.anno-props {
  position: absolute;
  left: 50%;
  bottom: 14px;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(41, 44, 52, 0.92);
  border: 1px solid var(--border-light);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.45);
  z-index: 10;
}
.props-title {
  color: var(--accent);
  font-weight: 600;
  white-space: nowrap;
  font-size: 12px;
}
.props-sep { width: 1px; height: 18px; background: var(--border-light); flex-shrink: 0; }
.coord-group { display: flex; align-items: center; gap: 4px; }
.coord-group label { color: #8a8f98; font-size: 12px; }
.coord-input {
  width: 54px;
  padding: 3px 5px;
  border-radius: 3px;
  border: 1px solid var(--border-light);
  background: var(--bg-root);
  color: #fff;
  font-size: 12px;
  text-align: right;
  outline: none;
  -moz-appearance: textfield;
}
.coord-input::-webkit-outer-spin-button,
.coord-input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
.coord-input:focus { border-color: var(--accent); }
.scope-seg {
  display: flex;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
}
.scope-seg button {
  padding: 4px 10px;
  border: none;
  background: transparent;
  color: #8a8f98;
  cursor: pointer;
  font-size: 12px;
  white-space: nowrap;
}
.scope-seg button:hover { background: var(--bg-hover); }
.scope-seg button.on { background: var(--accent); color: #10131a; font-weight: 600; }
.scope-seg button.on-blue { background: #61afef; }
.preset-btn {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid var(--border-light);
  background: transparent;
  color: #ddd;
  white-space: nowrap;
}
.preset-btn:hover { background: var(--bg-hover); border-color: #8a8f98; }
.clear-override-btn {
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid #61afef;
  background: rgba(97, 175, 239, 0.1);
  color: #61afef;
  white-space: nowrap;
}
.clear-override-btn:hover { background: rgba(97, 175, 239, 0.22); }

/* 造型列表：单帧覆盖角标（蓝=中心点，橙=碰撞） */
.costume-item { position: relative; }
.pivot-override-badge {
  position: absolute;
  top: 3px;
  right: 3px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #61afef;
  box-shadow: 0 0 4px #61afef;
}
.collision-override-badge {
  position: absolute;
  top: 3px;
  right: 14px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #e5c07b;
  box-shadow: 0 0 4px #e5c07b;
}
.marker-override-badge {
  position: absolute;
  top: 3px;
  right: 25px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #EA4942;
  box-shadow: 0 0 4px #EA4942;
}

/* ═══ 右: 预览面板 ═══ */
.preview-panel {
  width: 264px;
  min-width: 264px;
  border-left: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  background: var(--bg-root);
  padding: 0 8px;
}

.preview-label {
  color: #00FF8C;
  font-size: 12px;
  text-align: center;
  /* 与画布顶部标注工具条等高，横向分隔线对齐 */
  height: 36px;
  line-height: 36px;
  padding: 0;
  margin: 0;
  border: none;
  background: var(--bg-root);
  flex-shrink: 0;
}

/* 预览背景 */
.preview-bg {
  margin: 0;
  padding: 0;
}
.preview-image-box {
  position: relative;
  width: 100%;
  height: 256px;
  border: 1px solid rgb(69, 69, 69);
  background: #1E1E1E;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.preview-image {
  max-width: 248px;
  max-height: 248px;
}
/* 预览图包裹层：缩放移到包裹层，与画布区结构一致 */
.preview-image-wrap {
  position: relative;
  display: flex;
  flex-shrink: 0;
}

/* FPS 控制 (悬浮在预览底部)：左滑条 + 右数字输入，无底色 */
.fps-slider-overlay {
  position: absolute;
  bottom: 8px;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 4px;
}
.fps-overlay-disabled {
  opacity: 0.45;
}
.fps-input {
  width: 46px;
  height: 18px;
  padding: 0 4px;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: #fff;
  font-size: 11px;
  text-align: center;
  outline: none;
  -moz-appearance: textfield;
}
.fps-input::-webkit-outer-spin-button,
.fps-input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
.fps-input:focus { border-color: var(--accent); }
.fps-input:disabled,
.fps-slider:disabled { cursor: not-allowed; }
.fps-unit {
  font-size: 10px;
  color: #9ca0a4;
  white-space: nowrap;
}
.fps-slider {
  flex: 1;
  height: 4px;
  -webkit-appearance: none;
  appearance: none;
  background: var(--border-light);
  border-radius: 2px;
  outline: none;
  margin: 0;
}
.fps-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #9ca0a4;
  cursor: pointer;
}
.fps-slider::-webkit-slider-thumb:hover {
  background: #abb2bf;
}

/* 按钮栏 */
.preview-btns {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 6px 0;
}
.prev-btn {
  width: 38px;
  height: 24px;
  border: none;
  border-radius: 4px;
  background: rgb(40, 43, 52);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: background 0.12s;
}
.prev-btn:hover { background: rgb(62, 66, 79); }
.prev-btn.active { background: rgb(55, 120, 200); }
.prev-btn img { width: 28px; height: 16px; }

/* 动画列表 */
.anim-list {
  flex: 1;
  margin: 0;
  padding: 0;
  border: none;
  background: #1E1E1E;
  overflow-y: auto;
}
.anim-item {
  padding: 6px 8px;
  font-size: 12px;
  color: rgb(200, 200, 200);
  cursor: pointer;
  border-bottom: 1px solid rgba(255,255,255,0.05);
}
.anim-item:hover { background: var(--bg-hover); }
.anim-item-active { background: #528bff; color: white; }
.anim-item-active:hover { background: #528bff; }

.anim-item-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.anim-name {
  flex-shrink: 0;
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-left: 4px;
}
.anim-rename-input {
  flex-shrink: 0;
  width: 90px;
  height: 22px;
  background: rgb(30, 30, 40);
  border: 1px solid #528bff;
  border-radius: 3px;
  color: white;
  font-size: 12px;
  padding: 0 6px;
  outline: none;
  box-shadow: 0 0 0 1px rgba(82, 139, 255, 0.3);
}
.anim-range {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: auto;
}
.anim-spin {
  width: 35px;
  height: 20px;
  background: rgba(0,0,0,0.3);
  border: none;
  border-radius: 2px;
  color: white;
  font-size: 11px;
  text-align: center;
  padding: 0;
  outline: none;
  -moz-appearance: textfield;
}
.anim-spin::-webkit-outer-spin-button,
.anim-spin::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
.anim-dash { color: #9ca0a4; font-size: 11px; }
.anim-loop-btn {
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  transition: background 0.12s;
}
.anim-loop-btn:hover { background: rgba(255,255,255,0.1); }
.anim-loop-btn img { width: 16px; height: 16px; }

/* 右键菜单 */
:global(.context-menu) {
  position: fixed;
  background: var(--bg-root);
  border: 1px solid rgb(60, 60, 60);
  border-radius: 6px;
  padding: 4px 0;
  z-index: 9999;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
  min-width: 120px;
}
:global(.context-menu-item) {
  padding: 6px 14px;
  font-size: 12px;
  color: rgb(200, 200, 200);
  cursor: pointer;
  transition: background 0.1s;
}
:global(.context-menu-item:hover) {
  background: var(--bg-hover);
  color: white;
}
</style>
