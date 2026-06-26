import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useTerminalStore = defineStore('terminal', () => {
  const lines = ref<string[]>([])
  const MAX_LINES = 5000
  const FLUSH_INTERVAL_MS = 30

  let pendingText = ''
  let flushTimer: ReturnType<typeof setTimeout> | null = null
  let terminalInstance: any = null

  function bindTerminal(terminal: any) {
    terminalInstance = terminal
  }

  function appendLine(text: string) {
    if (!terminalInstance) return
    terminalInstance.writeln(text)
    lines.value.push(text)
    if (lines.value.length > MAX_LINES) {
      const excess = lines.value.length - MAX_LINES
      lines.value.splice(0, excess)
    }
  }

  function appendBatch(text: string) {
    pendingText += text
    if (!flushTimer) {
      flushTimer = setTimeout(flush, FLUSH_INTERVAL_MS)
    }
  }

  function flush() {
    if (!pendingText) {
      if (flushTimer) {
        flushTimer = null
      }
      return
    }

    const text = pendingText
    pendingText = ''
    flushTimer = null

    const waiting = text.includes('__BINGO_WAITING_INPUT__')
    const cleaned = text.replace('__BINGO_WAITING_INPUT__', '')

    for (const line of cleaned.split('\n')) {
      if (!line) continue
      const stripped = line.trim()
      if (stripped.startsWith('{"type":') && stripped.endsWith('}')) {
        continue
      }
      appendLine(line)
    }

    if (waiting && terminalInstance) {
      terminalInstance.write('\r\n> ')
    }
  }

  function handleStdout(data: string) {
    appendBatch(data)
  }

  function handleStderr(data: string) {
    appendLine(`\x1b[31m❌ ${data}\x1b[0m`)
  }

  function clear() {
    if (terminalInstance) {
      terminalInstance.clear()
    }
    lines.value = []
  }

  function destroy() {
    if (flushTimer) {
      clearTimeout(flushTimer)
      flushTimer = null
    }
    terminalInstance = null
  }

  return {
    lines,
    bindTerminal,
    appendLine,
    appendBatch,
    handleStdout,
    handleStderr,
    clear,
    destroy,
  }
})
