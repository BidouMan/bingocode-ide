import { defineStore } from 'pinia'
import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

export interface FileTreeNode {
  name: string
  path: string
  isDir: boolean
  expanded: boolean
  loaded: boolean
  children: FileTreeNode[]
}

const RECENT_FOLDERS_KEY = 'bingo-ide-recent-folders'
const LAST_FOLDER_KEY = 'bingo-ide-last-folder'
const MAX_RECENT = 10

// 跳过这些目录/文件
function shouldSkip(name: string): boolean {
  return name.startsWith('.')
    || name === '__pycache__'
    || name === 'node_modules'
    || name === 'venv'
    || name === 'target'
    || name === '.temp_run.py'
}

function loadRecentFolders(): string[] {
  try {
    const saved = localStorage.getItem(RECENT_FOLDERS_KEY)
    return saved ? JSON.parse(saved) : []
  } catch { return [] }
}

function saveRecentFolders(folders: string[]) {
  try { localStorage.setItem(RECENT_FOLDERS_KEY, JSON.stringify(folders)) } catch {}
}

export const useFileExplorerStore = defineStore('fileExplorer', () => {
  const workspaceFolder = ref('')
  const tree = ref<FileTreeNode[]>([])
  const recentFolders = ref<string[]>(loadRecentFolders())
  const loading = ref(false)

  async function listDirectory(dirPath: string): Promise<FileTreeNode[]> {
    const entries = await invoke<string[]>('list_dir', { path: dirPath })
    const nodes: FileTreeNode[] = []
    for (const entry of entries) {
      const name = entry.replace(/\/$/, '')
      if (shouldSkip(name)) continue
      const isDir = entry.endsWith('/')
      nodes.push({
        name,
        path: `${dirPath}/${name}`,
        isDir,
        expanded: false,
        loaded: false,
        children: [],
      })
    }
    // 目录在前，文件在后，各自按字母排序
    nodes.sort((a, b) => {
      if (a.isDir !== b.isDir) return a.isDir ? -1 : 1
      return a.name.localeCompare(b.name)
    })
    return nodes
  }

  async function openFolder(folderPath: string) {
    if (!folderPath) return
    loading.value = true
    try {
      workspaceFolder.value = folderPath
      tree.value = await listDirectory(folderPath)
      // 加入最近打开列表
      const idx = recentFolders.value.indexOf(folderPath)
      if (idx >= 0) recentFolders.value.splice(idx, 1)
      recentFolders.value.unshift(folderPath)
      if (recentFolders.value.length > MAX_RECENT) {
        recentFolders.value.length = MAX_RECENT
      }
      saveRecentFolders(recentFolders.value)
      try { localStorage.setItem(LAST_FOLDER_KEY, folderPath) } catch {}
    } finally {
      loading.value = false
    }
  }

  async function refresh() {
    if (!workspaceFolder.value) return
    tree.value = await listDirectory(workspaceFolder.value)
  }

  async function toggleNode(node: FileTreeNode) {
    if (!node.isDir) return
    if (!node.loaded) {
      node.children = await listDirectory(node.path)
      node.loaded = true
    }
    node.expanded = !node.expanded
  }

  function findNodeByPath(path: string, nodes: FileTreeNode[] = tree.value): FileTreeNode | null {
    for (const n of nodes) {
      if (n.path === path) return n
      if (n.isDir && n.expanded) {
        const found = findNodeByPath(path, n.children)
        if (found) return found
      }
    }
    return null
  }

  function getParentPath(path: string): string {
    const idx = path.lastIndexOf('/')
    return idx > 0 ? path.substring(0, idx) : ''
  }

  async function refreshParent(parentPath: string) {
    if (!parentPath || parentPath === workspaceFolder.value) {
      tree.value = await listDirectory(workspaceFolder.value)
      return
    }
    const parent = findNodeByPath(parentPath)
    if (parent && parent.isDir) {
      parent.children = await listDirectory(parentPath)
      parent.loaded = true
      parent.expanded = true
    }
  }

  async function createFile(parentPath: string, name: string) {
    const filePath = `${parentPath}/${name}`
    await invoke('write_file', { path: filePath, content: '' })
    await refreshParent(parentPath)
  }

  async function createFolder(parentPath: string, name: string) {
    const folderPath = `${parentPath}/${name}`
    await invoke('create_dir', { path: folderPath })
    await refreshParent(parentPath)
  }

  async function deleteNode(node: FileTreeNode) {
    await invoke('delete_path', { path: node.path })
    await refreshParent(getParentPath(node.path))
  }

  async function renameNode(node: FileTreeNode, newName: string) {
    const parentPath = getParentPath(node.path)
    const newPath = `${parentPath}/${newName}`
    await invoke('rename_path', { oldPath: node.path, newPath })
    node.name = newName
    node.path = newPath
    // 目录重命名后子节点路径失效，需要重新加载
    if (node.isDir) {
      node.loaded = false
      node.children = []
      node.expanded = false
    }
  }

  // 刷新子列表，保留已有子节点的展开状态
  async function refreshChildren(parentNode: FileTreeNode) {
    const oldChildren = parentNode.children
    const newChildren = await listDirectory(parentNode.path)
    // 保留旧节点的展开状态和已加载的子树
    for (const newNode of newChildren) {
      const old = oldChildren.find(c => c.path === newNode.path)
      if (old) {
        newNode.expanded = old.expanded
        newNode.loaded = old.loaded
        newNode.children = old.children
      }
    }
    parentNode.children = newChildren
    parentNode.loaded = true
  }

  async function addLocalFile(targetDir: string): Promise<string | null> {
    const selected = await invoke<string[]>('pick_files')
    if (!selected || selected.length === 0) return null
    let lastPath: string | null = null
    for (const src of selected) {
      try {
        const newPath = await invoke<string>('copy_file', { src, dstDir: targetDir })
        lastPath = newPath
      } catch (e) {
        console.error('[FileExplorer] 添加文件失败:', src, e)
      }
    }
    // 刷新目标目录
    const targetNode = findNodeByPath(targetDir)
    if (targetNode && targetNode.isDir && targetNode.loaded) {
      await refreshChildren(targetNode)
    } else if (targetDir === workspaceFolder.value) {
      const oldTree = tree.value
      const newTree = await listDirectory(workspaceFolder.value)
      for (const newNode of newTree) {
        const old = oldTree.find(c => c.path === newNode.path)
        if (old) {
          newNode.expanded = old.expanded
          newNode.loaded = old.loaded
          newNode.children = old.children
        }
      }
      tree.value = newTree
    }
    return lastPath
  }

  async function moveNode(sourcePath: string, targetDir: string): Promise<string | null> {
    const name = sourcePath.split('/').pop() || ''
    const newPath = `${targetDir}/${name}`
    // 同位置不移动
    if (sourcePath === newPath) return null
    // 目标已存在
    const exists = await invoke<boolean>('path_exists_cmd', { path: newPath })
    if (exists) return null
    await invoke('rename_path', { oldPath: sourcePath, newPath })
    // 刷新源父目录（保持展开状态）
    const sourceParent = getParentPath(sourcePath)
    const sourceParentNode = findNodeByPath(sourceParent)
    if (sourceParentNode && sourceParentNode.isDir && sourceParentNode.loaded) {
      await refreshChildren(sourceParentNode)
    } else if (sourceParent === workspaceFolder.value || !sourceParent) {
      // 根目录刷新也需要保留展开状态
      const oldTree = tree.value
      const newTree = await listDirectory(workspaceFolder.value)
      for (const newNode of newTree) {
        const old = oldTree.find(c => c.path === newNode.path)
        if (old) {
          newNode.expanded = old.expanded
          newNode.loaded = old.loaded
          newNode.children = old.children
        }
      }
      tree.value = newTree
    }
    // 刷新目标目录（保持展开状态）
    if (sourceParent !== targetDir) {
      if (targetDir === workspaceFolder.value) {
        // 目标是根目录
        const oldTree = tree.value
        const newTree = await listDirectory(workspaceFolder.value)
        for (const newNode of newTree) {
          const old = oldTree.find(c => c.path === newNode.path)
          if (old) {
            newNode.expanded = old.expanded
            newNode.loaded = old.loaded
            newNode.children = old.children
          }
        }
        tree.value = newTree
      } else {
        const targetNode = findNodeByPath(targetDir)
        if (targetNode && targetNode.isDir && targetNode.loaded) {
          await refreshChildren(targetNode)
        }
      }
    }
    return newPath
  }

  function removeRecentFolder(folderPath: string) {
    const idx = recentFolders.value.indexOf(folderPath)
    if (idx >= 0) {
      recentFolders.value.splice(idx, 1)
      saveRecentFolders(recentFolders.value)
    }
  }

  async function restoreLastFolder() {
    try {
      const last = localStorage.getItem(LAST_FOLDER_KEY)
      if (!last) return
      // 注意：Tauri 注册的命令名是 path_exists_cmd，不是 path_exists
      // （lib.rs 中 fn path_exists 是内部辅助函数，#[tauri::command] 标注的是 path_exists_cmd）
      const exists = await invoke<boolean>('path_exists_cmd', { path: last })
      if (exists) {
        await openFolder(last)
      } else {
        // 路径已失效，清理记录
        try { localStorage.removeItem(LAST_FOLDER_KEY) } catch {}
        removeRecentFolder(last)
      }
    } catch {}
  }

  return {
    workspaceFolder,
    tree,
    recentFolders,
    loading,
    openFolder,
    refresh,
    toggleNode,
    findNodeByPath,
    getParentPath,
    refreshParent,
    createFile,
    createFolder,
    deleteNode,
    renameNode,
    moveNode,
    addLocalFile,
    removeRecentFolder,
    restoreLastFolder,
  }
})
