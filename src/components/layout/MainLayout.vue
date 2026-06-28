<script setup lang="ts">
import { ref, nextTick, onMounted, watch } from 'vue'
import { useEditorStore } from '../../stores/editor'
import { useResourceStore } from '../../stores/resource'
import { useEngine } from '../../composables/useEngine'
import { useFileDialog } from '../../composables/useFileDialog'
import JSZip from 'jszip'
import GameCanvas from '../canvas/GameCanvas.vue'
import CodeEditor from '../editor/CodeEditor.vue'
import SpriteEditorView from '../sprite-editor/SpriteEditorView.vue'
import MapEditorView from '../map-editor/MapEditorView.vue'
import TerminalPanel from '../terminal/TerminalPanel.vue'
import UploadDrawer from '../resource-panel/UploadDrawer.vue'
import SpriteLibPage from '../resource-panel/SpriteLibPage.vue'

const editorStore = useEditorStore()
const resourceStore = useResourceStore()
const engine = useEngine()
const fileDialog = useFileDialog()

// change_page: 0=编辑器, 1=全屏, 2=地图库, 3=角色库, 4=素材库, 5=声音库
const currentPage = ref(0)
const consoleVisible = ref(false)
const consoleExpanded = ref(true)
const fileMenuVisible = ref(false)
const selectedResource = ref<string | null>(null)

// 角色缩略图缓存
const spriteThumbnails = ref<Record<string, string>>({})
// 角色右键菜单
const spriteContextMenu = ref<{ show: boolean; x: number; y: number; item: { id: string; name: string } | null }>({ show: false, x: 0, y: 0, item: null })
const spriteRenameId = ref<string | null>(null)

// 代码资源管理
const codeContextMenu = ref<{ show: boolean; x: number; y: number; item: { id: string; name: string } | null }>({ show: false, x: 0, y: 0, item: null })
const codeRenameId = ref<string | null>(null)
const codeRenameValue = ref('')
const spriteRenameValue = ref('')

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

function toggleFileMenu() {
  fileMenuVisible.value = !fileMenuVisible.value
}

function closeFileMenu() {
  fileMenuVisible.value = false
}

async function fileMenuAction(action: string) {
  closeFileMenu()

  switch (action) {
    case 'new': {
      const name = `未命名-${editorStore.currentTabs.length + 1}.py`
      editorStore.createTab(name, '', 'print("Hello Bingo!")\n')
      break
    }

    case 'open': {
      const file = await fileDialog.openFile('.py,.bingo,.json')
      if (!file) break
      if (file.name.endsWith('.bingo') || file.name.endsWith('.json')) {
        // 项目文件：解析后加载
        // TODO: Tauri 模式下解包 .bingo
        editorStore.createTab(file.name, file.name, file.content)
      } else {
        // 普通 Python 文件
        editorStore.createTab(file.name, file.name, file.content)
      }
      break
    }

    case 'save': {
      const tab = editorStore.currentTab
      if (!tab) break
      const filename = tab.name || '未命名.py'
      fileDialog.saveFile(filename, tab.content)
      tab.modified = false
      break
    }

    case 'saveAs': {
      const tab = editorStore.currentTab
      if (!tab) break
      fileDialog.saveFile(tab.name || '未命名.py', tab.content)
      break
    }

    case 'close':
      editorStore.closeTab(editorStore.activeTabIndex)
      break

    case 'exit':
      window.close()
      break
  }
}

async function toggleRun() {
  if (editorStore.isRunning) {
    await engine.stop()
  } else {
    if (!editorStore.isGameMode) consoleVisible.value = true
    await engine.run()
  }
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

function openResource(item: { id: string; name: string; type: string; content?: string }) {
  if (item.type === 'code') {
    // 在游戏模式标签中查找
    const idx = editorStore.gameTabs.findIndex(t => t.id === item.id)
    if (idx >= 0) {
      editorStore.setGameMode(true)
      editorStore.setActiveTab(idx)
    }
  }
}

function onResourceUploaded(type: string, name: string, content?: string) {
  editorStore.setResourceTab(type as any)
}

function onOpenLibrary(type: string) {
  if (type === 'sprite') {
    currentPage.value = 3  // sprite_lib page
  }
  // TODO: map=2, sound=5
}

function onSpriteLibImported(id: string, name: string, bgsUrl: string) {
  resourceStore.selectedSpriteId = id
  currentPage.value = 0
  editorStore.setResourceTab('sprite')
  editorStore.setActiveEditorMode('sprite')
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

// 加载角色缩略图
async function loadSpriteThumbnail(item: { id: string; path: string }) {
  if (spriteThumbnails.value[item.id]) return
  try {
    const resp = await fetch(item.path)
    const blob = await resp.blob()
    const zip = await JSZip.loadAsync(blob)
    const configEntry = zip.file('config.json')
    if (!configEntry) return
    const config = JSON.parse(await configEntry.async('text'))
    const firstFrame = (config.frames || [])[0]
    if (!firstFrame) return
    const entry = zip.file(firstFrame)
    if (!entry) return
    const frameBlob = await entry.async('blob')
    spriteThumbnails.value[item.id] = URL.createObjectURL(frameBlob)
  } catch (e) {
    console.warn('Failed to load sprite thumbnail:', e)
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
  resourceStore.removeItem(id, 'sprite')
  if (resourceStore.selectedSpriteId === id) resourceStore.selectedSpriteId = null
  spriteContextMenu.value.show = false
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
  const tabs = editorStore.gameTabs
  const idx = tabs.findIndex(t => t.id === id)
  if (idx >= 0) editorStore.closeTab(idx)
  codeContextMenu.value.show = false
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
    <div class="menu-bar">
      <!-- Logo (固定宽度) -->
      <button class="menu-logo">
        <img src="../../assets/icons/logo.svg" style="width:90px;height:40px;" />
      </button>

      <!-- ═══ 游戏模式菜单 ═══ -->
      <template v-if="editorStore.isGameMode">
        <div class="menu-file-wrapper" @mouseleave="closeFileMenu">
          <button class="menu-btn menu-btn-file" title="文件" @click="toggleFileMenu">
            <img src="../../assets/icons/icon--file.svg" class="menu-icon" />
            <span>文件</span>
          </button>
          <div v-show="fileMenuVisible" class="file-menu-dropdown">
            <button class="file-menu-item" @click="fileMenuAction('new')">新建</button>
            <button class="file-menu-item" @click="fileMenuAction('open')">打开</button>
            <button class="file-menu-item" @click="fileMenuAction('save')">保存</button>
            <button class="file-menu-item" @click="fileMenuAction('saveAs')">另存为</button>
            <button class="file-menu-item" @click="fileMenuAction('close')">关闭</button>
            <button class="file-menu-item" @click="fileMenuAction('exit')">退出</button>
          </div>
        </div>

        <!-- 代码 (图标+文字) -->
        <button class="menu-btn" :class="{ 'menu-btn-active': editorStore.resourceTab === 'code' }" @click="editorStore.setResourceTab('code')">
          <img src="../../assets/icons/代码编辑.svg" class="menu-icon" />
          <span>代码</span>
        </button>

        <!-- 角色 (图标+文字) -->
        <button class="menu-btn" :class="{ 'menu-btn-active': editorStore.resourceTab === 'sprite' }" @click="editorStore.setResourceTab('sprite')">
          <img src="../../assets/icons/角色精灵.svg" class="menu-icon" />
          <span>角色</span>
        </button>

        <!-- 地图 (图标+文字) -->
        <button class="menu-btn" :class="{ 'menu-btn-active': editorStore.resourceTab === 'map' }" @click="editorStore.setResourceTab('map')">
          <img src="../../assets/icons/addons.svg" class="menu-icon" />
          <span>地图</span>
        </button>
      </template>

      <!-- ═══ 代码模式菜单 ═══ -->
      <template v-else>
        <!-- 新建 -->
        <button class="menu-btn" @click="editorStore.createTab('未命名.py', '')" title="新建">
          <img src="../../assets/icons/新建地图.svg" class="menu-icon" />
          <span>新建</span>
        </button>

        <!-- 打开 -->
        <button class="menu-btn" @click="fileMenuAction('open')" title="打开">
          <img src="../../assets/icons/codemode_打开.svg" class="menu-icon" />
          <span>打开</span>
        </button>

        <!-- 保存 -->
        <button class="menu-btn" @click="fileMenuAction('save')" title="保存">
          <img src="../../assets/icons/codemode_保存.svg" class="menu-icon" />
          <span>保存</span>
        </button>

        <!-- 运行/停止 -->
        <button class="menu-btn" :class="{ 'menu-btn-run-active': editorStore.isRunning }" @click="toggleRun" :title="editorStore.isRunning ? '停止' : '运行'">
          <img v-if="!editorStore.isRunning" src="../../assets/icons/codemode_运行.svg" class="menu-icon" />
          <img v-else src="../../assets/icons/codemode_停止.svg" class="menu-icon" />
          <span>{{ editorStore.isRunning ? '停止' : '运行' }}</span>
        </button>
      </template>

      <!-- 设置 (两种模式都有) -->
      <button class="menu-btn">
        <img src="../../assets/icons/icon--settings.svg" class="menu-icon" />
        <span>设置</span>
      </button>

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
        <img src="../../assets/icons/help.svg" width="24" height="24" />
      </button>
    </div>

    <!-- ═══════════ change_page (外层切页) ═══════════ -->
    <div class="main-content">

      <!-- ─── page 0: edit_stage_frame ─── -->
      <div v-show="currentPage === 0" class="edit-stage-frame">

        <!-- ═══ Page 0: 游戏模式 (侧边栏 + 标签 + 代码编辑 + 控制台) ═══ -->
        <div v-if="editorStore.isGameMode" class="editor-page-game">
          <div class="sidebar">
            <div class="sidebar-toolbar">
              <button class="tool-btn" :class="{ 'tool-btn-active': editorStore.isRunning }" @click="toggleRun" title="运行">
                <img v-if="!editorStore.isRunning" src="../../assets/icons/icon--play.svg" width="16" height="16" />
                <img v-else src="../../assets/icons/icon--stop-all.svg" width="16" height="16" />
              </button>
              <button class="tool-btn" @click="engine.stop()" title="停止">
                <img src="../../assets/icons/icon--stop-all.svg" width="16" height="16" />
              </button>
              <div class="tool-spacer"></div>
              <button class="tool-btn" @click="switchPage(1)" title="全屏">
                <img src="../../assets/icons/icon--fullscreen.svg" width="20" height="20" />
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
              <button v-for="t in ['sprite','map','sound','code']" :key="t" class="outline-tab" :class="{ 'outline-tab-active': editorStore.resourceTab === t }" @click="editorStore.setResourceTab(t)">
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
                  >
                    <div class="resource-thumb resource-thumb-map"><span>{{ item.name.charAt(0) }}</span></div>
                    <span class="resource-grid-name">{{ item.name }}</span>
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
                    <img src="../../assets/icons/python_file_1.svg" class="resource-code-icon" />
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
              <UploadDrawer v-if="editorStore.resourceTab !== 'code'" :type="editorStore.resourceTab" @uploaded="onResourceUploaded" @open-library="onOpenLibrary" />
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
                  <CodeEditor v-if="!editorStore.isRunning" />
                  <GameCanvas v-else class="game-canvas-full" />
                </div>
              </div>
              <TerminalPanel v-model:visible="consoleVisible" />
            </div>
          </div>
        </div>

        <!-- ═══ Page 1: 角色编辑器 (全宽) ═══ -->
        <div v-else-if="editorStore.activeEditorMode === 'sprite'" class="editor-page-full">
          <SpriteEditorView />
        </div>

        <!-- ═══ Page 2: 地图编辑器 (全宽) ═══ -->
        <div v-else-if="editorStore.activeEditorMode === 'map'" class="editor-page-full">
          <MapEditorView />
        </div>

        <!-- ═══ Page 3: 代码模式 IDE (全宽) ═══ -->
        <div v-else class="editor-page-full">
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
              <button class="ide-tool-btn" title="撤销" @click="editorUndo"><img src="../../assets/icons/undo.svg" width="18" height="18" /></button>
              <button class="ide-tool-btn" title="重做" @click="editorRedo"><img src="../../assets/icons/redo.svg" width="18" height="18" /></button>
            </div>
          </div>
          <div class="ide-editor-area">
            <CodeEditor />
          </div>
          <TerminalPanel v-model:visible="consoleVisible" />
        </div>

      </div>

      <!-- ─── page 1: fullscreen ─── -->
      <div v-show="currentPage === 1" class="fullscreen-page">
        <div class="fullscreen-wrapper">
          <div class="fullscreen-toolbar">
            <button class="tool-btn" :class="{ 'tool-btn-active': editorStore.isRunning }" @click="toggleRun">
              <img v-if="!editorStore.isRunning" src="../../assets/icons/icon--play.svg" width="16" height="16" />
              <img v-else src="../../assets/icons/icon--stop-all.svg" width="16" height="16" />
            </button>
            <button class="tool-btn" @click="engine.stop()">
              <img src="../../assets/icons/icon--stop-all.svg" width="16" height="16" />
            </button>
            <div class="tool-spacer"></div>
            <button class="tool-btn" @click="switchPage(0)">
              <img src="../../assets/icons/icon--unfullscreen.svg" width="20" height="20" />
            </button>
          </div>
          <div class="fullscreen-game-frame">
            <GameCanvas v-if="currentPage === 1" class="fullscreen-canvas" />
          </div>
        </div>
      </div>

      <!-- ─── page 2: 地图库 ─── -->
      <div v-show="currentPage === 2" class="lib-page">
        <div class="lib-toolbar">
          <input class="lib-search" placeholder="搜索..." />
          <div class="lib-spacer"></div>
          <span class="lib-hint">请选择地图</span>
          <div class="lib-spacer"></div>
          <div style="width:120px"></div>
          <button class="lib-return-btn" @click="switchPage(0)">返回</button>
        </div>
        <div class="lib-list"><div class="resource-placeholder">暂无地图</div></div>
      </div>

      <!-- ─── page 3: 角色库 (独立全屏页面) ─── -->
      <div v-show="currentPage === 3" class="lib-page">
        <SpriteLibPage @close="switchPage(0)" @imported="onSpriteLibImported" />
      </div>

      <!-- ─── page 4: 素材库 ─── -->
      <div v-show="currentPage === 4" class="lib-page">
        <div class="lib-toolbar">
          <input class="lib-search" placeholder="搜索..." />
          <div class="lib-spacer"></div>
          <button class="lib-tab-btn lib-tab-active">图像</button>
          <button class="lib-tab-btn">图块</button>
          <button class="lib-tab-btn">集合</button>
          <div class="lib-spacer"></div>
          <div style="width:120px"></div>
          <button class="lib-return-btn" @click="switchPage(0)">返回</button>
        </div>
        <div class="lib-list"><div class="resource-placeholder">暂无素材</div></div>
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
  background: transparent;
  border: none;
  cursor: pointer;
}
.menu-logo:hover { background: rgb(61, 64, 72); }
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
.menu-btn-active { background: rgb(61, 64, 72); }
.menu-btn-run-active { background: rgb(95, 45, 39); color: rgb(200, 200, 200); }
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
  height: 40px;
}
.menu-btn-file {
  height: 100%;
}
.file-menu-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  width: 180px;
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
  width: 56px;
  height: 56px;
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
  image-rendering: pixelated;
  flex-shrink: 0;
}
.resource-thumb-map { background: rgb(61, 64, 72); }
.resource-thumb-sound { background: rgb(232, 167, 53); }
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

/* ═══ 全屏页 ═══ */
.fullscreen-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: rgb(41, 44, 52);
}
.fullscreen-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.fullscreen-toolbar {
  display: flex;
  align-items: center;
  height: 30px;
  width: 100%;
  padding: 0 5px;
  gap: 5px;
  flex-shrink: 0;
  background: rgb(34, 37, 43);
}
.fullscreen-game-frame {
  flex: 1;
  min-height: 0;
  width: 100%;
  border: 2px solid #4e4e4e;
  background: rgb(50, 50, 61);
  overflow: hidden;
}
.fullscreen-canvas { width: 100%; height: 100%; }

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
