import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useTerminalStore = defineStore('terminal', () => {
  const lines = ref<string[]>([])
  const MAX_LINES = 5000
  const FLUSH_INTERVAL_MS = 30

  let pendingText = ''
  let flushTimer: ReturnType<typeof setTimeout> | null = null
  let terminalInstance: any = null
  const earlyBuffer: string[] = []
  const waitingForInput = ref(false)
  // 终端模式：'python' = Python 控制台，'shell' = 系统终端
  const terminalMode = ref<'python' | 'shell'>('python')

  function bindTerminal(terminal: any) {
    terminalInstance = terminal
    for (const line of earlyBuffer) {
      terminalInstance.writeln(line)
    }
    earlyBuffer.length = 0
    if (lines.value.length > 0) {
      terminalInstance.scrollToBottom()
    }
  }

  function appendLine(text: string) {
    lines.value.push(text)
    if (lines.value.length > MAX_LINES) {
      const excess = lines.value.length - MAX_LINES
      lines.value.splice(0, excess)
    }
    if (terminalInstance) {
      terminalInstance.writeln(text)
    } else {
      earlyBuffer.push(text)
    }
  }

  function writeRaw(text: string) {
    if (terminalInstance) {
      terminalInstance.write(text)
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

    const parts = cleaned.split('\n')
    // 找到最后一个非空片段，用 writeRaw（不追加换行），让光标停在同一行
    let lastNonEmptyIdx = -1
    for (let i = parts.length - 1; i >= 0; i--) {
      if (parts[i].length > 0) { lastNonEmptyIdx = i; break }
    }
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      const stripped = part.trim()
      if (stripped.startsWith('{"type":') && stripped.endsWith('}')) {
        continue
      }
      if (i === lastNonEmptyIdx) {
        writeRaw(part)
      } else if (i < parts.length - 1) {
        appendLine(part)
      } else if (part) {
        writeRaw(part)
      }
    }

    if (waiting) {
      waitingForInput.value = true
    }
  }

  function handleStdout(data: string) {
    appendBatch(data)
  }

  function handleStderr(data: string) {
    appendBatch(`\x1b[31m❌ ${data}\x1b[0m`)
  }

  function consumeInput() {
    waitingForInput.value = false
  }

  function resetInputState() {
    waitingForInput.value = false
  }

  function flushNow() {
    if (flushTimer) {
      clearTimeout(flushTimer)
      flushTimer = null
    }
    if (pendingText) {
      flush()
    }
  }

  function clear() {
    earlyBuffer.length = 0
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
    waitingForInput,
    terminalMode,
    bindTerminal,
    appendLine,
    appendBatch,
    handleStdout,
    handleStderr,
    flushNow,
    consumeInput,
    resetInputState,
    clear,
    destroy,
  }
})
