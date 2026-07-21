/**
 * Monaco Editor 单例初始化模块
 * 应用启动时立即加载，编辑器创建时直接使用，零等待
 *
 * 加载策略：使用 Monaco 官方提供的 AMD loader 加载预打包的 min/vs 版本，
 * 而不是 ESM import。原因：
 * - ESM 版本（monaco-editor/esm/vs/editor/editor.main.js）有数千个子模块，
 *   Vite dev 模式需要即时编译每一个，耗时 5-6 秒
 * - min/vs 是预打包+minified 的单文件版本（loader.js + editor.main.js + worker），
 *   浏览器直接执行，无需 Vite 编译，加载时间 < 1 秒
 */
import type * as Monaco from 'monaco-editor'

let monacoInstance: typeof Monaco | null = null
let initPromise: Promise<typeof Monaco> | null = null
let ready = false

// 获取 Monaco 实例（已初始化时同步返回，否则等待）
export function getMonaco(): typeof Monaco | null {
  return monacoInstance
}

// Monaco 是否已就绪
export function isMonacoReady(): boolean {
  return ready
}

// 等待 Monaco 就绪
export function waitForMonaco(): Promise<typeof Monaco> {
  if (monacoInstance) return Promise.resolve(monacoInstance)
  if (initPromise) return initPromise
  return init()
}

// 启动预加载（应用启动时调用一次）
export function preloadMonaco() {
  if (!initPromise) {
    const t = performance.now()
    console.log('[Perf] preloadMonaco starting')
    initPromise = init().then((m) => {
      console.log(`[Perf] preloadMonaco ready: ${(performance.now() - t).toFixed(1)}ms`)
      return m
    })
  }
}

// 通过 AMD loader 异步加载 Monaco（绕过 Vite，直接走静态资源）
function loadMonacoViaAmd(): Promise<typeof Monaco> {
  return new Promise((resolve, reject) => {
    // 配置 AMD loader 路径，指向 publicDir 下的预打包 monaco
    // publicDir=engine/assets，所以 /monaco/vs 对应 engine/assets/monaco/vs
    const amdLoaderScript = document.createElement('script')
    amdLoaderScript.src = '/monaco/vs/loader.js'
    amdLoaderScript.onload = () => {
      const amdRequire = (window as any).require
      if (!amdRequire) {
        reject(new Error('AMD loader not found after script load'))
        return
      }
      amdRequire.config({ paths: { vs: '/monaco/vs' } })
      amdRequire(['vs/editor/editor.main'], () => {
        const m = (window as any).monaco
        if (!m) {
          reject(new Error('monaco global not found after AMD load'))
          return
        }
        resolve(m as typeof Monaco)
      })
    }
    amdLoaderScript.onerror = () => reject(new Error('Failed to load AMD loader.js'))
    document.head.appendChild(amdLoaderScript)
  })
}

async function init(): Promise<typeof Monaco> {
  const tInit = performance.now()

  // 通过 AMD loader 加载预打包的 Monaco（绕过 Vite 编译）
  const tLoad = performance.now()
  const m = await loadMonacoViaAmd()
  console.log(`[Perf]   monaco-init: AMD load took ${(performance.now() - tLoad).toFixed(1)}ms`)
  monacoInstance = m

  // ═══ 定义主题 ═══
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

  m.editor.defineTheme('bingo-nord', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'comment', foreground: '616e88', fontStyle: 'italic' },
      { token: 'keyword', foreground: '81a1c1' },
      { token: 'string', foreground: 'a3be8c' },
      { token: 'number', foreground: 'b48ead' },
      { token: 'type', foreground: '8fbcbb' },
      { token: 'function', foreground: '88c0d0' },
      { token: 'variable', foreground: 'd8dee9' },
      { token: 'operator', foreground: '81a1c1' },
      { token: 'delimiter', foreground: 'eceff4' },
      { token: 'identifier', foreground: 'd8dee9' },
    ],
    colors: {
      'editor.background': '#2e3440',
      'editor.foreground': '#d8dee9',
      'editor.lineHighlightBackground': '#3b4252',
      'editor.selectionBackground': '#434c5e',
      'editor.inactiveSelectionBackground': '#3b4252',
      'editorCursor.foreground': '#d8dee9',
      'editorWhitespace.foreground': '#4c566a',
      'editorIndentGuide.background': '#3b4252',
      'editorIndentGuide.activeBackground': '#4c566a',
      'editorLineNumber.foreground': '#4c566a',
      'editorLineNumber.activeForeground': '#81a1c1',
      'editorGutter.background': '#2e3440',
      'editorGutter.border': 'transparent',
      'editor.selectionHighlightBackground': '#434c5e55',
      'editorBracketMatch.background': '#434c5e55',
      'editorBracketMatch.border': '#81a1c1',
      'scrollbar.shadow': '#00000000',
      'scrollbarSlider.background': '#4c566a33',
      'scrollbarSlider.hoverBackground': '#4c566a55',
      'scrollbarSlider.activeBackground': '#4c566a88',
      'minimap.background': '#2e3440',
    },
  })

  m.editor.defineTheme('bingo-one-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'comment', foreground: '5c6370', fontStyle: 'italic' },
      { token: 'keyword', foreground: 'c678dd' },
      { token: 'string', foreground: '98c379' },
      { token: 'number', foreground: 'd19a66' },
      { token: 'type', foreground: 'e5c07b' },
      { token: 'function', foreground: '61afef' },
      { token: 'variable', foreground: 'e06c75' },
      { token: 'operator', foreground: '56b6c2' },
      { token: 'delimiter', foreground: 'abb2bf' },
      { token: 'identifier', foreground: 'e06c75' },
    ],
    colors: {
      'editor.background': '#282c34',
      'editor.foreground': '#abb2bf',
      'editor.lineHighlightBackground': '#2c313c',
      'editor.selectionBackground': '#3e4451',
      'editor.inactiveSelectionBackground': '#2c313c',
      'editorCursor.foreground': '#abb2bf',
      'editorWhitespace.foreground': '#3e4451',
      'editorIndentGuide.background': '#3e4451',
      'editorIndentGuide.activeBackground': '#3e4451',
      'editorLineNumber.foreground': '#4b5263',
      'editorLineNumber.activeForeground': '#abb2bf',
      'editorGutter.background': '#282c34',
      'editorGutter.border': 'transparent',
      'editor.selectionHighlightBackground': '#3e445155',
      'editorBracketMatch.background': '#3e445155',
      'editorBracketMatch.border': '#61afef',
      'scrollbar.shadow': '#00000000',
      'scrollbarSlider.background': '#4b526333',
      'scrollbarSlider.hoverBackground': '#4b526355',
      'scrollbarSlider.activeBackground': '#4b526388',
      'minimap.background': '#282c34',
    },
  })

  // ═══ Python Monarch 语法高亮 ═══
  m.languages.setMonarchTokensProvider('python', {
    keywords: ['def', 'class', 'return', 'if', 'elif', 'else', 'for', 'while', 'import', 'from', 'as', 'try', 'except', 'finally', 'with', 'yield', 'lambda', 'pass', 'break', 'continue', 'raise', 'and', 'or', 'not', 'in', 'is', 'global', 'nonlocal', 'del', 'assert'],
    builtin: ['print', 'len', 'range', 'int', 'str', 'float', 'list', 'dict', 'tuple', 'set', 'type', 'input', 'open', 'True', 'False', 'None', 'self', 'cls'],
    engine: ['Sprite', 'Timer', 'run', 'key_down', 'key_pressed', 'wait', 'broadcast', 'receive', 'pause', 'resume', 'is_paused', 'stop', 'show_fps', 'mouse_down', 'mouse_pressed', 'mouse', 'load_map', 'follow', 'play_sound', 'show_collision', 'random_int', 'random_float', 'draw_text', 'stop_sound', 'shake', 'start_game', 'register_generator', 'unregister_generator', 'GameStop', 'stop_game'],
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

  ready = true
  return m
}
