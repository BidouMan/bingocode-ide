import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { invoke } from '@tauri-apps/api/core'

export interface ProjectState {
  root: string
  name: string
  bingoPath: string | null
  runTarget: string
  codeDirty: boolean
  resourceDirty: boolean
}

// 持久化上次打开的 .bingo 项目路径，启动时自动恢复
const LAST_PROJECT_KEY = 'bingo-ide-last-project'

interface LastProjectInfo {
  bingoPath: string
  name: string
}

function loadLastProject(): LastProjectInfo | null {
  try {
    const saved = localStorage.getItem(LAST_PROJECT_KEY)
    if (!saved) return null
    const data = JSON.parse(saved)
    if (typeof data?.bingoPath === 'string' && data.bingoPath) {
      return { bingoPath: data.bingoPath, name: data.name || '未命名项目' }
    }
  } catch {}
  return null
}

function saveLastProject(bingoPath: string, name: string) {
  try {
    localStorage.setItem(LAST_PROJECT_KEY, JSON.stringify({ bingoPath, name }))
  } catch {}
}

function clearLastProject() {
  try {
    localStorage.removeItem(LAST_PROJECT_KEY)
  } catch {}
}

export const useProjectStore = defineStore('project', () => {
  const root = ref('')
  const name = ref('')
  const bingoPath = ref<string | null>(null)
  const runTarget = ref('')
  const codeDirty = ref(false)
  const resourceDirty = ref(false)
  const initialized = ref(false)
  // 启动恢复时使用：标记本次 initProject 是从上次项目恢复的，
  // MainLayout.onMounted 据此决定是否需要预加载项目资源
  const restoredFromLast = ref(false)

  const projectName = computed(() => name.value || '未命名项目')
  const isDirty = computed(() => codeDirty.value || resourceDirty.value)

  function setProject(projectRoot: string, projectName: string) {
    root.value = projectRoot
    name.value = projectName
    codeDirty.value = false
    resourceDirty.value = false
  }

  async function initProject() {
    if (initialized.value) return root.value
    // 优先尝试恢复上次打开的 .bingo 项目
    const last = loadLastProject()
    if (last) {
      console.log(`[Project] 尝试恢复上次项目: ${last.bingoPath}`)
      const ok = await openProject(last.bingoPath)
      if (ok) {
        initialized.value = true
        restoredFromLast.value = true
        return root.value
      }
      // 恢复失败（文件被删/损坏），回退到默认项目
      console.warn('[Project] 恢复上次项目失败，回退到默认项目')
      clearLastProject()
    }
    try {
      const projectRoot = await invoke<string>('init_default_project')
      root.value = projectRoot
      name.value = 'default'
      initialized.value = true
      return projectRoot
    } catch (e) {
      console.error('[Project] 初始化失败:', e)
      return ''
    }
  }

  async function newProject() {
    const projectRoot = await invoke<string>('init_default_project')
    root.value = projectRoot
    name.value = '未命名项目'
    bingoPath.value = null
    codeDirty.value = false
    resourceDirty.value = false
    // 新建项目没有 .bingo 路径，清除上次项目记录
    clearLastProject()
    return projectRoot
  }

  /** 将代码标签页写入工作目录的 code/ 文件夹 */
  async function flushCodeTabs() {
    const { useEditorStore } = await import('../stores/editor')
    const editor = useEditorStore()
    const codeDir = `${root.value}/code`
    await invoke('create_dir', { path: codeDir })

    // 收集所有标签（去重，同名只保留最新的）
    const allTabs = [...editor.gameTabs, ...editor.codeTabs]
    const seen = new Set<string>()
    for (const tab of allTabs) {
      if (tab.name && !seen.has(tab.name)) {
        seen.add(tab.name)
        await invoke('write_file', {
          path: `${codeDir}/${tab.name}`,
          content: tab.content,
        })
      }
    }
  }

  async function saveProject(): Promise<boolean> {
    if (!bingoPath.value || !root.value) return false
    try {
      await flushCodeTabs()
      await invoke('pack_bingo', {
        workspaceDir: root.value,
        outputPath: bingoPath.value,
      })
      codeDirty.value = false
      resourceDirty.value = false
      // 更新上次项目记录
      saveLastProject(bingoPath.value, name.value)
      return true
    } catch (e) {
      console.error('[Project] 保存失败:', e)
      return false
    }
  }

  async function saveProjectAs(outputPath: string): Promise<boolean> {
    if (!root.value) return false
    try {
      await flushCodeTabs()
      await invoke('pack_bingo', {
        workspaceDir: root.value,
        outputPath,
      })
      bingoPath.value = outputPath
      const fileName = outputPath.split('/').pop()?.replace('.bingo', '') || '未命名项目'
      name.value = fileName
      codeDirty.value = false
      resourceDirty.value = false
      // 更新上次项目记录
      saveLastProject(outputPath, fileName)
      return true
    } catch (e) {
      console.error('[Project] 另存为失败:', e)
      return false
    }
  }

  async function openProject(bingoFilePath: string): Promise<boolean> {
    try {
      const projectRoot = root.value || await invoke<string>('init_default_project')
      await invoke('unpack_bingo', {
        bingoPath: bingoFilePath,
        targetDir: projectRoot,
      })
      bingoPath.value = bingoFilePath
      const fileName = bingoFilePath.split('/').pop()?.replace('.bingo', '') || '未命名项目'
      name.value = fileName
      codeDirty.value = false
      resourceDirty.value = false
      // 更新上次项目记录
      saveLastProject(bingoFilePath, fileName)
      return true
    } catch (e) {
      console.error('[Project] 打开项目失败:', e)
      return false
    }
  }

  function setRunTarget(path: string) {
    runTarget.value = path
  }

  function markCodeDirty(dirty = true) {
    codeDirty.value = dirty
  }

  function markResourceDirty(dirty = true) {
    resourceDirty.value = dirty
  }

  function resetDirty() {
    codeDirty.value = false
    resourceDirty.value = false
  }

  return {
    root,
    name,
    bingoPath,
    runTarget,
    codeDirty,
    resourceDirty,
    initialized,
    restoredFromLast,
    projectName,
    isDirty,
    setProject,
    initProject,
    newProject,
    saveProject,
    saveProjectAs,
    openProject,
    setRunTarget,
    markCodeDirty,
    markResourceDirty,
    resetDirty,
    flushCodeTabs,
  }
})
