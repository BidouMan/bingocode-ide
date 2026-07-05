<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { open, save } from '@tauri-apps/plugin-dialog'
import { useEditorStore } from '../../stores/editor'
import { useResourceStore } from '../../stores/resource'
import { useProjectStore } from '../../stores/project'
import { useMapStore } from '../../stores/map'
import { useRenderStore } from '../../stores/render'
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
import iconPython from '../../assets/icons/python_file_1.svg'
import iconUndo from '../../assets/icons/undo.svg'
import iconRedo from '../../assets/icons/redo.svg'

const editorStore = useEditorStore()
const resourceStore = useResourceStore()
const projectStore = useProjectStore()
const mapStore = useMapStore()
const renderStore = useRenderStore()
const engine = useEngine()
const fileDialog = useFileDialog()

// change_page: 0=编辑器, 1=全屏, 2=地图库, 3=角色库, 4=素材库, 5=声音库
const currentPage = ref(0)
const consoleVisible = ref(false)
const canvasOffsetX = ref(0)
const consoleExpanded = ref(true)
const fileMenuVisible = ref(false)
const settingsMenuVisible = ref(false)
const settingsSubmenu = ref<string | null>(null)
const selectedResource = ref<string | null>(null)

// 角色缩略图缓存
const spriteThumbnails = ref<Record<string, string>>({})
// 地图缩略图缓存
const mapThumbnails = ref<Record<string, string>>({})
// 角色右键菜单
const spriteContextMenu = ref<{ show: boolean; x: number; y: number; item: { id: string; name: string } | null }>({ show: false, x: 0, y: 0, item: null })
const spriteRenameId = ref<string | null>(null)

// 代码资源管理
const codeContextMenu = ref<{ show: boolean; x: number; y: number; item: { id: string; name: string } | null }>({ show: false, x: 0, y: 0, item: null })
const codeRenameId = ref<string | null>(null)
const codeRenameValue = ref('')
const spriteRenameValue = ref('')

// 地图右键菜单
const mapContextMenu = ref<{ show: boolean; x: number; y: number; item: { id: string; name: string } | null }>({ show: false, x: 0, y: 0, item: null })
const mapRenameId = ref<string | null>(null)
const mapRenameValue = ref('')

// 角色列表变化时立即加载缩略图
function loadAllSpriteThumbnails() {
  for (const item of resourceStore.sprites) {
    if (item.path && !spriteThumbnails.value[item.id]) {
      loadSpriteThumbnail(item)
    }
  }
}

watch(() => [...resourceStore.sprites], loadAllSpriteThumbnails)

onMounted(loadAllSpriteThumbnails)

// 地图缩略图：只在切换到地图标签时刷新（不用实时）
function loadAllMapThumbnails() {
  for (const item of resourceStore.maps) {
    if (item.path) {
      loadMapThumbnail(item)
    }
  }
}

// 地图列表变化时不自动加载缩略图（改为切换标签时刷新）
watch(() => editorStore.resourceTab, (tab) => {
  if (tab === 'map') {
    // 切换到地图标签时刷新缩略图
    mapThumbnails.value = {}
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

// 新项目不预创建地图，用户通过按钮创建
onMounted(async () => {
  // 初始化默认项目目录
  await projectStore.initProject()
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

function openSettingsSubmenu(name: string) {
  settingsSubmenu.value = name
}

async function fileMenuAction(action: string) {
  closeFileMenu()

  // 任何项目操作都先停止运行
  if (editorStore.isRunning) {
    await engine.stop()
    renderStore.clearAll()
  }

  switch (action) {
    case 'new': {
      const projectRoot = await projectStore.newProject()
      if (!projectRoot) break
      // 清空所有旧数据
      resourceStore.clearAllResources()
      renderStore.clearAll()
      const gameTabs = editorStore.gameTabs
      gameTabs.splice(0, gameTabs.length)
      editorStore.gameActiveTabIndex = 0
      await nextTick()
      // 创建新项目默认代码文件
      const name = '未命名-1.py'
      const code = 'print("Hello Bingo!")\n'
      await invoke('create_dir', { path: `${projectRoot}/code` })
      await invoke('write_file', { path: `${projectRoot}/code/${name}`, content: code })
      editorStore.createTab(name, `${projectRoot}/code/${name}`, code)
      resourceStore.addItem({ name, type: 'code', path: `${projectRoot}/code/${name}`, content: code })
      break
    }

    case 'open': {
      const path = await open({
        title: '打开项目',
        filters: [{ name: 'Bingo 项目', extensions: ['bingo'] }],
      })
      if (!path) break
      await projectStore.openProject(path)
      const root = projectStore.root
      if (!root) break

      // 清空全部旧数据
      resourceStore.clearAllResources()
      renderStore.clearAll()
      const editorTabs = editorStore.gameTabs
      editorTabs.splice(0, editorTabs.length)
      editorStore.gameActiveTabIndex = 0
      await nextTick()

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
          resourceStore.addItem({ name: dirName, type: 'sprite', path: dirPath })
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

      // 刷新缩略图
      loadAllSpriteThumbnails()
      loadAllMapThumbnails()

      // 切换到第一个代码标签（如有）
      if (editorStore.currentTabs.length > 0) {
        editorStore.setActiveTab(0)
      }
      editorStore.setGameMode(true)
      editorStore.setActiveEditorMode('code')
      editorStore.setResourceTab('code')
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
          filters: [{ name: 'Bingo 项目', extensions: ['bingo'] }],
          defaultPath: `${projectStore.name || '未命名项目'}.bingo`,
        })
        if (!path) break
        await projectStore.saveProjectAs(path)
      }
      break
    }

    case 'saveAs': {
      const path = await save({
        title: '另存为',
        filters: [{ name: 'Bingo 项目', extensions: ['bingo'] }],
        defaultPath: `${projectStore.name || '未命名项目'}.bingo`,
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

async function toggleRun() {
  // 点击总是重新运行：如果正在运行先停掉
  if (editorStore.isRunning) {
    await engine.stop()
    // 等一帧确保引擎完全释放
    await new Promise(r => setTimeout(r, 50))
  }
  consoleVisible.value = true
  await nextTick()
  await engine.run()
}

async function uploadResource(type: 'sprite' | 'map' | 'sound' | 'code') {
  const acceptMap: Record<string, string> = {
    sprite: '.bgs,.png,.jpg,.gif',
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

async function openResource(item: { id: string; name: string; type: string; content?: string }) {
  if (item.type === 'code') {
    // 在游戏模式标签中查找
    const idx = editorStore.gameTabs.findIndex(t => t.id === item.id)
    if (idx >= 0) {
      editorStore.setGameMode(true)
      editorStore.setActiveTab(idx)
    }
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
  }
  // TODO: sound=5
}

async function onCreateMap() {
  const projectRoot = projectStore.root
  if (!projectRoot) return

  const mapCount = resourceStore.maps.length
  const name = `地图${mapCount + 1}`

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
        name: '图像图层',
        type: 'imagelayer',
        visible: true,
        locked: false,
        data: '',
        images: [],
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

async function onMapLibImported(bgmUrl: string, name: string) {
  const projectRoot = projectStore.root
  if (!projectRoot) return

  // 获取引擎素材目录，找到 .bgm 文件
  const engineAssetsDir = await invoke<string>('get_engine_assets_dir')
  const bgmPath = `${engineAssetsDir}/maps/packages/${name}.bgm`

  // 解压 .bgm 到项目目录
  try {
    await invoke<string>('extract_bgm_to_project', {
      bgmPath,
      projectRoot,
      mapName: name,
    })
  } catch (e) {
    console.error('[MapLib] 解压失败:', e)
    return
  }

  const projectPath = `${projectRoot}/assets/maps/${name}`
  resourceStore.addItem({ name, type: 'map', path: projectPath })
  editorStore.setResourceTab('map')
  currentPage.value = 0
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
    tileSetIndex: 0,
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
  currentPage.value = page
}

// 双击角色跳转到角色编辑页面
function openSpriteEditor(item: { id: string; name: string; path: string }) {
  resourceStore.selectedSpriteId = item.id
  editorStore.setActiveEditorMode('sprite')
  editorStore.setGameMode(false)
}

// 加载角色缩略图（通过 Rust 命令从解压目录读取）
async function loadSpriteThumbnail(item: { id: string; path: string }) {
  if (spriteThumbnails.value[item.id]) return
  if (!item.path) return
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    const dataUrl = await invoke<string>('get_sprite_thumbnail', {
      path: item.path,
    })
    spriteThumbnails.value[item.id] = dataUrl
  } catch (e) {
    console.warn('Failed to load sprite thumbnail:', e)
  }
}

async function loadMapThumbnail(item: { id: string; path: string }) {
  if (mapThumbnails.value[item.id]) return
  if (!item.path) return
  try {
    const { convertFileSrc } = await import('@tauri-apps/api/core')
    // 解压后的地图目录中有 thumbnail.png
    const thumbUrl = convertFileSrc(`${item.path}/thumbnail.png`)
    const resp = await fetch(thumbUrl)
    if (resp.ok) {
      mapThumbnails.value[item.id] = thumbUrl
    }
  } catch {
    // thumbnail load failed
  }
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
      input.setSelectionRange(input.value.length, input.value.length)
    }
  }))
}

function confirmSpriteRename() {
  if (!spriteRenameId.value) return
  const val = spriteRenameValue.value.trim()
  if (val) resourceStore.renameItem(spriteRenameId.value, val)
  spriteRenameId.value = null
}

function cancelSpriteRename() {
  spriteRenameId.value = null
}

function closeSpriteContextMenus() {
  spriteContextMenu.value.show = false
  mapContextMenu.value.show = false
  codeContextMenu.value.show = false
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
      input.setSelectionRange(input.value.length, input.value.length)
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

// 同步游戏模式标签和代码资源管理器
watch(() => [...editorStore.gameTabs], (tabs) => {
  for (const tab of tabs) {
    const existing = resourceStore.codes.find(c => c.id === tab.id)
    if (!existing) {
      resourceStore.codes.push({ id: tab.id, name: tab.name, type: 'code', path: tab.path, content: tab.content })
    } else {
      existing.name = tab.name
    }
  }
  // 移除资源管理器中不存在的标签
  resourceStore.codes = resourceStore.codes.filter(c => tabs.some(t => t.id === c.id))
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

function confirmCodeRename() {
  if (!codeRenameId.value) return
  const val = codeRenameValue.value.trim()
  if (val && val !== '') {
    const nameWithPy = val.endsWith('.py') ? val : val + '.py'
    // 同步更新标签页名称
    const tab = editorStore.gameTabs.find(t => t.id === codeRenameId.value)
    if (tab) tab.name = nameWithPy
    // 同步更新资源管理器
    const codeItem = resourceStore.codes.find(c => c.id === codeRenameId.value)
    if (codeItem) codeItem.name = nameWithPy
  }
  codeRenameId.value = null
  codeRenameValue.value = ''
}

function cancelCodeRename() {
  codeRenameId.value = null
  codeRenameValue.value = ''
}

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

function confirmTabRename() {
  if (!tabRenameId.value) return
  const val = tabRenameValue.value.trim()
  if (val) {
    const nameWithPy = val.endsWith('.py') ? val : val + '.py'
    const tab = editorStore.currentTabs.find(t => t.id === tabRenameId.value)
    if (tab) tab.name = nameWithPy
    // 同步资源管理器
    const codeItem = resourceStore.codes.find(c => c.id === tabRenameId.value)
    if (codeItem) codeItem.name = nameWithPy
  }
  tabRenameId.value = null
  tabRenameValue.value = ''
}

function cancelTabRename() {
  tabRenameId.value = null
  tabRenameValue.value = ''
}

// 代码文件显示名：隐藏 .py 后缀
function codeDisplayName(name: string) {
  return name.endsWith('.py') ? name.slice(0, -3) : name
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
          <button class="menu-btn menu-btn-file" title="项目" @click="toggleFileMenu">
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
        <!-- 新建 -->
        <button class="menu-btn" @click="editorStore.createTab('未命名.py', '')" title="新建">
          <img :src="iconNewMap" class="menu-icon" />
          <span>新建</span>
        </button>

        <!-- 打开 -->
        <button class="menu-btn" @click="fileMenuAction('open')" title="打开">
          <img :src="iconCodeOpen" class="menu-icon" />
          <span>打开</span>
        </button>

        <!-- 保存 -->
        <button class="menu-btn" @click="fileMenuAction('save')" title="保存">
          <img :src="iconCodeSave" class="menu-icon" />
          <span>保存</span>
        </button>

        <!-- 运行/停止 (代码模式单个切换) -->
        <button class="menu-btn" @click="toggleRun" :title="editorStore.isRunning ? '停止' : '运行'">
          <img v-if="!editorStore.isRunning" :src="iconCodeRun" class="menu-icon" />
          <img v-else :src="iconCodeStop" class="menu-icon" />
          <span>{{ editorStore.isRunning ? '停止' : '运行' }}</span>
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
          <div class="settings-item-group" @mouseenter="openSettingsSubmenu('renderMode')">
            <div class="file-menu-item settings-menu-item">
              <span>渲染模式</span>
              <span class="settings-arrow">›</span>
            </div>
            <div v-show="settingsSubmenu === 'renderMode'" class="settings-submenu">
              <button class="file-menu-item" :class="{ 'settings-item-active': editorStore.renderMode === 'smooth' }" @click="editorStore.setRenderMode('smooth'); closeSettingsMenu()">
                Smooth
              </button>
              <button class="file-menu-item" :class="{ 'settings-item-active': editorStore.renderMode === 'pixelated' }" @click="editorStore.setRenderMode('pixelated'); closeSettingsMenu()">
                Pixelated
              </button>
            </div>
          </div>
          <!-- 主题 -->
          <div class="settings-item-group" @mouseenter="openSettingsSubmenu('theme')">
            <div class="file-menu-item settings-menu-item">
              <span>主题</span>
              <span class="settings-arrow">›</span>
            </div>
            <div v-show="settingsSubmenu === 'theme'" class="settings-submenu">
              <button class="file-menu-item settings-item-disabled">Dark (默认)</button>
              <button class="file-menu-item settings-item-disabled">Light</button>
              <button class="file-menu-item settings-item-disabled">One Dark</button>
            </div>
          </div>
          <!-- 插件库 -->
          <div class="settings-item-group" @mouseenter="openSettingsSubmenu('plugins')">
            <div class="file-menu-item settings-menu-item">
              <span>插件库</span>
              <span class="settings-arrow">›</span>
            </div>
            <div v-show="settingsSubmenu === 'plugins'" class="settings-submenu">
              <button class="file-menu-item settings-item-disabled">暂无插件</button>
            </div>
          </div>
          <!-- 快捷键 -->
          <div class="settings-item-group" @mouseenter="openSettingsSubmenu('shortcuts')">
            <div class="file-menu-item settings-menu-item">
              <span>快捷键</span>
              <span class="settings-arrow">›</span>
            </div>
            <div v-show="settingsSubmenu === 'shortcuts'" class="settings-submenu">
              <button class="file-menu-item settings-item-disabled">编辑快捷键</button>
            </div>
          </div>
          <!-- 引擎设置 -->
          <div class="settings-item-group" @mouseenter="openSettingsSubmenu('engine')">
            <div class="file-menu-item settings-menu-item">
              <span>引擎设置</span>
              <span class="settings-arrow">›</span>
            </div>
            <div v-show="settingsSubmenu === 'engine'" class="settings-submenu">
              <button class="file-menu-item settings-item-disabled">Python 路径</button>
              <button class="file-menu-item settings-item-disabled">引擎参数</button>
            </div>
          </div>
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
      <button class="menu-btn menu-btn-help" title="帮助">
        <img :src="iconHelp" width="24" height="24" />
      </button>
    </div>

    <!-- ═══════════ change_page (外层切页) ═══════════ -->
    <div class="main-content">

      <!-- ─── page 0: edit_stage_frame ─── -->
      <div v-show="currentPage === 0" class="edit-stage-frame">

        <!-- ═══ Page 0: 游戏模式 — 角色编辑器 ═══ -->
        <div v-if="editorStore.isGameMode && editorStore.activeEditorMode === 'sprite'" class="editor-page-full">
          <SpriteEditorView />
        </div>

        <!-- ═══ Page 0: 游戏模式 — 地图编辑器 (v-show 保持 PixiJS 实例存活) ═══ -->
        <div v-show="editorStore.isGameMode && editorStore.activeEditorMode === 'map'" class="editor-page-full">
          <MapEditorView @open-resource-lib="currentPage = 4" />
        </div>

        <!-- ═══ Page 0: 游戏模式 — 代码编辑 (侧边栏 + 标签 + 代码编辑 + 控制台) ═══ -->
        <div v-if="editorStore.isGameMode && editorStore.activeEditorMode !== 'sprite' && editorStore.activeEditorMode !== 'map'" class="editor-page-game">
          <div class="sidebar">
            <div class="sidebar-toolbar">
              <button class="tool-btn" :class="{ 'tool-btn-active': editorStore.isRunning }" @click="toggleRun" title="运行">
                <img :src="iconPlay" width="16" height="16" />
              </button>
              <button class="tool-btn" @click="engine.stop()" title="停止">
                <img :src="iconStop" width="16" height="16" />
              </button>
              <div class="tool-spacer"></div>
              <button class="tool-btn" @click="switchPage(1)" title="全屏">
                <img :src="iconFullscreen" width="20" height="20" />
              </button>
            </div>
            <div class="game-preview-wrapper">
              <div class="game-preview-container">
                <GameCanvas v-if="editorStore.isRunning" class="game-preview-canvas" />
                <div v-else class="game-preview-placeholder">
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="rgb(80,80,80)" stroke-width="1.5"><polygon points="5,3 19,12 5,21" /></svg>
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
                      <img v-if="spriteThumbnails[item.id]" :src="spriteThumbnails[item.id]" class="resource-thumb-img" :style="{ imageRendering: editorStore.renderMode === 'pixelated' ? 'pixelated' : 'auto' }" />
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
                      <span class="resource-grid-name">{{ item.name }}</span>
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
                <div v-else-if="editorStore.resourceTab === 'sound'" class="resource-grid">
                  <div
                    v-for="item in resourceStore.sounds"
                    :key="item.id"
                    class="resource-grid-item"
                    :class="{ 'resource-grid-item-active': selectedResource === item.id }"
                    @click="selectedResource = item.id"
                  >
                    <div class="resource-thumb resource-thumb-sound"><span>{{ item.name.charAt(0) }}</span></div>
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
              <UploadDrawer v-if="editorStore.resourceTab !== 'code'" :type="editorStore.resourceTab" @uploaded="onResourceUploaded" @open-library="onOpenLibrary" @create-map="onCreateMap" />
            </div>
          </div>

          <!-- 游戏模式编辑区 -->
          <div class="game-editor-area">
            <div class="tab-bar">
              <div class="tab-bar-tabs">
                <div v-for="(tab, index) in editorStore.currentTabs" :key="tab.id" class="tab-item" :class="{ 'tab-item-active': editorStore.activeTabIndex === index }" @click="editorStore.setActiveTab(index)">
                  <template v-if="tabRenameId === tab.id">
                    <input class="tab-rename-input" v-model="tabRenameValue" @blur="confirmTabRename" @keydown.enter.prevent="confirmTabRename" @keydown.escape="cancelTabRename" @click.stop />
                  </template>
                  <template v-else>
                    <span @dblclick.stop="startTabRename(tab.id)">{{ codeDisplayName(tab.name) }}</span>
                  </template>
                  <button class="tab-close" @click.stop="editorStore.closeTab(index)">×</button>
                </div>
                <button class="tab-add" @click="editorStore.createTab('未命名.py', '')" title="新建文件">+</button>
              </div>
            </div>
            <div class="code-area">
              <div class="code-splitter">
                <div class="code-editor-pane">
                  <CodeEditor />
                </div>
              </div>
              <TerminalPanel v-model:visible="consoleVisible" />
            </div>
          </div>
        </div>

        <!-- ═══ Page 3: 代码模式 IDE (全宽) ═══ -->
        <div v-if="!editorStore.isGameMode" class="editor-page-full">
          <div class="ide-tab-bar">
            <div class="tab-bar-tabs">
              <div v-for="(tab, index) in editorStore.currentTabs" :key="tab.id" class="tab-item" :class="{ 'tab-item-active': editorStore.activeTabIndex === index }" @click="editorStore.setActiveTab(index)">
                <template v-if="tabRenameId === tab.id">
                  <input class="tab-rename-input" v-model="tabRenameValue" @blur="confirmTabRename" @keydown.enter.prevent="confirmTabRename" @keydown.escape="cancelTabRename" @click.stop />
                </template>
                <template v-else>
                  <span @dblclick.stop="startTabRename(tab.id)">{{ codeDisplayName(tab.name) }}</span>
                </template>
                <button class="tab-close" @click.stop="editorStore.closeTab(index)">×</button>
              </div>
              <button class="tab-add" @click="editorStore.createTab('未命名.py', '')" title="新建文件">+</button>
            </div>
            <div class="ide-toolbar">
              <button class="ide-tool-btn" title="撤销" @click="editorUndo"><img :src="iconUndo" width="18" height="18" /></button>
              <button class="ide-tool-btn" title="重做" @click="editorRedo"><img :src="iconRedo" width="18" height="18" /></button>
            </div>
          </div>
          <div class="ide-editor-area">
            <CodeEditor />
          </div>
          <TerminalPanel v-model:visible="consoleVisible" />
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
          <div class="tool-spacer"></div>
          <div class="toolbar-right" :style="{ paddingRight: canvasOffsetX + 'px' }">
            <button class="tool-btn" @click="switchPage(0)">
              <img :src="iconUnfullscreen" width="20" height="20" />
            </button>
          </div>
        </div>
        <div class="fullscreen-stage-area">
          <GameCanvas v-if="currentPage === 1" @offset-update="canvasOffsetX = $event" />
        </div>
      </div>

      <!-- ─── page 2: 地图库 ─── -->
      <div v-show="currentPage === 2" class="lib-page">
        <MapLibraryPage @close="switchPage(0)" @imported="onMapLibImported" />
      </div>

      <!-- ─── page 3: 角色库 (独立全屏页面) ─── -->
      <div v-show="currentPage === 3" class="lib-page">
        <SpriteLibPage @close="switchPage(0)" @imported="onSpriteLibImported" />
      </div>

      <!-- ─── page 4: 素材库 ─── -->
      <div v-show="currentPage === 4" class="lib-page">
        <MapResourceLibPage @close="switchPage(0)" @imported="onResLibImported" />
      </div>

      <!-- ─── page 5: 声音库 ─── -->
      <div v-show="currentPage === 5" class="lib-page">
        <div class="lib-toolbar">
          <input class="lib-search" placeholder="搜索..." />
          <div style="width:10px"></div>
          <button class="lib-tab-btn lib-tab-active">全部</button>
          <button class="lib-tab-btn">效果</button>
          <button class="lib-tab-btn">音乐</button>
          <div class="lib-spacer"></div>
          <button class="lib-return-btn" @click="switchPage(0)">返回</button>
        </div>
        <div class="lib-list"><div class="resource-placeholder">暂无声音</div></div>
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
  background: rgb(34, 37, 43);
  color: white;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* ═══ 顶部菜单栏 ═══ */
.menu-bar {
  display: flex;
  align-items: stretch;
  height: 40px;
  min-height: 40px;
  padding: 0;
  flex-shrink: 0;
  border-bottom: 1px solid rgb(12, 12, 12);
  background: rgb(34, 37, 43);
}
.menu-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 60px;
  flex-shrink: 0;
  background: rgb(34, 37, 43);
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
.menu-btn:hover { background: rgb(61, 64, 72); }
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
.menu-btn-file:hover {
  margin-bottom: 1px;
}
.file-menu-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  width: 144px;
  background: rgb(34, 37, 43);
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
  background: rgb(61, 64, 72);
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
  width: 128px;
  background: rgb(34, 37, 43);
  border-radius: 6px;
  padding: 4px 0;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}
.settings-item-active {
  color: #5BFB84;
}
.settings-item-disabled {
  color: rgb(100, 100, 100);
  cursor: default;
}
.settings-item-disabled:hover {
  background: transparent;
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
  color: rgb(160, 160, 160);
}
.toggle-switch {
  position: relative;
  width: 36px;
  height: 20px;
  border-radius: 10px;
  border: none;
  cursor: pointer;
  background: rgb(55, 120, 200);
  transition: background 0.2s;
}
.toggle-switch.toggle-on { background: rgb(91, 251, 132); }
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
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: rgb(41, 44, 52);
}

/* 游戏模式编辑区 */
.game-editor-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: rgb(41, 44, 52);
}

/* IDE 模式标签栏 */
.ide-tab-bar {
  display: flex;
  align-items: center;
  height: 30px;
  background: rgb(34, 37, 43);
  flex-shrink: 0;
}

/* IDE 编辑器区域 */
.ide-editor-area {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* ═══ 左侧边栏 ═══ */
.sidebar {
  width: 340px;
  min-width: 340px;
  max-width: 340px;
  display: flex;
  flex-direction: column;
  border-right: 1px solid rgb(12, 12, 12);
  background: rgb(34, 37, 43);
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
.tool-btn:hover { background: rgb(50, 29, 27); border-color: rgb(55, 59, 68); }
.tool-btn:active { background: rgb(95, 45, 39); }
.tool-btn-active { background: rgb(95, 45, 39); border-color: rgb(55, 59, 68); }
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
  background: rgb(50, 50, 61);
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
  background: rgb(50, 50, 61);
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
  color: rgb(128, 128, 128);
  font-size: 13px;
  padding: 8px 8px 4px 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.outline-tab:hover { color: white; }
.outline-tab-active { color: white; border-bottom-color: rgb(91, 251, 132); }

/* 资源列表 */
.outline-list-wrapper {
  flex: 1;
  min-height: 0;
  position: relative;
  background: rgb(30, 30, 30);
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
.resource-grid-item:hover { background: rgb(55, 58, 65); }
.resource-grid-item-active {
  background: rgb(60, 60, 60);
  box-shadow: inset 0 0 0 2px rgb(91, 199, 114);
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
  object-fit: cover;
  flex-shrink: 0;
}
.resource-thumb-map { background: rgb(61, 64, 72); }
.resource-thumb-sound { background: rgb(232, 167, 53); }
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
  color: rgb(200, 200, 200);
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
  color: rgb(200, 200, 200);
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
  color: rgb(200, 200, 200);
  font-size: 11px;
  padding: 0;
  text-align: center;
  outline: none;
  caret-color: white;
}
.resource-card-del {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  background: rgb(255, 77, 79);
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
.resource-card-del:hover { background: rgb(255, 120, 117); }

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
.resource-code-item:hover { background: rgb(61, 64, 72); }
.resource-code-item-active { background: rgb(55, 58, 65); }
.resource-code-item-active:hover { background: rgb(55, 58, 65); }
.resource-code-icon { width: 20px; height: 20px; flex-shrink: 0; }
.resource-code-name {
  font-size: 14px;
  color: rgb(224, 224, 224);
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
  color: rgb(80, 80, 80);
  font-size: 12px;
}
.outline-list-inner { padding: 8px; }

/* ═══ 右侧编辑区 ═══ */
.editor-area {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: rgb(41, 44, 52);
}

/* tab_bar */
.tab-bar {
  display: flex;
  align-items: stretch;
  height: 30px;
  background: rgb(34, 37, 43);
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
  color: rgb(128, 128, 128);
  cursor: pointer;
  border-right: 1px solid rgb(34, 37, 43);
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
.tab-item:hover { color: white; background: rgb(41, 44, 52); }
.tab-item-active { color: white; background: rgb(41, 44, 52); border-bottom: 2px solid rgb(91, 251, 132); }
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
  color: rgb(128, 128, 128);
  font-size: 16px;
  cursor: pointer;
  flex-shrink: 0;
}
.tab-add:hover { color: white; background: rgb(41, 44, 52); }

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
.ide-tool-btn:hover { color: white; background: rgb(61, 64, 72); }
.ide-tool-btn-active { color: rgb(200, 200, 200); background: rgb(95, 45, 39); }

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
  min-height: 0;
  display: flex;
  flex-direction: column;
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
  background: rgb(34, 37, 43);
  border-bottom: 1px solid rgb(12, 12, 12);
  gap: 4px;
  padding: 0;
}
.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 4px;
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
  background: rgb(34, 37, 43);
}
.lib-toolbar {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 5px;
  gap: 0;
  flex-shrink: 0;
  border-bottom: 1px solid rgb(12, 12, 12);
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
.lib-search:focus { border-color: rgb(91, 251, 132); }
.lib-spacer { flex: 1; }
.lib-hint { font-size: 12px; color: rgb(128, 128, 128); }
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
  color: rgb(128, 128, 128);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.lib-tab-btn:hover { color: white; }
.lib-tab-active { background: rgb(55, 120, 200); color: white; border-color: rgb(55, 120, 200); }
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
  color: rgb(128, 128, 128);
  background: rgb(34, 37, 43);
  border: 1px solid rgb(12, 12, 12);
  border-right: none;
  border-top: none;
  border-top-left-radius: 4px;
  cursor: pointer;
  z-index: 50;
}
.console-toggle:hover { color: white; background: rgb(41, 44, 52); }

/* ═══ 角色右键菜单 ═══ */
.sprite-ctx-menu {
  position: fixed;
  background: rgb(34, 37, 43);
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
  color: rgb(200, 200, 200);
  cursor: pointer;
}
.sprite-ctx-item:hover { background: rgb(61, 64, 72); color: white; }
.sprite-ctx-del:hover { background: rgb(95, 45, 39); color: white; }
</style>
