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
