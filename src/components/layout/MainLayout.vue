<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { open, save, ask } from '@tauri-apps/plugin-dialog'
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow'
import JSZip from 'jszip'
import { useEditorStore } from '../../stores/editor'
import { useResourceStore } from '../../stores/resource'
import { useProjectStore } from '../../stores/project'
import { useMapStore } from '../../stores/map'
import { useRenderStore } from '../../stores/render'
import { useTerminalStore } from '../../stores/terminal'
import { useEngine } from '../../composables/useEngine'
import { useFileDialog } from '../../composables/useFileDialog'
import GameCanvas from '../canvas/GameCanvas.vue'
import CodeEditor from '../editor/CodeEditor.vue'
import SpriteEditorView from '../sprite-editor/SpriteEditorView.vue'
import MapEditorView from '../map-editor/MapEditorView.vue'
import TerminalPanel from '../terminal/TerminalPanel.vue'
import UploadDrawer from '../resource-panel/UploadDrawer.vue'
import SpriteLibPage from '../resource-panel/SpriteLibPage.vue'
import MapLibraryPage from '../resource-panel/MapLibraryPage.vue'
import MapResourceLibPage from '../resource-panel/MapResourceLibPage.vue'
import SoundLibPage from '../resource-panel/SoundLibPage.vue'
import PaintEditorPage from '../paint-editor/PaintEditorPage.vue'
import FramePickerPage from '../resource-panel/FramePickerPage.vue'
import { appendFramesToSprite } from '../../composables/appendSpriteFrames'
import HelpPanel from '../help/HelpPanel.vue'
import PythonHelpPanel from '../help/PythonHelpPanel.vue'
import AiChatPanel from '../help/AiChatPanel.vue'
import { openHelpDocs } from '../help/HelpDocsOpener'
import PluginManager from '../common/PluginManager.vue'
import UpdateDialog from '../common/UpdateDialog.vue'
import FileExplorer from '../file-explorer/FileExplorer.vue'
import SnippetPanel from '../sidebar/SnippetPanel.vue'
import LearnPanel from '../sidebar/LearnPanel.vue'
import SearchPanel from '../sidebar/SearchPanel.vue'
import OutlinePanel from '../sidebar/OutlinePanel.vue'
import { useFileExplorerStore } from '../../stores/fileExplorer'
import iconLogo from '../../assets/icons/logo.svg'
import iconFile from '../../assets/icons/icon--file.svg'
import iconCodeEdit from '../../assets/icons/代码编辑.svg'
import iconSprite from '../../assets/icons/角色精灵.svg'
import iconMap from '../../assets/icons/addons.svg'
import iconNewMap from '../../assets/icons/新建地图.svg'
import iconCodeOpen from '../../assets/icons/codemode_打开.svg'
import iconCodeSave from '../../assets/icons/codemode_保存.svg'
import iconCodeRun from '../../assets/icons/codemode_运行.svg'
import iconCodeStop from '../../assets/icons/codemode_停止.svg'
import iconSettings from '../../assets/icons/icon--settings.svg'
import iconHelp from '../../assets/icons/help.svg'
import iconPlay from '../../assets/icons/icon--play.svg'
import iconStop from '../../assets/icons/icon--stop-all.svg'
import iconFullscreen from '../../assets/icons/icon--fullscreen.svg'
import iconUnfullscreen from '../../assets/icons/icon--unfullscreen.svg'
import iconFps from '../../assets/icons/fps.svg'
import iconCollision from '../../assets/icons/hitbox.svg'
import iconStats from '../../assets/icons/performance.svg'
import iconPython from '../../assets/icons/python_file_1.svg'
import iconUndo from '../../assets/icons/undo.svg'
import iconRedo from '../../assets/icons/redo.svg'
import iconSoundIcon from '../../assets/icons/sound_icon.svg'
import iconCodeFormat from '../../assets/icons/code_fomat.svg'
import iconAddOne from '../../assets/icons/add-one.svg'
import iconReduceOne from '../../assets/icons/reduce-one.svg'
import { useThemeStore } from '../../stores/theme'
import { normalizeSpriteThumb } from '../../utils/spriteThumb'

const editorStore = useEditorStore()
const resourceStore = useResourceStore()
const projectStore = useProjectStore()
const mapStore = useMapStore()
const renderStore = useRenderStore()
const terminalStore = useTerminalStore()
const themeStore = useThemeStore()
const fileExplorerStore = useFileExplorerStore()
const engine = useEngine()
const fileDialog = useFileDialog()

// loading进度
const loadingProgress = computed(() => {
  if (renderStore.textureTotal === 0) return 0
  return Math.floor((renderStore.textureLoaded / renderStore.textureTotal) * 100)
})

// change_page: 0=编辑器, 1=全屏, 2=地图库, 3=角色库, 4=素材库, 5=声音库, 6=角色绘制器, 7=造型选帧库
const currentPage = ref(0)
// 库页面用 v-show 常驻挂载，key 递增强制每次打开时重建组件：
// 重置默认 tab/分类，并让 onMounted 的目录重扫真正生效
const mapLibPageKey = ref(0)
const mapResLibPageKey = ref(0)
const spriteLibPageKey = ref(0)
const paintPageKey = ref(0)
const framePickerKey = ref(0)
/** 绘制页编辑目标（造型抽屉/双击帧时非空；资源抽屉「绘制角色」时为 null = 新建） */
const paintTarget = ref<{ id: string; name: string; path: string } | null>(null)
/** 绘制页打开方式：edit = 双击帧（选中该帧）；newFrame = 抽屉（自动新建空白帧） */
const paintOpenMode = ref<'edit' | 'newFrame'>('newFrame')
const paintInitialFrameIndex = ref(0)
/** 角色编辑器实例：追加帧后强制重载帧列表 */
const spriteEditorRef = ref<{ reload: () => Promise<void> } | null>(null)
watch(currentPage, (page) => {
  if (page === 2) mapLibPageKey.value++
  else if (page === 4) mapResLibPageKey.value++
  else if (page === 3) spriteLibPageKey.value++
  else if (page === 6) paintPageKey.value++
  else if (page === 7) framePickerKey.value++
})
// 控制台面板可见性：状态在 terminal store 中（引擎有输出自动弹出、手动停止收回）
const consoleVisible = computed({
  get: () => terminalStore.consoleVisible,
  set: (v) => { terminalStore.consoleVisible = v },
})
// 切换游戏/代码模式时自动停止运行中的程序，避免两套模式的运行状态串台
watch(() => editorStore.isGameMode, () => {
  if (editorStore.isRunning) {
    engine.stop()
  }
})
const canvasOffsetX = ref(0)
const consoleExpanded = ref(true)
const fileMenuVisible = ref(false)
const settingsMenuVisible = ref(false)
const settingsSubmenu = ref<string | null>(null)
const selectedResource = ref<string | null>(null)
const helpVisible = ref(false)
const aiChatVisible = ref(false)
const pluginManagerVisible = ref(false)
const ideExplorerVisible = ref(true)
const hasUpdate = ref(false)
const ideActivePanel = ref<'files' | 'search' | 'outline' | 'snippets' | 'learn'>('files')
const sidePanelWidth = ref(240)
const isResizingSidePanel = ref(false)

// 角色缩略图缓存（缩略图已按固定画布烤好，列表里再按格子尺寸缩小显示，走平滑即可）
const spriteThumbnails = ref<Record<string, string>>({})
// 地图缩略图缓存
const mapThumbnails = ref<Record<string, string>>({})
// 角色右键菜单
const spriteContextMenu = ref<{ show: boolean; x: number; y: number; item: { id: string; name: string } | null }>({ show: false, x: 0, y: 0, item: null })
const spriteRenameId = ref<string | null>(null)

// 代码资源管理
const codeContextMenu = ref<{ show: boolean; x: number; y: number; item: { id: string; name: string } | null }>({ show: false, x: 0, y: 0, item: null })
const codeRenameId = ref<string | null>(null)

// 标签页右键菜单
const tabContextMenu = ref<{ show: boolean; x: number; y: number; index: number }>({ show: false, x: 0, y: 0, index: -1 })

function onTabContextMenu(e: MouseEvent, index: number) {
  e.preventDefault()
  e.stopPropagation()
  tabContextMenu.value = { show: true, x: e.clientX, y: e.clientY, index }
}

function closeTabCtxMenu() {
  tabContextMenu.value.show = false
}

function tabCtxClose() {
  const idx = tabContextMenu.value.index
  closeTabCtxMenu()
  editorStore.closeTab(idx)
}

function tabCtxCloseOthers() {
  const idx = tabContextMenu.value.index
  closeTabCtxMenu()
  editorStore.closeOtherTabs(idx)
}

function tabCtxCloseToRight() {
  const idx = tabContextMenu.value.index
  closeTabCtxMenu()
  editorStore.closeTabsToRight(idx)
}

function tabCtxCloseAll() {
  closeTabCtxMenu()
  editorStore.closeAllTabs()
}
const codeRenameValue = ref('')
const spriteRenameValue = ref('')

// 地图右键菜单
const mapContextMenu = ref<{ show: boolean; x: number; y: number; item: { id: string; name: string } | null }>({ show: false, x: 0, y: 0, item: null })
const mapRenameId = ref<string | null>(null)
const mapRenameValue = ref('')

// 声音右键菜单
const soundContextMenu = ref<{ show: boolean; x: number; y: number; item: { id: string; name: string } | null }>({ show: false, x: 0, y: 0, item: null })

// 角色列表变化时立即加载缩略图
async function loadAllSpriteThumbnails() {
  const promises = resourceStore.sprites
    .filter(item => item.path && !spriteThumbnails.value[item.id])
    .map(item => loadSpriteThumbnail(item))
  await Promise.all(promises)
}

watch(() => [...resourceStore.sprites], loadAllSpriteThumbnails)

onMounted(loadAllSpriteThumbnails)

// 地图缩略图：只在切换到地图标签时刷新（不用实时）
async function loadAllMapThumbnails() {
  const promises = resourceStore.maps
    .filter(item => item.path)
    .map(item => loadMapThumbnail(item))
  await Promise.all(promises)
}

// 判断文件名是否为图片扩展名（用于精灵资源重载时区分图片角色与 .bgs 目录）
const IMAGE_FILE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']
function isImageFileName(fileName: string): boolean {
  const lower = fileName.toLowerCase()
  return IMAGE_FILE_EXTS.some(ext => lower.endsWith(ext))
}

/**
 * 从工作目录预加载项目资源（代码/地图/精灵/声音）。
 * 供文件菜单"打开项目"成功后调用。
 * 调用前需保证 projectStore.root 已指向有效工作目录、旧数据已清空。
 */
async function loadProjectResources(root: string) {
  if (!root) return
  // 先切到代码模式再建标签，确保 createTab 把代码文件放进 codeTabs（与本函数结尾的最终状态一致）
  editorStore.setActiveEditorMode('code')
  editorStore.setResourceTab('sprite')

  // ── 预加载代码文件 ──
  try {
    const files = await invoke<string[]>('list_dir', { path: `${root}/code` })
    for (const file of files) {
      if (file.endsWith('.py')) {
        const content = await invoke<string>('read_file', { path: `${root}/code/${file}` })
        editorStore.createTab(file, `${root}/code/${file}`, content)
        resourceStore.addItem({ name: file, type: 'code', path: `${root}/code/${file}`, content })
      }
    }
  } catch { /* code 目录可能不存在 */ }

  // ── 预加载地图资源 ──
  try {
    const mapEntries = await invoke<string[]>('list_dir', { path: `${root}/assets/maps` })
    for (const entry of mapEntries) {
      const mapName = entry.replace(/\/$/, '')
      const jsonPath = `${root}/assets/maps/${mapName}/map.json`
      const exists = await invoke<boolean>('path_exists', { path: jsonPath })
      if (!exists) continue
      const json = await invoke<string>('read_file', { path: jsonPath })
      const saveData = JSON.parse(json)
      const { deserializeMap } = await import('../../utils/mapSerializer')
      const mapData = deserializeMap(saveData)
      const mapId = resourceStore.addItem({ name: mapName, type: 'map', path: `${root}/assets/maps/${mapName}` })
      resourceStore.setCachedMapData(mapId, mapData)
    }
  } catch { /* assets/maps 可能不存在 */ }

  // ── 预加载精灵资源 ──
  try {
    const spriteEntries = await invoke<string[]>('list_dir', { path: `${root}/assets/sprites` })
    for (const entry of spriteEntries) {
      const dirName = entry.replace(/\/$/, '')
      if (!dirName) continue
      const dirPath = `${root}/assets/sprites/${dirName}`
      // 图片角色（单文件）store 名去掉扩展名，与上传时的命名保持一致
      const name = isImageFileName(dirName) ? dirName.replace(/\.[^.]+$/, '') : dirName
      resourceStore.addItem({ name, type: 'sprite', path: dirPath })
    }
  } catch { /* assets/sprites 可能不存在 */ }

  // ── 预加载声音资源 ──
  try {
    const soundFiles = await invoke<string[]>('list_dir', { path: `${root}/assets/sounds` })
    for (const file of soundFiles) {
      if (file.endsWith('.wav') || file.endsWith('.mp3') || file.endsWith('.ogg')) {
        const name = file.replace(/\.\w+$/, '')
        resourceStore.addItem({ name, type: 'sound', path: `${root}/assets/sounds/${file}` })
      }
    }
  } catch { /* assets/sounds 可能不存在 */ }

  // 刷新缩略图（并行加载，不阻塞后续流程）
  Promise.all([loadAllSpriteThumbnails(), loadAllMapThumbnails()])

  // 切换到第一个代码标签（如有）
  if (editorStore.currentTabs.length > 0) {
    editorStore.setActiveTab(0)
  }
  // 确保回到主页面
  currentPage.value = 0
}

// 地图列表变化时不自动加载缩略图（改为切换标签时刷新）
watch(() => editorStore.resourceTab, (tab) => {
  if (tab === 'map') {
    // 切换到地图标签时刷新缩略图
    mapThumbnails.value = {}
    loadAllMapThumbnails()
  }
})

// 新增地图资源时立即加载缩略图（不需要等切换标签）
watch(() => resourceStore.maps.length, () => {
  if (editorStore.resourceTab === 'map') {
    loadAllMapThumbnails()
  }
})

// 监听编辑器模式切换（从地图编辑器返回时刷新）
watch(() => editorStore.activeEditorMode, (mode) => {
  if (mode !== 'map' && editorStore.resourceTab === 'map') {
    mapThumbnails.value = {}
    loadAllMapThumbnails()
  }
})

onMounted(loadAllMapThumbnails)

// 启动时静默检查更新，只显示圆点提示，不弹窗
// 窗口标题动态显示实际安装的版本号（读取 app bundle 元数据，更新后重启即反映新版本）
onMounted(async () => {
  try {
    const { getVersion } = await import('@tauri-apps/api/app')
    await getCurrentWebviewWindow().setTitle(`BingoCode IDE v${await getVersion()}`)
  } catch (_e) {
    // 静默失败，保留 tauri.conf.json 里的静态标题
  }
})

onMounted(async () => {
  try {
    const { check } = await import('@tauri-apps/plugin-updater')
    const update = await check()
    if (update) {
      hasUpdate.value = true
    }
  } catch (_e) {
    // 静默失败
  }
})

// 新项目不预创建地图，用户通过按钮创建
onMounted(async () => {
  const t0 = performance.now()
  themeStore.initTheme()
  await projectStore.initProject()

  // 启动永远是全新默认项目：清空编辑器残留状态。
  // default 目录每次启动都会被 init_default_project 清空，
  // localStorage 里恢复的旧标签都是指向已删文件的幽灵，全部丢弃。
  resourceStore.clearAllResources()
  renderStore.clearAll()
  editorStore.gameTabs.splice(0, editorStore.gameTabs.length)
  editorStore.codeTabs.splice(0, editorStore.codeTabs.length)
  editorStore.gameActiveTabIndex = 0
  editorStore.codeActiveTabIndex = 0

  // 创建默认空代码文件（与"新建项目"一致，只保留一个 未命名-1.py）
  if (projectStore.root) {
    const projectRoot = projectStore.root
    const name = '未命名-1.py'
    editorStore.setActiveEditorMode('code')
    await invoke('create_dir', { path: `${projectRoot}/code` })
    await invoke('write_file', { path: `${projectRoot}/code/${name}`, content: '' })
    editorStore.createTab(name, `${projectRoot}/code/${name}`, '')
    resourceStore.addItem({ name, type: 'code', path: `${projectRoot}/code/${name}`, content: '' })
  }
  console.log(`[Perf] Startup: ${(performance.now() - t0).toFixed(0)}ms`)
})

// 代码编辑器右键菜单事件
window.addEventListener('editor-run', () => { toggleRun() })
window.addEventListener('editor-format', () => { ideFormatCode() })
window.addEventListener('editor-save', () => { ideSaveFile() })
window.addEventListener('click', () => { closeTabCtxMenu() })
window.addEventListener('contextmenu', () => { closeTabCtxMenu() })

// 游戏模式：Cmd/Ctrl+S 保存项目（未保存过弹保存窗口，已保存过直接覆盖旧文件）
// Monaco 编辑器内按键被其自身命令拦截（不冒泡到 window），因此编辑器内
// 通过 game-save 事件、编辑器外通过 keydown 监听，两个入口汇合到这里
let _savingProject = false
async function runGameSave() {
  if (_savingProject) return
  _savingProject = true
  try {
    await fileMenuAction('save')
  } finally {
    _savingProject = false
  }
}
window.addEventListener('game-save', () => { runGameSave() })
function onGameSaveShortcut(e: KeyboardEvent) {
  if (!editorStore.isGameMode) return
  if (!(e.metaKey || e.ctrlKey) || e.key.toLowerCase() !== 's') return
  e.preventDefault()
  runGameSave()
}
onMounted(() => window.addEventListener('keydown', onGameSaveShortcut))
onUnmounted(() => window.removeEventListener('keydown', onGameSaveShortcut))

// 退出保护：有未保存代码时弹窗提示（Tauri 原生窗口关闭）
const appWindow = getCurrentWebviewWindow()
let pendingClose = false

appWindow.onCloseRequested(async (e) => {
  if (pendingClose) {
    return
  }
  if (editorStore.hasUnsavedTabs) {
    e.preventDefault()
    const shouldSave = await ask('有未保存的代码，是否保存？', { title: '未保存的代码', kind: 'warning' })
    if (shouldSave) {
      await editorStore.saveAllModifiedTabs()
    }
  }
  pendingClose = true
  await appWindow.close()
})

// 自动选中第一个资源
function autoSelectFirst() {
  const tab = editorStore.resourceTab
  if (tab === 'sprite') {
    if (resourceStore.sprites.length > 0 && !resourceStore.selectedSpriteId) {
      resourceStore.selectedSpriteId = resourceStore.sprites[0].id
    }
  } else if (tab === 'map') {
    if (resourceStore.maps.length > 0 && !selectedResource.value) {
      selectedResource.value = resourceStore.maps[0].id
    }
  } else if (tab === 'sound') {
    if (resourceStore.sounds.length > 0 && !selectedResource.value) {
      selectedResource.value = resourceStore.sounds[0].id
    }
  }
}

// 切换标签时自动选中第一个
watch(() => editorStore.resourceTab, autoSelectFirst)

// 列表变化时保持选中有效
watch(() => [...resourceStore.maps], () => {
  if (editorStore.resourceTab === 'map') {
    if (resourceStore.maps.length > 0 && !resourceStore.maps.find(m => m.id === selectedResource.value)) {
      selectedResource.value = resourceStore.maps[0].id
    } else if (resourceStore.maps.length === 0) {
      selectedResource.value = null
    }
  }
})

watch(() => [...resourceStore.sounds], () => {
  if (editorStore.resourceTab === 'sound') {
    if (resourceStore.sounds.length > 0 && !resourceStore.sounds.find(s => s.id === selectedResource.value)) {
      selectedResource.value = resourceStore.sounds[0].id
    } else if (resourceStore.sounds.length === 0) {
      selectedResource.value = null
    }
  }
})

watch(() => [...resourceStore.sprites], () => {
  if (editorStore.resourceTab === 'sprite') {
    if (resourceStore.sprites.length > 0 && !resourceStore.sprites.find(s => s.id === resourceStore.selectedSpriteId)) {
      resourceStore.selectedSpriteId = resourceStore.sprites[0].id
    } else if (resourceStore.sprites.length === 0) {
      resourceStore.selectedSpriteId = null
    }
  }
})

// 初始化时也自动选中
onMounted(autoSelectFirst)

function toggleFileMenu() {
  fileMenuVisible.value = !fileMenuVisible.value
}

function closeFileMenu() {
  fileMenuVisible.value = false
}

function toggleSettingsMenu() {
  settingsMenuVisible.value = !settingsMenuVisible.value
  settingsSubmenu.value = null
}

function closeSettingsMenu() {
  settingsMenuVisible.value = false
  settingsSubmenu.value = null
}

// 侧边栏拖拽调整宽度
function startResizeSidePanel(e: MouseEvent) {
  e.preventDefault()
  isResizingSidePanel.value = true
  const startX = e.clientX
  const startWidth = sidePanelWidth.value
  const minW = 180
  const maxW = 480

  function onMove(ev: MouseEvent) {
    const delta = ev.clientX - startX
    const newWidth = Math.min(maxW, Math.max(minW, startWidth + delta))
    sidePanelWidth.value = newWidth
  }
  function onUp() {
    isResizingSidePanel.value = false
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onUp)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }
  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onUp)
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
}

function onHelpClick(e: MouseEvent) {
  if (e.metaKey || e.ctrlKey) {
    // Cmd/Ctrl + 点击 → 打开 AI 助手
    aiChatVisible.value = true
    helpVisible.value = false
  } else {
    // 普通点击 → 打开帮助文档
    helpVisible.value = !helpVisible.value
    aiChatVisible.value = false
  }
}

async function onOpenHelpDocs() {
  closeSettingsMenu()
  try {
    await openHelpDocs()
  } catch (error) {
    console.error('打开帮助文档失败:', error)
  }
}

async function checkUpdate() {
  closeSettingsMenu()
  try {
    const { check } = await import('@tauri-apps/plugin-updater')
    const update = await check()
    if (update) {
      hasUpdate.value = true
      // 发现更新，触发 UpdateDialog 显示
      window.dispatchEvent(new CustomEvent('app-update-available', { detail: update }))
    } else {
      hasUpdate.value = false
      // 没有更新，触发 UpdateDialog 显示提示
      window.dispatchEvent(new CustomEvent('app-update-none'))
    }
  } catch (e: unknown) {
    const errorMsg = e instanceof Error ? e.message : String(e)
    console.error('检查更新失败:', errorMsg)
    window.dispatchEvent(new CustomEvent('app-update-error', { detail: { message: errorMsg } }))
  }
}

function openSettingsSubmenu(name: string) {
  settingsSubmenu.value = name
}

async function fileMenuAction(action: string) {
  closeFileMenu()

  // 切换项目前：有未保存代码时提示保存
  if ((action === 'new' || action === 'open') && editorStore.hasUnsavedTabs) {
    const shouldSave = await ask('有未保存的代码，是否保存？', { title: '未保存的代码', kind: 'warning' })
    if (shouldSave) {
      await editorStore.saveAllModifiedTabs()
    }
  }

  // 任何项目操作都先停止运行（不等待后端返回）
  if (editorStore.isRunning) {
    engine.stop()
    renderStore.clearAll()
  }

  switch (action) {
    case 'new': {
      const projectRoot = await projectStore.newProject()
      if (!projectRoot) break
      // 清空所有旧数据（两套标签页都要清）
      resourceStore.clearAllResources()
      renderStore.clearAll()
      editorStore.gameTabs.splice(0, editorStore.gameTabs.length)
      editorStore.codeTabs.splice(0, editorStore.codeTabs.length)
      editorStore.gameActiveTabIndex = 0
      editorStore.codeActiveTabIndex = 0
      await nextTick()
      // 创建新项目默认代码文件（先切代码模式，确保 createTab 加入 codeTabs）
      const name = '未命名-1.py'
      await invoke('create_dir', { path: `${projectRoot}/code` })
      await invoke('write_file', { path: `${projectRoot}/code/${name}`, content: '' })
      editorStore.setActiveEditorMode('code')
      editorStore.createTab(name, `${projectRoot}/code/${name}`, '')
      resourceStore.addItem({ name, type: 'code', path: `${projectRoot}/code/${name}`, content: '' })
      editorStore.setResourceTab('sprite')
      currentPage.value = 0
      break
    }

    case 'open': {
      const path = await open({
        title: '打开项目',
        filters: [{ name: 'BingoCode 项目', extensions: ['bc'] }],
      })
      if (!path) break
      const openOk = await projectStore.openProject(path)
      // 打开失败时中止，避免误清空当前工作区
      if (!openOk) break
      const root = projectStore.root
      if (!root) break

      // 清空全部旧数据（两套标签页都要清）
      resourceStore.clearAllResources()
      renderStore.clearAll()
      editorStore.gameTabs.splice(0, editorStore.gameTabs.length)
      editorStore.codeTabs.splice(0, editorStore.codeTabs.length)
      editorStore.gameActiveTabIndex = 0
      editorStore.codeActiveTabIndex = 0
      await nextTick()

      // 预加载项目资源（代码/地图/精灵/声音）
      await loadProjectResources(root)
      break
    }

    case 'save': {
      if (projectStore.bingoPath) {
        // 已有保存路径，直接保存
        await projectStore.saveProject()
      } else {
        // 首次保存，弹窗选择路径
        const path = await save({
          title: '保存项目',
          filters: [{ name: 'BingoCode 项目', extensions: ['bc'] }],
          defaultPath: `${projectStore.name || '未命名项目'}.bc`,
        })
        if (!path) break
        await projectStore.saveProjectAs(path)
      }
      break
    }

    case 'saveAs': {
      const path = await save({
        title: '另存为',
        filters: [{ name: 'BingoCode 项目', extensions: ['bc'] }],
        defaultPath: `${projectStore.name || '未命名项目'}.bc`,
      })
      if (!path) break
      await projectStore.saveProjectAs(path)
      break
    }

    case 'exit':
      window.close()
      break
  }
}

let _toggling = false
let _lastToggleTime = 0
const TOGGLE_COOLDOWN_MS = 400
async function toggleRun() {
  // 防抖 + 冷却：忽略连点，防止停止后立即重启导致 Rust 端 stop_script
  // 和 run_script 竞态杀死新进程（小学生疯狂点击场景）
  const now = Date.now()
  if (_toggling || now - _lastToggleTime < TOGGLE_COOLDOWN_MS) return
  _toggling = true
  _lastToggleTime = now
  try {
    // 正在运行 → 只停止，不重新启动
    if (editorStore.isRunning) {
      engine.stop()
      return
    }
    // 如果当前在角色/地图编辑器，自动切回代码模式（GameCanvas 只在代码模式下挂载）
    if (editorStore.activeEditorMode === 'sprite' || editorStore.activeEditorMode === 'map') {
      editorStore.setActiveEditorMode('code')
    }
    // 控制台不在此处强制弹出：引擎有打印信息时自动弹出（见 useEngine）
    await nextTick()
    await engine.run()
  } finally {
    _toggling = false
  }
}

// ─── 调试工具 ───
function toggleShowFps() {
  renderStore.showFps = !renderStore.showFps
  engine.sendShowFps(renderStore.showFps)
}
function toggleShowCollision() {
  renderStore.showCollision = !renderStore.showCollision
  engine.sendShowCollision(renderStore.showCollision)
}
function toggleShowStats() {
  renderStore.showStats = !renderStore.showStats
}

async function uploadResource(type: 'sprite' | 'map' | 'sound' | 'code') {
  const acceptMap: Record<string, string> = {
    sprite: '.bgs,.bsf,.png,.jpg,.gif',
    map: '.bgm,.json,.info',
    sound: '.wav,.mp3,.ogg',
    code: '.py',
  }
  const file = await fileDialog.openFile(acceptMap[type])
  if (!file) return

  resourceStore.addItem({
    name: file.name,
    type,
    path: file.name,
    content: type === 'code' ? file.content : undefined,
  })

  if (type === 'code') {
    editorStore.createTab(file.name, file.name, file.content)
  }
}

async function openResource(item: { id: string; name: string; type: string; content?: string; path?: string }) {
  if (item.type === 'code') {
    // 优先按 id 查找，其次按 path 查找
    let idx = editorStore.gameTabs.findIndex(t => t.id === item.id)
    if (idx < 0 && item.path) {
      idx = editorStore.gameTabs.findIndex(t => t.path === item.path)
    }
    if (idx < 0) {
      // 标签已关闭，重新创建
      idx = editorStore.createTab(item.name, item.path || '', item.content || '')
    }
    editorStore.setGameMode(true)
    editorStore.setActiveTab(idx)
  } else if (item.type === 'map') {
    // 只设置路径，实际加载由 MapEditorView 的 switchToMap 统一处理
    mapStore.setMapPath(item.id)
    editorStore.setGameMode(true)
    editorStore.setActiveEditorMode('map')
    editorStore.setResourceTab('map')
  }
}

function onResourceUploaded(type: string, name: string, content?: string) {
  editorStore.setResourceTab(type as any)
}

function onOpenLibrary(type: string) {
  if (type === 'sprite') {
    currentPage.value = 3  // sprite_lib page
  } else if (type === 'map') {
    currentPage.value = 2  // map_lib page
  } else if (type === 'sound') {
    currentPage.value = 5  // sound_lib page
  }
}

function onOpenPaint() {
  // 资源抽屉「绘制角色」= 新建角色
  paintTarget.value = null
  paintOpenMode.value = 'newFrame'
  currentPage.value = 6  // paint editor page
}

/** 造型列表抽屉「绘制新帧」：载入当前角色全部帧 + 自动新建空白帧 */
function onOpenPaintAppend() {
  const id = resourceStore.selectedSpriteId
  const item = id ? resourceStore.getItem(id, 'sprite') : null
  if (!item) return
  paintTarget.value = { id: item.id, name: item.name, path: item.path }
  paintOpenMode.value = 'newFrame'
  currentPage.value = 6
}

/** 双击帧卡片：载入全部帧并选中被双击的帧 */
function onOpenPaintEdit(index: number) {
  const id = resourceStore.selectedSpriteId
  const item = id ? resourceStore.getItem(id, 'sprite') : null
  if (!item) return
  paintTarget.value = { id: item.id, name: item.name, path: item.path }
  paintOpenMode.value = 'edit'
  paintInitialFrameIndex.value = index
  currentPage.value = 6
}

/** 造型列表抽屉「内置素材帧」：选一个内置角色，其全部帧追加到当前角色 */
function onOpenFramePicker() {
  if (!resourceStore.selectedSpriteId) return
  currentPage.value = 7
}

async function onFramePicked(blobs: Blob[]) {
  const id = resourceStore.selectedSpriteId
  const item = id ? resourceStore.getItem(id, 'sprite') : null
  currentPage.value = 0
  if (!item || blobs.length === 0) return
  try {
    const res = await appendFramesToSprite(item.path, blobs)
    if (res.newPath) {
      resourceStore.updateItemPath(item.id, res.newPath)
    }
    resourceStore.bumpSpriteThumb(item.id)
    await nextTick()
    spriteEditorRef.value?.reload()
  } catch (e) {
    console.error('[MainLayout] 追加内置素材帧失败:', e)
  }
}

function onPaintSaved(id: string, _name: string) {
  // 保存后自动进入角色编辑器：选中角色并切到 sprite 编辑模式。
  // 追加模式下 id 不变 → selectedSpriteId watch 不触发，需手动重载帧列表
  const isAppend = resourceStore.selectedSpriteId === id
  resourceStore.selectedSpriteId = id
  editorStore.setResourceTab('sprite')
  editorStore.setGameMode(true)
  editorStore.setActiveEditorMode('sprite')
  currentPage.value = 0
  if (isAppend) {
    nextTick(() => spriteEditorRef.value?.reload())
  }
}

async function onCreateMap() {
  const projectRoot = projectStore.root
  if (!projectRoot) return

  const name = resourceStore.nextSequentialName('map', '地图')

  // 创建地图目录
  const mapDir = `${projectRoot}/assets/maps/${name}`
  await invoke('create_dir', { path: mapDir })

  // 保存空地图数据
  const mapData = {
    name,
    version: 5,
    width: 40,
    height: 30,
    tileSize: 16,
    offsetX: 0,
    offsetY: 0,
    gravity: false,
    layers: [
      {
        id: 0,
        name: '绘制图层',
        type: 'tilelayer',
        visible: true,
        locked: false,
        data: '',
      },
    ],
    tilesets: [],
  }
  await invoke('write_file', {
    path: `${mapDir}/map.json`,
    content: JSON.stringify(mapData, null, 2),
  })

  // 添加到资源管理器
  const id = resourceStore.addItem({ name, type: 'map', path: mapDir })
  editorStore.setResourceTab('map')
}

function onSpriteLibImported(id: string, name: string, bgsUrl: string) {
  resourceStore.selectedSpriteId = id
  editorStore.setResourceTab('sprite')
  currentPage.value = 0
}

function onSoundLibImported(id: string, name: string) {
  selectedResource.value = id
  editorStore.setResourceTab('sound')
  currentPage.value = 0
}

async function onMapLibImported(bgmUrl: string, name: string) {
  const projectRoot = projectStore.root
  if (!projectRoot) return

  // 获取引擎素材目录，找到 .bgm 文件
  const engineAssetsDir = await invoke<string>('get_engine_assets_dir')
  const bgmPath = `${engineAssetsDir}/maps/packages/${name}.bgm`

  // 默认名字统一为「地图N」顺序名（磁盘目录名与 store 名字保持一致）
  const mapName = resourceStore.nextSequentialName('map', '地图')

  // 解压 .bgm 到项目目录
  try {
    await invoke<string>('extract_bgm_to_project', {
      bgmPath,
      projectRoot,
      mapName,
    })
  } catch (e) {
    console.error('[MapLib] 解压失败:', e)
    return
  }

  const projectPath = `${projectRoot}/assets/maps/${mapName}`
  resourceStore.addItem({ name: mapName, type: 'map', path: projectPath })

  // .bgm 内 map.json 的路径嵌入了原地图名（assets/maps/<原名>/...），且 Rust zip 解压
  // 可能损坏 map.json（layers/tilesets 被清空）——直接用 JSZip 从原始 .bgm 读 map.json，
  // 重写路径后写入项目目录，避免瓦片集图片路径指向不存在的目录
  try {
    const data = await invoke<number[]>('read_binary', { path: bgmPath })
    const zip = await JSZip.loadAsync(new Uint8Array(data))
    const entry = zip.file('map.json')
    if (entry) {
      const json = await entry.async('text')
      const fixed = json.replace(/assets\/maps\/[^/]+\//g, `assets/maps/${mapName}/`)
      await invoke('write_file', { path: `${projectPath}/map.json`, content: fixed })
    }
  } catch (e) {
    console.warn('[MapLib] 修复 map.json 失败:', e)
  }

  editorStore.setResourceTab('map')
  currentPage.value = 0
}

// ====== 图片作为地图导入（上传图片 / 内置资源库选图共用） ======

// 用前端 Image 对象测量图片真实尺寸（图像渲染偏移依赖 width/height）
// 中文路径下 convertFileSrc 生成的 asset URL 会加载失败，统一走 data URL
async function measureImageSize(absPath: string): Promise<{ w: number; h: number }> {
  let src: string
  try {
    src = await invoke<string>('read_image_as_data_url', { path: absPath })
  } catch {
    src = convertFileSrc(absPath)
  }
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve({ w: img.naturalWidth || 640, h: img.naturalHeight || 480 })
    img.onerror = () => resolve({ w: 640, h: 480 })
    img.src = src
  })
}

// 为图片创建图像模式地图：复制图片 → 生成 map.json（单个图像图层，图片自动放置于原点）
async function createImageMapProject(fileName: string, opts: { bytes?: number[]; srcPath?: string }) {
  const projectRoot = projectStore.root
  if (!projectRoot) return

  const baseName = fileName.replace(/\.[^.]+$/, '') || '图片地图'
  // 默认名字统一为「地图N」顺序名（磁盘目录名与 store 名字保持一致）
  const mapName = resourceStore.nextSequentialName('map', '地图')

  const mapDir = `${projectRoot}/assets/maps/${mapName}`
  await invoke('create_dir', { path: `${mapDir}/images` })

  const imageRelPath = `assets/maps/${mapName}/images/${fileName}`
  if (opts.bytes) {
    await invoke('write_binary', { path: `${projectRoot}/${imageRelPath}`, data: opts.bytes })
  } else if (opts.srcPath) {
    await invoke('copy_file_to_project', { src: opts.srcPath, projectRoot, relativePath: imageRelPath })
  }

  const { w, h } = await measureImageSize(`${projectRoot}/${imageRelPath}`)

  const mapData = {
    name: mapName,
    width: 40,
    height: 30,
    tileSize: 16,
    gravity: false,
    collisionType: '图像',
    collisionEnabled: false,
    layers: [
      {
        id: 0,
        name: '图像图层',
        type: 'imagelayer',
        visible: true,
        locked: false,
        images: [
          {
            imagePath: imageRelPath,
            position: [0, 0],
            rotation: 0,
            scale: 1,
            scaleX: 1,
            scaleY: 1,
            opacity: 1,
            width: w,
            height: h,
            collisionType: '图像',
            collisionEnabled: false,
          },
        ],
        resources: [
          {
            name: baseName,
            path: imageRelPath,
            resourceType: 'image',
            tileWidth: 64,
            tileHeight: 64,
            collisionType: '图像',
            collisionEnabled: false,
          },
        ],
      },
    ],
    tilesets: [],
  }
  await invoke('write_file', {
    path: `${mapDir}/map.json`,
    content: JSON.stringify(mapData, null, 2),
  })

  // 生成缩略图（模拟画布快照：底色 + 图片绘制在原点），
  // 必须在 addItem 之前写好，资源列表首次读取即可命中
  const thumbDataUrl = await writeMapThumbnail(mapDir, `${projectRoot}/${imageRelPath}`, 40 * 16, 30 * 16)

  const newItemId = resourceStore.addItem({ name: mapName, type: 'map', path: mapDir })
  editorStore.setResourceTab('map')
  currentPage.value = 0
  // 等 watch（切 tab 清空 / maps.length 变化重载）执行完，再直接把已生成的
  // dataURL 写进缩略图缓存——不依赖二次文件读取，确保第一时间显示
  await nextTick()
  if (thumbDataUrl) {
    mapThumbnails.value[newItemId] = thumbDataUrl
  }
  // 兜底：缓存已有会直接短路返回
  await loadMapThumbnail({ id: newItemId, path: mapDir })
}

// 用 2D canvas 生成地图缩略图快照（与编辑器画布快照语义一致：底色 + 图层内容），
// 返回 dataURL 供调用方直接写入缩略图缓存
async function writeMapThumbnail(mapDir: string, imageAbsPath: string, width: number, height: number): Promise<string | null> {
  try {
    // 必须经 Rust 读成 dataURL 再画 canvas：asset:// 协议图片会污染 canvas，
    // 导致 toDataURL() 抛 SecurityError，缩略图静默失败
    const srcDataUrl = await invoke<string>('read_image_as_data_url', { path: imageAbsPath })
    const img = new Image()
    img.src = srcDataUrl
    await new Promise<void>((resolve) => {
      img.onload = () => resolve()
      img.onerror = () => resolve()
    })
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    if (!ctx) return null
    ctx.fillStyle = '#1e1e1e'
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    if (img.naturalWidth) ctx.drawImage(img, 0, 0)
    const dataUrl = canvas.toDataURL('image/png')
    const raw = Uint8Array.from(atob(dataUrl.split(',')[1]), c => c.charCodeAt(0))
    await invoke('write_binary', { path: `${mapDir}/thumbnail.png`, data: Array.from(raw) })
    return dataUrl
  } catch (e) {
    console.warn('[MainLayout] 生成地图缩略图失败:', e)
    return null
  }
}

// 上传图片作为地图（UploadDrawer，data 为图片字节数组）
async function onImportMapImage(name: string, data: number[]) {
  await createImageMapProject(name, { bytes: data })
}

// 从内置资源库选择图片作为地图（路径为引擎 assets 相对路径，如 /maps/images/x.png）
async function onMapLibImportedImage(engineRelPath: string) {
  const engineAssetsDir = await invoke<string>('get_engine_assets_dir')
  const absPath = `${engineAssetsDir}${engineRelPath}`
  const fileName = engineRelPath.split('/').pop() || 'image.png'
  await createImageMapProject(fileName, { srcPath: absPath })
}

async function onResLibImported(path: string) {
  const name = path.split('/').pop()?.split('.')[0] || '资源'
  const tileSize = mapStore.mapData.tileSize
  const isImageLayer = mapStore.activeLayer?.type === 'image'

  // 复制资源文件到项目地图目录
  let relativePath = path
  try {
    const engineDir = await invoke<string>('get_engine_assets_dir')
    const fullSrc = `${engineDir}${path}`
    const projectRoot = projectStore.root
    const mapName = mapStore.mapData.name || '未命名地图'
    const fileName = path.split('/').pop() || 'resource.png'
    relativePath = `assets/maps/${mapName}/images/${fileName}`
    await invoke<string>('copy_file_to_project', {
      src: fullSrc,
      projectRoot,
      relativePath,
    })
  } catch (e) {
    console.error('复制资源到项目目录失败:', e)
  }

  mapStore.addResource({
    name,
    path: relativePath,
    resourceType: isImageLayer ? 'image' : 'tileset',
    tileWidth: isImageLayer ? 64 : tileSize,
    tileHeight: isImageLayer ? 64 : tileSize,
    collisionType: '图像',
    collisionEnabled: false,
  })
  editorStore.setActiveEditorMode('map')
  editorStore.setResourceTab('map')
  currentPage.value = 0
}

function renameResource(item: { id: string; name: string; type: string }) {
  const newName = prompt('重命名为:', item.name)
  if (newName && newName !== item.name) {
    item.name = newName
  }
}

function editorUndo() {
  // Monaco 内部处理，通过 CodeEditor 组件暴露
  window.dispatchEvent(new CustomEvent('editor-undo'))
}

function editorRedo() {
  window.dispatchEvent(new CustomEvent('editor-redo'))
}

function switchPage(page: number) {
  // 从全屏切回小窗口时，关闭调试面板
  if (currentPage.value === 1 && page !== 1) {
    renderStore.showStats = false
    renderStore.showCollision = false
  }
  currentPage.value = page
}

// 双击角色跳转到角色编辑页面
function openSpriteEditor(item: { id: string; name: string; path: string }) {
  resourceStore.selectedSpriteId = item.id
  editorStore.setGameMode(true)
  editorStore.setActiveEditorMode('sprite')
}

// 加载角色缩略图（通过 Rust 命令从解压目录读取；.bsf sheet 目录由前端裁剪）
async function loadSpriteThumbnail(item: { id: string; path: string }) {
  if (spriteThumbnails.value[item.id]) return
  if (!item.path) return
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    // .bsf 文件或含 manifest.json 的 sheet 目录 → 前端从 sheet 裁第一帧
    if (/\.bsf$/i.test(item.path)) {
      const { getBsfThumbnail } = await import('../../composables/useSpriteData')
      spriteThumbnails.value[item.id] = await normalizeSpriteThumb(await getBsfThumbnail(item.path))
      return
    }
    const isImage = /\.(png|jpe?g|gif|bmp|webp)$/i.test(item.path)
    if (!isImage) {
      const hasManifest = await invoke<boolean>('path_exists', {
        path: `${item.path}/manifest.json`,
      }).catch(() => false)
      if (hasManifest) {
        const { getBsfThumbnail } = await import('../../composables/useSpriteData')
        spriteThumbnails.value[item.id] = await normalizeSpriteThumb(await getBsfThumbnail(item.path))
        return
      }
    }
    const dataUrl = await invoke<string>('get_sprite_thumbnail', {
      path: item.path,
    })
    // 裁到内容框：不同尺寸/留白的素材在列表里视觉大小一致
    spriteThumbnails.value[item.id] = await normalizeSpriteThumb(dataUrl)
  } catch (e) {
    console.warn('Failed to load sprite thumbnail:', e)
  }
}

// 编辑器修改默认渲染帧后（写盘完成 → bump），重载对应角色缩略图
watch(
  () => resourceStore.spriteThumbVersions,
  (versions, oldVersions) => {
    for (const [id, ver] of Object.entries(versions)) {
      if (oldVersions && oldVersions[id] === ver) continue
      delete spriteThumbnails.value[id]
      const item = resourceStore.sprites.find(s => s.id === id)
      if (item) loadSpriteThumbnail(item)
    }
  },
  { deep: true }
)

async function loadMapThumbnail(item: { id: string; path: string }) {
  if (mapThumbnails.value[item.id]) return
  if (!item.path) return
  try {
    // 用 Tauri invoke 直接读取图片（与角色缩略图同理，避免 convertFileSrc 权限问题）
    const thumbUrl = await invoke<string>('read_image_as_data_url', { path: `${item.path}/thumbnail.png` })
    mapThumbnails.value[item.id] = thumbUrl
  } catch {
    // thumbnail load failed
  }
}

// 地图保存后用刚生成的快照直接更新缩略图缓存——
// 编辑完成后资源列表立即显示最新图，无需切 tab 触发文件重读
function onMapThumbnailUpdated(itemId: string, dataUrl: string) {
  mapThumbnails.value[itemId] = dataUrl
}

// 角色右键菜单
function onSpriteContextMenu(e: MouseEvent, item: { id: string; name: string }) {
  e.preventDefault()
  e.stopPropagation()
  spriteContextMenu.value = { show: true, x: e.clientX, y: e.clientY, item }
}

function closeSpriteContextMenu() {
  spriteContextMenu.value.show = false
}

function deleteSpriteFromContext(id: string) {
  const item = resourceStore.sprites.find(i => i.id === id)
  resourceStore.removeItem(id, 'sprite')
  if (resourceStore.selectedSpriteId === id) resourceStore.selectedSpriteId = null
  spriteContextMenu.value.show = false
  // 同步删除项目目录中的文件
  if (item?.path) invoke('delete_path', { path: item.path }).catch(() => {})
}

function deleteMapFromContext(id: string) {
  const item = resourceStore.maps.find(i => i.id === id)
  resourceStore.removeItem(id, 'map')
  if (selectedResource.value === id) {
    selectedResource.value = resourceStore.maps.length > 0 ? resourceStore.maps[0].id : null
  }
  mapContextMenu.value.show = false
  // 同步删除项目目录中的文件
  if (item?.path) invoke('delete_path', { path: item.path }).catch(() => {})
}

function startSpriteRename(id: string) {
  const item = resourceStore.sprites.find(i => i.id === id)
  if (!item) return
  spriteRenameId.value = id
  spriteRenameValue.value = item.name
  spriteContextMenu.value.show = false
  // 等两轮 tick 确保 DOM 更新完毕
  nextTick(() => nextTick(() => {
    const input = document.querySelector('.sprite-rename-input') as HTMLInputElement | null
    if (input) {
      input.focus()
      input.select()  // 默认全选，方便一键删除重写
    }
  }))
}

async function migrateSpriteDir(oldName: string, newName: string): Promise<string | null> {
  if (!projectStore.root) return null
  const base = `${projectStore.root}/assets/sprites`
  try {
    // .bgs 角色：目录形式，整体改名
    const oldDir = `${base}/${oldName}`
    if (await invoke<boolean>('path_exists', { path: oldDir })) {
      await invoke('rename_path', { oldPath: oldDir, newPath: `${base}/${newName}` })
      return `${base}/${newName}`
    }
    // 图片角色：文件形式（保留原扩展名），按扩展名逐个尝试改名
    for (const ext of ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']) {
      const oldFile = `${base}/${oldName}${ext}`
      if (await invoke<boolean>('path_exists', { path: oldFile })) {
        await invoke('rename_path', { oldPath: oldFile, newPath: `${base}/${newName}${ext}` })
        return `${base}/${newName}${ext}`
      }
    }
  } catch (e) {
    console.error('[MainLayout] 迁移角色资源失败:', e)
  }
  return null
}

function confirmSpriteRename() {
  if (!spriteRenameId.value) return
  const val = spriteRenameValue.value.trim()
  if (!val) { spriteRenameId.value = null; return }

  const item = resourceStore.sprites.find(i => i.id === spriteRenameId.value)
  const oldName = item?.name
  if (!item || !oldName || oldName === val) { spriteRenameId.value = null; return }

  // 先执行磁盘迁移，再改名字
  migrateSpriteDir(oldName, val).then((newPath) => {
    resourceStore.renameItem(spriteRenameId.value!, val)
    // 优先用迁移返回的真实路径（图片角色带扩展名）
    if (newPath) {
      item.path = newPath
    } else if (projectStore.root) {
      item.path = `${projectStore.root}/assets/sprites/${val}`
    }
    spriteRenameId.value = null
  })
}

function cancelSpriteRename() {
  spriteRenameId.value = null
}

function closeSpriteContextMenus() {
  spriteContextMenu.value.show = false
  mapContextMenu.value.show = false
  codeContextMenu.value.show = false
  soundContextMenu.value.show = false
}

// 地图右键菜单
function onMapContextMenu(e: MouseEvent, item: { id: string; name: string }) {
  e.preventDefault()
  e.stopPropagation()
  mapContextMenu.value = { show: true, x: e.clientX, y: e.clientY, item }
}

function startMapRename(id: string) {
  const item = resourceStore.maps.find(i => i.id === id)
  if (!item) return
  mapRenameId.value = id
  mapRenameValue.value = item.name
  mapContextMenu.value.show = false
  nextTick(() => nextTick(() => {
    const input = document.querySelector('.map-rename-input') as HTMLInputElement | null
    if (input) {
      input.focus()
      input.select()  // 默认全选，方便一键删除重写
    }
  }))
}

function confirmMapRename() {
  if (!mapRenameId.value) return
  const val = mapRenameValue.value.trim()
  if (!val) { mapRenameId.value = null; return }
  
  const item = resourceStore.maps.find(i => i.id === mapRenameId.value)
  const oldName = item?.name
  if (!item || !oldName || oldName === val) { mapRenameId.value = null; return }
  
  // 先执行目录迁移，再改名字
  migrateMapDir(oldName, val).then(() => {
    resourceStore.renameItem(mapRenameId.value!, val)
    // 更新 item.path
    if (projectStore.root) {
      item.path = `${projectStore.root}/assets/maps/${val}`
    }
    mapRenameId.value = null
  })
}

async function migrateMapDir(oldName: string, newName: string) {
  if (!projectStore.root) return
  const oldDir = `${projectStore.root}/assets/maps/${oldName}`
  const newDir = `${projectStore.root}/assets/maps/${newName}`
  try {
    const exists = await invoke<boolean>('path_exists', { path: oldDir })
    if (!exists) return

    // 原子重命名整个目录
    await invoke('rename_path', { oldPath: oldDir, newPath: newDir })

    // 更新 map.json 中的资源路径（旧名→新名）
    const jsonPath = `${newDir}/map.json`
    const jsonExists = await invoke<boolean>('path_exists', { path: jsonPath })
    if (jsonExists) {
      const json = await invoke<string>('read_file', { path: jsonPath })
      const data = JSON.parse(json)
      let changed = false
      for (const layer of data.layers || []) {
        for (const res of layer.resources || []) {
          if (res.path?.startsWith(`assets/maps/${oldName}/`)) {
            res.path = res.path.replace(`assets/maps/${oldName}/`, `assets/maps/${newName}/`)
            changed = true
          }
        }
        for (const img of layer.images || []) {
          if (img.imagePath?.startsWith(`assets/maps/${oldName}/`)) {
            img.imagePath = img.imagePath.replace(`assets/maps/${oldName}/`, `assets/maps/${newName}/`)
            changed = true
          }
        }
      }
      // 更新 tilesets 中的 image 路径
      for (const ts of data.tilesets || []) {
        if (ts.image?.startsWith(`assets/maps/${oldName}/`)) {
          ts.image = ts.image.replace(`assets/maps/${oldName}/`, `assets/maps/${newName}/`)
          changed = true
        }
      }
      if (changed) {
        await invoke('write_file', { path: jsonPath, content: JSON.stringify(data) })
      }
    }
  } catch (e) {
    console.error('[MainLayout] 迁移地图目录失败:', e)
  }
}

function cancelMapRename() {
  mapRenameId.value = null
}

// 声音右键菜单
function onSoundContextMenu(e: MouseEvent, item: { id: string; name: string }) {
  e.preventDefault()
  e.stopPropagation()
  soundContextMenu.value = { show: true, x: e.clientX, y: e.clientY, item }
}

function deleteSoundFromContext(id: string) {
  const item = resourceStore.sounds.find(i => i.id === id)
  resourceStore.removeItem(id, 'sound')
  if (selectedResource.value === id) {
    selectedResource.value = resourceStore.sounds.length > 0 ? resourceStore.sounds[0].id : null
  }
  soundContextMenu.value.show = false
  // 同步删除项目目录中的文件
  if (item?.path) invoke('delete_path', { path: item.path }).catch(() => {})
}

// 同步游戏模式标签和代码资源管理器
watch(() => [...editorStore.gameTabs], (tabs, oldTabs) => {
  const tabIds = new Set(tabs.map(t => t.id))

  // 删除已不存在的 tab 对应的资源项
  if (oldTabs) {
    for (const oldTab of oldTabs) {
      if (!tabIds.has(oldTab.id)) {
        const idx = resourceStore.codes.findIndex(c => c.id === oldTab.id)
        if (idx >= 0) resourceStore.codes.splice(idx, 1)
      }
    }
  }

  // 新增或更新
  for (const tab of tabs) {
    const existing = resourceStore.codes.find(c => c.id === tab.id || (tab.path && c.path === tab.path))
    if (!existing) {
      resourceStore.codes.push({ id: tab.id, name: tab.name, type: 'code', path: tab.path, content: tab.content })
    } else {
      existing.name = tab.name
      if (tab.path) existing.path = tab.path
      existing.content = tab.content
    }
  }
}, { immediate: true, deep: true })

// 代码右键菜单
function onCodeContextMenu(e: MouseEvent, item: { id: string; name: string }) {
  e.preventDefault()
  e.stopPropagation()
  codeContextMenu.value = { show: true, x: e.clientX, y: e.clientY, item }
}

function closeCodeContextMenu() {
  codeContextMenu.value.show = false
}

function deleteCodeFromContext(id: string) {
  const item = resourceStore.codes.find(c => c.id === id)
  const tabs = editorStore.gameTabs
  const idx = tabs.findIndex(t => t.id === id)
  if (idx >= 0) editorStore.closeTab(idx)
  resourceStore.removeItem(id, 'code')
  codeContextMenu.value.show = false
  // 同步删除项目目录中的文件
  if (item?.path) invoke('delete_path', { path: item.path }).catch(() => {})
}

function startCodeRename(id: string) {
  const item = resourceStore.codes.find(c => c.id === id)
  if (!item) return
  codeRenameId.value = id
  // 输入时隐藏 .py 后缀
  codeRenameValue.value = codeDisplayName(item.name)
  codeContextMenu.value.show = false
  nextTick(() => {
    nextTick(() => {
      const input = document.querySelector('.code-rename-input') as HTMLInputElement | null
      if (input) {
        input.focus()
        input.select()
      }
    })
  })
}

async function migrateCodeFile(oldPath: string, newPath: string) {
  if (!oldPath || !newPath || oldPath === newPath) return
  try {
    const exists = await invoke<boolean>('path_exists', { path: oldPath })
    if (!exists) return
    await invoke('rename_path', { oldPath, newPath })
  } catch (e) {
    console.error('[MainLayout] 迁移代码文件失败:', e)
  }
}

async function confirmCodeRename() {
  if (!codeRenameId.value) return
  const val = codeRenameValue.value.trim()
  if (!val) { codeRenameId.value = null; codeRenameValue.value = ''; return }

  const nameWithPy = val.endsWith('.py') ? val : val + '.py'
  const item = resourceStore.codes.find(c => c.id === codeRenameId.value)
  const tab = editorStore.gameTabs.find(t => t.id === codeRenameId.value)
  if (!item || !tab) { codeRenameId.value = null; codeRenameValue.value = ''; return }

  const oldPath = tab.path || item.path || ''
  const projectRoot = projectStore.root || ''
  const isInsideProject = projectRoot && oldPath.startsWith(projectRoot)
  const newPath = projectRoot ? `${projectRoot}/code/${nameWithPy}` : nameWithPy

  // 如果新旧路径相同，只更新显示名
  if (oldPath === newPath) {
    tab.name = nameWithPy
    item.name = nameWithPy
    codeRenameId.value = null
    codeRenameValue.value = ''
    return
  }

  try {
    if (isInsideProject) {
      // 文件在项目目录内：执行文件重命名
      await migrateCodeFile(oldPath, newPath)
    } else if (projectRoot) {
      // 文件在项目外或无路径：写入项目目录（不动原文件）
      await invoke('create_dir', { path: `${projectRoot}/code` })
      await invoke('write_file', { path: newPath, content: tab.content || '' })
    }

    tab.name = nameWithPy
    tab.path = projectRoot ? newPath : ''
    tab.modified = false
    item.name = nameWithPy
    item.path = projectRoot ? newPath : ''
  } catch (e) {
    console.error('[MainLayout] 代码重命名失败:', e)
  } finally {
    codeRenameId.value = null
    codeRenameValue.value = ''
  }
}

function cancelCodeRename() {
  codeRenameId.value = null
  codeRenameValue.value = ''
}

// ═══ IDE 模式文件操作 ═══

// 打开文件夹（IDE 模式）
async function ideOpenFolder() {
  // 切换前：有未保存代码时提示保存
  if (editorStore.hasUnsavedTabs) {
    const shouldSave = await ask('有未保存的代码，是否保存？', { title: '未保存的代码', kind: 'warning' })
    if (shouldSave) {
      await editorStore.saveAllModifiedTabs()
    }
  }
  // 清空旧标签页
  editorStore.gameTabs.splice(0, editorStore.gameTabs.length)
  editorStore.codeTabs.splice(0, editorStore.codeTabs.length)
  editorStore.gameActiveTabIndex = 0
  editorStore.codeActiveTabIndex = 0
  const path = await open({
    title: '打开文件夹',
    directory: true,
  })
  if (path && typeof path === 'string') {
    await fileExplorerStore.openFolder(path)
  }
}

// 在文件树中新建文件（IDE 标签栏 + 按钮调用）
async function ideNewFileInTree() {
  if (!fileExplorerStore.workspaceFolder) {
    await ideOpenFolder()
    return
  }
  const name = '新文件.py'
  let counter = 1
  let finalName = name
  const basePath = fileExplorerStore.workspaceFolder
  while (await invoke<boolean>('path_exists', { path: `${basePath}/${finalName}` })) {
    counter++
    finalName = `新文件-${counter}.py`
  }
  try {
    await fileExplorerStore.createFile(basePath, finalName)
    const newPath = `${basePath}/${finalName}`
    const content = await invoke<string>('read_file', { path: newPath })
    editorStore.createTab(finalName, newPath, content)
  } catch (e) {
    console.error('[IDE] 新建文件失败:', e)
  }
}

// 保存 .py 文件（IDE 模式）
async function ideSaveFile() {
  const tab = editorStore.currentTab
  if (!tab) return

  if (tab.path) {
    // 有文件路径，直接保存
    try {
      await invoke('write_file', { path: tab.path, content: tab.content })
      editorStore.saveCurrentTab()
    } catch (e) {
      console.error('[IDE] 保存文件失败:', e)
    }
  } else {
    // 无文件路径，弹窗选择保存位置
    await ideSaveFileAs()
  }
}

// 另存为（IDE 模式）
async function ideSaveFileAs() {
  const tab = editorStore.currentTab
  if (!tab) return
  
  const path = await save({
    title: '保存 Python 文件',
    filters: [{ name: 'Python 文件', extensions: ['py'] }],
    defaultPath: tab.name,
  })
  
  if (!path) return
  
  try {
    await invoke('write_file', { path, content: tab.content })
    // 更新标签的路径和名称
    const fileName = path.split('/').pop() || tab.name
    tab.path = path
    tab.name = fileName
    tab.modified = false
    // 同步更新资源管理器
    const resource = resourceStore.codes.find(c => c.id === tab.id)
    if (resource) {
      resource.path = path
      resource.name = fileName
    }
  } catch (e) {
    console.error('[IDE] 另存为失败:', e)
  }
}

// ═══ IDE 模式文件操作结束 ═══

// ═══ 代码格式化 ═══

// 格式化代码 - 使用 Monaco DocumentFormattingEditProvider（VSCode 风格）
function ideFormatCode() {
  // 通过 Monaco 内置命令触发格式化，由 CodeEditor 中注册的 provider 处理
  window.dispatchEvent(new CustomEvent('editor-run-format'))
}

// ═══ 代码格式化结束 ═══

// 代码文件显示名：隐藏 .py 后缀
// 代码标签重命名
const tabRenameId = ref<string | null>(null)
const tabRenameValue = ref('')

function startTabRename(id: string) {
  const tab = editorStore.currentTabs.find(t => t.id === id)
  if (!tab) return
  tabRenameId.value = id
  tabRenameValue.value = codeDisplayName(tab.name)
  nextTick(() => nextTick(() => {
    const input = document.querySelector('.tab-rename-input') as HTMLInputElement | null
    if (input) { input.focus(); input.select() }
  }))
}

async function confirmTabRename() {
  if (!tabRenameId.value) return
  const val = tabRenameValue.value.trim()
  if (!val) { tabRenameId.value = null; tabRenameValue.value = ''; return }

  const nameWithPy = val.endsWith('.py') ? val : val + '.py'
  const tabId = tabRenameId.value
  const tab = editorStore.currentTabs.find(t => t.id === tabId)
  if (!tab) { tabRenameId.value = null; tabRenameValue.value = ''; return }

  const oldPath = tab.path || ''

  // ── 代码模式 (IDE)：文件在用户本地磁盘，重命名只改文件名，不动位置 ──
  if (!editorStore.isGameMode) {
    if (oldPath) {
      // 有文件路径：在同一目录下重命名文件
      const lastSlash = oldPath.lastIndexOf('/')
      const dir = lastSlash >= 0 ? oldPath.substring(0, lastSlash) : ''
      const newPath = dir ? `${dir}/${nameWithPy}` : nameWithPy
      if (oldPath !== newPath) {
        await migrateCodeFile(oldPath, newPath)
      }
      editorStore.renameTab(tabId, nameWithPy, newPath)
      const item = resourceStore.codes.find(c => c.id === tabId)
      if (item) { item.name = nameWithPy; item.path = newPath }
    } else {
      // 无路径（新文件）：只更新显示名
      editorStore.renameTab(tabId, nameWithPy)
      const item = resourceStore.codes.find(c => c.id === tabId)
      if (item) item.name = nameWithPy
    }
    tabRenameId.value = null
    tabRenameValue.value = ''
    return
  }

  // ── 游戏模式：文件在项目目录内 ──
  const projectRoot = projectStore.root || ''
  const newPath = projectRoot ? `${projectRoot}/code/${nameWithPy}` : nameWithPy

  if (oldPath === newPath) {
    editorStore.renameTab(tabId, nameWithPy)
    const item = resourceStore.codes.find(c => c.id === tabId)
    if (item) item.name = nameWithPy
    tabRenameId.value = null
    tabRenameValue.value = ''
    return
  }

  try {
    if (oldPath) {
      await migrateCodeFile(oldPath, newPath)
    } else if (projectRoot) {
      await invoke('create_dir', { path: `${projectRoot}/code` })
      await invoke('write_file', { path: newPath, content: tab.content || '' })
    }

    editorStore.renameTab(tabId, nameWithPy, newPath)
    const item = resourceStore.codes.find(c => c.id === tabId)
    if (item) {
      item.name = nameWithPy
      item.path = newPath
    }
    const updatedTab = editorStore.currentTabs.find(t => t.id === tabId)
    if (updatedTab) updatedTab.modified = false
  } catch (e) {
    console.error('[MainLayout] 标签重命名失败:', e)
  } finally {
    tabRenameId.value = null
    tabRenameValue.value = ''
  }
}

function cancelTabRename() {
  tabRenameId.value = null
  tabRenameValue.value = ''
}

// 代码文件显示名：隐藏 .py 后缀
function codeDisplayName(name: string) {
  return name.endsWith('.py') ? name.slice(0, -3) : name
}

function spriteDisplayName(name: string) {
  return name.replace(/\.(png|jpg|jpeg|gif|webp|bmp)$/i, '')
}
</script>

<template>
  <div class="app-root">
    <!-- ═══════════ 顶部菜单栏 ═══════════ -->
    <div v-show="currentPage !== 1" class="menu-bar">
      <!-- Logo (固定宽度) -->
      <button class="menu-logo">
        <img :src="iconLogo" class="menu-logo-img" />
      </button>

      <!-- ═══ 游戏模式菜单 ═══ -->
      <template v-if="editorStore.isGameMode">
        <div class="menu-file-wrapper" @mouseleave="closeFileMenu">
          <button class="menu-btn menu-btn-file" @click="toggleFileMenu">
            <img :src="iconFile" class="menu-icon" />
            <span>项目</span>
          </button>
          <div v-show="fileMenuVisible" class="file-menu-dropdown">
            <button class="file-menu-item" @click="fileMenuAction('new')">新建项目</button>
            <button class="file-menu-item" @click="fileMenuAction('open')">打开项目</button>
            <button class="file-menu-item" @click="fileMenuAction('save')">保存项目</button>
            <button class="file-menu-item" @click="fileMenuAction('saveAs')">另存为...</button>
            <div class="file-menu-divider"></div>
            <button class="file-menu-item" @click="fileMenuAction('exit')">退出</button>
          </div>
        </div>

        <!-- 代码 (图标+文字) -->
        <button class="menu-btn" :class="{ 'menu-btn-active': editorStore.activeEditorMode === 'code' }" @click="editorStore.setActiveEditorMode('code')">
          <img :src="iconCodeEdit" class="menu-icon" />
          <span>代码</span>
        </button>

        <!-- 角色 (图标+文字) -->
        <button class="menu-btn" :class="{ 'menu-btn-active': editorStore.activeEditorMode === 'sprite' }" @click="editorStore.setActiveEditorMode('sprite')">
          <img :src="iconSprite" class="menu-icon" />
          <span>角色</span>
        </button>

        <!-- 地图 (图标+文字) -->
        <button class="menu-btn" :class="{ 'menu-btn-active': editorStore.activeEditorMode === 'map' }" @click="editorStore.setActiveEditorMode('map')">
          <img :src="iconMap" class="menu-icon" />
          <span>地图</span>
        </button>
      </template>

      <!-- ═══ 代码模式菜单 ═══ -->
      <template v-else>
        <!-- 打开文件夹 (最左边) -->
        <button class="menu-btn" @click="ideOpenFolder" v-tooltip="'打开文件夹'">
          <img :src="iconCodeOpen" class="menu-icon" />
          <span>项目</span>
        </button>

        <!-- 保存 -->
        <button class="menu-btn" @click="ideSaveFile" v-tooltip="'保存'">
          <img :src="iconCodeSave" class="menu-icon" />
          <span>保存</span>
        </button>

        <!-- 运行/停止 -->
        <button class="menu-btn" @click="toggleRun" v-tooltip="editorStore.isRunning ? '停止' : '运行'">
          <img v-if="!editorStore.isRunning" :src="iconCodeRun" class="menu-icon" />
          <img v-else :src="iconCodeStop" class="menu-icon" />
          <span>{{ editorStore.isRunning ? '停止' : '运行' }}</span>
        </button>

        <!-- 格式化 -->
        <button class="menu-btn" @click="ideFormatCode" v-tooltip="'格式化代码'">
          <img :src="iconCodeFormat" class="menu-icon" />
          <span>格式化</span>
        </button>
      </template>

      <!-- 设置 (两种模式都有) -->
      <div class="menu-file-wrapper" @mouseleave="closeSettingsMenu">
        <button class="menu-btn" @click="toggleSettingsMenu">
          <img :src="iconSettings" class="menu-icon" />
          <span>设置</span>
        </button>
        <div v-show="settingsMenuVisible" class="file-menu-dropdown settings-menu">
          <!-- 渲染模式 -->
          <div class="settings-item-group" @mouseenter="openSettingsSubmenu('renderMode')" @mouseleave="settingsSubmenu = null">
            <div class="file-menu-item settings-menu-item">
              <span>渲染模式</span>
              <span class="settings-arrow">›</span>
            </div>
            <div v-show="settingsSubmenu === 'renderMode'" class="settings-submenu">
              <button class="file-menu-item" :class="{ 'settings-item-active': editorStore.renderMode === 'auto' }" @click="editorStore.setRenderMode('auto'); closeSettingsMenu()">
                Auto
              </button>
              <button class="file-menu-item" :class="{ 'settings-item-active': editorStore.renderMode === 'smooth' }" @click="editorStore.setRenderMode('smooth'); closeSettingsMenu()">
                Smooth
              </button>
              <button class="file-menu-item" :class="{ 'settings-item-active': editorStore.renderMode === 'pixelated' }" @click="editorStore.setRenderMode('pixelated'); closeSettingsMenu()">
                Pixelated
              </button>
            </div>
          </div>
          <!-- 主题 -->
          <div class="settings-item-group" @mouseenter="openSettingsSubmenu('theme')" @mouseleave="settingsSubmenu = null">
            <div class="file-menu-item settings-menu-item">
              <span>主题</span>
              <span class="settings-arrow">›</span>
            </div>
            <div v-show="settingsSubmenu === 'theme'" class="settings-submenu">
              <button
                v-for="themeName in themeStore.getThemeNames()"
                :key="themeName"
                class="file-menu-item"
                :class="{ 'settings-item-active': themeStore.currentTheme === themeName }"
                @click="themeStore.setTheme(themeName); closeSettingsMenu()"
              >
                {{ themeStore.getThemeDisplayName(themeName) }}
              </button>
            </div>
          </div>
          <!-- 插件库 -->
          <button class="file-menu-item" @click="pluginManagerVisible = true; closeSettingsMenu()">
            插件库
          </button>
          <!-- 快捷键 -->
          <div class="settings-item-group" @mouseenter="openSettingsSubmenu('shortcuts')" @mouseleave="settingsSubmenu = null">
            <div class="file-menu-item settings-menu-item">
              <span>快捷键</span>
              <span class="settings-arrow">›</span>
            </div>
            <div v-show="settingsSubmenu === 'shortcuts'" class="settings-submenu">
              <button class="file-menu-item settings-item-disabled">编辑快捷键</button>
            </div>
          </div>
          <!-- 引擎设置 -->
          <div class="settings-item-group" @mouseenter="openSettingsSubmenu('engine')" @mouseleave="settingsSubmenu = null">
            <div class="file-menu-item settings-menu-item">
              <span>引擎设置</span>
              <span class="settings-arrow">›</span>
            </div>
            <div v-show="settingsSubmenu === 'engine'" class="settings-submenu">
              <button class="file-menu-item settings-item-disabled">Python 路径</button>
              <button class="file-menu-item settings-item-disabled">引擎参数</button>
              <div class="file-menu-item settings-menu-item" @click="editorStore.setFocusMode(!editorStore.focusMode)">
                <span>专注模式</span>
                <span class="settings-toggle" :class="{ 'settings-toggle-on': editorStore.focusMode }">
                  <span class="settings-toggle-knob"></span>
                </span>
              </div>
            </div>
          </div>
          <!-- 分隔线 -->
          <div class="settings-divider"></div>
          <!-- 帮助文档 -->
          <button class="file-menu-item" @click="onOpenHelpDocs">
            帮助文档
          </button>
          <!-- 检查更新 -->
          <button class="file-menu-item settings-update-btn" @click="checkUpdate">
            检查更新
            <span v-if="hasUpdate" class="update-dot"></span>
          </button>
        </div>
      </div>

      <!-- 弹性空间 (占6份) -->
      <div class="menu-spacer"></div>

      <!-- 模式切换 -->
      <div class="mode-switch">
        <span class="mode-label">{{ editorStore.isGameMode ? '游戏模式' : '代码模式' }}</span>
        <button class="toggle-switch" :class="{ 'toggle-on': editorStore.isGameMode }" @click="editorStore.toggleGameMode()">
          <div class="toggle-knob"></div>
        </button>
      </div>

      <!-- 帮助 (仅图标) -->
      <button class="menu-btn menu-btn-help" v-tooltip="'帮助 (⌘+点击打开AI助手)'" @click="onHelpClick">
        <img :src="iconHelp" width="24" height="24" />
      </button>
    </div>

    <!-- ═══════════ change_page (外层切页) ═══════════ -->
    <div class="main-content">

      <!-- ─── page 0: edit_stage_frame ─── -->
      <div v-show="currentPage === 0" class="edit-stage-frame">

        <!-- ═══ Page 0: 游戏模式 — 角色编辑器 ═══ -->
        <div v-if="editorStore.isGameMode && editorStore.activeEditorMode === 'sprite'" class="editor-page-full">
          <SpriteEditorView ref="spriteEditorRef" @open-paint-append="onOpenPaintAppend" @open-paint-edit="onOpenPaintEdit" @open-frame-picker="onOpenFramePicker" />
        </div>

        <!-- ═══ Page 0: 游戏模式 — 地图编辑器 (v-show 保持 PixiJS 实例存活) ═══ -->
        <div v-show="editorStore.isGameMode && editorStore.activeEditorMode === 'map'" class="editor-page-full">
          <MapEditorView @open-resource-lib="currentPage = 4" @map-thumbnail-updated="onMapThumbnailUpdated" />
        </div>

        <!-- ═══ Page 0: 游戏模式 — 代码编辑 (侧边栏 + 标签 + 代码编辑 + 控制台) ═══ -->
        <div v-if="editorStore.isGameMode && editorStore.activeEditorMode !== 'sprite' && editorStore.activeEditorMode !== 'map'" class="editor-page-game">
          <div class="sidebar">
            <div class="sidebar-toolbar">
              <button class="tool-btn" :class="{ 'tool-btn-active': editorStore.isRunning }" @click="toggleRun" v-tooltip="'运行'">
                <img :src="iconPlay" width="16" height="16" />
              </button>
              <button class="tool-btn" @click="engine.stop()" v-tooltip="'停止'">
                <img :src="iconStop" width="16" height="16" />
              </button>
              <div class="tool-spacer"></div>
              <button class="tool-btn" @click="switchPage(1)" v-tooltip="'全屏'">
                <img :src="iconFullscreen" width="20" height="20" />
              </button>
            </div>
            <div class="game-preview-wrapper">
              <div class="game-preview-container">
                <GameCanvas class="game-preview-canvas" />
                <!-- Loading覆盖层 -->
                <div v-if="renderStore.isLoadingTextures" class="loading-overlay">
                  <div class="loading-content">
                    <div class="loading-balls">
                      <div class="ball ball-1"></div>
                      <div class="ball ball-2"></div>
                      <div class="ball ball-3"></div>
                    </div>
                    <div class="loading-text">加载资源中...</div>
                    <div class="loading-progress">{{ loadingProgress }}%</div>
                    <div class="loading-bar">
                      <div class="loading-bar-fill" :style="{ width: loadingProgress + '%' }"></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div class="outline-tabs">
              <button v-for="t in ['sprite','map','sound','code']" :key="t" class="outline-tab" :class="{ 'outline-tab-active': editorStore.resourceTab === t }" @click="editorStore.setResourceTab(t); closeSpriteContextMenus()">
                {{ t === 'sprite' ? '角色' : t === 'map' ? '场景' : t === 'sound' ? '声音' : '代码' }}
              </button>
            </div>
            <div class="outline-list-wrapper">
              <div class="outline-list">
                <div v-if="editorStore.resourceTab === 'sprite'" class="resource-grid" @click="closeSpriteContextMenus">
                  <div
                    v-for="item in resourceStore.sprites"
                    :key="item.id"
                    class="resource-grid-item"
                    :class="{ 'resource-grid-item-active': resourceStore.selectedSpriteId === item.id }"
                    @click="resourceStore.selectedSpriteId = item.id"
                    @dblclick="openSpriteEditor(item)"
                    @contextmenu="onSpriteContextMenu($event, item)"
                  >
                    <div class="resource-thumb">
                      <img v-if="spriteThumbnails[item.id]" :src="spriteThumbnails[item.id]" class="resource-thumb-img" />
                      <span v-else>{{ item.name.charAt(0) }}</span>
                    </div>
                    <template v-if="spriteRenameId === item.id">
                      <input
                        class="sprite-rename-input"
                        v-model="spriteRenameValue"
                        @blur="confirmSpriteRename"
                        @keydown.enter.prevent="confirmSpriteRename"
                        @keydown.escape="cancelSpriteRename"
                        @click.stop
                      />
                    </template>
                    <template v-else>
                      <span class="resource-grid-name">{{ spriteDisplayName(item.name) }}</span>
                    </template>
                  </div>
                  <div v-if="resourceStore.sprites.length === 0" class="resource-empty"></div>
                </div>
                <div v-else-if="editorStore.resourceTab === 'map'" class="resource-grid" @click="closeSpriteContextMenus">
                  <div
                    v-for="item in resourceStore.maps"
                    :key="item.id"
                    class="resource-grid-item"
                    :class="{ 'resource-grid-item-active': selectedResource === item.id }"
                    @click="selectedResource = item.id"
                    @dblclick="openResource(item)"
                    @contextmenu="onMapContextMenu($event, item)"
                  >
                    <div class="resource-thumb resource-thumb-checker">
                      <img v-if="mapThumbnails[item.id]" :src="mapThumbnails[item.id]" class="resource-thumb-img" :style="{ imageRendering: editorStore.renderMode === 'pixelated' ? 'pixelated' : 'auto' }" />
                    </div>
                    <template v-if="mapRenameId === item.id">
                      <input
                        class="map-rename-input"
                        v-model="mapRenameValue"
                        @blur="confirmMapRename"
                        @keydown.enter.prevent="confirmMapRename"
                        @keydown.escape="cancelMapRename"
                        @click.stop
                      />
                    </template>
                    <template v-else>
                      <span class="resource-grid-name">{{ item.name }}</span>
                    </template>
                  </div>
                  <div v-if="resourceStore.maps.length === 0" class="resource-empty"></div>
                </div>
                <div v-else-if="editorStore.resourceTab === 'sound'" class="resource-grid" @click="closeSpriteContextMenus">
                  <div
                    v-for="item in resourceStore.sounds"
                    :key="item.id"
                    class="resource-grid-item"
                    :class="{ 'resource-grid-item-active': selectedResource === item.id }"
                    @click="selectedResource = item.id"
                    @contextmenu="onSoundContextMenu($event, item)"
                  >
                    <div class="resource-thumb resource-thumb-sound"><img :src="iconSoundIcon" class="resource-thumb-img" /></div>
                    <span class="resource-grid-name">{{ item.name }}</span>
                  </div>
                  <div v-if="resourceStore.sounds.length === 0" class="resource-empty"></div>
                </div>
                <div v-else class="resource-code-list" @click="closeCodeContextMenu">
                  <div
                    v-for="item in resourceStore.codes"
                    :key="item.id"
                    class="resource-code-item"
                    :class="{ 'resource-code-item-active': editorStore.currentTab?.id === item.id }"
                    @click="selectedResource = item.id; openResource(item)"
                    @dblclick="openResource(item)"
                    @contextmenu="onCodeContextMenu($event, item)"
                  >
                    <img :src="iconPython" class="resource-code-icon" />
                    <template v-if="codeRenameId === item.id">
                      <input
                        class="code-rename-input"
                        v-model="codeRenameValue"
                        @blur="confirmCodeRename"
                        @keydown.enter.prevent="confirmCodeRename"
                        @keydown.escape="cancelCodeRename"
                        @click.stop
                      />
                    </template>
                    <template v-else>
                      <span class="resource-code-name">{{ codeDisplayName(item.name) }}</span>
                    </template>
                  </div>
                </div>
              </div>
              <UploadDrawer v-if="editorStore.resourceTab !== 'code'" :type="editorStore.resourceTab" @uploaded="onResourceUploaded" @open-library="onOpenLibrary" @open-paint="onOpenPaint" @create-map="onCreateMap" @import-map-image="onImportMapImage" />
            </div>
          </div>

          <!-- 游戏模式编辑区 -->
          <div class="game-editor-area">
            <div class="tab-bar">
              <div class="tab-bar-tabs">
                <div v-for="(tab, index) in editorStore.currentTabs" :key="tab.id" class="tab-item" :class="{ 'tab-item-active': editorStore.activeTabIndex === index }" @click="editorStore.setActiveTab(index)" @contextmenu="onTabContextMenu($event, index)">
                  <template v-if="tabRenameId === tab.id">
                    <input class="tab-rename-input" v-model="tabRenameValue" @blur="confirmTabRename" @keydown.enter.prevent="confirmTabRename" @keydown.escape="cancelTabRename" @click.stop />
                  </template>
                  <template v-else>
                    <span v-if="tab.modified" class="tab-modified-dot"></span>
                    <span @dblclick.stop="startTabRename(tab.id)">{{ codeDisplayName(tab.name) }}</span>
                  </template>
                  <button class="tab-close" @click.stop="editorStore.closeTab(index)">×</button>
                </div>
                <button class="tab-add" @click="editorStore.createTab('未命名.py', '')" v-tooltip="'新建文件'">+</button>
              </div>
            </div>
            <div class="code-area">
              <div class="code-splitter">
                <div class="code-editor-pane">
                  <CodeEditor />
                  <!-- 浮动工具栏 -->
                  <div class="ide-float-bar">
                    <button class="ide-float-btn" v-tooltip="'缩小'" @click="editorStore.zoomOut()"><img :src="iconReduceOne" width="16" height="16" /></button>
                    <button class="ide-float-btn ide-float-zoom" v-tooltip="'重置缩放'" @click="editorStore.resetZoom()">{{ editorStore.editorFontZoom }}%</button>
                    <button class="ide-float-btn" v-tooltip="'放大'" @click="editorStore.zoomIn()"><img :src="iconAddOne" width="16" height="16" /></button>
                    <div class="ide-float-divider"></div>
                    <button class="ide-float-btn" v-tooltip="'撤销'" @click="editorUndo"><img :src="iconUndo" width="14" height="14" /></button>
                    <button class="ide-float-btn" v-tooltip="'重做'" @click="editorRedo"><img :src="iconRedo" width="14" height="14" /></button>
                  </div>
                </div>
              </div>
              <TerminalPanel v-model:visible="consoleVisible" />
            </div>
          </div>
        </div>

        <!-- ═══ Page 3: 代码模式 IDE (Activity Bar + Side Panel + 编辑器) ═══ -->
        <div v-if="!editorStore.isGameMode" class="ide-layout-wrapper">
          <!-- Activity Bar (图标列) -->
          <div class="ide-activity-bar">
            <button
              class="activity-btn"
              :class="{ 'activity-btn-active': ideExplorerVisible && ideActivePanel === 'files' }"
              @click="ideActivePanel === 'files' ? (ideExplorerVisible = !ideExplorerVisible) : (ideActivePanel = 'files', ideExplorerVisible = true)"
              v-tooltip="'文件浏览器'"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>
            </button>
            <button
              class="activity-btn"
              :class="{ 'activity-btn-active': ideExplorerVisible && ideActivePanel === 'search' }"
              @click="ideActivePanel === 'search' ? (ideExplorerVisible = !ideExplorerVisible) : (ideActivePanel = 'search', ideExplorerVisible = true)"
              v-tooltip="'搜索'"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="10" cy="10" r="6" stroke="currentColor" stroke-width="1.5"/><path d="M15 15l4.5 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
            </button>
            <button
              class="activity-btn"
              :class="{ 'activity-btn-active': ideExplorerVisible && ideActivePanel === 'outline' }"
              @click="ideActivePanel === 'outline' ? (ideExplorerVisible = !ideExplorerVisible) : (ideActivePanel = 'outline', ideExplorerVisible = true)"
              v-tooltip="'代码大纲'"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M4 6h16M4 12h10M4 18h14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
            </button>
            <button
              class="activity-btn"
              :class="{ 'activity-btn-active': ideExplorerVisible && ideActivePanel === 'snippets' }"
              @click="ideActivePanel === 'snippets' ? (ideExplorerVisible = !ideExplorerVisible) : (ideActivePanel = 'snippets', ideExplorerVisible = true)"
              v-tooltip="'代码片段'"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M9.4 16.6L4.8 12l4.6-4.6M14.6 7.4l4.6 4.6-4.6 4.6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
            </button>
            <button
              class="activity-btn"
              :class="{ 'activity-btn-active': ideExplorerVisible && ideActivePanel === 'learn' }"
              @click="ideActivePanel === 'learn' ? (ideExplorerVisible = !ideExplorerVisible) : (ideActivePanel = 'learn', ideExplorerVisible = true)"
              v-tooltip="'Python 速查'"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.5"/><path d="M12 8v5M12 16h.01" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
            </button>
          </div>

          <!-- Side Panel (根据 activePanel 切换内容) -->
          <aside class="ide-side-panel" v-show="ideExplorerVisible" :style="{ width: sidePanelWidth + 'px' }">
            <FileExplorer v-if="ideActivePanel === 'files'" />
            <SearchPanel v-else-if="ideActivePanel === 'search'" />
            <OutlinePanel v-else-if="ideActivePanel === 'outline'" />
            <SnippetPanel v-else-if="ideActivePanel === 'snippets'" />
            <LearnPanel v-else-if="ideActivePanel === 'learn'" />
            <!-- 拖拽手柄 -->
            <div
              class="ide-side-resize-handle"
              :class="{ 'ide-side-resize-active': isResizingSidePanel }"
              @mousedown="startResizeSidePanel"
            ></div>
          </aside>

          <!-- 右侧编辑器区域 -->
          <div class="editor-page-full">
            <div class="ide-tab-bar">
              <div class="tab-bar-tabs">
                <div v-for="(tab, index) in editorStore.currentTabs" :key="tab.id" class="tab-item" :class="{ 'tab-item-active': editorStore.activeTabIndex === index }" @click="editorStore.setActiveTab(index)" @contextmenu="onTabContextMenu($event, index)">
                  <template v-if="tabRenameId === tab.id">
                    <input class="tab-rename-input" v-model="tabRenameValue" @blur="confirmTabRename" @keydown.enter.prevent="confirmTabRename" @keydown.escape="cancelTabRename" @click.stop />
                  </template>
                  <template v-else>
                    <span v-if="tab.modified" class="tab-modified-dot"></span>
                    <span @dblclick.stop="startTabRename(tab.id)">{{ codeDisplayName(tab.name) }}</span>
                  </template>
                  <button class="tab-close" @click.stop="editorStore.closeTab(index)">×</button>
                </div>
                <button class="tab-add" @click="ideNewFileInTree" v-tooltip="'新建文件'">+</button>
              </div>
            </div>
            <div class="ide-editor-area">
              <CodeEditor />
              <!-- 浮动工具栏 -->
              <div class="ide-float-bar">
                <button class="ide-float-btn" v-tooltip="'缩小'" @click="editorStore.zoomOut()"><img :src="iconReduceOne" width="16" height="16" /></button>
                <button class="ide-float-btn ide-float-zoom" v-tooltip="'重置缩放'" @click="editorStore.resetZoom()">{{ editorStore.editorFontZoom }}%</button>
                <button class="ide-float-btn" v-tooltip="'放大'" @click="editorStore.zoomIn()"><img :src="iconAddOne" width="16" height="16" /></button>
                <div class="ide-float-divider"></div>
                <button class="ide-float-btn" v-tooltip="'撤销'" @click="editorUndo"><img :src="iconUndo" width="14" height="14" /></button>
                <button class="ide-float-btn" v-tooltip="'重做'" @click="editorRedo"><img :src="iconRedo" width="14" height="14" /></button>
              </div>
            </div>
            <TerminalPanel v-model:visible="consoleVisible" />
          </div>
        </div>

      </div>

      <!-- ─── page 1: fullscreen (Scratch 风格) ─── -->
      <div v-show="currentPage === 1" class="fullscreen-page">
        <div class="fullscreen-toolbar">
          <div class="toolbar-left" :style="{ paddingLeft: canvasOffsetX + 'px' }">
            <button class="tool-btn" :class="{ 'tool-btn-active': editorStore.isRunning }" @click="toggleRun">
              <img :src="iconPlay" width="16" height="16" />
            </button>
            <button class="tool-btn" @click="engine.stop()">
              <img :src="iconStop" width="16" height="16" />
            </button>
          </div>
          <div class="toolbar-divider"></div>
          <button class="tool-btn" :class="{ 'tool-btn-active': renderStore.showFps }"
                  @click="toggleShowFps" v-tooltip="'显示帧数'">
            <img :src="iconFps" width="18" height="18" />
          </button>
          <button class="tool-btn" :class="{ 'tool-btn-active': renderStore.showCollision }"
                  @click="toggleShowCollision" v-tooltip="'显示碰撞'">
            <img :src="iconCollision" width="18" height="18" />
          </button>
          <button class="tool-btn" :class="{ 'tool-btn-active': renderStore.showStats }"
                  @click="toggleShowStats" v-tooltip="'性能面板'">
            <img :src="iconStats" width="18" height="18" />
          </button>
          <div class="tool-spacer"></div>
          <div class="toolbar-right" :style="{ paddingRight: canvasOffsetX + 'px' }">
            <button class="tool-btn" @click="switchPage(0)">
              <img :src="iconUnfullscreen" width="20" height="20" />
            </button>
          </div>
        </div>
        <div class="fullscreen-stage-area">
          <GameCanvas v-show="currentPage === 1" @offset-update="canvasOffsetX = $event" />
        </div>
      </div>

      <!-- ─── page 2: 地图库 ─── -->
      <div v-show="currentPage === 2" class="lib-page">
        <MapLibraryPage :key="mapLibPageKey" @close="switchPage(0)" @imported="onMapLibImported" @imported-image="onMapLibImportedImage" />
      </div>

      <!-- ─── page 3: 角色库 (独立全屏页面) ─── -->
      <div v-show="currentPage === 3" class="lib-page">
        <SpriteLibPage :key="spriteLibPageKey" @close="switchPage(0)" @imported="onSpriteLibImported" />
      </div>

      <!-- ─── page 4: 素材库 ─── -->
      <div v-show="currentPage === 4" class="lib-page">
        <MapResourceLibPage :key="mapResLibPageKey" @close="switchPage(0)" @imported="onResLibImported" />
      </div>

      <!-- ─── page 5: 声音库 ─── -->
      <div v-show="currentPage === 5" class="lib-page">
        <SoundLibPage @close="switchPage(0)" @imported="onSoundLibImported" />
      </div>

      <!-- ─── page 6: 角色绘制器 ─── -->
      <div v-show="currentPage === 6" class="lib-page">
        <PaintEditorPage
          :key="paintPageKey"
          :target-sprite="paintTarget"
          :open-mode="paintOpenMode"
          :initial-frame-index="paintInitialFrameIndex"
          @close="switchPage(0)"
          @saved="onPaintSaved"
        />
      </div>

      <!-- ─── page 7: 造型选帧库（内置素材帧追加到当前角色） ─── -->
      <div v-show="currentPage === 7" class="lib-page">
        <FramePickerPage :key="framePickerKey" @close="switchPage(0)" @picked="onFramePicked" />
      </div>

    </div>

    <!-- 控制台按钮已移至游戏模式编辑区内 -->

    <!-- 角色右键菜单 -->
    <Teleport to="body">
      <div
        v-if="spriteContextMenu.show"
        class="sprite-ctx-menu"
        :style="{ left: spriteContextMenu.x + 'px', top: spriteContextMenu.y + 'px' }"
        @click.stop
      >
        <div class="sprite-ctx-item" @click="startSpriteRename(spriteContextMenu.item!.id)">重命名</div>
        <div class="sprite-ctx-item sprite-ctx-del" @click="deleteSpriteFromContext(spriteContextMenu.item!.id)">删除</div>
      </div>
    </Teleport>

    <!-- 代码右键菜单 -->
    <Teleport to="body">
      <div
        v-if="codeContextMenu.show"
        class="sprite-ctx-menu"
        :style="{ left: codeContextMenu.x + 'px', top: codeContextMenu.y + 'px' }"
        @click.stop
      >
        <div class="sprite-ctx-item" @click="startCodeRename(codeContextMenu.item!.id)">重命名</div>
        <div class="sprite-ctx-item sprite-ctx-del" @click="deleteCodeFromContext(codeContextMenu.item!.id)">删除</div>
      </div>
    </Teleport>

    <!-- 地图右键菜单 -->
    <Teleport to="body">
      <div
        v-if="mapContextMenu.show"
        class="sprite-ctx-menu"
        :style="{ left: mapContextMenu.x + 'px', top: mapContextMenu.y + 'px' }"
        @click.stop
      >
        <div class="sprite-ctx-item" @click="startMapRename(mapContextMenu.item!.id)">重命名</div>
        <div class="sprite-ctx-item sprite-ctx-del" @click="deleteMapFromContext(mapContextMenu.item!.id)">删除</div>
      </div>
    </Teleport>

    <!-- 声音右键菜单 -->
    <Teleport to="body">
      <div
        v-if="soundContextMenu.show"
        class="sprite-ctx-menu"
        :style="{ left: soundContextMenu.x + 'px', top: soundContextMenu.y + 'px' }"
        @click.stop
      >
        <div class="sprite-ctx-item sprite-ctx-del" @click="deleteSoundFromContext(soundContextMenu.item!.id)">删除</div>
      </div>
    </Teleport>

    <!-- 帮助面板（游戏模式） -->
    <HelpPanel :visible="helpVisible && editorStore.isGameMode" @close="helpVisible = false" />

    <!-- 帮助面板（代码模式） -->
    <PythonHelpPanel :visible="helpVisible && !editorStore.isGameMode" @close="helpVisible = false" />

    <!-- AI 助手面板 -->
    <AiChatPanel :visible="aiChatVisible" @close="aiChatVisible = false" />

    <!-- 插件库弹窗 -->
    <PluginManager v-if="pluginManagerVisible" @close="pluginManagerVisible = false" />

    <!-- 更新提示 -->
    <UpdateDialog />

    <!-- 标签页右键菜单 -->
    <Teleport to="body">
      <div v-if="tabContextMenu.show" class="tab-ctx-menu" :style="{ left: tabContextMenu.x + 'px', top: tabContextMenu.y + 'px' }">
        <div class="tab-ctx-item" @click.stop="tabCtxClose">关闭</div>
        <div class="tab-ctx-item" @click.stop="tabCtxCloseOthers">关闭其他</div>
        <div class="tab-ctx-item" @click.stop="tabCtxCloseToRight">关闭右侧</div>
        <div class="tab-ctx-divider" />
        <div class="tab-ctx-item" @click.stop="tabCtxCloseAll">关闭所有</div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
/* ═══ 全局 ═══ */
.app-root {
  display: flex;
  flex-direction: column;
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: var(--bg-root);
  color: white;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft YaHei', 'PingFang SC', Roboto, sans-serif;
}

/* ═══ 顶部菜单栏 ═══ */
.menu-bar {
  display: flex;
  align-items: stretch;
  height: 40px;
  min-height: 40px;
  padding: 0;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border);
  background: var(--bg-root);
}
.menu-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 60px;
  flex-shrink: 0;
  background: var(--bg-root);
  border: none;
  cursor: pointer;
}
.menu-logo-img {
  width: 90px;
  height: 38px;
  object-fit: contain;
}
.menu-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}
.menu-btn {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex-shrink: 0;
  background: transparent;
  border: none;
  color: white;
  cursor: pointer;
  transition: background 0.15s;
  padding: 0 12px;
}
.menu-btn span {
  font-size: 11px;
  line-height: 1;
  white-space: nowrap;
}
.menu-btn:hover { background: var(--bg-hover); }
.menu-btn-help {
  width: 40px;
  min-width: 40px;
  padding: 0;
  justify-content: center;
}
.menu-btn-help:hover { background: transparent; }
.menu-btn-help:active { background: transparent; }
.menu-spacer { flex: 1; }

/* 文件下拉菜单 */
.menu-file-wrapper {
  position: relative;
  display: flex;
  align-items: stretch;
}
.menu-btn-file {
  overflow: hidden;
}
.file-menu-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  width: 144px;
  background: var(--bg-root);
  border-radius: 6px;
  padding: 4px 0;
  z-index: 100;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}
.file-menu-item {
  display: block;
  width: 100%;
  height: 32px;
  padding: 0 15px;
  background: transparent;
  border: none;
  color: white;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  border-radius: 4px;
  margin: 2px 8px;
  width: calc(100% - 16px);
  transition: background 0.12s;
}
.file-menu-item:hover {
  background: var(--bg-hover);
}
.file-menu-divider {
  height: 1px;
  margin: 4px 12px;
  background: rgb(50, 53, 60);
}
.settings-menu {
  width: 144px;
}
.settings-item-group {
  position: relative;
}
.settings-menu-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.settings-arrow {
  font-size: 14px;
  color: rgb(120, 120, 120);
}
.settings-submenu {
  position: absolute;
  left: 100%;
  top: -4px;
  width: 152px;
  background: var(--bg-root);
  border-radius: 6px;
  padding: 4px 0;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}
.settings-item-active {
  color: var(--accent);
}
/* 引擎设置内的小号 toggle 开关（子菜单仅 128px 宽） */
.settings-toggle {
  position: relative;
  width: 28px;
  height: 16px;
  border-radius: 8px;
  background: rgb(72, 76, 86);
  transition: background 0.2s;
  flex-shrink: 0;
}
.settings-toggle-on {
  background: var(--accent);
}
.settings-toggle-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: white;
  transition: transform 0.2s;
}
.settings-toggle-on .settings-toggle-knob {
  transform: translateX(12px);
}
.settings-item-disabled {
  color: rgb(100, 100, 100);
  cursor: default;
}
.settings-item-disabled:hover {
  background: transparent;
}
.settings-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 0;
}

/* 检查更新按钮圆点提示 */
.settings-update-btn {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.update-dot {
  width: 6px;
  height: 6px;
  background: #5BFB84;
  border-radius: 50%;
}

/* 模式切换开关 */
.mode-switch {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-right: 8px;
}
.mode-label {
  font-size: 11px;
  color: var(--text-secondary);
}
.toggle-switch {
  position: relative;
  width: 36px;
  height: 20px;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  background: var(--accent);
  transition: background 0.2s;
}
.toggle-switch.toggle-on { background: var(--accent); }
.toggle-knob {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: white;
  transition: transform 0.2s;
}
.toggle-on .toggle-knob { transform: translateX(16px); }

/* ═══ 主内容区 ═══ */
.main-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* ═══ edit_stage_frame ═══ */
.edit-stage-frame {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* 游戏模式页面 */
.editor-page-game {
  display: flex;
  height: 100%;
}

/* 全宽编辑器页面 (角色/地图/IDE) */
.editor-page-full {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-base);
}

/* 游戏模式编辑区 */
.game-editor-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-base);
}

/* IDE 模式标签栏 */
.ide-tab-bar {
  display: flex;
  align-items: center;
  height: 30px;
  background: var(--bg-root);
  flex-shrink: 0;
}

/* IDE 布局：Activity Bar + Side Panel + 编辑器 */
.ide-layout-wrapper {
  flex: 1;
  display: flex;
  min-height: 0;
}

/* Activity Bar (图标列) */
.ide-activity-bar {
  width: 44px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 0;
  background: rgb(30, 30, 30);
  border-right: 1px solid var(--border);
  gap: 2px;
}
.activity-btn {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: var(--text-muted);
  cursor: pointer;
  position: relative;
  transition: color 0.12s, background 0.12s;
}
.activity-btn:hover {
  color: var(--text);
  background: rgba(255,255,255,0.06);
}
.activity-btn-active {
  color: var(--text);
}
.activity-btn-active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 2px;
  background: var(--accent);
  border-radius: 0 2px 2px 0;
}

/* Side Panel (内容面板) */
.ide-side-panel {
  flex-shrink: 0;
  border-right: 1px solid var(--border);
  background: var(--bg-root);
  overflow: hidden;
  position: relative;
}

/* 侧边栏拖拽手柄 */
.ide-side-resize-handle {
  position: absolute;
  top: 0;
  right: -3px;
  bottom: 0;
  width: 7px;
  cursor: col-resize;
  z-index: 10;
}
.ide-side-resize-handle::after {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 3px;
  width: 2px;
  background: transparent;
  transition: background 0.1s ease;
}
.ide-side-resize-handle:hover::after,
.ide-side-resize-active::after {
  background: var(--accent);
}

/* IDE 编辑器区域 */
.ide-editor-area {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  position: relative;
}

/* ═══ 左侧边栏 ═══ */
.sidebar {
  width: 340px;
  min-width: 340px;
  max-width: 340px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--border);
  background: var(--bg-root);
  padding: 0 8px;
}
.sidebar-toolbar {
  display: flex;
  align-items: center;
  height: 30px;
  padding: 0 5px;
  gap: 5px;
  flex-shrink: 0;
}
.tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 2px;
  color: white;
  cursor: pointer;
  transition: all 0.15s;
}
.tool-btn:hover { background: var(--danger); border-color: var(--border-light); }
.tool-btn:active { background: var(--danger); }
.tool-btn-active { background: var(--danger); border-color: var(--border-light); }
.tool-spacer { flex: 1; }

/* 游戏预览 */
.game-preview-wrapper {
  display: flex;
  flex-shrink: 0;
}
.game-preview-container {
  width: 324px;
  height: 244px;
  border: 2px solid #4e4e4e;
  background: var(--bg-panel);
  overflow: hidden;
  position: relative;
}
.game-preview-canvas { width: 100%; height: 100%; }
.game-preview-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-panel);
}

/* Loading覆盖层 */
.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  /* 全不透明：加载完成前完全遮住游戏画面，完成后才"进入"游戏 */
  background: #1a1c21;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.loading-content {
  text-align: center;
  color: white;
}

.loading-balls {
  display: flex;
  justify-content: center;
  gap: 6px;
  margin-bottom: 12px;
}

.ball {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent);
  animation: bounce 1.4s ease-in-out infinite;
}

.ball-1 { animation-delay: -0.32s; }
.ball-2 { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.loading-text {
  font-size: 12px;
  margin-bottom: 6px;
  color: rgba(255, 255, 255, 0.8);
}

.loading-progress {
  font-size: 10px;
  color: var(--accent);
  font-family: monospace;
  margin-bottom: 6px;
}

.loading-bar {
  width: 120px;
  height: 3px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
  overflow: hidden;
  margin: 0 auto;
}

.loading-bar-fill {
  height: 100%;
  background: var(--accent);
  transition: width 0.3s ease;
}

/* 资源标签 */
.outline-tabs {
  display: flex;
  height: 50px;
  flex-shrink: 0;
  align-items: center;
}
.outline-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: 0px solid transparent;
  border-bottom: 3px solid rgb(47, 47, 47);
  color: var(--text-muted);
  font-size: 13px;
  padding: 8px 8px 4px 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.outline-tab:hover { color: white; }
.outline-tab-active { color: var(--text); border-bottom-color: var(--accent); }

/* 资源列表 */
.outline-list-wrapper {
  flex: 1;
  min-height: 0;
  position: relative;
  background: var(--bg-darker);
}
.outline-list {
  height: 100%;
  overflow-y: auto;
  padding-bottom: 50px;
}

/* 角色/地图/声音图标网格 */
.resource-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 5px;
  padding: 6px 4px;
}
.resource-grid-item {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 5px;
  border-radius: 6px;
  cursor: pointer;
  min-width: 0;
}
.resource-grid-item:hover { background: var(--bg-hover); }
.resource-grid-item-active {
  background: var(--bg-active);
  box-shadow: inset 0 0 0 2px var(--accent);
}
.resource-grid-item-active:hover { box-shadow: inset 0 0 0 2px rgb(91, 199, 114); }
.resource-thumb {
  width: 100%;
  aspect-ratio: 1;
  background: transparent;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: white;
  overflow: hidden;
  flex-shrink: 0;
}
.resource-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  flex-shrink: 0;
}
.resource-thumb-map { background: var(--bg-hover); }
.resource-thumb-sound { background: rgb(61, 61, 61); }
.resource-thumb-checker {
  background-color: #2a2a2a;
  background-image:
    linear-gradient(45deg, #3a3a3a 25%, transparent 25%),
    linear-gradient(-45deg, #3a3a3a 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, #3a3a3a 75%),
    linear-gradient(-45deg, transparent 75%, #3a3a3a 75%);
  background-size: 10px 10px;
  background-position: 0 0, 0 5px, 5px -5px, -5px 0;
}
.resource-grid-name {
  font-size: 11px;
  color: var(--text-secondary);
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  width: 100%;
}
.sprite-rename-input {
  width: 74px;
  height: 18px;
  background: transparent;
  border: none;
  border-radius: 0;
  color: var(--text-secondary);
  font-size: 11px;
  padding: 0;
  text-align: center;
  outline: none;
  caret-color: white;
}
.map-rename-input {
  width: 74px;
  height: 18px;
  background: transparent;
  border: none;
  border-radius: 0;
  color: var(--text-secondary);
  font-size: 11px;
  padding: 0;
  text-align: center;
  outline: none;
  caret-color: white;
}
/* 重命名输入框选中高亮：主题 accent 绿背景 + 亮白文字，与主题风格统一 */
.sprite-rename-input::selection,
.map-rename-input::selection,
.code-rename-input::selection,
.tab-rename-input::selection {
  background: var(--accent);
  color: #e8eaed;
}
.resource-card-del {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  background: var(--danger);
  border: 2px solid rgb(45, 45, 45);
  border-radius: 9px;
  color: white;
  font-size: 11px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}
.resource-grid-item:hover .resource-card-del { opacity: 1; }
.resource-card-del:hover {   background: var(--danger-hover); }

/* 代码列表视图 */
.resource-code-list { padding: 4px 0; }
.resource-code-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 15px;
  cursor: pointer;
  position: relative;
}
.resource-code-item:hover { background: var(--bg-hover); }
.resource-code-item-active { background: var(--bg-hover); }
.resource-code-item-active:hover { background: var(--bg-hover); }
.resource-code-icon { width: 20px; height: 20px; flex-shrink: 0; }
.resource-code-name {
  font-size: 14px;
  color: var(--text-secondary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.code-rename-input {
  width: 0;
  min-width: 60px;
  max-width: 180px;
  flex: 1;
  height: 22px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 3px;
  color: #e8e8e8;
  font-size: 14px;
  padding: 0 4px;
  outline: none;
  caret-color: white;
}
.resource-code-actions {
  display: flex;
  gap: 8px;
  opacity: 0;
  transition: opacity 0.15s;
}
.resource-code-actions-show { opacity: 1; }
.resource-action-btn {
  width: 26px;
  height: 26px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.12s;
}
.resource-action-btn:hover { background: rgba(255, 255, 255, 0.1); }
.resource-action-del:hover { background: rgba(255, 77, 77, 0.2); }

/* 空状态 */
.resource-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100px;
  color: var(--text-muted);
  font-size: 12px;
}
.outline-list-inner { padding: 8px; }

/* ═══ 右侧编辑区 ═══ */
.editor-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-base);
}

/* tab_bar */
.tab-bar {
  display: flex;
  align-items: stretch;
  height: 30px;
  background: var(--bg-root);
  flex-shrink: 0;
}
.tab-bar-tabs {
  display: flex;
  align-items: stretch;
  height: 100%;
  flex: 1;
  overflow-x: auto;
}
.tab-item {
  display: flex;
  align-items: center;
  height: 30px;
  padding: 0 12px;
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  border-right: 1px solid var(--bg-root);
  flex-shrink: 0;
  transition: all 0.15s;
  max-width: 120px;
  overflow: hidden;
}
.tab-item span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tab-item:hover { color: var(--text); background: var(--bg-base); }
.tab-item-active { color: var(--text); background: var(--bg-base); border-bottom: 2px solid var(--accent); }
.tab-modified-dot {
  width: 8px;
  height: 8px;
  min-width: 8px;
  border-radius: 50%;
  background: var(--accent);
  margin-right: 6px;
  flex-shrink: 0;
}
.tab-close {
  margin-left: 6px;
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  opacity: 0;
  font-size: 14px;
  line-height: 1;
}
.tab-item:hover .tab-close { opacity: 0.6; }
.tab-close:hover { opacity: 1 !important; }
.tab-rename-input {
  width: 0;
  min-width: 60px;
  max-width: 96px;
  flex: 1;
  height: 20px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 3px;
  color: #e8e8e8;
  font-size: 12px;
  padding: 0 4px;
  outline: none;
  caret-color: white;
}
.tab-add {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 100%;
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 16px;
  cursor: pointer;
  flex-shrink: 0;
}
.tab-add:hover { color: var(--text); background: var(--bg-base); }

/* IDE 模式工具栏 */
.ide-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 8px;
  flex-shrink: 0;
  margin-left: auto;
}
.ide-tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 24px;
  background: transparent;
  border: none;
  border-radius: 3px;
  color: rgb(180, 180, 180);
  cursor: pointer;
  transition: all 0.15s;
}
.ide-tool-btn:hover { color: var(--text); background: var(--bg-hover); }
.ide-tool-btn-active { color: var(--text-secondary); background: var(--danger); }

/* IDE 浮动工具栏 */
.ide-float-bar {
  position: absolute;
  bottom: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 0;
  background: rgba(30, 32, 40, 0.92);
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  padding: 4px;
  z-index: 10;
}
.ide-float-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 30px;
  height: 26px;
  padding: 0 6px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: var(--text-muted);
  font-size: 14px;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}
.ide-float-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--text);
}
.ide-float-btn:active {
  background: rgba(255, 255, 255, 0.12);
}
.ide-float-zoom {
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  font-weight: 500;
  min-width: 44px;
  color: var(--text-secondary);
  cursor: pointer;
}
.ide-float-zoom:hover {
  color: var(--text);
}
.ide-float-divider {
  width: 1px;
  height: 14px;
  background: rgba(255, 255, 255, 0.1);
  margin: 0 4px;
}

/* 代码区 */
.code-area {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 0 8px;
}
.code-splitter {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.code-editor-pane {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  position: relative;
}
.game-canvas-full {
  width: 100%;
  height: 100%;
}

/* 控制台样式已移至 TerminalPanel 组件 */
.console-btn {
  padding: 0 8px;
  font-size: 11px;
  color: rgb(100, 100, 100);
  background: transparent;
  border: none;
  cursor: pointer;
}
.console-btn:hover { color: rgb(200, 200, 200); }

/* ═══ 全屏页 (Scratch 风格：toolbar 全宽顶栏，canvas 居中) ═══ */
.fullscreen-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: rgb(18, 20, 24);
}
.fullscreen-toolbar {
  display: flex;
  align-items: center;
  height: 34px;
  flex-shrink: 0;
  background: var(--bg-root);
  border-bottom: 1px solid var(--border);
  gap: 4px;
  padding: 0;
}
.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
}
.toolbar-divider {
  width: 1px;
  height: 18px;
  background: var(--border);
  margin: 0 4px;
}
.fullscreen-stage-area {
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

/* ═══ 资源库页 ═══ */
.lib-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-root);
}
.lib-toolbar {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 5px;
  gap: 0;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border);
}
.lib-search {
  width: 200px;
  height: 28px;
  padding: 0 8px;
  background: rgb(52, 55, 62);
  border: 1px solid rgb(73, 76, 86);
  border-radius: 6px;
  color: rgb(150, 150, 150);
  font-size: 12px;
  outline: none;
}
.lib-search:focus { border-color: var(--accent); }
.lib-spacer { flex: 1; }
.lib-hint { font-size: 12px;   color: var(--text-secondary); }
.lib-return-btn {
  width: 80px;
  height: 28px;
  background: rgb(52, 55, 62);
  border: 1px solid rgb(73, 76, 86);
  border-radius: 4px;
  color: rgb(150, 150, 150);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.lib-return-btn:hover { background: rgb(62, 65, 72); color: white; }
.lib-tab-btn {
  padding: 4px 16px;
  background: transparent;
  border: 1px solid rgb(73, 76, 86);
  border-radius: 4px;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.lib-tab-btn:hover { color: white; }
.lib-tab-active { background: var(--accent); color: var(--text); border-color: var(--accent); }
.lib-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
}

/* ═══ 底部控制台按钮 ═══ */
.console-toggle {
  position: fixed;
  bottom: 0;
  right: 0;
  padding: 4px 12px;
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-root);
  border: 1px solid var(--border);
  border-right: none;
  border-top: none;
  border-top-left-radius: 4px;
  cursor: pointer;
  z-index: 50;
}
.console-toggle:hover { color: var(--text); background: var(--bg-base); }

/* ═══ 角色右键菜单 ═══ */
.sprite-ctx-menu {
  position: fixed;
  background: var(--bg-root);
  border: 1px solid rgb(60, 60, 60);
  border-radius: 6px;
  padding: 4px 0;
  z-index: 9999;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
  min-width: 100px;
}
.sprite-ctx-item {
  padding: 6px 14px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}
.sprite-ctx-item:hover { background: var(--bg-hover); color: var(--text); }
.sprite-ctx-del:hover { background: var(--danger); color: var(--text); }

/* ═══ 标签页右键菜单 ═══ */
.tab-ctx-menu {
  position: fixed;
  background: var(--bg-root);
  border: 1px solid rgb(60, 60, 60);
  border-radius: 6px;
  padding: 4px 0;
  z-index: 9999;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
  min-width: 120px;
}
.tab-ctx-item {
  padding: 6px 14px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}
.tab-ctx-item:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.tab-ctx-divider {
  height: 1px;
  background: rgb(60, 60, 60);
  margin: 4px 0;
}
</style>
