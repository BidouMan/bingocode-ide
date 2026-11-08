<script setup lang="ts">
import { ref, reactive, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useResourceStore } from '../../stores/resource'
import { useEditorStore } from '../../stores/editor'
import { useProjectStore } from '../../stores/project'
import { invoke } from '@tauri-apps/api/core'
import type { SpriteData, SpriteAnimation, SpriteTransform } from '../../composables/useSpriteData'
import { readSpriteFromPath, revokeSpriteUrls, saveSpriteConfig, saveBsfManifest, isImageSpritePath, buildSingleFrameBsfMeta, imageSpriteToBsfDir, loadImage, DEFAULT_SPRITE_TRANSFORM, imageContentBox } from '../../composables/useSpriteData'
import type { SpriteCollisionShape } from '../../composables/useSpriteData'
import { appendFramesToSprite } from '../../composables/appendSpriteFrames'
import { useFrameReorder } from '../../composables/useFrameReorder'
import { useSpriteHistory } from './useSpriteHistory'
import { cssImageRendering } from '../../utils/renderMode'
import { drawImageCrisp } from '../../utils/pixelCanvas'
import FrameUploadDrawer from './FrameUploadDrawer.vue'
import CollisionShapeOverlay from './CollisionShapeOverlay.vue'
// 下拉框复用地图编辑器属性面板的自绘组件，保证两个编辑器的控件样式一致
import CustomSelect from '../common/CustomSelect.vue'

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
const projectStore = useProjectStore()
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

/** 翻转模式在编辑器里的预览效果：按画布/预览图自身中心镜像，与游戏创建时的朝向一致 */
const flipPreviewStyle = computed(() => {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return {}
  const sx = bsf.flipX ? -1 : 1
  const sy = bsf.flipY ? -1 : 1
  if (sx === 1 && sy === 1) return {}
  return { transform: `scale(${sx}, ${sy})` }
})

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

/** 改名提交：先迁移磁盘路径（目录角色整体改名，图片角色保留扩展名），成功后再改显示名 */
async function commitSpriteRename() {
  const sprite = currentSprite.value
  const id = currentSpriteId.value
  const item = id ? resourceStore.sprites.find(s => s.id === id) : null
  if (!sprite || !item) return
  const val = spriteNameDraft.value.trim()
  const oldName = item.name
  if (!val) { spriteNameDraft.value = oldName; return }
  if (val === oldName) return

  let newPath: string | null = null
  const base = projectStore.root ? `${projectStore.root}/assets/sprites` : ''
  if (base) {
    try {
      const oldDir = `${base}/${oldName}`
      if (await invoke<boolean>('path_exists', { path: oldDir })) {
        await invoke('rename_path', { oldPath: oldDir, newPath: `${base}/${val}` })
        newPath = `${base}/${val}`
      } else {
        for (const ext of ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']) {
          const oldFile = `${base}/${oldName}${ext}`
          if (await invoke<boolean>('path_exists', { path: oldFile })) {
            await invoke('rename_path', { oldPath: oldFile, newPath: `${base}/${val}${ext}` })
            newPath = `${base}/${val}${ext}`
            break
          }
        }
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
    activeTool.value = 'select'
    cancelMarkerPlacing()
    annoDefaultPivot.value = currentSprite.value.bsf
      ? { ...currentSprite.value.bsf.pivot }
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
  // 标记放置：左键点一下就在鼠标处落点并退出放置（点已有标记时由标记手柄拦截，不会误加）
  if (e.button === 0 && markerPlacing.value) {
    const p = screenToCanvas(e) ?? ghostPoint
    if (p) {
      addMarker(p)
      cancelMarkerPlacing()
    }
  }
}

function onCanvasMouseMove(e: MouseEvent) {
  if (isPanning.value) {
    canvasPanX.value = panStartOffsetX.value + (e.clientX - panStartX.value)
    canvasPanY.value = panStartOffsetY.value + (e.clientY - panStartY.value)
    return
  }
  const p = screenToCanvas(e)
  // 放置中的幽灵图钉跟随鼠标（直接改 DOM 样式，不触发整页重渲染）
  if (markerPlacing.value) {
    if (p) {
      ghostPoint = p
      applyGhostPosition()
    }
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
 * 场景对象锚点（画布坐标）= 当前帧包围盒中心。
 * 角色在场景里以「视觉中心」摆放/旋转/缩放，选中框四周对称、正中心正好落在坐标轴上；
 * 角色自身的中心点（pivot）只作为游戏内注册点，由「中心」工具单独显示与编辑。
 */
const objectAnchor = computed<{ x: number; y: number }>(() => {
  const b = displayFrameBounds.value
  if (b && b.w > 0 && b.h > 0) return { x: b.x + b.w / 2, y: b.y + b.h / 2 }
  return spritePivot.value
})

/** 世界原点在场景视口中的屏幕位置 */
const originScreen = computed(() => ({
  x: viewSize.value.w / 2 + canvasPanX.value,
  y: viewSize.value.h / 2 + canvasPanY.value,
}))

/** 网格步长（世界像素）：保证屏幕上不小于 8px，随缩放自适应 1/2/4/8/16… */
function gridStepWorld(zoom: number): number {
  let step = 1
  while (step * zoom < 8) step *= 2
  return step
}

const sceneGridStyle = computed(() => {
  const z = canvasZoom.value
  const step = gridStepWorld(z)
  const minor = step * z
  const major = minor * 8
  const ox = originScreen.value.x
  const oy = originScreen.value.y
  const minorLineH = 'linear-gradient(to right, rgba(255,255,255,0.045) 1px, transparent 1px)'
  const minorLineV = 'linear-gradient(to bottom, rgba(255,255,255,0.045) 1px, transparent 1px)'
  const majorLineH = 'linear-gradient(to right, rgba(255,255,255,0.09) 1px, transparent 1px)'
  const majorLineV = 'linear-gradient(to bottom, rgba(255,255,255,0.09) 1px, transparent 1px)'
  return {
    backgroundImage: `${minorLineH}, ${minorLineV}, ${majorLineH}, ${majorLineV}`,
    backgroundSize: `${minor}px ${minor}px, ${minor}px ${minor}px, ${major}px ${major}px, ${major}px ${major}px`,
    backgroundPosition: `${ox}px ${oy}px, ${ox}px ${oy}px, ${ox}px ${oy}px, ${ox}px ${oy}px`,
  }
})

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

/** 单位定位依赖输入框实际宽度：跟随面板缩放实时更新 */
const unitFieldWidth = reactive({ x: 0, y: 0, angle: 0 })
const xFieldEl = ref<HTMLElement | null>(null)
const yFieldEl = ref<HTMLElement | null>(null)
const angleFieldEl = ref<HTMLElement | null>(null)
let unitResizeObserver: ResizeObserver | null = null

function observeUnitFields() {
  if (typeof ResizeObserver === 'undefined') return
  unitResizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      const el = entry.target as HTMLElement
      const width = entry.contentRect.width
      if (el === xFieldEl.value) unitFieldWidth.x = width
      else if (el === yFieldEl.value) unitFieldWidth.y = width
      else if (el === angleFieldEl.value) unitFieldWidth.angle = width
    }
  })
  for (const el of [xFieldEl.value, yFieldEl.value, angleFieldEl.value]) {
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

const gizmoVisible = computed(() => activeTool.value === 'select' && !!currentSprite.value)

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
const activeTool = ref<'select' | 'pivot' | 'collision' | 'marker'>('select')

/** 右侧面板标签页：动画（预览 + 片段）/ 属性（角色检视器，配合工具栏当前工具） */
const RIGHT_TAB_KEY = 'bingo-ide-sprite-right-tab'
function readSavedRightTab(): 'animation' | 'props' {
  try {
    return localStorage.getItem(RIGHT_TAB_KEY) === 'props' ? 'props' : 'animation'
  } catch {
    return 'animation' // 首次进入默认「动画」页
  }
}
const rightTab = ref<'animation' | 'props'>(readSavedRightTab())

/** 工具条切换工具：同时把右侧面板切到「属性」页——该工具的详细设置都在那里 */
function pickTool(tool: 'select' | 'pivot' | 'collision' | 'marker') {
  activateCanvasTool(tool)
  rightTab.value = 'props'
}

/** 工具条「动画」：只切右侧面板到「动画」页，不改变画布当前工具 */
function pickAnimation() {
  rightTab.value = 'animation'
}

/** 属性面板分区折叠状态：与地图编辑器检视器一致的可折叠分区，默认全部展开 */
const propFold = ref({
  basic: true,
  transform: true,
  pivot: true,
  collision: true,
  marker: true,
  markerDetail: true,
})

/** 属性面板下拉选项：与地图编辑器属性面板共用 CustomSelect，选项统一在脚本里定义 */
const SCOPE_OPTIONS = [
  { label: '全部帧', value: 'all' },
  { label: '仅当前帧', value: 'one' },
]

const FLIP_MODE_OPTIONS = [
  { label: '不翻转', value: 'none' },
  { label: '水平翻转', value: 'h' },
  { label: '垂直翻转', value: 'v' },
  { label: '水平 + 垂直', value: 'hv' },
]

/** 翻转模式下拉的当前值（把 flipX / flipY 两个开关合并成一个选项） */
const flipModeValue = computed(() => {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return 'none'
  if (bsf.flipX && bsf.flipY) return 'hv'
  if (bsf.flipX) return 'h'
  if (bsf.flipY) return 'v'
  return 'none'
})

function onFlipModeSelect(v: string) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  if (v === 'h' || v === 'hv') bsf.flipX = true
  else delete bsf.flipX
  if (v === 'v' || v === 'hv') bsf.flipY = true
  else delete bsf.flipY
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

/** 属性面板「碰撞类型」下拉的当前值：null（自动碰撞）显示为 auto */
const collisionTypeValue = computed(() => effCol.value?.type ?? 'auto')

/** 属性面板「碰撞类型」切换：自动 = 清空自定义碰撞，其余按类型转换 */
function onCollisionTypeSelect(value: string) {
  if (value === 'auto') resetCollisionToAuto()
  else convertCollisionType(value as 'rect' | 'capsule' | 'polygon')
}

/** 禁用碰撞：整角色不参与地形/边界物理阻挡（碰撞形状保留，重新勾选即恢复） */
const collisionDisabled = computed(() => !!currentSprite.value?.bsf?.collisionDisabled)

function onCollisionDisabledChange(e: Event) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  bsf.collisionDisabled = (e.target as HTMLInputElement).checked
  scheduleSave()
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

function activateCanvasTool(layer: 'select' | 'pivot' | 'collision' | 'marker') {
  // 幽灵图钉只在标记图层有效，切到别的图层先退出放置
  if (layer !== 'marker') cancelMarkerPlacing()
  activeTool.value = layer
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
    if (!currentSprite.value?.bsf) return
    // 只切换工具页：没有选中项时落到第一个标记，右侧改名/删除按钮不至于凭空消失。
    // 放置标记由此面板里的「添加标记」按钮负责，避免同一个按钮既切页又进入放置、语义冲突
    if (!selMarkerName.value || !markerNames.value.includes(selMarkerName.value)) {
      selMarkerName.value = markerNames.value[0] ?? null
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

/** 属性面板标记列表：坐标文本（整数像素，与场景信息栏一致） */
function markerCoordText(name: string): string {
  const p = effMarker(name, annoFrameIndex.value)
  return p ? `${Math.round(p.x)}, ${Math.round(p.y)}` : '—'
}

function markerHandleStyle(name: string) {
  const p = effMarker(name, annoFrameIndex.value)
  return p ? { left: `${p.x}px`, top: `${p.y}px` } : { display: 'none' }
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

function onMarkerCoordChange(axis: 'x' | 'y', e: Event) {
  const v = Number((e.target as HTMLInputElement).value)
  const cur = selMarkerPos.value
  if (!selMarkerName.value || !cur || !Number.isFinite(v)) return
  setMarkerPos(selMarkerName.value, axis === 'x' ? { x: v, y: cur.y } : { x: cur.x, y: v })
}

/** 当前帧内容框中心（放置幽灵图钉的默认落点） */
function frameContentCenter(): { x: number; y: number } | null {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return null
  const f = bsf.frames[annoFrameIndex.value]
  return f
    ? { x: Math.round(f.offset.x + f.rect.w / 2), y: Math.round(f.offset.y + f.rect.h / 2) }
    : { x: Math.round(bsf.canvas.w / 2), y: Math.round(bsf.canvas.h / 2) }
}

/** 新增标记：唯一命名 标记 / 标记1 / 标记2 / ...；不传坐标时落在当前帧内容框中心 */
function addMarker(at?: { x: number; y: number }) {
  const bsf = currentSprite.value?.bsf
  if (!bsf) return
  if (!bsf.markers) bsf.markers = {}
  const existing = new Set(markerNames.value)
  let name = '标记'
  let n = 1
  while (existing.has(name)) { name = `标记${n}`; n++ }
  const pos = at ?? frameContentCenter()
  if (!pos) return
  bsf.markers[name] = { x: pos.x, y: pos.y }
  selMarkerName.value = name
  scheduleSave()
}

// ====== 标记放置：点「添加标记」后，半透明图钉跟随鼠标，点一下落点并退出 ======
const markerPlacing = ref(false)
/** 幽灵图钉的 DOM：位置直接改 style，不走响应式，避免鼠标一动整页重渲染、图钉 SVG 反复重建导致闪烁 */
const markerGhostEl = ref<HTMLDivElement | null>(null)
/** 最近一次的落点（画布坐标，普通变量即可） */
let ghostPoint: { x: number; y: number } | null = null

/** 把幽灵图钉挪到最近落点（首次挂载时顺便显示出来） */
function applyGhostPosition() {
  const el = markerGhostEl.value
  if (!el || !ghostPoint) return
  // 用 transform 移动（合成层内平移），不触发每帧重排/重绘，避免跟随鼠标时闪烁
  el.style.transform = `translate3d(${ghostPoint.x}px, ${ghostPoint.y}px, 0)`
  el.style.opacity = '0.55'
}

function startMarkerPlacing() {
  if (!currentSprite.value?.bsf) return
  markerPlacing.value = true
  ghostPoint = ghostPoint ?? frameContentCenter()
  // 等幽灵图钉挂载到 DOM 后再写样式，避免先在左上角闪一下
  nextTick(applyGhostPosition)
}

function cancelMarkerPlacing() {
  markerPlacing.value = false
  ghostPoint = null
}

/** 「添加标记」按钮：再点一次可取消放置 */
function toggleMarkerPlacing() {
  if (markerPlacing.value) cancelMarkerPlacing()
  else startMarkerPlacing()
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
  // 点已有标记时退出放置，避免误加新点
  if (markerPlacing.value) cancelMarkerPlacing()
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

// ── 变换手柄拖拽：移动 / 等比缩放 / 旋转 ──

function normalizeAngle(a: number): number {
  const n = (((a + 180) % 360) + 360) % 360 - 180
  return Math.round((Math.abs(n) === 180 ? 180 : n) * 10) / 10
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
    t.x = Math.round(d.start.x + dx)
    t.y = Math.round(d.start.y + dy)
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

// 记住用户最后一次的场景缩放（切换角色 / 重新进入角色编辑器时沿用）
watch(canvasZoom, z => saveSceneZoom(z))

// 记住用户最后停留的右侧面板页（首次进入默认「动画」页）
watch(rightTab, tab => {
  try {
    localStorage.setItem(RIGHT_TAB_KEY, tab)
  } catch {
    // localStorage 不可用时忽略
  }
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
  if (e.key === 'Escape' && markerPlacing.value) cancelMarkerPlacing()
  if (e.key === 'Escape' && gizmoDrag.value) cancelGizmoDrag()
  // 空格临时平移（输入框里敲空格不拦截；不 preventDefault，避免抢掉按钮的键盘激活）
  if (e.code === 'Space' && !isTypingTarget(e.target)) {
    spaceHeld.value = true
    return
  }
  // 输入框里的按键留给输入框（原生撤销/重做、F 输入文字都不能被抢走）
  if (isTypingTarget(e.target)) return

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
          :class="{ active: activeTool === 'marker' }"
          type="button"
          @click="pickTool('marker')"
        >
          <img :src="iconMarker" class="layer-chip-icon" alt="" />标记
        </button>
        <!-- 详细设置集中在右侧「属性」面板：随当前工具联动 -->
      </div>

      <div
        ref="canvasRef"
        class="sprite-canvas scene-viewport"
        :class="{
          'is-panning': isPanning,
          'is-marker-placing': markerPlacing,
          'is-space-ready': spaceHeld && !isPanning,
        }"
        @wheel.prevent="onCanvasWheel"
        @mousedown="onCanvasMouseDown"
        @mousemove="onCanvasMouseMove"
        @mouseup="onCanvasMouseUp"
        @dblclick="resetCanvas"
      >
        <!-- 无限网格 + 世界原点轴（类似地图编辑器的工作区，不画舞台边界） -->
        <div class="scene-grid" :style="sceneGridStyle"></div>
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
              :style="{ imageRendering: imageRenderingStyle, ...frameCanvasStyle, ...flipPreviewStyle }"
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
                v-if="activeTool === 'collision'"
                :canvas-w="currentSprite.bsf.canvas.w"
                :canvas-h="currentSprite.bsf.canvas.h"
                :shape="collisionDisplay"
                :zoom="displayZoom"
                :angle="sceneTransform.angle"
                :disabled="collisionDisabled"
                @update="onCollisionUpdate"
              />
              <!-- 放置中的幽灵图钉：位置由 JS 直接改 style（不参与响应式，鼠标移动不会闪烁） -->
              <div
                v-if="markerPlacing"
                ref="markerGhostEl"
                class="marker-handle is-ghost"
              >
                <div class="marker-visual" :style="{ transform: `scale(${1 / displayZoom}) rotate(${sceneTransform.angle}deg)` }">
                  <div class="marker-icon" v-html="markerIconSvg"></div>
                  <span class="marker-label">新标记</span>
                </div>
              </div>
              <!-- 标记手柄：标记.svg 图钉（图标配色独立于 svg 填充，mask 上色），画布点选/拖拽 -->
              <div
                v-for="name in (activeTool === 'marker' ? markerNames : [])"
                :key="name"
                class="marker-handle"
                :class="{
                  'is-selected': name === selMarkerName,
                  'is-override': hasMarkerOverride(name, annoFrameIndex),
                }"
                :style="markerHandleStyle(name)"
                @mousedown="onMarkerMouseDown(name, $event)"
              >
                <div class="marker-visual" :style="{ transform: `scale(${1 / displayZoom}) rotate(${sceneTransform.angle}deg)` }">
                  <div class="marker-icon" v-html="markerIconSvg"></div>
                  <span class="marker-label">{{ name }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 变换手柄（屏幕空间：手柄尺寸恒定，不随场景缩放变形） -->
        <div class="scene-gizmo-layer" :style="sceneGizmoLayerStyle">
          <div
            v-if="gizmoVisible"
            class="gizmo-root"
            :style="gizmoRootStyle"
            @mousedown.stop
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
              title="旋转中心：中心点"
            ></div>
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

    <!-- 右: 面板（动画 / 属性 两页切换，272px） -->
    <div class="preview-panel">
      <div class="right-tabs">
        <button
          class="right-tab"
          :class="{ active: rightTab === 'animation' }"
          type="button"
          @click="rightTab = 'animation'"
        >动画</button>
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
              :style="{ imageRendering: imageRenderingStyle, ...flipPreviewStyle }"
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
      </template>

      <!-- 属性页：所有分区放在同一页（排版对齐地图编辑器属性面板） -->
      <div v-else class="props-scroll">
        <div class="att-frame">
          <!-- 基础设置：名称（可改） / 尺寸 / 图层 / 翻转 -->
          <div class="att-group">
            <div class="mi-section" :class="{ open: propFold.basic }">
              <button class="mi-head" type="button" @click="propFold.basic = !propFold.basic">
                <img :src="iconChevron" class="mi-chevron" alt="" />
                <span class="mi-head-title">基础设置</span>
              </button>
              <div v-if="propFold.basic" class="mi-body">
                <div class="att-row">
                  <span class="att-label">名称</span>
                  <input
                    v-model="spriteNameDraft"
                    class="att-input"
                    title="角色名称，改完按回车或点别处生效"
                    @blur="commitSpriteRename"
                    @keydown.enter="($event.target as HTMLInputElement).blur()"
                    @keydown.escape="spriteNameDraft = spriteDisplayName"
                  />
                </div>
                <!-- 尺寸：只读信息（.bsf 用画布尺寸，图片角色用当前帧内容框） -->
                <div class="att-row">
                  <span class="att-label">尺寸</span>
                  <div class="att-size-group">
                    <div class="att-axis-field">
                      <span class="att-axis-tag">X</span>
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
                      <span class="att-axis-tag">Y</span>
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
                  <!-- 翻转模式：默认朝向与镜像（写入数据，游戏里创建角色时生效） -->
                  <div class="att-row">
                    <span class="att-label">翻转模式</span>
                    <CustomSelect
                      class="att-select"
                      :model-value="flipModeValue"
                      :options="FLIP_MODE_OPTIONS"
                      @update:model-value="onFlipModeSelect"
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
                  <div class="att-row att-row-stacked">
                    <span class="att-label">位置</span>
                    <div class="att-axis-group">
                      <div class="att-axis-row">
                        <div class="att-axis-field">
                          <span class="att-axis-tag">X</span>
                          <input
                            class="att-input att-input-no-spin"
                            type="number"
                            step="0.5"
                            :value="annoPivot ? annoPivot.x.toFixed(1) : ''"
                            @change="onCoordChange('x', $event)"
                          />
                        </div>
                      </div>
                      <div class="att-axis-row">
                        <div class="att-axis-field">
                          <span class="att-axis-tag">Y</span>
                          <input
                            class="att-input att-input-no-spin"
                            type="number"
                            step="0.5"
                            :value="annoPivot ? annoPivot.y.toFixed(1) : ''"
                            @change="onCoordChange('y', $event)"
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
                  <div class="mi-actions">
                    <button class="mi-btn" type="button" @click="applyPivotPreset('center')">中心</button>
                    <button class="mi-btn" type="button" @click="applyPivotPreset('feet')">脚底</button>
                  </div>
                  <div class="mi-actions">
                    <button class="mi-btn" type="button" @click="resetAnno">重置</button>
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

          <!-- 碰撞（所有工具共用同一页） -->
          <div class="att-group">
            <div class="mi-section" :class="{ open: propFold.collision }">
              <button class="mi-head" type="button" @click="propFold.collision = !propFold.collision">
                <img :src="iconChevron" class="mi-chevron" alt="" />
                <span class="mi-head-title">碰撞</span>
              </button>
              <div v-if="propFold.collision" class="mi-body">
                <template v-if="canAnno">
                  <div class="att-row">
                    <span class="att-label">类型</span>
                    <CustomSelect
                      class="att-select"
                      :model-value="collisionTypeValue"
                      :options="COLLISION_TYPE_OPTIONS"
                      @update:model-value="onCollisionTypeSelect"
                    />
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
                  <div class="att-row">
                    <span class="att-label">禁用碰撞</span>
                    <label class="att-checkbox" title="关闭后不参与物理：不会被墙壁、地面挡住，也无法站在地上">
                      <input type="checkbox" :checked="collisionDisabled" @change="onCollisionDisabledChange" />
                    </label>
                  </div>
                  <div v-if="hasCollisionOverride(annoFrameIndex)" class="mi-actions">
                    <button class="mi-btn" type="button" @click="clearCollisionOverride">恢复统一</button>
                  </div>
                </template>
                <div v-else class="mi-list-empty">单图角色保存标注后会自动转为 .bsf，之后才能编辑碰撞。</div>
              </div>
            </div>
          </div>

          <!-- 标记（所有工具共用同一页） -->
          <div class="att-group">
            <div class="mi-section" :class="{ open: propFold.marker }">
              <button class="mi-head" type="button" @click="propFold.marker = !propFold.marker">
                <img :src="iconChevron" class="mi-chevron" alt="" />
                <span class="mi-head-title">标记</span>
                <span v-if="canAnno && markerNames.length" class="mi-count">{{ markerNames.length }}</span>
              </button>
              <div v-if="propFold.marker" class="mi-body">
                <template v-if="canAnno">
                  <div class="mi-actions">
                    <button
                      class="mi-btn"
                      type="button"
                      :class="{ 'is-on': markerPlacing }"
                      title="点一下进入放置，再在画布上点一下放好标记"
                      @click="toggleMarkerPlacing"
                    >{{ markerPlacing ? '点击画布放置…' : '添加标记' }}</button>
                  </div>
                  <div v-if="markerNames.length" class="mi-list">
                    <button
                      v-for="name in markerNames"
                      :key="name"
                      class="mi-list-row"
                      :class="{ 'is-selected': name === selMarkerName }"
                      type="button"
                      @click="selMarkerName = name"
                    >
                      <span class="mi-list-dot"></span>
                      <span class="mi-list-name">{{ name }}</span>
                      <span class="mi-list-coord">{{ markerCoordText(name) }}</span>
                    </button>
                  </div>
                  <div v-else class="mi-list-empty">还没有标记。点「添加标记」后在画布上点一下放置。</div>
                </template>
                <div v-else class="mi-list-empty">单图角色保存标注后会自动转为 .bsf，之后才能编辑标记。</div>
              </div>
            </div>

            <!-- 选中标记后的详细设置（与地图编辑器「标记检视器」一致的第二个分区） -->
            <div v-if="canAnno && selMarkerName" class="mi-section" :class="{ open: propFold.markerDetail }">
              <button class="mi-head" type="button" @click="propFold.markerDetail = !propFold.markerDetail">
                <img :src="iconChevron" class="mi-chevron" alt="" />
                <span class="mi-head-title">标记设置</span>
              </button>
              <div v-if="propFold.markerDetail" class="mi-body">
                <div class="att-row">
                  <span class="att-label">名称</span>
                  <input
                    v-model="markerNameDraft"
                    class="att-input"
                    title="标记名称"
                    @blur="commitMarkerRename"
                    @keydown.enter="($event.target as HTMLInputElement).blur()"
                    @keydown.escape="cancelMarkerRename"
                  />
                </div>
                <div class="att-row att-row-stacked">
                  <span class="att-label">坐标</span>
                  <div class="att-axis-group">
                    <div class="att-axis-row">
                      <div class="att-axis-field">
                        <span class="att-axis-tag">X</span>
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
                        <span class="att-axis-tag">Y</span>
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
                <div class="mi-actions">
                  <button class="mi-btn mi-btn-danger" type="button" @click="deleteMarker(selMarkerName)">删除标记</button>
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
