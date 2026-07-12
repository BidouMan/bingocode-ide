import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type EditorMode = 'code' | 'sprite' | 'map'
export type ResourceTab = 'sprite' | 'map' | 'sound' | 'code'
export type RenderMode = 'smooth' | 'pixelated'

export interface Tab {
  id: string
  name: string
  path: string
  content: string
  modified: boolean
}

let tabIdCounter = 0

function createDefaultTab(): Tab {
  return {
    id: `tab-${++tabIdCounter}`,
    name: '未命名-1.py',
    path: '',
    content: '',
    modified: false,
  }
}

// 从 localStorage 读取保存的模式
function loadSavedMode(): boolean {
  try {
    const saved = localStorage.getItem('bingo-ide-game-mode')
    return saved === 'true'
  } catch {
    return false
  }
}

// 保存模式到 localStorage
function saveMode(isGame: boolean) {
  try {
    localStorage.setItem('bingo-ide-game-mode', String(isGame))
  } catch {}
}

// 从 localStorage 读取字体缩放
function loadSavedZoom(): number {
  try {
    const saved = localStorage.getItem('bingo-ide-font-zoom')
    if (saved) {
      const val = parseInt(saved)
      if (val >= 50 && val <= 400) return val
    }
  } catch {}
  return 100
}

// 保存字体缩放到 localStorage
function saveZoom(zoom: number) {
  try {
    localStorage.setItem('bingo-ide-font-zoom', String(zoom))
  } catch {}
}

export const useEditorStore = defineStore('editor', () => {
  // ─── 模式 ───
  const isGameMode = ref(loadSavedMode())
  const activeEditorMode = ref<EditorMode>('code')
  const isRunning = ref(false)
  const resourceTab = ref<ResourceTab>('sprite')
  const renderMode = ref<RenderMode>('smooth')
  const savedZoom = loadSavedZoom()
  const editorFontSize = ref(Math.round(16 * savedZoom / 100))

  // ─── 游戏模式标签 ───
  const gameTabs = ref<Tab[]>([createDefaultTab()])
  const gameActiveTabIndex = ref(0)

  // ─── 代码模式标签 (IDE) ───
  const codeTabs = ref<Tab[]>([createDefaultTab()])
  const codeActiveTabIndex = ref(0)

  // ─── 计算属性 ───
  const currentTabs = computed(() => isGameMode.value ? gameTabs.value : codeTabs.value)
  const activeTabIndex = computed({
    get: () => isGameMode.value ? gameActiveTabIndex.value : codeActiveTabIndex.value,
    set: (v: number) => {
      if (isGameMode.value) gameActiveTabIndex.value = v
      else codeActiveTabIndex.value = v
    },
  })
  const currentTab = computed(() => {
    const tabs = currentTabs.value
    const idx = activeTabIndex.value
    if (idx >= 0 && idx < tabs.length) return tabs[idx]
    return null
  })

  // ─── 模式切换 ───
  function setGameMode(on: boolean) {
    isGameMode.value = on
    saveMode(on)
  }

  function toggleGameMode() {
    isGameMode.value = !isGameMode.value
    saveMode(isGameMode.value)
    if (!isGameMode.value) {
      activeEditorMode.value = 'code'
    }
  }

  function setActiveEditorMode(mode: EditorMode) {
    activeEditorMode.value = mode
  }

  function setResourceTab(tab: ResourceTab) {
    resourceTab.value = tab
  }

  // ─── 标签操作 (自动判断当前模式) ───
  function createTab(name: string, path: string, content = ''): number {
    const tabs = currentTabs.value
    const existing = tabs.findIndex((t) => t.path === path && path !== '')
    if (existing >= 0) {
      activeTabIndex.value = existing
      return existing
    }

    const tab: Tab = {
      id: `tab-${++tabIdCounter}`,
      name,
      path,
      content,
      modified: false,
    }
    tabs.push(tab)
    activeTabIndex.value = tabs.length - 1
    return activeTabIndex.value
  }

  function closeTab(index: number) {
    const tabs = currentTabs.value
    if (index < 0 || index >= tabs.length) return

    tabs.splice(index, 1)

    if (tabs.length === 0) {
      tabs.push(createDefaultTab())
      activeTabIndex.value = 0
    } else if (activeTabIndex.value >= tabs.length) {
      activeTabIndex.value = tabs.length - 1
    } else if (activeTabIndex.value > index) {
      activeTabIndex.value--
    }
  }

  function renameTab(id: string, newName: string) {
    const tabs = currentTabs.value
    const idx = tabs.findIndex(t => t.id === id)
    if (idx >= 0) {
      // 自动补 .py 后缀，保留原 path 不覆盖
      const name = newName.endsWith('.py') ? newName : newName + '.py'
      tabs[idx] = { ...tabs[idx], name }
    }
  }

  function setActiveTab(index: number) {
    const tabs = currentTabs.value
    if (index >= 0 && index < tabs.length) {
      activeTabIndex.value = index
    }
  }

  function saveCurrentTab() {
    if (currentTab.value) {
      currentTab.value.modified = false
    }
  }

  function setRunning(running: boolean) {
    isRunning.value = running
  }

  function toggleRun() {
    isRunning.value = !isRunning.value
  }

  function setRenderMode(mode: RenderMode) {
    renderMode.value = mode
  }

  // ─── 编辑器字体大小 ───
  const editorFontZoom = ref(savedZoom) // 独立的缩放百分比

  function zoomIn() {
    editorFontZoom.value = Math.min(400, editorFontZoom.value + 10)
    editorFontSize.value = Math.round(16 * editorFontZoom.value / 100)
    saveZoom(editorFontZoom.value)
  }

  function zoomOut() {
    editorFontZoom.value = Math.max(50, editorFontZoom.value - 10)
    editorFontSize.value = Math.round(16 * editorFontZoom.value / 100)
    saveZoom(editorFontZoom.value)
  }

  function resetZoom() {
    editorFontZoom.value = 100
    editorFontSize.value = 16
    saveZoom(100)
  }

  return {
    isGameMode,
    activeEditorMode,
    isRunning,
    resourceTab,
    renderMode,
    editorFontSize,
    editorFontZoom,
    gameTabs,
    gameActiveTabIndex,
    codeTabs,
    codeActiveTabIndex,
    currentTabs,
    activeTabIndex,
    currentTab,
    setGameMode,
    toggleGameMode,
    setActiveEditorMode,
    setResourceTab,
    setRenderMode,
    createTab,
    closeTab,
    renameTab,
    setActiveTab,
    saveCurrentTab,
    setRunning,
    toggleRun,
    zoomIn,
    zoomOut,
    resetZoom,
  }
})
