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

    // 只写项目自己的代码：以 gameTabs 为准，代码模式的标签只是它自己的视图，
    // 绝不能把代码模式打开/编辑的文件写进项目 code/（否则保存后重新打开项目，
    // 这些文件就会变成游戏模式的标签并被一起运行）
    const written = new Set<string>()

    for (const tab of [...editor.gameTabs]) {
      if (!tab.name) continue
      const targetPath = tab.path || `${codeDir}/${tab.name}`
      if (tab.path && !isProjectCodePath(tab.path, root.value)) continue
      const key = normalizeComparePath(targetPath)
      if (written.has(key)) continue
      written.add(key)
      await invoke('write_file', { path: targetPath, content: tab.content })
    }

    // 项目清单：只声明当前游戏模式的项目代码文件名。
    // 下次打开这个项目时按清单载入，不再扫描 code/ 目录，
    // 代码模式另存为进该目录的文件也就永远不会变成游戏代码。
    await editor.writeGameManifest(root.value)
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
