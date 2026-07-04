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
    content: 'print("Hello Bingo!")\n',
    modified: false,
  }
}

export const useEditorStore = defineStore('editor', () => {
  // ─── 模式 ───
  const isGameMode = ref(true)
  const activeEditorMode = ref<EditorMode>('code')
  const isRunning = ref(false)
  const resourceTab = ref<ResourceTab>('sprite')
  const renderMode = ref<RenderMode>('smooth')

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
  }

  function toggleGameMode() {
    isGameMode.value = !isGameMode.value
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
      // 自动补 .py 后缀
      const name = newName.endsWith('.py') ? newName : newName + '.py'
      tabs[idx] = { ...tabs[idx], name, path: name }
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

  return {
    isGameMode,
    activeEditorMode,
    isRunning,
    resourceTab,
    renderMode,
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
  }
})
