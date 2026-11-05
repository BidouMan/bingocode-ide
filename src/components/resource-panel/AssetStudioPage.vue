<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { open } from '@tauri-apps/plugin-dialog'
import { UNGROUPED, IMAGE_EXTS, joinPath, useMapResourceLibStore } from '../../stores/mapResourceLib'
import type { CategoryIndex, IndexEntry, MapResourceItem, ResourceCategory } from '../../stores/mapResourceLib'
import {
  SPRITE_PACKAGE_EXTS,
  SPRITE_STUDIO_CATEGORIES,
  isSpriteCategory,
  useSpriteResourceStudioStore,
} from '../../stores/spriteResourceStudio'
import { searchItems } from '../../utils/assetSearch'
import { fitPixelImage, THUMB_SIZE } from '../../utils/thumbFit'
import iconEdit from '../../assets/icons/编辑.svg'
import iconDelete from '../../assets/icons/icon--delete.svg'
import iconSettings from '../../assets/icons/icon--settings.svg'
import iconMove from '../../assets/icons/新建地图.svg'
import CustomSelect from '../common/CustomSelect.vue'

/**
 * 开发模式专用：内置素材整理页（多选 / 批量改目录 / 批量打标签 / 改名）。
 * 整页只在 dev 构建里被动态 import，正式包不会包含它。
 */
const emit = defineEmits<{
  close: []
  /** 绘制测试：把选中的图块/图集交给地图编辑器临时试画 */
  'tile-test': [items: Array<{ path: string; name: string; assetKind?: 'tile' | 'tileset'; tileSize?: number }>]
}>()

const mapStore = useMapResourceLibStore()
const spriteStore = useSpriteResourceStudioStore()

const CATEGORIES: Array<{ id: ResourceCategory; label: string }> = [
  { id: 'tiles', label: '图块' },
  { id: 'tilesets', label: '集合' },
  { id: 'images', label: '图像' },
  ...SPRITE_STUDIO_CATEGORIES,
]

const activeCategory = ref<ResourceCategory>('tiles')
/** 当前页签是角色素材（sprites）还是地图素材（maps） */
const isSpriteScope = computed(() => isSpriteCategory(activeCategory.value))

/**
 * 两个素材库共用一套整理 UI：按当前页签把读写委托给对应 store。
 * 角色 store 只被本页（dev 专用）引用，正式包不会包含它。
 */
const store = {
  get items() {
    return isSpriteScope.value ? spriteStore.items : mapStore.items
  },
  get engineDir() {
    return isSpriteScope.value ? spriteStore.engineDir : mapStore.engineDir
  },
  categoryDir(category: ResourceCategory) {
    return isSpriteScope.value
      ? spriteStore.categoryDir(category as 'characters' | 'items')
      : mapStore.categoryDir(category)
  },
  indexFilePath(category: ResourceCategory) {
    return isSpriteScope.value
      ? spriteStore.indexFilePath(category as 'characters' | 'items')
      : mapStore.indexFilePath(category)
  },
  readCategoryIndex(category: ResourceCategory) {
    return isSpriteScope.value
      ? spriteStore.readCategoryIndex(category as 'characters' | 'items')
      : mapStore.readCategoryIndex(category)
  },
  listGroups(category: ResourceCategory) {
    return isSpriteScope.value ? spriteStore.listGroups(category as 'characters' | 'items') : mapStore.listGroups(category)
  },
  loadBuiltinResources(force = false) {
    return isSpriteScope.value ? spriteStore.loadSpriteResources(force) : mapStore.loadBuiltinResources()
  },
}

const searchQuery = ref('')
const viewMode = ref<'grid' | 'list'>('grid')
const activeGroup = ref<string | null>(null)

const selectedRels = ref<string[]>([])
const lastClicked = ref<string | null>(null)
/** 多选模式：勾选后可累积选择；不勾选时点击即切换为只选当前这一个 */
const multiSelect = ref(false)

const entries = ref<Record<string, IndexEntry>>({})
const tagPool = ref<string[]>([])
const version = ref(1)
/**
 * 当前内存里的索引属于哪个分类。
 * 切页签瞬间置为 null：此时 entries/tagPool 还是上一个分类的数据，
 * 若此刻发生写入（比如焦点还在文件名框上按回车），会把旧分类的索引写进新分类的文件里，
 * 表现为「标签池被清空、条目大面积丢失」。写入前必须校验它和 activeCategory 一致。
 */
const indexCategory = ref<ResourceCategory | null>(null)
/** 当前分类下真实存在的文件夹（按手动顺序排列，含空目录） */
const folders = ref<string[]>([])

const busy = ref(false)
const error = ref('')

const newFolderInput = ref('')
/** 新建分类行是否处于输入态（点「+ 新建分类」展开，Esc 收起） */
const creatingFolder = ref(false)
const newFolderInputEl = ref<HTMLInputElement | null>(null)
/** 正在改名的文件夹（null = 没有） */
const renamingFolder = ref<string | null>(null)
const renameFolderInput = ref('')
const renameInputEl = ref<HTMLInputElement | null>(null)
/** 正在等待删除确认的文件夹（null = 没有） */
const confirmDeleteFolder = ref<string | null>(null)

/** 拖拽用的自定义 MIME（与 MapCanvas 的 application/x-bingo-* 惯例一致） */
const ASSET_MIME = 'application/x-bingo-asset'
const FOLDER_MIME = 'application/x-bingo-folder'
/** 素材拖拽：拖动开始时的素材 rel 快照（拖到已选中的素材上 = 整组一起动） */
const assetDragRels = ref<string[]>([])
/** 素材拖拽经过的分类行（高亮投放目标，用普通选中样式） */
const assetOverFolder = ref<string | null>(null)
/** 分类排序拖拽：被拖的分类名 */
const folderDragName = ref<string | null>(null)
/** 分类排序拖拽：插入位置（0..folders.length，基于原数组的槽位） */
const folderDropIndex = ref<number | null>(null)
/** 自定义拖拽幽灵元素（挂在 body 下，scoped 样式管不到，一律内联样式） */
let ghostEl: HTMLElement | null = null

/** 列表模式缩略图比图标模式小一档 */
const LIST_THUMB_SIZE = 32

/** 缩略图加载统一入口：像素图锐化 + 回填原始尺寸（仅地图素材 thumbnail 是文件 URL，
 *  natural 即原图尺寸；角色素材的尺寸在 store 填充阶段已写好，这里跳过避免覆盖） */
function onThumbLoad(event: Event) {
  const img = event.currentTarget as HTMLImageElement | null
  if (!img) return
  fitPixelImage(img)
  const rel = img.dataset.rel
  if (!rel || img.naturalWidth === 0) return
  // spriteResourceStudio 的缩略图是归一化 160×160 dataURL，不能取 natural
  if (img.src.startsWith('data:')) return
  const item = store.items.find(i => i.rel === rel)
  if (item && item.width == null) {
    item.width = img.naturalWidth
    item.height = img.naturalHeight
  }
}

const groupTarget = ref('')
const tagInput = ref('')
const tagFilter = ref('')
const fileInput = ref('')
/** 文件名「输入即改」的防抖定时器（切换选中项时要清掉，避免把旧输入写到新素材上） */
let fileNameTimer: ReturnType<typeof setTimeout> | null = null
/** 分类管理面板是否展开（点「分类」行右侧设置按钮切换） */
const folderPanelOpen = ref(false)
/** 标签管理面板是否展开（点「标签」标题右侧设置按钮切换） */
const tagPanelOpen = ref(false)

function toggleFolderPanel() {
  folderPanelOpen.value = !folderPanelOpen.value
  if (folderPanelOpen.value) {
    renamingFolder.value = null
    confirmDeleteFolder.value = null
    creatingFolder.value = false
  }
}

function toggleTagPanel() {
  tagPanelOpen.value = !tagPanelOpen.value
  if (!tagPanelOpen.value) {
    managingTag.value = null
    tagRenameValue.value = ''
  }
}

// ─── 数据加载 ───

async function loadIndex() {
  const category = activeCategory.value
  const idx = await store.readCategoryIndex(category)
  // 读取期间用户又切了页签：丢弃本次结果，否则会把 A 分类的索引装进 B 分类
  if (category !== activeCategory.value) return
  entries.value = idx.entries
  tagPool.value = [...idx.tagPool]
  version.value = idx.version
  await refreshFolders(idx.groups)
  if (category !== activeCategory.value) return
  if (idx.ok === false) {
    // 索引文件存在但解析失败：停止写入，避免用空数据把原文件覆盖掉
    indexCategory.value = null
    error.value = '索引文件内容损坏，已停止写入以免覆盖原数据（可先备份再修复 index.json）'
    return
  }
  error.value = ''
  indexCategory.value = category
}

/** 合并「索引里的顺序」和「磁盘上实际存在的文件夹」：索引有顺序的优先，新出现且未登记的按名称排 */
async function refreshFolders(order: string[] = folders.value) {
  if (!store.engineDir) return
  const scanned = await store.listGroups(activeCategory.value)
  const ordered = order.filter(name => scanned.includes(name))
  const rest = scanned
    .filter(name => !ordered.includes(name))
    .sort((a, b) => a.localeCompare(b, 'zh-CN'))
  folders.value = [...ordered, ...rest]
}

/** 列表变化后不再自动选中第一项：用户没主动点，右侧面板就保持未选中状态 */
function selectFirstIfEmpty() {
  // 刻意为空：保留函数签名，避免调用点散落修改
}

/** 按当前页签加载对应的素材库（角色库有缓存，地图库每次重扫） */
async function reloadAssets(force = false) {
  await store.loadBuiltinResources(force)
}

onMounted(async () => {
  await reloadAssets()
  await loadIndex()
  selectFirstIfEmpty()
})

watch(activeCategory, async () => {
  // 立刻失效：切页签后旧分类的 entries/tagPool 还在内存里，必须先禁止写入
  indexCategory.value = null
  entries.value = {}
  tagPool.value = []
  activeGroup.value = null
  selectedRels.value = []
  lastClicked.value = null
  renamingFolder.value = null
  confirmDeleteFolder.value = null
  creatingFolder.value = false
  folderPanelOpen.value = false
  resetFolderDrag()
  assetOverFolder.value = null
  await reloadAssets()
  await loadIndex()
  selectFirstIfEmpty()
})

// ─── 列表 / 筛选 ───

const groupOptions = computed(() => {
  // 角色素材不分子文件夹，没有分类筛选
  if (isSpriteScope.value) return []
  const groups: string[] = []
  for (const item of store.items) {
    if (item.category !== activeCategory.value) continue
    if (!groups.includes(item.group)) groups.push(item.group)
  }
  // 「未分类」垫底，其余按文件夹的手动顺序排
  return groups.sort((a, b) => {
    if (a === UNGROUPED) return 1
    if (b === UNGROUPED) return -1
    const ia = folders.value.indexOf(a)
    const ib = folders.value.indexOf(b)
    if (ia !== ib) {
      if (ia < 0) return 1
      if (ib < 0) return -1
      return ia - ib
    }
    return a.localeCompare(b, 'zh-CN')
  })
})

function folderItemCount(name: string) {
  return store.items.filter(i => i.category === activeCategory.value && i.group === name).length
}

type SortKey = 'name' | 'dir' | 'size' | null
type SortDir = 'asc' | 'desc'
const sortKey = ref<SortKey>(null)
const sortDir = ref<SortDir>('asc')

function toggleSort(key: Exclude<SortKey, null>) {
  if (sortKey.value !== key) {
    sortKey.value = key
    sortDir.value = 'asc'
  } else if (sortDir.value === 'asc') {
    sortDir.value = 'desc'
  } else {
    // 升序 → 降序 → 关闭
    sortKey.value = null
  }
}

function sortArrow(key: Exclude<SortKey, null>) {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? ' ▲' : ' ▼'
}

const filtered = computed(() => {
  let list = store.items.filter(r => r.category === activeCategory.value)
  if (activeGroup.value) list = list.filter(r => r.group === activeGroup.value)
  list = searchItems(list, searchQuery.value)
  if (sortKey.value) {
    const key = sortKey.value
    const dir = sortDir.value === 'asc' ? 1 : -1
    list = [...list].sort((a, b) => {
      let va: string | number
      let vb: string | number
      if (key === 'name') {
        va = a.name
        vb = b.name
      } else if (key === 'dir') {
        va = a.group || ''
        vb = b.group || ''
      } else {
        va = (a.width ?? 0) * (a.height ?? 0)
        vb = (b.width ?? 0) * (b.height ?? 0)
      }
      if (va < vb) return -1 * dir
      if (va > vb) return 1 * dir
      return 0
    })
  }
  return list
})

const selectedItems = computed(() =>
  selectedRels.value
    .map(rel => store.items.find(i => i.category === activeCategory.value && i.rel === rel))
    .filter((i): i is MapResourceItem => Boolean(i))
)

const singleItem = computed(() => (selectedItems.value.length === 1 ? selectedItems.value[0] : null))

/** 标签芯片 = 标签池 ∪ 当前分类里用到的标签，保证已有标签不会“隐身” */
const chipTags = computed(() => {
  const list = [...tagPool.value]
  for (const item of store.items) {
    if (item.category !== activeCategory.value) continue
    for (const tag of item.tags) if (!list.includes(tag)) list.push(tag)
  }
  return list
})

/** 标签筛选：标签多时用输入框收窄范围 */
const visibleTags = computed(() => {
  const q = tagFilter.value.trim().toLowerCase()
  if (!q) return chipTags.value
  return chipTags.value.filter(tag => tag.toLowerCase().includes(q))
})

// 选中项变化时，把「分类」下拉同步成选中素材当前的分类（多选且分类一致时也同步）
/** 下拉里的「多个分类」占位值：多选且分组不一致时显示，避免误以为全部都在某个分类里 */
const MIXED_GROUP = '__mixed__'

/** 分类下拉的选项：角色素材 = 角色/道具两个目录；地图素材 = 未分类 →（多选且分类不一时显示「多个分类」）→ 已有分类 */
const groupSelectOptions = computed(() => {
  if (isSpriteScope.value) {
    return SPRITE_STUDIO_CATEGORIES.map(cat => ({ label: cat.label, value: cat.id }))
  }
  const opts = [{ label: '未分类', value: '' }]
  if (groupTarget.value === MIXED_GROUP) opts.push({ label: '多个分类', value: MIXED_GROUP })
  return [...opts, ...folders.value.map(group => ({ label: group, value: group }))]
})

/** 移动按钮是否可用：角色素材要在「角色/道具」间切换，地图素材要选到具体分类 */
const moveDisabled = computed(() => {
  if (busy.value || selectedRels.value.length === 0) return true
  if (isSpriteScope.value) return !groupTarget.value || groupTarget.value === activeCategory.value
  return groupTarget.value === MIXED_GROUP
})

/** 把下拉框同步回选中素材的真实分类（移动成功/失败后都调用，避免下拉停在无效值） */
function syncGroupTarget() {
  const items = selectedItems.value
  if (!items.length) {
    groupTarget.value = ''
    return
  }
  if (isSpriteScope.value) {
    groupTarget.value = items[0].category
    return
  }
  const groupOf = (item: MapResourceItem) => (item.group === UNGROUPED ? '' : item.group)
  const first = groupOf(items[0])
  groupTarget.value = items.every(i => groupOf(i) === first) ? first : MIXED_GROUP
}

watch(
  () => selectedItems.value.map(i => i.rel).join('|'),
  syncGroupTarget,
  { immediate: true },
)

// 单选时把文件名（去掉扩展名）填入输入框；多选或清空时不覆盖用户输入内容
watch(
  () => singleItem.value?.rel ?? '',
  () => {
    if (fileNameTimer) {
      clearTimeout(fileNameTimer)
      fileNameTimer = null
    }
    fileInput.value = singleItem.value?.file.replace(/[.][^.]+$/, '') ?? ''
  },
  { immediate: true },
)

// ─── 选择 ───

function isSelected(rel: string) {
  return selectedRels.value.includes(rel)
}

function toggle(rel: string) {
  if (!multiSelect.value) {
    selectedRels.value = [rel]
    lastClicked.value = rel
    return
  }
  const index = selectedRels.value.indexOf(rel)
  if (index >= 0) selectedRels.value.splice(index, 1)
  else selectedRels.value.push(rel)
  lastClicked.value = rel
}

/**
 * 系统标准多选手势（不依赖「多选」开关）：
 * - 无修饰键：单选替换选区
 * - Cmd/Ctrl + 点击：切换单项选中状态（累加）
 * - Shift + 点击：从上次点击到当前位置的连续范围（按当前筛选列表顺序，天然跨行）
 *   - 单独 Shift：范围替换选区
 *   - Cmd/Ctrl + Shift：范围加入现有选区
 */
function onItemClick(rel: string, event: MouseEvent) {
  const additive = event.metaKey || event.ctrlKey
  const list = filtered.value.map(i => i.rel)

  if (event.shiftKey && lastClicked.value) {
    const from = list.indexOf(lastClicked.value)
    const to = list.indexOf(rel)
    if (from >= 0 && to >= 0) {
      const [start, end] = from < to ? [from, to] : [to, from]
      const range = list.slice(start, end + 1)
      selectedRels.value = additive
        ? [...new Set([...selectedRels.value, ...range])]
        : range
      return
    }
  }

  if (additive) {
    const index = selectedRels.value.indexOf(rel)
    if (index >= 0) selectedRels.value.splice(index, 1)
    else selectedRels.value.push(rel)
    lastClicked.value = rel
    return
  }

  // 普通点击：多选开关打开时仍走旧的累积切换，否则单选替换
  toggle(rel)
}

function selectAllVisible() {
  // 全选本身就是多选动作，自动把多选开关打开，避免开关和结果互相矛盾
  multiSelect.value = true
  selectedRels.value = [...new Set([...selectedRels.value, ...filtered.value.map(i => i.rel)])]
  lastClicked.value = null
}

function clearSelection() {
  selectedRels.value = []
  lastClicked.value = null
}

// ─── 索引读写 ───

function ensureEntry(rel: string): IndexEntry {
  if (!entries.value[rel]) entries.value[rel] = {}
  return entries.value[rel]
}

function entryTags(rel: string): string[] {
  return entries.value[rel]?.tags ?? []
}

/** 把索引内容写入指定文件 */
async function saveIndexFile(path: string, index: CategoryIndex): Promise<boolean> {
  try {
    // 防御：标签数组按顺序去重，避免重复标签落盘（列表里同一标签显示两次）
    const cleanEntries: Record<string, IndexEntry> = {}
    for (const [rel, entry] of Object.entries(index.entries)) {
      cleanEntries[rel] = entry.tags ? { ...entry, tags: [...new Set(entry.tags)] } : entry
    }
    const clean: CategoryIndex = {
      ...index,
      tagPool: [...new Set(index.tagPool)],
      entries: cleanEntries,
    }
    await invoke('write_file', {
      path,
      content: JSON.stringify(clean, null, 2) + '\n',
    })
    return true
  } catch (e) {
    error.value = `保存索引失败：${e}`
    return false
  }
}

/** 保存当前分类的索引：必须保证内存里的数据确实属于当前分类，否则拒绝写入 */
async function writeIndex(): Promise<boolean> {
  const category = activeCategory.value
  if (indexCategory.value !== category) {
    error.value = '索引正在加载，请稍后再试'
    return false
  }
  return saveIndexFile(store.indexFilePath(category), {
    version: version.value,
    tagPool: tagPool.value,
    groups: folders.value,
    entries: entries.value,
  })
}

/**
 * 下拉选好图块尺寸后立即写入分类索引：之后从资源库把该集合放进图块图层时，
 * 就按这个尺寸切图，不再按当前地图格子「猜」。
 */
async function onTileSizeChange(value: string) {
  const size = Number(value)
  if (!Number.isInteger(size) || size < 1 || size > 512) return
  const targets = [...selectedTilesets.value]
  if (!targets.length || busy.value) return
  busy.value = true
  error.value = ''
  for (const item of targets) ensureEntry(item.rel).tileSize = size
  const ok = await writeIndex()
  busy.value = false
  if (ok) {
    for (const item of targets) item.tileSize = size
  } else {
    // 写盘失败：重新读回索引，避免界面显示一个并未保存的值
    await loadIndex()
  }
}

/** 添加资源：从本地任意目录选文件（可多选），复制进当前分类目录 */
async function importAssets() {
  if (busy.value) return
  const spriteScope = isSpriteScope.value
  const picked = await open({
    title: '添加资源',
    multiple: true,
    filters: [
      spriteScope
        ? { name: '角色素材', extensions: ['bgs', 'bsf', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'] }
        : { name: '图片', extensions: ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'svg'] },
    ],
  })
  if (!picked) return
  const files = Array.isArray(picked) ? picked : [picked]
  if (files.length === 0) return

  busy.value = true
  error.value = ''
  try {
    let added = 0
    if (spriteScope) {
      // 角色素材：包文件进 packages/，普通图片进 images/
      for (const src of files) {
        const isPackage = SPRITE_PACKAGE_EXTS.test(src)
        if (!isPackage && !IMAGE_EXTS.test(src)) continue
        const targetDir = joinPath(
          store.categoryDir(activeCategory.value),
          isPackage ? 'packages' : 'images',
        )
        await invoke('create_dir', { path: targetDir })
        // copy_file 自带重名后缀处理（xxx_1.png），返回最终落盘路径
        const dst = await invoke<string>('copy_file', { src, dstDir: targetDir })
        if (dst) added++
      }
    } else {
      // 目标目录：当前筛选到某个分类就放进该分类，否则放分类根目录（未分类）
      const group = activeGroup.value && activeGroup.value !== UNGROUPED ? activeGroup.value : ''
      const targetDir = group
        ? joinPath(store.categoryDir(activeCategory.value), group)
        : store.categoryDir(activeCategory.value)
      if (group) await invoke('create_dir', { path: targetDir })

      for (const src of files) {
        const dst = await invoke<string>('copy_file', { src, dstDir: targetDir })
        if (dst) added++
      }
    }
    if (added === 0) error.value = '没有添加任何文件'
  } catch (e) {
    error.value = `添加失败：${String(e)}`
  } finally {
    busy.value = false
    await manualReload()
  }
}

/**
 * 绘制测试：把选中的图块 / 图集带进地图编辑器临时试画。
 * 只在内存里拼一张测试地图，不产生任何地图文件；看图块拼在一起效果如何，不好就直接删素材。
 */
function startDrawTest() {
  if (busy.value || isSpriteScope.value) return
  const items = selectedItems.value
  if (items.length === 0) {
    error.value = '请先选择要测试的图块素材'
    return
  }
  error.value = ''
  emit('tile-test', items.map(item => ({
    path: item.path,
    name: item.name,
    // 集合分类是多格图集：带上设定的图块尺寸，测试地图按它切而不是再猜
    assetKind: item.category === 'tilesets' ? 'tileset' : 'tile',
    tileSize: item.category === 'tilesets' ? item.tileSize : undefined,
  })))
}

/** 手动重新扫描并刷新列表（不自动调用：编辑过程中页面保持不动） */
async function manualReload() {
  busy.value = true
  const keep = [...selectedRels.value]
  await reloadAssets(true)
  await loadIndex()
  const category = activeCategory.value
  const kept = keep.filter(rel => store.items.some(i => i.category === category && i.rel === rel))
  // 重新加载后原来选中的都不在了就回落到第一个素材，保持面板始终有内容可操作
  selectedRels.value = kept.length ? kept : (filtered.value[0]?.rel ? [filtered.value[0].rel] : [])
  lastClicked.value = null
  busy.value = false
}

function findItem(rel: string) {
  return store.items.find(i => i.category === activeCategory.value && i.rel === rel)
}

/** 选中的图块集：图块尺寸只对「集合」页签有意义 */
const selectedTilesets = computed(() => selectedItems.value.filter(i => i.category === 'tilesets'))

/** 是否展示「图块尺寸」面板：仅集合页签（地图素材范围） */
const showTileSizeCard = computed(() => !isSpriteScope.value && activeCategory.value === 'tilesets')

/** 图块尺寸下拉选项（常用像素尺寸） */
const TILE_SIZE_OPTIONS = [8, 16, 24, 32, 48, 64].map(n => ({ label: `${n}×${n}`, value: String(n) }))

/** 下拉当前值；没设定过时默认显示 16 */
const tileSizeInput = ref('16')

const tileSizeStatus = computed(() => {
  const sizes = selectedTilesets.value.map(i => i.tileSize)
  if (!sizes.length) return ''
  const first = sizes[0]
  if (sizes.every(s => s === first)) return first ? `已设定 ${first}×${first}` : '未设定（默认 16）'
  return '选中项不一致，选择后统一应用'
})

watch(
  () => selectedTilesets.value.map(i => i.tileSize ?? '').join('|'),
  () => {
    const sizes = selectedTilesets.value.map(i => i.tileSize)
    const first = sizes[0]
    // 多选且尺寸不一致时回到默认 16，避免误以为全部都是同一个值
    tileSizeInput.value = sizes.length && sizes.every(s => s === first) ? String(first ?? 16) : '16'
  },
  { immediate: true },
)

/** 名字/标签改完只同步这一个条目，避免整页重扫导致列表跳动 */
function syncItemMeta(rel: string) {
  const item = findItem(rel)
  const entry = entries.value[rel]
  if (!item || !entry) return
  if (entry.name) item.name = entry.name
  item.tags = [...(entry.tags ?? [])]
  item.py = entry.py ?? ''
  item.pyi = entry.pyi ?? ''
}

/** 列表里的「目录」列：角色素材显示包文件 / 图片，地图素材显示分类名 */
function itemDirLabel(item: MapResourceItem): string {
  if (isSpriteCategory(item.category)) return item.spriteKind === 'package' ? '包文件' : '图片'
  return item.group
}

/** 素材所在目录（相对分类目录）：地图 = 分类文件夹；角色 = packages / images */
function itemRelPrefix(item: MapResourceItem): string {
  if (isSpriteCategory(item.category)) return item.spriteKind === 'package' ? 'packages' : 'images'
  return item.group === UNGROUPED ? '' : item.group
}

/** 按当前文件名规则拼出新的分类内相对路径（保留原扩展名） */
function buildItemRel(item: MapResourceItem, base: string): string {
  const ext = item.file.match(/[.][^.]+$/)?.[0] ?? '.png'
  const prefix = itemRelPrefix(item)
  return prefix ? `${prefix}/${base}${ext}` : `${base}${ext}`
}

/** 文件移动/改名后同步路径、分类与缩略图（只更新这一项，不重扫） */
function syncItemPath(oldRel: string, newRel: string) {
  const item = findItem(oldRel)
  if (!item) return
  const dir = store.categoryDir(activeCategory.value)
  item.rel = newRel
  item.file = newRel.split('/').pop() ?? item.file
  item.name = entries.value[newRel]?.name || item.file.replace(/[.][^.]+$/, '')
  if (isSpriteCategory(item.category)) {
    item.group = UNGROUPED
    item.path = `/sprites/${item.category}/${newRel}`
    // 角色缩略图是归一化后的 data URL，与文件路径无关，改名/移动都无需重载
    return
  }
  item.group = newRel.includes('/') ? newRel.slice(0, newRel.lastIndexOf('/')) : UNGROUPED
  item.path = `/maps/${activeCategory.value}/${newRel}`
  item.thumbnail = `${convertFileSrc(joinPath(dir, newRel))}?t=${Date.now()}`
}

// 拼音只在保存名字时预算好写进索引，正式包运行时不加载拼音库
let pinyinModule: typeof import('pinyin-pro') | null = null
async function computePinyin(text: string) {
  pinyinModule ??= await import('pinyin-pro')
  const full = pinyinModule.pinyin(text, { toneType: 'none', type: 'array' }).join('')
  const initials = pinyinModule.pinyin(text, { pattern: 'first', toneType: 'none', type: 'array' }).join('')
  return { py: full, pyi: initials }
}

// ─── 文件移动 ───

/** 目标目录内重名时自动加 -2 / -3，避免批量移动互相覆盖 */
function uniqueRel(group: string, file: string, used: Set<string>): string {
  const build = (name: string) => (group ? `${group}/${name}` : name)
  if (!used.has(build(file))) return build(file)
  const dot = file.lastIndexOf('.')
  const base = dot >= 0 ? file.slice(0, dot) : file
  const ext = dot >= 0 ? file.slice(dot) : ''
  let n = 2
  while (used.has(build(`${base}-${n}${ext}`))) n++
  return build(`${base}-${n}${ext}`)
}

/** 把一组素材移动到目标分类：按钮和「拖到分类行上」共用这一套（含重名去重、失败回滚） */
async function moveRelsToGroup(rels: string[], group: string) {
  if (!rels.length || busy.value) return
  busy.value = true
  error.value = ''

  const category = activeCategory.value
  const dir = store.categoryDir(category)
  const used = new Set(store.items.filter(i => i.category === category).map(i => i.rel))
  const moved: Array<{ oldRel: string; newRel: string }> = []

  try {
    if (group) await invoke('create_dir', { path: joinPath(dir, group) })
  } catch (e) {
    error.value = `创建目录失败：${e}`
    busy.value = false
    return
  }

  for (const rel of rels) {
    const item = store.items.find(i => i.category === category && i.rel === rel)
    if (!item) continue
    const newRel = uniqueRel(group, item.file, used)
    if (newRel === rel) continue
    try {
      await invoke('rename_path', { oldPath: joinPath(dir, rel), newPath: joinPath(dir, newRel) })
    } catch (e) {
      error.value = `「${item.name}」移动失败：${e}`
      continue
    }
    used.delete(rel)
    used.add(newRel)
    moved.push({ oldRel: rel, newRel })
    const meta = entries.value[rel]
    if (meta) {
      delete entries.value[rel]
      entries.value[newRel] = meta
    }
  }

  if (moved.length === 0) {
    busy.value = false
    return
  }

  // 索引写失败就把文件逐个移回去，保持文件和索引一致
  if (!(await writeIndex())) {
    for (const m of [...moved].reverse()) {
      const meta = entries.value[m.newRel]
      if (meta) {
        delete entries.value[m.newRel]
        entries.value[m.oldRel] = meta
      }
      try {
        await invoke('rename_path', { oldPath: joinPath(dir, m.newRel), newPath: joinPath(dir, m.oldRel) })
      } catch {
        // 回滚失败时不再叠加提示，用户已能看到根因
      }
    }
    busy.value = false
    return
  }

  // 移动完只更新对应条目，不重扫整个目录：列表位置、滚动位置都保持不动
  for (const m of moved) syncItemPath(m.oldRel, m.newRel)
  const movedMap = new Map(moved.map(m => [m.oldRel, m.newRel]))
  selectedRels.value = selectedRels.value.map(rel => movedMap.get(rel) ?? rel)
  if (lastClicked.value) lastClicked.value = movedMap.get(lastClicked.value) ?? lastClicked.value
  busy.value = false
}

async function applyGroup(group: string) {
  if (group === MIXED_GROUP) return
  if (isSpriteScope.value) {
    if (isSpriteCategory(group)) await moveToSpriteCategory(group)
    return
  }
  await moveRelsToGroup([...selectedRels.value], group)
  // 移动失败或素材本来就在该分类时，下拉回到真实值
  syncGroupTarget()
}

/** 角色素材换分类：在 sprites/characters 与 sprites/items 之间移动文件与索引条目 */
async function moveToSpriteCategory(target: ResourceCategory) {
  const source = activeCategory.value
  if (!isSpriteCategory(source) || !isSpriteCategory(target) || source === target) return
  // 索引还没切到当前分类时禁止写盘，否则会用旧分类的空索引覆盖目标索引
  if (indexCategory.value !== source) return
  const rels = [...selectedRels.value]
  if (!rels.length || busy.value) return

  busy.value = true
  error.value = ''
  const sourceDir = spriteStore.categoryDir(source)
  const targetDir = spriteStore.categoryDir(target)
  const targetIndex = await spriteStore.readCategoryIndex(target)
  if (targetIndex.ok === false) {
    error.value = '目标分类的索引文件已损坏，已停止写入以免覆盖原数据'
    busy.value = false
    return
  }
  const targetIndexBackup = JSON.parse(JSON.stringify(targetIndex)) as CategoryIndex
  const sourceEntriesBackup = { ...entries.value }
  const used = new Set(store.items.filter(i => i.category === target).map(i => i.rel))
  const moved: Array<{ item: MapResourceItem; oldRel: string; newRel: string; meta?: IndexEntry }> = []

  for (const rel of rels) {
    const item = store.items.find(i => i.category === source && i.rel === rel)
    if (!item) continue
    const kind = item.spriteKind === 'package' ? 'packages' : 'images'
    const newRel = uniqueRel(kind, item.file, used)
    try {
      await invoke('rename_path', { oldPath: joinPath(sourceDir, rel), newPath: joinPath(targetDir, newRel) })
    } catch (e) {
      error.value = `「${item.name}」移动失败：${e}`
      continue
    }
    used.delete(rel)
    used.add(newRel)
    const meta = entries.value[rel]
    moved.push({ item, oldRel: rel, newRel, meta })
    if (meta) {
      delete entries.value[rel]
      targetIndex.entries[newRel] = meta
      // 目标分类的标签池也收录这些标签，切过去后能直接看到
      for (const tag of meta.tags ?? []) {
        if (!targetIndex.tagPool.includes(tag)) targetIndex.tagPool.push(tag)
      }
    }
  }

  if (moved.length === 0) {
    busy.value = false
    return
  }

  const okTarget = await saveIndexFile(spriteStore.indexFilePath(target), targetIndex)
  const okSource =
    okTarget &&
    (await saveIndexFile(spriteStore.indexFilePath(source), {
      version: version.value,
      tagPool: tagPool.value,
      groups: folders.value,
      entries: entries.value,
    }))
  if (!okTarget || !okSource) {
    // 索引没写成功：文件移回原处，目标索引恢复原样
    for (const m of [...moved].reverse()) {
      try {
        await invoke('rename_path', { oldPath: joinPath(targetDir, m.newRel), newPath: joinPath(sourceDir, m.oldRel) })
      } catch {
        // 回滚失败时保留根因提示
      }
    }
    entries.value = sourceEntriesBackup
    await saveIndexFile(spriteStore.indexFilePath(target), targetIndexBackup)
    busy.value = false
    return
  }

  // 成功：更新内存里的素材归属（与角色库缓存共用同一批对象，切到目标页签也能看到）
  for (const m of moved) {
    const item = m.item
    item.category = target
    item.rel = m.newRel
    item.file = m.newRel.split('/').pop() ?? item.file
    item.group = UNGROUPED
    item.path = `/sprites/${target}/${m.newRel}`
    // 缩略图是 data URL，跨分类移动无需重载
  }
  const movedSet = new Set(moved.map(m => m.oldRel))
  selectedRels.value = selectedRels.value.filter(r => !movedSet.has(r))
  if (lastClicked.value && movedSet.has(lastClicked.value)) lastClicked.value = null
  groupTarget.value = ''
  busy.value = false
  // 移走的素材不在当前页签了，自动选中剩下的第一个
  selectFirstIfEmpty()
}

async function moveOne(oldRel: string, newRel: string): Promise<boolean> {
  // 上一次移动还没落盘时直接放弃，避免两次 rename 互相踩
  if (busy.value) return false
  const dir = store.categoryDir(activeCategory.value)
  busy.value = true
  error.value = ''
  try {
    await invoke('rename_path', { oldPath: joinPath(dir, oldRel), newPath: joinPath(dir, newRel) })
  } catch (e) {
    error.value = `重命名失败：${e}`
    busy.value = false
    return false
  }
  const meta = entries.value[oldRel]
  if (meta) {
    delete entries.value[oldRel]
    entries.value[newRel] = meta
  }
  if (!(await writeIndex())) {
    if (meta) {
      delete entries.value[newRel]
      entries.value[oldRel] = meta
    }
    try {
      await invoke('rename_path', { oldPath: joinPath(dir, newRel), newPath: joinPath(dir, oldRel) })
    } catch {
      // 同上
    }
    busy.value = false
    return false
  }
  syncItemPath(oldRel, newRel)
  selectedRels.value = selectedRels.value.map(rel => (rel === oldRel ? newRel : rel))
  if (lastClicked.value === oldRel) lastClicked.value = newRel
  busy.value = false
  return true
}

// ─── 文件夹（分类）管理 ───

function validateFolderName(name: string): string | null {
  if (!name) return '分类名不能为空'
  if (name === UNGROUPED) return `「${UNGROUPED}」是保留名称，换一个吧`
  if (/[\\/:*?"<>|]/.test(name)) return '分类名不能包含 \\ / : * ? " < > |'
  return null
}

function startCreateFolder() {
  creatingFolder.value = true
  renamingFolder.value = null
  confirmDeleteFolder.value = null
  newFolderInput.value = ''
  error.value = ''
  nextTick(() => newFolderInputEl.value?.focus())
}

function cancelCreateFolder() {
  creatingFolder.value = false
  newFolderInput.value = ''
}

async function createFolder() {
  const name = newFolderInput.value.trim()
  if (!name) return
  const invalid = validateFolderName(name)
  if (invalid) {
    error.value = invalid
    return
  }
  if (folders.value.includes(name)) {
    error.value = '已经有同名分类了'
    return
  }
  busy.value = true
  error.value = ''
  try {
    await invoke('create_dir', { path: joinPath(store.categoryDir(activeCategory.value), name) })
  } catch (e) {
    error.value = `新建分类失败：${e}`
    busy.value = false
    return
  }
  folders.value = [...folders.value, name]
  if (await writeIndex()) {
    // 输入行保持展开并清空，整理目录时通常要连续建好几个分类
    newFolderInput.value = ''
    nextTick(() => newFolderInputEl.value?.focus())
  }
  busy.value = false
}

function startRenameFolder(name: string) {
  renamingFolder.value = name
  renameFolderInput.value = name
  confirmDeleteFolder.value = null
  creatingFolder.value = false
  error.value = ''
  nextTick(() => {
    renameInputEl.value?.focus()
    renameInputEl.value?.select()
  })
}

async function applyRenameFolder(oldName: string) {
  const newName = renameFolderInput.value.trim()
  if (newName === oldName) {
    renamingFolder.value = null
    return
  }
  const invalid = validateFolderName(newName)
  if (invalid) {
    error.value = invalid
    return
  }
  if (folders.value.includes(newName)) {
    error.value = '已经有同名分类了'
    return
  }

  const category = activeCategory.value
  const dir = store.categoryDir(category)
  const prefix = `${oldName}/`

  busy.value = true
  error.value = ''
  try {
    await invoke('rename_path', { oldPath: joinPath(dir, oldName), newPath: joinPath(dir, newName) })
  } catch (e) {
    error.value = `分类改名失败：${e}`
    busy.value = false
    return
  }

  // 索引 key 的前缀跟着改
  const backupEntries = entries.value
  const nextEntries: Record<string, IndexEntry> = {}
  for (const [key, value] of Object.entries(backupEntries)) {
    nextEntries[key.startsWith(prefix) ? `${newName}/${key.slice(prefix.length)}` : key] = value
  }
  entries.value = nextEntries

  const backupFolders = [...folders.value]
  folders.value = folders.value.map(name => (name === oldName ? newName : name))

  if (!(await writeIndex())) {
    entries.value = backupEntries
    folders.value = backupFolders
    try {
      await invoke('rename_path', { oldPath: joinPath(dir, newName), newPath: joinPath(dir, oldName) })
    } catch {
      // 回滚失败时保留根因提示
    }
    renamingFolder.value = null
    busy.value = false
    return
  }

  // 同步列表项（只改这一批，不重扫）
  for (const item of store.items) {
    if (item.category !== category || item.group !== oldName) continue
    item.group = newName
    item.rel = `${newName}/${item.file}`
    item.path = `/maps/${category}/${item.rel}`
    item.thumbnail = `${convertFileSrc(joinPath(dir, item.rel))}?t=${Date.now()}`
  }
  const remap = (rel: string) => (rel.startsWith(prefix) ? `${newName}/${rel.slice(prefix.length)}` : rel)
  selectedRels.value = selectedRels.value.map(remap)
  if (lastClicked.value) lastClicked.value = remap(lastClicked.value)
  // 筛选条件跟着改名走，否则改名后筛选会落空
  if (activeGroup.value === oldName) activeGroup.value = newName

  renamingFolder.value = null
  await refreshFolders()
  busy.value = false
}

/** 拖拽排序：把 from 位置的分类挪到 to 位置，顺序写进 index.json 的 groups */
async function reorderFolders(from: number, to: number) {
  if (from === to || from < 0 || to < 0 || from >= folders.value.length || to >= folders.value.length) return
  const list = [...folders.value]
  const [moved] = list.splice(from, 1)
  list.splice(to, 0, moved)
  const backup = [...folders.value]
  folders.value = list
  error.value = ''
  if (!(await writeIndex())) folders.value = backup
}

function askDeleteFolder(name: string) {
  confirmDeleteFolder.value = name
  renamingFolder.value = null
  creatingFolder.value = false
  error.value = ''
}

async function deleteFolder(name: string) {
  const category = activeCategory.value
  const dir = store.categoryDir(category)
  const rels = store.items.filter(i => i.category === category && i.group === name).map(i => i.rel)
  const backupFolders = [...folders.value]
  const backupEntries = entries.value

  busy.value = true
  error.value = ''
  confirmDeleteFolder.value = null

  // 空目录直接删（先确认里面真的没东西，避免误删）
  if (rels.length === 0) {
    let remaining: string[] = []
    try {
      remaining = await invoke<string[]>('list_dir', { path: joinPath(dir, name) })
    } catch {
      // 读不到就按空目录处理
    }
    if (remaining.length > 0) {
      error.value = '分类里还有内容，先清理后再删除'
      busy.value = false
      return
    }
    folders.value = folders.value.filter(f => f !== name)
    if (!(await writeIndex())) {
      folders.value = backupFolders
      busy.value = false
      return
    }
    try {
      await invoke('delete_path', { path: joinPath(dir, name) })
    } catch (e) {
      error.value = `删除目录失败：${e}`
    }
    if (activeGroup.value === name) activeGroup.value = null
    busy.value = false
    return
  }

  // 非空目录：先把素材移回根目录（不删任何文件），再删空目录
  const used = new Set(store.items.filter(i => i.category === category).map(i => i.rel))
  const nextEntries: Record<string, IndexEntry> = { ...backupEntries }
  const moved: Array<{ oldRel: string; newRel: string }> = []

  for (const rel of rels) {
    const file = rel.slice(rel.lastIndexOf('/') + 1)
    const newRel = uniqueRel('', file, used)
    try {
      await invoke('rename_path', { oldPath: joinPath(dir, rel), newPath: joinPath(dir, newRel) })
    } catch (e) {
      error.value = `「${file}」移回未分类失败：${e}`
      // 有一项失败就整体回滚，避免删目录时连文件一起删掉
      for (const m of [...moved].reverse()) {
        try {
          await invoke('rename_path', { oldPath: joinPath(dir, m.newRel), newPath: joinPath(dir, m.oldRel) })
        } catch {
          // 回滚失败时保留根因提示
        }
      }
      entries.value = backupEntries
      folders.value = backupFolders
      busy.value = false
      return
    }
    used.delete(rel)
    used.add(newRel)
    moved.push({ oldRel: rel, newRel })
    if (nextEntries[rel]) {
      nextEntries[newRel] = nextEntries[rel]
      delete nextEntries[rel]
    }
  }

  entries.value = nextEntries
  folders.value = folders.value.filter(f => f !== name)

  if (!(await writeIndex())) {
    entries.value = backupEntries
    folders.value = backupFolders
    for (const m of [...moved].reverse()) {
      try {
        await invoke('rename_path', { oldPath: joinPath(dir, m.newRel), newPath: joinPath(dir, m.oldRel) })
      } catch {
        // 同上
      }
    }
    busy.value = false
    return
  }

  // 所有素材都已移出，目录此时为空，删除是安全的
  try {
    await invoke('delete_path', { path: joinPath(dir, name) })
  } catch (e) {
    error.value = `删除目录失败：${e}`
  }

  for (const m of moved) {
    const item = store.items.find(i => i.category === category && i.rel === m.oldRel)
    if (!item) continue
    item.rel = m.newRel
    item.file = m.newRel.split('/').pop() ?? item.file
    item.group = UNGROUPED
    item.name = nextEntries[m.newRel]?.name || item.file.replace(/[.][^.]+$/, '')
    item.path = `/maps/${category}/${m.newRel}`
    item.thumbnail = `${convertFileSrc(joinPath(dir, m.newRel))}?t=${Date.now()}`
  }
  const remap = (rel: string) => moved.find(m => m.oldRel === rel)?.newRel ?? rel
  selectedRels.value = selectedRels.value.map(remap)
  if (lastClicked.value) lastClicked.value = remap(lastClicked.value)
  if (activeGroup.value === name) activeGroup.value = null

  await refreshFolders()
  busy.value = false
}

// ─── 拖拽（素材移到分类 / 分类排序） ───

/** 自定义幽灵：保留原图标和文件名、以鼠标为中心，挂在 body 下用内联样式（scoped 管不到） */
function makeAssetGhost(item: MapResourceItem, count: number): HTMLElement {
  const ghost = document.createElement('div')
  Object.assign(ghost.style, {
    position: 'fixed',
    top: '-9999px',
    left: '-9999px',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '4px 10px 4px 4px',
    background: 'rgb(56, 58, 64)',
    border: '1px solid rgb(90, 93, 100)',
    borderRadius: '4px',
    color: 'white',
    fontSize: '12px',
    whiteSpace: 'nowrap',
    pointerEvents: 'none',
  } as Record<string, string>)
  const img = document.createElement('img')
  img.src = item.thumbnail
  Object.assign(img.style, { width: '24px', height: '24px', objectFit: 'contain' } as Record<string, string>)
  const label = document.createElement('span')
  label.textContent = count > 1 ? `${item.name} 等 ${count} 项` : item.name
  ghost.append(img, label)
  document.body.appendChild(ghost)
  ghostEl = ghost
  return ghost
}

function removeGhost() {
  ghostEl?.remove()
  ghostEl = null
}

function onAssetDragStart(item: MapResourceItem, e: DragEvent) {
  if (!e.dataTransfer) return
  // 拖到已选中的素材上 = 整组一起移动；拖到未选中的 = 只拖当前这个（顺手把它变成唯一选中）
  let rels: string[]
  if (selectedRels.value.includes(item.rel)) {
    rels = [...selectedRels.value]
  } else {
    selectedRels.value = [item.rel]
    lastClicked.value = item.rel
    rels = [item.rel]
  }
  assetDragRels.value = rels
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData(ASSET_MIME, JSON.stringify(rels))
  const ghost = makeAssetGhost(item, rels.length)
  e.dataTransfer.setDragImage(ghost, ghost.offsetWidth / 2, ghost.offsetHeight / 2)
}

function onAssetDragEnd() {
  assetDragRels.value = []
  assetOverFolder.value = null
  removeGhost()
}

/** 分类行既是素材的投放目标，也是排序拖拽的插入位置参照 */
function onFolderRowDragOver(name: string, index: number, e: DragEvent) {
  // 用组件内的拖拽状态判断类型，不依赖 dataTransfer.types（WebKit 在 dragover 阶段读不到自定义类型）
  if (assetDragRels.value.length > 0) {
    e.preventDefault()
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
    assetOverFolder.value = name
    return
  }
  if (folderDragName.value) {
    // 拖到自己这一行：不显示插入线、不允许投放（落回原地 = 无操作）
    if (folderDragName.value === name) {
      folderDropIndex.value = null
      return
    }
    e.preventDefault()
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
    const before = e.clientY < rect.top + rect.height / 2
    folderDropIndex.value = before ? index : index + 1
  }
}

function onFolderRowDragLeave(name: string, e: DragEvent) {
  // 进入子元素也会触发 dragleave，只有真的离开这一行才取消高亮
  const row = e.currentTarget as HTMLElement
  if (e.relatedTarget && row.contains(e.relatedTarget as Node)) return
  if (assetOverFolder.value === name) assetOverFolder.value = null
}

async function onFolderRowDrop(name: string, index: number, e: DragEvent) {
  if (assetDragRels.value.length > 0) {
    e.preventDefault()
    assetOverFolder.value = null
    const rels = [...assetDragRels.value]
    if (rels.length) await moveRelsToGroup(rels, name)
    return
  }
  if (folderDragName.value) {
    e.preventDefault()
    const from = folders.value.indexOf(folderDragName.value)
    const slot = folderDropIndex.value ?? index
    resetFolderDrag()
    if (from < 0) return
    // slot 基于原数组槽位，先删掉被拖元素后槽位前移一位
    const to = from < slot ? slot - 1 : slot
    await reorderFolders(from, to)
  }
}

function onFolderDragStart(name: string, e: DragEvent) {
  if (!e.dataTransfer) return
  folderDragName.value = name
  folderDropIndex.value = null
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData(FOLDER_MIME, name)
}

function resetFolderDrag() {
  folderDragName.value = null
  folderDropIndex.value = null
}

/** 「未分类」行：只作素材的投放目标（移回根目录），不参与排序和管理 */
function onUngroupedDragOver(e: DragEvent) {
  if (assetDragRels.value.length === 0) return
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
  assetOverFolder.value = UNGROUPED
}

function onUngroupedDragLeave(e: DragEvent) {
  const row = e.currentTarget as HTMLElement
  if (e.relatedTarget && row.contains(e.relatedTarget as Node)) return
  if (assetOverFolder.value === UNGROUPED) assetOverFolder.value = null
}

async function onUngroupedDrop(e: DragEvent) {
  if (assetDragRels.value.length === 0) return
  e.preventDefault()
  assetOverFolder.value = null
  const rels = [...assetDragRels.value]
  if (rels.length) await moveRelsToGroup(rels, '')
}

// ─── 右键删除 ───

const ctxMenu = ref<{ x: number; y: number; rel: string } | null>(null)

function closeCtxMenu() {
  ctxMenu.value = null
  window.removeEventListener('pointerdown', closeCtxMenu)
}

function openItemMenu(item: MapResourceItem, e: MouseEvent) {
  e.preventDefault()
  // 右键未选中的素材时先选中它，删除对象和视觉高亮保持一致
  if (!selectedRels.value.includes(item.rel)) {
    selectedRels.value = [item.rel]
    lastClicked.value = item.rel
  }
  ctxMenu.value = {
    x: Math.min(e.clientX, window.innerWidth - 100),
    y: Math.min(e.clientY, window.innerHeight - 44),
    rel: item.rel,
  }
  window.removeEventListener('pointerdown', closeCtxMenu)
  window.addEventListener('pointerdown', closeCtxMenu)
}

async function deleteItem(rel: string) {
  closeCtxMenu()
  if (busy.value) return
  const item = findItem(rel)
  if (!item) return
  const category = activeCategory.value
  const dir = store.categoryDir(category)
  busy.value = true
  error.value = ''
  try {
    await invoke('delete_path', { path: joinPath(dir, rel) })
  } catch (e) {
    error.value = `删除失败：${e}`
    busy.value = false
    return
  }
  delete entries.value[rel]
  if (!(await writeIndex())) error.value = '索引写入失败，素材已删除但索引可能不一致'
  // 直接从列表移除，避免整库重扫导致缩略图闪动；用 splice 保持角色库缓存同步
  const removeIndex = store.items.findIndex(i => i.category === category && i.rel === rel)
  if (removeIndex >= 0) store.items.splice(removeIndex, 1)
  selectedRels.value = selectedRels.value.filter(r => r !== rel)
  if (lastClicked.value === rel) lastClicked.value = null
  busy.value = false
  selectFirstIfEmpty()
}

// ─── 批量标签 ───

function tagAll(tag: string) {
  return selectedRels.value.length > 0 && selectedRels.value.every(rel => entryTags(rel).includes(tag))
}

function tagSome(tag: string) {
  return selectedRels.value.some(rel => entryTags(rel).includes(tag))
}

async function toggleTagOnSelection(tag: string) {
  const rels = [...selectedRels.value]
  if (!rels.length || busy.value) return
  busy.value = true
  error.value = ''
  const removeAll = rels.every(rel => entryTags(rel).includes(tag))
  for (const rel of rels) {
    const entry = ensureEntry(rel)
    const tags = [...(entry.tags ?? [])]
    // 多选时「部分有、部分没有」走添加分支：已有的素材不能再 push 一次，否则同一标签会重复
    entry.tags = removeAll
      ? tags.filter(t => t !== tag)
      : tags.includes(tag) ? tags : [...tags, tag]
  }
  const ok = await writeIndex()
  busy.value = false
  if (ok) for (const rel of rels) syncItemMeta(rel)
}

/** 在标签管理里新建标签（只加入标签池，给素材打标签靠点上方标签） */
async function addTag() {
  const tag = tagInput.value.trim()
  if (!tag || busy.value) return
  tagInput.value = ''
  if (tagPool.value.includes(tag)) return
  tagPool.value.push(tag)
  error.value = ''
  await writeIndex()
}

/** 在标签管理里删除标签：从标签池和所有素材上一起移除 */
async function removeTag(tag: string) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  tagPool.value = tagPool.value.filter(t => t !== tag)
  for (const entry of Object.values(entries.value)) {
    if (entry.tags?.includes(tag)) entry.tags = entry.tags.filter(t => t !== tag)
  }
  const ok = await writeIndex()
  busy.value = false
  if (ok) for (const rel of Object.keys(entries.value)) syncItemMeta(rel)
  if (tagFilter.value === tag) tagFilter.value = ''
}

// ─── 标签管理：选中标签后改名 / 调位置 / 删除 ───

const managingTag = ref<string | null>(null)
const tagRenameValue = ref('')

function selectManagingTag(tag: string) {
  if (managingTag.value === tag) {
    managingTag.value = null
    tagRenameValue.value = ''
    return
  }
  managingTag.value = tag
  tagRenameValue.value = tag
}

function cancelTagRename() {
  tagRenameValue.value = managingTag.value ?? ''
}

async function saveTagRename() {
  const oldTag = managingTag.value
  if (!oldTag || busy.value) return
  const name = tagRenameValue.value.trim()
  if (!name) {
    tagRenameValue.value = oldTag
    return
  }
  if (name === oldTag) return
  if (chipTags.value.includes(name)) {
    error.value = '已有同名标签'
    tagRenameValue.value = oldTag
    return
  }
  // 标签池和所有素材上的标签一起改名
  tagPool.value = tagPool.value.map(t => (t === oldTag ? name : t))
  for (const entry of Object.values(entries.value)) {
    if (entry.tags?.includes(oldTag)) entry.tags = entry.tags.map(t => (t === oldTag ? name : t))
  }
  managingTag.value = name
  tagRenameValue.value = name
  if (tagFilter.value === oldTag) tagFilter.value = name
  busy.value = true
  error.value = ''
  const ok = await writeIndex()
  busy.value = false
  if (ok) for (const rel of Object.keys(entries.value)) syncItemMeta(rel)
  else await loadIndex()
}

/** 把标签挪到标签池的指定位置，成功与否都保证内存顺序和磁盘一致 */
async function moveTagTo(from: number, to: number) {
  if (from === to || from < 0 || to < 0 || from >= tagPool.value.length || to >= tagPool.value.length) return
  const list = [...tagPool.value]
  const [moved] = list.splice(from, 1)
  list.splice(to, 0, moved)
  tagPool.value = list
  error.value = ''
  if (!(await writeIndex())) await loadIndex()
}

async function deleteManagingTag() {
  const tag = managingTag.value
  if (!tag) return
  managingTag.value = null
  tagRenameValue.value = ''
  await removeTag(tag)
}

// ─── 标签拖拽排序（仅管理模式） ───

const tagDragName = ref<string | null>(null)
/** 拖拽经过哪个标签、落在它的前还是后（用于画插入线） */
const tagDropSlot = ref<{ target: string; before: boolean } | null>(null)

function resetTagDrag() {
  tagDragName.value = null
  tagDropSlot.value = null
}

function onTagDragStart(tag: string, e: DragEvent) {
  if (!tagPanelOpen.value) return
  tagDragName.value = tag
  tagDropSlot.value = null
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', tag)
  }
}

function onTagDragOver(tag: string, e: DragEvent) {
  if (!tagPanelOpen.value || !tagDragName.value) return
  // 拖到自己身上：不画插入线
  if (tagDragName.value === tag) {
    tagDropSlot.value = null
    return
  }
  e.preventDefault()
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  tagDropSlot.value = { target: tag, before: e.clientX < rect.left + rect.width / 2 }
}

function onTagDragLeave(tag: string, e: DragEvent) {
  const el = e.currentTarget as HTMLElement
  if (e.relatedTarget && el.contains(e.relatedTarget as Node)) return
  if (tagDropSlot.value?.target === tag) tagDropSlot.value = null
}

async function onTagDrop(tag: string, e: DragEvent) {
  const dragged = tagDragName.value
  if (!tagPanelOpen.value || !dragged) return
  e.preventDefault()
  const slot = tagDropSlot.value?.target === tag ? tagDropSlot.value.before : true
  resetTagDrag()
  if (dragged === tag) return

  const from = tagPool.value.indexOf(dragged)
  const targetIdx = tagPool.value.indexOf(tag)
  if (targetIdx < 0) return

  // 拖拽的标签还不在池里（历史素材带过来的）：先插到目标位置
  if (from < 0) {
    const list = [...tagPool.value]
    list.splice(slot ? targetIdx : targetIdx + 1, 0, dragged)
    tagPool.value = list
    error.value = ''
    if (!(await writeIndex())) await loadIndex()
    return
  }

  const dropSlot = slot ? targetIdx : targetIdx + 1
  await moveTagTo(from, from < dropSlot ? dropSlot - 1 : dropSlot)
}

// ─── 单个改名 ───

/** 文件名校验：返回错误原因或 null（防抖保存时静默用，避免每敲一个字符就弹错） */
function validateFileName(base: string): string | null {
  if (!base) return '文件名不能为空'
  if (/[\\/:*?"<>|]/.test(base)) return '文件名不能包含 \\ / : * ? " < > |'
  const item = singleItem.value
  if (!item) return null
  const newRel = buildItemRel(item, base)
  if (store.items.some(i => i.category === activeCategory.value && i.rel === newRel)) return '同目录已有同名文件'
  return null
}

/** 输入即改：合法时防抖自动保存；不合法先不保存，等结束输入（blur / 回车）再提示原因 */
function onFileNameInput() {
  if (fileNameTimer) clearTimeout(fileNameTimer)
  fileNameTimer = null
  const base = fileInput.value.trim()
  if (!base || validateFileName(base)) return
  fileNameTimer = setTimeout(() => {
    fileNameTimer = null
    saveFileName()
  }, 400)
}

async function saveFileName() {
  if (fileNameTimer) {
    clearTimeout(fileNameTimer)
    fileNameTimer = null
  }
  const item = singleItem.value
  if (!item) return
  const base = fileInput.value.trim()
  const currentBase = item.file.replace(/[.][^.]+$/, '')
  if (!base) {
    fileInput.value = currentBase
    return
  }
  if (base === currentBase) return
  const invalid = validateFileName(base)
  if (invalid) {
    error.value = invalid
    return
  }
  const newRel = buildItemRel(item, base)

  if (!(await moveOne(item.rel, newRel))) return
  // 显示名直接跟随文件名：不再单独维护中文名
  const pin = await computePinyin(base)
  const meta = ensureEntry(newRel)
  meta.name = base
  meta.py = pin.py
  meta.pyi = pin.pyi
  if (await writeIndex()) syncItemMeta(newRel)
}
</script>

<template>
  <div class="studio" :style="{ '--thumb-size': `${THUMB_SIZE}px`, '--list-thumb-size': `${LIST_THUMB_SIZE}px` }">
    <!-- 工具栏 -->
    <div class="bar">
      <button
        v-for="cat in CATEGORIES"
        :key="cat.id"
        class="tab"
        :class="{ 'tab-on': activeCategory === cat.id }"
        :disabled="busy"
        @click="activeCategory = cat.id"
      >{{ cat.label }}</button>
      <input v-model="searchQuery" class="search" placeholder="搜索名字 / 拼音 / 标签" />
      <button class="btn" @click="selectAllVisible">全选</button>
      <button class="btn" @click="clearSelection">清空</button>
      <label class="multi">
        <input v-model="multiSelect" type="checkbox" class="multi-check" />
        多选
      </label>
      <span class="count">已选 {{ selectedRels.length }} / {{ filtered.length }}</span>
      <div class="spacer" />
      <button class="btn" :disabled="busy" @click="importAssets">添加资源</button>
      <button
        class="btn"
        :disabled="busy || selectedRels.length === 0 || isSpriteScope || activeCategory === 'images'"
        :title="isSpriteScope ? '绘制测试只支持地图图块 / 集合素材' : activeCategory === 'images' ? '绘制测试只支持图块 / 集合素材' : '带着选中图块进入地图编辑器临时试画'"
        @click="startDrawTest"
      >绘制测试</button>
      <button class="btn" :disabled="busy" @click="manualReload">重新加载</button>
      <button class="btn" :class="{ 'btn-on': viewMode === 'grid' }" @click="viewMode = 'grid'">图标</button>
      <button class="btn" :class="{ 'btn-on': viewMode === 'list' }" @click="viewMode = 'list'">列表</button>
      <button class="btn" @click="emit('close')">返回</button>
    </div>

    <!-- 分类筛选 -->
    <div v-if="groupOptions.length > 0" class="groups">
      <button class="chip" :class="{ 'chip-on': activeGroup === null }" @click="activeGroup = null">全部</button>
      <button
        v-for="group in groupOptions"
        :key="group"
        class="chip"
        :class="{ 'chip-on': activeGroup === group }"
        @click="activeGroup = activeGroup === group ? null : group"
      >{{ group }}</button>
    </div>

    <div class="body">
      <!-- 图标模式：大缩略图 -->
      <div v-if="viewMode === 'grid'" class="grid">
        <div
          v-for="item in filtered"
          :key="item.rel"
          class="card"
          :class="{ 'card-on': isSelected(item.rel) }"
          draggable="true"
          @click="onItemClick(item.rel, $event)"
          @contextmenu.prevent="openItemMenu(item, $event)"
          @dragstart="onAssetDragStart(item, $event)"
          @dragend="onAssetDragEnd"
        >
          <input
            type="checkbox"
            class="check"
            :checked="isSelected(item.rel)"
            @click.stop="toggle(item.rel)"
          />
          <div class="card-thumb">
            <img class="thumb-img" :src="item.thumbnail" loading="lazy" draggable="false" :data-rel="item.rel" @load="onThumbLoad" />
          </div>
          <div class="card-name">{{ item.name }}</div>
          <div class="card-meta">{{ itemDirLabel(item) }} · {{ item.file }}</div>
        </div>
        <div v-if="filtered.length === 0" class="empty">没有素材</div>
      </div>

      <!-- 列表模式 -->
      <div v-else class="list">
        <div class="row row-head">
          <span class="col-check" />
          <span class="col-thumb-head" />
          <span class="col-name sortable" @click="toggleSort('name')">名字{{ sortArrow('name') }}</span>
          <span class="col-group sortable" @click="toggleSort('dir')">目录{{ sortArrow('dir') }}</span>
          <span class="col-size sortable" @click="toggleSort('size')">尺寸{{ sortArrow('size') }}</span>
          <span class="col-tags">标签</span>
        </div>
        <div
          v-for="item in filtered"
          :key="item.rel"
          class="row"
          :class="{ 'row-on': isSelected(item.rel) }"
          draggable="true"
          @click="onItemClick(item.rel, $event)"
          @contextmenu.prevent="openItemMenu(item, $event)"
          @dragstart="onAssetDragStart(item, $event)"
          @dragend="onAssetDragEnd"
        >
          <input
            type="checkbox"
            class="check col-check"
            :checked="isSelected(item.rel)"
            @click.stop="toggle(item.rel)"
          />
          <span class="col-thumb">
            <img class="thumb-img" :src="item.thumbnail" loading="lazy" draggable="false" :data-rel="item.rel" @load="onThumbLoad" />
          </span>
          <span class="col-name" :title="item.name">{{ item.name }}</span>
          <span class="col-group">{{ itemDirLabel(item) }}</span>
          <span class="col-size">{{ item.width != null ? `${item.width}×${item.height}` : '—' }}</span>
          <span class="col-tags">
            <span v-for="tag in item.tags" :key="tag" class="mini-tag">{{ tag }}</span>
          </span>
        </div>
        <div v-if="filtered.length === 0" class="empty">没有素材</div>
      </div>

      <!-- 右侧操作面板：文件 → 标签 -->
      <div class="panel">
        <div v-if="error" class="msg err">{{ error }}</div>

        <!-- 1. 文件：文件名 + 分类（下拉选完直接移动） -->
        <div class="panel-card">
          <div class="panel-card-title">文件</div>
          <div v-if="singleItem" class="field">
            <label>文件名</label>
            <input
              v-model="fileInput"
              class="input"
              @input="onFileNameInput"
              @blur="saveFileName"
              @keydown.enter="($event.target as HTMLInputElement).blur()"
            />
          </div>
          <div class="field" :class="{ last: isSpriteScope || !folderPanelOpen }">
            <div class="field-head">
              <label>分类</label>
              <button
                v-if="!isSpriteScope"
                class="icon-btn gear"
                :class="{ 'gear-on': folderPanelOpen }"
                :title="folderPanelOpen ? '收起分类管理' : '分类管理'"
                @click="toggleFolderPanel"
              >
                <img :src="iconSettings" alt="" draggable="false" />
              </button>
            </div>
            <div class="inline">
              <CustomSelect
                v-model="groupTarget"
                class="group-select"
                :options="groupSelectOptions"
                :disabled="busy || selectedRels.length === 0"
              />
              <button
                class="icon-btn move-btn"
                title="移到所选分类"
                :disabled="moveDisabled"
                @click="applyGroup(groupTarget)"
              >
                <img :src="iconMove" alt="" draggable="false" />
              </button>
            </div>
          </div>

          <!-- 分类管理：点设置按钮后向下展开（角色素材只有角色/道具两个目录，不需要子分类） -->
          <div v-if="folderPanelOpen && !isSpriteScope" class="folder-manager">
            <p v-if="folders.length === 0 && !creatingFolder" class="panel-card-hint">还没有分类</p>

            <div
              v-for="(name, index) in folders"
              :key="name"
              class="folder-row"
              :class="{
                'folder-drop': assetOverFolder === name,
                'folder-dragging': folderDragName === name,
                'insert-before': folderDragName !== null && folderDragName !== name && folderDropIndex === index,
                'insert-after': folderDragName !== null && folderDragName !== name && folderDropIndex === index + 1 && index === folders.length - 1,
              }"
              :draggable="renamingFolder !== name && confirmDeleteFolder !== name"
              @dragstart="onFolderDragStart(name, $event)"
              @dragend="resetFolderDrag"
              @dragover="onFolderRowDragOver(name, index, $event)"
              @dragleave="onFolderRowDragLeave(name, $event)"
              @drop="onFolderRowDrop(name, index, $event)"
            >
              <template v-if="renamingFolder === name">
                <input
                  :ref="el => { if (el) renameInputEl = el as HTMLInputElement }"
                  v-model="renameFolderInput"
                  class="input"
                  @keydown.enter="applyRenameFolder(name)"
                  @keydown.esc="renamingFolder = null"
                />
                <button class="btn tiny" :disabled="busy" @click="applyRenameFolder(name)">确定</button>
                <button class="btn tiny" @click="renamingFolder = null">取消</button>
              </template>
              <template v-else-if="confirmDeleteFolder === name">
                <span class="folder-confirm">
                  {{ folderItemCount(name) > 0 ? `把 ${folderItemCount(name)} 个素材移回未分类？` : '删除这个空分类？' }}
                </span>
                <button class="btn tiny" @click="confirmDeleteFolder = null">取消</button>
                <button class="btn tiny danger" :disabled="busy" @click="deleteFolder(name)">删除</button>
              </template>
              <template v-else>
                <span class="folder-name" :title="name">{{ name }}</span>
                <span class="folder-count">{{ folderItemCount(name) }}</span>
                <span class="folder-actions">
                  <button class="icon-btn" title="改名" @click="startRenameFolder(name)">
                    <img :src="iconEdit" alt="" draggable="false" />
                  </button>
                  <button class="icon-btn" title="删除" @click="askDeleteFolder(name)">
                    <img :src="iconDelete" alt="" draggable="false" />
                  </button>
                </span>
              </template>
            </div>

            <!-- 未分类：只作素材的投放目标（移回根目录），不参与排序和管理 -->
            <div
              class="folder-row folder-static"
              :class="{ 'folder-drop': assetOverFolder === UNGROUPED }"
              @dragover="onUngroupedDragOver"
              @dragleave="onUngroupedDragLeave"
              @drop="onUngroupedDrop"
            >
              <span class="folder-name">{{ UNGROUPED }}</span>
              <span class="folder-count">{{ folderItemCount(UNGROUPED) }}</span>
            </div>

            <div v-if="creatingFolder" class="folder-row">
              <input
                ref="newFolderInputEl"
                v-model="newFolderInput"
                class="input"
                placeholder="分类名，回车创建"
                @keydown.enter="createFolder"
                @keydown.esc="cancelCreateFolder"
              />
              <button class="btn tiny" :disabled="busy" @click="createFolder">创建</button>
              <button class="btn tiny" @click="cancelCreateFolder">取消</button>
            </div>
            <button v-else class="folder-add" @click="startCreateFolder">+ 新建分类</button>
          </div>
        </div>

        <!-- 1.5 图块尺寸：只对「集合」页签生效，设定后导入地图按此尺寸切图 -->
        <div v-if="showTileSizeCard" class="panel-card">
          <div class="panel-card-title">图块尺寸</div>
          <div class="field last">
            <div class="field-head">
              <label>每格边长（像素）</label>
              <span v-if="tileSizeStatus" class="field-status">{{ tileSizeStatus }}</span>
            </div>
            <CustomSelect
              :model-value="tileSizeInput"
              :options="TILE_SIZE_OPTIONS"
              :disabled="busy || selectedTilesets.length === 0"
              @update:model-value="onTileSizeChange"
            />
            <p class="panel-card-hint">
              选择后立即生效；设定后把该集合放进图块图层时按这个尺寸切图。
            </p>
          </div>
        </div>

        <!-- 2. 标签：常驻显示；未选中素材时禁用点击，但能看到标签池 -->
        <div class="panel-card tags-card">
          <div class="panel-card-head">
            <span class="panel-card-title">标签</span>
            <button
              class="icon-btn gear"
              :class="{ 'gear-on': tagPanelOpen }"
              :title="tagPanelOpen ? '收起标签管理' : '标签管理'"
              @click="toggleTagPanel"
            >
              <img :src="iconSettings" alt="" draggable="false" />
            </button>
          </div>
          <input v-model="tagFilter" class="input tag-filter" placeholder="筛选标签" />
          <!-- 管理模式：点标签是「选中管理」，普通模式：点标签是给素材打上/去掉 -->
          <div class="tags" :class="{ 'tags-manage': tagPanelOpen }">
            <button
              v-for="tag in visibleTags"
              :key="tag"
              class="tag"
              :class="[
                tagPanelOpen
                  ? { 'tag-manage-on': managingTag === tag }
                  : { 'tag-all': tagAll(tag), 'tag-part': !tagAll(tag) && tagSome(tag) },
                tagPanelOpen && tagDragName
                  ? {
                      'tag-dragging': tagDragName === tag,
                      'tag-insert-before': tagDragName !== tag && tagDropSlot?.target === tag && tagDropSlot?.before,
                      'tag-insert-after': tagDragName !== tag && tagDropSlot?.target === tag && !tagDropSlot?.before,
                    }
                  : {},
              ]"
              :disabled="busy || (!tagPanelOpen && selectedRels.length === 0)"
              :draggable="tagPanelOpen"
              @click="tagPanelOpen ? selectManagingTag(tag) : toggleTagOnSelection(tag)"
              @dragstart="onTagDragStart(tag, $event)"
              @dragend="resetTagDrag"
              @dragover="onTagDragOver(tag, $event)"
              @dragleave="onTagDragLeave(tag, $event)"
              @drop="onTagDrop(tag, $event)"
            >{{ tag }}</button>
            <span v-if="visibleTags.length === 0" class="panel-card-hint">
              {{ chipTags.length === 0 ? '还没有标签' : '没有匹配的标签' }}
            </span>
          </div>

          <!-- 标签管理：选中标签后可改名 / 拖动排序 / 删除 -->
          <div v-if="tagPanelOpen" class="folder-manager">
            <div v-if="managingTag" class="inline tag-manage-row">
              <input
                v-model="tagRenameValue"
                class="input"
                placeholder="标签名"
                @keydown.enter="saveTagRename"
                @keydown.esc="cancelTagRename"
                @blur="saveTagRename"
              />
              <button class="btn tiny danger" :disabled="busy" @mousedown.prevent @click="deleteManagingTag">删除</button>
            </div>
            <div class="inline">
              <input v-model="tagInput" class="input" placeholder="新标签名，回车添加" @keydown.enter="addTag" />
              <button class="btn tiny" :disabled="busy" @click="addTag">添加</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 右键菜单：图块/素材右键删除 -->
    <Teleport to="body">
      <div
        v-if="ctxMenu"
        class="ctx-menu"
        :style="{ left: `${ctxMenu.x}px`, top: `${ctxMenu.y}px` }"
        @pointerdown.stop
        @contextmenu.prevent
      >
        <button class="danger" @click="deleteItem(ctxMenu.rel)">删除</button>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.studio {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-root);
  color: var(--text-secondary);
  font-size: 12px;
}

.bar {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 40px;
  padding: 0 8px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
  scrollbar-width: none;
}

.bar::-webkit-scrollbar {
  display: none;
}

.tab,
.btn {
  height: 26px;
  padding: 0 10px;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.tab:hover,
.btn:hover {
  background: var(--bg-hover);
  color: white;
}

.tab-on,
.btn-on {
  background: rgb(46, 49, 58);
  border-color: var(--accent);
  color: var(--accent);
}

.btn[disabled],
.tab[disabled] {
  opacity: 0.5;
  cursor: default;
}

.search {
  width: 260px;
  min-width: 260px;
  flex-shrink: 0;
  height: 26px;
  padding: 0 8px;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  outline: none;
}

.search:focus {
  border-color: var(--accent);
}

.count {
  color: #8a8f93;
  white-space: nowrap;
  flex-shrink: 0;
}

.multi {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-secondary);
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
}

.multi-check {
  accent-color: #5bfb84;
  cursor: pointer;
}

.spacer {
  flex: 1;
}

.groups {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 8px;
  flex-shrink: 0;
  overflow-x: auto;
  scrollbar-width: none;
}

.groups::-webkit-scrollbar {
  display: none;
}

.chip {
  height: 24px;
  padding: 0 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  color: #9ca0a4;
  font-size: 12px;
  white-space: nowrap;
  cursor: pointer;
}

.chip:hover {
  background: var(--bg-hover);
  color: white;
}

.chip-on {
  background: rgb(46, 49, 58);
  border-color: var(--border-light);
  color: white;
}

.body {
  flex: 1;
  min-height: 0;
  display: flex;
}

/* ─── 图标模式 ─── */
.grid {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  padding: 10px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  grid-auto-rows: max-content;
  gap: 10px;
  align-content: start;
}

.card {
  position: relative;
  background: rgb(45, 45, 45);
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
}

.card:hover {
  background: rgb(60, 60, 60);
}

.card-on {
  border-color: var(--accent);
  background: rgb(56, 58, 64);
}

.card-thumb {
  width: var(--thumb-size);
  height: var(--thumb-size);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: rgb(38, 38, 38);
  border-radius: 4px;
  margin: 0 auto 8px;
}

.card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  image-rendering: pixelated;
}

.card-name {
  color: white;
  font-size: 12px;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  color: #8a8f93;
  font-size: 11px;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 2px;
}

.check {
  cursor: pointer;
  accent-color: #5bfb84;
}

.card > .check {
  position: absolute;
  top: 12px;
  left: 12px;
  width: 14px;
  height: 14px;
}

/* ─── 列表模式 ─── */
.list {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: auto;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-bottom: 1px solid rgb(50, 50, 50);
  cursor: pointer;
}

.row:hover {
  background: rgb(52, 54, 58);
}

.row-on {
  background: rgb(56, 58, 64);
  box-shadow: inset 2px 0 0 var(--accent);
}

.row-head {
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--bg-panel);
  color: #8a8f93;
  cursor: default;
}

.col-check {
  width: 16px;
  flex: none;
}

.col-thumb {
  width: var(--list-thumb-size);
  height: var(--list-thumb-size);
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: rgb(38, 38, 38);
  border-radius: 4px;
}

/* 表头只占位、不显示缩略图方框 */
.col-thumb-head {
  width: var(--list-thumb-size);
  flex: none;
}

.col-thumb img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  image-rendering: pixelated;
}

.col-name {
  width: 240px;
  flex: none;
  color: white;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sortable {
  cursor: pointer;
  user-select: none;
}

.sortable:hover {
  color: var(--accent);
}

.col-group {
  width: 90px;
  flex: none;
  color: #9ca0a4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-size {
  width: 90px;
  flex: none;
  color: #9ca0a4;
  font-variant-numeric: tabular-nums;
  text-align: right;
  padding-right: 8px;
}

.col-tags {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.mini-tag {
  padding: 0 6px;
  border: 1px solid var(--border-light);
  border-radius: 3px;
  color: #8a8f93;
  font-size: 11px;
  line-height: 18px;
}

.empty {
  grid-column: 1 / -1;
  padding: 40px;
  text-align: center;
  color: #7c8084;
}

/* ─── 操作面板 ─── */
.panel {
  width: 320px;
  min-width: 320px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 10px;
  background: var(--bg-panel);
  border-left: 1px solid var(--border);
}

/* 同业务逻辑的先并成一张卡片，避免控件平铺成一长串 */
.panel-card {
  background: rgb(38, 40, 46);
  border: 1px solid rgb(52, 55, 60);
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 10px;
}

/* 标签卡片占满面板剩余高度，标签多了在卡片内滚动 */
.tags-card {
  flex: 1;
  min-height: 220px;
  display: flex;
  flex-direction: column;
}

/* 卡片标题行：标题左、设置按钮右 */
.panel-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-bottom: 8px;
}

.panel-card-head .panel-card-title {
  margin-bottom: 0;
}

.panel-card-title {
  color: #e6e6e6;
  font-size: 12px;
  margin-bottom: 8px;
}

/* 卡片内的表单行：小标签在上，控件在下 */
.field {
  margin-bottom: 8px;
}

.field.last {
  margin-bottom: 0;
}

.field > label {
  display: block;
  margin-bottom: 6px;
  color: #9ca0a4;
  font-size: 11px;
}

/* 字段标题行：左侧小标签，右侧放图标按钮（如分类管理齿轮） */
.field-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-bottom: 6px;
}

.field-head > label {
  color: #9ca0a4;
  font-size: 11px;
}

/* 字段标题右侧的状态文字（如「已设定 32×32」） */
.field-status {
  color: #7c8084;
  font-size: 11px;
}

.field > .inline {
  margin-top: 0;
}

/* 文件名输入框右侧留出设置按钮的宽度，和下方分类下拉的左右边缘对齐 */
.field > .input {
  width: calc(100% - 28px);
}

/* 分类下拉：自绘菜单（与项目其它下拉风格一致），高度对齐文件名输入框 */
.inline > .group-select {
  flex: 1;
  min-width: 0;
  height: 26px;
}

/* 分类很多时菜单自身滚动，避免超出面板被裁 */
.group-select :deep(.custom-select-dropdown) {
  max-height: 240px;
  overflow-y: auto;
}

.panel-card-hint {
  margin: 6px 0 0;
  color: #7c8084;
  font-size: 11px;
  line-height: 1.5;
}

.inline {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}

.input {
  flex: 1;
  min-width: 0;
  height: 26px;
  padding: 0 8px;
  background: var(--bg-root);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  outline: none;
}

.input:focus {
  border-color: var(--accent);
}

.tags {
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 6px;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  margin: 8px 0 6px;
}

/* 筛选框固定在标签标题下方一行，别被卡片的纵向 flex 拉高 */
.tag-filter {
  width: 100%;
  flex: none;
}

.tag {
  position: relative;
  height: 24px;
  padding: 0 8px;
  background: transparent;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: #9ca0a4;
  font-size: 12px;
  cursor: pointer;
}

/* 标签管理模式：标签可拖动排序 */
.tag[draggable='true'] {
  cursor: grab;
  user-select: none;
}

.tag-dragging {
  opacity: 0.4;
}

/* 标签排序的插入线（竖直） */
.tag-insert-before::before,
.tag-insert-after::after {
  content: '';
  position: absolute;
  top: 1px;
  bottom: 1px;
  width: 2px;
  background: var(--accent);
  border-radius: 1px;
  pointer-events: none;
}

.tag-insert-before::before {
  left: -4px;
}

.tag-insert-after::after {
  right: -4px;
}

.tag:hover {
  background: var(--bg-hover);
  color: white;
}

.tag-all {
  background: rgb(46, 49, 58);
  border-color: var(--accent);
  color: var(--accent);
}

/* 部分选中：虚线边框，一眼能看出不是所有选中项都有这个标签 */
.tag-part {
  border-style: dashed;
  border-color: var(--accent);
  color: var(--accent);
}

/* 标签管理模式下被选中的标签 */
.tag-manage-on {
  background: rgb(46, 49, 58);
  border-color: var(--accent);
  color: var(--accent);
}

.tag-manage-row {
  margin-bottom: 6px;
}

.msg {
  margin: 0 0 10px;
  line-height: 1.5;
}

.err {
  color: #e06c5a;
}

/* ─── 分类管理 ─── */

/* 设置按钮：展开中时用强调色，一眼能看出面板已打开 */
.gear {
  width: 22px;
  height: 22px;
}

/* 移动按钮：和下拉同一行，宽度与齿轮一致，保证上下两行右边缘对齐 */
.move-btn {
  width: 22px;
  height: 22px;
  flex: none;
}

.gear-on {
  background: rgb(46, 49, 58);
  box-shadow: inset 0 0 0 1px var(--accent);
}

/* 展开区：与上面的下拉用虚线分隔，明确是「管理」而不是「移动」 */
.folder-manager {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px dashed rgb(58, 61, 68);
}

.folder-row {
  position: relative;
  display: flex;
  align-items: center;
  gap: 4px;
  height: 28px;
  padding: 0 6px;
  border-radius: 4px;
}

/* 可拖排序的行给抓取手势；改名/删除确认状态下不可拖，光标保持默认 */
.folder-row[draggable='true'] {
  cursor: grab;
  user-select: none;
}

.folder-row:hover {
  background: var(--bg-hover);
}

/* 正在被拖走的行：压低透明度当占位 */
.folder-dragging {
  opacity: 0.35;
}

/* 素材拖上来：与普通选中样式一致（背景 + 左侧强调条） */
.folder-drop {
  background: rgb(56, 58, 64);
  box-shadow: inset 2px 0 0 var(--accent);
}

/* 排序插入指示线 */
.insert-before::before,
.insert-after::after {
  content: '';
  position: absolute;
  left: 2px;
  right: 2px;
  height: 2px;
  background: var(--accent);
  border-radius: 1px;
  pointer-events: none;
}

.insert-before::before {
  top: -1px;
}

.insert-after::after {
  bottom: -1px;
}

/* 未分类：伪分类，弱化显示，与真实分类用分割线隔开 */
.folder-static {
  margin-top: 4px;
  border-top: 1px solid rgb(50, 50, 50);
  border-radius: 0 0 4px 4px;
  color: #9ca0a4;
}

.folder-static:hover {
  background: var(--bg-hover);
}

.folder-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-count {
  color: #7c8084;
  font-size: 11px;
}

/* 改名 / 删除图标：只在行 hover 时出现，平时保持列表干净 */
.folder-actions {
  display: none;
  align-items: center;
  gap: 2px;
}

.folder-row:hover .folder-actions {
  display: flex;
}

.icon-btn {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 3px;
  cursor: pointer;
}

.icon-btn:hover {
  background: rgb(70, 72, 78);
}

.icon-btn:disabled {
  opacity: 0.35;
  cursor: default;
}

.icon-btn:disabled:hover {
  background: transparent;
}

.icon-btn img {
  width: 13px;
  height: 13px;
  pointer-events: none;
}

.folder-confirm {
  flex: 1;
  min-width: 0;
  color: #e06c5a;
  font-size: 11px;
  line-height: 1.4;
}

/* 新建分类：虚线按钮行，点击展开成输入行 */
.folder-add {
  width: 100%;
  height: 26px;
  margin-top: 4px;
  background: transparent;
  border: 1px dashed var(--border-light);
  border-radius: 4px;
  color: #9ca0a4;
  font-size: 12px;
  cursor: pointer;
}

.folder-add:hover {
  background: var(--bg-hover);
  color: white;
  border-style: solid;
}

.btn.tiny {
  height: 22px;
  padding: 0 6px;
  font-size: 11px;
}

.danger {
  color: #e06c5a;
}

.danger:hover {
  border-color: #5f2d27;
}

/* 右键菜单（Teleport 到 body，靠 scoped 属性挂样式） */
.ctx-menu {
  position: fixed;
  z-index: 1000;
  min-width: 88px;
  padding: 3px;
  background: rgb(48, 50, 56);
  border: 1px solid rgb(70, 72, 78);
  border-radius: 5px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.45);
}

.ctx-menu button {
  display: block;
  width: 100%;
  padding: 5px 10px;
  background: transparent;
  border: none;
  border-radius: 3px;
  color: #e6e6e6;
  font-size: 12px;
  text-align: left;
  cursor: pointer;
}

.ctx-menu button:hover {
  background: var(--bg-hover);
}

.ctx-menu button.danger {
  color: #e06c5a;
}
</style>
