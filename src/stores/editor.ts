import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import type { RenderMode } from '../utils/renderMode'
import { samePath, isProjectCodePath, baseName } from '../utils/projectPath'

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
  // 代码模式是独立 IDE：启动时不恢复任何历史标签，只认用户本次打开的工作区文件，
  // 避免把游戏模式的默认项目代码当成代码模式的文件显示出来
  const codeTabs = ref<Tab[]>([])
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

  // ─── 模式隔离：两套标签互不共享，也绝不按目录扫描互相“发现” ───
  // 游戏模式的标签只有三个来源：清单声明的项目代码、游戏模式里用户自己新建/上传的文件、
  // 启动/新建项目时的默认文件。代码模式是独立 IDE，只认它自己打开的工作区文件。
  // 关键点：游戏模式绝不扫描 <项目>/code 目录。否则代码模式另存为到该目录的文件、
  // 旧项目包带进来的文件、磁盘残留，都会被当成游戏代码一起写进运行清单被执行。
  const GAME_MANIFEST_FILE = 'bingo_project.json'

  function gameManifestPath(projectRoot: string) {
    return `${projectRoot}/code/${GAME_MANIFEST_FILE}`
  }

  /** 读取项目声明的游戏代码文件名；没有清单（旧项目包）返回 null */
  async function readGameManifest(projectRoot: string): Promise<string[] | null> {
    if (!projectRoot) return null
    try {
      const raw = await invoke<string>('read_file', { path: gameManifestPath(projectRoot) })
      const data = JSON.parse(raw)
      if (Array.isArray(data?.files)) {
        return data.files.filter((f: unknown): f is string => typeof f === 'string' && f.endsWith('.py'))
      }
    } catch {
      /* 旧项目没有清单 */
    }
    return null
  }

  /**
   * 用当前游戏标签刷新项目代码清单。
   * 只收「已经落盘 + 位于项目 code/ 下」的文件：还没运行/保存过的新标签没有真实文件，
   * 写进清单只会变成下次打开读不到的幽灵条目。
   * 清单里已经声明、磁盘上也还存在的文件继续保留：关掉标签只是关掉视图，
   * 不能把项目代码从项目里悄悄删掉（要删请用资源列表的删除，那会连同文件一起删）。
   */
  async function writeGameManifest(projectRoot: string): Promise<void> {
    if (!projectRoot) return
    const files: string[] = []
    const add = (name: string) => {
      if (!name || !name.endsWith('.py') || files.includes(name)) return
      files.push(name)
    }
    const previous = await readGameManifest(projectRoot)
    for (const name of previous || []) {
      try {
        const exists = await invoke<boolean>('path_exists', { path: `${projectRoot}/code/${name}` })
        if (exists) add(name)
      } catch { /* 查不到就当已删除 */ }
    }
    for (const tab of gameTabs.value) {
      if (!tab.path || !isProjectCodePath(tab.path, projectRoot)) continue
      add(baseName(tab.path))
    }
    try {
      await invoke('create_dir', { path: `${projectRoot}/code` })
      await invoke('write_file', {
        path: gameManifestPath(projectRoot),
        content: JSON.stringify({ files }, null, 2),
      })
    } catch (e) {
      console.error('[Editor] 写入项目代码清单失败:', e)
    }
  }

  /**
   * 打开项目后载入游戏模式的项目代码。
   * 清单是唯一真相：只载入清单声明的文件，绝不按目录扫描、也不按代码内容猜测，
   * 所以代码模式另存进来的练习文件、旧残留都进不了游戏模式。
   * 声明的文件这次读不到（被占用 / 已手工删除）时不建标签，但绝不因此重写清单，
   * 避免一次读取失败就把项目代码从清单里永久删掉。
   * 只有完全没有清单（清单写入失败等异常情况）才扫一次目录兜底，并补写清单。
   */
  async function loadGameProjectTabs(projectRoot: string): Promise<Tab[]> {
    if (!projectRoot) return []
    const created: Tab[] = []
    const manifest = await readGameManifest(projectRoot)
    let names = manifest
    if (!names) {
      let entries: string[] = []
      try {
        entries = await invoke<string[]>('list_dir', { path: `${projectRoot}/code` })
      } catch {
        entries = []
      }
      names = entries.filter(f => f.endsWith('.py') && !f.startsWith('.'))
    }
    for (const name of names) {
      const filePath = `${projectRoot}/code/${name}`
      if (gameTabs.value.some(t => t.path && samePath(t.path, filePath))) continue
      let content = ''
      try {
        content = await invoke<string>('read_file', { path: filePath })
      } catch {
        console.warn(`[Editor] 读取项目代码失败，本次跳过：${name}`)
        continue
      }
      // 同名但还没有路径的标签（启动占位 tab、游戏模式「+」新建的 tab）直接认领这个磁盘文件，
      // 避免同一个文件出现两个标签
      const pathless = gameTabs.value.find(t => !t.path && t.name === name)
      if (pathless) {
        pathless.path = filePath
        if (!pathless.modified) pathless.content = content
        continue
      }
      const tab: Tab = {
        id: `tab-${++tabIdCounter}`,
        name,
        path: filePath,
        content,
        modified: false,
      }
      gameTabs.value.push(tab)
      created.push(tab)
    }
    if (gameActiveTabIndex.value < 0 && gameTabs.value.length > 0) gameActiveTabIndex.value = 0
    if (!manifest) await writeGameManifest(projectRoot)
    return created
  }

  /** 启动 / 新建项目时把游戏模式标签重置为只有一个默认文件（绝不扫描目录） */
  function resetGameTabsToDefault(projectRoot: string, fileName: string) {
    gameTabs.value = [{
      id: `tab-${++tabIdCounter}`,
      name: fileName,
      path: projectRoot ? `${projectRoot}/code/${fileName}` : '',
      content: '',
      modified: false,
    }]
    gameActiveTabIndex.value = 0
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
  }

  function closeOtherTabs(index: number) {
    const tabs = isGameMode.value ? gameTabs : codeTabs
    if (index < 0 || index >= tabs.value.length) return
    const kept = tabs.value[index]
    tabs.value = [kept]
    activeTabIndex.value = 0
  }

  function closeTabsToRight(index: number) {
    const tabs = isGameMode.value ? gameTabs : codeTabs
    if (index < 0 || index >= tabs.value.length - 1) return
    tabs.value = tabs.value.slice(0, index + 1)
    if (activeTabIndex.value >= tabs.value.length) {
      activeTabIndex.value = tabs.value.length - 1
    }
  }

  function closeAllTabs() {
    const tabs = isGameMode.value ? gameTabs : codeTabs
    tabs.value = []
    activeTabIndex.value = -1
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

  const hasUnsavedGameTabs = computed(() => gameTabs.value.some(t => t.modified))
  const hasUnsavedCodeTabs = computed(() => codeTabs.value.some(t => t.modified))
  // 仅用于退出程序时判断是否需要提示保存（两种模式都可能有用未保存内容）
  const hasUnsavedTabs = computed(() => hasUnsavedGameTabs.value || hasUnsavedCodeTabs.value)

  /** 只保存「当前模式」的修改，运行等模式内操作不得写另一模式的文件 */
  async function saveCurrentModeModifiedTabs(): Promise<number> {
    let saved = 0
    for (const tab of currentTabs.value) {
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

  // 项目整体保存成功后调用：只清理游戏模式标签的修改标记，
  // 代码模式的标签不属于该项目，不能被项目保存影响
  function clearAllModified() {
    for (const t of gameTabs.value) t.modified = false
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
    loadGameProjectTabs,
    resetGameTabsToDefault,
    writeGameManifest,
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
    hasUnsavedGameTabs,
    hasUnsavedCodeTabs,
    hasUnsavedTabs,
    saveCurrentModeModifiedTabs,
    saveAllModifiedTabs,
    clearAllModified,
    setRunning,
    toggleRun,
    zoomIn,
    zoomOut,
    resetZoom,
  }
})
