<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'
import { useTerminalStore } from '../../stores/terminal'
import { useEditorStore } from '../../stores/editor'
import { useThemeStore } from '../../stores/theme'
import { useEngine } from '../../composables/useEngine'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const terminalStore = useTerminalStore()
const editorStore = useEditorStore()
const themeStore = useThemeStore()
const engine = useEngine()
const containerRef = ref<HTMLDivElement>()
let terminal: Terminal | null = null
let fitAddon: FitAddon | null = null
const MAX_LINES = 5000
const collapsed = ref(true)
let inputBuffer = ''

// 符号按钮列表（IME 键盘按不了的符号，鼠标点击插入）
const SYMBOL_BUTTONS = ['+', '-', '*', '/', '(', ')', '!', '@', '#', '$', '%', '^', '&', '=', ':', ';', '"', "'", ',', '.', '?', '<', '>', '[', ']', '{', '}', '|', '\\', '~', '`']

// Shift+数字的符号映射（US 键盘布局）
const DIGIT_SHIFT_MAP = [')', '!', '@', '#', '$', '%', '^', '&', '*', '(']

function insertSymbol(sym: string) {
  if (!terminal || !editorStore.isRunning) return
  inputBuffer += sym
  terminal.write(sym)
}

// 用物理按键码 + shiftKey 确定字符（IME 无法篡改，在 IME 处理前截获）
function keydownToChar(e: KeyboardEvent): string | null {
  if (e.key === 'Enter' || e.key === 'Backspace') return null
  if (e.metaKey || e.ctrlKey || e.altKey) return null
  // 数字键：用 shiftKey 物理状态判断 Shift+数字
  const digitMatch = e.code.match(/^Digit(\d)$/)
  if (digitMatch) {
    const digit = parseInt(digitMatch[1])
    return e.shiftKey ? DIGIT_SHIFT_MAP[digit] : digitMatch[1]
  }
  // 小键盘
  if (e.code === 'NumpadMultiply') return '*'
  if (e.code === 'NumpadAdd') return '+'
  if (e.code === 'NumpadSubtract') return '-'
  if (e.code === 'NumpadDivide') return '/'
  if (e.code === 'NumpadDecimal') return '.'
  // 符号键
  const symMap: Record<string, [string, string]> = {
    'Minus': ['-', '_'], 'Equal': ['=', '+'],
    'BracketLeft': ['[', '{'], 'BracketRight': [']', '}'],
    'Backslash': ['\\', '|'], 'Semicolon': [';', ':'],
    'Quote': ["'", '"'], 'Comma': [',', '<'],
    'Period': ['.', '>'], 'Slash': ['/', '?'],
    'Backquote': ['`', '~'], 'Space': [' ', ' '],
  }
  const pair = symMap[e.code]
  if (pair) return e.shiftKey ? pair[1] : pair[0]
  // 普通键：直接取 event.key（仅在 IME 未拦截时有效）
  if (e.key.length === 1) return e.key
  return null
}

// keydown 统一处理所有按键输入（代码模式 + game 模式），用物理键码绕过 IME
function onTerminalKeydown(e: KeyboardEvent) {
  if (!editorStore.isRunning) return

  if (e.key === 'Enter') {
    e.preventDefault()
    e.stopPropagation()
    terminalStore.consumeInput()
    terminal?.write('\r\n')
    engine.sendInput(inputBuffer)
    inputBuffer = ''
    return
  }
  if (e.key === 'Backspace') {
    e.preventDefault()
    e.stopPropagation()
    if (inputBuffer.length > 0) {
      inputBuffer = inputBuffer.slice(0, -1)
      terminal!.write('\b \b')
    }
    return
  }

  const char = keydownToChar(e)
  if (char !== null) {
    e.preventDefault()
    e.stopPropagation()
    inputBuffer += char
    terminal!.write(char)
  }
}

function createTerminal() {
  if (!containerRef.value || terminal) return

  terminal = new Terminal({
    fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
    fontSize: 13,
    lineHeight: 1.4,
    theme: themeStore.colors.terminalTheme as any,
    scrollback: MAX_LINES,
    convertEol: true,
    cursorBlink: true,
    cursorStyle: 'bar',
    cursorInactiveStyle: 'none',
    allowProposedApi: true,
  })

  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.loadAddon(new WebLinksAddon())

  terminal.open(containerRef.value)
  terminalStore.bindTerminal(terminal)

  // 捕获阶段拦截 keydown，在 xterm.js 处理之前截获，e.preventDefault() 才能阻止 xterm 重复处理
  containerRef.value.addEventListener('keydown', onTerminalKeydown, true)

  // 所有输入由 keydown 统一处理，onData 仅兜底（正常情况不会触发）
  terminal.onData((data: string) => {
    if (!editorStore.isRunning) return

    if (data === '\r') {
      terminalStore.consumeInput()
      terminal!.write('\r\n')
      engine.sendInput(inputBuffer)
      inputBuffer = ''
    } else if (data === '\x7f') {
      if (inputBuffer.length > 0) {
        inputBuffer = inputBuffer.slice(0, -1)
        terminal!.write('\b \b')
      }
    } else if (data >= ' ') {
      inputBuffer += data
      terminal!.write(data)
    }
  })
}

function fitTerminal() {
  if (!fitAddon || !terminal) return
  const vp = (terminal as any).viewport
  if (!vp || !vp.scrollBarWidth) return
  fitAddon.fit()
}

function clearInputBuffer() {
  inputBuffer = ''
}

function onBodyClick() {
  setTimeout(() => terminal?.focus(), 0)
}

function close() {
  emit('update:visible', false)
}

function toggleCollapse() {
  collapsed.value = !collapsed.value
  if (!collapsed.value) {
    nextTick(() => {
      createTerminal()
      if (editorStore.isRunning) {
        terminal?.blur()
      } else {
        terminal?.focus()
      }
    })
  }
}

watch(
  () => props.visible,
  async (val) => {
    if (val) {
      collapsed.value = false
      await nextTick()
      createTerminal()
      if (editorStore.isRunning) {
        terminal?.blur()
      }
    }
  }
)

watch(
  () => terminalStore.waitingForInput,
  (waiting) => {
    if (waiting && editorStore.isRunning) {
      nextTick(() => terminal?.focus())
    }
  }
)

watch(
  () => editorStore.isRunning,
  (running) => {
    if (!running) {
      clearInputBuffer()
    }
  }
)

watch(
  () => themeStore.currentTheme,
  () => {
    if (terminal) {
      terminal.options.theme = themeStore.colors.terminalTheme as any
    }
  }
)

let resizeObserver: ResizeObserver | null = null

// ═══ 拖动调整大小 ═══
const panelHeight = ref(200)
const isDragging = ref(false)
const showHighlight = ref(false)
let highlightTimer: ReturnType<typeof setTimeout> | null = null
let startY = 0
let startHeight = 0

function onDragHandleEnter() {
  highlightTimer = setTimeout(() => {
    showHighlight.value = true
  }, 300)
}

function onDragHandleLeave() {
  if (highlightTimer) {
    clearTimeout(highlightTimer)
    highlightTimer = null
  }
  if (!isDragging.value) {
    showHighlight.value = false
  }
}

function onDragStart(e: MouseEvent) {
  isDragging.value = true
  showHighlight.value = true
  startY = e.clientY
  startHeight = panelHeight.value
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
  document.body.style.cursor = 'row-resize'
  document.body.style.userSelect = 'none'
}

function onDragMove(e: MouseEvent) {
  if (!isDragging.value) return
  const delta = startY - e.clientY
  const newHeight = Math.max(100, Math.min(window.innerHeight * 0.7, startHeight + delta))
  panelHeight.value = newHeight
  fitTerminal()
}

function onDragEnd() {
  isDragging.value = false
  showHighlight.value = false
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

onMounted(() => {
  window.addEventListener('resize', () => fitTerminal())
  resizeObserver = new ResizeObserver(() => fitTerminal())
  if (containerRef.value) resizeObserver.observe(containerRef.value)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  if (containerRef.value) {
    containerRef.value.removeEventListener('keydown', onTerminalKeydown, true)
  }
  terminal?.dispose()
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  if (highlightTimer) clearTimeout(highlightTimer)
})
</script>

<template>
  <div class="console-panel" :class="{ collapsed }" :style="{ height: collapsed ? '26px' : panelHeight + 'px' }">
    <div
      class="console-drag-handle"
      :class="{ 'console-drag-handle-active': showHighlight }"
      @mouseenter="onDragHandleEnter"
      @mouseleave="onDragHandleLeave"
      @mousedown.prevent="onDragStart"
    />
    <div class="console-header">
      <div class="console-header-left">
        <svg class="console-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="4,17 10,11 4,5" />
          <line x1="12" y1="19" x2="20" y2="19" />
        </svg>
        <span class="console-title">控制台</span>
      </div>
      <div class="console-header-right">
        <button class="console-action" @click="terminalStore.clear()" v-tooltip="'清空'">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3,6 5,6 21,6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </button>
        <button class="console-action" @click="toggleCollapse" v-tooltip="collapsed ? '展开' : '收起'">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline v-if="collapsed" points="6,15 12,9 18,15" />
            <polyline v-else points="6,9 12,15 18,9" />
          </svg>
        </button>
      </div>
    </div>

    <div v-show="!collapsed" ref="containerRef" class="console-body" @mousedown="onBodyClick" />
    <!-- 符号按钮栏：IME 按不了的符号用鼠标点 -->
    <div v-show="!collapsed && terminalStore.waitingForInput" class="symbol-bar">
      <button
        v-for="sym in SYMBOL_BUTTONS"
        :key="sym"
        class="symbol-btn"
        @mousedown.prevent="insertSymbol(sym)"
      >{{ sym }}</button>
    </div>
  </div>
</template>

<style scoped>
.console-panel {
  display: flex;
  flex-direction: column;
  border-top: 1px solid rgb(60, 60, 60);
  background: #1e1e1e;
  flex-shrink: 0;
  position: relative;
  overflow: hidden;
}
.console-panel.collapsed {
  height: 26px;
}

.console-drag-handle {
  position: absolute;
  top: -3px;
  left: 0;
  right: 0;
  height: 7px;
  cursor: row-resize;
  z-index: 10;
}
.console-drag-handle::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 0;
  right: 0;
  height: 2px;
  background: transparent;
  transition: background 0.1s ease;
}
.console-drag-handle-active::after {
  background: var(--accent);
}

.console-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 26px;
  padding: 0 10px;
  background: #252526;
  border-bottom: 1px solid rgb(60, 60, 60);
  flex-shrink: 0;
}

.console-header-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.console-icon {
  color: var(--text-muted);
}

.console-title {
  font-size: 11px;
  font-weight: 600;
  color: rgb(180, 180, 180);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.console-header-right {
  display: flex;
  align-items: center;
  gap: 2px;
}

.console-action {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  border-radius: 3px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.12s;
}
.console-action:hover {
  background: var(--bg-hover);
  color: white;
}

.console-body {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  background: #1e1e1e;
}
.console-body :deep(.xterm) {
  padding-left: 8px;
  background: #1e1e1e;
}
.console-body :deep(.xterm-viewport) {
  background: #1e1e1e !important;
}

.symbol-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  padding: 4px 6px;
  background: #252526;
  border-top: 1px solid rgb(60, 60, 60);
  max-height: 60px;
  overflow-y: auto;
}
.symbol-btn {
  width: 26px;
  height: 26px;
  border: 1px solid rgb(70, 70, 70);
  border-radius: 3px;
  background: #2d2d2d;
  color: #d4d4d4;
  font-size: 12px;
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  user-select: none;
}
.symbol-btn:hover {
  background: #3d4048;
  border-color: rgb(91, 251, 132);
}
</style>
