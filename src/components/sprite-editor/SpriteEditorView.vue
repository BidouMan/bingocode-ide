<script setup lang="ts">
import { ref, reactive, computed, watch, watchEffect, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useResourceStore } from '../../stores/resource'
import { useEditorStore } from '../../stores/editor'
import { invoke } from '@tauri-apps/api/core'
import type { SpriteData, SpriteAnimation, SpriteTransform, SpriteFrame } from '../../composables/useSpriteData'
import { readSpriteFromPath, revokeSpriteUrls, saveSpriteConfig, saveBsfManifest, isImageSpritePath, buildSingleFrameBsfMeta, imageSpriteToBsfDir, loadImage, DEFAULT_SPRITE_TRANSFORM, imageContentBox } from '../../composables/useSpriteData'
import type { SpriteCollisionShape } from '../../composables/useSpriteData'
import { appendFramesToSprite } from '../../composables/appendSpriteFrames'
import { useFrameReorder } from '../../composables/useFrameReorder'
import { useSpriteHistory } from './useSpriteHistory'
import { cssImageRendering, detectPixelArt } from '../../utils/renderMode'
import { drawImageCrisp } from '../../utils/pixelCanvas'
import { snapRectOffset, snapThreshold } from '../../utils/smartSnap'
import FrameUploadDrawer from './FrameUploadDrawer.vue'
import CollisionShapeOverlay from './CollisionShapeOverlay.vue'
// 下拉框复用地图编辑器属性面板的自绘组件，保证两个编辑器的控件样式一致
import CustomSelect from '../common/CustomSelect.vue'
// 类型（tag）预设：角色按玩法身份分类，与地图的墙体/地面等类型分开
import {
  ONE_WAY_DIRECTIONS,
  PHYSICS_MATERIAL_OPTIONS,
  SPRITE_COLLISION_TAG_PRESETS,
  SPRITE_DEFAULT_COLLISION_TAG,
} from '../../utils/shapeStyle'

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
// ?raw：中心锚点图形直接内联成 <svg> 元素（不依赖 <img> 资源加载，避免 WebView 里加载/解码失败导致不可见）
import iconPivotAnchorSvgRaw from '../../assets/icons/中心锚点.svg?raw'
import iconResetAnchor from '../../assets/icons/重置锚点.svg'
// 变换行独立重置图标（Godot 风格）
import iconReset from '../../assets/icons/重置.svg'
import iconMarker from '../../assets/icons/标记.svg'
import iconMarkerRaw from '../../assets/icons/标记.svg?raw'
import iconAnimation from '../../assets/icons/动画.svg'
import iconSpriteEmpty from '../../assets/icons/角色精灵.svg'
import iconSelectTool from '../../assets/icons/选择箭头.svg'
import iconZoomIn from '../../assets/icons/add-one.svg'
import iconZoomOut from '../../assets/icons/reduce-one.svg'
import iconUndo from '../../assets/icons/undo.svg'
import iconRedo from '../../assets/icons/redo.svg'
// 属性面板分区折叠箭头（与地图编辑器检视器同一个图标）
import iconChevron from '../../assets/icons/right_arrow.svg'

const resourceStore = useResourceStore()
const editorStore = useEditorStore()
const fileDialog = useFileDialog()

/** 中心锚点图形标记：去掉 XML 声明、给根 svg 内联尺寸，直接内联进 DOM（画布与变换手柄中心共用）
 *  （v-html 注入的节点拿不到 scoped 样式，尺寸必须写在 svg 自身的 style 上） */
const pivotAnchorMarkup = iconPivotAnchorSvgRaw
  .slice(iconPivotAnchorSvgRaw.indexOf('<svg'))
  .replace('<svg', '<svg style="display:block;width:100%;height:100%"')

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
/**
 * 画风判定（像素画 / 插画）：自动模式下优先于尺寸。
 * null = 尚未分析完成，此时按尺寸兜底（见 utils/renderMode.ts）。
 */
const spritePixelArt = ref<boolean | null>(null)

const imageRenderingStyle = computed(() =>
  cssImageRendering(
    editorStore.renderMode,
    spriteNaturalW.value,
    spriteNaturalH.value,
    spritePixelArt.value,
  ),
)

/**
 * 画布图片的显示尺寸 = 帧原始尺寸 × 缩放。
 * 采用 canvas 自绘（而非 <img> + image-rendering）：WKWebView 下被放大的图层会走
 * 合成层平滑重采样，pixelated 直接被覆盖，小素材一放大就糊；canvas 里
 * imageSmoothingEnabled=false 就是最近邻采样（等价 Godot 纹理过滤设 nearest）。
 */
const canvasFrameNatural = ref<{ w: number; h: number } | null>(null)

/** 非 .bsf 角色（旧 .bgs）：当前帧非透明内容框，用于中心点/包围盒（引擎也是内容重心定位） */
const nonBsfBox = ref<{ url: string; box: { x: number; y: number; w: number; h: number } } | null>(null)
let nonBsfMeasureToken = 0

async function measureNonBsfBox() {
  const sprite = currentSprite.value
  const frame = sprite?.frames[canvasDisplayIndex.value]
  if (!sprite || sprite.bsf || !frame) {
    nonBsfBox.value = null
    return
  }
  const token = ++nonBsfMeasureToken
  try {
    const img = await frameImage(frame.url)
    if (token !== nonBsfMeasureToken) return
    nonBsfBox.value = { url: frame.url, box: imageContentBox(img) }
  } catch {
    if (token === nonBsfMeasureToken) nonBsfBox.value = null
  }
}

/** 光栅化安全上限（像素）：大插画 × 高倍缩放不能无限放大布局尺寸，否则显存/内存爆掉 */
const RASTER_CAP = 4096

/** 角色场景变换：未写入数据时用默认值（原点 / 0° / 100%，即不改变引擎默认出生位置） */
const sceneTransform = computed<SpriteTransform>(
  () => currentSprite.value?.transform ?? DEFAULT_SPRITE_TRANSFORM,
)

/** 角色实际显示倍率（分轴）= 场景缩放 × 角色缩放百分比（屏幕像素 / 素材像素） */
const displayZoomX = computed(() => {
  const t = sceneTransform.value
  return canvasZoom.value * (Math.max(5, t.scaleX ?? t.scale) / 100)
})
const displayZoomY = computed(() => {
  const t = sceneTransform.value
  return canvasZoom.value * (Math.max(5, t.scaleY ?? t.scale) / 100)
})

/** 综合显示倍率：非等比缩放时取两轴较大值（布局光栅按最大倍率准备，另一轴缩小后依然清晰） */
const displayZoom = computed(() => Math.max(displayZoomX.value, displayZoomY.value))

/** 参与布局的缩放倍率：小图（≤128px）在 32× 上限内永远走布局放大，始终清晰 */
const canvasLayoutZoom = computed(() => {
  const size = canvasFrameNatural.value
  if (!size) return displayZoom.value
  const naturalMax = Math.max(size.w, size.h, 1)
  return Math.min(displayZoom.value, RASTER_CAP / naturalMax)
})

/** 场景世界层：屏幕中心为世界原点，pan 平移 + zoom 缩放；子元素用世界坐标（y 向上取负） */
const sceneWorldStyle = computed(() => ({
  transform: `translate(${canvasPanX.value}px, ${canvasPanY.value}px) scale(${canvasZoom.value})`,
}))

/**
 * 角色对象：定位在场景锚点（当前帧包围盒中心），围绕锚点旋转 + 剩余缩放。
 * 画布已按 canvasLayoutZoom 光栅化，这里只补 (角色缩放 / 光栅倍率) 的余量。
 * 支持 X / Y 分轴缩放（取消「约束比例」后可设置不同宽高比）。
 */
const spriteObjectStyle = computed(() => {
  const t = sceneTransform.value
  const layout = canvasLayoutZoom.value
  const sx = Math.max(5, t.scaleX ?? t.scale)
  const sy = Math.max(5, t.scaleY ?? t.scale)
  const objectScaleX = layout > 0 ? (sx / 100) / layout : 1
  const objectScaleY = layout > 0 ? (sy / 100) / layout : 1
  const parts = [`rotate(${-t.angle}deg)`]
  if (Math.abs(objectScaleX - 1) > 0.0001 || Math.abs(objectScaleY - 1) > 0.0001) {
    parts.push(`scale(${objectScaleX}, ${objectScaleY})`)
  }
  return {
    left: `${t.x}px`,
    top: `${-t.y}px`,
    transform: parts.join(' '),
    transformOrigin: '0 0',
  }
})

/** 帧画布：以场景锚点（包围盒中心）为原点摆放 */
const frameCanvasStyle = computed(() => {
  const p = objectAnchor.value
  const layout = canvasLayoutZoom.value
  return { left: `${-p.x * layout}px`, top: `${-p.y * layout}px` }
})

/** 标注层：画布坐标 + transform 缩放（缩放不影响图片采样，只放大矢量手柄） */
const annoLayerStyle = computed(() => {
  const canvas = currentSprite.value?.bsf?.canvas
  if (!canvas) return {}
  const p = objectAnchor.value
  const layout = canvasLayoutZoom.value
  return {
    left: `${-p.x * layout}px`,
    top: `${-p.y * layout}px`,
    width: `${canvas.w}px`,
    height: `${canvas.h}px`,
    transform: `scale(${layout})`,
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
  // 旧 .bgs 角色没有 manifest：量出内容框，让中心点与包围盒对齐引擎语义
  if (!currentSprite.value?.bsf) measureNonBsfBox()
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

// ─── 属性面板「角色信息 → 名称」：可改名（同步磁盘目录/文件名，与资源面板右键改名同一套规则） ───
/**
 * 显示名以资源管理器里的名字为准（素材库的中文名 / 文件名），
 * 不用 manifest 内部 name —— 那是素材作者在制作软件里取的名字（如 fish_7）。
 */
const spriteDisplayName = computed(() => {
  const id = currentSpriteId.value || resourceStore.selectedSpriteId
  const item = id ? resourceStore.sprites.find(s => s.id === id) : null
  return item?.name || currentSprite.value?.name || ''
})
const spriteNameDraft = ref('')
watch(
  spriteDisplayName,
  (name) => { spriteNameDraft.value = name ?? '' },
  { immediate: true },
)

const SPRITE_IMAGE_EXT = /\.(png|jpg|jpeg|gif|bmp|webp)$/i

/** 改名输入校验：只允许单层名字——空名、`.`、`..`、含路径分隔符一律拒绝（防路径穿越） */
function normalizeSpriteName(raw: string): string | null {
  const val = raw.trim()
  if (!val || val === '.' || val === '..') return null
  if (/[/\\]/.test(val)) return null
  return val
}

/** 改名提交：先迁移磁盘路径（目录角色整体改名，图片角色保留扩展名），成功后再改显示名 */
async function commitSpriteRename() {
  const sprite = currentSprite.value
  const id = currentSpriteId.value
  const item = id ? resourceStore.sprites.find(s => s.id === id) : null
  if (!sprite || !item) return
  const oldName = item.name
  const val = normalizeSpriteName(spriteNameDraft.value)
  if (!val || val === oldName) { spriteNameDraft.value = oldName; return }

  let newPath: string | null = null
  // 以资源项的真实路径为准（显示名可能与磁盘名不一致），并只改同级的名字，不改变所在目录
  const srcPath = item.path
  if (srcPath) {
    try {
      if (await invoke<boolean>('path_exists', { path: srcPath })) {
        const sepIdx = Math.max(srcPath.lastIndexOf('/'), srcPath.lastIndexOf('\\'))
        if (sepIdx < 0) throw new Error('资源路径无效')
        const sep = srcPath[sepIdx]
        const parent = srcPath.slice(0, sepIdx)
        const ext = SPRITE_IMAGE_EXT.exec(srcPath)?.[0] ?? ''
        const target = `${parent}${sep}${val}${ext}`
        if (target === srcPath) { spriteNameDraft.value = oldName; return }
        // 目标已存在时拒绝，避免把别人的角色覆盖/合并
        if (await invoke<boolean>('path_exists', { path: target })) throw new Error('同名角色已存在')
        await invoke('rename_path', { oldPath: srcPath, newPath: target })
        newPath = target
      }
    } catch (e) {
      console.error('[SpriteEditor] 重命名角色失败:', e)
      spriteNameDraft.value = oldName
      return
    }
  }

  resourceStore.renameItem(item.id, val)
  sprite.name = val
  if (newPath) {
    item.path = newPath
    currentSpritePath.value = newPath
  }
}
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

// ─── 撤销 / 重做（右下角浮动工具条）：整份可编辑状态快照 ───
// 一次拖动（连续 mousemove）或一次停顿内的连续输入合并成一步，见 useSpriteHistory
/** 删除造型时被主动释放的帧 objectURL：撤销/重做复原该帧时按 blob 重建，既回收内存又不会裂图 */
const revokedFrameUrls = new Set<string>()
function restoreFrameUrl(frame: SpriteFrame): SpriteFrame {
  if (!frame.url || !revokedFrameUrls.has(frame.url) || !frame.blob) return frame
  revokedFrameUrls.delete(frame.url)
  frameImages.delete(frame.url)
  return { ...frame, url: URL.createObjectURL(frame.blob) }
}
const { canUndo, canRedo, undo, redo, reset: resetHistory } = useSpriteHistory(
  () => currentSprite.value,
  () => {
    // 快照回写后校正依赖选中项：帧下标、动画选中、标记选中
    const sprite = currentSprite.value
    if (!sprite) return
    const maxFrame = Math.max(0, sprite.frames.length - 1)
    selectedFrameIndex.value = Math.min(selectedFrameIndex.value, maxFrame)
    canvasDisplayIndex.value = Math.min(canvasDisplayIndex.value, maxFrame)
    costumeHighlightIndex.value = Math.min(costumeHighlightIndex.value, maxFrame)
    if (selectedAnim.value) {
      const name = selectedAnim.value.name
      selectedAnim.value = sprite.animations.find(a => a.name === name) ?? null
    }
    if (selMarkerName.value && !markerNames.value.includes(selMarkerName.value)) {
      selMarkerName.value = null
    }
    defaultFrameDirty = true
    scheduleSave()
  },
  { restoreFrame: restoreFrameUrl },
)

// 场景视图：缩放和平移（世界坐标系与游戏一致：x 向右、y 向上）
const canvasZoom = ref(1)
const canvasPanX = ref(0)
const canvasPanY = ref(0)
const isPanning = ref(false)
const panStartX = ref(0)
const panStartY = ref(0)
const panStartOffsetX = ref(0)
const panStartOffsetY = ref(0)
const canvasRef = ref<HTMLDivElement | null>(null)
/** 按住空格临时进入平移模式（与地图编辑器一致） */
const spaceHeld = ref(false)
/** 场景视口尺寸（网格对齐、适配视图需要） */
const viewSize = ref({ w: 0, h: 0 })
/** 进入角色时视口还没测量到：等挂载/尺寸就绪后再适配一次 */
const sceneFitPending = ref(false)
let viewResizeObserver: ResizeObserver | null = null

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
      resetHistory()
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

let naturalSizeToken = 0

/**
 * 记录当前角色的自然尺寸与画风（自动渲染模式的判定依据）。
 * 尺寸：.bsf 取画布，其余取首帧图片尺寸；画风：分析首帧像素（同一角色各帧画风一致）。
 */
async function updateSpriteNaturalSize() {
  const token = ++naturalSizeToken
  const sprite = currentSprite.value
  spritePixelArt.value = null
  if (!sprite) return
  const first = sprite.frames[0]
  /** 首帧图像：尺寸与画风共用一次解码 */
  let firstImg: HTMLImageElement | null = null
  if (sprite.bsf) {
    spriteNaturalW.value = sprite.bsf.canvas.w
    spriteNaturalH.value = sprite.bsf.canvas.h
  } else {
    try {
      firstImg = await loadImage(first.blob)
      if (token !== naturalSizeToken) return
      spriteNaturalW.value = firstImg.naturalWidth || firstImg.width
      spriteNaturalH.value = firstImg.naturalHeight || firstImg.height
    } catch {
      spriteNaturalW.value = 0
      spriteNaturalH.value = 0
    }
  }
  // 矢量素材（SVG）按目标像素重绘：最近邻会把栅格化锯齿固化下来，恒平滑
  if (/\.svg$/i.test(currentSpritePath.value)) {
    spritePixelArt.value = false
    return
  }
  if (!first) return
  if (!firstImg) {
    try {
      firstImg = await loadImage(first.blob)
      if (token !== naturalSizeToken) return
    } catch {
      // 分析失败保持 null：自动模式回退到尺寸判定
      return
    }
  }
  spritePixelArt.value = detectPixelArt(firstImg, spriteNaturalW.value, spriteNaturalH.value)
}

async function loadSprite(item: { id: string; name: string; path: string }) {
  // 防重复加载：同一个角色不重新加载（早退也要清掉上一次的载入错误，否则错误横幅会一直残留）
  if (currentSpritePath.value === item.path && currentSprite.value) {
    loadError.value = null
    return
  }
  try {
    // 先把旧角色从视图摘除（模板立即重渲染），等 DOM 换掉后再回收 ObjectURL：
    // 否则旧帧 <img>/canvas 还指向已释放的 blob，会出现瞬态 ERR_FILE_NOT_FOUND 裂图
    const previous = currentSprite.value
    currentSprite.value = null
    frameImages.clear()
    await nextTick()
    revokeSpriteUrls(previous)
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
    cancelMarkerPlacing()
    selMarkerName.value = null
    annoScope.value = 'all'
    // 进入时与右侧面板保持一致：停留在动画面板则不进选择状态（不显示变换手柄）
    const showAnimationPage = rightTab.value === 'animation'
    activeTool.value = showAnimationPage ? 'none' : 'select'
    selectionActive.value = !showAnimationPage
    annoDefaultPivot.value = currentSprite.value.bsf
      ? { ...(currentSprite.value.bsf.pivotBase || currentSprite.value.bsf.pivot) }
      : null
    // 场景视图：等 DOM 渲染后恢复缩放（首次 100%、之后沿用上次），并把角色包围盒中心放到视口中心
    await nextTick()
    if (viewSize.value.w > 0) {
      sceneFitPending.value = false
      applyInitialSceneView()
    } else {
      sceneFitPending.value = true
    }
    if (currentSprite.value.animations.length > 0) {
      const first = currentSprite.value.animations[0]
      selectedAnim.value = first
      fpsValue.value = first.fps || 10
      startAnimation(first)
    }
    // 角色切换 / 重载完成：当前状态作为撤销历史的起点
    resetHistory()
  } catch (e) {
    console.error('Failed to load sprite:', e)
    loadError.value = e instanceof Error ? e.message : String(e)
    resetHistory()
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
  const newZoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, oldZoom * delta))

  // 以鼠标位置为中心缩放: 保持鼠标下的像素点不动
  canvasPanX.value = mouseX - (mouseX - canvasPanX.value) * (newZoom / oldZoom)
  canvasPanY.value = mouseY - (mouseY - canvasPanY.value) * (newZoom / oldZoom)
  canvasZoom.value = newZoom
}

/** 平移：中键、空格 + 左键、Alt + 左键（与地图编辑器一致） */
function shouldStartPan(e: MouseEvent): boolean {
  return e.button === 1 || (e.button === 0 && (spaceHeld.value || e.altKey))
}

// 中键 / 空格 / Alt 按下开始平移
function onCanvasMouseDown(e: MouseEvent) {
  if (shouldStartPan(e)) {
    e.preventDefault()
    e.stopPropagation()
    isPanning.value = true
    panStartX.value = e.clientX
    panStartY.value = e.clientY
    panStartOffsetX.value = canvasPanX.value
    panStartOffsetY.value = canvasPanY.value
    return
  }
  // 标记放置：左键点一下就在鼠标处落点并结束放置（点已有图钉时由图钉手柄拦截，不会误加）
  if (e.button === 0 && markerPlacing.value) {
    e.preventDefault()
    placeMarkerAt(screenToCanvas(e) ?? markerGhost.value)
    return
  }

  // 选择工具：点空白处取消选中（手柄自身 mousedown 已 stop，不会进到这里）；点角色重新选中
  // 动画面板下（activeTool = none）同样允许点选，但只改选中状态，不切换右侧面板
  if (e.button === 0 && (activeTool.value === 'select' || activeTool.value === 'none')) {
    // 没点在图钉上（图钉已 stopPropagation）= 取消标记选中，回到选角色
    selMarkerName.value = null
    const p = screenToCanvas(e)
    const b = displayFrameBounds.value
    selectionActive.value = !!p
      && p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h
  }
}

function onCanvasMouseMove(e: MouseEvent) {
  if (isPanning.value) {
    canvasPanX.value = panStartOffsetX.value + (e.clientX - panStartX.value)
    canvasPanY.value = panStartOffsetY.value + (e.clientY - panStartY.value)
    return
  }
  // 放置中的幽灵图钉跟随鼠标（与地图编辑器一致）
  if (markerPlacing.value) {
    const p = screenToCanvas(e)
    if (p) lastCanvasPoint = p
    updateMarkerGhost(e, p)
  }
}

function onCanvasMouseUp(e: MouseEvent) {
  // 中键 / 空格或 Alt + 左键 都可能发起平移，松开对应键都要结束
  if (e.button === 1 || (e.button === 0 && isPanning.value)) {
    isPanning.value = false
  }
}

function onGlobalMouseUp(e: MouseEvent) {
  if (e.button === 1 || (e.button === 0 && isPanning.value)) {
    isPanning.value = false
  }
}

// ═══ 中心点标注（.bsf 角色 / 单图角色合成单帧 bsf：manifest 带 pivot 元数据） ═══

/** 编辑作用域：all = 改统一值（全部帧生效）；one = 写当前帧覆盖 */
const annoScope = ref<'all' | 'one'>('all')

/** 属性面板「作用范围」下拉：切换编辑作用域 */
function onScopeSelect(value: string) {
  annoScope.value = value === 'one' ? 'one' : 'all'
}
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

/** 素材原始中心点：属性面板显示偏移的 0,0 基准（未移动过就是 0,0） */
const annoPivotBase = computed(() => {
  const bsf = currentSprite.value?.bsf
  return bsf ? (bsf.pivotBase || bsf.pivot) : null
})

/**
 * 中心点相对素材原始位置的偏移（属性面板显示值）。
 * 存储仍用画布绝对坐标 pivot（引擎协议不变），只在界面层换算：
 * 没动过中心点就显示 0,0，避免小学生看到「画布绝对坐标」这类反直觉数字。
 */
const annoPivotOffset = computed(() => {
  const p = annoPivot.value
  const b = annoPivotBase.value
  if (!p || !b) return null
  return { x: p.x - b.x, y: p.y - b.y }
})

// ═══ 场景视图：角色对象几何 / 网格 / 视图适配 ═══

/** 角色中心点（画布坐标）：.bsf 用帧有效中心；旧 .bgs 用内容框中心（与引擎一致） */
const spritePivot = computed<{ x: number; y: number }>(() => {
  if (canAnno.value) {
    const p = effPivot(annoFrameIndex.value)
    if (p) return p
    const c = currentSprite.value?.bsf?.canvas
    return c ? { x: c.w / 2, y: c.h / 2 } : { x: 0, y: 0 }
  }
  const sprite = currentSprite.value
  const frame = sprite?.frames[canvasDisplayIndex.value]
  const measured = nonBsfBox.value
  if (measured && frame && measured.url === frame.url) {
    return { x: measured.box.x + measured.box.w / 2, y: measured.box.y + measured.box.h / 2 }
  }
  return { x: spriteNaturalW.value / 2, y: spriteNaturalH.value / 2 }
})

/** 角色包围盒（画布坐标）：.bsf 用帧实际渲染矩形（不含透明画布留白），旧 .bgs 用内容框 */
const displayFrameBounds = computed(() => {
  if (canAnno.value) {
    const f = currentSprite.value?.bsf?.frames[annoFrameIndex.value]
    if (f) return { x: f.offset.x, y: f.offset.y, w: f.rect.w, h: f.rect.h }
  }
  const sprite = currentSprite.value
  const frame = sprite?.frames[canvasDisplayIndex.value]
  const measured = nonBsfBox.value
  if (measured && frame && measured.url === frame.url) return measured.box
  return {
    x: 0,
    y: 0,
    w: canvasFrameNatural.value?.w ?? spriteNaturalW.value,
    h: canvasFrameNatural.value?.h ?? spriteNaturalH.value,
  }
})

const ZOOM_MIN = 0.1
const ZOOM_MAX = 32
const zoomPercent = computed(() => Math.round(canvasZoom.value * 100))

/** 属性面板「尺寸」：素材尺寸（.bsf 用画布尺寸，图片角色用当前帧内容框），只读展示 */
const spriteSize = computed(() => {
  const c = currentSprite.value?.bsf?.canvas
  if (c) return { w: c.w, h: c.h }
  const b = displayFrameBounds.value
  return { w: Math.round(b.w), h: Math.round(b.h) }
})

/**
 * 拖拽中心点期间的临时锚点：锁定为拖拽开始时的中心点。
 * 逐帧改中心点 + 逐帧补偿变换会让画面在亚像素间反复取整而抖动；
 * 拖拽期间改由固定锚点渲染（画面绝对不动，锚点图标跟手），松手时一次性补偿。
 */
const pivotViewAnchor = ref<{ x: number; y: number } | null>(null)

/**
 * 场景对象锚点（画布坐标）= 角色中心点（pivot），与 Godot 一致：
 * 节点原点就是中心点，图片围绕它摆放/旋转/缩放。
 * 所以中心点在 0,0、变换位置也在 0,0 时，图像一定会以中心点压在坐标原点上。
 */
const objectAnchor = computed<{ x: number; y: number }>(
  () => pivotViewAnchor.value ?? spritePivot.value,
)

/** 世界原点在场景视口中的屏幕位置 */
const originScreen = computed(() => ({
  x: viewSize.value.w / 2 + canvasPanX.value,
  y: viewSize.value.h / 2 + canvasPanY.value,
}))

/**
 * 网格基准格距（世界像素）：100% 缩放下的一格大小，也是「缩小视图」时的固定世界步长。
 * 参考 Godot：缩小画面时网格跟随世界一起变小变密，而不是立刻换成更粗的格子。
 */
const GRID_BASE_STEP = 32
/** 放大方向的最小屏幕间距（px）：格线保持 24~48px，不会越放越密 */
const GRID_MIN_SCREEN_PX = 24
/** 缩小方向的格线最小可见间距（px）：低于它才并入更粗的格子，避免糊成一片 */
const GRID_MIN_VISIBLE_PX = 8

/**
 * 网格步长（世界像素），缩小时与放大时行为不同：
 * - 放大（zoom ≥ 1）：取 1/2/4/8… 中屏幕间距 ≥ 24px 的最小步长（当前效果，格线间距恒定）
 * - 缩小（zoom < 1）：固定 32 世界像素一格，格子随缩放一起变小变密；
 *   只有屏幕间距小于 8px 时才并入更粗的格子，保证还能看清
 */
function gridStepWorld(zoom: number): number {
  if (zoom >= 1) {
    let step = 1
    while (step * zoom < GRID_MIN_SCREEN_PX) step *= 2
    return step
  }
  let step = GRID_BASE_STEP
  while (step * zoom < GRID_MIN_VISIBLE_PX) step *= 2
  return step
}

/** 场景显示开关：网格默认显示；碰撞盒默认不勾选（只查看，不切碰撞工具） */
const showGrid = ref(true)
const showCollisionBox = ref(false)
/** 智能吸附（与地图编辑器 / 绘制页同一套算法）：拖动角色时对齐世界原点轴与网格线 */
const snapEnabled = ref(true)

/**
 * 网格用 canvas 自绘，而不是 CSS background 平铺：
 * 分数格距时 CSS 平铺会在每个 tile 边缘产生“两条几乎重叠的线”（滚轮缩放的瞬间特别明显），
 * 逐条线按设备像素取整绘制可以完全避开这个接缝，线距也更均匀（Godot 的观感）。
 */
const gridCanvasEl = ref<HTMLCanvasElement | null>(null)

function drawSceneGrid() {
  const el = gridCanvasEl.value
  if (!el) return
  const { w, h } = viewSize.value
  if (w <= 0 || h <= 0) return
  const dpr = window.devicePixelRatio || 1
  const pw = Math.max(1, Math.round(w * dpr))
  const ph = Math.max(1, Math.round(h * dpr))
  if (el.width !== pw || el.height !== ph) {
    el.width = pw
    el.height = ph
  }
  const ctx = el.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, pw, ph)
  if (!showGrid.value) return

  const spacing = gridStepWorld(canvasZoom.value) * canvasZoom.value
  if (!Number.isFinite(spacing) || spacing < 1) return
  const ox = originScreen.value.x
  const oy = originScreen.value.y
  // 1 CSS 像素粗的线（高分屏按设备像素放大，保持清晰）
  const lw = Math.max(1, Math.round(dpr))
  const minorCol = 'rgba(255, 255, 255, 0.045)'
  const majorCol = 'rgba(255, 255, 255, 0.09)'

  // 竖线：世界原点出发，每 8 格一条粗线
  const kStartX = Math.floor(-ox / spacing)
  const kEndX = Math.ceil((w - ox) / spacing)
  for (let k = kStartX; k <= kEndX; k++) {
    const x = Math.round((ox + k * spacing) * dpr)
    ctx.fillStyle = Math.abs(k % 8) === 0 ? majorCol : minorCol
    ctx.fillRect(x, 0, lw, ph)
  }
  // 横线
  const kStartY = Math.floor(-oy / spacing)
  const kEndY = Math.ceil((h - oy) / spacing)
  for (let k = kStartY; k <= kEndY; k++) {
    const y = Math.round((oy + k * spacing) * dpr)
    ctx.fillStyle = Math.abs(k % 8) === 0 ? majorCol : minorCol
    ctx.fillRect(0, y, pw, lw)
  }
}

// 缩放 / 平移 / 改尺寸 / 开关网格时实时重绘（canvas 引用就绪时也会自动重跑一次）
watchEffect(drawSceneGrid)

/** 把角色包围盒中心对齐到视口中心（保持给定缩放） */
function centerOnSprite(zoom = canvasZoom.value) {
  const t = sceneTransform.value
  const p = objectAnchor.value
  const b = displayFrameBounds.value
  const scaleFactor = Math.max(5, t.scale) / 100
  const rad = (-t.angle) * Math.PI / 180
  const dx = (b.x + b.w / 2 - p.x) * zoom * scaleFactor
  const dy = (b.y + b.h / 2 - p.y) * zoom * scaleFactor
  const rx = dx * Math.cos(rad) - dy * Math.sin(rad)
  const ry = dx * Math.sin(rad) + dy * Math.cos(rad)
  canvasPanX.value = -t.x * zoom - rx
  canvasPanY.value = t.y * zoom - ry
}

/** 场景缩放记忆：首次进入 100%，之后沿用用户最后一次的缩放 */
const SCENE_ZOOM_KEY = 'bingo-ide-sprite-scene-zoom'
function readSavedSceneZoom(): number | null {
  try {
    const raw = localStorage.getItem(SCENE_ZOOM_KEY)
    if (!raw) return null
    const z = Number(raw)
    return Number.isFinite(z) && z > 0 ? z : null
  } catch {
    return null
  }
}
function saveSceneZoom(z: number) {
  try {
    localStorage.setItem(SCENE_ZOOM_KEY, String(z))
  } catch {
    // localStorage 不可用时忽略（仅影响记忆，不影响编辑）
  }
}

/** 进入角色时恢复视图：首次 100%，之后用上次的缩放；角色始终放到视口中心 */
function applyInitialSceneView() {
  if (!currentSprite.value) return
  const saved = readSavedSceneZoom()
  const z = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, saved ?? 1))
  canvasZoom.value = z
  centerOnSprite(z)
}

/** 重置视图：100% 缩放并把角色放回视口中心 */
function resetCanvas() {
  canvasZoom.value = 1
  centerOnSprite(1)
}

function zoomBy(factor: number) {
  const old = canvasZoom.value
  const next = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, old * factor))
  const ratio = next / old
  // 保持视口中心不动（初始适配已把角色对到中心）
  canvasPanX.value *= ratio
  canvasPanY.value *= ratio
  canvasZoom.value = next
}

/** 确保 transform 字段存在：只有用户真正编辑过才会写进角色数据 */
function ensureTransform(): SpriteTransform | null {
  const sprite = currentSprite.value
  if (!sprite) return null
  if (!sprite.transform) sprite.transform = { ...DEFAULT_SPRITE_TRANSFORM }
  return sprite.transform
}

/** 隐藏测量元素：与数字输入框同一套字体，用 DOM 实测文本宽度（canvas 里字体设置容易失效） */
let unitMeasureEl: HTMLSpanElement | null = null

function ensureUnitMeasureEl(): HTMLSpanElement {
  if (!unitMeasureEl) {
    unitMeasureEl = document.createElement('span')
    // 与 .att-input 保持一致的字体设置；white-space:pre 让空格/小数点按原样占宽
    unitMeasureEl.style.cssText =
      'position:absolute;left:-9999px;top:0;visibility:hidden;white-space:pre;'
      + 'font-size:12px;font-family:inherit;font-variant-numeric:tabular-nums'
    document.body.appendChild(unitMeasureEl)
  }
  return unitMeasureEl
}

/** 文本实际宽度（px）：'1' 比 '0' 窄，按字符数估算会累积偏差，必须实测 */
function textWidthPx(text: string): number {
  const el = ensureUnitMeasureEl()
  el.textContent = text || '0'
  return el.getBoundingClientRect().width
}

onBeforeUnmount(() => unitMeasureEl?.remove())

/**
 * 单位文字定位：紧跟在数字后面，只留 8px 呼吸间距。
 * 用真实测量出的数字宽度定位（而不是按字符数 × ch 估算），
 * 这样无论输入 0 还是 1、正数还是负数，单位都贴住最后一个数字。
 * 数字超长时单位最多移动到输入框边缘就锁住（配合输入框右侧内边距，
 * 数字会先被裁切，因此两者永远不会重叠）。
 * @param text 当前显示/编辑中的数字文本
 * @param startPx 数字起始位置（输入框边框 + 左内边距）
 * @param fieldWidth 整个输入框的实际宽度（0 = 还没测到，先用理想位置）
 * @param unitText 单位文字（px / °），用于预留自身宽度
 */
function unitStyleAfterText(
  text: string,
  startPx: number,
  fieldWidth: number,
  unitText = 'px',
): Record<string, string> {
  const desired = startPx + textWidthPx(text) + 8
  if (!fieldWidth) return { left: `${desired}px` }
  // 单位最远停到输入框右缘（右侧 24px 内边距 + 自身宽度 + 6px 间隔）
  const maxLeft = fieldWidth - 24 - textWidthPx(unitText) - 6
  return { left: `${Math.min(desired, Math.max(startPx, maxLeft))}px` }
}

/** 单位定位依赖输入框实际宽度：跟随面板缩放实时更新
 *  碰撞页的位置 / 旋转输入框与属性页同款，各自取自己的实测宽度 */
const unitFieldWidth = reactive({
  x: 0, y: 0, angle: 0, pivotX: 0, pivotY: 0,
  colPosX: 0, colPosY: 0, colAngle: 0,
})
const xFieldEl = ref<HTMLElement | null>(null)
const yFieldEl = ref<HTMLElement | null>(null)
const angleFieldEl = ref<HTMLElement | null>(null)
const pivotXFieldEl = ref<HTMLElement | null>(null)
const pivotYFieldEl = ref<HTMLElement | null>(null)
const colPosXFieldEl = ref<HTMLElement | null>(null)
const colPosYFieldEl = ref<HTMLElement | null>(null)
const colAngleFieldEl = ref<HTMLElement | null>(null)
let unitResizeObserver: ResizeObserver | null = null

function observeUnitFields() {
  if (typeof ResizeObserver === 'undefined') return
  // 属性页 / 碰撞页同时只有一页挂载，切换页时重新吸附当前这页的输入框
  unitResizeObserver?.disconnect()
  unitResizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      const el = entry.target as HTMLElement
      const width = entry.contentRect.width
      if (el === xFieldEl.value) unitFieldWidth.x = width
      else if (el === yFieldEl.value) unitFieldWidth.y = width
      else if (el === angleFieldEl.value) unitFieldWidth.angle = width
      else if (el === pivotXFieldEl.value) unitFieldWidth.pivotX = width
      else if (el === pivotYFieldEl.value) unitFieldWidth.pivotY = width
      else if (el === colPosXFieldEl.value) unitFieldWidth.colPosX = width
      else if (el === colPosYFieldEl.value) unitFieldWidth.colPosY = width
      else if (el === colAngleFieldEl.value) unitFieldWidth.colAngle = width
    }
  })
  const fields = [
    xFieldEl.value, yFieldEl.value, angleFieldEl.value, pivotXFieldEl.value, pivotYFieldEl.value,
    colPosXFieldEl.value, colPosYFieldEl.value, colAngleFieldEl.value,
  ]
  for (const el of fields) {
    if (el) unitResizeObserver.observe(el)
  }
}

onMounted(() => nextTick(observeUnitFields))
onBeforeUnmount(() => unitResizeObserver?.disconnect())

/**
 * 编辑期间的临时文本：单位位置跟随用户正在输入的内容一起右移，
 * 提交（change/blur）后清空，回到以真实值为准。
 */
const draftText = reactive<Record<string, string | null>>({})

/** 输入位数上限：10 位（负号和小数点不计入），右侧还要留出重置按钮的空间 */
const MAX_INPUT_DIGITS = 10

/**
 * 清理输入文本：只保留数字、开头负号、一个小数点，总位数不超过上限。
 * 输入框用 type="text" 而不是 type="number"：number 输入框在输入 “-” / “12.” 这类
 * 中间状态时 value 会变空，导致单位定位和显示对不上（小数输入时会重叠）。
 */
function sanitizeNumericInput(raw: string): string {
  const negative = raw.trimStart().startsWith('-')
  const body = raw.replace(/[^\d.]/g, '')
  let out = ''
  let digits = 0
  for (const ch of body) {
    if (ch === '.') {
      if (!out.includes('.')) out += ch
      continue
    }
    if (digits >= MAX_INPUT_DIGITS) continue
    out += ch
    digits++
  }
  // 负号单独存在时也保留，否则没法开始输入负数
  return (negative ? '-' : '') + out
}

function onFieldDraft(key: string, e: Event) {
  const el = e.target as HTMLInputElement
  const cleaned = sanitizeNumericInput(el.value)
  // 立即修正输入框内容，避免非法字符先闪一帧再被绑定值覆盖
  if (cleaned !== el.value) el.value = cleaned
  draftText[key] = cleaned
}

function clearDraft(key: string) {
  draftText[key] = null
}

/**
 * 数值显示文本：与输入框里实际渲染的字符完全一致（最多两位小数、去掉多余的 0）。
 * 单位定位必须用同一个字符串测量，否则会出现「显示 0.1、单位按 0 定位」的错位重叠。
 */
function formatFieldText(value: number): string {
  if (!Number.isFinite(value)) return '0'
  return String(Number(value.toFixed(2)))
}

/** 输入框显示值：正在编辑时用用户输入的原文，否则用真实数据（格式化后）。 */
function draftValue(key: string, value: number): string {
  return draftText[key] ?? formatFieldText(value)
}

/** 聚焦即全选当前数值：直接输入就能整体替换 */
function selectOnFocus(e: Event) {
  const el = e.target as HTMLInputElement
  // 鼠标点击会在 focus 之后才把光标落位，延后一帧再全选，避免选择被点击取消
  setTimeout(() => el.select(), 0)
}

/** 位置单位：与输入框显示文本共用同一字符串（编辑中 = 原文，否则 = 格式化值） */
function axisUnitStyleFor(key: 'x' | 'y', value: number): Record<string, string> {
  return unitStyleAfterText(
    draftText[key] ?? formatFieldText(value),
    28,
    unitFieldWidth[key],
    'px',
  )
}

/** 旋转单位：与输入框显示文本共用同一字符串 */
function angleUnitStyle(value: number): Record<string, string> {
  return unitStyleAfterText(
    draftText.angle ?? formatFieldText(value),
    7,
    unitFieldWidth.angle,
    '°',
  )
}

/** 中心点单位：与输入框显示文本共用同一字符串（编辑中 = 原文，否则 = 格式化值） */
function pivotUnitStyle(key: 'px' | 'py', value: number): Record<string, string> {
  return unitStyleAfterText(
    draftText[key] ?? formatFieldText(value),
    28,
    key === 'px' ? unitFieldWidth.pivotX : unitFieldWidth.pivotY,
    'px',
  )
}

/** 缩放 X / Y 的显示值：分轴字段缺省时等于统一缩放 */
const scaleXValue = computed(() => sceneTransform.value.scaleX ?? sceneTransform.value.scale)
const scaleYValue = computed(() => sceneTransform.value.scaleY ?? sceneTransform.value.scale)

/** 约束比例：勾选时 X / Y 联动（默认勾选）；取消后允许分别设置宽高比例
 *  切换到已保存分轴缩放的角色时自动取消勾选，避免显示值被误清 */
const scaleLink = ref(true)
watch(
  () => [sceneTransform.value.scaleX, sceneTransform.value.scaleY],
  ([sx, sy]) => {
    // 有分轴数据 = 之前取消过约束；切换到普通角色时恢复默认勾选
    scaleLink.value = sx === undefined && sy === undefined
  },
  { immediate: true },
)

function onScaleLinkChange(e: Event) {
  scaleLink.value = (e.target as HTMLInputElement).checked
  const t = ensureTransform()
  if (!t) return
  if (scaleLink.value) {
    // 重新锁定：以 X 为基准统一，清掉分轴字段
    t.scale = scaleXValue.value
    delete t.scaleX
    delete t.scaleY
    scheduleSave()
  }
}

/** 缩放输入：约束比例时同时改 X / Y，否则只改当前轴 */
function onScaleInput(axis: 'x' | 'y', e: Event) {
  const raw = Number((e.target as HTMLInputElement).value)
  if (!Number.isFinite(raw)) return
  const t = ensureTransform()
  if (!t) return
  const v = Math.min(1000, Math.max(5, raw))
  if (scaleLink.value) {
    t.scale = v
    delete t.scaleX
    delete t.scaleY
  } else if (axis === 'x') {
    t.scaleX = v
  } else {
    t.scaleY = v
  }
  clearDraft(axis === 'x' ? 'scaleX' : 'scaleY')
  scheduleSave()
}

/** 位置坐标的安全范围：超出这个范围的坐标在 640×480 舞台上毫无意义，防止乱输入把角色丢出画面 */
const MAX_POSITION = 4000
/** 旋转兜底上限：10 圈以内，超长数字输入也不会让角色转到看不出角度 */
const MAX_ANGLE = 3600

/** 写入单个变换字段（拖拽手柄 / 滑条共用；改统一缩放时清掉分轴值） */
function setTransformField(field: keyof SpriteTransform, value: number) {
  if (!Number.isFinite(value)) return
  const t = ensureTransform()
  if (!t) return
  if (field === 'scale') {
    t.scale = Math.min(1000, Math.max(5, value))
    delete t.scaleX
    delete t.scaleY
  } else if (field === 'x' || field === 'y') {
    // 位置超长数字收回到安全范围，避免角色被甩到看不见的地方
    t[field] = Math.max(-MAX_POSITION, Math.min(MAX_POSITION, value))
  } else if (field === 'angle') {
    // 角度同样兜底：微小滑动/超长数字都不会转成无意义的圈数
    t.angle = Math.max(-MAX_ANGLE, Math.min(MAX_ANGLE, value))
  } else t[field] = value
  // 拖拽手柄 / 滑条改值后，输入框里残留的编辑文本作废，显示最新值
  clearDraft(field)
  if (field === 'scale') {
    clearDraft('scaleX')
    clearDraft('scaleY')
  }
  scheduleSave()
}

/** 每个输入框是否已偏离默认值：只有某轴改动过，才在那个输入框内部显示自己的重置图标 */
const xDirty = computed(() => sceneTransform.value.x !== 0)
const yDirty = computed(() => sceneTransform.value.y !== 0)
const scaleXDirty = computed(() => scaleXValue.value !== 100)
const scaleYDirty = computed(() => scaleYValue.value !== 100)
const rotationDirty = computed(() => sceneTransform.value.angle !== 0)

/** 重置单个输入框：X / Y / 角度回 0，缩放轴回 100%；全部回默认值时不再保留 transform 字段 */
function resetTransformAxis(field: 'x' | 'y' | 'angle' | 'scaleX' | 'scaleY') {
  const t = ensureTransform()
  if (!t) return
  if (field === 'scaleX' || field === 'scaleY') {
    // 勾选「约束比例」时 X / Y 联动：点任意一个重置按钮都把两轴一起还原
    if (scaleLink.value) {
      t.scale = 100
      delete t.scaleX
      delete t.scaleY
      clearDraft('scaleX')
      clearDraft('scaleY')
    } else {
      t[field] = 100
      clearDraft(field)
    }
  } else {
    t[field] = 0
    clearDraft(field)
  }
  // 分轴值与统一缩放相同时不留冗余字段
  if (t.scaleX !== undefined && t.scaleX === t.scale) delete t.scaleX
  if (t.scaleY !== undefined && t.scaleY === t.scale) delete t.scaleY
  const allDefault = t.x === 0 && t.y === 0 && t.angle === 0
    && t.scale === 100 && t.scaleX === undefined && t.scaleY === undefined
  if (allDefault) {
    const sprite = currentSprite.value
    if (sprite) sprite.transform = undefined
  }
  scheduleSave()
}

function onTransformInput(field: keyof SpriteTransform, e: Event) {
  const v = Number((e.target as HTMLInputElement).value)
  if (!Number.isFinite(v)) return
  setTransformField(field, v)
  clearDraft(field)
}

/** 中心点各轴是否偏离素材原始位置：改动过才在对应输入框内显示重置图标 */
const pivotXDirty = computed(() => (annoPivotOffset.value?.x ?? 0) !== 0)
const pivotYDirty = computed(() => (annoPivotOffset.value?.y ?? 0) !== 0)

/** 重置单轴中心点：回到素材原始位置（该轴偏移 = 0） */
function resetPivotAxis(axis: 'x' | 'y') {
  const cur = annoPivot.value
  const base = annoPivotBase.value
  if (!cur || !base) return
  setPivot(axis === 'x' ? { x: base.x, y: cur.y } : { x: cur.x, y: base.y })
}

// ═══ 变换手柄（「选择」工具）：移动 / 等比缩放 / 旋转 ═══

type GizmoCorner = 'tl' | 'tr' | 'br' | 'bl'
type GizmoDrag = {
  kind: 'move' | 'scale' | 'rotate'
  startClientX: number
  startClientY: number
  start: SpriteTransform
  pivotClientX: number
  pivotClientY: number
  startDistance: number
  startPointerAngle: number
}

const gizmoDrag = ref<GizmoDrag | null>(null)

/** 选择工具的选中状态：点空白取消（手柄隐藏），点角色或切回「选择」恢复 */
const selectionActive = ref(true)

const gizmoVisible = computed(
  () =>
    (activeTool.value === 'select' || activeTool.value === 'none') &&
    selectionActive.value &&
    !!currentSprite.value,
)

const sceneGizmoLayerStyle = computed(() => ({
  transform: `translate(${canvasPanX.value}px, ${canvasPanY.value}px)`,
}))

/** 手柄根节点：世界坐标 (t.x, t.y) 映射到视口（y 向上取负） */
const gizmoRootStyle = computed(() => {
  const t = sceneTransform.value
  const z = canvasZoom.value
  return { left: `${t.x * z}px`, top: `${-t.y * z}px` }
})

const gizmoRotatorStyle = computed(() => ({
  transform: `rotate(${-sceneTransform.value.angle}deg)`,
}))

/**
 * 中心锚点图标位置：真实中心点相对包围盒中心的偏移（屏幕像素）。
 * 之前图标固定画在包围盒中心，点「脚底」等预设改了中心点却看不出变化；
 * 现在图标跟随 pivot，预设与拖动都能直接看到锚点移动。
 */
const gizmoAnchorIconStyle = computed(() => {
  const p = spritePivot.value
  const a = objectAnchor.value
  if (!p || !a) return {}
  const dzx = displayZoomX.value
  const dzy = displayZoomY.value
  return {
    left: `${(p.x - a.x) * dzx - 9}px`,
    top: `${(p.y - a.y) * dzy - 9}px`,
  }
})

/** 选择框相对场景锚点（包围盒中心）的偏移与尺寸（显示倍率 = 场景缩放 × 角色缩放，分轴） */
const gizmoFrameStyle = computed(() => {
  const p = objectAnchor.value
  const b = displayFrameBounds.value
  const dzx = displayZoomX.value
  const dzy = displayZoomY.value
  return {
    left: `${(b.x - p.x) * dzx}px`,
    top: `${(b.y - p.y) * dzy}px`,
    width: `${Math.max(1, b.w * dzx)}px`,
    height: `${Math.max(1, b.h * dzy)}px`,
  }
})

const gizmoArmStyle = computed(() => {
  const p = objectAnchor.value
  const b = displayFrameBounds.value
  const dzx = displayZoomX.value
  const dzy = displayZoomY.value
  return {
    left: `${(b.x + b.w / 2 - p.x) * dzx}px`,
    top: `${(b.y - p.y) * dzy - 22}px`,
  }
})

const gizmoKnobStyle = computed(() => {
  const p = objectAnchor.value
  const b = displayFrameBounds.value
  const dzx = displayZoomX.value
  const dzy = displayZoomY.value
  return {
    left: `${(b.x + b.w / 2 - p.x) * dzx}px`,
    top: `${(b.y - p.y) * dzy - 30}px`,
  }
})

/** 四角缩放手柄：反向旋转保持屏幕轴对齐 */
function gizmoHandleStyle(corner: GizmoCorner) {
  const pos: Record<GizmoCorner, [number, number]> = {
    tl: [0, 0], tr: [100, 0], br: [100, 100], bl: [0, 100],
  }
  return {
    left: `${pos[corner][0]}%`,
    top: `${pos[corner][1]}%`,
    transform: `translate(-50%, -50%) rotate(${sceneTransform.value.angle}deg)`,
  }
}

/** 中心点位移补偿到变换位置：dx/dy 为画布坐标增量，让图像画面保持不动 */
function compensatePivotDelta(dx: number, dy: number) {
  if (!dx && !dy) return
  const t = ensureTransform()
  if (!t) return
  const sx = (t.scaleX ?? t.scale) / 100
  const sy = (t.scaleY ?? t.scale) / 100
  t.x += dx * sx
  t.y -= dy * sy
  clearDraft('x')
  clearDraft('y')
}

function setPivot(p: { x: number; y: number }, compensate = true) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  // 改动前的有效中心点：用于补偿变换位置，让角色画面保持不动（只移动锚点）
  const oldP = annoPivot.value ? { ...annoPivot.value } : null
  if (annoScope.value === 'all') {
    bsf.pivot = { x: p.x, y: p.y }
  } else {
    const f = bsf.frames[annoFrameIndex.value]
    if (f) f.pivot = { x: p.x, y: p.y }
  }
  // 场景以中心点为原点：中心点一动图像就会跟着飘。
  // 这里反向补偿变换位置（世界坐标），使拖拽中心点/应用预设时角色停在原地。
  // 拖拽过程中锚点被 pivotViewAnchor 锁住，逐帧补偿会在亚像素间反复取整产生抖动，
  // 所以拖拽时跳过、松手时一次性补偿。
  if (compensate && oldP && (oldP.x !== p.x || oldP.y !== p.y)) {
    compensatePivotDelta(p.x - oldP.x, p.y - oldP.y)
  }
  // 拖拽手柄 / 预设会绕过输入框：清掉残留的编辑文本，避免输入框显示旧数字
  clearDraft('px')
  clearDraft('py')
  scheduleSave()
}

function clearPivotOverride() {
  const f = currentSprite.value?.bsf?.frames[annoFrameIndex.value]
  if (!f) return
  delete f.pivot
  scheduleSave()
}

// ═══ 碰撞标注（.bsf / 单图角色；无自定义 = 引擎自动碰撞，学生默认路径） ═══

/** 当前激活的标注图层：中心 / 碰撞（单选，同一套画布框架；none = 只显示动画面板） */
const activeTool = ref<'none' | 'select' | 'pivot' | 'collision'>('select')

/** 右侧面板标签页：动画（预览 + 片段）/ 碰撞（点击工具条「碰撞」进入）/ 属性（角色检视器，选中标记时整页切为标记管理） */
const RIGHT_TAB_KEY = 'bingo-ide-sprite-right-tab'
function readSavedRightTab(): 'animation' | 'props' {
  try {
    return localStorage.getItem(RIGHT_TAB_KEY) === 'props' ? 'props' : 'animation'
  } catch {
    return 'animation' // 首次进入默认「动画」页
  }
}
const rightTab = ref<'animation' | 'collision' | 'props'>(readSavedRightTab())

/** 第一个标签随当前工具变化：碰撞工具显示「碰撞」，其余显示「动画」 */
const rightContextTab = computed<'animation' | 'collision'>(() =>
  activeTool.value === 'collision' ? 'collision' : 'animation',
)

/** 工具条切换工具：碰撞工具进「碰撞」页，其余进「属性」页 */
function pickTool(tool: 'select' | 'pivot' | 'collision') {
  cancelMarkerPlacing()
  selMarkerName.value = null
  activateCanvasTool(tool)
  rightTab.value = tool === 'collision' ? 'collision' : 'props'
}

/** 工具条「动画」：只切右侧面板到「动画」页，并退出「选择」工具的选中高亮 */
function pickAnimation() {
  cancelMarkerPlacing()
  selMarkerName.value = null
  rightTab.value = 'animation'
  activeTool.value = 'none'
  selectionActive.value = false
}

/** 属性面板分区折叠状态：与地图编辑器检视器一致的可折叠分区，默认全部展开 */
const propFold = ref({
  basic: true,
  transform: true,
  pivot: true,
  collision: true,
  // 标记页的三个分区
  markerInfo: true,
  markerDisplay: true,
  markerList: true,
})

/** 属性面板下拉选项：与地图编辑器属性面板共用 CustomSelect，选项统一在脚本里定义 */
const SCOPE_OPTIONS = [
  { label: '全部帧', value: 'all' },
  { label: '仅当前帧', value: 'one' },
]

const ROTATION_MODE_OPTIONS = [
  { label: '任意旋转', value: 'all' },
  { label: '左右翻转', value: 'left_right' },
  { label: '不可旋转', value: 'none' },
]

/** 翻转模式下拉的当前值（与 set_rotation_mode() 的三种模式一一对应） */
const rotationModeValue = computed(() => currentSprite.value?.bsf?.rotationMode ?? 'all')

function onRotationModeSelect(v: string) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  if (v === 'left_right' || v === 'none') bsf.rotationMode = v
  else delete bsf.rotationMode
  scheduleSave()
}

const COLLISION_TYPE_OPTIONS = [
  { label: '自动（内容包围盒）', value: 'auto' },
  { label: '矩形', value: 'rect' },
  { label: '胶囊', value: 'capsule' },
  { label: '自定义多边形', value: 'polygon' },
]

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

/** 自动：删除自定义碰撞（统一值 + 全部帧覆盖），回引擎内容包围盒默认 */
function resetCollisionToAuto() {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  delete bsf.collision
  for (const f of bsf.frames) delete f.collision
  scheduleSave()
}

/** 属性面板「碰撞类型」下拉的当前值：null（自动碰撞）显示为 auto */
const collisionTypeValue = computed(() => effCol.value?.type ?? 'auto')

/** 属性面板「碰撞类型」切换：自动 = 清空自定义碰撞，其余按类型转换 */
function onCollisionTypeSelect(value: string) {
  if (value === 'auto') resetCollisionToAuto()
  else convertCollisionType(value as 'rect' | 'capsule' | 'polygon')
}

/** 禁用碰撞：整角色不参与地形/边界物理阻挡（碰撞形状保留，重新勾选即恢复） */
const collisionDisabled = computed(() => !!currentSprite.value?.bsf?.collisionDisabled)

/** 碰撞页分区折叠状态（独立于属性页） */
const colFold = ref({ basic: true, transform: true })

/** 作用：与地图图块/形状同一套语义（碰撞 / 感应 / 碰撞 + 感应） */
const COLLISION_KIND_OPTIONS = [
  { label: '碰撞', value: 'solid' },
  { label: '感应', value: 'sensor' },
  { label: '碰撞 + 感应', value: 'both' },
]

const collisionKindValue = computed(() => currentSprite.value?.bsf?.collisionKind ?? 'solid')

/** 感应角色 / 已禁用碰撞的角色没有物理阻挡：单向碰撞控件保留但禁用（对齐地图属性面板） */
const collisionPhysicsDisabled = computed(
  () => collisionKindValue.value === 'sensor' || collisionDisabled.value,
)

function onCollisionKindSelect(v: string) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  if (v === 'solid') delete bsf.collisionKind
  else bsf.collisionKind = v as 'sensor' | 'both'
  scheduleSave()
}

function onCollisionDisabledChange(e: Event) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  if ((e.target as HTMLInputElement).checked) bsf.collisionDisabled = true
  else delete bsf.collisionDisabled
  scheduleSave()
}

/** 类型（tag）：代码里 is_touch("标签") 查询用；下拉预设 + 自定义（与地图属性面板同款交互） */
const SPRITE_TAG_CUSTOM = '自定义'
const spriteTagCustomMode = ref(false)
watch(currentSprite, () => {
  spriteTagCustomMode.value = false
})

const collisionTagValue = computed(() =>
  spriteTagCustomMode.value
    ? SPRITE_TAG_CUSTOM
    : (currentSprite.value?.bsf?.collisionTag || '').trim() || SPRITE_DEFAULT_COLLISION_TAG,
)

const collisionTagOptions = computed(() => {
  const current = (currentSprite.value?.bsf?.collisionTag || '').trim()
  // 旧角色用过的自定义标签也要能在下拉里选到
  const extra = current && !SPRITE_COLLISION_TAG_PRESETS.includes(current) ? [current] : []
  return [
    ...SPRITE_COLLISION_TAG_PRESETS.map(tag => ({ label: tag, value: tag })),
    ...extra.map(tag => ({ label: tag, value: tag })),
    { label: '自定义…', value: SPRITE_TAG_CUSTOM },
  ]
})

function onCollisionTagSelect(v: string) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  if (v === SPRITE_TAG_CUSTOM) {
    spriteTagCustomMode.value = true
    bsf.collisionTag = ''
  } else {
    spriteTagCustomMode.value = false
    // 「身体」是默认值，不写字段
    if (v && v !== SPRITE_DEFAULT_COLLISION_TAG) bsf.collisionTag = v
    else delete bsf.collisionTag
  }
  scheduleSave()
}

const collisionTagDraft = computed(() => currentSprite.value?.bsf?.collisionTag || '')

/** 自定义标签输入：输入过程中原样写入（避免中文输入法组字被打断） */
function onCollisionTagInput(e: Event) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  bsf.collisionTag = (e.target as HTMLInputElement).value
  scheduleSave()
}

function onCollisionTagBlur(e: Event) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  const name = (e.target as HTMLInputElement).value.trim()
  if (name && name !== SPRITE_DEFAULT_COLLISION_TAG) bsf.collisionTag = name
  else {
    delete bsf.collisionTag
    spriteTagCustomMode.value = false
  }
  scheduleSave()
}

/** 单向碰撞：该角色可当单向碰撞体（把「方向」那一侧当作实心面） */
const collisionOneWay = computed(() => !!currentSprite.value?.bsf?.collisionOneWay)

function onCollisionOneWayChange(e: Event) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  if ((e.target as HTMLInputElement).checked) bsf.collisionOneWay = true
  else {
    delete bsf.collisionOneWay
    delete bsf.collisionOneWayDirX
    delete bsf.collisionOneWayDirY
    delete bsf.collisionOneWayMargin
  }
  scheduleSave()
}

/** 单向碰撞方向：与地图属性面板同一份选项；缺省 (0,1) 从上方踩住 */
const collisionOneWayDirValue = computed(() => {
  const bsf = currentSprite.value?.bsf
  const dx = bsf?.collisionOneWayDirX ?? 0
  const dy = bsf?.collisionOneWayDirY ?? 1
  if (Math.abs(dx) > Math.abs(dy)) return dx > 0 ? '1,0' : '-1,0'
  return dy < 0 ? '0,-1' : '0,1'
})

const collisionOneWayMargin = computed(() => currentSprite.value?.bsf?.collisionOneWayMargin ?? 0)

function onCollisionOneWayDirChange(v: string) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  const [dx, dy] = v.split(',').map(Number)
  if (dx === 0 && dy === 1) {
    delete bsf.collisionOneWayDirX
    delete bsf.collisionOneWayDirY
  } else {
    bsf.collisionOneWayDirX = dx
    bsf.collisionOneWayDirY = dy
  }
  scheduleSave()
}

function onCollisionOneWayMarginInput(e: Event) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  const raw = Number((e.target as HTMLInputElement).value)
  const margin = Number.isFinite(raw) ? Math.min(8, Math.max(0, raw)) : 0
  if (margin > 0) bsf.collisionOneWayMargin = margin
  else delete bsf.collisionOneWayMargin
  scheduleSave()
}

const physicsMaterialOptions = PHYSICS_MATERIAL_OPTIONS

/** 碰撞层级：现阶段只保存到 .bsf，运行时暂未接入（和地图图块/形状面板同一套交互） */
const collisionLayersEnabled = computed(() => !!currentSprite.value?.bsf?.collisionLayersEnabled)
/** 所在碰撞层 1~8，缺省 1 */
const collisionLayer = computed(() => currentSprite.value?.bsf?.collisionLayer ?? 1)
/** 可碰撞掩码层号数组，缺省 [1] */
const collisionMask = computed<number[]>(() => currentSprite.value?.bsf?.collisionMask ?? [1])

function onCollisionLayersChange(e: Event) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  if ((e.target as HTMLInputElement).checked) bsf.collisionLayersEnabled = true
  else {
    delete bsf.collisionLayersEnabled
    delete bsf.collisionLayer
    delete bsf.collisionMask
  }
  scheduleSave()
}

function onCollisionLayerSelect(n: number) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  // 1 是默认层，不写冗余字段
  if (n === 1) delete bsf.collisionLayer
  else bsf.collisionLayer = n
  scheduleSave()
}

function toggleCollisionMask(n: number) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  const next = new Set<number>(bsf.collisionMask ?? [1])
  if (next.has(n)) next.delete(n)
  else next.add(n)
  bsf.collisionMask = Array.from(next).sort((a, b) => a - b)
  scheduleSave()
}

/** 碰撞形状旋转：现阶段只保存到 .bsf，运行时暂未接入 */
const collisionAngleValue = computed(() => currentSprite.value?.bsf?.collisionAngle ?? 0)

function onCollisionAngleInput(e: Event) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  let n = Number((e.target as HTMLInputElement).value)
  if (!Number.isFinite(n)) n = 0
  n = Math.max(-180, Math.min(180, Math.round(n)))
  if (n === 0) delete bsf.collisionAngle
  else bsf.collisionAngle = n
  clearDraft('colAngle')
  scheduleSave()
}

/** 单位标签定位：与属性页同款按数字宽度计算（位置 px / 旋转 °） */
function collisionUnitStyleFor(axis: 'x' | 'y', value: number): Record<string, string> {
  return unitStyleAfterText(
    draftText[axis === 'x' ? 'colPosX' : 'colPosY'] ?? formatFieldText(value),
    28,
    axis === 'x' ? unitFieldWidth.colPosX : unitFieldWidth.colPosY,
    'px',
  )
}

function collisionAngleUnitStyle(): Record<string, string> {
  return unitStyleAfterText(
    draftText.colAngle ?? formatFieldText(collisionAngleValue.value),
    7,
    unitFieldWidth.colAngle,
    '°',
  )
}

/** 碰撞变换各轴是否偏离默认值：偏离时才显示输入框内的重置图标 */
const collisionPosXDirty = computed(() => collisionPosX.value !== 0)
const collisionPosYDirty = computed(() => collisionPosY.value !== 0)
const collisionScaleXDirty = computed(() => collisionScaleX.value !== 100)
const collisionScaleYDirty = computed(() => collisionScaleY.value !== 100)
const collisionAngleDirty = computed(() => collisionAngleValue.value !== 0)

/** 重置单个碰撞轴：位置回 0、缩放回 100%、旋转回 0° */
function resetCollisionAxis(field: 'posX' | 'posY' | 'scaleX' | 'scaleY' | 'angle') {
  if (field === 'angle') {
    const bsf = currentSprite.value?.bsf
    if (!bsf) return
    delete bsf.collisionAngle
    clearDraft('colAngle')
    scheduleSave()
    return
  }
  // 自动碰撞态这些值本来就是默认值，无需转成自定义形状
  const shape = effCol.value
  if (!shape) return
  if (field === 'posX' || field === 'posY') {
    const base = collisionBase.value
    if (!base) return
    const cur = collisionShapeBounds(shape)
    const dx = field === 'posX' ? base.cx - cur.cx : 0
    const dy = field === 'posY' ? base.cy - cur.cy : 0
    setCollision(translateCollisionShape(shape, dx, dy))
    clearDraft(field === 'posX' ? 'colPosX' : 'colPosY')
    return
  }
  let fx = 1
  let fy = 1
  if (collisionScaleLocked.value) {
    // 约束比例时两轴一起回到 100%
    fx = 100 / Math.max(1, collisionScaleX.value)
    fy = 100 / Math.max(1, collisionScaleY.value)
    clearDraft('colScaleX')
    clearDraft('colScaleY')
  } else if (field === 'scaleX') {
    fx = 100 / Math.max(1, collisionScaleX.value)
    clearDraft('colScaleX')
  } else {
    fy = 100 / Math.max(1, collisionScaleY.value)
    clearDraft('colScaleY')
  }
  setCollision(scaleCollisionShape(shape, fx, fy))
}

/** 碰撞面板位置 / 缩放的基准：当前帧内容框（自动碰撞实际使用的框） */
const collisionBase = computed(() => {
  const f = currentSprite.value?.bsf?.frames[annoFrameIndex.value]
  if (!f) return null
  return {
    cx: f.offset.x + f.rect.w / 2,
    cy: f.offset.y + f.rect.h / 2,
    w: Math.max(1, f.rect.w),
    h: Math.max(1, f.rect.h),
  }
})

/** 碰撞形状的包围盒（polygon 取点集 AABB；胶囊取外接矩形） */
function collisionShapeBounds(shape: SpriteCollisionShape) {
  if (shape.type === 'rect') {
    return { cx: shape.cx, cy: shape.cy, w: Math.max(1, shape.w), h: Math.max(1, shape.h) }
  }
  if (shape.type === 'capsule') {
    return { cx: shape.cx, cy: shape.cy, w: Math.max(1, shape.radius * 2), h: Math.max(1, shape.height) }
  }
  const xs = shape.points.map(pt => pt[0])
  const ys = shape.points.map(pt => pt[1])
  if (xs.length === 0) return { cx: 0, cy: 0, w: 1, h: 1 }
  const x0 = Math.min(...xs)
  const x1 = Math.max(...xs)
  const y0 = Math.min(...ys)
  const y1 = Math.max(...ys)
  return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, w: Math.max(1, x1 - x0), h: Math.max(1, y1 - y0) }
}

const collisionBoundsBox = computed(() => collisionShapeBounds(collisionDisplay.value))

const collisionPosX = computed(() => {
  const base = collisionBase.value
  return base ? Math.round((collisionBoundsBox.value.cx - base.cx) * 10) / 10 : 0
})

const collisionPosY = computed(() => {
  const base = collisionBase.value
  // 画布坐标 y 向下，面板按「向上为正」显示（与场景变换一行保持同一习惯）
  return base ? Math.round((base.cy - collisionBoundsBox.value.cy) * 10) / 10 : 0
})

const collisionScaleX = computed(() => {
  const base = collisionBase.value
  return base ? Math.round((collisionBoundsBox.value.w / base.w) * 100) : 100
})

const collisionScaleY = computed(() => {
  const base = collisionBase.value
  return base ? Math.round((collisionBoundsBox.value.h / base.h) * 100) : 100
})

/** 约束比例：改一轴时另一轴同步（与截图默认勾选一致） */
const collisionScaleLocked = ref(true)

function onCollisionScaleLockChange(e: Event) {
  collisionScaleLocked.value = (e.target as HTMLInputElement).checked
}

/** 自动态下改位置 / 缩放：以内容框为初值转成自定义形状（与画布拖手柄的转正逻辑一致） */
function ensureCustomCollision(): SpriteCollisionShape | null {
  if (!canAnno.value) return null
  const existing = effCol.value
  if (existing) return existing
  const shape = frameContentCollision()
  setCollision(shape)
  return shape
}

function translateCollisionShape(shape: SpriteCollisionShape, dx: number, dy: number): SpriteCollisionShape {
  if (shape.type === 'polygon') {
    return {
      type: 'polygon',
      points: shape.points.map(([x, y]) => [x + dx, y + dy] as [number, number]),
    }
  }
  return { ...shape, cx: shape.cx + dx, cy: shape.cy + dy }
}

function scaleCollisionShape(shape: SpriteCollisionShape, fx: number, fy: number): SpriteCollisionShape {
  if (shape.type === 'rect') {
    return { ...shape, w: Math.max(1, shape.w * fx), h: Math.max(1, shape.h * fy) }
  }
  if (shape.type === 'capsule') {
    return {
      ...shape,
      radius: Math.max(1, shape.radius * ((fx + fy) / 2)),
      height: Math.max(2, shape.height * fy),
    }
  }
  const b = collisionShapeBounds(shape)
  return {
    type: 'polygon',
    points: shape.points.map(([x, y]) => [b.cx + (x - b.cx) * fx, b.cy + (y - b.cy) * fy] as [number, number]),
  }
}

/** 位置输入：值 = 相对自动碰撞框中心的偏移（px，向右 / 向上为正） */
function onCollisionPosChange(axis: 0 | 1, e: Event) {
  const base = collisionBase.value
  const shape = ensureCustomCollision()
  if (!base || !shape) return
  const n = Number((e.target as HTMLInputElement).value)
  if (!Number.isFinite(n)) return
  const v = Math.min(MAX_POSITION, Math.max(-MAX_POSITION, n))
  const cur = collisionShapeBounds(shape)
  const dx = axis === 0 ? v - (cur.cx - base.cx) : 0
  // 面板 Y 向上为正，画布坐标 y 向下 → 取反
  const dy = axis === 1 ? (base.cy - v) - cur.cy : 0
  setCollision(translateCollisionShape(shape, dx, dy))
  clearDraft(axis === 0 ? 'colPosX' : 'colPosY')
}

/** 缩放输入：值 = 相对自动碰撞框的百分比（100 = 原尺寸） */
function onCollisionScaleChange(axis: 0 | 1, e: Event) {
  const shape = ensureCustomCollision()
  if (!shape) return
  const n = Number((e.target as HTMLInputElement).value)
  if (!Number.isFinite(n) || n <= 0) return
  const v = Math.min(1000, Math.max(1, n))
  const curPct = axis === 0 ? collisionScaleX.value : collisionScaleY.value
  const factor = v / Math.max(1, curPct)
  let fx = 1
  let fy = 1
  if (axis === 0) {
    fx = factor
    if (collisionScaleLocked.value) fy = factor
  } else {
    fy = factor
    if (collisionScaleLocked.value) fx = factor
  }
  setCollision(scaleCollisionShape(shape, fx, fy))
  if (collisionScaleLocked.value) {
    clearDraft('colScaleX')
    clearDraft('colScaleY')
  } else {
    clearDraft(axis === 0 ? 'colScaleX' : 'colScaleY')
  }
}

/** 受重力影响：缺省受重力（勾选）；不勾选 = 重力地图里也不下坠，撞墙/落地照常 */
const gravityEnabled = computed(() => currentSprite.value?.bsf?.gravity !== false)

function onGravityChange(e: Event) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  const checked = (e.target as HTMLInputElement).checked
  if (checked) {
    delete bsf.gravity
  } else {
    bsf.gravity = false
  }
  scheduleSave()
}

/** Y 轴排序：勾选后同层内按脚底 Y 坐标排序（越靠下越靠前） */
const spriteYSort = computed(() => !!currentSprite.value?.bsf?.ySort)

function onYSortChange(e: Event) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  const checked = (e.target as HTMLInputElement).checked
  if (checked) bsf.ySort = true
  else delete bsf.ySort
  scheduleSave()
}

/** 初始隐藏：勾选后角色创建时不可见（代码里 show() 后出现），适合先摆好位置隐藏的角色 */
const spriteHidden = computed(() => !!currentSprite.value?.bsf?.hidden)

/** 默认图层：数字越大越靠前；同一层按创建顺序（后创建的在上面） */
const spriteLayer = computed(() => currentSprite.value?.bsf?.layer ?? 0)

function onLayerChange(e: Event) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  const raw = Math.round(Number((e.target as HTMLInputElement).value))
  const n = Number.isFinite(raw) ? Math.max(-100, Math.min(100, raw)) : 0
  if (n === 0) delete bsf.layer
  else bsf.layer = n
  scheduleSave()
}

function onHiddenChange(e: Event) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  if ((e.target as HTMLInputElement).checked) bsf.hidden = true
  else delete bsf.hidden
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

function activateCanvasTool(layer: 'select' | 'pivot' | 'collision') {
  activeTool.value = layer
  // 切回「选择」= 重新选中角色（把变换手柄显示出来）
  if (layer === 'select') selectionActive.value = true
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

/** 标记名称输入草稿（输入框用本地状态 v-model，失焦 / 回车才提交，避免每敲一个字就写盘） */
const markerNameDraft = ref('')
watch(
  selMarkerName,
  (name) => {
    markerNameDraft.value = name ?? ''
  },
  { immediate: true },
)

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

/** 画布上要显示的标记名（「显示与锁定」里关掉显示的标记只留在管理列表里） */
const visibleMarkerNames = computed(() => markerNames.value.filter(n => markerFlag(n, 'visible')))

/** 标记展示 / 锁定设置（只读统一值；缺省：显示、名称、坐标都开，不锁定） */
function markerFlag(name: string | null, key: 'visible' | 'showLabel' | 'showCoords' | 'locked'): boolean {
  if (!name) return false
  const m = currentSprite.value?.bsf?.markers?.[name]
  return m?.[key] ?? (key !== 'locked')
}

function setMarkerFlag(
  name: string | null,
  key: 'visible' | 'showLabel' | 'showCoords' | 'locked',
  value: boolean,
) {
  const bsf = currentSprite.value?.bsf
  if (!bsf || !name) return
  const p = effMarker(name, annoFrameIndex.value)
  if (!p) return
  if (!bsf.markers) bsf.markers = {}
  // 只存在帧覆盖的名字没有统一值：补一条承载展示设置
  if (!bsf.markers[name]) bsf.markers[name] = { x: p.x, y: p.y }
  bsf.markers[name][key] = value
  scheduleSave()
}

/** 「显示与锁定」勾选（作用于当前选中的标记） */
function onMarkerFlagChange(
  key: 'visible' | 'showLabel' | 'showCoords' | 'locked',
  e: Event,
) {
  setMarkerFlag(selMarkerName.value, key, (e.target as HTMLInputElement).checked)
}

/** 角色标记常用类型（兼作常用挂点名：选了就把还是默认名的标记顺手改名） */
const MARKER_TYPE_PRESETS = ['右手', '左手', '头部', '背部', '脚底', '发射点', '特效点']
const markerTypeSelectOptions = [
  { value: '未分类', label: '未分类' },
  ...MARKER_TYPE_PRESETS.map(t => ({ value: t, label: t })),
  { value: '__custom__', label: '自定义…' },
]
const markerTypeEditing = ref(false)
const markerTypeDraft = ref('')
const markerTypeInputEl = ref<HTMLInputElement | null>(null)
const markerTypeFilter = ref('all')

const selMarkerRawType = computed(() => {
  const n = selMarkerName.value
  return n ? (currentSprite.value?.bsf?.markers?.[n]?.type ?? '') : ''
})
const selMarkerType = computed(() =>
  markerTypeEditing.value ? '__custom__' : selMarkerRawType.value || '未分类',
)
watch(selMarkerName, () => {
  markerTypeEditing.value = false
  markerTypeDraft.value = selMarkerRawType.value
}, { immediate: true })

/** 写入标记类型（存统一值；只有帧覆盖的名字会补一条统一值承载类型） */
function setMarkerType(value: string) {
  const bsf = currentSprite.value?.bsf
  const name = selMarkerName.value
  if (!bsf || !name) return
  const p = effMarker(name, annoFrameIndex.value)
  if (!p) return
  if (!bsf.markers) bsf.markers = {}
  if (!bsf.markers[name]) bsf.markers[name] = { x: p.x, y: p.y }
  bsf.markers[name].type = value || undefined
  // 选了常用类型、名字还是自动生成的「标记 / 标记N」→ 顺手改成常用名（重名则加序号）
  if (value && MARKER_TYPE_PRESETS.includes(value) && /^标记\d*$/.test(name)) {
    let target = value
    let i = 2
    while (markerNames.value.includes(target)) {
      target = `${value}${i}`
      i++
    }
    renameMarker(name, target)
    return
  }
  scheduleSave()
}

/** 类型下拉：预设 / 未分类直接写入，自定义则展开输入框 */
function onMarkerTypeSelect(value: string) {
  if (value === '__custom__') {
    markerTypeEditing.value = true
    markerTypeDraft.value = MARKER_TYPE_PRESETS.includes(selMarkerRawType.value) ? '' : selMarkerRawType.value
    nextTick(() => {
      markerTypeInputEl.value?.focus()
      markerTypeInputEl.value?.select()
    })
    return
  }
  markerTypeEditing.value = false
  setMarkerType(value === '未分类' ? '' : value)
}

/** 提交自定义类型（失焦 / 回车） */
function commitMarkerTypeDraft() {
  setMarkerType(markerTypeDraft.value.trim())
  markerTypeEditing.value = false
}

/** 标记管理列表的类型筛选项：全部 + 未分类 + 常用类型 + 已有的自定义类型 */
const markerTypeFilterOptions = computed(() => {
  const bsf = currentSprite.value?.bsf
  const extra = new Set<string>()
  for (const n of markerNames.value) {
    const t = bsf?.markers?.[n]?.type
    if (t && !MARKER_TYPE_PRESETS.includes(t)) extra.add(t)
  }
  return [
    { value: 'all', label: '全部类型' },
    { value: '未分类', label: '未分类' },
    ...MARKER_TYPE_PRESETS.map(t => ({ value: t, label: t })),
    ...[...extra].map(t => ({ value: t, label: t })),
  ]
})
const filteredMarkerNames = computed(() => {
  if (markerTypeFilter.value === 'all') return markerNames.value
  const bsf = currentSprite.value?.bsf
  return markerNames.value.filter(
    n => (bsf?.markers?.[n]?.type || '未分类') === markerTypeFilter.value,
  )
})

/** 复制标记：名字加「副本」并避开重名，展示设置一起复制 */
function duplicateMarker(name: string | null) {
  const bsf = currentSprite.value?.bsf
  if (!bsf || !name) return
  const src = effMarker(name, annoFrameIndex.value)
  if (!src) return
  const entry = bsf.markers?.[name]
  const base = `${name}副本`
  let newName = base
  let i = 2
  while (markerNames.value.includes(newName)) {
    newName = `${base}${i}`
    i++
  }
  if (!bsf.markers) bsf.markers = {}
  bsf.markers[newName] = {
    x: src.x,
    y: src.y,
    ...(entry?.type ? { type: entry.type } : {}),
    ...(entry?.visible === false ? { visible: false } : {}),
    ...(entry?.showLabel === false ? { showLabel: false } : {}),
    ...(entry?.showCoords === false ? { showCoords: false } : {}),
    ...(entry?.locked ? { locked: true } : {}),
  }
  selMarkerName.value = newName
  scheduleSave()
}

/** 当前帧某标记的有效位置：帧覆盖 > 统一值 > null */
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

/** 任意画布坐标 → 图钉 style（放置中的幽灵图钉复用同一套定位） */
function markerPointStyle(p: { x: number; y: number } | null) {
  return p ? { left: `${p.x}px`, top: `${p.y}px` } : { display: 'none' }
}

/** 坐标文本（标记列表 / 幽灵图钉标签共用；取整像素，与场景信息栏一致） */
function markerCoordText(p: { x: number; y: number } | null): string {
  return p ? `${Math.round(p.x)}, ${Math.round(p.y)}` : ''
}

/** 选中标记在当前帧的有效位置（标记设置里的坐标输入用） */
const selMarkerPos = computed(() =>
  selMarkerName.value ? effMarker(selMarkerName.value, annoFrameIndex.value) : null,
)

function markerHandleStyle(name: string) {
  return markerPointStyle(effMarker(name, annoFrameIndex.value))
}

/**
 * 画布标记图钉：直接把 标记.svg 内联为 DOM（fill 换成 currentColor），
 * 颜色由 CSS color 控制（未选中灰白 / 选中红 / 帧覆盖蓝），不依赖 mask-image 的跨 WebView 支持差异。
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

/** 「标记设置」名称输入框（双击图钉聚焦改名用） */
const markerNameInputEl = ref<HTMLInputElement | null>(null)

/** 当前帧内容框中心：工具栏新建标记的默认落点（建完可直接拖到想要的位置） */
function frameContentCenter(): { x: number; y: number } {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return { x: 0, y: 0 }
  const f = bsf.frames[annoFrameIndex.value]
  return f
    ? { x: Math.round(f.offset.x + f.rect.w / 2), y: Math.round(f.offset.y + f.rect.h / 2) }
    : { x: Math.round(bsf.canvas.w / 2), y: Math.round(bsf.canvas.h / 2) }
}

// ── 标记放置（一次性）：点工具栏「标记」→ 半透明图钉跟随鼠标 → 画布点一下落点并结束 ──

const markerPlacing = ref(false)
/** 幽灵图钉落点（画布坐标，只用于显示坐标文字）；null = 不在放置状态 */
const markerGhost = ref<{ x: number; y: number } | null>(null)
/**
 * 幽灵图钉的屏幕位置（相对画布容器，CSS px）。
 * 屏幕空间渲染 = 不参与世界缩放/角色旋转/标注层缩放，避免多层 transform 里逐帧改 left/top 造成重绘闪烁（与地图编辑器一致）。
 */
const markerGhostScreen = ref<{ x: number; y: number } | null>(null)
/** 最近一次鼠标所在画布坐标：进入放置时鼠标还没动过也能先显示在图钉位置 */
let lastCanvasPoint: { x: number; y: number } | null = null

function startMarkerPlacing() {
  if (!currentSprite.value?.bsf) return
  // 标记不是一种工具：放置期间用「选择」工具，落点后能立刻点选、拖动
  activeTool.value = 'select'
  // 落点后会选中新标记，属性面板整页切到「标记管理」，先保证停在属性标签
  rightTab.value = 'props'
  selectionActive.value = false
  selMarkerName.value = null
  markerPlacing.value = true
  const p0 = lastCanvasPoint ?? frameContentCenter()
  markerGhost.value = p0
  markerGhostScreen.value = canvasToScreen(p0)
}

function cancelMarkerPlacing() {
  markerPlacing.value = false
  markerGhost.value = null
  markerGhostScreen.value = null
}

/** 工具栏「标记」：点一下进入一次性放置（只建一个），再点一下取消 */
function toggleMarkerPlacing() {
  if (markerPlacing.value) cancelMarkerPlacing()
  else startMarkerPlacing()
}

/** 放置中的幽灵图钉跟随鼠标（直接落在光标处） */
function updateMarkerGhost(e: MouseEvent, p: { x: number; y: number } | null) {
  if (!markerPlacing.value) return
  const rect = canvasRef.value?.getBoundingClientRect()
  if (p) markerGhost.value = p
  markerGhostScreen.value = rect
    ? { x: e.clientX - rect.left, y: e.clientY - rect.top }
    : null
}

/** 画布落点（唯一入口）：建标记 → 选中 → 退出放置 → 打开右侧标记设置 */
function placeMarkerAt(p: { x: number; y: number } | null) {
  if (!p) return
  const name = addMarker(p)
  cancelMarkerPlacing()
  if (!name) return
  selectMarker(name)
  focusMarkerName()
}

/** 新增标记：唯一命名 标记 / 标记1 / 标记2 ...；统一值（全部帧共用） */
function addMarker(p: { x: number; y: number }): string | null {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return null
  if (!bsf.markers) bsf.markers = {}
  const used = new Set(markerNames.value)
  let name = '标记'
  let n = 1
  while (used.has(name)) {
    name = `标记${n}`
    n++
  }
  bsf.markers[name] = { x: p.x, y: p.y }
  selMarkerName.value = name
  scheduleSave()
  return name
}

/** 从列表 / 画布选中一个标记：高亮它并收起角色的变换手柄 */
function selectMarker(name: string) {
  selMarkerName.value = name
  selectionActive.value = false
  // 选中标记 → 属性面板整页切换为「标记管理」
  if (name) rightTab.value = 'props'
}

/** 选中标记后把焦点交给右侧「标记管理」的名称输入（双击图钉用） */
function focusMarkerName() {
  if (!selMarkerName.value) return
  rightTab.value = 'props'
  nextTick(() => {
    markerNameInputEl.value?.focus()
    markerNameInputEl.value?.select()
  })
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

/** 提交标记改名（失焦 / 回车）：空名或重名时回显原名，不生效 */
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

/** 坐标输入：改选中标记在「作用范围」下的位置 */
function onMarkerCoordChange(axis: 'x' | 'y', e: Event) {
  const v = Number((e.target as HTMLInputElement).value)
  const cur = selMarkerPos.value
  if (!selMarkerName.value || !cur || !Number.isFinite(v)) return
  setMarkerPos(selMarkerName.value, axis === 'x' ? { x: v, y: cur.y } : { x: cur.x, y: v })
}

/**
 * 「脚底」预设：所有帧内容包围盒并集的「水平中心 + 最低点」。
 * 用并集而不是当前帧，避免逐帧覆盖后锚点随动画上下跳动；
 * 水平方向取内容并集的中心，角色左右对称、脚底贴地。
 */
function feetPresetPoint(): { x: number; y: number } {
  const bsf = currentSprite.value?.bsf
  if (!bsf || bsf.frames.length === 0) return { x: 0, y: 0 }
  let minX = Infinity
  let maxX = -Infinity
  let maxBottom = -Infinity
  for (const f of bsf.frames) {
    const left = f.offset.x
    const right = f.offset.x + f.rect.w
    const bottom = f.offset.y + f.rect.h
    if (left < minX) minX = left
    if (right > maxX) maxX = right
    if (bottom > maxBottom) maxBottom = bottom
  }
  return { x: (minX + maxX) / 2, y: maxBottom }
}

/** 预设：中心 = 回到素材原始中心点（偏移 0,0）；脚底 = 内容并集底部中心 */
function applyPivotPreset(kind: 'center' | 'feet') {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  const base = bsf.pivotBase || bsf.pivot
  const p = kind === 'center'
    ? { x: base.x, y: base.y }
    : feetPresetPoint()
  setPivot(p)
}

/**
 * 中心点位置输入：界面值是相对素材原始中心点的偏移，写回时换算成画布绝对坐标。
 * 兜底：中心点被限制在画布范围内（乱输入超长数字不会把它甩到画布外）。
 */
function onCoordChange(axis: 'x' | 'y', e: Event) {
  const raw = Number((e.target as HTMLInputElement).value)
  const cur = annoPivot.value
  const base = annoPivotBase.value
  const canvas = currentSprite.value?.bsf?.canvas
  clearDraft(axis === 'x' ? 'px' : 'py')
  if (!cur || !base || !Number.isFinite(raw)) return
  const clamp = (v: number, max: number) => Math.min(max, Math.max(0, v))
  const targetX = axis === 'x' ? raw + base.x : cur.x
  const targetY = axis === 'y' ? raw + base.y : cur.y
  setPivot({
    x: canvas ? clamp(targetX, canvas.w) : targetX,
    y: canvas ? clamp(targetY, canvas.h) : targetY,
  })
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
 * 角色在场景里会被平移 / 旋转 / 缩放，不能读包围盒（旋转后的包围盒不是真实比例），
 * 必须按正向变换做精确逆运算：
 * 屏幕 = 视口中心 + pan + (x·zoom, -y·zoom) + R(-angle)·((画布点 - 中心点)·显示倍率)
 */
function screenToCanvas(e: MouseEvent): { x: number; y: number } | null {
  const sprite = currentSprite.value
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!sprite || !rect) return null
  const t = sceneTransform.value
  const z = canvasZoom.value
  const dz = displayZoom.value
  if (dz <= 0) return null
  // 场景锚点（包围盒中心）在屏幕上的位置
  const anchorX = rect.left + rect.width / 2 + canvasPanX.value + t.x * z
  const anchorY = rect.top + rect.height / 2 + canvasPanY.value - t.y * z
  const sx = e.clientX - anchorX
  const sy = e.clientY - anchorY
  // 反向旋转（CSS 旋转 -angle，逆运算 +angle）
  const a = t.angle * Math.PI / 180
  const cos = Math.cos(a)
  const sin = Math.sin(a)
  const vx = (sx * cos - sy * sin) / dz
  const vy = (sx * sin + sy * cos) / dz
  const p = objectAnchor.value
  return { x: Math.round((vx + p.x) * 2) / 2, y: Math.round((vy + p.y) * 2) / 2 }
}

/** 逻辑画布坐标 → 画布容器内的屏幕坐标（screenToCanvas 的正向变换；幽灵图钉用） */
function canvasToScreen(p: { x: number; y: number }): { x: number; y: number } | null {
  const sprite = currentSprite.value
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!sprite || !rect) return null
  const t = sceneTransform.value
  const z = canvasZoom.value
  const dz = displayZoom.value
  if (dz <= 0) return null
  const a = t.angle * Math.PI / 180
  const cos = Math.cos(a)
  const sin = Math.sin(a)
  const o = objectAnchor.value
  const dx = (p.x - o.x) * dz
  const dy = (p.y - o.y) * dz
  return {
    x: rect.width / 2 + canvasPanX.value + t.x * z + (dx * cos + dy * sin),
    y: rect.height / 2 + canvasPanY.value - t.y * z + (-dx * sin + dy * cos),
  }
}

function onPivotMouseDown(e: MouseEvent) {
  if (e.button !== 0) return // 中键放行画布平移，仅左键起拖
  e.stopPropagation()
  e.preventDefault()
  // 锁定拖拽期间的外层锚点：角色画面绝对不动，只有锚点图标跟手（避免逐帧补偿抖动）
  const p = annoPivot.value
  pivotViewAnchor.value = p ? { ...p } : null
  isPivotDragging.value = true
}

function onPivotDragMove(e: MouseEvent) {
  if (!isPivotDragging.value) return
  const p = screenToCanvas(e)
  if (p) setPivot(p, false)
}

function onPivotDragUp() {
  if (!isPivotDragging.value) return
  isPivotDragging.value = false
  // 松手：把拖拽期间累计的中心点位移一次性补偿进变换位置
  const base = pivotViewAnchor.value
  const cur = annoPivot.value
  pivotViewAnchor.value = null
  if (base && cur) compensatePivotDelta(cur.x - base.x, cur.y - base.y)
  scheduleSave()
}

// ── 标记拖拽（选中 + 拖动；复用中心的全局监听模式） ──

const isMarkerDragging = ref(false)

function onMarkerMouseDown(name: string, e: MouseEvent) {
  if (e.button !== 0) return
  // 只有「选择 / 动画」工具下图钉可交互；中心、碰撞工具下只做展示，点击穿透给对应手柄
  if (activeTool.value !== 'select' && activeTool.value !== 'none') return
  e.stopPropagation()
  e.preventDefault()
  // 放置中点已有图钉 = 放弃这次放置，直接选中它
  if (markerPlacing.value) cancelMarkerPlacing()
  selectMarker(name)
  // 锁定位置：可以选中查看，但不进入拖动
  isMarkerDragging.value = !markerFlag(name, 'locked')
}

function onMarkerDragMove(e: MouseEvent) {
  if (!isMarkerDragging.value || !selMarkerName.value) return
  const p = screenToCanvas(e)
  if (p) setMarkerPos(selMarkerName.value, p)
}

function onMarkerDragUp() {
  isMarkerDragging.value = false
}

// ── 变换手柄拖拽：移动 / 等比缩放 / 旋转 ──

function normalizeAngle(a: number): number {
  const n = (((a + 180) % 360) + 360) % 360 - 180
  return Math.round((Math.abs(n) === 180 ? 180 : n) * 10) / 10
}

/**
 * 角色包围盒在「场景屏幕坐标」下的轴对齐矩形（y 向下，与 CSS 一致）。
 * 智能吸附用它把包围盒的边 / 中心对齐到世界原点轴与网格线。
 */
function frameWorldRect(t: SpriteTransform): { left: number; top: number; right: number; bottom: number } | null {
  const b = displayFrameBounds.value
  const p = objectAnchor.value
  if (b.w <= 0 || b.h <= 0) return null
  const sx = Math.max(5, t.scaleX ?? t.scale) / 100
  const sy = Math.max(5, t.scaleY ?? t.scale) / 100
  // 内容框中心相对角色原点（中心点）的偏移 → 分轴缩放 → 旋转（CSS 用 -angle）
  const cx = (b.x + b.w / 2 - p.x) * sx
  const cy = (b.y + b.h / 2 - p.y) * sy
  const rad = (-t.angle * Math.PI) / 180
  const cos = Math.cos(rad)
  const sin = Math.sin(rad)
  const rx = cx * cos - cy * sin
  const ry = cx * sin + cy * cos
  const hw0 = (b.w * sx) / 2
  const hh0 = (b.h * sy) / 2
  const hw = Math.abs(hw0 * cos) + Math.abs(hh0 * sin)
  const hh = Math.abs(hw0 * sin) + Math.abs(hh0 * cos)
  const centerX = t.x + rx
  const centerY = -t.y + ry
  return { left: centerX - hw, top: centerY - hh, right: centerX + hw, bottom: centerY + hh }
}

/**
 * 变换手柄外层：左键点在框内不穿透给画布（避免误取消选中）；
 * 但中键 / 空格+左键 / Alt+左键 是画布平移，必须放行，否则鼠标停在角色框内时无法平移画布
 */
function onGizmoRootMouseDown(e: MouseEvent) {
  if (shouldStartPan(e)) return
  e.stopPropagation()
}

/** 手柄拖动开始：内部=移动，四角=等比缩放，顶部圆点=旋转 */
function startGizmoDrag(kind: 'move' | 'scale' | 'rotate', e: MouseEvent) {
  if (e.button !== 0 || !gizmoVisible.value) return
  e.preventDefault()
  e.stopPropagation()
  const t = ensureTransform()
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!t || !rect) return
  const z = canvasZoom.value
  const pivotClientX = rect.left + rect.width / 2 + canvasPanX.value + t.x * z
  const pivotClientY = rect.top + rect.height / 2 + canvasPanY.value - t.y * z
  const dx = e.clientX - pivotClientX
  const dy = e.clientY - pivotClientY
  gizmoDrag.value = {
    kind,
    startClientX: e.clientX,
    startClientY: e.clientY,
    start: { ...t },
    pivotClientX,
    pivotClientY,
    startDistance: Math.hypot(dx, dy),
    startPointerAngle: Math.atan2(dy, dx),
  }
  document.addEventListener('mousemove', onGizmoDragMove)
  document.addEventListener('mouseup', onGizmoDragUp)
}

function onGizmoDragMove(e: MouseEvent) {
  const d = gizmoDrag.value
  if (!d) return
  const t = ensureTransform()
  if (!t) return
  const z = canvasZoom.value
  if (d.kind === 'move') {
    let dx = (e.clientX - d.startClientX) / z
    let dy = -(e.clientY - d.startClientY) / z
    if (e.shiftKey) {
      if (Math.abs(dx) >= Math.abs(dy)) dy = 0
      else dx = 0
    }
    let nx = d.start.x + dx
    let ny = d.start.y + dy
    if (snapEnabled.value) {
      // 智能吸附：包围盒的边 / 中心就近对齐世界原点轴（x=0 / y=0）与网格线；
      // 附近没有候选线时 snapRectOffset 会回退成整数像素吸附
      const rect = frameWorldRect({ ...d.start, x: nx, y: ny })
      if (rect) {
        const off = snapRectOffset(rect, { xs: [0], ys: [0] }, gridStepWorld(z), snapThreshold(z))
        nx += off.dx
        ny -= off.dy // 场景屏幕坐标 y 向下 → 用户坐标 y 向上
      }
    }
    t.x = Math.round(nx)
    t.y = Math.round(ny)
  } else if (d.kind === 'scale') {
    const dist = Math.hypot(e.clientX - d.pivotClientX, e.clientY - d.pivotClientY)
    const ratio = d.startDistance > 0 ? dist / d.startDistance : 1
    const clamp = (v: number) => Math.min(1000, Math.max(5, Math.round(v)))
    if (scaleLink.value) {
      // 约束比例：两轴同步，清掉分轴值
      t.scale = clamp(d.start.scale * ratio)
      delete t.scaleX
      delete t.scaleY
    } else {
      // 已取消约束：按各自起点等比缩放，保持宽高比
      const sx0 = d.start.scaleX ?? d.start.scale
      const sy0 = d.start.scaleY ?? d.start.scale
      t.scaleX = clamp(sx0 * ratio)
      t.scaleY = clamp(sy0 * ratio)
    }
  } else {
    const pointerAngle = Math.atan2(e.clientY - d.pivotClientY, e.clientX - d.pivotClientX)
    const delta = (pointerAngle - d.startPointerAngle) * 180 / Math.PI
    // 屏幕顺时针 = 用户角度逆时针为负
    let angle = d.start.angle - delta
    angle = e.shiftKey ? Math.round(angle / 15) * 15 : angle
    t.angle = normalizeAngle(angle)
  }
  scheduleSave()
}

function onGizmoDragUp() {
  if (!gizmoDrag.value) return
  gizmoDrag.value = null
  document.removeEventListener('mousemove', onGizmoDragMove)
  document.removeEventListener('mouseup', onGizmoDragUp)
  scheduleSave()
}

/** Esc 取消正在进行的变换拖拽：回到拖拽前状态 */
function cancelGizmoDrag() {
  const d = gizmoDrag.value
  if (!d) return
  const t = ensureTransform()
  if (t) {
    t.x = d.start.x
    t.y = d.start.y
    t.angle = d.start.angle
    t.scale = d.start.scale
    // 分轴缩放同样恢复（start 里缺省表示当时是统一缩放）
    if (d.start.scaleX === undefined) delete t.scaleX
    else t.scaleX = d.start.scaleX
    if (d.start.scaleY === undefined) delete t.scaleY
    else t.scaleY = d.start.scaleY
  }
  gizmoDrag.value = null
  document.removeEventListener('mousemove', onGizmoDragMove)
  document.removeEventListener('mouseup', onGizmoDragUp)
}

/** 键盘事件来自输入框时不触发全局快捷键 */
function isTypingTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  if (!el) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable
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
  const sprite = currentSprite.value
  if (!sprite) return
  const [removed] = sprite.frames.splice(index, 1)
  // .bsf 帧元数据与帧列表一一对应：必须同步删除，否则保存 manifest 时会把已删帧写回去
  if (sprite.bsf && index < sprite.bsf.frames.length) {
    sprite.bsf.frames.splice(index, 1)
  }
  // 回收该帧的 objectURL（撤销恢复时由 useSpriteHistory 的 restoreFrame 用 blob 重建）
  if (removed?.url) {
    revokedFrameUrls.add(removed.url)
    frameImages.delete(removed.url)
    URL.revokeObjectURL(removed.url)
  }
  for (const anim of sprite.animations) {
    if (anim.end > sprite.frames.length) {
      anim.end = sprite.frames.length
    }
    if (anim.start > anim.end) anim.start = anim.end
  }
  if (sprite.defaultFrameIndex != null && sprite.defaultFrameIndex >= sprite.frames.length) {
    sprite.defaultFrameIndex = Math.max(0, sprite.frames.length - 1)
  }
  if (selectedFrameIndex.value >= sprite.frames.length) {
    selectedFrameIndex.value = Math.max(0, sprite.frames.length - 1)
  }
  costumeContextMenu.value.show = false
  scheduleSave()
}

function onAnimContextMenu(e: MouseEvent, name: string) {
  e.preventDefault()
  animContextMenu.value = { show: true, x: e.clientX, y: e.clientY, name }
}

let wasPlayingBeforeRename = false

/** 重命名输入框的 ref 用函数式绑定：它位于 v-for 内，模板 ref 会被 Vue 收集成数组，不能直接 .focus() */
function setRenameInput(el: unknown) {
  renameInputRef.value = (el as HTMLInputElement | null) || null
}

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

// 记住用户最后一次的场景缩放（切换角色 / 重新进入角色编辑器时沿用）
watch(canvasZoom, z => saveSceneZoom(z))

// 记住用户最后停留的右侧面板页（首次进入默认「动画」页；碰撞页不作为常驻页记忆）
watch(rightTab, tab => {
  try {
    localStorage.setItem(RIGHT_TAB_KEY, tab === 'collision' ? 'props' : tab)
  } catch {
    // localStorage 不可用时忽略
  }
  // 属性页 / 碰撞页切换后输入框是新建的节点，重新吸附才能测到宽度
  nextTick(observeUnitFields)
})

// 帧切换 / 缩放 / 预览倍率 / 渲染模式变化 → 重绘（flush: post 保证 canvas 已挂载）
// 注意：必须放在所有 ref/computed 声明之后——watch 创建时会立即求值一次来源，
// 提前注册会在 setup 阶段抛 TDZ（Cannot access 'canvasZoom' before initialization），
// 整个角色编辑器挂载失败、连 Vue 的更新队列都会卡住
watch(
  [
    () => currentSprite.value?.frames[canvasDisplayIndex.value]?.url,
    () => currentSprite.value?.frames[selectedFrameIndex.value]?.url,
    () => canvasZoom.value,
    // 角色缩放会改变光栅化倍率，必须重画（否则 canvas 尺寸不跟随，放大后发糊）
    () => sceneTransform.value.scale,
    () => sceneTransform.value.scaleX,
    () => sceneTransform.value.scaleY,
    () => previewScale.value,
    () => editorStore.renderMode,
    // 画风分析是异步的：结果落地后要按新的采样方式重画 canvas
    () => spritePixelArt.value,
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
  // 标记放置中按 Esc 退出（与地图编辑器一致）
  window.addEventListener('keydown', onEditorKeydown)
  window.addEventListener('keyup', onEditorKeyup)
  window.addEventListener('blur', onWindowBlur)
  // 场景视口尺寸：网格对齐 / 适配视图 / 原点坐标都依赖它
  const el = canvasRef.value
  if (el) {
    viewSize.value = { w: el.clientWidth, h: el.clientHeight }
    viewResizeObserver = new ResizeObserver(() => {
      viewSize.value = { w: el.clientWidth, h: el.clientHeight }
    })
    viewResizeObserver.observe(el)
  }
  // 首屏：canvas 挂载后按当前帧画一次；视口刚测好时补做一次视图适配
  nextTick(() => {
    redrawSpriteImages()
    if (sceneFitPending.value) {
      sceneFitPending.value = false
      applyInitialSceneView()
    }
  })
})

onBeforeUnmount(() => {
  stopAnimation()
  revokeSpriteUrls(currentSprite.value)
  if (saveTimer) clearTimeout(saveTimer)
  viewResizeObserver?.disconnect()
  viewResizeObserver = null
  document.removeEventListener('mouseup', onGlobalMouseUp)
  document.removeEventListener('mousemove', onPivotDragMove)
  document.removeEventListener('mouseup', onPivotDragUp)
  document.removeEventListener('mousemove', onMarkerDragMove)
  document.removeEventListener('mouseup', onMarkerDragUp)
  document.removeEventListener('mousemove', onGizmoDragMove)
  document.removeEventListener('mouseup', onGizmoDragUp)
  window.removeEventListener('keydown', onEditorKeydown)
  window.removeEventListener('keyup', onEditorKeyup)
  window.removeEventListener('blur', onWindowBlur)
})

function onEditorKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && gizmoDrag.value) cancelGizmoDrag()
  // 空格临时平移（输入框里敲空格不拦截；不 preventDefault，避免抢掉按钮的键盘激活）
  if (e.code === 'Space' && !isTypingTarget(e.target)) {
    spaceHeld.value = true
    return
  }
  // 输入框里的按键留给输入框（原生撤销/重做、F 输入文字都不能被抢走）
  if (isTypingTarget(e.target)) return

  // 标记：Esc 退出放置 / 取消选中；Delete 删除选中（与地图编辑器一致）
  if (e.key === 'Escape') {
    if (markerPlacing.value) {
      cancelMarkerPlacing()
      e.preventDefault()
      return
    }
    if (selMarkerName.value) {
      selMarkerName.value = null
      return
    }
  }
  if ((e.key === 'Delete' || e.key === 'Backspace') && selMarkerName.value) {
    deleteMarker(selMarkerName.value)
    e.preventDefault()
    return
  }

  // 撤销 / 重做（与绘制页、地图编辑器一致）：
  // macOS = Cmd+Z / Cmd+Shift+Z；Windows = Ctrl+Z / Ctrl+Y（同时兼容 Ctrl+Shift+Z）
  const mod = e.ctrlKey || e.metaKey
  if (mod) {
    const key = e.key.toLowerCase()
    if (key === 'z') {
      if (e.shiftKey) redo()
      else undo()
      e.preventDefault()
      return
    }
    if (key === 'y' && !e.shiftKey) {
      redo()
      e.preventDefault()
      return
    }
  }

  // F：角色回到视口中心，并把缩放恢复成 100%
  if (!mod && !e.altKey && !e.shiftKey && (e.key === 'f' || e.key === 'F')) {
    if (currentSprite.value) resetCanvas()
    e.preventDefault()
  }
}

function onEditorKeyup(e: KeyboardEvent) {
  if (e.code === 'Space') spaceHeld.value = false
}

function onWindowBlur() {
  spaceHeld.value = false
}
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
      <!-- 场景工具条：选择（变换）/ 中心 / 碰撞 / 标记，同一场景框架 -->
      <div v-if="currentSprite" class="anno-toolbar">
        <button
          class="layer-chip"
          :class="{ active: activeTool === 'select' }"
          type="button"
          @click="pickTool('select')"
        >
          <img :src="iconSelectTool" class="layer-chip-icon" alt="" />选择
        </button>
        <button
          v-if="canAnno"
          class="layer-chip"
          :class="{ active: activeTool === 'pivot' }"
          type="button"
          @click="pickTool('pivot')"
        >
          <img :src="iconCenterPivot" class="layer-chip-icon" alt="" />中心
        </button>
        <button
          v-if="canAnno"
          class="layer-chip"
          :class="{ active: activeTool === 'collision' }"
          type="button"
          @click="pickTool('collision')"
        >
          <img :src="iconResetAnchor" class="layer-chip-icon" alt="" />碰撞
        </button>
        <button
          class="layer-chip"
          :class="{ active: rightTab === 'animation' }"
          type="button"
          @click="pickAnimation"
        >
          <img :src="iconAnimation" class="layer-chip-icon" alt="" />动画
        </button>
        <button
          v-if="canAnno"
          class="layer-chip"
          :class="{ active: markerPlacing }"
          type="button"
          :title="markerPlacing ? '取消放置标记' : '标记：点一下后图钉跟随鼠标，在画布上点一下完成创建'"
          @click="toggleMarkerPlacing"
        >
          <img :src="iconMarker" class="layer-chip-icon" alt="" />标记
        </button>
        <!-- 常驻显示开关：碰撞盒 / 网格 / 智能吸附（与地图编辑器、绘制页同一套开关语义） -->
        <span class="anno-toolbar-sep"></span>
        <button
          v-if="canAnno"
          class="layer-chip chip-toggle"
          :class="{ active: showCollisionBox }"
          type="button"
          title="显示碰撞形状（只查看，需切到「碰撞」工具才能拖动）"
          @click="showCollisionBox = !showCollisionBox"
        >
          <span class="chip-check" :class="{ on: showCollisionBox }"></span>显示碰撞
        </button>
        <button
          class="layer-chip chip-toggle"
          :class="{ active: showGrid }"
          type="button"
          title="显示网格"
          @click="showGrid = !showGrid"
        >
          <span class="chip-check" :class="{ on: showGrid }"></span>网格
        </button>
        <button
          class="layer-chip chip-toggle"
          :class="{ active: snapEnabled }"
          type="button"
          title="智能吸附：拖动角色时对齐世界原点轴与网格线"
          @click="snapEnabled = !snapEnabled"
        >
          <span class="chip-check" :class="{ on: snapEnabled }"></span>吸附
        </button>
        <!-- 详细设置集中在右侧「属性」面板：随当前工具联动 -->
      </div>

      <div
        ref="canvasRef"
        class="sprite-canvas scene-viewport"
        :class="{
          'is-panning': isPanning,
          'is-space-ready': spaceHeld && !isPanning,
          'is-marker-placing': markerPlacing,
        }"
        @wheel.prevent="onCanvasWheel"
        @mousedown="onCanvasMouseDown"
        @mousemove="onCanvasMouseMove"
        @mouseup="onCanvasMouseUp"
        @dblclick="resetCanvas"
      >
        <!-- 无限网格 + 世界原点轴（类似地图编辑器的工作区，不画舞台边界） -->
        <canvas v-show="showGrid" ref="gridCanvasEl" class="scene-grid-canvas"></canvas>
        <div class="scene-axis scene-axis-x" :style="{ top: `${originScreen.y}px` }"></div>
        <div class="scene-axis scene-axis-y" :style="{ left: `${originScreen.x}px` }"></div>
        <div
          class="scene-origin-dot"
          :style="{ left: `${originScreen.x}px`, top: `${originScreen.y}px` }"
        ></div>

        <!-- 世界层：角色对象以中心点为定位 / 旋转原点，包围盒随变换移动 -->
        <div class="scene-world" :style="sceneWorldStyle">
          <div
            v-if="currentSprite?.frames[canvasDisplayIndex]"
            class="sprite-object"
            :style="spriteObjectStyle"
          >
            <!-- 帧图由 canvas 自绘：采样方式（最近邻/平滑）由 imageSmoothingEnabled 决定，
                 不受浏览器对 <img> 放大时的合成层重采样影响 -->
            <canvas
              ref="spriteCanvasEl"
              class="canvas-sprite"
              :style="{ imageRendering: imageRenderingStyle, ...frameCanvasStyle }"
            />
            <!-- 标注层：画布坐标 + transform 缩放（手柄内部再 1/显示倍率 反向缩放保持屏幕尺寸恒定） -->
            <div
              v-if="canAnno && currentSprite?.bsf"
              class="canvas-anno-layer"
              :style="annoLayerStyle"
            >
              <!-- 洋葱皮幽灵：相邻帧有效中心点不一致时显示（中心点图层） -->
              <div
                v-for="g in (activeTool === 'pivot' ? pivotGhosts : [])"
                :key="g.i"
                class="pivot-ghost"
                :style="{ left: `${g.x}px`, top: `${g.y}px` }"
              >
                <div class="ghost-counter" :style="{ transform: `scale(${1 / displayZoom})` }">
                  <span class="ghost-ring"></span>
                </div>
              </div>
              <!-- 中心点手柄（碰撞图层下弱化显示、不响应交互） -->
              <div
                v-if="annoPivot"
                class="pivot-handle"
                :class="{ 'is-override': annoScope === 'one', 'is-inactive': activeTool !== 'pivot', 'is-select': activeTool === 'select' }"
                :style="pivotHandleStyle"
                @mousedown="onPivotMouseDown"
              >
                <div class="pivot-visual" :style="{ transform: `scale(${1 / Math.max(0.001, canvasLayoutZoom)})` }">
                  <div class="pivot-anchor-icon" v-html="pivotAnchorMarkup"></div>
                </div>
              </div>
              <!-- 碰撞形状叠加层（自动态显示引擎内容框；拖动手柄立即转为自定义） -->
              <CollisionShapeOverlay
                v-if="activeTool === 'collision' || showCollisionBox"
                :class="{ 'collision-preview': activeTool !== 'collision' }"
                :canvas-w="currentSprite.bsf.canvas.w"
                :canvas-h="currentSprite.bsf.canvas.h"
                :shape="collisionDisplay"
                :zoom="displayZoom"
                :angle="sceneTransform.angle"
                :shape-angle="collisionAngleValue"
                :kind="collisionKindValue"
                :disabled="collisionDisabled"
                @update="onCollisionUpdate"
              />
            </div>
          </div>
        </div>

        <!-- 变换手柄（屏幕空间：手柄尺寸恒定，不随场景缩放变形） -->
        <div class="scene-gizmo-layer" :style="sceneGizmoLayerStyle">
          <div
            v-if="gizmoVisible"
            class="gizmo-root"
            :style="gizmoRootStyle"
            @mousedown="onGizmoRootMouseDown"
            @dblclick.stop
          >
            <div class="gizmo-rotator" :style="gizmoRotatorStyle">
              <div
                class="gizmo-frame"
                :style="gizmoFrameStyle"
                title="拖动移动角色"
                @mousedown="startGizmoDrag('move', $event)"
              >
                <span
                  v-for="corner in (['tl', 'tr', 'br', 'bl'] as const)"
                  :key="corner"
                  class="gizmo-handle"
                  :style="gizmoHandleStyle(corner)"
                  @mousedown="startGizmoDrag('scale', $event)"
                ></span>
              </div>
              <div class="gizmo-arm" :style="gizmoArmStyle"></div>
              <div
                class="gizmo-knob"
                :style="gizmoKnobStyle"
                title="拖动旋转角色（按住 Shift 每 15° 吸附）"
                @mousedown="startGizmoDrag('rotate', $event)"
              ></div>
            </div>
            <div
              class="gizmo-anchor-icon"
              v-html="pivotAnchorMarkup"
              :style="gizmoAnchorIconStyle"
              title="旋转中心：中心点"
            ></div>
          </div>
        </div>

        <!-- 标记图钉层：与角色变换完全同步，但绘制在变换手柄之上
             （否则悬停在角色范围内时命中带 cursor:move 的变换框，无法直接点选标记） -->
        <div
          v-if="canAnno && markerNames.length"
          class="scene-world marker-world"
          :style="sceneWorldStyle"
        >
          <div class="sprite-object" :style="spriteObjectStyle">
            <div class="canvas-anno-layer" :style="annoLayerStyle">
              <div
                v-for="name in visibleMarkerNames"
                :key="name"
                class="marker-handle"
                :class="{
                  'is-selected': name === selMarkerName,
                  'is-override': hasMarkerOverride(name, annoFrameIndex),
                  'is-interactive': activeTool === 'select' || activeTool === 'none',
                  'is-locked': markerFlag(name, 'locked'),
                }"
                :style="markerHandleStyle(name)"
                @mousedown="onMarkerMouseDown(name, $event)"
                @dblclick.stop="focusMarkerName"
              >
                <div class="marker-visual" :style="{ transform: `scale(${1 / displayZoom}) rotate(${sceneTransform.angle}deg)` }">
                  <div class="marker-icon" v-html="markerIconSvg"></div>
                  <span
                    v-if="markerFlag(name, 'showLabel') || markerFlag(name, 'showCoords')"
                    class="marker-label"
                  >
                    <b v-if="markerFlag(name, 'showLabel')">{{ name }}</b>
                    <span v-if="markerFlag(name, 'showCoords')">({{ markerCoordText(effMarker(name, annoFrameIndex)) }})</span>
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 放置中的幽灵图钉：屏幕空间跟随鼠标（不放进缩放/旋转图层，避免逐帧重绘闪烁；与地图编辑器同款） -->
        <div
          v-if="markerPlacing && markerGhostScreen"
          class="marker-handle is-ghost is-ghost-overlay"
          :style="{ transform: `translate(${markerGhostScreen.x}px, ${markerGhostScreen.y}px)` }"
        >
          <div class="marker-visual">
            <div class="marker-icon" v-html="markerIconSvg"></div>
            <span class="marker-label"><b>新标记</b><span v-if="markerGhost">({{ markerCoordText(markerGhost) }})</span></span>
          </div>
        </div>

        <!-- 右下角浮动视图工具条：缩放 / 撤销 / 重做（与地图编辑器一致） -->
        <div class="scene-zoom-bar" @mousedown.stop @dblclick.stop>
          <button class="scene-float-btn" type="button" v-tooltip="'缩小'" @click="zoomBy(0.9)">
            <img :src="iconZoomOut" width="16" height="16" draggable="false" />
          </button>
          <button class="scene-float-zoom" type="button" v-tooltip="'重置视图（100%）'" @click="resetCanvas">
            {{ zoomPercent }}%
          </button>
          <button class="scene-float-btn" type="button" v-tooltip="'放大'" @click="zoomBy(1.1)">
            <img :src="iconZoomIn" width="16" height="16" draggable="false" />
          </button>
          <div class="scene-float-divider"></div>
          <button
            class="scene-float-btn"
            type="button"
            :disabled="!canUndo"
            v-tooltip="'撤销（Ctrl+Z）'"
            @click="undo()"
          >
            <img :src="iconUndo" width="14" height="14" draggable="false" />
          </button>
          <button
            class="scene-float-btn"
            type="button"
            :disabled="!canRedo"
            v-tooltip="'重做（Ctrl+Shift+Z）'"
            @click="redo()"
          >
            <img :src="iconRedo" width="14" height="14" draggable="false" />
          </button>
        </div>
      </div>
    </div>

    <!-- 右: 面板（第一个标签随工具在 动画/碰撞 之间切换，另有属性页；选中标记时属性页整体切为标记管理；272px） -->
    <div class="preview-panel">
      <div class="right-tabs">
        <button
          class="right-tab"
          :class="{ active: rightTab === rightContextTab }"
          type="button"
          @click="rightTab = rightContextTab"
        >{{ rightContextTab === 'collision' ? '碰撞' : '动画' }}</button>
        <button
          class="right-tab"
          :class="{ active: rightTab === 'props' }"
          type="button"
          @click="rightTab = 'props'"
        >属性</button>
      </div>

      <!-- 动画页：预览 + 播放控制 + 动画片段 -->
      <template v-if="rightTab === 'animation'">

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
                :ref="setRenameInput"
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
      </template>

      <!-- 碰撞页：点击工具条「碰撞」进入；内容全部针对碰撞，排版对齐属性面板 -->
      <div v-else-if="rightTab === 'collision'" class="props-scroll">
        <div class="att-frame">
          <div v-if="!canAnno" class="mi-list-empty">
            当前角色还没有可编辑的标注数据（单图角色首次编辑并保存后会自动转为 .bsf）。
          </div>
          <template v-else>
            <!-- 基础设置：作用 / 类型 / 形状 / 单向碰撞 / 碰撞层级 -->
            <div class="att-group">
              <div class="mi-section" :class="{ open: colFold.basic }">
                <button class="mi-head" type="button" @click="colFold.basic = !colFold.basic">
                  <img :src="iconChevron" class="mi-chevron" alt="" />
                  <span class="mi-head-title">基础设置</span>
                </button>
                <div v-if="colFold.basic" class="mi-body">
                  <div class="att-row">
                    <span class="att-label">作用</span>
                    <CustomSelect
                      class="att-select"
                      :model-value="collisionKindValue"
                      :options="COLLISION_KIND_OPTIONS"
                      @update:model-value="onCollisionKindSelect"
                    />
                  </div>
                  <div class="att-row">
                    <span class="att-label">类型</span>
                    <CustomSelect
                      class="att-select"
                      :model-value="collisionTagValue"
                      :options="collisionTagOptions"
                      placeholder="未命名"
                      @update:model-value="onCollisionTagSelect"
                    />
                  </div>
                  <div v-if="spriteTagCustomMode" class="att-row">
                    <span class="att-label">类型名</span>
                    <input
                      class="att-input"
                      :value="collisionTagDraft"
                      maxlength="20"
                      placeholder="设置类型名"
                      @input="onCollisionTagInput"
                      @blur="onCollisionTagBlur"
                      @keydown.enter="($event.target as HTMLInputElement).blur()"
                    />
                  </div>
                  <div class="att-row">
                    <span class="att-label">形状</span>
                    <CustomSelect
                      class="att-select"
                      :model-value="collisionTypeValue"
                      :options="COLLISION_TYPE_OPTIONS"
                      @update:model-value="onCollisionTypeSelect"
                    />
                  </div>
                  <div class="att-row">
                    <span class="att-label">单向碰撞</span>
                    <label class="att-checkbox" title="只从「方向」那一侧挡住，另一侧可以穿过">
                      <input
                        type="checkbox"
                        :checked="collisionOneWay"
                        :disabled="collisionPhysicsDisabled"
                        @change="onCollisionOneWayChange"
                      />
                      <span class="att-checkbox-text">启用</span>
                    </label>
                  </div>
                  <template v-if="collisionOneWay">
                    <div class="att-row">
                      <span class="att-label">方向</span>
                      <CustomSelect
                        class="att-select"
                        :model-value="collisionOneWayDirValue"
                        :options="ONE_WAY_DIRECTIONS"
                        :disabled="collisionPhysicsDisabled"
                        @update:model-value="onCollisionOneWayDirChange"
                      />
                    </div>
                    <div class="att-row">
                      <span class="att-label">厚度</span>
                      <input
                        class="att-input att-input-no-spin"
                        type="number"
                        min="0"
                        max="8"
                        step="0.5"
                        :value="collisionOneWayMargin"
                        :disabled="collisionPhysicsDisabled"
                        @change="onCollisionOneWayMarginInput"
                      />
                    </div>
                  </template>
                  <div class="att-row">
                    <span class="att-label">碰撞层级</span>
                    <label class="att-checkbox" title="碰撞层级开关（现阶段保存设置，运行时暂未接入）">
                      <input
                        type="checkbox"
                        :checked="collisionLayersEnabled"
                        @change="onCollisionLayersChange"
                      />
                      <span class="att-checkbox-text">启用</span>
                    </label>
                  </div>
                  <template v-if="collisionLayersEnabled">
                    <div class="layer-block">
                      <span class="layer-block-name">碰撞层</span>
                      <div class="layer-grid">
                        <button
                          v-for="n in 8"
                          :key="`sprite-layer-${n}`"
                          type="button"
                          class="layer-cell"
                          :class="{ 'layer-cell-active': collisionLayer === n }"
                          @click="onCollisionLayerSelect(n)"
                        >{{ n }}</button>
                      </div>
                    </div>
                    <div class="layer-block">
                      <span class="layer-block-name">碰撞掩码</span>
                      <div class="layer-grid">
                        <button
                          v-for="n in 8"
                          :key="`sprite-mask-${n}`"
                          type="button"
                          class="layer-cell"
                          :class="{ 'layer-cell-active': collisionMask.includes(n) }"
                          @click="toggleCollisionMask(n)"
                        >{{ n }}</button>
                      </div>
                    </div>
                    <div class="att-row">
                      <span class="att-label">碰撞材质</span>
                      <CustomSelect
                        class="att-select"
                        model-value="default"
                        :options="physicsMaterialOptions"
                        disabled
                      />
                    </div>
                  </template>
                  <div class="att-row">
                    <span class="att-label">禁用碰撞</span>
                    <label class="att-checkbox" title="整个角色不参与地形/边界物理阻挡（形状保留，取消勾选即恢复）">
                      <input
                        type="checkbox"
                        :checked="collisionDisabled"
                        @change="onCollisionDisabledChange"
                      />
                      <span class="att-checkbox-text">启用</span>
                    </label>
                  </div>
                  <div v-if="collisionTypeValue !== 'auto'" class="mi-actions">
                    <button class="mi-btn" type="button" @click="resetCollisionToAuto">恢复自动碰撞</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 变换：位置 / 缩放（约束比例）/ 旋转，均相对自动碰撞框 -->
            <div class="att-group">
              <div class="mi-section" :class="{ open: colFold.transform }">
                <button class="mi-head" type="button" @click="colFold.transform = !colFold.transform">
                  <img :src="iconChevron" class="mi-chevron" alt="" />
                  <span class="mi-head-title">变换</span>
                </button>
                <div v-if="colFold.transform" class="mi-body">
                  <div class="att-row att-row-stacked has-reset">
                    <span class="att-label">位置</span>
                    <div class="att-axis-group">
                      <div class="att-axis-row">
                        <div class="att-axis-field has-unit" ref="colPosXFieldEl">
                          <span class="att-axis-tag is-x">X</span>
                          <input
                            class="att-input att-input-no-spin"
                            type="text"
                            inputmode="decimal"
                            title="相对自动碰撞框中心的左右偏移：0 = 没动过，正数向右"
                            :value="draftValue('colPosX', collisionPosX)"
                            @focus="selectOnFocus"
                            @input="onFieldDraft('colPosX', $event)"
                            @blur="clearDraft('colPosX')"
                            @change="onCollisionPosChange(0, $event)"
                          />
                          <span class="att-axis-unit" :style="collisionUnitStyleFor('x', collisionPosX)">px</span>
                          <!-- X 被改动过才显示：单独重置水平偏移 -->
                          <button
                            class="att-reset"
                            :class="{ 'is-dirty': collisionPosXDirty }"
                            type="button"
                            :disabled="!collisionPosXDirty"
                            title="重置 X（回到自动碰撞框中心）"
                            @click="resetCollisionAxis('posX')"
                          >
                            <img :src="iconReset" alt="" />
                          </button>
                        </div>
                      </div>
                      <div class="att-axis-row">
                        <div class="att-axis-field has-unit" ref="colPosYFieldEl">
                          <span class="att-axis-tag is-y">Y</span>
                          <input
                            class="att-input att-input-no-spin"
                            type="text"
                            inputmode="decimal"
                            title="相对自动碰撞框中心的上下偏移：0 = 没动过，正数向上"
                            :value="draftValue('colPosY', collisionPosY)"
                            @focus="selectOnFocus"
                            @input="onFieldDraft('colPosY', $event)"
                            @blur="clearDraft('colPosY')"
                            @change="onCollisionPosChange(1, $event)"
                          />
                          <span class="att-axis-unit" :style="collisionUnitStyleFor('y', collisionPosY)">px</span>
                          <button
                            class="att-reset"
                            :class="{ 'is-dirty': collisionPosYDirty }"
                            type="button"
                            :disabled="!collisionPosYDirty"
                            title="重置 Y（回到自动碰撞框中心）"
                            @click="resetCollisionAxis('posY')"
                          >
                            <img :src="iconReset" alt="" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="att-row att-row-stacked has-reset">
                    <span class="att-label">缩放</span>
                    <div class="att-axis-group">
                      <div class="att-axis-row">
                        <div class="att-axis-field">
                          <span class="att-axis-tag is-x">X</span>
                          <input
                            class="att-input att-input-no-spin"
                            type="text"
                            inputmode="decimal"
                            title="水平缩放百分比，100 = 自动碰撞框原宽"
                            :value="draftValue('colScaleX', collisionScaleX)"
                            @focus="selectOnFocus"
                            @input="onFieldDraft('colScaleX', $event)"
                            @blur="clearDraft('colScaleX')"
                            @change="onCollisionScaleChange(0, $event)"
                          />
                          <!-- X 缩放被改动过才显示 -->
                          <button
                            class="att-reset"
                            :class="{ 'is-dirty': collisionScaleXDirty }"
                            type="button"
                            :disabled="!collisionScaleXDirty"
                            title="重置水平缩放（回到 100%）"
                            @click="resetCollisionAxis('scaleX')"
                          >
                            <img :src="iconReset" alt="" />
                          </button>
                        </div>
                      </div>
                      <div class="att-axis-row">
                        <div class="att-axis-field">
                          <span class="att-axis-tag is-y">Y</span>
                          <input
                            class="att-input att-input-no-spin"
                            type="text"
                            inputmode="decimal"
                            title="垂直缩放百分比，100 = 自动碰撞框原高"
                            :value="draftValue('colScaleY', collisionScaleY)"
                            @focus="selectOnFocus"
                            @input="onFieldDraft('colScaleY', $event)"
                            @blur="clearDraft('colScaleY')"
                            @change="onCollisionScaleChange(1, $event)"
                          />
                          <button
                            class="att-reset"
                            :class="{ 'is-dirty': collisionScaleYDirty }"
                            type="button"
                            :disabled="!collisionScaleYDirty"
                            title="重置垂直缩放（回到 100%）"
                            @click="resetCollisionAxis('scaleY')"
                          >
                            <img :src="iconReset" alt="" />
                          </button>
                        </div>
                      </div>
                      <div class="att-axis-row att-axis-lock">
                        <label class="att-checkbox" title="勾选时 X / Y 同步缩放">
                          <input
                            type="checkbox"
                            :checked="collisionScaleLocked"
                            @change="onCollisionScaleLockChange($event)"
                          />
                        </label>
                        <span class="att-checkbox-text">约束比例</span>
                      </div>
                    </div>
                  </div>

                  <!-- 旋转：滑条内嵌在数字框底部；现阶段仅保存设置，运行时暂未接入 -->
                  <div class="att-row att-row-stacked has-reset">
                    <span class="att-label">旋转</span>
                    <div class="att-slider-field" ref="colAngleFieldEl">
                      <input
                        class="att-input att-input-no-spin"
                        type="text"
                        inputmode="decimal"
                        title="逆时针为正（现阶段保存设置，运行时暂未接入）"
                        :value="draftValue('colAngle', collisionAngleValue)"
                        @focus="selectOnFocus"
                        @input="onFieldDraft('colAngle', $event)"
                        @blur="clearDraft('colAngle')"
                        @change="onCollisionAngleInput"
                      />
                      <span class="att-axis-unit is-degree" :style="collisionAngleUnitStyle()">°</span>
                      <input
                        class="att-range"
                        type="range"
                        min="-180"
                        max="180"
                        step="1"
                        :value="collisionAngleValue"
                        @input="onCollisionAngleInput"
                      />
                      <button
                        class="att-reset"
                        :class="{ 'is-dirty': collisionAngleDirty }"
                        type="button"
                        :disabled="!collisionAngleDirty"
                        title="重置旋转（回到 0°）"
                        @click="resetCollisionAxis('angle')"
                      >
                        <img :src="iconReset" alt="" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>

      <!-- 属性页：未选中标记时显示角色检视器；选中标记后整页内容切换为「标记管理」 -->
      <div v-else class="props-scroll">
        <div class="att-frame">
          <template v-if="!(canAnno && selMarkerName)">
          <!-- 基础设置：名称（可改） / 尺寸 / 图层 / 翻转 -->
          <div class="att-group">
            <div class="mi-section" :class="{ open: propFold.basic }">
              <button class="mi-head" type="button" @click="propFold.basic = !propFold.basic">
                <img :src="iconChevron" class="mi-chevron" alt="" />
                <span class="mi-head-title">基础设置</span>
              </button>
              <div v-if="propFold.basic" class="mi-body">
                <div class="att-row">
                  <span class="att-label">图像名称</span>
                  <input
                    v-model="spriteNameDraft"
                    class="att-input"
                    title="角色图像名称，改完按回车或点别处生效"
                    @blur="commitSpriteRename"
                    @keydown.enter="($event.target as HTMLInputElement).blur()"
                    @keydown.escape="spriteNameDraft = spriteDisplayName"
                  />
                </div>
                <!-- 画布尺寸：只读信息（.bsf 用画布尺寸，图片角色用当前帧内容框） -->
                <div class="att-row">
                  <span class="att-label">画布尺寸</span>
                  <div class="att-size-group">
                    <div class="att-axis-field">
                      <span class="att-axis-tag is-x">X</span>
                      <input
                        class="att-input att-input-no-spin"
                        type="number"
                        :value="spriteSize.w"
                        readonly
                        tabindex="-1"
                        title="画布尺寸，由素材画面决定"
                      />
                    </div>
                    <div class="att-axis-field">
                      <span class="att-axis-tag is-y">Y</span>
                      <input
                        class="att-input att-input-no-spin"
                        type="number"
                        :value="spriteSize.h"
                        readonly
                        tabindex="-1"
                        title="画布尺寸，由素材画面决定"
                      />
                    </div>
                  </div>
                </div>
                <!-- 图层设置：数字越大越靠前；下面几项是角色级开关 -->
                  <div class="att-row">
                    <span class="att-label">图层设置</span>
                    <div class="att-size-group">
                      <input
                        class="att-input att-input-no-spin"
                        type="number"
                        step="1"
                        title="数字越大越靠前（可填负数垫底）；同一层按创建顺序，后创建的在上面"
                        :value="spriteLayer"
                        :disabled="!currentSprite?.bsf"
                        @change="onLayerChange"
                      />
                    </div>
                  </div>
                  <!-- 翻转模式：与 set_rotation_mode() 的三种旋转模式一致（写入数据，游戏里创建角色时生效） -->
                  <div class="att-row">
                    <span class="att-label">翻转模式</span>
                    <CustomSelect
                      class="att-select"
                      :model-value="rotationModeValue"
                      :options="ROTATION_MODE_OPTIONS"
                      @update:model-value="onRotationModeSelect"
                    />
                  </div>
                  <div class="att-row">
                    <span class="att-label">初始隐藏</span>
                    <label class="att-checkbox" title="勾选后角色刚创建时看不见（代码里 show() 再出现），适合先藏起来的角色">
                      <input
                        type="checkbox"
                        :checked="spriteHidden"
                        :disabled="!currentSprite?.bsf"
                        @change="onHiddenChange"
                      />
                    </label>
                  </div>
                  <div class="att-row">
                    <span class="att-label">受到重力</span>
                    <label class="att-checkbox" title="关闭后不受地图重力影响，不会向下掉落；撞墙、落地等碰撞不受影响（适合子弹、飞行敌人）">
                      <input
                        type="checkbox"
                        :checked="gravityEnabled"
                        :disabled="!currentSprite?.bsf"
                        @change="onGravityChange"
                      />
                    </label>
                  </div>
                  <div class="att-row">
                    <span class="att-label">Y轴排序</span>
                    <label class="att-checkbox" title="同一图层内按脚底高度排序：越靠下方的角色盖住上方的角色（适合俯视/横版场景的遮挡）">
                      <input
                        type="checkbox"
                        :checked="spriteYSort"
                        :disabled="!currentSprite?.bsf"
                        @change="onYSortChange"
                      />
                    </label>
                  </div>
              </div>
            </div>
          </div>

          <!-- 变换：位置 / 缩放 / 旋转 / 重置（独立分区，默认展开） -->
          <div class="att-group">
            <div class="mi-section" :class="{ open: propFold.transform }">
              <button class="mi-head" type="button" @click="propFold.transform = !propFold.transform">
                <img :src="iconChevron" class="mi-chevron" alt="" />
                <span class="mi-head-title">变换</span>
              </button>
              <div v-if="propFold.transform" class="mi-body">
                <!-- 位置：X / Y 分两行，X 红、Y 绿（与画布坐标轴颜色一致） -->
                <div class="att-row att-row-stacked has-reset">
                  <span class="att-label">位置</span>
                  <div class="att-axis-group">
                    <div class="att-axis-row">
                      <div class="att-axis-field has-unit" ref="xFieldEl">
                        <span class="att-axis-tag is-x">X</span>
                        <input
                          class="att-input att-input-no-spin"
                          type="text"
                          inputmode="decimal"
                          title="相对默认出生位置的水平偏移（向右为正）"
                          :value="draftValue('x', sceneTransform.x)"
                          @focus="selectOnFocus"
                          @input="onFieldDraft('x', $event)"
                          @blur="clearDraft('x')"
                          @change="onTransformInput('x', $event)"
                        />
                        <span class="att-axis-unit" :style="axisUnitStyleFor('x', sceneTransform.x)">px</span>
                        <!-- X 被改动过才显示：单独重置水平位置 -->
                        <button
                          class="att-reset"
                          :class="{ 'is-dirty': xDirty }"
                          type="button"
                          :disabled="!xDirty"
                          title="重置 X（回到 0）"
                          @click="resetTransformAxis('x')"
                        >
                          <img :src="iconReset" alt="" />
                        </button>
                      </div>
                    </div>
                    <div class="att-axis-row">
                      <div class="att-axis-field has-unit" ref="yFieldEl">
                        <span class="att-axis-tag is-y">Y</span>
                        <input
                          class="att-input att-input-no-spin"
                          type="text"
                          inputmode="decimal"
                          title="相对默认出生位置的垂直偏移（向上为正）"
                          :value="draftValue('y', sceneTransform.y)"
                          @focus="selectOnFocus"
                          @input="onFieldDraft('y', $event)"
                          @blur="clearDraft('y')"
                          @change="onTransformInput('y', $event)"
                        />
                        <span class="att-axis-unit" :style="axisUnitStyleFor('y', sceneTransform.y)">px</span>
                        <!-- Y 被改动过才显示：单独重置垂直位置 -->
                        <button
                          class="att-reset"
                          :class="{ 'is-dirty': yDirty }"
                          type="button"
                          :disabled="!yDirty"
                          title="重置 Y（回到 0）"
                          @click="resetTransformAxis('y')"
                        >
                          <img :src="iconReset" alt="" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- 缩放：X / Y 两行（百分比，100 = 原尺寸）；取消「约束比例」可分别设置 -->
                <div class="att-row att-row-stacked has-reset">
                  <span class="att-label">缩放</span>
                  <div class="att-axis-group">
                    <div class="att-axis-row">
                      <div class="att-axis-field">
                        <span class="att-axis-tag is-x">X</span>
                        <input
                          class="att-input att-input-no-spin"
                          type="text"
                          inputmode="decimal"
                          title="水平缩放百分比，100 = 原尺寸"
                          :value="draftValue('scaleX', scaleXValue)"
                          @focus="selectOnFocus"
                          @input="onFieldDraft('scaleX', $event)"
                          @blur="clearDraft('scaleX')"
                          @change="onScaleInput('x', $event)"
                        />
                        <!-- X 缩放被改动过才显示 -->
                        <button
                          class="att-reset"
                          :class="{ 'is-dirty': scaleXDirty }"
                          type="button"
                          :disabled="!scaleXDirty"
                          title="重置水平缩放（回到 100%）"
                          @click="resetTransformAxis('scaleX')"
                        >
                          <img :src="iconReset" alt="" />
                        </button>
                      </div>
                    </div>
                    <div class="att-axis-row">
                      <div class="att-axis-field">
                        <span class="att-axis-tag is-y">Y</span>
                        <input
                          class="att-input att-input-no-spin"
                          type="text"
                          inputmode="decimal"
                          title="垂直缩放百分比，100 = 原尺寸"
                          :value="draftValue('scaleY', scaleYValue)"
                          @focus="selectOnFocus"
                          @input="onFieldDraft('scaleY', $event)"
                          @blur="clearDraft('scaleY')"
                          @change="onScaleInput('y', $event)"
                        />
                        <!-- Y 缩放被改动过才显示 -->
                        <button
                          class="att-reset"
                          :class="{ 'is-dirty': scaleYDirty }"
                          type="button"
                          :disabled="!scaleYDirty"
                          title="重置垂直缩放（回到 100%）"
                          @click="resetTransformAxis('scaleY')"
                        >
                          <img :src="iconReset" alt="" />
                        </button>
                      </div>
                    </div>
                    <div class="att-axis-row att-axis-lock">
                      <label class="att-checkbox" title="勾选时 X / Y 同步变化；取消后可分别设置宽高比例">
                        <input type="checkbox" :checked="scaleLink" @change="onScaleLinkChange" />
                      </label>
                      <span class="att-checkbox-text">约束比例</span>
                    </div>
                  </div>
                </div>

                <!-- 旋转：滑条内嵌在数字框底部（Godot 风格），数值仍可直接输入 -->
                <div class="att-row att-row-stacked has-reset">
                  <span class="att-label">旋转</span>
                  <div class="att-slider-field" ref="angleFieldEl">
                    <input
                      class="att-input att-input-no-spin"
                      type="text"
                      inputmode="decimal"
                      title="逆时针为正"
                      :value="draftValue('angle', sceneTransform.angle)"
                      @focus="selectOnFocus"
                      @input="onFieldDraft('angle', $event)"
                      @blur="clearDraft('angle')"
                      @change="onTransformInput('angle', $event)"
                    />
                    <!-- 角度单位：紧跟数字后面 -->
                    <span
                      class="att-axis-unit is-degree"
                      :style="angleUnitStyle(sceneTransform.angle)"
                    >°</span>
                    <input
                      class="att-range"
                      type="range"
                      min="-180"
                      max="180"
                      step="1"
                      :value="sceneTransform.angle"
                      @input="onTransformInput('angle', $event)"
                    />
                    <!-- 旋转被改动后才显示：一键回到 0° -->
                    <button
                      class="att-reset"
                      :class="{ 'is-dirty': rotationDirty }"
                      type="button"
                      :disabled="!rotationDirty"
                      title="重置旋转（回到 0°）"
                      @click="resetTransformAxis('angle')"
                    >
                      <img :src="iconReset" alt="" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- 中心点（所有工具共用同一页） -->
          <div class="att-group">
            <div class="mi-section" :class="{ open: propFold.pivot }">
              <button class="mi-head" type="button" @click="propFold.pivot = !propFold.pivot">
                <img :src="iconChevron" class="mi-chevron" alt="" />
                <span class="mi-head-title">中心点</span>
              </button>
              <div v-if="propFold.pivot" class="mi-body">
                <template v-if="canAnno">
                  <div class="att-row att-row-stacked has-reset">
                    <span class="att-label">位置</span>
                    <div class="att-axis-group">
                      <div class="att-axis-row">
                        <div class="att-axis-field has-unit" ref="pivotXFieldEl">
                          <span class="att-axis-tag is-x">X</span>
                          <input
                            class="att-input att-input-no-spin"
                            type="text"
                            inputmode="decimal"
                            title="相对素材原始中心点的左右偏移：0 = 没动过，正数向右"
                            :value="annoPivotOffset ? draftValue('px', annoPivotOffset.x) : ''"
                            @focus="selectOnFocus"
                            @input="onFieldDraft('px', $event)"
                            @blur="clearDraft('px')"
                            @change="onCoordChange('x', $event)"
                          />
                          <span class="att-axis-unit" :style="annoPivotOffset ? pivotUnitStyle('px', annoPivotOffset.x) : {}">px</span>
                          <!-- X 被改动过才显示：单独重置水平偏移 -->
                          <button
                            class="att-reset"
                            :class="{ 'is-dirty': pivotXDirty }"
                            type="button"
                            :disabled="!pivotXDirty"
                            title="重置 X（回到素材原始位置）"
                            @click="resetPivotAxis('x')"
                          >
                            <img :src="iconReset" alt="" />
                          </button>
                        </div>
                      </div>
                      <div class="att-axis-row">
                        <div class="att-axis-field has-unit" ref="pivotYFieldEl">
                          <span class="att-axis-tag is-y">Y</span>
                          <input
                            class="att-input att-input-no-spin"
                            type="text"
                            inputmode="decimal"
                            title="相对素材原始中心点的上下偏移：0 = 没动过，正数向下"
                            :value="annoPivotOffset ? draftValue('py', annoPivotOffset.y) : ''"
                            @focus="selectOnFocus"
                            @input="onFieldDraft('py', $event)"
                            @blur="clearDraft('py')"
                            @change="onCoordChange('y', $event)"
                          />
                          <span class="att-axis-unit" :style="annoPivotOffset ? pivotUnitStyle('py', annoPivotOffset.y) : {}">px</span>
                          <!-- Y 被改动过才显示：单独重置垂直偏移 -->
                          <button
                            class="att-reset"
                            :class="{ 'is-dirty': pivotYDirty }"
                            type="button"
                            :disabled="!pivotYDirty"
                            title="重置 Y（回到素材原始位置）"
                            @click="resetPivotAxis('y')"
                          >
                            <img :src="iconReset" alt="" />
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="att-row">
                    <span class="att-label">作用范围</span>
                    <CustomSelect
                      class="att-select"
                      :model-value="annoScope"
                      :options="SCOPE_OPTIONS"
                      @update:model-value="onScopeSelect"
                    />
                  </div>
                  <div class="mi-actions">
                    <button class="mi-btn" type="button" @click="applyPivotPreset('center')">中心</button>
                    <button class="mi-btn" type="button" @click="applyPivotPreset('feet')">脚底</button>
                    <button
                      v-if="hasPivotOverride(annoFrameIndex)"
                      class="mi-btn"
                      type="button"
                      @click="clearPivotOverride"
                    >恢复统一</button>
                  </div>
                </template>
                <div v-else class="mi-list-empty">单图角色保存标注后会自动转为 .bsf，之后才能编辑中心点。</div>
              </div>
            </div>
          </div>

          </template>

          <!-- 标记页：选中标记后属性页整体切换到这里（三个可折叠分区） -->
          <template v-if="canAnno && selMarkerName">
            <div class="att-group">
              <!-- 标记信息 -->
              <div class="mi-section" :class="{ open: propFold.markerInfo }">
                <button class="mi-head" type="button" @click="propFold.markerInfo = !propFold.markerInfo">
                  <img :src="iconChevron" class="mi-chevron" alt="" />
                  <span class="mi-head-title">标记信息</span>
                </button>
                <div v-if="propFold.markerInfo" class="mi-body">
                  <div class="att-row">
                    <span class="att-label">名称</span>
                    <input
                      ref="markerNameInputEl"
                      v-model="markerNameDraft"
                      class="att-input"
                      title="标记名称"
                      @focus="selectOnFocus"
                      @blur="commitMarkerRename"
                      @keydown.enter="($event.target as HTMLInputElement).blur()"
                      @keydown.escape="cancelMarkerRename"
                    />
                  </div>
                  <div class="att-row">
                    <span class="att-label">类型</span>
                    <CustomSelect
                      class="att-select"
                      :model-value="selMarkerType"
                      :options="markerTypeSelectOptions"
                      @update:model-value="onMarkerTypeSelect"
                    />
                  </div>
                  <div v-if="markerTypeEditing" class="att-row">
                    <span class="att-label"></span>
                    <input
                      ref="markerTypeInputEl"
                      v-model="markerTypeDraft"
                      class="att-input"
                      placeholder="输入自定义类型"
                      @focus="selectOnFocus"
                      @blur="commitMarkerTypeDraft"
                      @keydown.enter="($event.target as HTMLInputElement).blur()"
                    />
                  </div>
                  <div class="att-row att-row-stacked">
                    <span class="att-label">位置</span>
                    <div class="att-axis-group">
                      <div class="att-axis-row">
                        <div class="att-axis-field">
                          <span class="att-axis-tag is-x">X</span>
                          <input
                            class="att-input att-input-no-spin"
                            type="number"
                            step="0.5"
                            :value="selMarkerPos ? selMarkerPos.x.toFixed(1) : ''"
                            @change="onMarkerCoordChange('x', $event)"
                          />
                        </div>
                      </div>
                      <div class="att-axis-row">
                        <div class="att-axis-field">
                          <span class="att-axis-tag is-y">Y</span>
                          <input
                            class="att-input att-input-no-spin"
                            type="number"
                            step="0.5"
                            :value="selMarkerPos ? selMarkerPos.y.toFixed(1) : ''"
                            @change="onMarkerCoordChange('y', $event)"
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                  <div class="att-row">
                    <span class="att-label">作用范围</span>
                    <CustomSelect
                      class="att-select"
                      :model-value="annoScope"
                      :options="SCOPE_OPTIONS"
                      @update:model-value="onScopeSelect"
                    />
                  </div>
                </div>
              </div>

              <!-- 显示与锁定 -->
              <div class="mi-section" :class="{ open: propFold.markerDisplay }">
                <button class="mi-head" type="button" @click="propFold.markerDisplay = !propFold.markerDisplay">
                  <img :src="iconChevron" class="mi-chevron" alt="" />
                  <span class="mi-head-title">显示与锁定</span>
                </button>
                <div v-if="propFold.markerDisplay" class="mi-body">
                  <div class="att-row">
                    <span class="att-label">显示</span>
                    <label class="att-checkbox" title="关闭后画布上不显示这个标记，但仍可在管理列表里找到并修改">
                      <input
                        type="checkbox"
                        :checked="markerFlag(selMarkerName, 'visible')"
                        @change="onMarkerFlagChange('visible', $event)"
                      />
                    </label>
                  </div>
                  <div class="att-row">
                    <span class="att-label">名称</span>
                    <label class="att-checkbox" title="图钉下方的标签是否显示标记名字">
                      <input
                        type="checkbox"
                        :checked="markerFlag(selMarkerName, 'showLabel')"
                        @change="onMarkerFlagChange('showLabel', $event)"
                      />
                    </label>
                  </div>
                  <div class="att-row">
                    <span class="att-label">坐标</span>
                    <label class="att-checkbox" title="图钉下方的标签是否显示坐标">
                      <input
                        type="checkbox"
                        :checked="markerFlag(selMarkerName, 'showCoords')"
                        @change="onMarkerFlagChange('showCoords', $event)"
                      />
                    </label>
                  </div>
                  <div class="att-row">
                    <span class="att-label">锁定</span>
                    <label class="att-checkbox" title="锁定后图钉只能点选查看，不能拖动位置">
                      <input
                        type="checkbox"
                        :checked="markerFlag(selMarkerName, 'locked')"
                        @change="onMarkerFlagChange('locked', $event)"
                      />
                    </label>
                  </div>
                </div>
              </div>

              <!-- 标记管理：类型筛选 + 标记列表 + 复制 / 删除 -->
              <div class="mi-section" :class="{ open: propFold.markerList }">
                <button class="mi-head" type="button" @click="propFold.markerList = !propFold.markerList">
                  <img :src="iconChevron" class="mi-chevron" alt="" />
                  <span class="mi-head-title">标记管理</span>
                  <span class="mi-count">{{ filteredMarkerNames.length }}</span>
                </button>
                <div v-if="propFold.markerList" class="mi-body">
                  <div class="att-row">
                    <span class="att-label">标记类型</span>
                    <CustomSelect
                      class="att-select"
                      :model-value="markerTypeFilter"
                      :options="markerTypeFilterOptions"
                      @update:model-value="v => (markerTypeFilter = v)"
                    />
                  </div>
                  <div v-if="filteredMarkerNames.length" class="mi-list">
                    <button
                      v-for="name in filteredMarkerNames"
                      :key="name"
                      class="mi-list-row"
                      :class="{ 'is-selected': name === selMarkerName }"
                      type="button"
                      @click="selectMarker(name)"
                    >
                      <span class="mi-list-dot"></span>
                      <span class="mi-list-name">{{ name }}</span>
                      <span class="mi-list-coord">{{ markerCoordText(effMarker(name, annoFrameIndex)) }}</span>
                    </button>
                  </div>
                  <div v-else class="mi-list-empty">这个类型下没有标记。</div>
                  <div class="mi-actions">
                    <button class="mi-btn" type="button" @click="duplicateMarker(selMarkerName)">复制</button>
                    <button class="mi-btn mi-btn-danger" type="button" @click="deleteMarker(selMarkerName)">删除</button>
                    <button
                      v-if="hasMarkerOverride(selMarkerName, annoFrameIndex)"
                      class="mi-btn"
                      type="button"
                      @click="clearMarkerOverride"
                    >恢复统一</button>
                  </div>
                </div>
              </div>
            </div>
          </template>

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

<style scoped src="./SpriteEditorView.css"></style>
