<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useMapStore, DEFAULT_CAMERA_SETTINGS, type ShapeKind, type ShapeItem, type TileData } from '../../stores/map'
import { useEditorStore } from '../../stores/editor'
import { useResourceStore } from '../../stores/resource'
import { useMapEditorStore } from '../../stores/mapEditor'
import CustomSelect from '../common/CustomSelect.vue'
import { toUserX, toWorldX, toUserY, toWorldY, toUserAngle, toWorldAngle, toUserDeltaY, toWorldDeltaY } from '../../utils/coords'
import { shapeColorCss, shapeKindLabel } from '../../utils/shapeStyle'
import { useTileAssetImport } from '../../composables/useTileAssetImport'
import iconChevron from '../../assets/icons/right_arrow.svg'
import iconSettings from '../../assets/icons/icon--settings.svg'
import iconCopy from '../../assets/icons/copy.svg'
import iconDelete from '../../assets/icons/选中删除.svg'

defineProps<{
  disabled?: boolean
  /** 顶部已切到「形状」分页时为 true：显示形状检视器 + 形状列表，否则显示地图 / 图层属性 */
  shapePage?: boolean
  /** 顶部已切到「图块」分页时为 true：只显示图块设置（碰撞编辑器在画布下方） */
  tilePage?: boolean
}>()

const emit = defineEmits<{
  /** 属性面板修改了图像变换（位置/旋转/缩放/不透明度） */
  'transform-changed': []
  /** 标记管理里请求把视口居中到某个标记 */
  'focus-marker': [id: string]
  /** 形状列表里请求把视口居中到某个形状 */
  'focus-shape': [id: string]
  /** 图块页里的图块集操作：新建图块集 */
  'new-tileset-group': []
}>()

const mapStore = useMapStore()
const editorStore = useEditorStore()
const resourceStore = useResourceStore()
const mapEditorStore = useMapEditorStore()
const { refitTilesetsToGrid } = useTileAssetImport()

// ====== 场景标记检视器 ======
/** 选中的图钉：选中时属性面板整体切换为该标记的检视器 */
const selectedMarker = computed(() => mapStore.selectedMarker)

/** 名称输入草稿：提交前就能提示重名（store 提交时还会再校验一次） */
const markerNameDraft = ref('')

watch(
  () => [selectedMarker.value?.id, selectedMarker.value?.name],
  ([, name]) => {
    markerNameDraft.value = typeof name === 'string' ? name : ''
  },
  { immediate: true },
)

/** 名称重复会让代码里 get_marker("名字") 有歧义，重复时在面板里提示 */
const markerNameDuplicated = computed(() => {
  const marker = selectedMarker.value
  const text = markerNameDraft.value.trim()
  if (!marker || !text) return false
  return mapStore.mapData.markers.some(item => item.id !== marker.id && item.name === text)
})

/** 检视器分区的折叠状态（Godot / Unity 风格的可折叠分组，默认全展开） */
const markerFold = reactive({ basic: true, display: true, manage: true })

/** 标记管理列表：这张地图上的全部标记 */
const sceneMarkers = computed(() => mapStore.mapData.markers)

/** 类型筛选：默认全部；选项由地图里实际出现的类型生成 */
const MARKER_FILTER_ALL = '__all__'
const markerTypeFilter = ref(MARKER_FILTER_ALL)
const markerFilterOptions = computed(() => {
  const types = new Set<string>()
  for (const item of sceneMarkers.value) if (item.type) types.add(item.type)
  return [
    { label: '全部类型', value: MARKER_FILTER_ALL },
    ...[...types].sort((a, b) => a.localeCompare(b, 'zh-CN')).map(type => ({ label: type, value: type })),
  ]
})

/** 筛选后的列表；选中项被筛掉时仍保持选中，只是暂时看不到 */
const filteredMarkers = computed(() =>
  markerTypeFilter.value === MARKER_FILTER_ALL
    ? sceneMarkers.value
    : sceneMarkers.value.filter(item => item.type === markerTypeFilter.value),
)

// 类型被改名/删除后筛选项消失，自动退回「全部类型」
watch(markerFilterOptions, (options) => {
  if (!options.some(option => option.value === markerTypeFilter.value)) {
    markerTypeFilter.value = MARKER_FILTER_ALL
  }
})

/** 点击管理列表某一行：选中画布上对应的图钉 */
function selectMarkerFromList(id: string) {
  mapEditorStore.setSelectedMarkerId(id)
}

/** 双击管理列表某一行：把视口居中到该标记（大地图快速定位） */
function focusMarkerFromList(id: string) {
  mapEditorStore.setSelectedMarkerId(id)
  emit('focus-marker', id)
}

/** 删除标记后自动落到相邻标记上，管理列表不会因面板关闭而中断 */
function removeMarkerWithNeighbor(id: string) {
  const list = sceneMarkers.value
  const index = list.findIndex(item => item.id === id)
  const next = list[index + 1] ?? list[index - 1]
  mapStore.removeMarker(id)
  if (next) mapEditorStore.setSelectedMarkerId(next.id)
}

function deleteSelectedMarker() {
  const marker = selectedMarker.value
  if (!marker) return
  removeMarkerWithNeighbor(marker.id)
}

// ====== 行内改名（右键菜单里的「重命名」） ======
const renamingMarkerId = ref<string | null>(null)
const renameDraft = ref('')
const renameInputRef = ref<HTMLInputElement | null>(null)

/** 行内输入框的 ref 回调：同时只有一个改名输入框，直接存元素本身 */
function setRenameInput(el: unknown) {
  if (el) renameInputRef.value = el as HTMLInputElement
}

/** 进入改名：展开管理分区并聚焦输入框、全选原名 */
function startMarkerRename(id: string) {
  const marker = sceneMarkers.value.find(item => item.id === id)
  if (!marker) return
  markerFold.manage = true
  mapEditorStore.setSelectedMarkerId(id)
  renamingMarkerId.value = id
  renameDraft.value = marker.name
  nextTick(() => {
    renameInputRef.value?.focus()
    renameInputRef.value?.select()
  })
}

/** 提交改名：去空格，空名或重名时保持原名（store 也会再校验一次） */
function commitMarkerRename(id: string) {
  if (renamingMarkerId.value !== id) return
  const marker = sceneMarkers.value.find(item => item.id === id)
  const text = renameDraft.value.trim()
  if (marker && text && text !== marker.name) mapStore.renameMarker(id, text)
  renamingMarkerId.value = null
  renameDraft.value = ''
}

function cancelMarkerRename() {
  renamingMarkerId.value = null
  renameDraft.value = ''
}

// ====== 列表右键菜单（重命名 / 定位 / 复制 / 显示 / 锁定 / 删除） ======
const markerMenu = ref<{ id: string; x: number; y: number } | null>(null)
const markerMenuRef = ref<HTMLElement | null>(null)

/** 右键菜单对应的标记：标记被删掉时菜单自动失效 */
const menuMarker = computed(() => {
  const menu = markerMenu.value
  if (!menu) return null
  return sceneMarkers.value.find(item => item.id === menu.id) ?? null
})

function openMarkerMenu(id: string, e: MouseEvent) {
  e.preventDefault()
  // 右键同时也选中该行，和文件管理器的习惯一致
  mapEditorStore.setSelectedMarkerId(id)
  markerMenu.value = { id, x: e.clientX, y: e.clientY }
  nextTick(() => clampMarkerMenu())
}

/** 菜单贴边时往回收，避免超出窗口 */
function clampMarkerMenu() {
  const el = markerMenuRef.value
  const menu = markerMenu.value
  if (!el || !menu) return
  const margin = 8
  menu.x = Math.max(margin, Math.min(menu.x, window.innerWidth - el.offsetWidth - margin))
  menu.y = Math.max(margin, Math.min(menu.y, window.innerHeight - el.offsetHeight - margin))
}

type MarkerMenuAction =
  | 'rename'
  | 'focus'
  | 'duplicate'
  | 'toggle-visible'
  | 'toggle-locked'
  | 'delete'

function runMarkerMenu(action: MarkerMenuAction) {
  const marker = menuMarker.value
  markerMenu.value = null
  if (!marker) return
  switch (action) {
    case 'rename':
      startMarkerRename(marker.id)
      break
    case 'focus':
      focusMarkerFromList(marker.id)
      break
    case 'duplicate':
      mapStore.duplicateMarker(marker.id)
      break
    case 'toggle-visible':
      mapStore.setMarkerVisible(marker.id, marker.visible === false)
      break
    case 'toggle-locked':
      mapStore.setMarkerLocked(marker.id, marker.locked !== true)
      break
    case 'delete':
      removeMarkerWithNeighbor(marker.id)
      break
  }
}

/** 点菜单以外的地方关闭（菜单内点击由 click 处理，不能提前关） */
function onWindowPointerDownCloseMenu(e: PointerEvent) {
  if (!markerMenu.value && !tilesetMenu.value) return
  if ((e.target as HTMLElement | null)?.closest('.mi-menu')) return
  markerMenu.value = null
  tilesetMenu.value = null
}

function onWindowKeydownCloseMenu(e: KeyboardEvent) {
  if (e.key !== 'Escape') return
  markerMenu.value = null
  tilesetMenu.value = null
}

onMounted(() => {
  window.addEventListener('pointerdown', onWindowPointerDownCloseMenu)
  window.addEventListener('keydown', onWindowKeydownCloseMenu)
})

onBeforeUnmount(() => {
  window.removeEventListener('pointerdown', onWindowPointerDownCloseMenu)
  window.removeEventListener('keydown', onWindowKeydownCloseMenu)
})

/** 地图 / 图层检视器分区折叠状态（与标记检视器共用同一套外观） */
const fold = reactive({
  map: true,
  scene: true,
  layer: true,
  transform: true,
  tileBasic: true,
  tileTransform: true,
  tileSets: true,
})

/** 标记类型：内置常用的几种，最后一项可输入自定义类型 */
const MARKER_TYPE_PRESETS = [
  { label: '出生点', value: '出生点' },
  { label: '敌人', value: '敌人' },
  { label: '道具', value: '道具' },
  { label: '触发器', value: '触发器' },
  { label: '镜头', value: '镜头' },
  { label: '存档点', value: '存档点' },
]
const CUSTOM_MARKER_TYPE = '自定义'
const markerTypeOptions = [
  ...MARKER_TYPE_PRESETS,
  { label: '自定义…', value: CUSTOM_MARKER_TYPE },
]

/** 正在编辑自定义类型的标记 id（下拉选「自定义」时进入，失焦后提交） */
const customTypeEditingId = ref<string | null>(null)
const customTypeDraft = ref('')

/** 下拉框显示值：自定义编辑中或类型不在预设里，都显示为「自定义」 */
const markerTypeValue = computed(() => {
  const marker = selectedMarker.value
  if (!marker) return '出生点'
  if (customTypeEditingId.value === marker.id) return CUSTOM_MARKER_TYPE
  return MARKER_TYPE_PRESETS.some(item => item.value === marker.type)
    ? marker.type
    : CUSTOM_MARKER_TYPE
})

// 切换标记时退出自定义编辑态，避免把上一个标记的输入带到新标记
watch(
  () => selectedMarker.value?.id,
  () => {
    customTypeEditingId.value = null
    customTypeDraft.value = ''
  },
)

const markerNameInputRef = ref<HTMLInputElement>()

/** 双击图钉后把焦点交给名称输入框（由父组件转调） */
function focusMarkerName() {
  markerNameInputRef.value?.focus()
  markerNameInputRef.value?.select()
}

defineExpose({ focusMarkerName })

/** 名称提交：空名或重名时回填原名 */
function onMarkerRename(e: Event) {
  const marker = selectedMarker.value
  const el = e.target as HTMLInputElement
  if (!marker) return
  if (!mapStore.renameMarker(marker.id, el.value)) el.value = marker.name
  markerNameDraft.value = marker.name
}

/** 名称输入中：同步草稿，重名提示实时出现 */
function onMarkerNameInput(e: Event) {
  markerNameDraft.value = (e.target as HTMLInputElement).value
}

/** 坐标输入：用户坐标 ↔ 世界坐标；空值或非数字回填当前值 */
function onMarkerCoord(axis: 'x' | 'y', e: Event) {
  const marker = selectedMarker.value
  const el = e.target as HTMLInputElement
  if (!marker) return
  const raw = el.value.trim()
  const value = Number(raw)
  if (!raw || !Number.isFinite(value)) {
    el.value = String(Math.round(axis === 'x' ? toUserX(marker.x) : toUserY(marker.y)))
    return
  }
  const user = Math.round(value)
  if (axis === 'x') mapStore.updateMarkerPosition(marker.id, toWorldX(user), marker.y)
  else mapStore.updateMarkerPosition(marker.id, marker.x, toWorldY(user))
  el.value = String(user)
}

/** 类型下拉：选内置类型直接写入；选「自定义」进入输入态，失焦后提交 */
function onMarkerTypeSelect(value: string) {
  const marker = selectedMarker.value
  if (!marker) return
  if (value === CUSTOM_MARKER_TYPE) {
    customTypeEditingId.value = marker.id
    customTypeDraft.value = MARKER_TYPE_PRESETS.some(item => item.value === marker.type)
      ? ''
      : marker.type
    return
  }
  customTypeEditingId.value = null
  customTypeDraft.value = ''
  mapStore.setMarkerType(marker.id, value)
}

/** 自定义类型输入：先存在草稿里，避免中途被空值兜底改成「出生点」 */
function onCustomMarkerTypeInput(e: Event) {
  customTypeDraft.value = (e.target as HTMLInputElement).value
}

/** 自定义类型输入结束：提交去空格后的文字；留空则保持原类型不变 */
function onCustomMarkerTypeBlur(e: Event) {
  const marker = selectedMarker.value
  if (!marker) return
  const text = (e.target as HTMLInputElement).value.trim()
  if (text) mapStore.setMarkerType(marker.id, text)
  customTypeEditingId.value = null
  customTypeDraft.value = ''
}

/** 显示：隐藏后不在地图上画图钉，但代码里仍能取到 */
function onMarkerVisibleChange(e: Event) {
  const marker = selectedMarker.value
  if (!marker) return
  mapStore.setMarkerVisible(marker.id, (e.target as HTMLInputElement).checked)
}

/** 锁定：锁定后图钉不能拖动，仍可选中和改坐标 */
function onMarkerLockedChange(e: Event) {
  const marker = selectedMarker.value
  if (!marker) return
  mapStore.setMarkerLocked(marker.id, (e.target as HTMLInputElement).checked)
}

/** 图钉下方标签：分别控制是否显示名称 / 坐标 */
function onMarkerLabelChange(part: 'name' | 'coord', e: Event) {
  const marker = selectedMarker.value
  if (!marker) return
  mapStore.setMarkerLabelVisible(marker.id, part, (e.target as HTMLInputElement).checked)
}

/** 名称/坐标输入框按回车直接生效并退出编辑 */
function blurPanelInput(e: KeyboardEvent) {
  (e.target as HTMLInputElement).blur()
}

/** 相机 / 下滑的详细参数：点行尾的设置按钮展开，避免和分区折叠重复 */
const showCameraSettings = ref(false)
const showSlopeSettings = ref(false)
/** 图层视差：后续版本实现，先占位展示设置项 */
const showParallaxSettings = ref(false)

const isTileMode = computed(() => mapStore.activeMode === 'tile')
const isShapeMode = computed(() => mapStore.activeMode === 'shape')
const isImageMode = computed(() => mapStore.activeMode === 'image')

// ====== 形状检视器：顶部切到「形状」分页时，和形状列表一起展示 ======
const selectedShapeItem = computed(() => mapStore.activeShape)
const shapeFold = reactive({ basic: true, transform: true, manager: true })
const shapeKindOptions = [
  { label: '碰撞', value: 'solid' },
  { label: '感应', value: 'sensor' },
  { label: '碰撞 + 感应', value: 'both' },
]
const shapeKindValue = computed(() => selectedShapeItem.value?.kind || 'solid')
/** 感应形状没有物理行为：单向碰撞相关控件保留但禁用，避免面板忽隐忽现 */
const shapePhysicsDisabled = computed(() => shapeKindValue.value === 'sensor')

// ====== 单向碰撞（参考 Godot 的 One Way Collision） ======
const shapeOneWayEnabled = computed(() => selectedShapeItem.value?.oneWay === true)
/** 方向四选一，值编码成 "dx,dy"（世界坐标，y 向下） */
const ONE_WAY_DIRECTIONS = [
  { label: '从上方踩住', value: '0,1' },    // 下落时挡住
  { label: '从下方顶住', value: '0,-1' },   // 上升时挡住
  { label: '从左侧挡住', value: '1,0' },    // 向右走时挡住
  { label: '从右侧挡住', value: '-1,0' },   // 向左走时挡住
]
const shapeOneWayDirValue = computed(() => {
  const s = selectedShapeItem.value
  const dx = s?.oneWayDirX ?? 0
  const dy = s?.oneWayDirY ?? 1
  // 归一到四方向：取绝对值大的分量
  if (Math.abs(dx) > Math.abs(dy)) return dx > 0 ? '1,0' : '-1,0'
  return dy < 0 ? '0,-1' : '0,1'
})
const shapeOneWayMarginValue = computed(() => selectedShapeItem.value?.oneWayMargin ?? 0)

function onShapeKindChange(val: string) {
  // 多选时一起改：面板显示的是主选中形状的当前值
  mapStore.updateShapes(selectedShapeIds.value, { kind: val as ShapeKind })
}
function onShapeOneWayToggle(e: Event) {
  mapStore.updateShapes(selectedShapeIds.value, {
    oneWay: (e.target as HTMLInputElement).checked,
  })
}
function onShapeOneWayDirChange(val: string) {
  const [dx, dy] = val.split(',').map(Number)
  mapStore.updateShapes(selectedShapeIds.value, { oneWayDirX: dx, oneWayDirY: dy })
}
function onShapeOneWayMarginInput(e: Event) {
  const raw = Number((e.target as HTMLInputElement).value)
  const margin = Number.isFinite(raw) ? Math.min(8, Math.max(0, raw)) : 0
  mapStore.updateShapes(selectedShapeIds.value, { oneWayMargin: margin })
}

// ====== 形状类型：界面叫「类型」，内部/代码里就是 tag（is_touch 查询用） ======
/** 类型预设：常用玩法分类（按用户确认的顺序） */
const SHAPE_TAG_PRESETS = ['墙体', '地面', '道具', '机关', '危险区']
/** 下拉里的「自定义…」入口 */
const SHAPE_TAG_CUSTOM = '自定义'
/** 当前是否处于「自定义」输入模式（下拉选中自定义时显示输入框） */
const tagCustomMode = ref(false)
watch(() => selectedShapeItem.value?.id, () => { tagCustomMode.value = false })

/** 全图标签统计（包含其它形状层）：代码里 is_touch("标签") 是全局查询，候选也取全图 */
const shapeTagStats = computed(() => {
  const counts = new Map<string, number>()
  for (const layer of mapStore.mapData.layers) {
    if (layer.type !== 'shape') continue
    for (const item of layer.shapes) {
      const tag = (item.tag || '').trim()
      if (tag) counts.set(tag, (counts.get(tag) ?? 0) + 1)
    }
  }
  return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0], 'zh-CN'))
})
/** 本图用过的、不在预设里的标签（旧地图的自定义标签也能在这里选到） */
const shapeTagExtraOptions = computed(() => {
  const used = shapeTagStats.value.map(([tag]) => tag)
  return [...new Set(used)].filter(tag => !SHAPE_TAG_PRESETS.includes(tag))
})
const shapeTagOptions = computed(() => [
  ...SHAPE_TAG_PRESETS.map(tag => ({ label: tag, value: tag })),
  ...shapeTagExtraOptions.value.map(tag => ({ label: tag, value: tag })),
  { label: '自定义…', value: SHAPE_TAG_CUSTOM },
])
/** 下拉当前值；自定义模式下固定显示「自定义」 */
const shapeTagValue = computed(() =>
  tagCustomMode.value ? SHAPE_TAG_CUSTOM : (selectedShapeItem.value?.tag || '').trim(),
)
function onShapeTagSelect(val: string) {
  if (!selectedShapeIds.value.length) return
  if (val === SHAPE_TAG_CUSTOM) {
    tagCustomMode.value = true
    mapStore.updateShapes(selectedShapeIds.value, { tag: '' })
    return
  }
  tagCustomMode.value = false
  mapStore.updateShapes(selectedShapeIds.value, { tag: val })
}
/** 自定义标签输入：输入过程中原样写入（避免中文输入法组字被打断） */
const customShapeTagText = computed(() => selectedShapeItem.value?.tag || '')
function onCustomShapeTagInput(e: Event) {
  mapStore.updateShapes(selectedShapeIds.value, {
    tag: (e.target as HTMLInputElement).value,
  })
}
function onCustomShapeTagBlur(e: Event) {
  const name = (e.target as HTMLInputElement).value.trim()
  mapStore.updateShapes(selectedShapeIds.value, { tag: name || '墙体' })
  if (!name) tagCustomMode.value = false
}

// ====== 形状列表：按类型筛选 + 底部按钮 ======
const SHAPE_KIND_ALL = '__all__'
const shapeKindFilter = ref(SHAPE_KIND_ALL)
const shapeKindFilterOptions = computed(() => [
  { label: '全部类型', value: SHAPE_KIND_ALL },
  ...shapeKindOptions,
])

/** 当前形状层按类型筛选后的列表 */
const listedShapes = computed(() => {
  const list = mapStore.activeShapes
  const filter = shapeKindFilter.value
  if (filter === SHAPE_KIND_ALL) return list
  return list.filter(s => (s.kind || 'solid') === filter)
})

/** 列表卡片名称：没有标签就显示「未命名」 */
function shapeDisplayName(item: ShapeItem) {
  return (item.tag || '').trim() || '未命名'
}

/** 当前选中的形状（支持多选）：点击列表行或画布时按住 Shift / Cmd / Ctrl 追加 */
const selectedShapeIds = computed(() => mapEditorStore.activeShapeIds)

function isShapeSelected(id: string) {
  return selectedShapeIds.value.includes(id)
}
function selectAllShapes() {
  mapEditorStore.setActiveShapeIds(listedShapes.value.map(s => s.id))
}
function clearShapeSelection() {
  mapEditorStore.setActiveShapeIds([])
}

// ====== 碰撞体变换（位置 / 大小 / 旋转） ======
// 碰撞体没有独立的变换节点，点集就是几何本身，所以这里的输入都是直接改写顶点：
// 位置=整体平移，大小=绕整体包围盒中心缩放，旋转=绕包围盒中心旋转
const shapeTransformDisabled = computed(
  () => !selectedShapeItem.value || mapStore.activeLayer?.locked === true,
)

/** 参与变换的碰撞体：多选时一起变（以整体包围盒为参照） */
const transformShapes = computed(() => {
  const ids = new Set(selectedShapeIds.value)
  return mapStore.activeShapes.filter(s => ids.has(s.id))
})

/** 选中碰撞体的整体包围盒（世界坐标）；位置与大小都读它 */
const shapeBox = computed(() => {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const item of transformShapes.value) {
    for (const p of item.points) {
      if (p[0] < minX) minX = p[0]
      if (p[0] > maxX) maxX = p[0]
      if (p[1] < minY) minY = p[1]
      if (p[1] > maxY) maxY = p[1]
    }
  }
  if (!Number.isFinite(minX)) return null
  return { cx: (minX + maxX) / 2, cy: (minY + maxY) / 2, w: maxX - minX, h: maxY - minY }
})

/** 位置显示的是包围盒中心点，按用户坐标（原点左下、y 向上） */
const shapePosX = computed(() =>
  shapeBox.value ? Math.round(toUserX(shapeBox.value.cx)) : 0,
)
const shapePosY = computed(() =>
  shapeBox.value ? Math.round(toUserY(shapeBox.value.cy)) : 0,
)
/** 大小 = 包围盒宽高（像素），保留一位小数：旋转过的碰撞体不再落在整数上 */
const round1 = (n: number) => Math.round(n * 10) / 10
const shapeSizeW = computed(() => (shapeBox.value ? round1(shapeBox.value.w) : 0))
const shapeSizeH = computed(() => (shapeBox.value ? round1(shapeBox.value.h) : 0))
/** 约束比例：勾选后改宽高时另一轴按同一比例跟随 */
const shapeScaleLocked = ref(true)

/** 已旋转角度（度，逆时针为正）：碰撞体本身不存旋转，这里累计「本次选中期间」转过的角度 */
const shapeRotation = ref(0)
watch(() => selectedShapeIds.value.join(','), () => { shapeRotation.value = 0 })

/** 按回调批量改写所有选中碰撞体的顶点 */
function mapShapePoints(fn: (p: number[]) => [number, number]) {
  for (const item of transformShapes.value) {
    mapStore.updateShapePoints(item.id, item.points.map(fn))
  }
}

/** 位置：输入的是包围盒中心点，换算成整体平移量 */
function setShapePosition(axis: 0 | 1, e: Event) {
  const box = shapeBox.value
  const value = Number((e.target as HTMLInputElement).value)
  if (!box || !Number.isFinite(value)) return
  const target = axis === 0 ? toWorldX(value) : toWorldY(value)
  const delta = target - (axis === 0 ? box.cx : box.cy)
  if (!delta) return
  mapShapePoints(p => (axis === 0 ? [p[0] + delta, p[1]] : [p[0], p[1] + delta]))
}

/** 大小：输入的是像素宽/高，绕整体包围盒中心缩放；约束比例时另一轴同步 */
function setShapeSize(axis: 'w' | 'h', e: Event) {
  const box = shapeBox.value
  const value = Number((e.target as HTMLInputElement).value)
  if (!box || !Number.isFinite(value)) return
  const current = axis === 'w' ? box.w : box.h
  // 退化成一条线（宽或高为 0）时无法按比例缩放
  if (current < 0.01) return
  // 最小 1%，避免把碰撞体缩成一条线
  const ratio = Math.max(0.01, Math.abs(value) / current)
  const sx = axis === 'w' || shapeScaleLocked.value ? ratio : 1
  const sy = axis === 'h' || shapeScaleLocked.value ? ratio : 1
  mapShapePoints(p => [
    box.cx + (p[0] - box.cx) * sx,
    box.cy + (p[1] - box.cy) * sy,
  ])
}

/** 旋转：输入用户角度（逆时针为正），按与上次输入的角度差绕包围盒中心旋转 */
function setShapeRotation(e: Event) {
  const box = shapeBox.value
  const value = Number((e.target as HTMLInputElement).value)
  if (!box || !Number.isFinite(value)) return
  const delta = value - shapeRotation.value
  shapeRotation.value = value
  if (!delta) return
  // 世界坐标 y 向下，取负号才是视觉上的逆时针
  const rad = (-delta * Math.PI) / 180
  const cos = Math.cos(rad)
  const sin = Math.sin(rad)
  mapShapePoints(p => {
    const dx = p[0] - box.cx
    const dy = p[1] - box.cy
    return [box.cx + dx * cos - dy * sin, box.cy + dx * sin + dy * cos]
  })
}

// 切换图层 / 重新加载地图时清空选中
watch(
  () => [mapStore.activeLayerIndex, mapStore.mapLoadCount],
  () => { mapEditorStore.setActiveShapeIds([]) },
)

/** 底部按钮作用对象 = 当前多选的形状 */
const actionShapeIds = computed(() => selectedShapeIds.value)
const actionShapes = computed(() => {
  const ids = new Set(actionShapeIds.value)
  return mapStore.activeShapes.filter(s => ids.has(s.id))
})
/** 作用对象全部已禁用时，按钮显示「启用」 */
const actionAllDisabled = computed(
  () => actionShapes.value.length > 0 && actionShapes.value.every(s => s.disabled === true),
)
function toggleActionDisabled() {
  if (!actionShapeIds.value.length) return
  mapStore.updateShapes(actionShapeIds.value, { disabled: !actionAllDisabled.value })
}
function removeActionShapes() {
  if (!actionShapeIds.value.length) return
  mapStore.removeShapes(actionShapeIds.value)
}

/** 点击列表行：普通点击单选；按住 Shift / Cmd / Ctrl 加入或移出多选 */
function selectShapeFromList(id: string, e?: MouseEvent) {
  const additive = !!e && (e.shiftKey || e.metaKey || e.ctrlKey)
  mapEditorStore.selectShape(id, additive)
  mapEditorStore.setShapeTool('select')
}
/** 双击列表行：定位到该形状 */
function focusShapeFromList(id: string) {
  mapEditorStore.setActiveShapeId(id)
  emit('focus-shape', id)
}

// ====== 图像变换（位置 / 旋转 / 缩放） ======
// 位置与旋转按用户坐标显示：原点在地图左下角、y 向上为正、角度逆时针为正；
// 内部仍以世界坐标（左上原点、y 向下）存储，只在显示/输入时换算。
const selectedImage = computed(() => mapStore.selectedImage)
/** 图片中心点的世界坐标：position 存的是左上角，渲染时锚点(0.5)落在中心，旋转也绕中心 */
function imageCenterWorld(img: {
  position?: [number, number]
  width?: number
  height?: number
  scale?: number
  scaleX?: number
  scaleY?: number
} | null | undefined) {
  if (!img) return { x: 0, y: 0 }
  const sx = img.scaleX ?? img.scale ?? 1
  const sy = img.scaleY ?? img.scale ?? 1
  return {
    x: (img.position?.[0] ?? 0) + ((img.width || 0) * sx) / 2,
    y: (img.position?.[1] ?? 0) + ((img.height || 0) * sy) / 2,
  }
}
const imagePosX = computed(() => Math.round(toUserX(imageCenterWorld(selectedImage.value).x)))
const imagePosY = computed(() => Math.round(toUserY(imageCenterWorld(selectedImage.value).y)))
const imageRotation = computed(() =>
  Math.round(toUserAngle(selectedImage.value?.rotation ?? 0) * 10) / 10,
)
/** 缩放按百分比展示（100 = 原尺寸），与不透明度等其它数值的写法保持一致 */
const imageScaleX = computed(() =>
  Math.round((selectedImage.value?.scaleX ?? selectedImage.value?.scale ?? 1) * 100),
)
const imageScaleY = computed(() =>
  Math.round((selectedImage.value?.scaleY ?? selectedImage.value?.scale ?? 1) * 100),
)
// 无选中图像或图层被锁定时不可编辑变换
const transformDisabled = computed(
  () => !selectedImage.value || mapStore.activeLayer?.locked === true,
)

/** 缩放锁定（等比缩放）：勾选后改 X 时 Y 按同一倍率跟随，反之亦然 */
const scaleLocked = ref(true)

/** 位置：输入的是中心点的用户坐标，写回时换算成世界坐标下的左上角 */
function setImagePosition(axis: 0 | 1, e: Event) {
  const img = selectedImage.value
  const value = Number((e.target as HTMLInputElement).value)
  if (!img || !Number.isFinite(value)) return
  const sx = img.scaleX ?? img.scale ?? 1
  const sy = img.scaleY ?? img.scale ?? 1
  const pos = [img.position?.[0] ?? 0, img.position?.[1] ?? 0]
  pos[axis] =
    axis === 0
      ? toWorldX(value) - ((img.width || 0) * sx) / 2
      : toWorldY(value) - ((img.height || 0) * sy) / 2
  img.position = pos
  emit('transform-changed')
}

function setImageRotation(e: Event) {
  const img = selectedImage.value
  const value = Number((e.target as HTMLInputElement).value)
  if (!img || !Number.isFinite(value)) return
  // 输入的是用户角度（逆时针为正），写回前换算成世界角度（顺时针为正）
  img.rotation = toWorldAngle(value)
  emit('transform-changed')
}

/** 缩放：输入的是百分比（100 = 原尺寸），内部换回倍率；锁定等比时另一轴按倍率跟随 */
function applyImageScale(axis: 'x' | 'y', percent: number) {
  const img = selectedImage.value
  if (!img) return
  // 0 会导致矩阵退化，最小保留 1%（负值=镜像）
  const clamped = Math.abs(percent) < 1 ? (percent < 0 ? -1 : 1) : percent
  const value = clamped / 100
  const oldX = img.scaleX ?? img.scale ?? 1
  const oldY = img.scaleY ?? img.scale ?? 1
  const round = (n: number) => Math.round(n * 10000) / 10000
  if (axis === 'x') {
    img.scaleX = value
    img.scale = value
    // 等比锁定：Y 按 X 的倍率同步缩放，保持宽高比
    if (scaleLocked.value && oldX !== 0) img.scaleY = round(oldY * (value / oldX))
  } else {
    img.scaleY = value
    if (scaleLocked.value && oldY !== 0) {
      img.scaleX = round(oldX * (value / oldY))
      img.scale = img.scaleX
    }
  }
  emit('transform-changed')
}

function setImageScale(axis: 'x' | 'y', e: Event) {
  const value = Number((e.target as HTMLInputElement).value)
  if (!Number.isFinite(value)) return
  applyImageScale(axis, value)
}


/** 地图尺寸提交：输入过程中不实时生效，失焦/回车时统一校验后调整，
 *  避免逐字输入（如 40 → 450）触发多次画板重建与内容裁剪 */
function commitMapSize(axis: 'width' | 'height', e: Event) {
  const el = e.target as HTMLInputElement
  const parsed = Number(el.value)
  const current = axis === 'width' ? mapStore.mapData.width : mapStore.mapData.height
  const value = Number.isFinite(parsed) && parsed >= 1 ? Math.round(parsed) : current
  if (value !== current) mapStore.updateMapProperty(axis, value)
  // 非法/空值回填当前合法值，避免输入框与实际地图尺寸不一致
  el.value = String(value)
}

/** 地图尺寸上下箭头：按 1 个单位增减，最小 1，走和手动输入相同的校验 */
function stepMapSize(axis: 'width' | 'height', delta: number) {
  const current = axis === 'width' ? mapStore.mapData.width : mapStore.mapData.height
  const value = Math.round(current) + delta
  if (value >= 1) mapStore.updateMapProperty(axis, value)
}

const shapeCount = computed(() => mapStore.activeShapes.length)
const shapeDisabledCount = computed(
  () => mapStore.activeShapes.filter(p => p.disabled === true).length,
)

/** 图层锁定（与图层列表的锁定按钮同一状态） */
const layerLocked = computed(() => mapStore.activeLayer?.locked === true)
function onLayerLockChange(e: Event) {
  const index = mapStore.activeLayerIndex
  if (index < 0) return
  const locked = (e.target as HTMLInputElement).checked
  if (locked !== layerLocked.value) mapStore.toggleLayerLock(index)
}

/** 显示渲染：等同图层可见性，与图层列表行内的眼睛图标共用一个字段 */
const layerVisible = computed(() => mapStore.activeLayer?.visible !== false)
function onLayerVisibleChange(e: Event) {
  const index = mapStore.activeLayerIndex
  if (index < 0) return
  const visible = (e.target as HTMLInputElement).checked
  if (visible !== layerVisible.value) mapStore.toggleLayerVisibility(index)
}

/** 渲染：游戏运行窗口是否绘制该图层（默认 true，编辑器里始终可见） */
const layerRender = computed(() => mapStore.activeLayer?.render !== false)
function onLayerRenderChange(e: Event) {
  const layer = mapStore.activeLayer
  if (!layer) return
  layer.render = (e.target as HTMLInputElement).checked
}

/** 不透明度：图片图层才有（一张图 = 一个图层），数值即图片自身的 opacity */
const layerOpacityPercent = computed(() => {
  const layer = mapStore.activeLayer
  if (!layer || layer.type !== 'image') return 100
  return Math.round((layer.image?.opacity ?? 1) * 100)
})
const layerCanOpacity = computed(
  () => mapStore.activeLayer?.type === 'image' && mapStore.activeLayer?.locked !== true,
)
function onLayerOpacityInput(e: Event) {
  const layer = mapStore.activeLayer
  if (!layer || layer.type !== 'image') return
  const value = Number((e.target as HTMLInputElement).value)
  if (!Number.isFinite(value)) return
  layer.image.opacity = Math.max(0, Math.min(1, value / 100))
  mapStore.imageRevision++
}

// ====== 相机跟随（勾选后在下发展开设置；运行时由引擎读取） ======
const camera = computed(() => ({ ...DEFAULT_CAMERA_SETTINGS, ...(mapStore.mapData.camera ?? {}) }))
const cameraSmoothingPercent = computed(() => Math.round(camera.value.smoothing * 100))

/**
 * 从项目代码里静态收集可跟随的角色变量名（`变量 = Sprite(...)`，按出现顺序）。
 * 只做正则扫描（面板打开/代码变更时），不执行代码，开销可忽略。
 */
const spriteTargetOptions = computed(() => {
  const names = new Set<string>()
  const scan = (text: string) => {
    if (!text) return
    const re = /^[ \t]*([^\s=#,()[\]{}]+)[ \t]*=[ \t]*Sprite[ \t]*\(/gm
    let match: RegExpExecArray | null
    while ((match = re.exec(text)) !== null) names.add(match[1])
  }
  for (const tab of [...editorStore.gameTabs, ...editorStore.codeTabs]) scan(tab.content)
  for (const item of resourceStore.codes) if (item.content) scan(item.content)
  return [...names].map(name => ({ label: name, value: name }))
})

/** 目标必须始终是存在的角色名：为空/失效时自动取第一个（= 第一个创建的角色） */
watch(
  spriteTargetOptions,
  (options) => {
    if (!camera.value.enabled) return
    const names = options.map(o => o.value)
    if (!names.includes(camera.value.target)) {
      mapStore.updateCameraSettings({ target: names[0] ?? '' })
    }
  },
  { immediate: true },
)

function onCameraEnabledChange(e: Event) {
  const enabled = (e.target as HTMLInputElement).checked
  mapStore.updateCameraSettings({ enabled })
  // 勾选时把目标补成第一个角色；场景里没有任何角色时留空（引擎会安全跳过）
  if (enabled) {
    const names = spriteTargetOptions.value.map(o => o.value)
    if (!names.includes(camera.value.target)) {
      mapStore.updateCameraSettings({ target: names[0] ?? '' })
    }
  }
}
function onCameraTargetChange(val: string) {
  mapStore.updateCameraSettings({ target: val })
}
function onCameraSmoothingChange(e: Event) {
  const value = Number((e.target as HTMLInputElement).value)
  if (!Number.isFinite(value)) return
  mapStore.updateCameraSettings({ smoothing: Math.max(0, Math.min(0.95, value / 100)) })
}
function onCameraOffsetChange(axis: 'x' | 'y', e: Event) {
  const value = Number((e.target as HTMLInputElement).value)
  if (!Number.isFinite(value)) return
  mapStore.updateCameraSettings(axis === 'x' ? { offsetX: value } : { offsetY: value })
}
function onCameraLimitChange(e: Event) {
  mapStore.updateCameraSettings({ limitBounds: (e.target as HTMLInputElement).checked })
}



// ====== 图块模式：选中瓦片/资源的碰撞属性 ======
const selectedTileData = computed(() => {
  if (mapStore.selectedTileIndex < 0) return null
  const layer = mapStore.activeLayer
  if (!layer || layer.type !== 'drawing') return null
  const tileSet = mapStore.getTileSetForResource(mapStore.selectedResource)
  if (!tileSet) return null
  return tileSet.tiles[mapStore.selectedTileIndex] ?? null
})

// ====== 图块基础设置：类型（= 图块 tag）+ 尺寸 ======
const TILE_CATEGORY_CUSTOM = '自定义'
const tileCategoryCustomMode = ref(false)
watch(
  () => [mapStore.activeLayerIndex, mapStore.selectedResourceIndex, mapStore.selectedTileIndex],
  () => { tileCategoryCustomMode.value = false },
)

const tileCategoryStats = computed(() => {
  const counts = new Map<string, number>()
  for (const tileSet of mapStore.mapData.tileSets) {
    for (const tile of tileSet.tiles) {
      const tag = (tile.tag || '').trim()
      if (tag) counts.set(tag, (counts.get(tag) ?? 0) + 1)
    }
  }
  return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0], 'zh-CN'))
})
const tileCategoryExtraOptions = computed(() => {
  const used = tileCategoryStats.value.map(([tag]) => tag)
  return [...new Set(used)].filter(tag => !SHAPE_TAG_PRESETS.includes(tag))
})
const tileCategoryOptions = computed(() => [
  ...SHAPE_TAG_PRESETS.map(tag => ({ label: tag, value: tag })),
  ...tileCategoryExtraOptions.value.map(tag => ({ label: tag, value: tag })),
  { label: '自定义…', value: TILE_CATEGORY_CUSTOM },
])
const tileCategoryValue = computed(() =>
  tileCategoryCustomMode.value
    ? TILE_CATEGORY_CUSTOM
    // 没设过类型时默认按「墙体」显示（与碰撞图层新建时的默认一致）
    : (selectedTileData.value?.tag || '').trim() || '墙体',
)

/** 写入选中图块的类型（没有选中图块时忽略） */
function setSelectedTileCategory(tag: string) {
  for (const target of tileEditTargets.value) {
    mapStore.setTileTag(target.tileSetIndex, target.tileIndex, tag)
  }
}
function onTileCategorySelect(val: string) {
  if (val === TILE_CATEGORY_CUSTOM) {
    tileCategoryCustomMode.value = true
    setSelectedTileCategory('')
    return
  }
  tileCategoryCustomMode.value = false
  setSelectedTileCategory(val)
}
const customTileCategoryText = computed(() => selectedTileData.value?.tag || '')
function onCustomTileCategoryInput(e: Event) {
  setSelectedTileCategory((e.target as HTMLInputElement).value)
}
function onCustomTileCategoryBlur(e: Event) {
  const name = (e.target as HTMLInputElement).value.trim()
  setSelectedTileCategory(name)
  if (!name) tileCategoryCustomMode.value = false
}

/** 作用：碰撞 / 感应 / 碰撞 + 感应（与碰撞图层同一套语义） */
const tileKindOptions = [
  { label: '碰撞', value: 'solid' },
  { label: '感应', value: 'sensor' },
  { label: '碰撞 + 感应', value: 'both' },
]

/** 当前图块所属图块集下标；没有选中图块时为 -1 */
const selectedTileSetIndex = computed(() =>
  mapStore.tileSetIndexOfResource(mapStore.selectedResource),
)

/** 面板要改的图块：调色板里选中的全部优先，没多选时退回当前画笔那一块 */
const tileEditTargets = computed(() => {
  const targets: { tileSetIndex: number; tileIndex: number }[] = []
  const resources = mapStore.activeLayerResources
  for (const sel of mapStore.tileBrushSelection) {
    const resource = resources.find(r => r.id === sel.resourceId)
    if (!resource) continue
    const tileSetIndex = mapStore.tileSetIndexOfResource(resource)
    if (tileSetIndex < 0) continue
    targets.push({ tileSetIndex, tileIndex: sel.tileIndex })
  }
  if (targets.length === 0 && selectedTileSetIndex.value >= 0 && mapStore.selectedTileIndex >= 0) {
    targets.push({
      tileSetIndex: selectedTileSetIndex.value,
      tileIndex: mapStore.selectedTileIndex,
    })
  }
  return targets
})

/** 有可编辑的图块（还没碰撞数据也可以，写入时自动补） */
const tileEditable = computed(() => tileEditTargets.value.length > 0)

const tileKindValue = computed(() => selectedTileData.value?.kind || 'solid')
/** 感应图块没有物理阻挡：单向碰撞控件保留但禁用 */
const tilePhysicsDisabled = computed(() => tileKindValue.value === 'sensor')

const tileOneWayEnabled = computed(() => selectedTileData.value?.oneWay === true)
/** 方向四选一，和碰撞图层共用一份定义 */
const tileOneWayDirValue = computed(() => {
  const tile = selectedTileData.value
  const dx = tile?.oneWayDirX ?? 0
  const dy = tile?.oneWayDirY ?? 1
  if (Math.abs(dx) > Math.abs(dy)) return dx > 0 ? '1,0' : '-1,0'
  return dy < 0 ? '0,-1' : '0,1'
})
const tileOneWayMarginValue = computed(() => selectedTileData.value?.oneWayMargin ?? 0)

function patchSelectedTile(
  patch: Partial<Pick<TileData, 'kind' | 'oneWay' | 'oneWayDirX' | 'oneWayDirY' | 'oneWayMargin'>>,
) {
  // 一次改掉所有选中的图块；面板显示的是最后选中的那一块
  for (const target of tileEditTargets.value) {
    mapStore.updateTile(target.tileSetIndex, target.tileIndex, patch)
  }
}

/** 设置作用 / 单向碰撞时顺带打开碰撞，否则这些设置不生效 */
function ensureTileCollision() {
  for (const target of tileEditTargets.value) {
    mapStore.setTileCollision(target.tileSetIndex, target.tileIndex, true, {
      points: [[0, 0], [1, 0], [1, 1], [0, 1]],
    })
  }
}

function onTileKindChange(val: string) {
  if (!tileEditable.value) return
  ensureTileCollision()
  patchSelectedTile({ kind: val as ShapeKind })
}
function onTileOneWayToggle(e: Event) {
  if (!tileEditable.value) return
  const checked = (e.target as HTMLInputElement).checked
  if (checked) ensureTileCollision()
  patchSelectedTile({ oneWay: checked })
}
function onTileOneWayDirChange(val: string) {
  const [dx, dy] = val.split(',').map(Number)
  patchSelectedTile({ oneWayDirX: dx, oneWayDirY: dy })
}
function onTileOneWayMarginInput(e: Event) {
  const raw = Number((e.target as HTMLInputElement).value)
  const margin = Number.isFinite(raw) ? Math.min(8, Math.max(0, raw)) : 0
  patchSelectedTile({ oneWayMargin: margin })
}

// ====== 碰撞层级（参考 Unity 的 Physics Layers；当前只做界面，尚未接入运行时） ======
/** 勾选后才在下方展开设置 */
const tilePhysicsEnabled = ref(false)
const tileCollisionLayer = ref(1)
const tileCollisionMask = reactive(new Set<number>([1]))
const tilePhysicsMaterialOptions = [
  { label: '默认', value: 'default' },
  { label: '弹性', value: 'bouncy' },
  { label: '粗糙', value: 'friction' },
]

function onTilePhysicsToggle(e: Event) {
  tilePhysicsEnabled.value = (e.target as HTMLInputElement).checked
}

function toggleTileCollisionMask(n: number) {
  if (tileCollisionMask.has(n)) tileCollisionMask.delete(n)
  else tileCollisionMask.add(n)
}

// ====== 变换：整层位移 / 缩放 / 旋转 ======
/** 变换作用在整个图块图层上 */
const activeDrawingLayer = computed(() => {
  const layer = mapStore.activeLayer
  return layer && layer.type === 'drawing' ? layer : null
})
const tileLayerOffsetX = computed(() => Math.round(activeDrawingLayer.value?.offsetX ?? 0))
// 面板显示用户坐标（y 向上），存的是世界坐标（y 向下），位移只翻符号
const tileLayerOffsetY = computed(() => Math.round(toUserDeltaY(activeDrawingLayer.value?.offsetY ?? 0)))
/** 缩放按百分比展示（100 = 原尺寸） */
const tileLayerScaleX = computed(() => Math.round((activeDrawingLayer.value?.scaleX ?? 1) * 100))
const tileLayerScaleY = computed(() => Math.round((activeDrawingLayer.value?.scaleY ?? 1) * 100))
/** 旋转面板显示用户角度（逆时针为正），存的是世界角度（顺时针为正） */
const tileLayerRotation = computed(() =>
  Math.round(toUserAngle(activeDrawingLayer.value?.rotation ?? 0) * 10) / 10,
)
/** 约束比例：勾选后改 X 时 Y 按同一倍率跟随 */
const tileScaleLocked = ref(true)

function onTileLayerOffsetChange(axis: 'x' | 'y', e: Event) {
  const layer = activeDrawingLayer.value
  if (!layer) return
  const raw = Number((e.target as HTMLInputElement).value)
  const value = Number.isFinite(raw) ? Math.round(raw) : 0
  mapStore.setLayerTransform(layer.id, axis === 'x'
    ? { offsetX: value }
    : { offsetY: toWorldDeltaY(value) })
}

/** 缩放：输入百分比，0 会导致矩阵退化，最小保留 1%（负值=镜像） */
function applyTileLayerScale(axis: 'x' | 'y', percent: number) {
  const layer = activeDrawingLayer.value
  if (!layer) return
  const clamped = Math.abs(percent) < 1 ? (percent < 0 ? -1 : 1) : percent
  const value = clamped / 100
  const oldX = layer.scaleX ?? 1
  const oldY = layer.scaleY ?? 1
  const round = (n: number) => Math.round(n * 10000) / 10000
  if (axis === 'x') {
    const patch: { scaleX: number; scaleY?: number } = { scaleX: value }
    if (tileScaleLocked.value && oldX !== 0) patch.scaleY = round(oldY * (value / oldX))
    mapStore.setLayerTransform(layer.id, patch)
  } else {
    const patch: { scaleX?: number; scaleY: number } = { scaleY: value }
    if (tileScaleLocked.value && oldY !== 0) patch.scaleX = round(oldX * (value / oldY))
    mapStore.setLayerTransform(layer.id, patch)
  }
}

function onTileLayerScaleChange(axis: 'x' | 'y', e: Event) {
  const value = Number((e.target as HTMLInputElement).value)
  if (!Number.isFinite(value)) return
  applyTileLayerScale(axis, value)
}

/** 输入的是用户角度（逆时针为正），写回前换算成世界角度 */
function onTileLayerRotationChange(e: Event) {
  const layer = activeDrawingLayer.value
  if (!layer) return
  const value = Number((e.target as HTMLInputElement).value)
  if (!Number.isFinite(value)) return
  mapStore.setLayerTransform(layer.id, { rotation: toWorldAngle(value) })
}

// ====== 图块尺寸 ======
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
  mapStore.updateTileSize(newSize)
  // 已有图块集按新格子重新换算（从导入时的原图出发，避免反复缩放）
  void refitTilesetsToGrid(newSize)
}

/**
 * 图块集列表：每个图块集就是一个独立的资源仓库。
 * 每行 = 状态圆点 + 名称 + 图块尺寸；点某一行即选中该集，左侧资源列表跟着切换。
 */
const tileSetGroups = computed(() => {
  const resources = mapStore.mapData.resources.filter(r => r.resourceType !== 'image')
  const groups = mapStore.mapData.tilesetGroups ?? []
  return groups.map(group => {
    const owned = resources.filter(r => r.groupId === group.id)
    const first = owned[0]
    return {
      id: group.id,
      name: group.name || '图块集合',
      // 图块尺寸取该图块集里第一个素材的切片尺寸，没有素材时按地图格子尺寸显示
      tileWidth: first?.tileWidth ?? mapStore.mapData.tileSize,
      tileHeight: first?.tileHeight ?? mapStore.mapData.tileSize,
      locked: group.locked === true,
      disabled: group.disabled === true,
    }
  })
})

/** 列表中选中的图块集：没选过或选中项被删除时退回第一个 */
const selectedTilesetRow = computed(() =>
  tileSetGroups.value.find(g => g.id === mapStore.selectedTilesetGroupId)
  ?? tileSetGroups.value[0]
  ?? null,
)

/** 列表里选中的图块集不可删除：锁定或全图只剩这一个图块集 */
const canDeleteTileset = computed(() =>
  !!selectedTilesetRow.value
  && !selectedTilesetRow.value.locked
  && tileSetGroups.value.length > 1,
)

/** 选中图块集：左侧资源列表切到该集的资源仓库（不切图层） */
function selectTilesetRow(id: string) {
  mapStore.useTilesetGroupForActiveLayer(id)
}

function onTilesetDelete() {
  const row = selectedTilesetRow.value
  if (!row) return
  mapStore.deleteTilesetGroup(row.id)
}

function onTilesetToggleDisabled() {
  const row = selectedTilesetRow.value
  if (!row || row.locked) return
  mapStore.setTilesetGroupFlags(row.id, { disabled: !row.disabled })
}

/** 复制选中的图块集：分组、图块素材、碰撞和调色板条目一起复制 */
function onTilesetDuplicate() {
  const row = selectedTilesetRow.value
  if (!row) return
  mapStore.duplicateTilesetGroup(row.id)
}

// ====== 图块集行内改名（右键菜单里的「重命名」） ======
const renamingTilesetId = ref<string | null>(null)
const tilesetRenameDraft = ref('')
const tilesetRenameInputRef = ref<HTMLInputElement | null>(null)

function setTilesetRenameInput(el: unknown) {
  if (el) tilesetRenameInputRef.value = el as HTMLInputElement
}

/** 进入改名：展开图块集分区、选中该行并聚焦输入框 */
function startTilesetRename(id: string) {
  const row = tileSetGroups.value.find(g => g.id === id) ?? tileSetGroups.value[0]
  if (!row) return
  fold.tileSets = true
  mapStore.selectTilesetGroup(row.id)
  renamingTilesetId.value = row.id
  tilesetRenameDraft.value = row.name
  nextTick(() => {
    tilesetRenameInputRef.value?.focus()
    tilesetRenameInputRef.value?.select()
  })
}

/** 提交改名：去空格；空名保持原名 */
function commitTilesetRename(id: string) {
  if (renamingTilesetId.value !== id) return
  const text = tilesetRenameDraft.value.trim()
  if (text) mapStore.renameTilesetGroup(id, text)
  renamingTilesetId.value = null
  tilesetRenameDraft.value = ''
}

function cancelTilesetRename() {
  renamingTilesetId.value = null
  tilesetRenameDraft.value = ''
}

// ====== 图块集右键菜单（重命名 / 复制 / 隐藏 / 锁定 / 删除） ======
const tilesetMenu = ref<{ id: string; x: number; y: number } | null>(null)
const tilesetMenuRef = ref<HTMLElement | null>(null)

/** 菜单对应的图块集：行被删掉时菜单自动失效 */
const menuTileset = computed(() => {
  const menu = tilesetMenu.value
  if (!menu) return null
  return tileSetGroups.value.find(g => g.id === menu.id) ?? null
})

function openTilesetMenu(id: string, e: MouseEvent) {
  e.preventDefault()
  // 右键同时也选中该行，和文件管理器的习惯一致
  mapStore.selectTilesetGroup(id)
  tilesetMenu.value = { id, x: e.clientX, y: e.clientY }
  nextTick(() => clampTilesetMenu())
}

/** 菜单贴边时往回收，避免超出窗口 */
function clampTilesetMenu() {
  const el = tilesetMenuRef.value
  const menu = tilesetMenu.value
  if (!el || !menu) return
  const margin = 8
  menu.x = Math.max(margin, Math.min(menu.x, window.innerWidth - el.offsetWidth - margin))
  menu.y = Math.max(margin, Math.min(menu.y, window.innerHeight - el.offsetHeight - margin))
}

type TilesetMenuAction =
  | 'rename'
  | 'duplicate'
  | 'toggle-hidden'
  | 'toggle-locked'
  | 'delete'

function runTilesetMenu(action: TilesetMenuAction) {
  const row = menuTileset.value
  tilesetMenu.value = null
  if (!row) return
  switch (action) {
    case 'rename':
      startTilesetRename(row.id)
      break
    case 'duplicate':
      mapStore.duplicateTilesetGroup(row.id)
      break
    case 'toggle-hidden':
      // 锁定后不能隐藏（与底部「禁用」按钮的规则一致）
      if (!row.locked) mapStore.setTilesetGroupFlags(row.id, { disabled: !row.disabled })
      break
    case 'toggle-locked':
      mapStore.setTilesetGroupFlags(row.id, { locked: !row.locked })
      break
    case 'delete':
      mapStore.deleteTilesetGroup(row.id)
      break
  }
}

</script>

<template>
  <div class="property-panel">
    <!-- 地图属性 -->
    <div class="att-frame">
      <!-- 标记检视器：选中图钉时替代地图 / 图层属性 -->
      <div v-if="selectedMarker" class="att-group marker-inspector">
        <!-- 基本：名称 / 类型 / 坐标 -->
        <div class="mi-section" :class="{ open: markerFold.basic }">
          <button class="mi-head" :disabled="disabled" @click="markerFold.basic = !markerFold.basic">
            <img :src="iconChevron" class="mi-chevron" alt="" />
            <span class="mi-head-title">基本</span>
          </button>
          <div v-if="markerFold.basic" class="mi-body">
            <div class="att-row">
              <span class="att-label">名称</span>
              <div class="att-field">
                <input
                  ref="markerNameInputRef"
                  class="att-input"
                  :class="{ 'att-input-warn': markerNameDuplicated }"
                  :value="selectedMarker?.name"
                  maxlength="20"
                  placeholder="标记名"
                  :disabled="disabled"
                  @input="onMarkerNameInput"
                  @change="onMarkerRename"
                  @keydown.enter="blurPanelInput"
                />
                <span v-if="markerNameDuplicated" class="att-warn">已有同名标记</span>
              </div>
            </div>
            <div class="att-row">
              <span class="att-label">类型</span>
              <CustomSelect
                class="att-select"
                :model-value="markerTypeValue"
                :options="markerTypeOptions"
                :disabled="disabled"
                @update:model-value="onMarkerTypeSelect"
              />
            </div>
            <div v-if="markerTypeValue === CUSTOM_MARKER_TYPE" class="att-row">
              <span class="att-label">类型名</span>
              <input
                class="att-input"
                :value="customTypeDraft"
                maxlength="20"
                placeholder="输入类型名"
                :disabled="disabled"
                @input="onCustomMarkerTypeInput"
                @blur="onCustomMarkerTypeBlur"
                @keydown.enter="blurPanelInput"
              />
            </div>
            <div class="att-row">
              <span class="att-label">位置</span>
              <div class="att-size-group">
                <span class="att-size-label">X</span>
                <input
                  class="att-input att-input-no-spin"
                  type="number"
                  :value="Math.round(toUserX(selectedMarker?.x ?? 0))"
                  :disabled="disabled"
                  @change="onMarkerCoord('x', $event)"
                />
                <span class="att-size-label">Y</span>
                <input
                  class="att-input att-input-no-spin"
                  type="number"
                  :value="Math.round(toUserY(selectedMarker?.y ?? 0))"
                  :disabled="disabled"
                  @change="onMarkerCoord('y', $event)"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- 显示与锁定：直接写入标记，随地图存档 -->
        <div class="mi-section" :class="{ open: markerFold.display }">
          <button class="mi-head" :disabled="disabled" @click="markerFold.display = !markerFold.display">
            <img :src="iconChevron" class="mi-chevron" alt="" />
            <span class="mi-head-title">显示与锁定</span>
          </button>
          <div v-if="markerFold.display" class="mi-body">
            <div class="att-row">
              <span class="att-label">显示</span>
              <label class="att-checkbox">
                <input
                  type="checkbox"
                  :checked="selectedMarker?.visible !== false"
                  :disabled="disabled"
                  @change="onMarkerVisibleChange"
                />
                <span class="att-checkbox-text">在地图上显示</span>
              </label>
            </div>
            <div class="att-row">
              <span class="att-label">名称</span>
              <label class="att-checkbox">
                <input
                  type="checkbox"
                  :checked="selectedMarker?.showName !== false"
                  :disabled="disabled"
                  @change="onMarkerLabelChange('name', $event)"
                />
                <span class="att-checkbox-text">标签显示名称</span>
              </label>
            </div>
            <div class="att-row">
              <span class="att-label">坐标</span>
              <label class="att-checkbox">
                <input
                  type="checkbox"
                  :checked="selectedMarker?.showCoord !== false"
                  :disabled="disabled"
                  @change="onMarkerLabelChange('coord', $event)"
                />
                <span class="att-checkbox-text">标签显示坐标</span>
              </label>
            </div>
            <div class="att-row">
              <span class="att-label">锁定</span>
              <label class="att-checkbox">
                <input
                  type="checkbox"
                  :checked="selectedMarker?.locked === true"
                  :disabled="disabled"
                  @change="onMarkerLockedChange"
                />
                <span class="att-checkbox-text">禁止拖动</span>
              </label>
            </div>
          </div>
        </div>

        <!-- 标记管理：列出这张地图的全部标记，点一行就选中、双击居中、右键调出更多操作 -->
        <div class="mi-section" :class="{ open: markerFold.manage }">
          <button class="mi-head" :disabled="disabled" @click="markerFold.manage = !markerFold.manage">
            <img :src="iconChevron" class="mi-chevron" alt="" />
            <span class="mi-head-title">标记管理</span>
            <span class="mi-count">{{ sceneMarkers.length }}</span>
          </button>
          <div v-if="markerFold.manage" class="mi-body">
            <!-- 类型筛选：默认全部，选项来自本图实际出现的类型 -->
            <CustomSelect
              class="mi-filter"
              :model-value="markerTypeFilter"
              :options="markerFilterOptions"
              :disabled="disabled"
              @update:model-value="markerTypeFilter = $event"
            />
            <div class="mi-list">
              <template v-for="item in filteredMarkers" :key="item.id">
                <!-- 行内改名：右键菜单触发后原地变成输入框 -->
                <div
                  v-if="renamingMarkerId === item.id"
                  class="mi-list-row mi-list-row-edit"
                  :class="{ 'is-selected': item.id === selectedMarker?.id }"
                >
                  <span class="mi-list-dot" />
                  <input
                    :ref="setRenameInput"
                    v-model="renameDraft"
                    class="mi-list-rename"
                    maxlength="20"
                    :disabled="disabled"
                    @keydown.enter.prevent="commitMarkerRename(item.id)"
                    @keydown.esc.prevent="cancelMarkerRename"
                    @blur="commitMarkerRename(item.id)"
                  />
                </div>
                <button
                  v-else
                  class="mi-list-row"
                  :class="{
                    'is-selected': item.id === selectedMarker?.id,
                    'is-hidden': item.visible === false,
                  }"
                  :disabled="disabled"
                  @click="selectMarkerFromList(item.id)"
                  @dblclick="focusMarkerFromList(item.id)"
                  @contextmenu="openMarkerMenu(item.id, $event)"
                >
                  <span class="mi-list-dot" />
                  <span class="mi-list-name">{{ item.name }}</span>
                  <span class="mi-list-coord">{{ Math.round(toUserX(item.x)) }}, {{ Math.round(toUserY(item.y)) }}</span>
                </button>
              </template>
              <div v-if="!filteredMarkers.length" class="mi-list-empty">
                {{ sceneMarkers.length ? '没有这个类型的标记' : '这张地图还没有标记' }}
              </div>
            </div>
            <div class="mi-actions">
              <button
                class="mi-btn"
                :disabled="disabled"
                @click="selectedMarker && mapStore.duplicateMarker(selectedMarker.id)"
              >
                <img :src="iconCopy" alt="" />
                <span>复制</span>
              </button>
              <button
                class="mi-btn mi-btn-danger"
                :disabled="disabled"
                @click="deleteSelectedMarker"
              >
                <img :src="iconDelete" alt="" />
                <span>删除</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <template v-else>
      <!-- 形状页：形状检视器 + 形状列表 -->
      <template v-if="isShapeMode && shapePage">
      <!-- 形状检视器：选中形状时显示在「形状」页顶部 -->
      <div v-if="selectedShapeItem" class="att-group marker-inspector">
        <!-- 基本：能力类型 / 标签 -->
        <div class="mi-section" :class="{ open: shapeFold.basic }">
          <button class="mi-head" :disabled="disabled" @click="shapeFold.basic = !shapeFold.basic">
            <img :src="iconChevron" class="mi-chevron" alt="" />
            <span class="mi-head-title">基本</span>
          </button>
          <div v-if="shapeFold.basic" class="mi-body">
            <div class="att-row">
              <span class="att-label">作用</span>
              <CustomSelect
                class="att-select"
                :model-value="shapeKindValue"
                :options="shapeKindOptions"
                :disabled="disabled"
                @update:model-value="onShapeKindChange"
              />
            </div>
            <!-- 类型：下拉选常用类型；最后一项「自定义…」可以自己输入（内部就是代码查询用的标签名） -->
            <div class="att-row">
              <span class="att-label">类型</span>
              <CustomSelect
                class="att-select"
                :model-value="shapeTagValue"
                :options="shapeTagOptions"
                placeholder="未命名"
                :disabled="disabled"
                @update:model-value="onShapeTagSelect"
              />
            </div>
            <div v-if="tagCustomMode" class="att-row">
              <span class="att-label">类型名</span>
              <input
                class="att-input"
                :value="customShapeTagText"
                maxlength="20"
                placeholder="设置类型名"
                :disabled="disabled"
                @input="onCustomShapeTagInput"
                @blur="onCustomShapeTagBlur"
                @keydown.enter="blurPanelInput"
              />
            </div>
            <!-- 单向碰撞（参考 Godot 的 One Way Collision）：勾选后只从「方向」那一侧挡住 -->
            <div class="att-row">
              <span class="att-label">单向碰撞</span>
              <label class="att-checkbox">
                <input
                  type="checkbox"
                  :checked="shapeOneWayEnabled"
                  :disabled="disabled || shapePhysicsDisabled"
                  @change="onShapeOneWayToggle"
                />
                <span class="att-checkbox-text">启用</span>
              </label>
            </div>
            <template v-if="shapeOneWayEnabled">
              <div class="att-row">
                <span class="att-label">方向</span>
                <CustomSelect
                  class="att-select"
                  :model-value="shapeOneWayDirValue"
                  :options="ONE_WAY_DIRECTIONS"
                  :disabled="disabled || shapePhysicsDisabled"
                  @update:model-value="onShapeOneWayDirChange"
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
                  :value="shapeOneWayMarginValue"
                  :disabled="disabled || shapePhysicsDisabled"
                  @change="onShapeOneWayMarginInput"
                />
              </div>
            </template>
          </div>
        </div>

        <!-- 变换：位置 / 大小 / 旋转，数值直接改写碰撞体顶点 -->
        <div class="mi-section" :class="{ open: shapeFold.transform }">
          <button class="mi-head" :disabled="disabled" @click="shapeFold.transform = !shapeFold.transform">
            <img :src="iconChevron" class="mi-chevron" alt="" />
            <span class="mi-head-title">变换</span>
          </button>
          <div v-if="shapeFold.transform" class="mi-body">
            <!-- 位置：包围盒中心点，X / Y 上下两行 -->
            <div class="att-row att-row-stacked">
              <span class="att-label">位置</span>
              <div class="att-axis-group">
                <div class="att-axis-row">
                  <span class="att-size-label">X</span>
                  <input
                    class="att-input att-input-no-spin"
                    type="number"
                    :value="shapePosX"
                    :disabled="disabled || shapeTransformDisabled"
                    @change="setShapePosition(0, $event)"
                  />
                </div>
                <div class="att-axis-row">
                  <span class="att-size-label">Y</span>
                  <input
                    class="att-input att-input-no-spin"
                    type="number"
                    :value="shapePosY"
                    :disabled="disabled || shapeTransformDisabled"
                    @change="setShapePosition(1, $event)"
                  />
                </div>
              </div>
            </div>

            <!-- 大小：包围盒宽高（像素），绕中心缩放，可勾选约束比例 -->
            <div class="att-row att-row-stacked">
              <span class="att-label">大小</span>
              <div class="att-axis-group">
                <div class="att-axis-row">
                  <span class="att-size-label">宽</span>
                  <input
                    class="att-input att-input-no-spin"
                    type="number"
                    step="1"
                    :value="shapeSizeW"
                    :disabled="disabled || shapeTransformDisabled"
                    @change="setShapeSize('w', $event)"
                  />
                </div>
                <div class="att-axis-row">
                  <span class="att-size-label">高</span>
                  <input
                    class="att-input att-input-no-spin"
                    type="number"
                    step="1"
                    :value="shapeSizeH"
                    :disabled="disabled || shapeTransformDisabled"
                    @change="setShapeSize('h', $event)"
                  />
                </div>
                <div class="att-axis-row att-axis-lock">
                  <span class="att-size-label">约束比例</span>
                  <label class="att-checkbox">
                    <input
                      type="checkbox"
                      v-model="shapeScaleLocked"
                      :disabled="disabled || shapeTransformDisabled"
                    />
                  </label>
                </div>
              </div>
            </div>

            <!-- 旋转：数字框在上、滑条在下（单位是度，不写 °） -->
            <div class="att-row att-row-stacked">
              <span class="att-label">旋转</span>
              <div class="att-axis-group">
                <input
                  class="att-input att-input-no-spin"
                  type="number"
                  step="1"
                  :value="shapeRotation"
                  :disabled="disabled || shapeTransformDisabled"
                  @change="setShapeRotation"
                />
                <input
                  class="att-range"
                  type="range"
                  min="-180"
                  max="180"
                  step="1"
                  :value="shapeRotation"
                  :disabled="disabled || shapeTransformDisabled"
                  @input="setShapeRotation"
                />
              </div>
            </div>
          </div>
        </div>
      </div>
      </template>

      <!-- 属性页 / 其它模式：地图与图层属性（图块页、形状页各自独立） -->
      <template v-if="(!isShapeMode || !shapePage) && (!isTileMode || !tilePage)">
      <div class="att-group">
        <!-- 地图：名称 / 尺寸 -->
        <div class="mi-section" :class="{ open: fold.map }">
          <button class="mi-head" :disabled="disabled" @click="fold.map = !fold.map">
            <img :src="iconChevron" class="mi-chevron" alt="" />
            <span class="mi-head-title">地图</span>
          </button>
          <div v-if="fold.map" class="mi-body">
            <div class="att-row">
              <span class="att-label">地图名称</span>
              <input
                class="att-input"
                :value="mapStore.mapData.name"
                :disabled="disabled"
                @input="mapStore.updateMapProperty('name', ($event.target as HTMLInputElement).value)"
              />
            </div>

            <div class="att-row">
              <span class="att-label">地图尺寸</span>
              <div class="att-size-group">
                <span class="att-size-label">X</span>
                <div class="att-spin">
                  <input
                    class="att-input att-input-no-spin"
                    type="number"
                    min="1"
                    step="1"
                    :value="mapStore.mapData.width"
                    :disabled="disabled"
                    @change="commitMapSize('width', $event)"
                  />
                  <div class="att-spin-btns">
                    <button class="att-spin-btn" :disabled="disabled" @click="stepMapSize('width', 1)">
                      <img :src="iconChevron" class="att-spin-arrow up" alt="增加" />
                    </button>
                    <button class="att-spin-btn" :disabled="disabled" @click="stepMapSize('width', -1)">
                      <img :src="iconChevron" class="att-spin-arrow down" alt="减少" />
                    </button>
                  </div>
                </div>
                <span class="att-size-label">Y</span>
                <div class="att-spin">
                  <input
                    class="att-input att-input-no-spin"
                    type="number"
                    min="1"
                    step="1"
                    :value="mapStore.mapData.height"
                    :disabled="disabled"
                    @change="commitMapSize('height', $event)"
                  />
                  <div class="att-spin-btns">
                    <button class="att-spin-btn" :disabled="disabled" @click="stepMapSize('height', 1)">
                      <img :src="iconChevron" class="att-spin-arrow up" alt="增加" />
                    </button>
                    <button class="att-spin-btn" :disabled="disabled" @click="stepMapSize('height', -1)">
                      <img :src="iconChevron" class="att-spin-arrow down" alt="减少" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 场景：相机跟随 / 重力 / 边界 / 下滑 -->
        <div class="mi-section" :class="{ open: fold.scene }">
          <button class="mi-head" :disabled="disabled" @click="fold.scene = !fold.scene">
            <img :src="iconChevron" class="mi-chevron" alt="" />
            <span class="mi-head-title">场景</span>
          </button>
          <div v-if="fold.scene" class="mi-body">
            <div class="att-row">
              <span class="att-label">相机跟随</span>
              <label class="att-checkbox">
                <input
                  type="checkbox"
                  :checked="camera.enabled"
                  :disabled="disabled"
                  @change="onCameraEnabledChange"
                />
                <span class="att-checkbox-text">{{ camera.enabled ? '启用' : '禁用' }}</span>
              </label>
              <button
                class="att-gear-btn"
                :class="{ active: showCameraSettings }"
                :disabled="disabled"
                title="相机设置"
                @click="showCameraSettings = !showCameraSettings"
              >
                <img :src="iconSettings" alt="相机设置" />
              </button>
            </div>

            <!-- 相机参数：点行尾设置按钮展开；相机未启用时置灰 -->
            <div v-if="showCameraSettings" class="att-subgroup">
              <div class="att-row">
                <span class="att-label">跟随角色</span>
                <CustomSelect
                  class="att-select"
                  :model-value="camera.target"
                  :options="spriteTargetOptions"
                  :disabled="disabled || !camera.enabled || spriteTargetOptions.length === 0"
                  placeholder="暂无角色"
                  @update:model-value="onCameraTargetChange"
                />
              </div>

              <div class="att-row">
                <span class="att-label">平滑跟随</span>
                <input
                  class="att-range"
                  type="range"
                  min="0"
                  max="95"
                  :value="cameraSmoothingPercent"
                  :disabled="disabled || !camera.enabled"
                  @input="onCameraSmoothingChange"
                />
                <span class="att-value">{{ cameraSmoothingPercent }}%</span>
              </div>

              <div class="att-row">
                <span class="att-label">偏移</span>
                <div class="att-size-group">
                  <span class="att-size-label">X</span>
                  <input
                    class="att-input att-input-no-spin"
                    type="number"
                    :value="camera.offsetX"
                    :disabled="disabled || !camera.enabled"
                    @change="onCameraOffsetChange('x', $event)"
                  />
                  <span class="att-size-label">Y</span>
                  <input
                    class="att-input att-input-no-spin"
                    type="number"
                    :value="camera.offsetY"
                    :disabled="disabled || !camera.enabled"
                    @change="onCameraOffsetChange('y', $event)"
                  />
                </div>
              </div>

              <div class="att-row">
                <span class="att-label">边界限制</span>
                <label class="att-checkbox">
                  <input
                    type="checkbox"
                    :checked="camera.limitBounds"
                    :disabled="disabled || !camera.enabled"
                    @change="onCameraLimitChange"
                  />
                  <span class="att-checkbox-text">限制在地图内</span>
                </label>
              </div>
            </div>

            <div class="att-row">
              <span class="att-label">地图重力</span>
              <label class="att-checkbox">
                <input
                  type="checkbox"
                  :checked="mapStore.mapData.gravity"
                  :disabled="disabled"
                  @change="mapStore.updateMapProperty('gravity', ($event.target as HTMLInputElement).checked)"
                />
                <span class="att-checkbox-text">{{ mapStore.mapData.gravity ? '启用' : '禁用' }}</span>
              </label>
            </div>

            <div class="att-row">
              <span class="att-label">限制边界</span>
              <label class="att-checkbox">
                <input
                  type="checkbox"
                  :checked="mapStore.mapData.boundaryCollision"
                  :disabled="disabled"
                  @change="mapStore.updateMapProperty('boundaryCollision', ($event.target as HTMLInputElement).checked)"
                />
                <span class="att-checkbox-text">{{ mapStore.mapData.boundaryCollision ? '启用' : '禁用' }}</span>
              </label>
            </div>

            <div class="att-row">
              <span class="att-label">禁止下滑</span>
              <label class="att-checkbox">
                <input
                  type="checkbox"
                  :checked="mapStore.mapData.stopOnSlope"
                  :disabled="disabled"
                  @change="mapStore.updateMapProperty('stopOnSlope', ($event.target as HTMLInputElement).checked)"
                />
                <span class="att-checkbox-text">{{ mapStore.mapData.stopOnSlope ? '启用' : '禁用' }}</span>
              </label>
              <button
                class="att-gear-btn"
                :class="{ active: showSlopeSettings }"
                :disabled="disabled"
                title="下滑设置"
                @click="showSlopeSettings = !showSlopeSettings"
              >
                <img :src="iconSettings" alt="下滑设置" />
              </button>
            </div>

            <!-- 下滑参数：占位选项，功能后续版本实现
                 参考成熟引擎：坡度上限=Godot floor_max_angle / Unity slopeLimit，
                 下坡贴地=Godot floor_snap_length，坡上匀速=Godot floor_constant_speed -->
            <div v-if="showSlopeSettings" class="att-subgroup">
              <div class="att-row">
                <span class="att-label">坡度上限</span>
                <input class="att-input att-input-no-spin" type="number" value="45" disabled />
                <span class="att-value">度</span>
              </div>

              <div class="att-row">
                <span class="att-label">下滑速度</span>
                <input class="att-range" type="range" min="0" max="100" value="50" disabled />
                <span class="att-value">50%</span>
              </div>

              <div class="att-row">
                <span class="att-label">下坡贴地</span>
                <label class="att-checkbox">
                  <input type="checkbox" checked disabled />
                  <span class="att-checkbox-text">启用</span>
                </label>
              </div>

              <div class="att-row">
                <span class="att-label">坡上匀速</span>
                <label class="att-checkbox">
                  <input type="checkbox" disabled />
                  <span class="att-checkbox-text">禁用</span>
                </label>
              </div>
            </div>
          </div>
        </div>

      </div>

      <!-- 当前图层属性 -->
      <div class="att-group">
        <!-- 图层：锁定与按类型的图层信息 -->
        <div class="mi-section" :class="{ open: fold.layer }">
          <button class="mi-head" :disabled="disabled" @click="fold.layer = !fold.layer">
            <img :src="iconChevron" class="mi-chevron" alt="" />
            <span class="mi-head-title">图层</span>
          </button>
          <div v-if="fold.layer" class="mi-body">
        <div class="att-row">
          <span class="att-label">锁定</span>
          <label class="att-checkbox">
            <input
              type="checkbox"
              :checked="layerLocked"
              :disabled="disabled || mapStore.activeLayerIndex < 0"
              @change="onLayerLockChange"
            />
            <span class="att-checkbox-text">{{ layerLocked ? '启用' : '禁用' }}</span>
          </label>
        </div>

        <div class="att-row">
          <span class="att-label">显示</span>
          <label class="att-checkbox">
            <input
              type="checkbox"
              :checked="layerVisible"
              :disabled="disabled || mapStore.activeLayerIndex < 0"
              @change="onLayerVisibleChange"
            />
            <span class="att-checkbox-text">{{ layerVisible ? '启用' : '禁用' }}</span>
          </label>
        </div>

        <!-- 渲染：游戏运行窗口是否绘制该图层（编辑器里始终可见） -->
        <div class="att-row">
          <span class="att-label">渲染</span>
          <label class="att-checkbox">
            <input
              type="checkbox"
              :checked="layerRender"
              :disabled="disabled || mapStore.activeLayerIndex < 0"
              @change="onLayerRenderChange"
            />
            <span class="att-checkbox-text">{{ layerRender ? '启用' : '禁用' }}</span>
          </label>
        </div>

        <!-- 视差：后续版本实现，先占位，设置项全部灰色不可用 -->
        <div class="att-row">
          <span class="att-label">视差</span>
          <label class="att-checkbox">
            <input type="checkbox" disabled />
            <span class="att-checkbox-text">禁用</span>
          </label>
          <button
            class="att-gear-btn"
            :class="{ active: showParallaxSettings }"
            title="视差设置"
            @click="showParallaxSettings = !showParallaxSettings"
          >
            <img :src="iconSettings" alt="视差设置" />
          </button>
        </div>

        <!-- 视差参数：点行尾设置按钮展开，占位项全部禁用 -->
        <div v-if="showParallaxSettings" class="att-subgroup">
          <div class="att-row">
            <span class="att-label">视差系数</span>
            <div class="att-size-group">
              <span class="att-size-label">X</span>
              <input class="att-input att-input-no-spin" type="number" value="1" disabled />
              <span class="att-size-label">Y</span>
              <input class="att-input att-input-no-spin" type="number" value="1" disabled />
            </div>
          </div>

          <div class="att-row">
            <span class="att-label">跟随相机</span>
            <label class="att-checkbox">
              <input type="checkbox" checked disabled />
              <span class="att-checkbox-text">启用</span>
            </label>
          </div>

          <div class="att-row">
            <span class="att-label">循环滚动</span>
            <label class="att-checkbox">
              <input type="checkbox" disabled />
              <span class="att-checkbox-text">禁用</span>
            </label>
          </div>
        </div>

        <!-- Y 轴排序：按图层内物体脚下位置决定前后遮挡（参考 Godot Y Sort），后续版本实现 -->
        <div class="att-row">
          <span class="att-label">Y 轴排序</span>
          <label class="att-checkbox">
            <input type="checkbox" disabled />
            <span class="att-checkbox-text">禁用</span>
          </label>
        </div>

        <!-- 不透明度：图片图层生效（改的是图片自身透明度），图块/形状层后续版本支持 -->
        <div class="att-row">
          <span class="att-label">不透明度</span>
          <input
            class="att-range"
            type="range"
            min="0"
            max="100"
            step="1"
            :value="layerOpacityPercent"
            :disabled="disabled || !layerCanOpacity"
            @input="onLayerOpacityInput"
          />
          <span class="att-value">{{ layerOpacityPercent }}%</span>
        </div>

        <template v-if="isShapeMode">
          <div class="att-row">
            <span class="att-label">形状数</span>
            <span class="att-value">{{ shapeCount }}</span>
          </div>

          <div class="att-row">
            <span class="att-label">已禁用</span>
            <span class="att-value">{{ shapeDisabledCount }}</span>
          </div>
        </template>
          </div>
        </div>
      </div>

      <!-- 图像变换：位置 / 旋转 / 缩放（不透明度在图层面板的图层属性里） -->
      <div v-if="isImageMode" class="att-group">
        <!-- 变换：图片位置与形态 -->
        <div class="mi-section" :class="{ open: fold.transform }">
          <button class="mi-head" :disabled="disabled" @click="fold.transform = !fold.transform">
            <img :src="iconChevron" class="mi-chevron" alt="" />
            <span class="mi-head-title">变换</span>
          </button>
          <div v-if="fold.transform" class="mi-body">
        <!-- 位置：X / Y 上下两行，输入框左边缘对齐 -->
        <div class="att-row att-row-stacked">
          <span class="att-label">位置</span>
          <div class="att-axis-group">
            <div class="att-axis-row">
              <span class="att-size-label">X</span>
              <input
                class="att-input att-input-no-spin"
                type="number"
                :value="imagePosX"
                :disabled="disabled || transformDisabled"
                @change="setImagePosition(0, $event)"
              />
            </div>
            <div class="att-axis-row">
              <span class="att-size-label">Y</span>
              <input
                class="att-input att-input-no-spin"
                type="number"
                :value="imagePosY"
                :disabled="disabled || transformDisabled"
                @change="setImagePosition(1, $event)"
              />
            </div>
          </div>
        </div>

        <!-- 缩放：X / Y 上下两行，Y 下方单独一行勾选「约束比例」（等比缩放） -->
        <div class="att-row att-row-stacked">
          <span class="att-label">缩放</span>
          <div class="att-axis-group">
            <div class="att-axis-row">
              <span class="att-size-label">X</span>
              <input
                class="att-input att-input-no-spin"
                type="number"
                step="1"
                :value="imageScaleX"
                :disabled="disabled || transformDisabled"
                @change="setImageScale('x', $event)"
              />
            </div>
            <div class="att-axis-row">
              <span class="att-size-label">Y</span>
              <input
                class="att-input att-input-no-spin"
                type="number"
                step="1"
                :value="imageScaleY"
                :disabled="disabled || transformDisabled"
                @change="setImageScale('y', $event)"
              />
            </div>
            <div class="att-axis-row att-axis-lock">
              <span class="att-size-label">约束比例</span>
              <label class="att-checkbox">
                <input
                  type="checkbox"
                  v-model="scaleLocked"
                  :disabled="disabled || transformDisabled"
                />
              </label>
            </div>
          </div>
        </div>

        <!-- 旋转：放最后一行，数字框在上、滑条在下（单位就是度，不写 °） -->
        <div class="att-row att-row-stacked">
          <span class="att-label">旋转</span>
          <div class="att-axis-group">
            <input
              class="att-input att-input-no-spin"
              type="number"
              step="1"
              :value="imageRotation"
              :disabled="disabled || transformDisabled"
              @change="setImageRotation"
            />
            <input
              class="att-range"
              type="range"
              min="-180"
              max="180"
              step="1"
              :value="imageRotation"
              :disabled="disabled || transformDisabled"
              @input="setImageRotation"
            />
          </div>
        </div>
          </div>
        </div>
      </div>
      </template>

      <!-- 图块页：基础设置 / 变换 / 图块集列表 -->
      <template v-if="isTileMode && tilePage">
      <div class="att-group">

        <!-- 基础设置 -->
        <div class="mi-section" :class="{ open: fold.tileBasic }">
          <button class="mi-head" :disabled="disabled" @click="fold.tileBasic = !fold.tileBasic">
            <img :src="iconChevron" class="mi-chevron" alt="" />
            <span class="mi-head-title">基础设置</span>
          </button>
          <div v-if="fold.tileBasic" class="mi-body">
            <div class="att-row">
              <span class="att-label">作用</span>
              <CustomSelect
                class="att-select"
                :model-value="tileKindValue"
                :options="tileKindOptions"
                :disabled="disabled || !tileEditable"
                @update:model-value="onTileKindChange"
              />
            </div>

            <div class="att-row">
              <span class="att-label">类型</span>
              <CustomSelect
                class="att-select"
                :model-value="tileCategoryValue"
                :options="tileCategoryOptions"
                placeholder="未分类"
                :disabled="disabled || !tileEditable"
                @update:model-value="onTileCategorySelect"
              />
            </div>

            <div v-if="tileCategoryCustomMode" class="att-row">
              <span class="att-label">类型名</span>
              <input
                class="att-input"
                :value="customTileCategoryText"
                maxlength="20"
                placeholder="设置类型名"
                :disabled="disabled"
                @input="onCustomTileCategoryInput"
                @blur="onCustomTileCategoryBlur"
                @keydown.enter="blurPanelInput"
              />
            </div>

            <!-- 单向碰撞（参考 Godot 的 One Way Collision）：勾选后只从「方向」那一侧挡住 -->
            <div class="att-row">
              <span class="att-label">单向碰撞</span>
              <label class="att-checkbox">
                <input
                  type="checkbox"
                  :checked="tileOneWayEnabled"
                  :disabled="disabled || !tileEditable || tilePhysicsDisabled"
                  @change="onTileOneWayToggle"
                />
                <span class="att-checkbox-text">启用</span>
              </label>
            </div>
            <template v-if="tileOneWayEnabled">
              <div class="att-row">
                <span class="att-label">方向</span>
                <CustomSelect
                  class="att-select"
                  :model-value="tileOneWayDirValue"
                  :options="ONE_WAY_DIRECTIONS"
                  :disabled="disabled || !tileEditable || tilePhysicsDisabled"
                  @update:model-value="onTileOneWayDirChange"
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
                  :value="tileOneWayMarginValue"
                  :disabled="disabled || !tileEditable || tilePhysicsDisabled"
                  @change="onTileOneWayMarginInput"
                />
              </div>
            </template>

            <!-- 碰撞层级：勾选后在下方展开设置（和单向碰撞一样的内联展开） -->
            <div class="att-row">
              <span class="att-label">碰撞层级</span>
              <label class="att-checkbox">
                <input
                  type="checkbox"
                  :checked="tilePhysicsEnabled"
                  :disabled="disabled"
                  @change="onTilePhysicsToggle"
                />
                <span class="att-checkbox-text">启用</span>
              </label>
            </div>
            <template v-if="tilePhysicsEnabled">
              <div class="layer-block">
                <span class="layer-block-name">碰撞层</span>
                <div class="layer-grid">
                  <button
                    v-for="n in 8"
                    :key="`layer-${n}`"
                    class="layer-cell"
                    :class="{ 'layer-cell-active': tileCollisionLayer === n }"
                    :disabled="disabled"
                    @click="tileCollisionLayer = n"
                  >{{ n }}</button>
                </div>
              </div>

              <div class="layer-block">
                <span class="layer-block-name">碰撞掩码</span>
                <div class="layer-grid">
                  <button
                    v-for="n in 8"
                    :key="`mask-${n}`"
                    class="layer-cell"
                    :class="{ 'layer-cell-active': tileCollisionMask.has(n) }"
                    :disabled="disabled"
                    @click="toggleTileCollisionMask(n)"
                  >{{ n }}</button>
                </div>
              </div>

              <div class="att-row">
                <span class="att-label">碰撞材质</span>
                <CustomSelect
                  class="att-select"
                  model-value="default"
                  :options="tilePhysicsMaterialOptions"
                  disabled
                />
              </div>
            </template>

            <div class="att-row">
              <span class="att-label">图块尺寸</span>
              <CustomSelect
                class="att-select"
                :model-value="tileSizeValue"
                :options="tileSizeOptions"
                :disabled="disabled"
                @update:model-value="onTileSizeChange"
              />
            </div>
          </div>
        </div>

        <!-- 变换：整个图块图层一起位移 / 缩放 / 旋转 -->
        <div class="mi-section" :class="{ open: fold.tileTransform }">
          <button class="mi-head" :disabled="disabled" @click="fold.tileTransform = !fold.tileTransform">
            <img :src="iconChevron" class="mi-chevron" alt="" />
            <span class="mi-head-title">变换</span>
          </button>
          <div v-if="fold.tileTransform" class="mi-body">
            <div class="att-row att-row-stacked">
              <span class="att-label">位置</span>
              <div class="att-axis-group">
                <div class="att-axis-row">
                  <span class="att-size-label">X</span>
                  <input
                    class="att-input att-input-no-spin"
                    type="number"
                    :value="tileLayerOffsetX"
                    :disabled="disabled || !activeDrawingLayer"
                    @change="onTileLayerOffsetChange('x', $event)"
                  />
                </div>
                <div class="att-axis-row">
                  <span class="att-size-label">Y</span>
                  <input
                    class="att-input att-input-no-spin"
                    type="number"
                    :value="tileLayerOffsetY"
                    :disabled="disabled || !activeDrawingLayer"
                    @change="onTileLayerOffsetChange('y', $event)"
                  />
                </div>
              </div>
            </div>

            <div class="att-row att-row-stacked">
              <span class="att-label">缩放</span>
              <div class="att-axis-group">
                <div class="att-axis-row">
                  <span class="att-size-label">X</span>
                  <input
                    class="att-input att-input-no-spin"
                    type="number"
                    step="1"
                    :value="tileLayerScaleX"
                    :disabled="disabled || !activeDrawingLayer"
                    @change="onTileLayerScaleChange('x', $event)"
                  />
                </div>
                <div class="att-axis-row">
                  <span class="att-size-label">Y</span>
                  <input
                    class="att-input att-input-no-spin"
                    type="number"
                    step="1"
                    :value="tileLayerScaleY"
                    :disabled="disabled || !activeDrawingLayer"
                    @change="onTileLayerScaleChange('y', $event)"
                  />
                </div>
                <div class="att-axis-row att-axis-lock">
                  <span class="att-size-label">约束比例</span>
                  <label class="att-checkbox">
                    <input
                      type="checkbox"
                      v-model="tileScaleLocked"
                      :disabled="disabled || !activeDrawingLayer"
                    />
                  </label>
                </div>
              </div>
            </div>

            <div class="att-row att-row-stacked">
              <span class="att-label">旋转</span>
              <div class="att-axis-group">
                <input
                  class="att-input att-input-no-spin"
                  type="number"
                  step="1"
                  :value="tileLayerRotation"
                  :disabled="disabled || !activeDrawingLayer"
                  @change="onTileLayerRotationChange"
                />
                <input
                  class="att-range"
                  type="range"
                  min="-180"
                  max="180"
                  step="1"
                  :value="tileLayerRotation"
                  :disabled="disabled || !activeDrawingLayer"
                  @input="onTileLayerRotationChange"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- 图块集列表 -->
        <div class="mi-section" :class="{ open: fold.tileSets }">
          <button class="mi-head" :disabled="disabled" @click="fold.tileSets = !fold.tileSets">
            <img :src="iconChevron" class="mi-chevron" alt="" />
            <span class="mi-head-title">图块集列表</span>
            <span class="mi-count">{{ tileSetGroups.length }}</span>
          </button>
          <div v-if="fold.tileSets" class="mi-body">
            <div class="mi-list">
              <template v-for="group in tileSetGroups" :key="group.id || 'default'">
                <!-- 行内改名：右键菜单触发后原地变成输入框 -->
                <div
                  v-if="renamingTilesetId === group.id"
                  class="mi-list-row mi-list-row-edit tileset-row"
                  :class="{ 'is-selected': group.id === selectedTilesetRow?.id }"
                >
                  <span class="mi-list-dot tileset-dot" />
                  <input
                    :ref="setTilesetRenameInput"
                    v-model="tilesetRenameDraft"
                    class="mi-list-rename"
                    maxlength="20"
                    :disabled="disabled"
                    @keydown.enter.prevent="commitTilesetRename(group.id)"
                    @keydown.esc.prevent="cancelTilesetRename"
                    @blur="commitTilesetRename(group.id)"
                  />
                </div>
                <button
                  v-else
                  class="mi-list-row tileset-row"
                  :class="{
                    'is-selected': group.id === selectedTilesetRow?.id,
                    'is-off': group.disabled,
                  }"
                  :disabled="disabled"
                  @click="selectTilesetRow(group.id)"
                  @contextmenu="openTilesetMenu(group.id, $event)"
                >
                  <span class="mi-list-dot tileset-dot" />
                  <span class="mi-list-name">{{ group.name }}</span>
                  <span class="tileset-size">{{ group.tileWidth }}x{{ group.tileHeight }}</span>
                </button>
              </template>
              <div v-if="!tileSetGroups.length" class="mi-list-empty">
                还没有图块集，点下方「新建」建一个空的
              </div>
            </div>
            <div class="tileset-actions">
              <button class="mi-btn" :disabled="disabled" @click="emit('new-tileset-group')">新建</button>
              <button
                class="mi-btn mi-btn-danger"
                :disabled="disabled || !canDeleteTileset"
                @click="onTilesetDelete"
              >删除</button>
              <button
                class="mi-btn"
                :disabled="disabled || !selectedTilesetRow"
                @click="onTilesetDuplicate"
              >复制</button>
              <button
                class="mi-btn"
                :disabled="disabled || !selectedTilesetRow || selectedTilesetRow.locked"
                @click="onTilesetToggleDisabled"
              >{{ selectedTilesetRow?.disabled ? '启用' : '禁用' }}</button>
            </div>
          </div>
        </div>
      </div>
      </template>
      </template>

      <!-- 形状列表：当前形状层的全部形状（按类型筛选 + 底部按钮），只在「形状」页显示 -->
      <div v-if="isShapeMode && shapePage && !selectedMarker" class="att-group marker-inspector shape-manager">
        <div class="mi-section" :class="{ open: shapeFold.manager }">
          <button class="mi-head" :disabled="disabled" @click="shapeFold.manager = !shapeFold.manager">
            <img :src="iconChevron" class="mi-chevron" alt="" />
            <span class="mi-head-title">碰撞列表</span>
            <span class="mi-count">{{ mapStore.activeShapes.length }}</span>
          </button>
          <div v-if="shapeFold.manager" class="mi-body">
            <!-- 按形状类型筛选 -->
            <CustomSelect
              class="mi-filter"
              :model-value="shapeKindFilter"
              :options="shapeKindFilterOptions"
              :disabled="disabled"
              @update:model-value="shapeKindFilter = $event"
            />
            <div class="mi-list">
              <div
                v-for="item in listedShapes"
                :key="item.id"
                class="mi-list-row sm-row"
                :class="{ 'is-selected': isShapeSelected(item.id), 'is-off': item.disabled === true }"
              >
                <button
                  class="sm-main"
                  :disabled="disabled"
                  @click="selectShapeFromList(item.id, $event)"
                  @dblclick="focusShapeFromList(item.id)"
                >
                  <span class="sm-dot" :style="{ background: shapeColorCss(item) }" />
                  <span class="sm-name" :class="{ empty: !(item.tag || '').trim() }">
                    {{ shapeDisplayName(item) }}
                  </span>
                  <span class="sm-kind">{{ shapeKindLabel(item.kind) }}</span>
                </button>
              </div>
              <div v-if="!listedShapes.length" class="mi-list-empty">
                {{ mapStore.activeShapes.length ? '没有这个类型的碰撞体' : '这个碰撞层还没有碰撞体' }}
              </div>
            </div>

            <!-- 底部一行四个按钮：全选 / 清空 / 禁用（启用） / 删除 -->
            <div class="sm-actions">
              <button class="mi-btn" :disabled="disabled || !listedShapes.length" @click="selectAllShapes">全选</button>
              <button class="mi-btn" :disabled="disabled || !selectedShapeIds.length" @click="clearShapeSelection">清空</button>
              <button
                class="mi-btn"
                :disabled="disabled || !actionShapeIds.length"
                @click="toggleActionDisabled"
              >{{ actionAllDisabled ? '启用' : '禁用' }}</button>
              <button
                class="mi-btn mi-btn-danger"
                :disabled="disabled || !actionShapeIds.length"
                @click="removeActionShapes"
              >
                <span>删除</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 标记管理右键菜单：Teleport 到 body，避免被右栏滚动容器裁剪
           放在 v-if / v-else 分支之外，避免打断条件分支链 -->
      <Teleport to="body">
        <div
          v-if="markerMenu"
          ref="markerMenuRef"
          class="mi-menu"
          :style="{ left: `${markerMenu.x}px`, top: `${markerMenu.y}px` }"
        >
          <button class="mi-menu-item" @click="runMarkerMenu('rename')">重命名</button>
          <button class="mi-menu-item" @click="runMarkerMenu('focus')">定位到此标记</button>
          <button class="mi-menu-item" @click="runMarkerMenu('duplicate')">复制标记</button>
          <div class="mi-menu-sep" />
          <button class="mi-menu-item" @click="runMarkerMenu('toggle-visible')">
            {{ menuMarker?.visible === false ? '在地图上显示' : '在地图上隐藏' }}
          </button>
          <button class="mi-menu-item" @click="runMarkerMenu('toggle-locked')">
            {{ menuMarker?.locked === true ? '解锁（允许拖动）' : '锁定（禁止拖动）' }}
          </button>
          <div class="mi-menu-sep" />
          <button class="mi-menu-item mi-menu-danger" @click="runMarkerMenu('delete')">删除标记</button>
        </div>
      </Teleport>

      <!-- 图块集右键菜单：重命名 / 复制 / 隐藏 / 锁定 / 删除 -->
      <Teleport to="body">
        <div
          v-if="tilesetMenu"
          ref="tilesetMenuRef"
          class="mi-menu"
          :style="{ left: `${tilesetMenu.x}px`, top: `${tilesetMenu.y}px` }"
        >
          <button class="mi-menu-item" @click="runTilesetMenu('rename')">重命名</button>
          <button class="mi-menu-item" @click="runTilesetMenu('duplicate')">复制图块集</button>
          <div class="mi-menu-sep" />
          <button
            class="mi-menu-item"
            :disabled="menuTileset?.locked === true"
            @click="runTilesetMenu('toggle-hidden')"
          >{{ menuTileset?.disabled ? '显示图块集' : '隐藏图块集' }}</button>
          <button class="mi-menu-item" @click="runTilesetMenu('toggle-locked')">
            {{ menuTileset?.locked ? '解锁' : '锁定' }}
          </button>
          <div class="mi-menu-sep" />
          <button
            class="mi-menu-item mi-menu-danger"
            :disabled="!canDeleteTileset"
            @click="runTilesetMenu('delete')"
          >删除图块集</button>
        </div>
      </Teleport>
    </div>
  </div>
</template>

<style scoped>
.property-panel {
  display: flex;
  flex-direction: column;
  /* 与滚动内容同色：面板全部折叠后下方空白不能变成另一种颜色 */
  background: var(--bg-root);
}

.att-frame {
  display: flex;
  flex-direction: column;
  /* 统一标准：分组之间与分节之间一样，都是 12px */
  gap: 12px;
  padding: 12px 16px 16px 16px;
  background: var(--bg-root);
}

/* 属性分组：地图 / 图层 / 变换（不显示分组标题，仅用间距区分） */
.att-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 标签与控件之间收紧：标签只有两个字时也不会拉开一大片空白 */
.att-row {
  display: flex;
  align-items: center;
  gap: 10px;
  /* 统一行高：输入框 / 下拉 / 复选框行都是 24px，纵向节奏一致 */
  min-height: 24px;
}

/* 下拉框：固定占满标签右侧剩余宽度，右边缘对齐属性区 */
.att-select {
  flex: 1;
  width: 100%;
  min-width: 0;
}

/* 子菜单：开关开启后展开的从属设置（缩进 + 左侧竖线，表明从属于上方开关） */
.att-subgroup {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-left: 2px;
  padding: 2px 0 2px 12px;
  border-left: 1px solid rgba(255, 255, 255, 0.09);
}

/* 标签列：最长的标签是 4 个字，列宽按此收紧，控件左边缘不再离得太远 */
.att-label {
  color: #9ca0a4;
  font-size: 12px;
  min-width: 50px;
  flex-shrink: 0;
  white-space: nowrap;
  /* 与 24px 的行高对齐，单行/多行标题都在同一基线上 */
  line-height: 24px;
}

/* 行尾设置按钮：相机 / 下滑详细参数的入口，hover 与展开时用底色提示状态 */
.att-gear-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  margin-left: auto;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: default;
  flex-shrink: 0;
}

.att-gear-btn img {
  width: 14px;
  height: 14px;
  opacity: 0.55;
}

.att-gear-btn:hover {
  background: rgb(61, 64, 72);
}

.att-gear-btn:hover img {
  opacity: 0.9;
}

.att-gear-btn.active {
  background: rgb(61, 64, 72);
}

.att-gear-btn.active img {
  opacity: 1;
}

.att-gear-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.att-input {
  width: 100%;
  height: 24px;
  background: rgb(40, 43, 52);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: white;
  padding: 0 6px;
  font-size: 12px;
  outline: none;
  box-sizing: border-box;
}

.att-input:hover {
  background: rgb(50, 53, 62);
  border: 1px solid rgb(65, 69, 82);
}

.att-input:focus {
  background: var(--border-light);
  border: 1px solid rgb(65, 69, 82);
  color: white;
}

/* 输入框 + 下方提示（如重名警告）的纵向容器 */
.att-field {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.att-input-warn {
  border-color: rgb(140, 70, 60);
}

.att-warn {
  font-size: 11px;
  line-height: 1.2;
  color: #e08874;
}

.att-input-no-spin::-webkit-inner-spin-button,
.att-input-no-spin::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.att-input-no-spin[type="number"] {
  -moz-appearance: textfield;
}

.att-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.att-checkbox input[type="checkbox"]:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.att-size-group {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

/* 同一行两个数值输入（地图尺寸等）等分剩余宽度 */
.att-size-group .att-input {
  flex: 1 1 0;
  width: 100%;
  min-width: 0;
}

/* 数字框 + 行尾上下箭头（自绘，macOS 上原生箭头不悬停不显示） */
.att-spin {
  position: relative;
  display: flex;
  flex: 1 1 0;
  width: 100%;
  min-width: 0;
}

.att-spin .att-input {
  padding-right: 17px;
}

.att-spin-btns {
  position: absolute;
  top: 1px;
  right: 1px;
  bottom: 1px;
  width: 14px;
  display: flex;
  flex-direction: column;
  border-radius: 0 3px 3px 0;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.045);
}

.att-spin-btn {
  flex: 1 1 0;
  min-height: 0;
  padding: 0;
  border: none;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: default;
}

.att-spin-btn + .att-spin-btn {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.att-spin-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.att-spin-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* 复用分区标题的小箭头，转成上下两个方向 */
.att-spin-arrow {
  width: 8px;
  height: 8px;
  opacity: 0.75;
}

.att-spin-arrow.up {
  transform: rotate(-90deg);
}

.att-spin-arrow.down {
  transform: rotate(90deg);
}

/* X / Y 分两行：标签贴住第一行，两行输入框左边缘对齐 */
.att-row-stacked {
  align-items: flex-start;
}

.att-row-stacked > .att-label {
  line-height: 24px;
}

.att-axis-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

/* 刻度标签与输入框的间距跟「地图尺寸」那一行保持一致（8px） */
.att-axis-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-width: 0;
}

.att-axis-row .att-input {
  flex: 1 1 0;
  width: 100%;
  min-width: 0;
}

/* 缩放下方「约束比例」行：文字跟 X / Y 同列，选框紧跟其后 */
.att-axis-lock {
  gap: 8px;
}

/* 旋转滑条：竖排在输入框下方，按自身 3px 高度撑开，不再参与拉伸分配 */
.att-axis-group .att-range {
  flex: 0 0 auto;
  width: 100%;
  margin: 3px 0 1px;
}

.att-size-label {
  color: #9ca0a4;
  font-size: 12px;
}

.att-checkbox {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: default;
}

.att-checkbox input[type="checkbox"] {
  width: 14px;
  height: 14px;
  accent-color: #528bff;
  border-radius: 3px;
}

.att-checkbox-text {
  color: #9ca0a4;
  font-size: 12px;
}

/* 只读信息值（瓦片数量 / 图片尺寸 / 形状数量等） */
.att-value {
  color: #d5d8dc;
  font-size: 12px;
  white-space: nowrap;
}


/* 占位控件：禁用态（功能开发中） */
.att-range {
  flex: 1;
  min-width: 0;
}

.att-range:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* ====== 标记 / 形状检视器（Godot / Unity 风格的可折叠分区） ====== */
/* 分组间距沿用 .att-group 的 12px：分节之间 = 底部留白 12 + 分组间距 12 = 24px，
   与「地图 / 场景 / 图层」等页面完全一致（这里不要再单独压成 0） */

.mi-section {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

/* 第一块分区不画上分割线，避免紧贴上方标签栏形成多余线条 */
.att-frame > .att-group:first-child > .mi-section:first-child {
  border-top: none;
}

/* 分区标题：整行可点，左侧箭头指示展开状态（参考 Godot / Unity 检视器） */
.mi-head {
  display: flex;
  align-items: center;
  gap: 6px;
  width: calc(100% + 16px);
  height: 30px;
  margin: 0 -8px;
  padding: 0 8px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: #9ea3aa;
  font-size: 12px;
  font-family: inherit;
  text-align: left;
  cursor: default;
  transition: background 0.12s ease, color 0.12s ease;
}

.mi-head:hover {
  background: rgba(255, 255, 255, 0.045);
  color: #e2e5e9;
}

.mi-head:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mi-head:disabled:hover {
  background: transparent;
  color: #9ea3aa;
}

/* 展开中的分区标题更亮，让"当前展开哪一组"一眼可见 */
.mi-section.open > .mi-head {
  color: #d5d8dc;
}

/* 收起时朝右 >，展开时朝下 v；与帮助面板、素材栏的箭头保持同一套动作 */
.mi-chevron {
  flex-shrink: 0;
  width: 14px;
  height: 14px;
  opacity: 0.5;
  transition: transform 0.18s ease, opacity 0.18s ease;
}

.mi-section.open > .mi-head .mi-chevron {
  transform: rotate(90deg);
  opacity: 0.8;
}

.mi-head:hover .mi-chevron {
  opacity: 0.9;
}

.mi-head-title {
  flex: 1;
}

.mi-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 2px 0 12px;
}

.mi-actions {
  display: flex;
  gap: 8px;
}

/* 分区标题右侧的数量（如标记个数） */
.mi-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 15px;
  padding: 0 5px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: #a7acb4;
  font-size: 10px;
  line-height: 1;
}

/* 标记管理列表：当前地图的全部标记，点一行就选中对应图钉 */
.mi-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 168px;
  overflow-y: auto;
}

.mi-list-row {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  /* 与输入框同高：列表卡片、下拉、输入框统一 24px */
  height: 24px;
  padding: 0 6px;
  border: 1px solid transparent;
  border-radius: 4px;
  background: transparent;
  font-family: inherit;
  text-align: left;
  cursor: default;
}

.mi-list-row:hover { background: rgb(48, 51, 60); }
.mi-list-row.is-selected {
  background: rgb(46, 49, 58);
  border-color: var(--border-light);
}
.mi-list-row.is-hidden { opacity: 0.45; }
.mi-list-row:disabled { opacity: 0.4; }

.mi-list-dot {
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #98a0aa;
}
.mi-list-row.is-selected .mi-list-dot { background: #ff5252; }

.mi-list-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: #d7dbe1;
}

.mi-list-coord {
  flex-shrink: 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 10px;
  color: #8f959d;
}

.mi-list-empty {
  padding: 6px 2px;
  font-size: 11px;
  color: #7c818a;
}

.mi-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  flex: 1;
  /* 统一控件高度：按钮与输入框、下拉都是 24px */
  height: 24px;
  padding: 0 8px;
  background: rgb(48, 51, 60);
  border: 1px solid var(--border-light);
  border-radius: 5px;
  color: #cfd3d9;
  font-size: 12px;
  font-family: inherit;
  cursor: default;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.mi-btn img {
  width: 13px;
  height: 13px;
  opacity: 0.75;
}

.mi-btn:hover {
  background: rgb(61, 64, 72);
  color: #fff;
}

.mi-btn:hover img {
  opacity: 1;
}

.mi-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mi-btn-danger:hover {
  background: rgba(95, 45, 39, 0.75);
  border-color: rgba(224, 92, 78, 0.5);
  color: #ffb4ab;
}

/* 标记管理顶部的类型筛选 */
.mi-filter {
  width: 100%;
}

/* 行内改名：与列表行同高，输入框占满名称位置 */
.mi-list-row-edit {
  background: rgb(46, 49, 58);
  border-color: var(--border-light);
}

.mi-list-rename {
  flex: 1;
  min-width: 0;
  height: 20px;
  padding: 0 4px;
  background: rgb(40, 43, 52);
  border: 1px solid rgb(65, 69, 82);
  border-radius: 3px;
  color: #fff;
  font-size: 12px;
  font-family: inherit;
  outline: none;
  box-sizing: border-box;
}

/* 列表右键菜单：fixed 定位在鼠标处，由 clampMarkerMenu 收进窗口内 */
.mi-menu {
  position: fixed;
  z-index: 3000;
  min-width: 148px;
  padding: 4px;
  background: var(--bg-root);
  border: 1px solid var(--border-light);
  border-radius: 6px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
}

.mi-menu-item {
  display: flex;
  align-items: center;
  width: 100%;
  height: 26px;
  padding: 0 8px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: #cfd3d9;
  font-size: 12px;
  font-family: inherit;
  text-align: left;
  cursor: default;
}

.mi-menu-item:hover {
  background: rgb(61, 64, 72);
  color: #fff;
}

/* 不可用的菜单项（如锁定后不能隐藏 / 删除） */
.mi-menu-item:disabled {
  opacity: 0.4;
}

.mi-menu-item:disabled:hover {
  background: transparent;
  color: #cfd3d9;
}

.mi-menu-sep {
  height: 1px;
  margin: 4px 6px;
  background: rgba(255, 255, 255, 0.07);
}

.mi-menu-danger:hover {
  background: rgba(95, 45, 39, 0.75);
  color: #ffb4ab;
}

/* ====== 形状列表：卡片 / 底部操作 ====== */
/* 卡片沿用 .mi-list-row 的统一行高与内边距，多选改为 Shift / Cmd / Ctrl 点选 */

.sm-main {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
  height: 100%;
  padding: 0;
  background: transparent;
  border: none;
  color: inherit;
  font-family: inherit;
  text-align: left;
  cursor: default;
}

.sm-main:disabled { opacity: 0.5; cursor: not-allowed; }

.sm-dot {
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.sm-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
  color: #d7dbe1;
  text-align: left;
}

.sm-name.empty { color: #6f747c; }

/* 卡片右侧的形状类型（只读） */
.sm-kind { flex-shrink: 0; font-size: 10px; color: #8f959d; }

/* 已禁用的形状：名称变淡，一眼能区分 */
.sm-row.is-off .sm-name,
.sm-row.is-off .sm-dot { opacity: 0.5; }

/* 底部操作区：全选 / 清空 / 禁用（启用） / 删除 排成一行 */
.sm-actions {
  display: flex;
  gap: 6px;
}

/* 面板较窄时四个按钮平分宽度，不靠内容撑开 */
.sm-actions .mi-btn {
  min-width: 0;
  padding: 0 4px;
}

/* ====== 图块集列表 ====== */
/* 行结构：圆点（选中=主题绿，未选中=灰） + 名称 + 图块尺寸 + 锁定状态 */
.tileset-dot {
  background: #98a0aa;
}

.tileset-row.is-selected .tileset-dot {
  background: #5BFB84;
}

.tileset-size {
  flex-shrink: 0;
  color: #9ca0a4;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
}

/* 已禁用的图块集：名称与圆点变淡，一眼能区分 */
.tileset-row.is-off .mi-list-name,
.tileset-row.is-off .tileset-dot {
  opacity: 0.5;
}

.tileset-actions {
  display: flex;
  gap: 6px;
}

.tileset-actions .mi-btn {
  flex: 1 1 0;
  min-width: 0;
  justify-content: center;
  padding: 0 4px;
}

/* ====== 碰撞层级（勾选后在面板内展开，和单向碰撞一致） ====== */
.layer-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}

.layer-block-name {
  color: #9ca0a4;
  font-size: 12px;
  line-height: 18px;
}

.layer-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
}

.layer-cell {
  height: 26px;
  background: rgb(34, 37, 43);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: #b9bdc2;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  cursor: default;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.layer-cell:hover:not(:disabled):not(.layer-cell-active) {
  background: var(--border-light);
}

.layer-cell-active {
  background: rgba(91, 251, 132, 0.16);
  border-color: rgba(91, 251, 132, 0.6);
  color: #e8eaec;
  box-shadow: inset 0 0 0 1px rgba(91, 251, 132, 0.25);
}

.layer-cell:disabled {
  opacity: 0.5;
}
</style>