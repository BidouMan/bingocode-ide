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
    setRunTarget,
    markCodeDirty,
    markResourceDirty,
    resetDirty,
  }
})
