import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { isProjectCodePath, baseName, normalizeComparePath } from '../utils/projectPath'

export interface ProjectState {
  root: string
  name: string
  bingoPath: string | null
  runTarget: string
  codeDirty: boolean
  resourceDirty: boolean
}

export const useProjectStore = defineStore('project', () => {
  const root = ref('')
  const name = ref('')
  const bingoPath = ref<string | null>(null)
  const runTarget = ref('')
  const codeDirty = ref(false)
  const resourceDirty = ref(false)
  const initialized = ref(false)

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
    // 启动永远是全新默认项目状态（不自动恢复上次打开的项目）
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
    return projectRoot
  }

  /** 将代码标签页写入工作目录的 code/ 文件夹 */
  async function flushCodeTabs() {
    const { useEditorStore } = await import('../stores/editor')
    const editor = useEditorStore()
    const codeDir = `${root.value}/code`
    await invoke('create_dir', { path: codeDir })

    // 只写项目自己的代码：代码模式里打开的其它文件夹文件、代码片段等不能混进项目 code/，
    // 否则保存项目时会被一起打包，下次打开项目还会多出莫名其妙的文件
    //
    // 项目代码归游戏模式所有：以 gameTabs 为准写盘，代码模式的标签只是它自己的视图，
    // 不能反过来覆盖（否则会把另一侧的旧内容写回磁盘）。同一路径只写一次。
    const written = new Set<string>()

    for (const list of [editor.gameTabs, editor.codeTabs]) {
      for (const tab of [...list]) {
        if (!tab.name) continue
        let targetPath = tab.path
        if (targetPath) {
          if (!isProjectCodePath(targetPath, root.value)) continue
        } else {
          // 无路径的标签只有游戏模式会产出（项目内的新代码文件）
          if (!editor.gameTabs.includes(tab)) continue
          targetPath = `${codeDir}/${tab.name}`
        }
        const key = normalizeComparePath(targetPath)
        if (written.has(key)) continue
        written.add(key)
        await invoke('write_file', { path: targetPath, content: tab.content })
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
      const { useEditorStore } = await import('../stores/editor')
      useEditorStore().clearAllModified()
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
      // Windows 路径是反斜杠，不能 split('/') 取文件名
      const fileName = baseName(outputPath).replace(/\.bc$/, '') || '未命名项目'
      name.value = fileName
      codeDirty.value = false
      resourceDirty.value = false
      const { useEditorStore } = await import('../stores/editor')
      useEditorStore().clearAllModified()
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
      // 关键：解包完成后必须把工作目录写回 root，否则 MainLayout 拿空 root 直接中断
      root.value = projectRoot
      bingoPath.value = bingoFilePath
      // Windows 路径是反斜杠，不能 split('/') 取文件名
      const fileName = baseName(bingoFilePath).replace(/\.bc$/, '') || '未命名项目'
      name.value = fileName
      codeDirty.value = false
      resourceDirty.value = false
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
