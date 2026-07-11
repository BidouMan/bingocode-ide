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
const inputRef = ref<HTMLInputElement>()
let terminal: Terminal | null = null
let fitAddon: FitAddon | null = null
const MAX_LINES = 5000
const collapsed = ref(true)
let inputBuffer = ''

function commitInput() {
  if (!inputBuffer) return
  terminalStore.consumeInput()
  terminal?.writeln(inputBuffer)
  engine.sendInput(inputBuffer)
  inputBuffer = ''
}

function commitInputFromField() {
  inputBuffer = inputRef.value?.value || ''
  commitInput()
  if (inputRef.value) inputRef.value.value = ''
}

// 物理键盘码 → 字符映射（绕过 IME 对 Shift 的拦截）
const KEY_MAP: Record<string, string> = {
  'Space': ' ',
  'Minus': '-', 'Equal': '=', 'BracketLeft': '[', 'BracketRight': ']',
  'Backslash': '\\', 'Semicolon': ';', 'Quote': "'", 'Comma': ',',
  'Period': '.', 'Slash': '/', 'Backquote': '`', 'IntlBackslash': '\\',
  'NumpadDivide': '/', 'NumpadMultiply': '*', 'NumpadSubtract': '-',
  'NumpadAdd': '+', 'NumpadDecimal': '.',
}
const SHIFT_KEY_MAP: Record<string, string> = {
  'Minus': '_', 'Equal': '+', 'BracketLeft': '{', 'BracketRight': '}',
  'Backslash': '|', 'Semicolon': ':', 'Quote': '"', 'Comma': '<',
  'Period': '>', 'Slash': '?', 'Backquote': '~',
}
const DIGIT_SHIFT = ['!', '@', '#', '$', '%', '^', '&', '*', '(', ')']  // Shift+0 到 Shift+9

function keydownToChar(e: KeyboardEvent): string | null {
  if (e.key === 'Enter' || e.key === 'Backspace') return null
  if (e.metaKey || e.ctrlKey || e.altKey) return null
  // 数字小键盘特殊处理
  if (e.location === KeyboardEvent.DOM_KEY_LOCATION_NUMPAD) {
    return KEY_MAP[e.code] || null
  }
  // 用 e.code（物理按键位置，IME 无法篡改）映射字符
  const match = e.code.match(/^Digit(\d)$/)
  if (match) {
    const digit = parseInt(match[1])
    return e.shiftKey ? DIGIT_SHIFT[digit] : match[1]
  }
  // 非数字键
  if (e.shiftKey) return SHIFT_KEY_MAP[e.code] || (e.key.length === 1 ? e.key : null)
  return KEY_MAP[e.code] || (e.key.length === 1 ? e.key : null)
}

function onInputKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    e.preventDefault()
    commitInputFromField()
    return
  }
  if (e.key === 'Backspace') {
    e.preventDefault()
    inputBuffer = inputBuffer.slice(0, -1)
    if (inputRef.value) inputRef.value.value = inputBuffer
    return
  }
  const char = keydownToChar(e)
  if (char !== null) {
    e.preventDefault()
    inputBuffer += char
    if (inputRef.value) inputRef.value.value = inputBuffer
  }
}

watch(
  () => terminalStore.waitingForInput,
  (waiting) => {
    if (waiting && editorStore.isRunning) {
      nextTick(() => {
        inputRef.value?.focus()
        // 失焦 terminal，防止 onData 抢输入
        terminal?.blur()
      })
    }
  }
)

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

  terminal.onData((data: string) => {
    if (!editorStore.isRunning) return

    // 有原生输入框时，不通过 terminal 捕获
    if (terminalStore.waitingForInput) return

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
    <div v-show="!collapsed && terminalStore.waitingForInput" class="console-input-line">
      <input
        ref="inputRef"
        class="console-input"
        placeholder="输入..."
        @keydown="onInputKeydown"
      />
      <button class="console-input-btn" @click="commitInputFromField">↵</button>
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
  background: #1e1e1e;
}
.console-body :deep(.xterm) {
  padding-left: 8px;
  background: #1e1e1e;
}
.console-body :deep(.xterm-viewport) {
  background: #1e1e1e !important;
}

.console-input-line {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: #252526;
  border-top: 1px solid rgb(60, 60, 60);
}
.console-input {
  flex: 1;
  height: 28px;
  padding: 0 8px;
  border: 1px solid rgb(60, 60, 60);
  border-radius: 3px;
  background: #1e1e1e;
  color: #d4d4d4;
  font-size: 13px;
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
  outline: none;
  line-height: 28px;
  vertical-align: middle;
}
.console-input:focus {
  border-color: var(--accent, #5BFB84);
}
.console-input-btn {
  width: 28px;
  height: 28px;
  border: 1px solid rgb(60, 60, 60);
  border-radius: 3px;
  background: #2d2d2d;
  color: #d4d4d4;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.console-input-btn:hover {
  background: #3d3d3d;
}
</style>
