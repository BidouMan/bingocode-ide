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

onMounted(() => {
  window.addEventListener('resize', () => fitTerminal())
  resizeObserver = new ResizeObserver(() => fitTerminal())
  if (containerRef.value) resizeObserver.observe(containerRef.value)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  terminal?.dispose()
})
</script>

<template>
  <div class="console-panel" :class="{ collapsed }">
    <div class="console-header">
      <div class="console-header-left">
        <svg class="console-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="4,17 10,11 4,5" />
          <line x1="12" y1="19" x2="20" y2="19" />
        </svg>
        <span class="console-title">控制台</span>
      </div>
      <div class="console-header-right">
        <button class="console-action" @click="terminalStore.clear()" title="清空">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3,6 5,6 21,6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </button>
        <button class="console-action" @click="toggleCollapse" :title="collapsed ? '展开' : '收起'">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline v-if="collapsed" points="6,15 12,9 18,15" />
            <polyline v-else points="6,9 12,15 18,9" />
          </svg>
        </button>
      </div>
    </div>

    <div v-show="!collapsed" ref="containerRef" class="console-body" @mousedown="onBodyClick" />
  </div>
</template>

<style scoped>
.console-panel {
  display: flex;
  flex-direction: column;
  border-top: 1px solid rgb(60, 60, 60);
  background: #1e1e1e;
  flex-shrink: 0;
  height: 200px;
}
.console-panel.collapsed {
  height: 26px;
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
</style>
