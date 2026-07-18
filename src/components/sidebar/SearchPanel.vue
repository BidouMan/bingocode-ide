<script setup lang="ts">
import { ref, watch } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { useFileExplorerStore } from '../../stores/fileExplorer'
import { useEditorStore } from '../../stores/editor'

const fileExplorerStore = useFileExplorerStore()
const editorStore = useEditorStore()

const searchText = ref('')
const replaceText = ref('')
const showReplace = ref(false)
const results = ref<{ path: string; name: string; line: number; col: number; text: string; matchStart: number; matchEnd: number }[]>([])
const searching = ref(false)
const searched = ref(false)

// 递归收集工作区所有 .py 文件
async function collectPyFiles(dirPath: string): Promise<string[]> {
  const entries = await invoke<string[]>('list_dir', { path: dirPath })
  const files: string[] = []
  for (const entry of entries) {
    const name = entry.replace(/\/$/, '')
    if (name.startsWith('.') || name === '__pycache__' || name === 'node_modules' || name === 'venv') continue
    const fullPath = `${dirPath}/${name}`
    if (entry.endsWith('/')) {
      files.push(...await collectPyFiles(fullPath))
    } else if (name.endsWith('.py')) {
      files.push(fullPath)
    }
  }
  return files
}

async function doSearch() {
  const query = searchText.value.trim()
  if (!query) { results.value = []; searched.value = false; return }
  if (!fileExplorerStore.workspaceFolder) return

  searching.value = true
  searched.value = true
  results.value = []

  try {
    const files = await collectPyFiles(fileExplorerStore.workspaceFolder)
    for (const filePath of files) {
      try {
        const content = await invoke<string>('read_file', { path: filePath })
        const lines = content.split('\n')
        const fileName = filePath.split('/').pop() || ''
        for (let i = 0; i < lines.length; i++) {
          const line = lines[i]
          const idx = line.toLowerCase().indexOf(query.toLowerCase())
          if (idx >= 0) {
            results.value.push({
              path: filePath,
              name: fileName,
              line: i + 1,
              col: idx + 1,
              text: line.trim(),
              matchStart: idx - (line.length - line.trimStart().length),
              matchEnd: idx + query.length - (line.length - line.trimStart().length),
            })
            // 每个文件最多 20 条
            if (results.value.filter(r => r.path === filePath).length >= 20) break
          }
        }
      } catch { /* 跳过无法读取的文件 */ }
      // 总结果上限 200
      if (results.value.length >= 200) break
    }
  } finally {
    searching.value = false
  }
}

async function openResult(result: { path: string; name: string; line: number }) {
  // 打开文件并跳转到行
  const existing = editorStore.currentTabs.find(t => t.path === result.path)
  if (existing) {
    const idx = editorStore.currentTabs.indexOf(existing)
    editorStore.setActiveTab(idx)
  } else {
    try {
      const content = await invoke<string>('read_file', { path: result.path })
      editorStore.createTab(result.name, result.path, content)
    } catch { return }
  }
  // 跳转到行（延迟一帧等编辑器更新）
  setTimeout(() => {
    window.dispatchEvent(new CustomEvent('editor:goto-line', { detail: { line: result.line } }))
  }, 100)
}

function highlightMatch(text: string, start: number, end: number): string {
  if (start < 0 || end > text.length || start >= end) return escapeHtml(text)
  return escapeHtml(text.substring(0, start))
    + '<mark>' + escapeHtml(text.substring(start, end)) + '</mark>'
    + escapeHtml(text.substring(end))
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

// 回车搜索
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    e.preventDefault()
    doSearch()
  }
}
</script>

<template>
  <div class="search-panel">
    <div class="search-header">搜索</div>
    <div class="search-inputs">
      <div class="search-row">
        <input
          class="search-input"
          v-model="searchText"
          placeholder="搜索内容..."
          @keydown="onKeydown"
        />
        <button class="search-go" @click="doSearch" :disabled="searching" v-tooltip="'搜索'">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><circle cx="6.5" cy="6.5" r="5" stroke="currentColor" stroke-width="1.5"/><path d="M10.5 10.5L14 14" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        </button>
        <button class="search-toggle" @click="showReplace = !showReplace" v-tooltip="'替换'">
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none"><path d="M2 8h9M8 5l3 3-3 3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
      </div>
      <div v-if="showReplace" class="search-row">
        <input class="search-input" v-model="replaceText" placeholder="替换为..." />
      </div>
    </div>

    <div v-if="searching" class="search-status">搜索中...</div>
    <div v-else-if="searched && results.length === 0" class="search-status">没有找到结果</div>
    <div v-else-if="results.length > 0" class="search-status">找到 {{ results.length }} 条结果</div>

    <div class="search-results">
      <div v-for="r in results" :key="`${r.path}:${r.line}:${r.col}`" class="search-result" @click="openResult(r)">
        <div class="result-file">{{ r.name }}<span class="result-line">:{{ r.line }}</span></div>
        <div class="result-text" v-html="highlightMatch(r.text, r.matchStart, r.matchEnd)"></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.search-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-root);
  user-select: none;
}
.search-header {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
  padding: 10px 12px 6px;
}
.search-inputs {
  padding: 0 8px 6px;
}
.search-row {
  display: flex;
  gap: 4px;
  margin-bottom: 4px;
}
.search-input {
  flex: 1;
  height: 24px;
  background: var(--bg-base);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text);
  font-size: 12px;
  padding: 0 6px;
  outline: none;
}
.search-input:focus { border-color: var(--accent); }
.search-input::placeholder { color: var(--text-muted); }
.search-go, .search-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text-muted);
  cursor: pointer;
  flex-shrink: 0;
}
.search-go:hover, .search-toggle:hover {
  color: var(--text);
  background: var(--bg-hover);
}
.search-go:disabled { opacity: 0.4; cursor: default; }
.search-status {
  font-size: 11px;
  color: var(--text-muted);
  padding: 2px 12px 6px;
}
.search-results {
  flex: 1;
  overflow-y: auto;
  padding: 0 6px 6px;
}
.search-result {
  padding: 4px 8px;
  border-radius: 3px;
  cursor: pointer;
  margin-bottom: 1px;
}
.search-result:hover { background: var(--bg-hover); }
.result-file {
  font-size: 11px;
  color: var(--text);
}
.result-line {
  color: var(--text-muted);
}
.result-text {
  font-size: 10px;
  color: var(--text-muted);
  font-family: monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.result-text :deep(mark) {
  background: rgba(91, 251, 132, 0.25);
  color: var(--accent);
  border-radius: 2px;
  padding: 0 1px;
}
</style>
