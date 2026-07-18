<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { open } from '@tauri-apps/plugin-dialog'
import { invoke } from '@tauri-apps/api/core'
import { useFileExplorerStore, type FileTreeNode } from '../../stores/fileExplorer'
import { useEditorStore } from '../../stores/editor'
import { useResourceStore } from '../../stores/resource'
import FileTreeNodeItem from './FileTreeNodeItem.vue'

const fileExplorerStore = useFileExplorerStore()
const editorStore = useEditorStore()
const resourceStore = useResourceStore()

// 右键菜单
const contextMenu = ref<{ show: boolean; x: number; y: number; node: FileTreeNode | null }>({
  show: false, x: 0, y: 0, node: null,
})

// 新建项（文件/文件夹）的内联输入
const creating = ref<{ type: 'file' | 'folder'; parentPath: string; value: string } | null>(null)

// 重命名内联输入
const renaming = ref<{ path: string; value: string } | null>(null)

// 最近文件夹下拉
const showRecent = ref(false)

const folderName = computed(() => {
  if (!fileExplorerStore.workspaceFolder) return '未打开文件夹'
  // 兼容 Windows 反斜杠和 Unix 正斜杠
  const normalized = fileExplorerStore.workspaceFolder.replace(/\\/g, '/')
  const parts = normalized.split('/')
  return parts[parts.length - 1] || fileExplorerStore.workspaceFolder
})

// 获取父级路径（显示为灰色小字）
const folderParentPath = computed(() => {
  if (!fileExplorerStore.workspaceFolder) return ''
  const normalized = fileExplorerStore.workspaceFolder.replace(/\\/g, '/')
  const parts = normalized.split('/')
  parts.pop()
  return parts.join('/') || ''
})

const hasWorkspace = computed(() => !!fileExplorerStore.workspaceFolder)

// 内联 SVG 图标（黑白灰风格文件夹 + 绿色py徽章）
const folderIconSvg = `<svg width="22" height="18" viewBox="0 0 16 16" fill="none"><path d="M1.5 4C1.5 3.17 2.17 2.5 3 2.5h3l1.5 1.5h5c.83 0 1.5.67 1.5 1.5V12c0 .83-.67 1.5-1.5 1.5h-9C2.67 13.5 1.5 12.83 1.5 12V4z" fill="rgba(160,160,170,0.2)"/><path d="M1.5 4C1.5 3.17 2.17 2.5 3 2.5h3l1.5 1.5h5c.83 0 1.5.67 1.5 1.5V12c0 .83-.67 1.5-1.5 1.5h-9C2.67 13.5 1.5 12.83 1.5 12V4z" stroke="rgba(160,160,170,0.5)" stroke-width="0.8"/></svg>`
const pyIconSvg = `<span style="display:inline-flex;align-items:center;justify-content:center;width:26px;height:18px;border-radius:3px;background:rgba(91,251,132,0.2);color:rgba(91,251,132,0.9);font-size:9px;font-family:monospace;font-weight:700;letter-spacing:0.3px;">py</span>`
const emptyFolderIconSvg = `<svg width="48" height="48" viewBox="0 0 16 16" fill="none"><path d="M1.5 4C1.5 3.17 2.17 2.5 3 2.5h3l1.5 1.5h5c.83 0 1.5.67 1.5 1.5V12c0 .83-.67 1.5-1.5 1.5h-9C2.67 13.5 1.5 12.83 1.5 12V4z" fill="#3a3d44" stroke="rgba(160,160,170,0.3)" stroke-width="0.8"/></svg>`

onMounted(() => {
  fileExplorerStore.restoreLastFolder()
})

async function openFolderPicker() {
  const path = await open({
    title: '打开文件夹',
    directory: true,
  })
  if (path && typeof path === 'string') {
    await fileExplorerStore.openFolder(path)
  }
}

async function onNodeClick(node: FileTreeNode) {
  if (node.isDir) {
    await fileExplorerStore.toggleNode(node)
    return
  }
  await openFileInTab(node)
}

async function openFileInTab(node: FileTreeNode) {
  const existing = editorStore.currentTabs.find(t => t.path === node.path)
  if (existing) {
    const idx = editorStore.currentTabs.indexOf(existing)
    editorStore.setActiveTab(idx)
    return
  }
  try {
    const content = await invoke<string>('read_file', { path: node.path })
    editorStore.createTab(node.name, node.path, content)
  } catch (e) {
    console.error('[FileExplorer] 读取文件失败:', e)
  }
}

async function addLocalFile(targetDir: string) {
  closeContextMenu()
  try {
    await fileExplorerStore.addLocalFile(targetDir)
  } catch (e) {
    console.error('[FileExplorer] 添加文件失败:', e)
  }
}

function onContextMenu(e: MouseEvent, node: FileTreeNode | null) {
  e.preventDefault()
  e.stopPropagation()
  contextMenu.value = { show: true, x: e.clientX, y: e.clientY, node }
}

function onRootContextMenu(e: MouseEvent) {
  if (!hasWorkspace.value) return
  e.preventDefault()
  // 根目录右键
  contextMenu.value = {
    show: true, x: e.clientX, y: e.clientY,
    node: {
      name: folderName.value,
      path: fileExplorerStore.workspaceFolder,
      isDir: true,
      expanded: true,
      loaded: true,
      children: [],
    },
  }
}

function closeContextMenu() {
  contextMenu.value.show = false
}

function startCreate(type: 'file' | 'folder', parentPath: string) {
  creating.value = { type, parentPath, value: '' }
  closeContextMenu()
  nextTick(() => {
    const input = document.querySelector('.fe-create-input') as HTMLInputElement | null
    if (input) input.focus()
  })
}

async function confirmCreate() {
  if (!creating.value) return
  const { type, parentPath, value } = creating.value
  const name = value.trim()
  if (!name) { creating.value = null; return }
  try {
    if (type === 'file') {
      await fileExplorerStore.createFile(parentPath, name)
    } else {
      await fileExplorerStore.createFolder(parentPath, name)
    }
  } catch (e) {
    console.error('[FileExplorer] 创建失败:', e)
  } finally {
    creating.value = null
  }
}

function cancelCreate() {
  creating.value = null
}

function startRename(node: FileTreeNode) {
  renaming.value = { path: node.path, value: node.name }
  closeContextMenu()
  nextTick(() => {
    const input = document.querySelector('.fe-rename-input') as HTMLInputElement | null
    if (input) { input.focus(); input.select() }
  })
}

async function confirmRename() {
  if (!renaming.value) return
  const { path, value } = renaming.value
  const newName = value.trim()
  if (!newName) { renaming.value = null; return }
  const node = fileExplorerStore.findNodeByPath(path)
  if (node && newName !== node.name) {
    const oldPath = node.path
    try {
      await fileExplorerStore.renameNode(node, newName)
      // 同步更新已打开的标签页
      const tab = editorStore.currentTabs.find(t => t.path === oldPath)
      if (tab) {
        const parentPath = fileExplorerStore.getParentPath(oldPath)
        const newPath = `${parentPath}/${newName}`
        tab.name = newName
        tab.path = newPath
        tab.modified = false
        const res = resourceStore.codes.find(c => c.id === tab.id)
        if (res) { res.name = newName; res.path = newPath }
      }
    } catch (e) {
      console.error('[FileExplorer] 重命名失败:', e)
    }
  }
  renaming.value = null
}

function cancelRename() {
  renaming.value = null
}

async function deleteNode(node: FileTreeNode) {
  closeContextMenu()
  const msg = node.isDir ? `确定删除文件夹 "${node.name}" 及其所有内容？` : `确定删除文件 "${node.name}"？`
  if (!confirm(msg)) return
  try {
    await fileExplorerStore.deleteNode(node)
    // 关闭已打开的标签页
    const openTabs = editorStore.currentTabs.filter(t => t.path.startsWith(node.path))
    for (const tab of openTabs) {
      const idx = editorStore.currentTabs.indexOf(tab)
      if (idx >= 0) editorStore.closeTab(idx)
    }
  } catch (e) {
    console.error('[FileExplorer] 删除失败:', e)
  }
}

async function switchToRecent(folder: string) {
  showRecent.value = false
  await fileExplorerStore.openFolder(folder)
}

function removeRecent(folder: string, e: MouseEvent) {
  e.stopPropagation()
  fileExplorerStore.removeRecentFolder(folder)
}

function collapseAll() {
  function walk(nodes: FileTreeNode[]) {
    for (const n of nodes) {
      if (n.isDir) {
        n.expanded = false
        walk(n.children)
      }
    }
  }
  walk(fileExplorerStore.tree)
}

const activeFilePath = computed(() => editorStore.currentTab?.path || '')

const rootCreateActive = computed(() =>
  creating.value && creating.value.parentPath === fileExplorerStore.workspaceFolder
)

// 拖拽状态：用 mousedown/mousemove/mouseup 模拟
const isDragging = ref(false)
const dragSourcePath = ref<string | null>(null)
const dragSourceName = ref<string | null>(null)
const dragSourceIsDir = ref(false)
const dragOverPath = ref<string | null>(null)
const dragStartPos = ref<{ x: number; y: number } | null>(null)
const dragGhostPos = ref<{ x: number; y: number } | null>(null)

const DRAG_THRESHOLD = 5

function onTreeMouseDown(e: MouseEvent) {
  if (e.button !== 0) return
  const nodeEl = (e.target as HTMLElement)?.closest?.('[data-path]') as HTMLElement | null
  if (!nodeEl) return
  const path = nodeEl.dataset.path
  const name = path?.split('/').pop()
  const isDir = nodeEl.dataset.isdir === '1'
  if (!path || !name) return

  dragStartPos.value = { x: e.clientX, y: e.clientY }
  dragSourcePath.value = path
  dragSourceName.value = name
  dragSourceIsDir.value = isDir
  isDragging.value = false
}

function onTreeMouseMove(e: MouseEvent) {
  if (!dragStartPos.value || !dragSourcePath.value) return
  const dx = e.clientX - dragStartPos.value.x
  const dy = e.clientY - dragStartPos.value.y
  if (!isDragging.value && (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD)) {
    isDragging.value = true
    document.body.style.cursor = 'grabbing'
  }
  if (!isDragging.value) return

  // 更新幽灵位置
  dragGhostPos.value = { x: e.clientX, y: e.clientY }

  // 查找鼠标下方的节点
  const el = document.elementFromPoint(e.clientX, e.clientY)
  const nodeEl = (el as HTMLElement)?.closest?.('[data-path]') as HTMLElement | null
  if (nodeEl && nodeEl.dataset.isdir === '1') {
    const path = nodeEl.dataset.path!
    if (path !== dragSourcePath.value && !path.startsWith(dragSourcePath.value + '/')) {
      dragOverPath.value = path
    } else {
      dragOverPath.value = null
    }
  } else {
    dragOverPath.value = null
  }
}

function onTreeMouseUp(e: MouseEvent) {
  if (!isDragging.value || !dragSourcePath.value) {
    dragStartPos.value = null
  dragSourcePath.value = null
  dragSourceName.value = null
  dragSourceIsDir.value = false
  isDragging.value = false
    return
  }

  const sourcePath = dragSourcePath.value
  let targetDir: string | null = null

  if (dragOverPath.value) {
    targetDir = dragOverPath.value
  } else if (fileExplorerStore.workspaceFolder) {
    targetDir = fileExplorerStore.workspaceFolder
  }

  // 清理状态
  dragStartPos.value = null
  dragSourcePath.value = null
  dragSourceName.value = null
  dragOverPath.value = null
  dragGhostPos.value = null
  isDragging.value = false
  document.body.style.cursor = ''

  if (targetDir) {
    handleDropInto(sourcePath, targetDir)
  }
}

function onTreeMouseLeave() {
  if (isDragging.value) {
    dragOverPath.value = null
    dragGhostPos.value = null
  }
}

// 拖拽时阻止节点 click 事件（防止展开/折叠）
function onNodeClickGuard(node: FileTreeNode) {
  if (isDragging.value) return
  onNodeClick(node)
}

async function handleDropInto(sourcePath: string, targetDir: string) {
  // 防止拖到自身父目录
  const sourceParent = sourcePath.substring(0, sourcePath.lastIndexOf('/'))
  if (sourceParent === targetDir) return
  // 防止拖到自身或自身子节点
  if (targetDir.startsWith(sourcePath)) return

  try {
    const newPath = await fileExplorerStore.moveNode(sourcePath, targetDir)
    if (newPath) {
      // 同步更新已打开的标签页
      const tabs = editorStore.currentTabs.filter(t => t.path === sourcePath || t.path.startsWith(sourcePath + '/'))
      for (const tab of tabs) {
        const relativePath = tab.path.substring(sourceParent.length)
        tab.path = targetDir + relativePath
      }
      const sourceName = sourcePath.split('/').pop() || ''
      const resources = resourceStore.codes.filter(c => c.path === sourcePath || c.path?.startsWith(sourcePath + '/'))
      for (const res of resources) {
        const relativePath = res.path?.substring(sourceParent.length) || ''
        res.path = targetDir + relativePath
        if (res.name === sourceName && res.path === newPath) {
          // 顶层资源名不变，路径已更新
        }
      }
    }
  } catch (e) {
    console.error('[FileExplorer] 移动失败:', e)
  }
}
</script>

<template>
  <div class="fe-root" @click="closeContextMenu">
    <!-- 拖拽幽灵元素 -->
    <Teleport to="body">
      <div
        v-if="isDragging && dragGhostPos && dragSourceName"
        class="fe-drag-ghost"
        :style="{ left: dragGhostPos.x + 'px', top: dragGhostPos.y + 'px', transform: 'translate(-50%, -50%)' }"
      >
        <span class="fe-drag-ghost-icon" v-if="dragSourceIsDir" v-html="folderIconSvg"></span>
        <span class="fe-drag-ghost-icon" v-else v-html="pyIconSvg"></span>
        <span class="fe-drag-ghost-name">{{ dragSourceName }}</span>
      </div>
    </Teleport>
    <!-- 头部：文件夹名 + 工具按钮 -->
    <div class="fe-header">
      <div class="fe-title-wrapper" @click="hasWorkspace && (showRecent = !showRecent)">
        <span class="fe-folder-icon" v-html="folderIconSvg"></span>
        <div class="fe-title-group">
          <span class="fe-title" :title="fileExplorerStore.workspaceFolder">{{ folderName }}</span>
          <span v-if="showRecent && folderParentPath" class="fe-title-path" :title="fileExplorerStore.workspaceFolder">{{ folderParentPath }}</span>
        </div>
        <span
          v-if="hasWorkspace && fileExplorerStore.recentFolders.length > 0"
          class="fe-recent-arrow"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline v-if="showRecent" points="6,9 12,15 18,9" />
            <polyline v-else points="6,15 12,9 18,15" />
          </svg>
        </span>
      </div>
      <div class="fe-actions" v-if="hasWorkspace">
        <button class="fe-action-btn" v-tooltip="'新建文件'" @click.stop="startCreate('file', fileExplorerStore.workspaceFolder)">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        </button>
        <button class="fe-action-btn" v-tooltip="'新建文件夹'" @click.stop="startCreate('folder', fileExplorerStore.workspaceFolder)">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M2 4.5C2 3.67 2.67 3 3.5 3h3l1.5 1.5h4.5c.83 0 1.5.67 1.5 1.5V12c0 .83-.67 1.5-1.5 1.5h-9C2.67 13.5 2 12.83 2 12V4.5z" stroke="currentColor" stroke-width="1.2" fill="none"/><path d="M8 7.5v3M6.5 9h3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/></svg>
        </button>
        <button class="fe-action-btn" v-tooltip="'添加文件'" @click.stop="addLocalFile(fileExplorerStore.workspaceFolder)">
          <svg width="14" height="14" viewBox="0 0 300 300" fill="none" xmlns="http://www.w3.org/2000/svg">
            <g transform="translate(150,150)">
              <g transform="translate(-150,-150)">
                <g transform="scale(0.292969)">
                  <path d="M731.429,341.333L804.571,341.333C844.696,341.333 877.714,374.351 877.714,414.476L877.714,828.952C877.714,869.077 844.696,902.095 804.571,902.095L219.429,902.095C179.304,902.095 146.286,869.077 146.286,828.952L146.286,414.476C146.286,374.351 179.304,341.333 219.429,341.333L292.571,341.333L292.571,414.476L219.429,414.476L219.429,828.952L804.571,828.952L804.571,414.476L731.429,414.476L731.429,341.333Z" fill="currentColor"/>
                  <path d="M518.461,93.672L690.834,266.045L639.147,317.781L554.545,233.204L554.545,581.51L481.402,581.51L481.402,234.228L397.775,317.806L346.063,266.094L518.437,93.696L518.461,93.672Z" fill="currentColor"/>
                </g>
              </g>
            </g>
          </svg>
        </button>
        <button class="fe-action-btn" v-tooltip="'刷新'" @click.stop="fileExplorerStore.refresh()">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M13 8a5 5 0 1 1-1.46-3.54M13 3v3h-3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
        </button>
        <button class="fe-action-btn" v-tooltip="'全部折叠'" @click.stop="collapseAll">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M4 6l4 4 4-4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>
        </button>
      </div>
    </div>

    <!-- 最近文件夹下拉 -->
    <div v-if="showRecent" class="fe-recent-dropdown">
      <div class="fe-recent-header">最近打开</div>
      <div v-if="fileExplorerStore.recentFolders.length === 0" class="fe-recent-empty">暂无记录</div>
      <div
        v-for="folder in fileExplorerStore.recentFolders"
        :key="folder"
        class="fe-recent-item"
        @click="switchToRecent(folder)"
      >
        <span class="fe-recent-icon" v-html="folderIconSvg"></span>
        <div class="fe-recent-info">
          <span class="fe-recent-name">{{ (folder.replace(/\\/g, '/').split('/').pop()) || folder }}</span>
          <span class="fe-recent-path" :title="folder">{{ folder.replace(/\\/g, '/').split('/').slice(0, -1).join('/') }}</span>
        </div>
        <button class="fe-recent-del" @click="removeRecent(folder, $event)" v-tooltip="'移除记录'">×</button>
      </div>
    </div>

    <!-- 文件树 -->
    <div
      class="fe-tree"
      v-if="hasWorkspace"
      @contextmenu="onRootContextMenu"
      @mousedown="onTreeMouseDown"
      @mousemove="onTreeMouseMove"
      @mouseup="onTreeMouseUp"
      @mouseleave="onTreeMouseLeave"
    >
      <!-- 根级新建输入 -->
      <div v-if="rootCreateActive" class="fe-create-row" style="padding-left: 22px;">
        <span class="fe-node-icon" v-html="creating!.type === 'folder' ? folderIconSvg : pyIconSvg"></span>
        <input
          class="fe-create-input"
          v-model="creating!.value"
          :placeholder="creating!.type === 'file' ? '文件名.py' : '文件夹名'"
          @blur="confirmCreate"
          @keydown.enter.prevent="confirmCreate"
          @keydown.escape="cancelCreate"
          @click.stop
        />
      </div>

      <FileTreeNodeItem
        v-for="node in fileExplorerStore.tree"
        :key="node.path"
        :node="node"
        :depth="0"
        :active-path="activeFilePath"
        :drag-over-path="dragOverPath"
        :creating="creating"
        :renaming="renaming"
        @toggle="onNodeClickGuard(node)"
        @context-menu="(e) => onContextMenu(e, node)"
        @start-create="startCreate"
        @start-rename="startRename"
        @confirm-create="confirmCreate"
        @cancel-create="cancelCreate"
        @confirm-rename="confirmRename"
        @cancel-rename="cancelRename"
        @delete="deleteNode"
      />
    </div>

    <!-- 空状态 -->
    <div v-else class="fe-empty">
      <div class="fe-empty-icon" v-html="emptyFolderIconSvg"></div>
      <div class="fe-empty-text">还没有打开文件夹</div>
      <button class="fe-empty-btn" @click="openFolderPicker">打开文件夹</button>
    </div>

    <!-- 右键菜单 -->
    <Teleport to="body">
      <div
        v-if="contextMenu.show"
        class="fe-ctx-menu"
        :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }"
        @click.stop
      >
        <template v-if="contextMenu.node?.isDir">
          <div class="fe-ctx-item" @click="contextMenu.node && addLocalFile(contextMenu.node.path)">添加本地文件</div>
          <div class="fe-ctx-divider"></div>
          <div class="fe-ctx-item" @click="contextMenu.node && startCreate('file', contextMenu.node.path)">新建文件</div>
          <div class="fe-ctx-item" @click="contextMenu.node && startCreate('folder', contextMenu.node.path)">新建文件夹</div>
          <div class="fe-ctx-divider"></div>
          <div class="fe-ctx-item" @click="contextMenu.node && startRename(contextMenu.node)">重命名</div>
          <div class="fe-ctx-item fe-ctx-danger" @click="contextMenu.node && deleteNode(contextMenu.node)">删除</div>
        </template>
        <template v-else-if="contextMenu.node">
          <div class="fe-ctx-item" @click="contextMenu.node && startRename(contextMenu.node)">重命名</div>
          <div class="fe-ctx-item fe-ctx-danger" @click="contextMenu.node && deleteNode(contextMenu.node)">删除</div>
        </template>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.fe-root {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-root);
  overflow: hidden;
  user-select: none;
  position: relative;
}

/* 头部 */
.fe-header {
  display: flex;
  align-items: center;
  height: 32px;
  padding: 0 6px 0 10px;
  flex-shrink: 0;
  gap: 4px;
  background: rgba(0, 0, 0, 0.15);
}
.fe-title-wrapper {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
}
.fe-title-wrapper:hover { background: var(--bg-hover); }
.fe-folder-icon {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.fe-title-group {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}
.fe-title {
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
  line-height: 1.2;
}
.fe-title-path {
  font-size: 10px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.2;
}
.fe-recent-arrow {
  display: flex;
  align-items: center;
  color: var(--text-muted);
  flex-shrink: 0;
}
.fe-actions {
  display: flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}
.fe-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: transparent;
  border: none;
  border-radius: 3px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.12s;
}
.fe-action-btn:hover {
  background: var(--bg-hover);
  color: var(--text);
}

/* 最近文件夹下拉 */
.fe-recent-dropdown {
  position: absolute;
  top: 32px;
  left: 0;
  right: 0;
  background: var(--bg-root);
  border: 1px solid var(--border);
  border-top: none;
  max-height: 280px;
  overflow-y: auto;
  z-index: 50;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
.fe-recent-header {
  padding: 6px 12px 4px;
  font-size: 10px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.fe-recent-empty {
  padding: 8px 12px 12px;
  font-size: 12px;
  color: var(--text-muted);
}
.fe-recent-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  cursor: pointer;
  transition: background 0.12s;
}
.fe-recent-item:hover { background: var(--bg-hover); }
.fe-recent-icon { display: flex; flex-shrink: 0; }
.fe-recent-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}
.fe-recent-name {
  font-size: 12px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.2;
}
.fe-recent-path {
  font-size: 10px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.2;
}
.fe-recent-del {
  width: 18px;
  height: 18px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  font-size: 14px;
  cursor: pointer;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.12s;
}
.fe-recent-item:hover .fe-recent-del { opacity: 1; }
.fe-recent-del:hover { background: var(--danger); color: white; }

/* 文件树 */
.fe-tree {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
  position: relative;
}

/* 根级新建输入行 */
.fe-create-row {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 24px;
  padding-right: 8px;
}
.fe-create-input,
.fe-rename-input {
  flex: 1;
  min-width: 40px;
  height: 18px;
  background: var(--bg-base);
  border: 1px solid var(--accent);
  border-radius: 2px;
  color: var(--text);
  font-size: 12px;
  padding: 0 4px;
  outline: none;
  caret-color: var(--accent);
}
.fe-create-input::placeholder,
.fe-rename-input::placeholder {
  color: var(--text-muted);
  font-size: 11px;
}
.fe-node-icon {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

/* 空状态 */
.fe-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 20px;
}
.fe-empty-icon { opacity: 0.4; }
.fe-empty-text {
  font-size: 12px;
  color: var(--text-muted);
  text-align: center;
}
.fe-empty-btn {
  padding: 6px 16px;
  background: var(--accent);
  color: var(--bg-root);
  border: none;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: opacity 0.15s;
}
.fe-empty-btn:hover { opacity: 0.9; }

/* 右键菜单 */
.fe-ctx-menu {
  position: fixed;
  background: var(--bg-root);
  border: 1px solid rgb(60, 60, 60);
  border-radius: 6px;
  padding: 4px 0;
  z-index: 9999;
  box-shadow: 0 4px 16px rgba(0,0,0,0.5);
  min-width: 120px;
}
.fe-ctx-item {
  padding: 6px 14px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}
.fe-ctx-item:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.fe-ctx-danger:hover {
  background: var(--danger);
  color: white;
}
.fe-ctx-divider {
  height: 1px;
  margin: 4px 8px;
  background: var(--border);
}

/* 拖拽幽灵元素 */
.fe-drag-ghost {
  position: fixed;
  pointer-events: none;
  z-index: 99999;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px 2px 4px;
  background: var(--bg-hover);
  color: var(--text);
  font-size: 12px;
  border-radius: 4px;
  white-space: nowrap;
  opacity: 0.85;
  box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}
.fe-drag-ghost-icon {
  display: flex;
  align-items: center;
}
.fe-drag-ghost-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
