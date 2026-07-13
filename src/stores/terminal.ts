import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useTerminalStore = defineStore('terminal', () => {
  const lines = ref<string[]>([])
  const MAX_LINES = 5000

  let terminalInstance: any = null
  const earlyBuffer: string[] = []
  const waitingForInput = ref(false)
  // 终端模式：'python' = Python 控制台，'shell' = 系统终端
  const terminalMode = ref<'python' | 'shell'>('python')
  // shell 运行命令回调（由 TerminalPanel 注册）
  let shellRunCallback: ((cmd: string) => void) | null = null

  function registerShellRunner(callback: (cmd: string) => void) {
    shellRunCallback = callback
  }

  function runInShell(cmd: string) {
    shellRunCallback?.(cmd)
  }

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

  const MAX_PENDING = 10240 // 缓冲上限 10KB

  // 高频输出节流：收集到缓冲区，每帧只写一次到 xterm
  let pendingText = ''
  let flushTimer: number | null = null

  function appendBatch(text: string) {
    pendingText += text
    if (pendingText.length > MAX_PENDING) {
      pendingText = pendingText.slice(-MAX_PENDING)
    }
    if (!flushTimer) {
      flushTimer = requestAnimationFrame(flush)
    }
  }

  function flush() {
    if (!pendingText) {
      flushTimer = null
      return
    }

    const text = pendingText
    pendingText = ''
    flushTimer = null

    const waiting = text.includes('__BINGO_WAITING_INPUT__')
    const cleaned = text.replace('__BINGO_WAITING_INPUT__', '')

    // 超过 8KB 只保留最新部分，避免 xterm 渲染阻塞 UI
    const maxLen = 8192
    const trimmed = cleaned.length > maxLen ? cleaned.slice(-maxLen) : cleaned

    const parts = trimmed.split('\n')
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
    registerShellRunner,
    runInShell,
    bindTerminal,
    appendLine,
    writeRaw,
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
