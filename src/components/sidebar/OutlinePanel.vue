<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { useEditorStore } from '../../stores/editor'

const editorStore = useEditorStore()

interface OutlineItem {
  name: string
  type: 'function' | 'class' | 'variable' | 'import'
  line: number
  indent: number
}

const items = ref<OutlineItem[]>([])

// 筛选开关
const showFunctions = ref(true)
const showClasses = ref(true)
const showVariables = ref(false)
const showImports = ref(false)

// 重命名状态
const renamingKey = ref<string | null>(null)
const renamingValue = ref('')

// 解析 Python 代码，提取函数、类、顶层变量、import
function parseOutline(code: string): OutlineItem[] {
  const result: OutlineItem[] = []
  if (!code) return result

  const lines = code.split('\n')
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmed = line.trimStart()
    if (!trimmed || trimmed.startsWith('#')) continue

    const indent = line.length - trimmed.length

    // import 语句
    if (/^(import |from )/.test(trimmed)) {
      result.push({ name: trimmed.replace(/^(from|import)\s+/, '').split(/\s+/)[0], type: 'import', line: i + 1, indent: 0 })
      continue
    }

    // 只取顶层（indent === 0）
    if (indent > 0) continue

    // class 定义
    const classMatch = trimmed.match(/^class\s+(\w+)/)
    if (classMatch) {
      result.push({ name: classMatch[1], type: 'class', line: i + 1, indent })
      continue
    }

    // 函数定义
    const funcMatch = trimmed.match(/^def\s+(\w+)/)
    if (funcMatch) {
      result.push({ name: funcMatch[1], type: 'function', line: i + 1, indent })
      continue
    }

    // 顶层变量赋值（简单场景）
    const varMatch = trimmed.match(/^([a-zA-Z_]\w*)\s*=/)
    if (varMatch && !trimmed.startsWith('self.')) {
      result.push({ name: varMatch[1], type: 'variable', line: i + 1, indent })
    }
  }

  return result
}

// 监听当前标签页内容变化
watch(
  () => editorStore.currentTab?.content,
  (code) => {
    if (code !== undefined) {
      items.value = parseOutline(code)
    }
  },
  { immediate: true }
)

// 根据筛选过滤
const filteredItems = computed(() => {
  return items.value.filter(item => {
    if (item.type === 'function' && !showFunctions.value) return false
    if (item.type === 'class' && !showClasses.value) return false
    if (item.type === 'variable' && !showVariables.value) return false
    if (item.type === 'import' && !showImports.value) return false
    return true
  })
})

// 点击跳转到行
function gotoLine(line: number) {
  window.dispatchEvent(new CustomEvent('editor:goto-line', { detail: { line } }))
}

// 双击进入重命名
function startRename(item: OutlineItem) {
  renamingKey.value = `${item.type}:${item.name}:${item.line}`
  renamingValue.value = item.name
  nextTick(() => {
    const input = document.querySelector('.outline-rename-input') as HTMLInputElement | null
    if (input) { input.focus(); input.select() }
  })
}

// 确认重命名：替换代码中所有同名标识符
function confirmRename(item: OutlineItem) {
  const newName = renamingValue.value.trim()
  renamingKey.value = null
  if (!newName || newName === item.name) return

  // 通过事件让 Monaco 执行全文件替换
  window.dispatchEvent(new CustomEvent('editor:rename-symbol', {
    detail: { oldName: item.name, newName, line: item.line, type: item.type }
  }))
}

function cancelRename() {
  renamingKey.value = null
}

function isRenaming(item: OutlineItem): boolean {
  return renamingKey.value === `${item.type}:${item.name}:${item.line}`
}
</script>

<template>
  <div class="outline-panel">
    <div class="outline-header">大纲</div>
    <!-- 筛选按钮 -->
    <div class="outline-filters">
      <button
        class="filter-btn"
        :class="{ 'filter-btn-on': showFunctions }"
        @click="showFunctions = !showFunctions"
        title="函数"
      >def</button>
      <button
        class="filter-btn"
        :class="{ 'filter-btn-on': showClasses }"
        @click="showClasses = !showClasses"
        title="类"
      >class</button>
      <button
        class="filter-btn"
        :class="{ 'filter-btn-on': showVariables }"
        @click="showVariables = !showVariables"
        title="变量"
      >val</button>
      <button
        class="filter-btn filter-btn-import"
        :class="{ 'filter-btn-on': showImports }"
        @click="showImports = !showImports"
        title="导入"
      >import</button>
    </div>
    <div v-if="!editorStore.currentTab" class="outline-empty">没有打开的文件</div>
    <div v-else-if="filteredItems.length === 0" class="outline-empty">当前文件没有可识别的结构</div>
    <div v-else class="outline-list">
      <div
        v-for="item in filteredItems"
        :key="`${item.type}:${item.name}:${item.line}`"
        class="outline-item"
        @click="gotoLine(item.line)"
        @dblclick.stop="startRename(item)"
      >
        <span class="outline-icon" :class="`outline-icon-${item.type}`">
          <template v-if="item.type === 'function'">def</template>
          <template v-else-if="item.type === 'class'">C</template>
          <template v-else-if="item.type === 'variable'">val</template>
          <template v-else-if="item.type === 'import'">→</template>
        </span>
        <template v-if="isRenaming(item)">
          <input
            class="outline-rename-input"
            v-model="renamingValue"
            @blur="confirmRename(item)"
            @keydown.enter.prevent="confirmRename(item)"
            @keydown.escape="cancelRename"
            @click.stop
          />
        </template>
        <template v-else>
          <span class="outline-name">{{ item.name }}</span>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.outline-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-root);
  user-select: none;
}
.outline-header {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
  padding: 10px 12px 4px;
}

/* 筛选按钮 */
.outline-filters {
  display: flex;
  gap: 4px;
  padding: 4px 10px 8px;
  flex-wrap: wrap;
}
.filter-btn {
  padding: 2px 8px;
  font-size: 10px;
  font-family: monospace;
  border-radius: 3px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.12s;
  line-height: 1.4;
}
.filter-btn:hover { border-color: var(--text-muted); color: var(--text-secondary); }
.filter-btn-on { border-color: transparent; color: #fff; }
.filter-btn-on.filter-btn-on { /* specificity */ }
/* 每种类型激活时的颜色 */
.filter-btn-on { background: #8b6fc0; }
.filter-btn:first-child.filter-btn-on { background: #c6a0f6; color: #1e1e2e; }
.filter-btn:nth-child(2).filter-btn-on { background: #6cb6ff; color: #1e1e2e; }
.filter-btn:nth-child(3).filter-btn-on { background: #5bfb84; color: #1e1e2e; }
.filter-btn-import.filter-btn-on { background: #dcb67a; color: #1e1e2e; }

.outline-empty {
  font-size: 11px;
  color: var(--text-muted);
  padding: 8px 12px;
}
.outline-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 6px 6px;
}
.outline-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px;
  border-radius: 3px;
  cursor: pointer;
  transition: background 0.08s;
}
.outline-item:hover { background: var(--bg-hover); }

/* 图标：用文字标签代替小 SVG，更清晰 */
.outline-icon {
  min-width: 28px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 3px;
  font-size: 10px;
  font-family: monospace;
  font-weight: 600;
  flex-shrink: 0;
}
.outline-icon-function { background: rgba(198, 160, 246, 0.25); color: #c6a0f6; }
.outline-icon-class { background: rgba(108, 182, 255, 0.25); color: #6cb6ff; }
.outline-icon-variable { background: rgba(91, 251, 132, 0.2); color: #5bfb84; }
.outline-icon-import { background: rgba(220, 182, 122, 0.2); color: #dcb67a; }

.outline-name {
  font-size: 12px;
  color: var(--text-secondary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 重命名输入框 */
.outline-rename-input {
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
  font-family: monospace;
}
</style>
