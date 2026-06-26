<script setup lang="ts">
import { ref } from 'vue'
import { useEditorStore } from '../../stores/editor'
import { useResourceStore } from '../../stores/resource'
import { useEngine } from '../../composables/useEngine'
import { useFileDialog } from '../../composables/useFileDialog'
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
    const existing = editorStore.currentTabs.find(t => t.name === item.name)
    if (existing) {
      editorStore.setActiveTab(editorStore.currentTabs.indexOf(existing))
    } else {
      editorStore.createTab(item.name, item.name, item.content || '')
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
</script>

<template>
  <div class="app-root">
    <!-- ═══════════ 顶部菜单栏 ═══════════ -->
    <div class="menu-bar">
      <!-- Logo (固定宽度) -->
      <button class="menu-logo">
        <img src="../../assets/icons/logo.svg" style="width:90px;height:40px;" />
      </button>

      <!-- 文件 (图标+文字) + 下拉菜单 -->
      <div class="menu-file-wrapper" @mouseleave="closeFileMenu">
        <button class="menu-btn" title="文件" @click="toggleFileMenu">
          <svg class="menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14,2 14,8 20,8"/>
          </svg>
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
      <button class="menu-btn" :class="{ 'menu-btn-active': editorStore.activeEditorMode === 'code' }" @click="editorStore.setActiveEditorMode('code'); editorStore.setGameMode(true)">
        <svg class="menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16,18 22,12 16,6"/><polyline points="8,6 2,12 8,18"/></svg>
        <span>代码</span>
      </button>

      <!-- 角色 (图标+文字) -->
      <button class="menu-btn" :class="{ 'menu-btn-active': editorStore.activeEditorMode === 'sprite' }" @click="editorStore.setActiveEditorMode('sprite'); editorStore.setGameMode(false)">
        <svg class="menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21,15 16,10 5,21"/></svg>
        <span>角色</span>
      </button>

      <!-- 地图 (图标+文字) -->
      <button class="menu-btn" :class="{ 'menu-btn-active': editorStore.activeEditorMode === 'map' }" @click="editorStore.setActiveEditorMode('map'); editorStore.setGameMode(false)">
        <svg class="menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="1,6 1,22 8,18 16,22 23,18 23,2 16,6 8,2"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/></svg>
        <span>地图</span>
      </button>

      <!-- 设置 (图标+文字) -->
      <button class="menu-btn">
        <svg class="menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
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
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
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
                <svg v-if="!editorStore.isRunning" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
              </button>
              <button class="tool-btn" @click="engine.stop()" title="停止">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
              </button>
              <div class="tool-spacer"></div>
              <button class="tool-btn" @click="switchPage(1)" title="全屏">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15,3 21,3 21,9"/><polyline points="9,21 3,21 3,15"/><line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/></svg>
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
                <div v-if="editorStore.resourceTab === 'sprite'" class="resource-grid">
                  <div v-for="item in resourceStore.sprites" :key="item.id" class="resource-grid-item" :class="{ 'resource-grid-item-active': resourceStore.selectedSpriteId === item.id }" @click="resourceStore.selectedSpriteId = item.id" @dblclick="openResource(item)">
                    <div class="resource-thumb"><span>{{ item.name.charAt(0) }}</span></div>
                    <span class="resource-grid-name">{{ item.name }}</span>
                    <button class="resource-card-del" @click.stop="resourceStore.removeItem(item.id, 'sprite')">×</button>
                  </div>
                  <div v-if="resourceStore.sprites.length === 0" class="resource-empty"><span>暂无角色</span></div>
                </div>
                <div v-else-if="editorStore.resourceTab === 'map'" class="resource-grid">
                  <div v-for="item in resourceStore.maps" :key="item.id" class="resource-grid-item" :class="{ 'resource-grid-item-active': selectedResource === item.id }" @click="selectedResource = item.id" @dblclick="openResource(item)">
                    <div class="resource-thumb resource-thumb-map"><span>{{ item.name.charAt(0) }}</span></div>
                    <span class="resource-grid-name">{{ item.name }}</span>
                    <button class="resource-card-del" @click.stop="resourceStore.removeItem(item.id, 'map')">×</button>
                  </div>
                  <div v-if="resourceStore.maps.length === 0" class="resource-empty"><span>暂无地图</span></div>
                </div>
                <div v-else-if="editorStore.resourceTab === 'sound'" class="resource-grid">
                  <div v-for="item in resourceStore.sounds" :key="item.id" class="resource-grid-item" :class="{ 'resource-grid-item-active': selectedResource === item.id }" @click="selectedResource = item.id">
                    <div class="resource-thumb resource-thumb-sound"><span>{{ item.name.charAt(0) }}</span></div>
                    <span class="resource-grid-name">{{ item.name }}</span>
                    <button class="resource-card-del" @click.stop="resourceStore.removeItem(item.id, 'sound')">×</button>
                  </div>
                  <div v-if="resourceStore.sounds.length === 0" class="resource-empty"><span>暂无声音</span></div>
                </div>
                <div v-else class="resource-code-list">
                  <div v-for="item in resourceStore.codes" :key="item.id" class="resource-code-item" @click="selectedResource = item.id" @dblclick="openResource(item)">
                    <img src="../../assets/icons/python_file_1.svg" class="resource-code-icon" />
                    <span class="resource-code-name">{{ item.name }}</span>
                  </div>
                  <div v-if="resourceStore.codes.length === 0" class="resource-empty"><span>暂无代码文件</span></div>
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
                  <span>{{ tab.name }}</span>
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
                <span>{{ tab.name }}</span>
                <button class="tab-close" @click.stop="editorStore.closeTab(index)">×</button>
              </div>
              <button class="tab-add" @click="editorStore.createTab('未命名.py', '')" title="新建文件">+</button>
            </div>
            <div class="ide-toolbar">
              <button class="ide-tool-btn" :class="{ 'ide-tool-btn-active': editorStore.isRunning }" @click="toggleRun" title="运行">
                <svg v-if="!editorStore.isRunning" width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>
                <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
              </button>
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
              <svg v-if="!editorStore.isRunning" width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
            </button>
            <button class="tool-btn" @click="engine.stop()">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><rect x="4" y="4" width="16" height="16" rx="2"/></svg>
            </button>
            <div class="tool-spacer"></div>
            <button class="tool-btn" @click="switchPage(0)">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="4,14 10,14 10,20"/><polyline points="20,10 14,10 14,4"/><line x1="14" y1="10" x2="21" y2="3"/><line x1="3" y1="21" x2="10" y2="14"/></svg>
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
  height: 56px;
  min-height: 56px;
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
  width: 22px;
  height: 22px;
  flex-shrink: 0;
}
.menu-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 72px;
  min-width: 72px;
  flex-shrink: 0;
  background: transparent;
  border: none;
  color: white;
  cursor: pointer;
  transition: background 0.15s;
  gap: 4px;
  padding: 6px 0;
}
.menu-btn span {
  font-size: 11px;
  line-height: 1;
  white-space: nowrap;
}
.menu-btn:hover { background: rgb(61, 64, 72); }
.menu-btn-active { background: rgb(61, 64, 72); }
.menu-btn-help {
  width: 40px;
  min-width: 40px;
}
.menu-btn-help:hover { background: transparent; }
.menu-btn-help:active { background: transparent; }
.menu-spacer { flex: 1; }

/* 文件下拉菜单 */
.menu-file-wrapper {
  position: relative;
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
}

/* 游戏模式页面 */
.editor-page-game {
  display: flex;
  height: 100%;
}

/* 全宽编辑器页面 (角色/地图/IDE) */
.editor-page-full {
  display: flex;
  flex-direction: column;
  height: 100%;
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
  justify-content: center;
  padding: 8px 0;
  flex-shrink: 0;
}
.game-preview-container {
  width: 320px;
  height: 240px;
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
}
.outline-tab {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  border-bottom: 3px solid rgb(47, 47, 47);
  color: rgb(128, 128, 128);
  font-size: 13px;
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
  background: rgb(41, 44, 52);
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
  transition: background 0.12s;
}
.resource-grid-item:hover { background: rgb(55, 58, 65); }
.resource-grid-item-active {
  background: rgb(60, 60, 60);
  outline: 2px solid rgb(255, 85, 85);
  outline-offset: -2px;
}
.resource-thumb {
  width: 48px;
  height: 48px;
  background: rgb(74, 144, 226);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: white;
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
  max-width: 74px;
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
  transition: background 0.12s;
  position: relative;
}
.resource-code-item:hover { background: rgb(61, 64, 72); }
.resource-code-icon { width: 20px; height: 20px; flex-shrink: 0; }
.resource-code-name {
  font-size: 14px;
  color: rgb(224, 224, 224);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  padding: 4px 0;
}
.fullscreen-toolbar {
  display: flex;
  align-items: center;
  height: 30px;
  width: 100%;
  padding: 0 5px;
  gap: 5px;
  flex-shrink: 0;
}
.fullscreen-game-frame {
  flex: 1;
  min-height: 0;
  width: 100%;
  max-width: 960px;
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
</style>
