<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useEditorStore } from '../../stores/editor'
import { useThemeStore } from '../../stores/theme'
import { allEngineCompletions, dotCompletions, spriteDotDefault, pythonCompletions, pythonDotCompletions } from './engine-completions'

const editorStore = useEditorStore()
const themeStore = useThemeStore()

const isMac = navigator.platform.toUpperCase().includes('MAC')
const modKey = isMac ? '⌘' : 'Ctrl'

// ─── 右键菜单 ───
const ctxMenu = ref({ show: false, x: 0, y: 0 })

function onContextMenu(e: MouseEvent) {
  e.preventDefault()
  if (!editor) return
  editor.focus()
  // 边界检测：防止菜单超出屏幕
  const menuW = 200
  const menuH = 280
  let x = e.clientX
  let y = e.clientY
  if (x + menuW > window.innerWidth) x = window.innerWidth - menuW
  if (y + menuH > window.innerHeight) y = window.innerHeight - menuH
  ctxMenu.value = { show: true, x, y }
}

function closeCtxMenu() {
  ctxMenu.value.show = false
}

// ─── 菜单动作 ───
function doUndo() { closeCtxMenu(); editor?.trigger('contextMenu', 'undo') }
function doRedo() { closeCtxMenu(); editor?.trigger('contextMenu', 'redo') }
function doCut() { closeCtxMenu(); document.execCommand('cut') }
function doCopy() { closeCtxMenu(); document.execCommand('copy') }
function doPaste() {
  closeCtxMenu()
  navigator.clipboard.readText().then(text => {
    if (text && editor) {
      const selection = editor.getSelection()
      if (selection) {
        editor.executeEdits('contextMenu', [{
          range: selection,
          text,
          forceMoveMarkers: true,
        }])
      }
    }
  }).catch(() => {})
}

function doComment() {
  closeCtxMenu()
  if (!editor || !monaco) return
  const model = editor.getModel()
  if (!model) return
  const selections = editor.getSelections()
  if (!selections) return
  const edits: any[] = []
  let shouldComment = false
  for (const sel of selections) {
    const startLine = sel.startLineNumber
    const endLine = sel.endLineNumber
    for (let i = startLine; i <= endLine; i++) {
      const lineContent = model.getLineContent(i)
      if (lineContent.trimStart().startsWith('#')) {
        shouldComment = false
        break
      } else if (lineContent.trim().length > 0) {
        shouldComment = true
      }
    }
    if (shouldComment) break
  }
  for (const sel of selections) {
    for (let i = sel.startLineNumber; i <= sel.endLineNumber; i++) {
      const lineContent = model.getLineContent(i)
      if (shouldComment) {
        edits.push({
          range: new monaco.Range(i, 1, i, 1),
          text: '# ',
          forceMoveMarkers: true,
        })
      } else if (lineContent.trimStart().startsWith('#')) {
        const hashIdx = lineContent.indexOf('#')
        // 移除 # 和后面的空格（如果有）
        const endCol = (lineContent.charAt(hashIdx + 1) === ' ') ? hashIdx + 3 : hashIdx + 2
        edits.push({
          range: new monaco.Range(i, hashIdx + 1, i, endCol),
          text: '',
          forceMoveMarkers: true,
        })
      }
    }
  }
  if (edits.length > 0) {
    editor.executeEdits('contextMenu', edits)
  }
}

function doRun() {
  closeCtxMenu()
  window.dispatchEvent(new CustomEvent('editor-run'))
}

function doFormat() {
  closeCtxMenu()
  window.dispatchEvent(new CustomEvent('editor-format'))
}

function doCheck() {
  closeCtxMenu()
  window.dispatchEvent(new CustomEvent('editor-check'))
}
const containerRef = ref<HTMLDivElement>()
let editor: any = null
let monaco: any = null
let ignoreChange = false
let wheelHandler: ((e: WheelEvent) => void) | null = null
let ctxMenuHandler: ((e: Event) => void) | null = null
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
    engine: ['Sprite','Timer','run','key_down','key_pressed','wait','broadcast','receive','pause','resume','is_paused','stop','show_fps','mouse_down','mouse_pressed','mouse','load_map','follow','play_sound','show_collision','random_int','random_float','draw_text','stop_sound','shake','start_game','register_generator','unregister_generator','GameStop','stop_game'],
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
            '@engine': 'type',
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
    suggest: {
      showMethods: true,
      showFunctions: true,
      showConstructors: true,
      showFields: true,
      showVariables: true,
      showClasses: true,
      showModules: true,
      showKeywords: true,
      showWords: true,
      showSnippets: false,
      showConstants: true,
    },
    parameterHints: { enabled: false },
    contextmenu: false,
  })

  // 注册智能补全（游戏模式 = 引擎 API + Python 标准库，代码模式 = Python 标准库）
  m.languages.registerCompletionItemProvider('python', {
    triggerCharacters: ['.', ' '],
    provideCompletionItems(model, position) {
      const textUntilPosition = model.getValueInRange({
        startLineNumber: position.lineNumber,
        startColumn: 1,
        endLineNumber: position.lineNumber,
        endColumn: position.column,
      })

      const wordInfo = model.getWordUntilPosition(position)
      const range = {
        startLineNumber: position.lineNumber,
        endLineNumber: position.lineNumber,
        startColumn: wordInfo.startColumn,
        endColumn: wordInfo.endColumn,
      }

      // 点号后触发：根据模式过滤对应类的方法/属性
      const dotMatch = textUntilPosition.match(/(\w+)\.\s*$/)
      if (dotMatch) {
        const varName = dotMatch[1].toLowerCase()
        if (editorStore.isGameMode) {
          // 游戏模式：优先匹配已知变量名，否则默认显示 Sprite 方法
          const methods = dotCompletions[varName] || spriteDotDefault
          return { suggestions: methods.map(item => ({ ...item, range })) }
        } else {
          // 代码模式：匹配 Python 类型方法
          const methods = pythonDotCompletions[varName]
          if (methods) {
            return { suggestions: methods.map(item => ({ ...item, range })) }
          }
        }
      }

      // 普通触发：返回对应模式的补全项
      if (editorStore.isGameMode) {
        // 游戏模式：引擎 API + Python 标准库（去重）
        const seen = new Set<string>()
        const merged = [...pythonCompletions, ...allEngineCompletions].filter(item => {
          if (seen.has(item.label)) return false
          seen.add(item.label)
          return true
        })
        return { suggestions: merged.map(item => ({ ...item, range })) }
      } else {
        return { suggestions: pythonCompletions.map(item => ({ ...item, range })) }
      }
    },
  })

  nextTick(() => {
    if (editor) {
      editor.layout()
      editor.focus()
    }
  })

  // 在 window 捕获阶段监听右键，确保不被 Monaco 拦截
  ctxMenuHandler = (e: Event) => {
    const me = e as MouseEvent
    const editorDom = editor?.getDomNode()
    if (editorDom && editorDom.contains(me.target as Node)) {
      me.preventDefault()
      me.stopPropagation()
      onContextMenu(me)
    }
  }
  window.addEventListener('contextmenu', ctxMenuHandler, true)

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
  window.addEventListener('click', closeCtxMenu)
  window.addEventListener('contextmenu', closeCtxMenu)
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

// 跳转到指定行（搜索/大纲面板调用）
function handleGotoLine(e: Event) {
  const { line } = (e as CustomEvent).detail
  if (editor && line) {
    editor.revealLineInCenter(line)
    editor.setPosition({ lineNumber: line, column: 1 })
    editor.focus()
  }
}
window.addEventListener('editor:goto-line', handleGotoLine)

// 在光标位置插入文本（代码片段面板调用）
function handleInsertText(e: Event) {
  const { text } = (e as CustomEvent).detail
  if (editor && text) {
    const position = editor.getPosition()
    if (position) {
      editor.executeEdits('snippet', [{
        range: new monaco.Range(position.lineNumber, position.column, position.lineNumber, position.column),
        text: text + '\n',
      }])
    }
    editor.focus()
  }
}
window.addEventListener('editor:insert-text', handleInsertText)

// 重命名符号（大纲面板调用）：全文件替换同名标识符
function handleRenameSymbol(e: Event) {
  const { oldName, newName, type } = (e as CustomEvent).detail
  if (!editor || !oldName || !newName || oldName === newName) return

  const model = editor.getModel()
  if (!model) return

  // 构造匹配正则：确保替换的是完整标识符（不是子串）
  // \b 在 monaco 中对 _ 开头的标识符可能不准，用 (^|[^a-zA-Z_]) 前瞻
  const escapedOld = oldName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  // 根据类型，只在匹配关键字后面的位置替换
  const patterns: Record<string, RegExp> = {
    function: new RegExp(`(\\bdef\\s+)${escapedOld}\\b`, 'g'),
    class: new RegExp(`(\\bclass\\s+)${escapedOld}\\b`, 'g'),
    variable: new RegExp(`(?<=^|[^a-zA-Z_])${escapedOld}\\b`, 'gm'),
    import: new RegExp(`(?<=^import\\s+|^from\\s+\\S+\\s+import\\s+)${escapedOld}\\b`, 'gm'),
  }

  // 简单方案：全文件 \b 替换完整标识符
  const fullPattern = new RegExp(`\\b${escapedOld}\\b`, 'g')
  const content = model.getValue()
  const newContent = content.replace(fullPattern, newName)

  if (newContent !== content) {
    editor.pushUndoStop()
    editor.executeEdits('rename-symbol', [{
      range: model.getFullModelRange(),
      text: newContent,
    }])
    editor.pushUndoStop()
  }
}
window.addEventListener('editor:rename-symbol', handleRenameSymbol)

onBeforeUnmount(() => {
  window.removeEventListener('editor-undo', handleUndo)
  window.removeEventListener('editor-redo', handleRedo)
  window.removeEventListener('editor-refresh-content', handleRefreshContent)
  window.removeEventListener('editor:goto-line', handleGotoLine)
  window.removeEventListener('editor:insert-text', handleInsertText)
  window.removeEventListener('editor:rename-symbol', handleRenameSymbol)
  window.removeEventListener('click', closeCtxMenu)
  window.removeEventListener('contextmenu', closeCtxMenu)
  if (ctxMenuHandler) {
    window.removeEventListener('contextmenu', ctxMenuHandler, true)
    ctxMenuHandler = null
  }
  if (wheelHandler) {
    window.removeEventListener('wheel', wheelHandler, { capture: true } as any)
    wheelHandler = null
  }
  if (editor) {
    const editorDom = editor.getDomNode()
    if (editorDom) {
      editorDom.removeEventListener('contextmenu', onContextMenu)
    }
    editor.dispose()
    editor = null
  }
})
</script>

<template>
  <div ref="containerRef" class="code-editor-container" />
  <Teleport to="body">
    <div
      v-if="ctxMenu.show"
      class="editor-ctx-menu"
      :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
      @click.stop
    >
      <div class="editor-ctx-item" @click="doUndo">
        <span>撤销</span><span class="editor-ctx-shortcut">{{ modKey }}+Z</span>
      </div>
      <div class="editor-ctx-item" @click="doRedo">
        <span>重做</span><span class="editor-ctx-shortcut">{{ modKey }}+Shift+Z</span>
      </div>
      <div class="editor-ctx-divider" />
      <div class="editor-ctx-item" @click="doCut">
        <span>剪切</span><span class="editor-ctx-shortcut">{{ modKey }}+X</span>
      </div>
      <div class="editor-ctx-item" @click="doCopy">
        <span>复制</span><span class="editor-ctx-shortcut">{{ modKey }}+C</span>
      </div>
      <div class="editor-ctx-item" @click="doPaste">
        <span>粘贴</span><span class="editor-ctx-shortcut">{{ modKey }}+V</span>
      </div>
      <div class="editor-ctx-divider" />
      <div class="editor-ctx-item" @click="doComment">
        <span>注释/取消注释</span><span class="editor-ctx-shortcut">{{ modKey }}+/</span>
      </div>
      <div class="editor-ctx-divider" />
      <div class="editor-ctx-item" @click="doRun">
        <span>运行</span><span class="editor-ctx-shortcut">F5</span>
      </div>
      <div class="editor-ctx-item" @click="doFormat">
        <span>格式化代码</span><span class="editor-ctx-shortcut">Shift+Alt+F</span>
      </div>
      <div class="editor-ctx-item" @click="doCheck">
        <span>检查语法</span><span class="editor-ctx-shortcut"></span>
      </div>
    </div>
  </Teleport>
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

.editor-ctx-menu {
  position: fixed;
  background: #1a1b26;
  border: 1px solid #3b4261;
  border-radius: 6px;
  padding: 4px 0;
  z-index: 10000;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
  min-width: 180px;
}
.editor-ctx-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 14px;
  font-size: 13px;
  color: #a9b1d6;
  cursor: pointer;
  user-select: none;
}
.editor-ctx-item:hover {
  background: #24283b;
  color: #c0caf5;
}
.editor-ctx-shortcut {
  font-size: 11px;
  color: #565f89;
  margin-left: 24px;
}
.editor-ctx-divider {
  height: 1px;
  background: #3b4261;
  margin: 4px 8px;
}
</style>
