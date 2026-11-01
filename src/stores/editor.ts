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

  /** 把当前游戏模式的项目代码文件名写成清单（不含代码模式的标签，也不含项目目录外的文件） */
  async function writeGameManifest(projectRoot: string): Promise<void> {
    if (!projectRoot) return
    const files: string[] = []
    for (const tab of gameTabs.value) {
      if (!tab.name) continue
      if (tab.path && !isProjectCodePath(tab.path, projectRoot)) continue
      const name = tab.path ? baseName(tab.path) : tab.name
      if (!name) continue
      if (!files.includes(name)) files.push(name)
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

  // 游戏代码特征：项目里的 .py 必须真的用到引擎 API 才算游戏代码。
  // 代码模式写的练习代码（turtle、input/print、random 猜数字等）一条都不命中，
  // 就算被旧项目包错误地打进 code/ 目录，也绝不会被载入游戏模式。
  const GAME_CODE_MARKERS = [
    'Sprite(', 'run()', 'load_map(', 'key_down(', 'key_pressed(', 'key_up(',
    'Timer(', 'bingo_engine', 'play_sound(', 'play_music(', 'set_background(',
    'time_passed(', 'mouse',
  ]

  function looksLikeGameCode(content: string): boolean {
    if (!content.trim()) return false
    // 明确是代码模式的教学/练习代码（turtle 画图），永远不算游戏代码
    if (/\bimport\s+turtle\b/.test(content) || /\bturtle\./.test(content)) return false
    return GAME_CODE_MARKERS.some(marker => content.includes(marker))
  }
  /**
   * 打开项目后载入游戏模式的项目代码。
   * 只载入清单里声明的文件；旧项目包没有清单时扫描出来的候选文件还要过一遍游戏代码校验，
   * 任何不含引擎 API 的 .py（代码模式的 turtle/练习代码）一律不载入，也不会写进清单。
   * 这样即便旧项目包里被打进了代码模式的文件，也永远进不了游戏模式、更不会被运行。
   */
  async function loadGameProjectTabs(projectRoot: string): Promise<Tab[]> {
    if (!projectRoot) return []
    const created: Tab[] = []
    const manifest = await readGameManifest(projectRoot)
    const fromManifest = manifest !== null
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
        continue
      }
      // 旧包/无清单：必须像游戏代码；有清单：至少不能是 turtle 之类的教学代码
      if (!fromManifest ? !looksLikeGameCode(content) : (!content.trim() || /\bimport\s+turtle\b/.test(content))) {
        console.warn(`[Editor] 跳过非游戏代码文件：${name}`)
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
    await writeGameManifest(projectRoot)
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
