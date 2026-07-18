<script setup lang="ts">
import { computed } from 'vue'
import type { FileTreeNode } from '../../stores/fileExplorer'

const props = defineProps<{
  node: FileTreeNode
  depth: number
  activePath?: string
  dragOverPath?: string | null
  creating?: { type: 'file' | 'folder'; parentPath: string; value: string } | null
  renaming?: { path: string; value: string } | null
}>()

const emit = defineEmits<{
  toggle: []
  'open-file': []
  'context-menu': [e: MouseEvent]
  'start-create': [type: 'file' | 'folder', parentPath: string]
  'start-rename': [node: FileTreeNode]
  'confirm-create': []
  'cancel-create': []
  'confirm-rename': []
  'cancel-rename': []
  delete: [node: FileTreeNode]
}>()

const isActive = computed(() => props.activePath === props.node.path)
const isRenaming = computed(() => props.renaming?.path === props.node.path)
const showCreateInThis = computed(() =>
  props.creating && props.creating.parentPath === props.node.path && props.node.isDir
)

const isDragOver = computed(() => props.dragOverPath === props.node.path && props.node.isDir)

// 文件类型判断
const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp']
function getFileType(name: string): 'py' | 'json' | 'txt' | 'img' | 'other' {
  const lower = name.toLowerCase()
  if (lower.endsWith('.py')) return 'py'
  if (lower.endsWith('.json')) return 'json'
  if (lower.endsWith('.txt')) return 'txt'
  if (IMAGE_EXTS.some(ext => lower.endsWith(ext))) return 'img'
  return 'other'
}
const fileType = computed(() => getFileType(props.node.name))
const createFileType = computed(() =>
  props.creating ? getFileType(props.creating.value || 'file.py') : 'other'
)
</script>

<template>
  <div class="fe-node-wrapper">
    <!-- 节点行 -->
    <div
      class="fe-node"
      :class="{
        'fe-node-dir': node.isDir,
        'fe-node-file': !node.isDir,
        'fe-node-active': isActive,
        'fe-drag-over': isDragOver,
      }"
      :style="{ paddingLeft: (8 + depth * 14) + 'px' }"
      :data-path="node.path"
      :data-isdir="node.isDir ? '1' : '0'"
      @click="emit('toggle')"
      @contextmenu="emit('context-menu', $event)"
    >
      <span v-if="node.isDir" class="fe-arrow" :class="{ 'fe-arrow-open': node.expanded }">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline v-if="node.expanded" points="6,9 12,15 18,9" />
          <polyline v-else points="9,6 15,12 9,18" />
        </svg>
      </span>
      <span v-else class="fe-arrow-spacer"></span>
      <!-- 文件夹图标：黑白灰风格 -->
      <span v-if="node.isDir" class="fe-icon fe-icon-folder">
        <svg width="22" height="18" viewBox="0 0 16 16" fill="none"><path d="M1.5 4C1.5 3.17 2.17 2.5 3 2.5h3l1.5 1.5h5c.83 0 1.5.67 1.5 1.5V12c0 .83-.67 1.5-1.5 1.5h-9C2.67 13.5 1.5 12.83 1.5 12V4z" fill="rgba(160,160,170,0.2)"/><path d="M1.5 4C1.5 3.17 2.17 2.5 3 2.5h3l1.5 1.5h5c.83 0 1.5.67 1.5 1.5V12c0 .83-.67 1.5-1.5 1.5h-9C2.67 13.5 1.5 12.83 1.5 12V4z" stroke="rgba(160,160,170,0.5)" stroke-width="0.8"/></svg>
      </span>
      <!-- 文件图标：按类型分色 -->
      <span v-else-if="fileType === 'py'" class="fe-icon fe-icon-badge fe-icon-py">py</span>
      <span v-else-if="fileType === 'json'" class="fe-icon fe-icon-badge fe-icon-json">{ }</span>
      <span v-else-if="fileType === 'txt'" class="fe-icon fe-icon-badge fe-icon-txt">txt</span>
      <span v-else-if="fileType === 'img'" class="fe-icon fe-icon-badge fe-icon-img">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><rect x="1.5" y="2.5" width="13" height="11" rx="1.5" stroke="currentColor" stroke-width="1"/><circle cx="5.5" cy="6.5" r="1.5" fill="currentColor" opacity="0.6"/><path d="M2 11l3.5-3.5L8 10l2.5-3L14 11.5" stroke="currentColor" stroke-width="1" stroke-linejoin="round" fill="none"/></svg>
      </span>
      <span v-else class="fe-icon fe-icon-file">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3.5 2h6L13 5.5V13c0 .55-.45 1-1 1H3.5c-.55 0-1-.45-1-1V3c0-.55.45-1 1-1z" stroke="var(--text-muted)" stroke-width="0.8" fill="none"/><path d="M9 2v3.5h4" stroke="var(--text-muted)" stroke-width="0.8" fill="none"/></svg>
      </span>
      <template v-if="isRenaming">
        <input
          class="fe-rename-input"
          :value="renaming!.value"
          @input="renaming!.value = ($event.target as HTMLInputElement).value"
          @blur="emit('confirm-rename')"
          @keydown.enter.prevent="emit('confirm-rename')"
          @keydown.escape="emit('cancel-rename')"
          @click.stop
        />
      </template>
      <template v-else>
        <span class="fe-node-name" :title="node.name">{{ node.name }}</span>
      </template>
    </div>

    <!-- 新建输入行 -->
    <div
      v-if="showCreateInThis"
      class="fe-create-row"
      :style="{ paddingLeft: (8 + (depth + 1) * 14) + 'px' }"
    >
      <span class="fe-arrow-spacer"></span>
      <span v-if="creating!.type === 'folder'" class="fe-icon fe-icon-folder">
        <svg width="22" height="18" viewBox="0 0 16 16" fill="none"><path d="M1.5 4C1.5 3.17 2.17 2.5 3 2.5h3l1.5 1.5h5c.83 0 1.5.67 1.5 1.5V12c0 .83-.67 1.5-1.5 1.5h-9C2.67 13.5 1.5 12.83 1.5 12V4z" fill="rgba(160,160,170,0.2)"/><path d="M1.5 4C1.5 3.17 2.17 2.5 3 2.5h3l1.5 1.5h5c.83 0 1.5.67 1.5 1.5V12c0 .83-.67 1.5-1.5 1.5h-9C2.67 13.5 1.5 12.83 1.5 12V4z" stroke="rgba(160,160,170,0.5)" stroke-width="0.8"/></svg>
      </span>
      <span v-else-if="createFileType === 'json'" class="fe-icon fe-icon-badge fe-icon-json">{ }</span>
      <span v-else-if="createFileType === 'txt'" class="fe-icon fe-icon-badge fe-icon-txt">txt</span>
      <span v-else-if="createFileType === 'img'" class="fe-icon fe-icon-badge fe-icon-img">
        <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><rect x="1.5" y="2.5" width="13" height="11" rx="1.5" stroke="currentColor" stroke-width="1"/><circle cx="5.5" cy="6.5" r="1.5" fill="currentColor" opacity="0.6"/><path d="M2 11l3.5-3.5L8 10l2.5-3L14 11.5" stroke="currentColor" stroke-width="1" stroke-linejoin="round" fill="none"/></svg>
      </span>
      <span v-else class="fe-icon fe-icon-badge fe-icon-py">py</span>
      <input
        class="fe-create-input"
        :value="creating!.value"
        :placeholder="creating!.type === 'file' ? '文件名.py' : '文件夹名'"
        @input="creating!.value = ($event.target as HTMLInputElement).value"
        @blur="emit('confirm-create')"
        @keydown.enter.prevent="emit('confirm-create')"
        @keydown.escape="emit('cancel-create')"
        @click.stop
      />
    </div>

    <!-- 子节点 -->
    <template v-if="node.isDir && node.expanded && node.children.length > 0">
      <FileTreeNodeItem
        v-for="child in node.children"
        :key="child.path"
        :node="child"
        :depth="depth + 1"
        :active-path="activePath"
        :drag-over-path="dragOverPath"
        :creating="creating"
        :renaming="renaming"
        @toggle="emit('toggle')"
        @open-file="emit('open-file')"
        @context-menu="emit('context-menu', $event)"
        @start-create="(type, parentPath) => emit('start-create', type, parentPath)"
        @start-rename="(n) => emit('start-rename', n)"
        @confirm-create="emit('confirm-create')"
        @cancel-create="emit('cancel-create')"
        @confirm-rename="emit('confirm-rename')"
        @cancel-rename="emit('cancel-rename')"
        @delete="(n) => emit('delete', n)"
      />
    </template>
  </div>
</template>

<script lang="ts">
// 递归组件需要显式 name
export default { name: 'FileTreeNodeItem' }
</script>

<style scoped>
.fe-node-wrapper { display: block; }

.fe-node {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 24px;
  padding-right: 8px;
  cursor: pointer;
  transition: background 0.08s;
  position: relative;
  user-select: none;
  -webkit-user-select: none;
}
.fe-node:hover { background: var(--bg-hover); }
.fe-node-active {
  background: var(--bg-active);
}

/* 拖拽视觉反馈：使用和选中相同的高亮 */
.fe-drag-over {
  background: var(--bg-active) !important;
}

.fe-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 12px;
  color: var(--text-muted);
  flex-shrink: 0;
  transition: color 0.12s;
}
.fe-node:hover .fe-arrow {
  color: var(--text-secondary);
}
.fe-arrow-spacer {
  width: 12px;
  flex-shrink: 0;
}

/* 图标样式 */
.fe-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 16px;
  height: 16px;
}
.fe-icon-folder {
  width: 22px;
  height: 18px;
}
/* 徽章类图标（py/json/txt/img）：统一尺寸 */
.fe-icon-badge {
  width: 24px;
  height: 17px;
  border-radius: 3px;
  font-size: 8px;
  font-family: monospace;
  font-weight: 700;
  letter-spacing: 0.3px;
}
.fe-icon-py {
  background: rgba(91, 251, 132, 0.2);
  color: rgba(91, 251, 132, 0.9);
}
.fe-icon-json {
  background: rgba(255, 180, 71, 0.2);
  color: rgba(255, 180, 71, 0.9);
}
.fe-icon-txt {
  background: rgba(128, 128, 140, 0.25);
  color: rgba(180, 180, 190, 0.9);
}
.fe-icon-img {
  background: rgba(170, 120, 255, 0.2);
  color: rgba(170, 120, 255, 0.9);
}
.fe-icon-file {
  width: 16px;
  height: 16px;
}

.fe-node-name {
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.fe-node-active .fe-node-name { color: var(--text); }

.fe-create-row {
  display: flex;
  align-items: center;
  gap: 6px;
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
</style>
