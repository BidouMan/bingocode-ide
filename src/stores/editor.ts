import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import type { RenderMode } from '../utils/renderMode'
import { isProjectCodePath, samePath } from '../utils/projectPath'

export type EditorMode = 'code' | 'sprite' | 'map'
export type ResourceTab = 'sprite' | 'map' | 'sound' | 'code'
export type { RenderMode }

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
    name: '游戏脚本_1.py',
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

// ─── 专注模式（课堂防偷懒开关，仅老师知道入口）───
// 开 = 禁用代码编辑器复制/剪切/粘贴；关 = 正常可用。默认开（新装即禁用）
function loadFocusMode(): boolean {
  try {
    const saved = localStorage.getItem('bingo-ide-focus-mode')
    return saved === null ? true : saved === '1'
  } catch {
    return true
  }
}

function saveFocusMode(on: boolean) {
  try {
    localStorage.setItem('bingo-ide-focus-mode', on ? '1' : '0')
  } catch {}
}

export const useEditorStore = defineStore('editor', () => {
  // ─── 模式 ───
  const isGameMode = ref(loadSavedMode())
  const activeEditorMode = ref<EditorMode>('code')
  const isRunning = ref(false)
  const resourceTab = ref<ResourceTab>('sprite')
  // 默认「自动」：按素材自然尺寸判定（小图走最近邻，大插画走平滑，见 utils/renderMode.ts）
  const renderMode = ref<RenderMode>('auto')
  const focusMode = ref(loadFocusMode())
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

  // ─── 模式隔离：两套标签互不共享，磁盘是唯一真相 ───
  // 游戏模式和代码模式共用同一个项目目录（<项目>/code/*.py），但两套标签页各自持有独立对象：
  // 关闭、重命名、删除、编辑都只在当前模式生效，绝不复制/联动另一模式。
  // 两者交换内容的唯一通道是磁盘：离开模式前写盘，进入模式后按磁盘刷新。
  type TabMode = 'game' | 'code'

  function tabsOfMode(mode: TabMode): Tab[] {
    return mode === 'game' ? gameTabs.value : codeTabs.value
  }

  function activeIndexOfMode(mode: TabMode) {
    return mode === 'game' ? gameActiveTabIndex : codeActiveTabIndex
  }

  /** 把「当前模式」里项目代码的未保存修改写回磁盘（切换模式前调用） */
  async function flushCurrentModeProjectTabs(projectRoot: string): Promise<number> {
    if (!projectRoot) return 0
    let saved = 0
    for (const tab of currentTabs.value) {
      if (!tab.modified || !tab.path) continue
      if (!isProjectCodePath(tab.path, projectRoot)) continue
      try {
        await invoke('write_file', { path: tab.path, content: tab.content })
        tab.modified = false
        saved++
      } catch (e) {
        console.error(`[Editor] 切换模式前保存 ${tab.name} 失败:`, e)
      }
    }
    return saved
  }

  /**
   * 把磁盘上的项目代码读成指定模式的标签（每个模式各自独立的对象）。
   * 只补该模式还没有的文件，不删除、不覆盖已有标签。返回本次新建的标签。
   */
  async function loadProjectCodeTabsInto(mode: TabMode, projectRoot: string): Promise<Tab[]> {
    if (!projectRoot) return []
    const created: Tab[] = []
    let files: string[] = []
    try {
      files = await invoke<string[]>('list_dir', { path: `${projectRoot}/code` })
    } catch {
      return created
    }
    const tabs = tabsOfMode(mode)
    const indexRef = activeIndexOfMode(mode)
    for (const file of files) {
      if (!file.endsWith('.py')) continue
      const filePath = `${projectRoot}/code/${file}`
      if (tabs.some(t => t.path && samePath(t.path, filePath))) continue
      // 同名但还没有路径的标签（启动占位 tab、游戏模式「+」新建的 tab）直接认领这个磁盘文件，
      // 避免同一个文件出现两个标签
      const pathless = tabs.find(t => !t.path && t.name === file)
      if (pathless) {
        pathless.path = filePath
        if (!pathless.modified) {
          try {
            pathless.content = await invoke<string>('read_file', { path: filePath })
          } catch {}
        }
        continue
      }
      let content = ''
      try {
        content = await invoke<string>('read_file', { path: filePath })
      } catch {
        continue
      }
      const tab: Tab = {
        id: `tab-${++tabIdCounter}`,
        name: file,
        path: filePath,
        content,
        modified: false,
      }
      tabs.push(tab)
      created.push(tab)
    }
    if (indexRef.value < 0 && tabs.length > 0) indexRef.value = 0
    if (mode === 'code') saveCodeTabsState()
    return created
  }

  /**
   * 切换模式后调用：让当前模式的项目代码标签与磁盘保持一致。
   * - 磁盘上已不存在的项目文件 → 关闭对应标签
   * - 磁盘内容变化且标签没有未保存修改 → 用磁盘内容刷新
   */
  async function refreshCurrentModeProjectTabs(projectRoot: string): Promise<void> {
    if (!projectRoot) return
    const tabs = currentTabs.value
    const indexRef = activeTabIndex

    for (const tab of [...tabs]) {
      if (!tab.path || !isProjectCodePath(tab.path, projectRoot)) continue
      if (tab.modified) continue
      let exists = true
      try {
        exists = await invoke<boolean>('path_exists', { path: tab.path })
      } catch {}
      if (!exists) {
        const idx = tabs.indexOf(tab)
        if (idx >= 0) tabs.splice(idx, 1)
        continue
      }
      try {
        const content = await invoke<string>('read_file', { path: tab.path })
        if (content !== tab.content) tab.content = content
      } catch {}
    }

    if (tabs.length === 0) indexRef.value = -1
    else if (indexRef.value < 0 || indexRef.value >= tabs.length) indexRef.value = 0
  }

  function setActiveEditorMode(mode: EditorMode) {
    activeEditorMode.value = mode
  }

  function setResourceTab(tab: ResourceTab) {
    resourceTab.value = tab
  }

  // ─── 标签操作 (自动判断当前模式) ───
  // 新建代码文件的默认名：游戏脚本_1.py、游戏脚本_2.py、游戏脚本_3.py …
  function nextCodeFileName(): string {
    let max = 0
    for (const tab of currentTabs.value) {
      const m = tab.name.match(/^游戏脚本_(\d+)\.py$/)
      if (m) max = Math.max(max, parseInt(m[1], 10))
    }
    return `游戏脚本_${max + 1}.py`
  }

  function createTab(name: string, path: string, content = '', id?: string): number {
    const tabs = currentTabs.value
    // Windows 上同一文件可能因分隔符/大小写不同而路径字符串不一致，统一比较后再去重
    const existing = tabs.findIndex((t) => path !== '' && t.path !== '' && samePath(t.path, path))
    if (existing >= 0) {
      activeTabIndex.value = existing
      saveCodeTabsState()
      return existing
    }

    const tab: Tab = {
      id: id || `tab-${++tabIdCounter}`,
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
    // 关闭只作用于当前模式：另一模式的标签是独立对象，不联动
    saveCodeTabsState()
  }

  function closeOtherTabs(index: number) {
    const tabs = isGameMode.value ? gameTabs : codeTabs
    if (index < 0 || index >= tabs.value.length) return
    const kept = tabs.value[index]
    tabs.value = [kept]
    activeTabIndex.value = 0
    saveCodeTabsState()
  }

  function closeTabsToRight(index: number) {
    const tabs = isGameMode.value ? gameTabs : codeTabs
    if (index < 0 || index >= tabs.value.length - 1) return
    tabs.value = tabs.value.slice(0, index + 1)
    if (activeTabIndex.value >= tabs.value.length) {
      activeTabIndex.value = tabs.value.length - 1
    }
    saveCodeTabsState()
  }

  function closeAllTabs() {
    const tabs = isGameMode.value ? gameTabs : codeTabs
    tabs.value = []
    activeTabIndex.value = -1
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

  function saveCurrentTab() {
    if (currentTab.value) {
      currentTab.value.modified = false
    }
  }

  const hasUnsavedTabs = computed(() => {
    const allTabs = [...gameTabs.value, ...codeTabs.value]
    const unsaved = allTabs.some(t => t.modified)
    console.log('[Editor] hasUnsavedTabs check:', allTabs.map(t => ({ name: t.name, modified: t.modified, path: t.path })), '=>', unsaved)
    return unsaved
  })

  async function saveAllModifiedTabs(): Promise<number> {
    const allTabs = [...gameTabs.value, ...codeTabs.value]
    let saved = 0
    for (const tab of allTabs) {
      if (tab.modified && tab.path) {
        try {
          await invoke('write_file', { path: tab.path, content: tab.content })
          tab.modified = false
          saved++
        } catch (e) {
          console.error(`[Editor] 保存 ${tab.name} 失败:`, e)
        }
      }
    }
    return saved
  }

  // 项目整体保存成功后调用：所有标签内容已持久化进项目包
  function clearAllModified() {
    for (const t of gameTabs.value) t.modified = false
    for (const t of codeTabs.value) t.modified = false
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

  function setFocusMode(on: boolean) {
    focusMode.value = on
    saveFocusMode(on)
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
    focusMode,
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
    flushCurrentModeProjectTabs,
    loadProjectCodeTabsInto,
    refreshCurrentModeProjectTabs,
    setActiveEditorMode,
    setResourceTab,
    setRenderMode,
    setFocusMode,
    nextCodeFileName,
    createTab,
    closeTab,
    closeOtherTabs,
    closeTabsToRight,
    closeAllTabs,
    renameTab,
    setActiveTab,
    saveCurrentTab,
    hasUnsavedTabs,
    saveAllModifiedTabs,
    clearAllModified,
    setRunning,
    toggleRun,
    zoomIn,
    zoomOut,
    resetZoom,
  }
})
