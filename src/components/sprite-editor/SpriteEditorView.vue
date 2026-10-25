<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useResourceStore } from '../../stores/resource'
import { useEditorStore } from '../../stores/editor'
import type { SpriteData, SpriteAnimation } from '../../composables/useSpriteData'
import { readSpriteFromPath, revokeSpriteUrls, saveSpriteConfig, saveBsfManifest, isImageSpritePath, buildSingleFrameBsfMeta, imageSpriteToBsfDir, loadImage } from '../../composables/useSpriteData'
import type { SpriteCollisionShape } from '../../composables/useSpriteData'
import { appendFramesToSprite } from '../../composables/appendSpriteFrames'
import { useFrameReorder } from '../../composables/useFrameReorder'
import { cssImageRendering } from '../../utils/renderMode'
import { drawImageCrisp } from '../../utils/pixelCanvas'
import FrameUploadDrawer from './FrameUploadDrawer.vue'
import CollisionShapeOverlay from './CollisionShapeOverlay.vue'

const emit = defineEmits<{
  /** 造型列表抽屉：打开绘制页为当前角色绘制新帧（编辑模式，自动新建空白帧） */
  openPaintAppend: []
  /** 双击帧卡片：打开绘制页编辑该帧 */
  openPaintEdit: [index: number]
  /** 造型列表抽屉：打开内置素材选帧页 */
  openFramePicker: []
  /** 空状态：打开内置角色库 */
  openSpriteLibrary: []
  /** 空状态：打开绘制页新建角色 */
  openPaintNew: []
}>()

import { useFileDialog } from '../../composables/useFileDialog'
import { SPRITE_ACCEPT, importSpriteFile } from '../../composables/useSpriteImport'

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
import iconSpriteEmpty from '../../assets/icons/角色精灵.svg'

const resourceStore = useResourceStore()
const editorStore = useEditorStore()
const fileDialog = useFileDialog()

/** 空状态「上传角色」：本地文件导入后自动选中（图片/ .bgs / .bsf / svg） */
async function onEmptyUpload() {
  const result = await fileDialog.openFile(SPRITE_ACCEPT)
  if (!result) return
  const id = await importSpriteFile(result.file, result.name)
  if (id) resourceStore.selectedSpriteId = id
}

/** 当前角色素材的自然尺寸（.bsf 用 canvas，其余用首帧图片尺寸）：自动渲染模式的判定依据 */
const spriteNaturalW = ref(0)
const spriteNaturalH = ref(0)

const imageRenderingStyle = computed(() =>
  cssImageRendering(editorStore.renderMode, spriteNaturalW.value, spriteNaturalH.value),
)

/**
 * 画布图片的显示尺寸 = 帧原始尺寸 × 缩放。
 * 采用 canvas 自绘（而非 <img> + image-rendering）：WKWebView 下被放大的图层会走
 * 合成层平滑重采样，pixelated 直接被覆盖，小素材一放大就糊；canvas 里
 * imageSmoothingEnabled=false 就是最近邻采样（等价 Godot 纹理过滤设 nearest）。
 */
const canvasFrameNatural = ref<{ w: number; h: number } | null>(null)

/** 光栅化安全上限（像素）：大插画 × 高倍缩放不能无限放大布局尺寸，否则显存/内存爆掉 */
const RASTER_CAP = 4096

/** 参与布局的缩放倍率：小图（≤128px）在 32× 上限内永远走布局放大，始终清晰 */
const canvasLayoutZoom = computed(() => {
  const size = canvasFrameNatural.value
  if (!size) return canvasZoom.value
  const naturalMax = Math.max(size.w, size.h, 1)
  return Math.min(canvasZoom.value, RASTER_CAP / naturalMax)
})

/** 超出光栅上限的余量交给合成层缩放（倍数很小，观感损失可忽略） */
const canvasResidualScale = computed(() =>
  canvasLayoutZoom.value > 0 ? canvasZoom.value / canvasLayoutZoom.value : 1,
)

const canvasWrapperStyle = computed(() => {
  const parts: string[] = []
  if (canvasPanX.value || canvasPanY.value) {
    parts.push(`translate(${canvasPanX.value}px, ${canvasPanY.value}px)`)
  }
  if (Math.abs(canvasResidualScale.value - 1) > 0.001) {
    parts.push(`scale(${canvasResidualScale.value})`)
  }
  return parts.length > 0 ? { transform: parts.join(' ') } : {}
})

/** 标注层：画布坐标 + transform 缩放（缩放不影响图片采样，只放大矢量手柄） */
const annoLayerStyle = computed(() => {
  const canvas = currentSprite.value?.bsf?.canvas
  if (!canvas) return {}
  return {
    width: `${canvas.w}px`,
    height: `${canvas.h}px`,
    transform: `scale(${canvasLayoutZoom.value})`,
  }
})

// ─── canvas 自绘：画布帧 + 预览帧（采样方式由 imageSmoothingEnabled 决定） ───
const spriteCanvasEl = ref<HTMLCanvasElement | null>(null)
const previewCanvasEl = ref<HTMLCanvasElement | null>(null)
/** 帧图片解码缓存（key = 帧 url；同一帧反复重绘/缩放只解码一次） */
const frameImages = new Map<string, HTMLImageElement>()
let spriteDrawToken = 0
let previewDrawToken = 0

async function frameImage(url: string): Promise<HTMLImageElement> {
  const cached = frameImages.get(url)
  if (cached) return cached
  const img = await loadImage(url)
  frameImages.set(url, img)
  return img
}

async function drawSpriteFrame() {
  const el = spriteCanvasEl.value
  const frame = currentSprite.value?.frames[canvasDisplayIndex.value]
  if (!el || !frame) return
  const token = ++spriteDrawToken
  const img = await frameImage(frame.url).catch(() => null)
  if (!img || token !== spriteDrawToken) return
  const natural = { w: img.naturalWidth || img.width, h: img.naturalHeight || img.height }
  // 先落原始尺寸：光栅上限与标注层对齐都以它为准（.bsf 各帧同画布，.bgs 可能不同）
  canvasFrameNatural.value = natural
  const zoom = canvasLayoutZoom.value
  drawImageCrisp(
    el,
    img,
    natural.w * zoom,
    natural.h * zoom,
    imageRenderingStyle.value !== 'pixelated',
    RASTER_CAP,
  )
}

async function drawPreviewFrame() {
  const el = previewCanvasEl.value
  const frame = currentSprite.value?.frames[selectedFrameIndex.value]
  if (!el || !frame) return
  const token = ++previewDrawToken
  const img = await frameImage(frame.url).catch(() => null)
  if (!img || token !== previewDrawToken) return
  const natural = { w: img.naturalWidth || img.width, h: img.naturalHeight || img.height }
  const scale = previewScale.value
  drawImageCrisp(
    el,
    img,
    Math.min(natural.w, 248) * scale,
    Math.min(natural.h, 248) * scale,
    imageRenderingStyle.value !== 'pixelated',
  )
}

function redrawSpriteImages() {
  drawSpriteFrame()
  drawPreviewFrame()
}

const currentSprite = ref<SpriteData | null>(null)
const currentSpritePath = ref('')
// 当前已加载角色对应的资源 id：用于区分「重命名当前角色」与「切换到别的角色」
const currentSpriteId = ref<string | null>(null)
/** 载入失败信息（读盘/解析异常直接显示出来，避免"点了没反应"看起来像跳转失败） */
const loadError = ref<string | null>(null)
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
/** 标注层：屏幕坐标 → 画布坐标用它实测的包围盒反推比例（含 pan/缩放/余量缩放） */
const annoLayerRef = ref<HTMLDivElement | null>(null)

const costumeContextMenu = ref<{ show: boolean; x: number; y: number; index: number }>({ show: false, x: 0, y: 0, index: 0 })
const animContextMenu = ref<{ show: boolean; x: number; y: number; name: string }>({ show: false, x: 0, y: 0, name: '' })
const renamingAnim = ref<string | null>(null)
const renameInputRef = ref<HTMLInputElement | null>(null)
let playTimer: ReturnType<typeof setInterval> | null = null

// ─── 造型列表拖拽排序（PS 图层面板观感：快照跟手 + 插入线） ───
const costumeListEl = ref<HTMLElement | null>(null)
const {
  draggingIndex: frameDragIndex,
  ghost: frameDragGhost,
  indicator: frameDropIndicator,
  onItemMouseDown: onCostumeMouseDown,
  shouldSuppressClick: shouldSuppressCostumeClick,
} = useFrameReorder({
  orientation: 'vertical',
  count: () => currentSprite.value?.frames.length ?? 0,
  getItemEls: () => Array.from(costumeListEl.value?.querySelectorAll<HTMLElement>('.costume-item') ?? []),
  getScrollEl: () => costumeListEl.value,
  onReorder: (from, to) => moveCostume(from, to),
})

watch(
  () => resourceStore.selectedSpriteId,
  (id) => {
    if (!id) {
      // 项目切换/资源清空后不得残留上一个项目的角色
      revokeSpriteUrls(currentSprite.value)
      currentSprite.value = null
      currentSpritePath.value = ''
      currentSpriteId.value = null
      loadError.value = null
      return
    }
    const item = resourceStore.sprites.find(s => s.id === id)
    if (item && item.path) loadSprite(item)
  },
  { immediate: true }
)

// 资源面板重命名当前角色后 item.path 会变：只同步保存路径，不重新加载（内容未变，避免打断编辑）。
// 不处理切换角色的场景（selectedSpriteId 与已加载 id 不一致），那个由上面的 loadSprite 负责
watch(
  () => resourceStore.sprites.find(s => s.id === resourceStore.selectedSpriteId)?.path,
  (p) => {
    if (!p || !currentSprite.value) return
    if (resourceStore.selectedSpriteId !== currentSpriteId.value) return
    if (p !== currentSpritePath.value) currentSpritePath.value = p
  }
)

// 自动保存：每次修改后写回 config.json / manifest.json
let saveTimer: ReturnType<typeof setTimeout> | null = null
// 默认渲染帧是否被改过：保存成功后据此刷新资源面板缩略图（其他字段修改不需要）
let defaultFrameDirty = false
function scheduleSave() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(persistSprite, 300)
}

/**
 * 落盘：
 * - .bsf 角色写 manifest.json（clips + pivot/碰撞/挂点）
 * - 单图角色（png 等）：中心点/碰撞/挂点无处可存 → 首次落盘时转正为 .bsf 目录
 * - 旧 .bgs 目录角色写 config.json（segments）
 */
async function persistSprite() {
  const sprite = currentSprite.value
  let path = currentSpritePath.value
  if (!sprite || !path) return
  try {
    if (sprite.bsf) {
      if (isImageSpritePath(path)) {
        path = await imageSpriteToBsfDir(path, sprite)
        currentSpritePath.value = path
        if (resourceStore.selectedSpriteId) resourceStore.updateItemPath(resourceStore.selectedSpriteId, path)
      } else {
        await saveBsfManifest(path, sprite)
      }
    } else {
      await saveSpriteConfig(path, sprite)
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
}

/** 记录当前角色的自然尺寸（自动渲染模式的判定依据）：.bsf 取画布，其余取首帧图片尺寸 */
async function updateSpriteNaturalSize() {
  const sprite = currentSprite.value
  if (!sprite) return
  if (sprite.bsf) {
    spriteNaturalW.value = sprite.bsf.canvas.w
    spriteNaturalH.value = sprite.bsf.canvas.h
    return
  }
  try {
    const img = await loadImage(sprite.frames[0].blob)
    spriteNaturalW.value = img.naturalWidth || img.width
    spriteNaturalH.value = img.naturalHeight || img.height
  } catch {
    spriteNaturalW.value = 0
    spriteNaturalH.value = 0
  }
}

async function loadSprite(item: { id: string; name: string; path: string }) {
  // 防重复加载：同一个角色不重新加载
  if (currentSpritePath.value === item.path && currentSprite.value) return
  try {
    // 释放旧的 ObjectURL 防止内存泄漏
    revokeSpriteUrls(currentSprite.value)
    // 图片角色 → 单帧；.bsf 目录 → manifest + sheet 裁帧；.bgs 目录 → config.json
    currentSprite.value = await readSpriteFromPath(item.path)
    // 单图角色（单张 png/jpg 贴图）：内存合成单帧 .bsf 元数据，让中心/碰撞/标记工具可用；
    // 只有 manifest 能承载这些标注，首次标注落盘时转正为 .bsf 目录（见 persistSprite）
    if (!currentSprite.value.bsf && isImageSpritePath(item.path)) {
      try {
        currentSprite.value.bsf = await buildSingleFrameBsfMeta(currentSprite.value)
      } catch (e) {
        console.warn('[SpriteEditor] 单图角色标注元数据合成失败:', e)
      }
    }
    currentSpritePath.value = item.path
    currentSpriteId.value = item.id
    loadError.value = null
    // 自然尺寸：.bsf 取画布（sheet 是几十帧拼图，尺寸不能当素材尺寸），其余取首帧图片尺寸
    await updateSpriteNaturalSize()
    // 画布帧尺寸与解码缓存都属于上一个角色，换角色先清掉
    canvasFrameNatural.value = null
    frameImages.clear()
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
    loadError.value = e instanceof Error ? e.message : String(e)
  }
}

function selectFrame(index: number) {
  stopAnimation()
  selectedFrameIndex.value = index
  costumeHighlightIndex.value = index
  canvasDisplayIndex.value = index
  markDefaultFrame(index)
}

/** 点击/双击前检查拖拽尾随 click，防止排序后误选旧下标的帧 */
function onCostumeClick(index: number) {
  if (shouldSuppressCostumeClick()) return
  selectFrame(index)
}

function onCostumeDblClick(index: number) {
  if (shouldSuppressCostumeClick()) return
  emit('openPaintEdit', index)
}

/** 拖拽排序造型帧：帧列表与 .bsf 帧元数据同步换位，动画段继续按位置区间生效 */
function moveCostume(from: number, to: number) {
  const sprite = currentSprite.value
  const count = sprite?.frames.length ?? 0
  if (!sprite || from === to || from < 0 || to < 0 || from >= count || to >= count) return
  const moveItem = <T,>(arr: T[]) => {
    const [item] = arr.splice(from, 1)
    arr.splice(to, 0, item)
  }
  moveItem(sprite.frames)
  // 帧级中心/碰撞/标记覆盖挂在 bsf.frames 上，必须与可见帧同步换位
  if (sprite.bsf) moveItem(sprite.bsf.frames)
  // 动画段是位置区间：区间编号不动；显式 clip 序列保存时按区间重建
  for (const anim of sprite.animations) anim.frameNames = undefined
  // 拖拽的帧成为当前造型（与点击选中一致，默认渲染帧/缩略图同步）
  defaultFrameDirty = true
  selectFrame(to)
  scheduleSave()
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

// ═══ 中心点标注（.bsf 角色 / 单图角色合成单帧 bsf：manifest 带 pivot 元数据） ═══

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

// ═══ 碰撞标注（.bsf / 单图角色；无自定义 = 引擎自动碰撞，学生默认路径） ═══

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

/** 禁用碰撞：整角色不参与地形/边界物理阻挡（碰撞形状保留，重新勾选即恢复） */
const collisionDisabled = computed(() => !!currentSprite.value?.bsf?.collisionDisabled)

function onCollisionDisabledChange(e: Event) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  bsf.collisionDisabled = (e.target as HTMLInputElement).checked
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
    // 已禁用碰撞时不写入形状数据，避免关闭状态反而产生无意义的碰撞体
    if (
      !bsf.collisionDisabled &&
      !bsf.collision &&
      !bsf.frames[annoFrameIndex.value]?.collision
    ) {
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

/**
 * 标记名称输入草稿：输入框必须用本地状态（v-model），
 * 不能单向绑定 :value——动画播放时组件每帧重渲染会把用户正在删改的文字重置回原名
 */
const markerNameDraft = ref('')
watch(selMarkerName, (name) => {
  markerNameDraft.value = name ?? ''
}, { immediate: true })

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

/** 提交标记改名（失焦/回车）：空名或重名时回显原名，不生效 */
function commitMarkerRename() {
  const name = selMarkerName.value
  if (!name) return
  const trimmed = markerNameDraft.value.trim()
  if (!trimmed || trimmed === name || markerNames.value.includes(trimmed)) {
    markerNameDraft.value = name
    return
  }
  renameMarker(name, trimmed)
}

/** 取消标记改名（Esc）：丢弃草稿并退出输入 */
function cancelMarkerRename(e: KeyboardEvent) {
  markerNameDraft.value = selMarkerName.value ?? ''
  ;(e.target as HTMLInputElement).blur()
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

/**
 * 屏幕坐标 → 逻辑画布坐标（0.5px 吸附）。
 * 不能手算 zoom/pan 逆变换：标注层既被 canvasLayoutZoom 缩放，又可能被外层的
 * 「余量缩放」(canvasResidualScale) 二次缩放，手算极易漏项（旧实现把画布中心
 * 偏移当未缩放处理，缩放≠1 时中心点/标记就会偏离鼠标）。
 * 直接读标注层实际包围盒反推比例，与 CollisionShapeOverlay 同一套算法。
 */
function screenToCanvas(e: MouseEvent): { x: number; y: number } | null {
  const el = annoLayerRef.value
  const bsf = currentSprite.value?.bsf
  if (!el || !bsf || bsf.canvas.w <= 0 || bsf.canvas.h <= 0) return null
  const rect = el.getBoundingClientRect()
  if (rect.width <= 0 || rect.height <= 0) return null
  const lx = (e.clientX - rect.left) / (rect.width / bsf.canvas.w)
  const ly = (e.clientY - rect.top) / (rect.height / bsf.canvas.h)
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

// 帧切换 / 缩放 / 预览倍率 / 渲染模式变化 → 重绘（flush: post 保证 canvas 已挂载）
// 注意：必须放在所有 ref/computed 声明之后——watch 创建时会立即求值一次来源，
// 提前注册会在 setup 阶段抛 TDZ（Cannot access 'canvasZoom' before initialization），
// 整个角色编辑器挂载失败、连 Vue 的更新队列都会卡住
watch(
  [
    () => currentSprite.value?.frames[canvasDisplayIndex.value]?.url,
    () => currentSprite.value?.frames[selectedFrameIndex.value]?.url,
    () => canvasZoom.value,
    () => previewScale.value,
    () => editorStore.renderMode,
  ],
  () => redrawSpriteImages(),
  { flush: 'post' },
)

// 注册全局 mouseup 监听
onMounted(() => {
  document.addEventListener('mouseup', onGlobalMouseUp)
  // 中心/标记拖拽用全局监听：拖出画布也不中断
  document.addEventListener('mousemove', onPivotDragMove)
  document.addEventListener('mouseup', onPivotDragUp)
  document.addEventListener('mousemove', onMarkerDragMove)
  document.addEventListener('mouseup', onMarkerDragUp)
  // 首屏：canvas 挂载后按当前帧画一次
  nextTick(redrawSpriteImages)
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
    <!-- 载入失败提示：路径失效 / 目录缺 manifest.json 等会走到这里（否则页面一片空白像是没跳转） -->
    <div v-if="loadError" class="load-error">
      角色载入失败：{{ loadError }}
      <span class="load-error-path">{{ currentSpritePath }}</span>
    </div>
    <!-- 左: 造型列表 (100px) + 追加抽屉 -->
    <div class="costume-list-wrap">
      <div
        ref="costumeListEl"
        class="costume-list"
        :class="{ 'costume-list-dragging': frameDragIndex !== null }"
      >
        <div
          v-for="(frame, idx) in (currentSprite?.frames || [])"
          :key="idx"
          class="costume-item"
          :class="{
            'costume-item-active': costumeHighlightIndex === idx,
            'costume-item-dragging': frameDragIndex === idx,
          }"
          title="拖拽可调整顺序，双击进入绘制编辑"
          @click="onCostumeClick(idx)"
          @dblclick.stop="onCostumeDblClick(idx)"
          @contextmenu="onCostumeContextMenu($event, idx)"
          @mousedown="onCostumeMouseDown(idx, $event)"
        >
          <img :src="frame.url" class="costume-thumb" :style="{ imageRendering: imageRenderingStyle }" draggable="false" />
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
          <div class="props-sep"></div>
          <label class="anno-checkbox" title="关闭后不参与物理：不会被墙壁、地面挡住，也不受重力下落">
            <input
              type="checkbox"
              :checked="collisionDisabled"
              @change="onCollisionDisabledChange"
            />
            <span>禁用碰撞</span>
          </label>
        </template>
        <template v-else>
          <!-- 标记：画布点选操作 + 添加/改名/删除 + 坐标 + 作用域 -->
          <div class="props-sep"></div>
          <button class="preset-btn" type="button" title="添加标记" @click="addMarker">添加</button>
          <input
            v-if="selMarkerName"
            class="marker-rename-input"
            v-model="markerNameDraft"
            title="标记名称"
            @blur="commitMarkerRename"
            @keydown.enter="($event.target as HTMLInputElement).blur()"
            @keydown.escape="cancelMarkerRename"
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
            :style="canvasWrapperStyle"
          >
            <!-- 帧图由 canvas 自绘：采样方式（最近邻/平滑）由 imageSmoothingEnabled 决定，
                 不受浏览器对 <img> 放大时的合成层重采样影响 -->
            <canvas
              v-if="currentSprite?.frames[canvasDisplayIndex]"
              ref="spriteCanvasEl"
              class="canvas-sprite"
              :style="{ imageRendering: imageRenderingStyle }"
            />
            <!-- 标注层：画布坐标 + transform 缩放（手柄内部再 1/zoom 反向缩放保持屏幕尺寸恒定） -->
            <div
              v-if="canAnno && currentSprite?.bsf"
              ref="annoLayerRef"
              class="canvas-anno-layer"
              :style="annoLayerStyle"
            >
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
                v-if="activeAnnoLayer === 'collision'"
                :canvas-w="currentSprite.bsf.canvas.w"
                :canvas-h="currentSprite.bsf.canvas.h"
                :shape="collisionDisplay"
                :zoom="canvasZoom"
                :disabled="collisionDisabled"
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
        </div>
      </div>
    </div>

    <!-- 右: 预览面板 (264px) -->
    <div class="preview-panel">
      <div class="preview-label">ANIMATION</div>

      <!-- 预览区域 256×256 -->
      <div class="preview-bg">
        <div class="preview-image-box" :style="getPreviewBgStyle()">
          <div class="preview-image-wrap">
            <canvas
              v-if="currentSprite?.frames[selectedFrameIndex]"
              ref="previewCanvasEl"
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

    <!-- 空状态：项目里还没有任何角色 -->
    <div v-if="resourceStore.sprites.length === 0" class="sprite-empty-banner">
      <div class="empty-content">
        <img :src="iconSpriteEmpty" class="empty-icon" alt="" />
        <p class="empty-text">请先选择、绘制或上传角色</p>
        <div class="empty-actions">
          <button class="empty-btn" @click="emit('openSpriteLibrary')">选择角色</button>
          <button class="empty-btn empty-btn-secondary" @click="emit('openPaintNew')">绘制角色</button>
          <button class="empty-btn empty-btn-secondary" @click="onEmptyUpload">上传角色</button>
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

    <!-- 拖拽排序：插入线 + 跟随光标的造型快照（PS 图层面板观感） -->
    <Teleport to="body">
      <div
        v-if="frameDropIndicator"
        class="frame-drop-line"
        :style="{
          left: frameDropIndicator.x + 'px',
          top: frameDropIndicator.y + 'px',
          width: frameDropIndicator.length + 'px',
        }"
      ></div>
      <div
        v-if="frameDragGhost"
        class="costume-drag-ghost"
        :style="{ left: frameDragGhost.x + 'px', top: frameDragGhost.y + 'px' }"
      >
        <img
          v-if="currentSprite?.frames[frameDragGhost.index]"
          :src="currentSprite.frames[frameDragGhost.index].url"
          class="costume-ghost-thumb"
          :style="{ imageRendering: imageRenderingStyle }"
          draggable="false"
        />
        <span class="costume-ghost-label">帧 {{ frameDragGhost.index + 1 }}</span>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.load-error {
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 40;
  max-width: 80%;
  padding: 8px 12px;
  border-radius: 6px;
  background: rgba(95, 45, 39, 0.95);
  border: 1px solid #a1443a;
  color: #ffd9d4;
  font-size: 12px;
  line-height: 1.5;
}
.load-error-path {
  display: block;
  margin-top: 4px;
  color: #ffb3a8;
  font-size: 11px;
  word-break: break-all;
}
.sprite-editor-page {
  position: relative;
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
/* 拖拽源：压暗但保留原位置（PS 图层面板观感） */
.costume-item.costume-item-dragging {
  opacity: 0.35;
  cursor: grabbing;
}
.costume-list-dragging .costume-item {
  cursor: grabbing;
}

/* ─── 拖拽快照 / 插入线（fixed，不被列表容器裁剪） ─── */
.frame-drop-line {
  position: fixed;
  height: 2px;
  border-radius: 2px;
  background: var(--accent);
  box-shadow: 0 0 0 1px rgba(34, 37, 43, 0.85), 0 0 10px rgba(91, 251, 132, 0.6);
  transform: translateY(-50%);
  pointer-events: none;
  z-index: 99999;
}
.costume-drag-ghost {
  position: fixed;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4px;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  background: var(--bg-darker);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.5);
  opacity: 0.85;
  transform: translate(-50%, -50%) scale(1.03);
  pointer-events: none;
  z-index: 100000;
}
.costume-ghost-thumb {
  width: 78px;
  height: 60px;
  object-fit: contain;
}
.costume-ghost-label {
  font-size: 10px;
  line-height: 1;
  color: var(--accent);
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
  position: relative;
  /* 以中心为原点缩放：超出光栅上限的余量由外层 transform 补齐时仍然居中 */
  transform-origin: center center;
}
/* 标注层：尺寸=画布坐标尺寸，zoom 由 transform 提供（只放大矢量 UI，不影响图片采样） */
.canvas-anno-layer {
  position: absolute;
  left: 0;
  top: 0;
  transform-origin: 0 0;
  pointer-events: none;
}
.canvas-anno-layer > * { pointer-events: auto; }
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
  /* 窄窗口下工具条本身不换行、不压缩：按钮保持原尺寸，内容超出时横向滚动（滚动条隐藏） */
  flex-wrap: nowrap;
  white-space: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
}
.anno-toolbar::-webkit-scrollbar { display: none; }
/* 工具条内所有控件禁止收缩，避免图标/文字被挤成竖排 */
.anno-toolbar > * { flex-shrink: 0; }
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
  white-space: nowrap;
  flex-shrink: 0;
}
.layer-chip:hover:not(:disabled) { background: var(--bg-hover); color: #fff; }
.layer-chip.active { border-color: var(--accent); color: var(--accent); background: rgba(91, 251, 132, 0.08); }
.layer-chip:disabled { opacity: 0.4; cursor: not-allowed; }
.layer-chip .soon { font-size: 9px; opacity: 0.7; margin-left: 2px; }
.layer-chip-icon { width: 14px; height: 14px; flex-shrink: 0; }
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
  cursor: default;
  z-index: 5;
}
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
  left: -13px;
  top: -24px;
  width: 26px;
  height: 26px;
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
  left: 14px;
  top: -24px;
  font-size: 14px;
  line-height: 18px;
  color: var(--mk-color);
  background: rgba(34, 37, 43, 0.85);
  padding: 0 5px;
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
  border-color: var(--accent);
}
.anno-toolbar .marker-rename-input { height: 20px; }

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
/* 禁用碰撞开关（与地图编辑器碰撞层工具栏同款） */
.anno-checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
  color: #9ca0a4;
  font-size: 12px;
  white-space: nowrap;
}
.anno-checkbox input[type="checkbox"] {
  width: 14px;
  height: 14px;
  margin: 0;
  accent-color: #528bff;
  cursor: pointer;
}
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
/* 尺寸由 drawImageCrisp 按「min(自然尺寸,248) × 预览倍率」写入（canvas 自绘，采样自控） */
.preview-image {
  display: block;
}
/* 预览图包裹层：仅作排布容器（缩放已在图片自身尺寸上完成） */
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

/* ═══ 空状态横幅（与地图编辑器空状态保持一致） ═══ */
.sprite-empty-banner {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: rgba(41, 44, 52, 0.95);
  z-index: 30;
}
.empty-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.empty-icon {
  width: 48px;
  height: 48px;
  color: #3D4048;
}
.empty-text {
  color: #8B8FA3;
  font-size: 14px;
  margin: 0;
}
.empty-actions {
  display: flex;
  gap: 12px;
}
.empty-btn {
  padding: 8px 24px;
  border-radius: 6px;
  border: 1px solid #3D4048;
  background: #4B9B5C;
  color: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.empty-btn:hover {
  background: #5bc772;
  border-color: #5bc772;
}
.empty-btn-secondary {
  background: #3D4048;
}
.empty-btn-secondary:hover {
  background: #4D5058;
  border-color: #4D5058;
}
</style>
