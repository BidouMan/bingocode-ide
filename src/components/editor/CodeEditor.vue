<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useEditorStore } from '../../stores/editor'

const editorStore = useEditorStore()
const containerRef = ref<HTMLDivElement>()
let editor: any = null
let monaco: any = null
let ignoreChange = false
const tabStates = new Map<string, { viewState: any; content: string }>()

async function initMonaco() {
  const mod = await import('@monaco-editor/loader')
  const loader = mod.default || mod

  if (!containerRef.value) return

  const m = await loader.init()
  monaco = m

  // 自定义暗色主题，匹配原版 QSS 配色
  m.editor.defineTheme('bingo-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'comment', foreground: '6A9955', fontStyle: 'italic' },
      { token: 'keyword', foreground: 'C586C0' },
      { token: 'string', foreground: 'CE9178' },
      { token: 'number', foreground: 'B5CEA8' },
      { token: 'type', foreground: '4EC9B0' },
      { token: 'function', foreground: 'DCDCAA' },
      { token: 'variable', foreground: '9CDCFE' },
      { token: 'operator', foreground: 'D4D4D4' },
    ],
    colors: {
      'editor.background': '#1E1E1E',
      'editor.foreground': '#D4D4D4',
      'editor.lineHighlightBackground': '#2A2D2E',
      'editor.selectionBackground': '#264F78',
      'editor.inactiveSelectionBackground': '#3A3D41',
      'editorCursor.foreground': '#FFFFFF',
      'editorWhitespace.foreground': '#3B3B3B',
      'editorIndentGuide.background': '#3B3B3B',
      'editorIndentGuide.activeBackground': '#6B6B6B',
      'editorLineNumber.foreground': '#858585',
      'editorLineNumber.activeForeground': '#C6C6C6',
      'editor.selectionHighlightBackground': '#ADD6FF26',
      'editorBracketMatch.background': '#0064001A',
      'editorBracketMatch.border': '#888888',
      'scrollbar.shadow': '#00000000',
      'scrollbarSlider.background': '#79797933',
      'scrollbarSlider.hoverBackground': '#79797955',
      'scrollbarSlider.activeBackground': '#79797988',
      'minimap.background': '#1E1E1E',
    },
  })

  editor = m.editor.create(containerRef.value, {
    value: editorStore.currentTab?.content || '',
    language: 'python',
    theme: 'bingo-dark',
    fontSize: 14,
    fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
    fontLigatures: true,
    minimap: { enabled: false },
    automaticLayout: true,
    scrollBeyondLastLine: false,
    renderWhitespace: 'selection',
    bracketPairColorization: { enabled: true },
    guides: { bracketPairs: true },
    cursorBlinking: 'smooth',
    cursorSmoothCaretAnimation: 'on',
    smoothScrolling: true,
    padding: { top: 12, bottom: 12 },
    tabSize: 4,
    insertSpaces: true,
    wordWrap: 'off',
    lineNumbers: 'on',
    glyphMargin: false,
    folding: true,
    lineDecorationsWidth: 8,
    lineNumbersMinChars: 4,
    renderLineHighlight: 'all',
    scrollbar: {
      vertical: 'auto',
      horizontal: 'auto',
      verticalScrollbarSize: 10,
      horizontalScrollbarSize: 10,
    },
    overviewRulerLanes: 0,
    hideCursorInOverviewRuler: true,
    overviewRulerBorder: false,
    roundedSelection: true,
    selectOnLineNumbers: true,
  })

  // 强制 Monaco 重新计算布局（确保容器尺寸已确定）
  nextTick(() => {
    if (editor) {
      editor.layout()
      editor.focus()
    }
  })

  // 内容变更 → 同步到 store
  editor.onDidChangeModelContent(() => {
    if (ignoreChange) return
    const tab = editorStore.currentTab
    if (tab) {
      tab.content = editor.getValue()
      tab.modified = true
    }
  })

  // Ctrl+S 保存
  editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
    const tab = editorStore.currentTab
    if (tab) {
      tab.modified = false
    }
  })

  // 恢复初始标签的状态
  const tab = editorStore.currentTab
  if (tab) {
    tabStates.set(tab.id, {
      viewState: null,
      content: tab.content,
    })
  }
}

// 切换标签：保存旧标签状态 → 恢复新标签状态
function switchTab() {
  if (!editor || !monaco) return

  const oldIndex = editorStore.activeTabIndex
  const newTab = editorStore.currentTab

  // 保存旧标签的光标/滚动位置
  // (通过 activeTabIndex watch 触发)

  if (!newTab) return

  // 检查是否已有保存的状态
  let saved = tabStates.get(newTab.id)
  if (!saved) {
    saved = { viewState: null, content: newTab.content }
    tabStates.set(newTab.id, saved)
  }

  // 切换内容
  ignoreChange = true
  const model = editor.getModel()
  if (model) {
    model.setValue(newTab.content || '')
    monaco.editor.setModelLanguage(model, 'python')
  }
  ignoreChange = false

  // 恢复光标/滚动位置
  if (saved.viewState) {
    editor.restoreViewState(saved.viewState)
  }
}

watch(
  () => editorStore.activeTabIndex,
  () => {
    nextTick(switchTab)
  }
)

onMounted(() => {
  initMonaco()

  // 监听外部撤销/重做事件
  window.addEventListener('editor-undo', handleUndo)
  window.addEventListener('editor-redo', handleRedo)
})

function handleUndo() {
  if (editor) editor.trigger('keyboard', 'undo')
}

function handleRedo() {
  if (editor) editor.trigger('keyboard', 'redo')
}

onBeforeUnmount(() => {
  window.removeEventListener('editor-undo', handleUndo)
  window.removeEventListener('editor-redo', handleRedo)
  if (editor) {
    editor.dispose()
    editor = null
  }
})
</script>

<template>
  <div ref="containerRef" class="code-editor-container" />
</template>

<style scoped>
.code-editor-container {
  flex: 1;
  min-height: 0;
  background: #1e1e1e;
}
</style>
