import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

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

  const projectName = computed(() => name.value || '未命名项目')
  const isDirty = computed(() => codeDirty.value || resourceDirty.value)

  function setProject(projectRoot: string, projectName: string) {
    root.value = projectRoot
    name.value = projectName
    codeDirty.value = false
    resourceDirty.value = false
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
    projectName,
    isDirty,
    setProject,
    setRunTarget,
    markCodeDirty,
    markResourceDirty,
    resetDirty,
  }
})
