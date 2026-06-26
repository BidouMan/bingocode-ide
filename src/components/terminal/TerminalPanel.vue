<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'
import { useTerminalStore } from '../../stores/terminal'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
}>()

const terminalStore = useTerminalStore()
const containerRef = ref<HTMLDivElement>()
let terminal: Terminal | null = null
let fitAddon: FitAddon | null = null
const MAX_LINES = 5000
const collapsed = ref(false)

function createTerminal() {
  if (!containerRef.value) return

  terminal = new Terminal({
    fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
    fontSize: 13,
    lineHeight: 1.4,
    theme: {
      background: '#1e1e1e',
      foreground: '#cccccc',
      cursor: '#ffffff',
      cursorAccent: '#1e1e1e',
      selectionBackground: '#264f78',
      selectionForeground: '#ffffff',
      black: '#1e1e1e',
      red: '#f44747',
      green: '#6a9955',
      yellow: '#dcdcaa',
      blue: '#569cd6',
      magenta: '#c586c0',
      cyan: '#4ec9b0',
      white: '#cccccc',
    },
    scrollback: MAX_LINES,
    convertEol: true,
    cursorBlink: true,
    cursorStyle: 'bar',
    fontSize: 13,
    allowProposedApi: true,
  })

  fitAddon = new FitAddon()
  terminal.loadAddon(fitAddon)
  terminal.loadAddon(new WebLinksAddon())

  terminal.open(containerRef.value)
  fitAddon.fit()

  terminalStore.bindTerminal(terminal)
}

function close() {
  emit('update:visible', false)
}

function toggleCollapse() {
  collapsed.value = !collapsed.value
  if (!collapsed.value) {
    nextTick(() => {
      fitAddon?.fit()
      terminal?.focus()
    })
  }
}

watch(
  () => props.visible,
  async (val) => {
    if (val && !terminal) {
      await nextTick()
      createTerminal()
    }
    if (val) {
      await nextTick()
      fitAddon?.fit()
      terminal?.focus()
    }
  }
)

onMounted(() => {
  if (props.visible) {
    createTerminal()
  }
  window.addEventListener('resize', () => fitAddon?.fit())
})

onBeforeUnmount(() => {
  terminal?.dispose()
})
</script>

<template>
  <div class="console-panel" :class="{ collapsed }">
    <!-- 标题栏 -->
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
            <polyline v-if="collapsed" points="6,9 12,15 18,9" />
            <polyline v-else points="6,15 12,9 18,15" />
          </svg>
        </button>
      </div>
    </div>

    <!-- 终端内容 -->
    <div v-show="!collapsed" ref="containerRef" class="console-body" />
  </div>
</template>

<style scoped>
.console-panel {
  display: flex;
  flex-direction: column;
  border-top: 1px solid rgb(12, 12, 12);
  background: #1e1e1e;
  flex-shrink: 0;
  height: 200px;
  transition: height 0.2s ease;
}
.console-panel.collapsed {
  height: 32px;
}

.console-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 32px;
  padding: 0 12px;
  background: #252526;
  border-bottom: 1px solid rgb(12, 12, 12);
  flex-shrink: 0;
}

.console-header-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.console-icon {
  color: rgb(128, 128, 128);
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
  color: rgb(128, 128, 128);
  cursor: pointer;
  transition: all 0.12s;
}
.console-action:hover {
  background: rgb(61, 64, 72);
  color: white;
}

.console-body {
  flex: 1;
  min-height: 0;
}
</style>
