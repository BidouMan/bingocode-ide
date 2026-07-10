<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useEditorStore } from '../../stores/editor'
import { useThemeStore } from '../../stores/theme'

const editorStore = useEditorStore()
const themeStore = useThemeStore()
const containerRef = ref<HTMLDivElement>()
let editor: any = null
let monaco: any = null
let ignoreChange = false
let wheelHandler: ((e: WheelEvent) => void) | null = null
const tabStates = new Map<string, { viewState: any; content: string }>()

function updateLineNumberWidth() {
  if (!editor) return
  const lineCount = editor.getModel()?.getLineCount() ?? 0
  let chars = 3
  if (lineCount >= 10000) chars = 5
  else if (lineCount >= 1000) chars = 4
  editor.updateOptions({ lineNumbersMinChars: chars })
}

async function initMonaco() {
  // 配置 Monaco web worker（ES 模块模式必须手动指定）
  window.MonacoEnvironment = {
    getWorker(_: any, label: string) {
      return new Worker(new URL('monaco-editor/esm/vs/editor/editor.worker.js', import.meta.url), { type: 'module' })
    },
  }

  // 直接从本地 npm 包加载 Monaco（ES 模块），不走 CDN 也不走 @monaco-editor/loader 的脚本注入
  const m = await import('monaco-editor/esm/vs/editor/editor.main.js')
  monaco = m

  if (!containerRef.value) return

  // Tokyo Night 风格主题
  m.editor.defineTheme('bingo-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'comment', foreground: '565f89', fontStyle: 'italic' },
      { token: 'keyword', foreground: 'bb9af7' },
      { token: 'string', foreground: '9ece6a' },
      { token: 'number', foreground: 'ff9e64' },
      { token: 'type', foreground: '2ac3de' },
      { token: 'function', foreground: '7aa2f7' },
      { token: 'variable', foreground: 'c0caf5' },
      { token: 'operator', foreground: '89ddff' },
      { token: 'delimiter', foreground: 'e2b78d' },
      { token: 'identifier', foreground: 'c0caf5' },
    ],
    colors: {
      'editor.background': '#1a1b26',
      'editor.foreground': '#c0caf5',
      'editor.lineHighlightBackground': '#1e2030',
      'editor.selectionBackground': '#33467c',
      'editor.inactiveSelectionBackground': '#283457',
      'editorCursor.foreground': '#c0caf5',
      'editorWhitespace.foreground': '#3b4261',
      'editorIndentGuide.background': '#292e42',
      'editorIndentGuide.activeBackground': '#3b4261',
      'editorLineNumber.foreground': '#3d4260',
      'editorLineNumber.activeForeground': '#737aa2',
      'editorGutter.background': '#1a1b26',
      'editorGutter.border': 'transparent',
      'editor.selectionHighlightBackground': '#33467c55',
      'editorBracketMatch.background': '#33467c55',
      'editorBracketMatch.border': '#565f89',
      'scrollbar.shadow': '#00000000',
      'scrollbarSlider.background': '#3b426133',
      'scrollbarSlider.hoverBackground': '#3b426155',
      'scrollbarSlider.activeBackground': '#3b426188',
      'minimap.background': '#1a1b26',
    },
  })

  // Light theme
  m.editor.defineTheme('bingo-light', {
    base: 'vs',
    inherit: true,
    rules: [
      { token: 'comment', foreground: 'a0a1a7', fontStyle: 'italic' },
      { token: 'keyword', foreground: 'a626a4' },
      { token: 'string', foreground: '50a14f' },
      { token: 'number', foreground: '986801' },
      { token: 'type', foreground: 'c18401' },
      { token: 'function', foreground: '4078f2' },
      { token: 'variable', foreground: '383a42' },
      { token: 'operator', foreground: '383a42' },
      { token: 'delimiter', foreground: '383a42' },
      { token: 'identifier', foreground: '383a42' },
    ],
    colors: {
      'editor.background': '#ffffff',
      'editor.foreground': '#383a42',
      'editor.lineHighlightBackground': '#f5f5f5',
      'editor.selectionBackground': '#bfceff',
      'editor.inactiveSelectionBackground': '#e5ebf6',
      'editorCursor.foreground': '#526fff',
      'editorWhitespace.foreground': '#d1d9e0',
      'editorIndentGuide.background': '#e8eaed',
      'editorIndentGuide.activeBackground': '#c4c7c9',
      'editorLineNumber.foreground': '#a0a1a7',
      'editorLineNumber.activeForeground': '#383a42',
      'editorGutter.background': '#ffffff',
      'editorGutter.border': 'transparent',
      'editor.selectionHighlightBackground': '#bfceff55',
      'editorBracketMatch.background': '#bfceff55',
      'editorBracketMatch.border': '#a0a1a7',
      'scrollbar.shadow': '#00000000',
      'scrollbarSlider.background': '#383a4233',
      'scrollbarSlider.hoverBackground': '#383a4255',
      'scrollbarSlider.activeBackground': '#383a4288',
      'minimap.background': '#ffffff',
    },
  })

  // Warm theme (Gruvbox-style warm dark)
  m.editor.defineTheme('bingo-warm', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'comment', foreground: '928374', fontStyle: 'italic' },
      { token: 'keyword', foreground: 'fb4934' },
      { token: 'string', foreground: 'b8bb26' },
      { token: 'number', foreground: 'd3869b' },
      { token: 'type', foreground: '8ec07c' },
      { token: 'function', foreground: 'fabd2f' },
      { token: 'variable', foreground: 'ebdbb2' },
      { token: 'operator', foreground: 'fb4934' },
      { token: 'delimiter', foreground: 'ebdbb2' },
      { token: 'identifier', foreground: 'ebdbb2' },
    ],
    colors: {
      'editor.background': '#282828',
      'editor.foreground': '#ebdbb2',
      'editor.lineHighlightBackground': '#3c3836',
      'editor.selectionBackground': '#504945',
      'editor.inactiveSelectionBackground': '#3c3836',
      'editorCursor.foreground': '#ebdbb2',
      'editorWhitespace.foreground': '#665c54',
      'editorIndentGuide.background': '#3c3836',
      'editorIndentGuide.activeBackground': '#665c54',
      'editorLineNumber.foreground': '#665c54',
      'editorLineNumber.activeForeground': '#fabd2f',
      'editorGutter.background': '#282828',
      'editorGutter.border': 'transparent',
      'editor.selectionHighlightBackground': '#50494555',
      'editorBracketMatch.background': '#50494555',
      'editorBracketMatch.border': '#928374',
      'scrollbar.shadow': '#00000000',
      'scrollbarSlider.background': '#665c5433',
      'scrollbarSlider.hoverBackground': '#665c5455',
      'scrollbarSlider.activeBackground': '#665c5488',
      'minimap.background': '#282828',
    },
  })

  // Python Monarch tokenizer
  m.languages.setMonarchTokensProvider('python', {
    keywords: ['def','class','return','if','elif','else','for','while','import','from','as','try','except','finally','with','yield','lambda','pass','break','continue','raise','and','or','not','in','is','global','nonlocal','del','assert'],
    builtin: ['print','len','range','int','str','float','list','dict','tuple','set','type','input','open','True','False','None','self','cls'],
    tokenizer: {
      root: [
        [/"""/, 'string', '@multiString'],
        [/'''/, 'string', '@multiString'],
        [/''/, 'string'],
        [/""/, 'string'],
        [/"(?!")/, 'string', '@dblString'],
        [/'(?!')/, 'string', '@sglString'],
        [/#.*$/, 'comment'],
        [/\b\d+\.?\d*\b/, 'number'],
        [/[a-zA-Z_]\w*/, {
          cases: {
            '@keywords': 'keyword',
            '@builtin': 'type',
            '@default': 'identifier',
          },
        }],
        [/[ \t]+/, 'white'],
        [/[(){}[\]]/, 'delimiter'],
        [/./, 'source'],
      ],
      dblString: [
        [/[^"\\]+/, 'string'],
        [/\\./, 'string.escape'],
        [/"/, 'string', '@pop'],
      ],
      sglString: [
        [/[^'\\]+/, 'string'],
        [/\\./, 'string.escape'],
        [/'/, 'string', '@pop'],
      ],
      multiString: [
        [/[^"']+/, 'string'],
        [/"""/, 'string', '@pop'],
        [/'''/, 'string', '@pop'],
        [/""/, 'string'],
        [/''/, 'string'],
        [/["']/, 'string'],
      ],
    },
  })

  editor = m.editor.create(containerRef.value, {
    value: editorStore.currentTab?.content || '',
    language: 'python',
    theme: themeStore.colors.monacoTheme,
    fontSize: editorStore.editorFontSize,
    lineHeight: Math.round(editorStore.editorFontSize * 1.5),
    fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
    fontLigatures: false,
    mouseWheelZoom: false,
    minimap: { enabled: false },
    automaticLayout: true,
    scrollBeyondLastLine: false,
    renderWhitespace: 'selection',
    bracketPairColorization: { enabled: false },
    matchBrackets: 'never',
    guides: { bracketPairs: false },
    highlightActiveBracketPair: false,
    selectionHighlight: false,
    cursorBlinking: 'solid',
    cursorSmoothCaretAnimation: 'off',
    smoothScrolling: false,
    padding: { top: 0, bottom: 0 },
    tabSize: 4,
    insertSpaces: true,
    wordWrap: 'off',
    lineNumbers: 'on',
    glyphMargin: false,
    folding: true,
    lineDecorationsWidth: 16,
    lineNumbersMinChars: 3,
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
    suggest: { showUnused: false },
    parameterHints: { enabled: false },
  })

  nextTick(() => {
    if (editor) {
      editor.layout()
      editor.focus()
    }
  })

  // IME 中文输入法处理
  // 抖动根因：组合期间 textarea 宽度变化 (1→59px) 触发容器重排
  // 方案：永久固定 textarea 尺寸 + contain:strict 隔离布局影响，opacity:0 隐藏
  const editorDomNode = editor.getDomNode()
  if (editorDomNode) {
    if (!document.getElementById('ime-stable-style')) {
      const style = document.createElement('style')
      style.id = 'ime-stable-style'
      style.textContent = `
        .monaco-editor textarea.inputarea {
          width: 1px !important;
          min-width: 1px !important;
          max-width: 1px !important;
          height: 24px !important;
          min-height: 24px !important;
          max-height: 24px !important;
          overflow: hidden !important;
          contain: strict !important;
          opacity: 0 !important;
        }
      `
      document.head.appendChild(style)
    }
  }

  // 自定义滚轮缩放：Cmd/Ctrl + 滚轮，每次加减 10%
  wheelHandler = (e: WheelEvent) => {
    if ((e.ctrlKey || e.metaKey) && containerRef.value?.contains(e.target as Node)) {
      e.preventDefault()
      e.stopPropagation()
      if (e.deltaY > 0) {
        editorStore.zoomOut()
      } else {
        editorStore.zoomIn()
      }
    }
  }
  window.addEventListener('wheel', wheelHandler, { capture: true, passive: false })

  // 内容变更 → 同步到 store + 动态调整行号宽度
  editor.onDidChangeModelContent(() => {
    if (ignoreChange) return
    const tab = editorStore.currentTab
    if (tab) {
      tab.content = editor.getValue()
      tab.modified = true
    }
    updateLineNumberWidth()
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

function switchTab() {
  if (!editor || !monaco) return

  const newTab = editorStore.currentTab

  if (!newTab) return

  let saved = tabStates.get(newTab.id)
  if (!saved) {
    saved = { viewState: null, content: newTab.content }
    tabStates.set(newTab.id, saved)
  }

  ignoreChange = true
  const model = editor.getModel()
  if (model) {
    model.setValue(newTab.content || '')
    monaco.editor.setModelLanguage(model, 'python')
  }
  ignoreChange = false

  if (saved.viewState) {
    editor.restoreViewState(saved.viewState)
  }
  updateLineNumberWidth()
}

watch(
  () => editorStore.currentTab,
  () => {
    nextTick(switchTab)
  }
)

watch(
  () => themeStore.currentTheme,
  () => {
    if (monaco && themeStore.colors.monacoTheme) {
      monaco.editor.setTheme(themeStore.colors.monacoTheme)
    }
  }
)

watch(
  () => editorStore.editorFontSize,
  (newSize) => {
    if (editor) {
      // 行间距跟随字体大小：fontSize * 1.5
      const lineHeight = Math.round(newSize * 1.5)
      editor.updateOptions({ fontSize: newSize, lineHeight })
    }
  }
)

onMounted(() => {
  initMonaco()

  window.addEventListener('editor-undo', handleUndo)
  window.addEventListener('editor-redo', handleRedo)
  window.addEventListener('editor-refresh-content', handleRefreshContent)
})

function handleUndo() {
  if (editor) editor.trigger('keyboard', 'undo')
}

function handleRedo() {
  if (editor) editor.trigger('keyboard', 'redo')
}

function handleRefreshContent() {
  if (!editor || !monaco) return
  const tab = editorStore.currentTab
  if (tab) {
    ignoreChange = true
    const model = editor.getModel()
    if (model) {
      model.setValue(tab.content || '')
    }
    ignoreChange = false
  }
}

onBeforeUnmount(() => {
  window.removeEventListener('editor-undo', handleUndo)
  window.removeEventListener('editor-redo', handleRedo)
  window.removeEventListener('editor-refresh-content', handleRefreshContent)
  if (wheelHandler) {
    window.removeEventListener('wheel', wheelHandler, { capture: true } as any)
    wheelHandler = null
  }
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
  background: #1a1b26;
}
.code-editor-container :deep(.margin) {
  border-right: none;
  background: #1a1b26;
}
.code-editor-container :deep(.monaco-editor .margin) {
  padding-right: 4px;
}
</style>
