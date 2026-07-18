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

// 保存/恢复代码模式标签页
const CODE_TABS_KEY = 'bingo-ide-code-tabs'

function loadSavedCodeTabs(): Tab[] {
  try {
    const saved = localStorage.getItem(CODE_TABS_KEY)
    if (!saved) return []
    const data = JSON.parse(saved)
    const tabs = data?.tabs
    if (!Array.isArray(tabs) || tabs.length === 0) return []
    return tabs.map((t: any) => ({
      id: t.id || `tab-${++tabIdCounter}`,
      name: t.name || '未命名.py',
      path: t.path || '',
      content: '', // 内容延迟加载
      modified: false,
    }))
  } catch {
    return []
  }
}

function loadSavedCodeActiveIndex(): number {
  try {
    const saved = localStorage.getItem(CODE_TABS_KEY)
    if (!saved) return -1
    const data = JSON.parse(saved)
    const idx = data?.activeIndex ?? -1
    return typeof idx === 'number' ? idx : -1
  } catch {
    return -1
  }
}

function saveCodeTabs(tabs: Tab[], activeIndex: number) {
  try {
    const data = tabs.map(t => ({ id: t.id, name: t.name, path: t.path }))
    localStorage.setItem(CODE_TABS_KEY, JSON.stringify({ tabs: data, activeIndex }))
  } catch {}
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
  const codeTabs = ref<Tab[]>(loadSavedCodeTabs())
  const codeActiveTabIndex = ref(loadSavedCodeActiveIndex())

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
      saveCodeTabsState()
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
    saveCodeTabsState()
    return activeTabIndex.value
  }

  function closeTab(index: number) {
    const tabs = currentTabs.value
    if (index < 0 || index >= tabs.length) return

    tabs.splice(index, 1)

    if (tabs.length === 0) {
      activeTabIndex.value = -1
    } else if (activeTabIndex.value >= tabs.length) {
      activeTabIndex.value = tabs.length - 1
    } else if (activeTabIndex.value > index) {
      activeTabIndex.value--
    }
    saveCodeTabsState()
  }

  function renameTab(id: string, newName: string, newPath?: string) {
    const tabs = currentTabs.value
    const idx = tabs.findIndex(t => t.id === id)
    if (idx >= 0) {
      // 自动补 .py 后缀
      const name = newName.endsWith('.py') ? newName : newName + '.py'
      const patch: Partial<Tab> = { name }
      if (newPath !== undefined) patch.path = newPath
      tabs[idx] = { ...tabs[idx], ...patch }
    }
    saveCodeTabsState()
  }

  function setActiveTab(index: number) {
    const tabs = currentTabs.value
    if (index >= 0 && index < tabs.length) {
      activeTabIndex.value = index
    }
    saveCodeTabsState()
  }

  // 保存代码模式标签状态到 localStorage
  function saveCodeTabsState() {
    saveCodeTabs(codeTabs.value, codeActiveTabIndex.value)
  }

  // 恢复代码标签页内容（从文件重新加载）
  async function restoreCodeTabContents() {
    for (const tab of codeTabs.value) {
      if (tab.path && !tab.content) {
        try {
          const { invoke } = await import('@tauri-apps/api/core')
          tab.content = await invoke<string>('read_file', { path: tab.path })
        } catch {
          // 文件可能已被删除，移除这个标签
          const idx = codeTabs.value.indexOf(tab)
          if (idx >= 0) codeTabs.value.splice(idx, 1)
        }
      }
    }
    // 修正 activeIndex
    if (codeTabs.value.length === 0) {
      codeActiveTabIndex.value = -1
    } else if (codeActiveTabIndex.value >= codeTabs.value.length) {
      codeActiveTabIndex.value = codeTabs.value.length - 1
    }
    saveCodeTabsState()
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
    restoreCodeTabContents,
    setRunning,
    toggleRun,
    zoomIn,
    zoomOut,
    resetZoom,
  }
})
